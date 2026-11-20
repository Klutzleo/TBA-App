"""
Security events and server errors (admin center, phase E).

A small, safe event log so the admin can see what is happening: blocked signups, failed logins, rate-limit hits and unhandled server errors.

Privacy and safety rules:
- No raw IP address is stored, only a short salted hash (enough to tell "the same source again" without keeping the address).
- No email, password, token or request body is ever stored. A failed login records only whether the account exists (its id) and the hash.
- Server errors keep the exception class, where it was raised and, for non-database errors, a short message. Database errors can carry
  query parameters, so their message is dropped.
- Recording must never break a request: every failure is swallowed, writes are capped per minute (an attack must not fill the database),
  and old rows are pruned.
"""
import hashlib
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from backend.models import SecurityEvent

logger = logging.getLogger(__name__)

KINDS = ("signup_blocked", "login_failed", "login_suspended", "rate_limited", "server_error")
RETENTION_DAYS = 30
MAX_PER_MINUTE = 300
_PRUNE_EVERY = 200

_lock = threading.Lock()
_window_start = 0.0
_window_count = 0
_since_prune = 0


def ip_hash(ip) -> str | None:
    if not ip:
        return None
    salt = os.getenv("SECRET_KEY", "tba")
    return hashlib.sha256(f"{salt}|{ip}".encode()).hexdigest()[:12]


def client_ip(request) -> str | None:
    """First hop of X-Forwarded-For when the proxy set it, else the socket address. Only used to group events, never to make a decision."""
    try:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None


def _allowed() -> bool:
    global _window_start, _window_count
    now = time.monotonic()
    with _lock:
        if now - _window_start >= 60:
            _window_start, _window_count = now, 0
        _window_count += 1
        return _window_count <= MAX_PER_MINUTE


def record_event(kind: str, request=None, user_id=None, path: str | None = None, **detail) -> None:
    """Write one event. Never raises and never blocks the caller for long."""
    global _since_prune
    try:
        if kind not in KINDS or not _allowed():
            return
        from backend.db import SessionLocal
        db = SessionLocal()
        try:
            db.add(SecurityEvent(kind=kind, ip_hash=ip_hash(client_ip(request)) if request is not None else None, user_id=user_id,
                                 path=(path or (request.url.path if request is not None else None)), detail=detail))
            db.commit()
            _since_prune += 1
            if _since_prune >= _PRUNE_EVERY:
                _since_prune = 0
                db.query(SecurityEvent).filter(SecurityEvent.created_at < datetime.utcnow() - timedelta(days=RETENTION_DAYS)).delete()
                db.commit()
        finally:
            db.close()
    except Exception as e:  # logging must never become the outage
        logger.debug(f"security event not recorded: {type(e).__name__}")


def describe_exception(exc: BaseException) -> dict:
    """What is safe and useful to keep about an unhandled exception."""
    import traceback
    mod = type(exc).__module__ or ""
    out = {"error": type(exc).__name__}
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    if frames:
        f = frames[-1]
        out["where"] = f"{os.path.basename(f.filename)}:{f.lineno} in {f.name}"
    if not mod.startswith(("sqlalchemy", "psycopg2", "sqlite3")):
        out["message"] = str(exc).splitlines()[0][:200] if str(exc) else ""
    return out
