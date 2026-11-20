"""
Admin center, phase C: the admin can suspend an account. Login and API calls already refused is_active=False; this adds the live chat
connection (closed at once, and refused on reconnect), an audit trail, and no digest email for a suspended account.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suspension.db")
os.environ.setdefault("API_KEY", "devkey")


class FakeWS:
    def __init__(self):
        self.closed = None
        self.sent = []

    async def accept(self, subprotocol=None):
        pass

    async def send_json(self, m):
        self.sent.append(m)

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


@pytest.fixture
def w(monkeypatch):
    from backend.db import SessionLocal, init_db
    from backend.models import AdminAuditLog, User
    init_db()
    db = SessionLocal()
    db.query(AdminAuditLog).delete()
    db.commit()
    tag = uuid.uuid4().hex[:8]
    u = {}
    for n in ("admin", "alice", "bob"):
        u[n] = User(id=uuid.uuid4(), email=f"{n}_{tag}@example.com", username=f"{n}_{tag}", hashed_password="x")
        db.add(u[n])
    db.commit()
    monkeypatch.setenv("ADMIN_USER_IDS", str(u["admin"].id))
    yield dict(db=db, u=u)
    db.close()


def _suspend(w, who, reason="harassment, confirmed"):
    from routes.reports import SuspendRequest, suspend_user
    return asyncio.run(suspend_user(w["u"][who].id, SuspendRequest(reason=reason), None, w["u"]["admin"], w["db"]))


def test_suspend_marks_the_account_and_is_audited(w):
    out = _suspend(w, "bob")
    assert out["suspended"] is True
    w["db"].refresh(w["u"]["bob"])
    b = w["u"]["bob"]
    assert b.is_active is False and b.suspended_at is not None and b.suspension_reason == "harassment, confirmed"
    from routes.reports import audit_log
    e = audit_log(10, w["u"]["admin"], w["db"])["entries"][0]
    assert e["action"] == "user_suspended" and e["detail"]["username"] == b.username and e["admin"] == w["u"]["admin"].username


def test_suspended_account_is_refused_by_the_normal_auth_check(w):
    _suspend(w, "bob")
    from backend.auth.jwt import create_access_token, get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    bob = w["u"]["bob"]
    token = create_access_token(str(bob.id), bob.email, bob.username)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_user(credentials=creds, db=w["db"]))
    assert e.value.status_code == 403
    # and the same token works for someone who is not suspended
    alice = w["u"]["alice"]
    ok = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token(str(alice.id), alice.email, alice.username))
    assert asyncio.run(get_current_user(credentials=ok, db=w["db"])).id == alice.id


def test_live_connections_are_closed_in_every_campaign(w):
    from routes.campaign_websocket import CampaignConnectionManager, manager
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    bob1, bob2, alice = FakeWS(), FakeWS(), FakeWS()
    mgr = CampaignConnectionManager()
    mgr.active_connections[c1] = [(bob1, w["u"]["bob"].id, "b", "b"), (alice, w["u"]["alice"].id, "a", "a")]
    mgr.active_connections[c2] = [(bob2, w["u"]["bob"].id, "b", "b")]
    closed = asyncio.run(mgr.close_user_everywhere(w["u"]["bob"].id, "This account is suspended."))
    assert closed == 2 and bob1.closed == (1008, "This account is suspended.") and bob2.closed[0] == 1008
    assert alice.closed is None and c2 not in mgr.active_connections


def test_suspend_endpoint_closes_the_live_connection(w):
    from routes import campaign_websocket as cw
    cid, sock = uuid.uuid4(), FakeWS()
    cw.manager.active_connections[cid] = [(sock, w["u"]["bob"].id, "b", "b")]
    try:
        out = _suspend(w, "bob")
        assert out["connections_closed"] == 1 and sock.closed[0] == 1008
    finally:
        cw.manager.active_connections.pop(cid, None)


def test_cannot_suspend_an_admin_or_yourself(w):
    from routes.reports import SuspendRequest, suspend_user
    with pytest.raises(HTTPException) as e:
        asyncio.run(suspend_user(w["u"]["admin"].id, SuspendRequest(reason="oops"), None, w["u"]["admin"], w["db"]))
    assert e.value.status_code == 400
    w["db"].refresh(w["u"]["admin"])
    assert w["u"]["admin"].is_active is True


def test_unsuspend_restores_and_is_audited(w):
    _suspend(w, "bob")
    from routes.reports import audit_log, unsuspend_user
    unsuspend_user(w["u"]["bob"].id, None, w["u"]["admin"], w["db"])
    w["db"].refresh(w["u"]["bob"])
    b = w["u"]["bob"]
    assert b.is_active is True and b.suspended_at is None and b.suspension_reason is None
    assert audit_log(10, w["u"]["admin"], w["db"])["entries"][0]["action"] == "user_unsuspended"


def test_suspend_requires_admin_and_a_reason(w):
    from pydantic import ValidationError
    from routes.moderation import require_admin
    from routes.reports import SuspendRequest
    with pytest.raises(HTTPException):
        require_admin(w["u"]["alice"])
    with pytest.raises(ValidationError):
        SuspendRequest(reason="")


def test_report_detail_tells_the_admin_if_the_person_is_suspended(w):
    from backend.models import Report
    r = Report(kind="player", reporter_user_id=w["u"]["alice"].id, reported_user_id=w["u"]["bob"].id, reason="harassment", snapshot={})
    w["db"].add(r)
    w["db"].commit()
    from routes.reports import get_report
    assert get_report(r.id, w["u"]["admin"], w["db"])["reported_suspended"] is False
    _suspend(w, "bob")
    assert get_report(r.id, w["u"]["admin"], w["db"])["reported_suspended"] is True
