"""
Admin center, phase E: security events and the server-error feed.
Privacy: no raw IPs, emails or database parameters are stored. Safety: recording never breaks a request and is capped.
"""
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_security_events.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.app import application
    from backend.db import init_db
    init_db()
    return TestClient(application, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    from backend import security_events
    from backend.db import SessionLocal
    from backend.models import SecurityEvent
    from routes.auth import limiter
    limiter.reset()
    security_events._window_start, security_events._window_count = 0.0, 0
    for k in ("TURNSTILE_SECRET_KEY", "TURNSTILE_SITE_KEY"):
        monkeypatch.delenv(k, raising=False)
    db = SessionLocal()
    db.query(SecurityEvent).delete()
    db.commit()
    db.close()


def _route(path, fn):
    """Add a test route in front of the app's catch-all static mount (a route added after the mount never matches)."""
    from fastapi.routing import APIRoute
    from backend.app import application
    application.router.routes.insert(0, APIRoute(path, fn))


def _events(kind=None):
    from backend.db import SessionLocal
    from backend.models import SecurityEvent
    db = SessionLocal()
    try:
        q = db.query(SecurityEvent)
        if kind:
            q = q.filter(SecurityEvent.kind == kind)
        return q.order_by(SecurityEvent.created_at).all()
    finally:
        db.close()


def _signup(client, **extra):
    tag = uuid.uuid4().hex[:8]
    body = {"email": f"person_{tag}@example.com", "username": f"person_{tag}", "password": "A-good-password-1"}
    body.update(extra)
    return client.post("/api/auth/register", json=body), body


def test_blocked_signups_are_recorded_by_reason(client):
    assert _signup(client, website="i am a bot")[0].status_code == 400
    r, body = _signup(client)
    r2 = client.post("/api/auth/register", json={**body, "email": f"x_{uuid.uuid4().hex[:6]}@mailinator.com", "username": f"u_{uuid.uuid4().hex[:6]}"})
    assert r2.status_code == 400
    reasons = sorted(e.detail["reason"] for e in _events("signup_blocked"))
    assert reasons == ["disposable_email", "honeypot"]


def test_failed_login_records_that_but_never_the_email_or_password(client):
    email = f"nobody_{uuid.uuid4().hex[:6]}@example.com"
    assert client.post("/api/auth/login", json={"email": email, "password": "Wrong-password-9"}).status_code == 401
    ev = _events("login_failed")
    assert len(ev) == 1 and ev[0].detail == {"account_exists": False} and ev[0].user_id is None
    blob = str([(e.detail, e.path, e.ip_hash) for e in _events()])
    assert email not in blob and "Wrong-password-9" not in blob


def test_failed_login_for_a_real_account_records_the_account_id_only(client):
    r, body = _signup(client)
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"email": body["email"], "password": "Not-the-password-1"}).status_code == 401
    ev = _events("login_failed")[0]
    assert ev.detail == {"account_exists": True} and str(ev.user_id) == r.json()["user_id"]


def test_ip_is_stored_only_as_a_short_hash(client):
    _signup(client, website="bot")
    e = _events("signup_blocked")[0]
    assert e.ip_hash and len(e.ip_hash) == 12 and "testclient" not in e.ip_hash and "127.0.0.1" not in e.ip_hash
    from backend.security_events import ip_hash
    assert ip_hash("1.2.3.4") == ip_hash("1.2.3.4") != ip_hash("1.2.3.5")


def test_rate_limit_hits_are_recorded(client):
    for _ in range(11):
        _signup(client, website="bot")  # the 11th in an hour is refused by the limiter
    assert len(_events("rate_limited")) >= 1


def test_an_unhandled_error_is_recorded_without_database_parameters_and_the_client_gets_a_plain_500(client):
    async def boom():
        raise ValueError("something broke with value 42")

    async def db_boom():
        from sqlalchemy.exc import IntegrityError
        raise IntegrityError("INSERT INTO users VALUES (:e)", {"e": "secret@example.com"}, Exception("dup"))

    _route("/api/public/_test_boom", boom)
    _route("/api/public/_test_dbboom", db_boom)
    r = client.get("/api/public/_test_boom")
    assert r.status_code == 500 and r.json() == {"detail": "Internal Server Error"}
    assert client.get("/api/public/_test_dbboom").status_code == 500
    errs = _events("server_error")
    assert len(errs) == 2
    plain = next(e for e in errs if e.detail["error"] == "ValueError")
    assert plain.detail["message"] == "something broke with value 42" and "test_security_events.py" in plain.detail["where"] and plain.detail["request_id"]
    db_err = next(e for e in errs if e.detail["error"] == "IntegrityError")
    assert "message" not in db_err.detail and "secret@example.com" not in str([e.detail for e in errs])


def test_recording_never_breaks_the_caller(monkeypatch):
    from backend import security_events
    import backend.db as dbmod

    def broken():
        raise RuntimeError("database is down")

    monkeypatch.setattr(dbmod, "SessionLocal", broken)
    security_events.record_event("login_failed", None)  # must not raise
    security_events.record_event("not_a_kind", None)    # unknown kinds are ignored


def test_writes_are_capped_per_minute(monkeypatch):
    from backend import security_events
    monkeypatch.setattr(security_events, "MAX_PER_MINUTE", 3)
    for _ in range(10):
        security_events.record_event("rate_limited", None)
    assert len(_events("rate_limited")) == 3


def test_old_events_are_pruned(monkeypatch):
    from datetime import datetime, timedelta
    from backend import security_events
    from backend.db import SessionLocal
    from backend.models import SecurityEvent
    db = SessionLocal()
    db.add(SecurityEvent(kind="login_failed", created_at=datetime.utcnow() - timedelta(days=45), detail={}))
    db.commit()
    db.close()
    monkeypatch.setattr(security_events, "_PRUNE_EVERY", 1)
    monkeypatch.setattr(security_events, "_since_prune", 0)
    security_events.record_event("login_failed", None)
    assert len(_events("login_failed")) == 1  # the 45 day old row is gone, the new one stays


def test_admin_summary_and_error_feed(client):
    from backend.db import SessionLocal
    from backend.models import User
    from routes.admin_security import errors, summary
    _signup(client, website="bot")
    _signup(client, website="bot")
    client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Wrong-password-9"})
    _route("/api/public/_test_boom2", lambda: 1 / 0)
    client.get("/api/public/_test_boom2")
    client.get("/api/public/_test_boom2")
    db = SessionLocal()
    try:
        admin = User(id=uuid.uuid4(), email=f"a_{uuid.uuid4().hex[:6]}@example.com", username=f"a_{uuid.uuid4().hex[:6]}", hashed_password="x")
        s = summary(24, admin, db)
        assert s["counts"]["signup_blocked"] == 2 and s["counts"]["login_failed"] == 1 and s["counts"]["server_error"] == 2
        assert s["signup_block_reasons"] == {"honeypot": 2}
        assert s["busiest_sources"] and s["busiest_sources"][0]["count"] >= 2
        assert all(e["kind"] != "server_error" for e in s["recent"])
        e = errors(72, 50, admin, db)
        assert e["total"] == 2 and e["groups"][0]["count"] == 2 and e["groups"][0]["error"] == "ZeroDivisionError"
    finally:
        db.close()


def test_security_views_are_admin_only():
    from fastapi import HTTPException
    from types import SimpleNamespace
    from routes.moderation import require_admin
    with pytest.raises(HTTPException):
        require_admin(SimpleNamespace(id=uuid.uuid4()))
