"""Admin center, phase E: what the security log and the server-error feed show the admin. Read-only."""
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import SecurityEvent, User
from backend.security_events import KINDS
from routes.moderation import require_admin

security_router = APIRouter(prefix="/api/admin/security")


def _row(e: SecurityEvent) -> dict:
    return {"id": str(e.id), "kind": e.kind, "source": e.ip_hash, "path": e.path, "detail": e.detail or {},
            "at": e.created_at.isoformat() if e.created_at else None}


@security_router.get("/summary")
def summary(hours: int = Query(24, ge=1, le=720), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Counts per kind in the window, signup blocks by reason, the busiest sources, and the latest non-error events."""
    since = datetime.utcnow() - timedelta(hours=hours)
    counts = {k: 0 for k in KINDS}
    for kind, n in db.query(SecurityEvent.kind, func.count()).filter(SecurityEvent.created_at >= since).group_by(SecurityEvent.kind).all():
        counts[kind] = n
    reasons = Counter()
    for (detail,) in db.query(SecurityEvent.detail).filter(SecurityEvent.kind == "signup_blocked", SecurityEvent.created_at >= since).all():
        reasons[(detail or {}).get("reason", "unknown")] += 1
    # a source with many failures is the thing worth looking at; the hash is not an address and cannot be turned back into one
    busy = db.query(SecurityEvent.ip_hash, SecurityEvent.kind, func.count().label("n")).filter(
        SecurityEvent.created_at >= since, SecurityEvent.ip_hash.isnot(None), SecurityEvent.kind.in_(("login_failed", "signup_blocked", "rate_limited"))
    ).group_by(SecurityEvent.ip_hash, SecurityEvent.kind).order_by(func.count().desc()).limit(8).all()
    recent = db.query(SecurityEvent).filter(SecurityEvent.created_at >= since, SecurityEvent.kind != "server_error").order_by(
        SecurityEvent.created_at.desc()).limit(50).all()
    return {"hours": hours, "counts": counts, "signup_block_reasons": dict(reasons),
            "busiest_sources": [{"source": s, "kind": k, "count": n} for s, k, n in busy], "recent": [_row(e) for e in recent]}


@security_router.get("/errors")
def errors(hours: int = Query(72, ge=1, le=720), limit: int = Query(50, ge=1, le=200), admin: User = Depends(require_admin),
           db: Session = Depends(get_db)):
    """Unhandled server errors, newest first, plus the same error grouped so a single bug that fired 40 times reads as one line."""
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = db.query(SecurityEvent).filter(SecurityEvent.kind == "server_error", SecurityEvent.created_at >= since).order_by(
        SecurityEvent.created_at.desc()).limit(500).all()
    groups = {}
    for e in rows:
        d = e.detail or {}
        key = (d.get("error"), d.get("where"), e.path)
        g = groups.setdefault(key, {"error": d.get("error"), "where": d.get("where"), "path": e.path, "message": d.get("message"),
                                    "count": 0, "last_at": e.created_at.isoformat() if e.created_at else None})
        g["count"] += 1
    return {"hours": hours, "total": len(rows), "groups": sorted(groups.values(), key=lambda g: -g["count"])[:20],
            "latest": [_row(e) for e in rows[:limit]]}
