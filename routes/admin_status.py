"""
Admin center, phase F: one read-only status page for the admin.

Shows: the deployed version, the database and migrations, the latest nightly backup / restore drill / uptime check (from the public GitHub
Actions history), how email and the human check are configured (yes/no only, never a key), error and security counts, and each campaign's health.
Nothing here changes anything, and nothing secret is returned.
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Campaign, CampaignMembership, Character, Encounter, Message, Report, SecurityEvent, User
from routes.moderation import require_admin

logger = logging.getLogger(__name__)

status_router = APIRouter(prefix="/api/admin")

_STARTED = datetime.utcnow()
GITHUB_REPO = os.getenv("GITHUB_REPO", "Klutzleo/TBA-App")
CHECKS = (  # (workflow file, label, how old before it counts as stale)
    ("backup.yml", "Nightly backup", timedelta(hours=36)),
    ("restore-drill.yml", "Restore drill", timedelta(days=35)),
    ("uptime.yml", "Uptime check", timedelta(minutes=90)),
)
_CACHE = {"at": 0.0, "data": None}
_CACHE_SECONDS = 300


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _github_checks() -> list:
    """Latest run of each workflow from the public GitHub API (no token, so it only sees public information). Cached for five minutes so a
    busy admin page cannot burn GitHub's anonymous rate limit. A failure is reported as unknown, never as healthy."""
    if _CACHE["data"] is not None and time.monotonic() - _CACHE["at"] < _CACHE_SECONDS:
        return _CACHE["data"]
    out = []
    now = datetime.now(timezone.utc)
    for wf, label, max_age in CHECKS:
        item = {"name": label, "state": "unknown", "detail": "Could not reach GitHub", "at": None}
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{wf}/runs",
                             params={"per_page": 1}, headers={"Accept": "application/vnd.github+json"}, timeout=5)
            if r.ok:
                runs = r.json().get("workflow_runs", [])
                if not runs:
                    item.update(state="unknown", detail="No runs yet")
                else:
                    run = runs[0]
                    when = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                    ok = run.get("conclusion") == "success"
                    running = run.get("status") != "completed"
                    stale = now - when > max_age
                    state = "running" if running else ("good" if ok and not stale else "bad")
                    detail = ("Running now" if running else (run.get("conclusion") or "unknown")) + (", and it is overdue" if stale and not running else "")
                    item.update(state=state, detail=detail, at=when.isoformat(), url=run.get("html_url"))
        except Exception as e:
            logger.warning(f"GitHub status check failed: {type(e).__name__}")
        out.append(item)
    if any(i["state"] != "unknown" for i in out):  # do not cache a total failure
        _CACHE.update(at=time.monotonic(), data=out)
    return out


def _live_counts() -> dict:
    try:
        from routes.campaign_websocket import manager
        return {str(cid): len({str(c[1]) for c in conns}) for cid, conns in manager.active_connections.items() if conns}
    except Exception:
        return {}


@status_router.get("/status")
def system_status(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    # database and migrations
    started = time.perf_counter()
    db.execute(text("SELECT 1"))
    ping_ms = round((time.perf_counter() - started) * 1000, 1)
    latest = None
    try:
        row = db.execute(text("SELECT filename, applied_at FROM schema_migrations ORDER BY applied_at DESC, filename DESC LIMIT 1")).first()
        latest = {"file": row[0], "at": _iso(row[1])} if row else None
    except Exception:
        db.rollback()  # SQLite in development has no schema_migrations table

    # errors and security in the last 24 hours
    since = datetime.utcnow() - timedelta(hours=24)
    counts = dict(db.query(SecurityEvent.kind, func.count()).filter(SecurityEvent.created_at >= since).group_by(SecurityEvent.kind).all())
    last_err = db.query(func.max(SecurityEvent.created_at)).filter(SecurityEvent.kind == "server_error").scalar()

    # campaigns, busiest first
    live = _live_counts()
    campaigns = db.query(Campaign).filter(Campaign.is_active == True).all()  # noqa: E712
    ids = [c.id for c in campaigns]
    members = dict(db.query(CampaignMembership.campaign_id, func.count()).filter(CampaignMembership.campaign_id.in_(ids)).group_by(CampaignMembership.campaign_id).all()) if ids else {}
    last_msg = dict(db.query(Message.campaign_id, func.max(Message.created_at)).filter(Message.campaign_id.in_(ids)).group_by(Message.campaign_id).all()) if ids else {}
    fights = {r[0] for r in db.query(Encounter.campaign_id).filter(Encounter.campaign_id.in_(ids), Encounter.is_active == True).all()} if ids else set()  # noqa: E712
    pending = dict(db.query(Character.campaign_id, func.count()).filter(Character.campaign_id.in_(ids), Character.status == "pending_approval").group_by(Character.campaign_id).all()) if ids else {}
    open_reports = dict(db.query(Report.campaign_id, func.count()).filter(Report.campaign_id.in_(ids), Report.status.in_(("open", "reviewing"))).group_by(Report.campaign_id).all()) if ids else {}
    rows = [{"id": str(c.id), "name": c.name, "members": members.get(c.id, 0), "online_now": live.get(str(c.id), 0), "last_message_at": _iso(last_msg.get(c.id)),
             "active_encounter": c.id in fights, "pending_characters": pending.get(c.id, 0), "open_reports": open_reports.get(c.id, 0)} for c in campaigns]
    rows.sort(key=lambda r: r["last_message_at"] or "", reverse=True)

    return {
        "version": {"commit": (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "")[:7] or None, "message": (os.getenv("RAILWAY_GIT_COMMIT_MESSAGE") or "")[:120] or None,
                    "deployment": (os.getenv("RAILWAY_DEPLOYMENT_ID") or "")[:8] or None, "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME"),
                    "started_at": _iso(_STARTED)},
        "database": {"ok": True, "ping_ms": ping_ms, "latest_migration": latest, "accounts": db.query(func.count(User.id)).scalar(),
                     "suspended_accounts": db.query(func.count(User.id)).filter(User.is_active == False).scalar()},  # noqa: E712
        "checks": _github_checks(),
        "config": {"email_configured": bool(os.getenv("RESEND_API_KEY")), "from_email": (os.getenv("FROM_EMAIL") or "").split("@")[-1] or None,
                   "human_check_on": bool(os.getenv("TURNSTILE_SECRET_KEY") and os.getenv("TURNSTILE_SITE_KEY")),
                   "moderation_email_set": bool(os.getenv("MODERATION_EMAIL")), "push_configured": bool(os.getenv("VAPID_PRIVATE_KEY") or os.getenv("VAPID_PUBLIC_KEY"))},
        "last_24h": {"server_errors": counts.get("server_error", 0), "failed_logins": counts.get("login_failed", 0), "blocked_signups": counts.get("signup_blocked", 0),
                     "rate_limited": counts.get("rate_limited", 0), "last_server_error_at": _iso(last_err)},
        "open_reports": db.query(func.count(Report.id)).filter(Report.status.in_(("open", "reviewing"))).scalar(),
        "online_now": sum(live.values()),
        "campaigns": rows,
    }
