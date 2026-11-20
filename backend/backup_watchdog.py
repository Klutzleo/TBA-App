"""
Backup watchdog.

GitHub's own scheduler does not run this repo's scheduled workflows reliably: the 10:17 UTC nightly backup never fired, and the 10-minute uptime
check ran about every 8 hours. A backup that depends on that is not a backup. So the app, which is always running, checks every hour whether
each job is due and, if it is, starts the existing workflow through GitHub's `workflow_dispatch` API. The workflows themselves are unchanged and
still run on their own schedule when GitHub does fire them; the watchdog only fills the gaps.

Due means: a job has a daily or monthly boundary (the time it is scheduled for). If the most recent boundary has passed and there is no
successful run since it, the job is due. It then starts it, unless a run is already in progress or a run was started in the last 6 hours (a failed
run needs a person, not a retry loop).

Needs one secret, GITHUB_DISPATCH_TOKEN, a fine-grained GitHub token for this repository only with "Actions: read and write". Without it the
watchdog does nothing and says so on the admin Status tab. The token is read from the environment, sent only to api.github.com, and never logged,
stored or returned.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

GITHUB_REPO = os.getenv("GITHUB_REPO", "Klutzleo/TBA-App")
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 300      # let a fresh deploy settle before the first look
RETRY_GAP = timedelta(hours=6)       # never start the same job more often than this
IN_PROGRESS_WINDOW = timedelta(hours=3)

# (workflow file, label, schedule). Same times as the cron lines in the workflows.
JOBS = (
    {"file": "backup.yml", "label": "Nightly backup", "kind": "daily", "hour": 10, "minute": 17},
    {"file": "restore-drill.yml", "label": "Restore drill", "kind": "monthly", "day": 1, "hour": 11, "minute": 43},
)

STATE = {"enabled": False, "last_check": None, "last_started": {}, "last_error": None}
_task = None


def token() -> str | None:
    return (os.getenv("GITHUB_DISPATCH_TOKEN") or "").strip() or None


def due_boundary(job: dict, now: datetime) -> datetime:
    """The most recent time this job was supposed to run, at or before `now` (UTC)."""
    if job["kind"] == "daily":
        b = now.replace(hour=job["hour"], minute=job["minute"], second=0, microsecond=0)
        return b if b <= now else b - timedelta(days=1)
    b = now.replace(day=job["day"], hour=job["hour"], minute=job["minute"], second=0, microsecond=0)
    if b <= now:
        return b
    prev_month_last_day = now.replace(day=1) - timedelta(days=1)
    return prev_month_last_day.replace(day=job["day"], hour=job["hour"], minute=job["minute"], second=0, microsecond=0)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def decide(job: dict, runs: list, now: datetime) -> tuple[bool, str]:
    """Pure decision: should this job be started now? Returns (start, reason). `runs` is GitHub's workflow_runs list, newest first."""
    boundary = due_boundary(job, now)
    for r in runs:
        created = _parse(r["created_at"])
        if r.get("status") != "completed" and now - created < IN_PROGRESS_WINDOW:
            return False, "a run is already in progress"
    if any(r.get("conclusion") == "success" and _parse(r["created_at"]) >= boundary for r in runs):
        return False, "already ran since the last scheduled time"
    if runs and now - _parse(runs[0]["created_at"]) < RETRY_GAP:
        return False, "a run was started in the last 6 hours"
    return True, "due"


def _headers() -> dict:
    return {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token()}", "X-GitHub-Api-Version": "2022-11-28"}


def check_once(now: datetime | None = None) -> list:
    """One pass over every job. Blocking (uses requests); call it from a thread. Returns what it did, for tests and the Status tab."""
    now = now or datetime.now(timezone.utc)
    STATE["enabled"] = bool(token())
    STATE["last_check"] = now.isoformat()
    actions = []
    if not token():
        return actions
    for job in JOBS:
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{job['file']}/runs",
                             params={"per_page": 10}, headers=_headers(), timeout=10)
            if r.status_code != 200:
                STATE["last_error"] = f"{job['label']}: could not read runs (HTTP {r.status_code})"
                actions.append((job["file"], "error", STATE["last_error"]))
                continue
            start, reason = decide(job, r.json().get("workflow_runs", []), now)
            if not start:
                actions.append((job["file"], "skip", reason))
                continue
            d = requests.post(f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{job['file']}/dispatches",
                              json={"ref": "main"}, headers=_headers(), timeout=10)
            if d.status_code == 204:
                STATE["last_started"][job["file"]] = now.isoformat()
                STATE["last_error"] = None
                logger.warning(f"backup_watchdog: started {job['label']} (GitHub had not run it on schedule)")
                actions.append((job["file"], "started", reason))
            else:
                STATE["last_error"] = f"{job['label']}: GitHub refused the start (HTTP {d.status_code})"
                logger.error(f"backup_watchdog: {STATE['last_error']}")
                actions.append((job["file"], "error", STATE["last_error"]))
        except Exception as e:  # never let the watchdog die; never put a secret in the message
            STATE["last_error"] = f"{job['label']}: {type(e).__name__}"
            logger.error(f"backup_watchdog: {STATE['last_error']}")
            actions.append((job["file"], "error", STATE["last_error"]))
    return actions


async def _worker():
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(check_once)
        except Exception as e:
            logger.error(f"backup_watchdog: pass failed ({type(e).__name__})")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start_workers():
    """Call once from backend/app.py's lifespan() startup."""
    global _task
    STATE["enabled"] = bool(token())
    _task = asyncio.create_task(_worker())
    logger.info(f"backup_watchdog: {'on' if token() else 'OFF (no GITHUB_DISPATCH_TOKEN)'}")


async def stop_workers():
    """Call once from backend/app.py's lifespan() shutdown."""
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


def status() -> dict:
    """What the admin Status tab shows. Never includes the token."""
    return {"enabled": bool(token()), "last_check": STATE["last_check"], "last_started": dict(STATE["last_started"]), "last_error": STATE["last_error"]}
