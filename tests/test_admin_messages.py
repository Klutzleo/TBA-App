"""Admin center, phase D: the admin can message a player or a campaign (bell, push, email), with saved templates, all audit-logged."""
import os
import uuid
from datetime import datetime

import pytest
from fastapi import BackgroundTasks, HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_admin_messages.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture
def w(monkeypatch):
    from backend.db import SessionLocal, init_db
    from backend.models import AdminAuditLog, AdminTemplate, Campaign, CampaignMembership, Notification, User
    init_db()
    db = SessionLocal()
    for m in (AdminAuditLog, AdminTemplate, Notification):
        db.query(m).delete()
    db.commit()
    tag = uuid.uuid4().hex[:8]
    u = {}
    for n in ("admin", "sw", "alice", "bob", "gone", "banned"):
        u[n] = User(id=uuid.uuid4(), email=f"{n}_{tag}@example.com", username=f"{n}_{tag}", hashed_password="x")
        db.add(u[n])
    db.commit()
    monkeypatch.setenv("ADMIN_USER_IDS", str(u["admin"].id))
    camp = Campaign(id=uuid.uuid4(), name=f"Msg {tag}", description="x" * 12, created_by_user_id=u["sw"].id, created_by_id=str(u["sw"].id),
                    story_weaver_id=u["sw"].id, join_code=tag[:6].upper())
    db.add(camp)
    db.commit()
    for n in ("sw", "alice", "bob", "gone", "banned"):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u[n].id, role="story_weaver" if n == "sw" else "player"))
    db.commit()
    gone = db.query(CampaignMembership).filter(CampaignMembership.user_id == u["gone"].id).first()
    gone.left_at = datetime.utcnow()           # left the campaign: must not be messaged as a member
    u["banned"].is_active = False              # suspended: must not be messaged at all
    db.commit()
    yield dict(db=db, u=u, camp=camp)
    db.close()


def _send(w, **kw):
    from routes.admin_messages import MessageRequest, send_message
    base = dict(subject="Hello there", body="A message from the admin.")
    base.update(kw)
    return send_message(MessageRequest(**base), BackgroundTasks(), w["u"]["admin"], w["db"])


def _bells(w, who):
    from backend.models import Notification
    return w["db"].query(Notification).filter(Notification.user_id == w["u"][who].id).all()


def test_message_one_player_creates_a_bell_and_an_audit_entry(w):
    out = _send(w, target="user", target_id=w["u"]["alice"].id)
    assert out["sent"] is True and out["recipients"] == 1
    assert [n.title for n in _bells(w, "alice")] == ["Hello there"] and _bells(w, "bob") == []
    from routes.reports import audit_log
    e = audit_log(5, w["u"]["admin"], w["db"])["entries"][0]
    assert e["action"] == "message_sent" and e["detail"]["recipients"] == 1 and e["detail"]["body"] == "A message from the admin."


def test_campaign_message_reaches_current_active_members_only(w):
    out = _send(w, target="campaign", target_id=w["camp"].id)
    assert out["recipients"] == 3  # sw, alice, bob. Not the one who left, not the suspended one
    assert _bells(w, "gone") == [] and _bells(w, "banned") == []
    assert len(_bells(w, "sw")) == len(_bells(w, "alice")) == len(_bells(w, "bob")) == 1


def test_dry_run_sends_nothing(w):
    out = _send(w, target="campaign", target_id=w["camp"].id, dry_run=True)
    assert out["sent"] is False and out["recipients"] == 3
    assert _bells(w, "alice") == []
    from backend.models import AdminAuditLog
    assert w["db"].query(AdminAuditLog).count() == 0


def test_cannot_message_a_suspended_player_or_a_missing_one(w):
    with pytest.raises(HTTPException) as e:
        _send(w, target="user", target_id=w["u"]["banned"].id)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        _send(w, target="campaign", target_id=uuid.uuid4())
    assert e.value.status_code == 404


def test_validation_and_admin_only(w):
    from pydantic import ValidationError
    from routes.admin_messages import MessageRequest
    from routes.moderation import require_admin
    with pytest.raises(ValidationError):
        MessageRequest(target="user", target_id=uuid.uuid4(), subject="x", body="too short subject")
    with pytest.raises(ValidationError):
        MessageRequest(target="user", target_id=uuid.uuid4(), subject="Fine", body="ok body", channels=[])
    with pytest.raises(HTTPException):
        require_admin(w["u"]["alice"])


def test_push_and_email_go_to_each_recipient_and_one_failure_does_not_stop_the_rest(w, monkeypatch):
    from routes import admin_messages as am
    pushed, mailed = [], []

    def fake_push(db, user_id, title, body, **kw):
        if user_id == str(w["u"]["alice"].id):
            raise RuntimeError("push service down")
        pushed.append(user_id)

    def fake_mail(addr, subject, body):
        mailed.append(addr)

    import backend.notifications as bn
    monkeypatch.setattr(bn, "send_push", fake_push)
    monkeypatch.setattr(am, "send_admin_message_email", fake_mail)
    ids = [w["u"]["alice"].id, w["u"]["bob"].id]
    am._deliver_slow_channels(ids, {w["u"]["alice"].id: "a@example.com", w["u"]["bob"].id: "b@example.com"}, "Hi there", "body text", ["push", "email"])
    assert pushed == [str(w["u"]["bob"].id)] and mailed == ["a@example.com", "b@example.com"]


def test_bell_only_does_not_queue_push_or_email(w):
    tasks = BackgroundTasks()
    from routes.admin_messages import MessageRequest, send_message
    send_message(MessageRequest(target="user", target_id=w["u"]["alice"].id, subject="Only bell", body="just a bell", channels=["bell"]), tasks, w["u"]["admin"], w["db"])
    assert len(tasks.tasks) == 0
    send_message(MessageRequest(target="user", target_id=w["u"]["alice"].id, subject="Bell and push", body="bell push", channels=["bell", "push"]), tasks, w["u"]["admin"], w["db"])
    assert len(tasks.tasks) == 1


def test_lookup_and_templates(w):
    from routes.admin_messages import TemplateRequest, delete_template, list_templates, lookup, save_template
    res = lookup(w["u"]["alice"].username[:8], w["u"]["admin"], w["db"])
    assert any(x["username"] == w["u"]["alice"].username for x in res["users"])
    assert any(c["name"] == w["camp"].name for c in lookup(w["camp"].name[:6], w["u"]["admin"], w["db"])["campaigns"])
    assert lookup("%", w["u"]["admin"], w["db"]) == {"users": [], "campaigns": []}  # a wildcard is not a way to list everyone
    tid = save_template(TemplateRequest(name="Mine", subject="My subject", body="My body"), w["u"]["admin"], w["db"])["id"]
    names = [t["name"] for t in list_templates(w["u"]["admin"], w["db"])["templates"]]
    assert "Mine" in names and "Behavior warning" in names
    delete_template(uuid.UUID(tid), w["u"]["admin"], w["db"])
    assert "Mine" not in [t["name"] for t in list_templates(w["u"]["admin"], w["db"])["templates"]]
