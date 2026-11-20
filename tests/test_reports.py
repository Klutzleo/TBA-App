"""
Admin center, phase B: player and bug reports, the admin inbox, the evidence view and the audit log.
Handlers are called directly (the dependency wiring is covered by checking require_admin on its own).
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_reports.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture
def w(monkeypatch):
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Message, MessageRecipient, User
    from backend.models import AdminAuditLog, Notification, Report
    init_db()
    db = SessionLocal()
    for model in (Report, AdminAuditLog, Notification):  # the test DB is shared across tests: start each from empty
        db.query(model).delete()
    db.commit()
    tag = uuid.uuid4().hex[:8]
    u = {}
    for n in ("admin", "sw", "alice", "bob", "carol", "outsider"):
        u[n] = User(id=uuid.uuid4(), email=f"{n}_{tag}@example.com", username=f"{n}_{tag}", hashed_password="x")
        db.add(u[n])
    db.commit()
    monkeypatch.setenv("ADMIN_USER_IDS", str(u["admin"].id))
    monkeypatch.setenv("MODERATION_EMAIL", "")
    camp = Campaign(id=uuid.uuid4(), name=f"Reports {tag}", description="x" * 12, created_by_user_id=u["sw"].id, created_by_id=str(u["sw"].id),
                    story_weaver_id=u["sw"].id, join_code=tag[:6].upper())
    db.add(camp)
    db.commit()
    for n in ("sw", "alice", "bob", "carol"):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u[n].id, role="story_weaver" if n == "sw" else "player"))
    db.commit()
    t = datetime.utcnow() - timedelta(minutes=30)
    counter = [0]

    def say(who, text, whisper_to=None):
        counter[0] += 1
        m = Message(id=uuid.uuid4(), campaign_id=camp.id, sender_id=u[who].id, sender_name=who, message_type="chat",
                    mode="WHISPER" if whisper_to else "IC", content=text, created_at=t + timedelta(seconds=counter[0]))
        db.add(m)
        db.flush()
        for r in whisper_to or []:
            db.add(MessageRecipient(message_id=m.id, user_id=u[r].id))
        db.commit()
        return m

    yield dict(db=db, u=u, camp=camp, say=say, tag=tag)
    db.close()


def _report(w, who, reported, message=None, reason="harassment", note=None):
    from routes.reports import PlayerReport, report_player
    return report_player(PlayerReport(campaign_id=w["camp"].id, reported_user_id=w["u"][reported].id, message_id=message.id if message else None,
                                      reason=reason, note=note), BackgroundTasks(), w["u"][who], w["db"])


def test_player_report_snapshot_has_the_message_and_its_surroundings(w):
    w["say"]("alice", "hi")
    bad = w["say"]("bob", "something awful")
    w["say"]("carol", "whoa")
    assert _report(w, "alice", "bob", bad)["status"] == "reported"
    from backend.models import Report
    r = w["db"].query(Report).filter(Report.reporter_user_id == w["u"]["alice"].id).one()
    assert r.snapshot["message"]["text"] == "something awful"
    assert [m["text"] for m in r.snapshot["context"]] == ["hi", "something awful", "whoa"]
    assert r.snapshot["reported_username"] == w["u"]["bob"].username


def test_report_cannot_expose_a_whisper_the_reporter_was_not_part_of(w):
    secret = w["say"]("bob", "whisper to carol", whisper_to=["carol"])
    w["say"]("bob", "public line")
    with pytest.raises(HTTPException) as e:
        _report(w, "alice", "bob", secret)  # alice cannot see this whisper, so she cannot report it
    assert e.value.status_code == 404
    from backend.models import Report
    assert w["db"].query(Report).count() == 0 or all("whisper to carol" not in str(r.snapshot) for r in w["db"].query(Report).all())
    # a report on a public message must not pull the secret whisper into its context either
    pub = w["say"]("bob", "mean public line")
    _report(w, "alice", "bob", pub)
    r = w["db"].query(Report).filter(Report.reporter_user_id == w["u"]["alice"].id).one()
    assert "whisper to carol" not in str(r.snapshot)


def test_reporter_must_be_a_member_and_target_must_be_in_the_campaign(w):
    with pytest.raises(HTTPException) as e:
        _report(w, "outsider", "bob")
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        _report(w, "alice", "outsider")
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        _report(w, "alice", "alice")
    assert e.value.status_code == 400


def test_duplicate_and_rate_limit(w):
    assert _report(w, "alice", "bob")["status"] == "reported"
    assert _report(w, "alice", "bob")["status"] == "already_reported"
    from routes.reports import BugReport, report_bug
    for i in range(4):
        report_bug(BugReport(description=f"something broke number {i}"), BackgroundTasks(), w["u"]["alice"], w["db"])
    with pytest.raises(HTTPException) as e:
        report_bug(BugReport(description="one more thing broke"), BackgroundTasks(), w["u"]["alice"], w["db"])
    assert e.value.status_code == 429


def test_bug_report_needs_a_real_description():
    from pydantic import ValidationError
    from routes.reports import BugReport
    with pytest.raises(ValidationError):
        BugReport(description="short")


def test_admin_endpoints_are_admin_only(w):
    from routes.moderation import require_admin
    with pytest.raises(HTTPException) as e:
        require_admin(w["u"]["alice"])
    assert e.value.status_code == 403
    assert require_admin(w["u"]["admin"]) is w["u"]["admin"]


def test_admin_alert_is_a_bell_notification(w):
    _report(w, "alice", "bob")
    from backend.models import Notification
    n = w["db"].query(Notification).filter(Notification.user_id == w["u"]["admin"].id).all()
    assert n and "New player report" in n[0].title


def test_inbox_lists_reporter_to_admin_and_update_is_audited(w):
    _report(w, "alice", "bob", note="he keeps doing it")
    from routes.reports import UpdateReport, audit_log, get_report, list_reports, update_report
    items = list_reports("all", "active", w["u"]["admin"], w["db"])["reports"]
    assert len(items) == 1 and items[0]["reporter"] == w["u"]["alice"].username and items[0]["reported"] == w["u"]["bob"].username
    rid = uuid.UUID(items[0]["id"])
    assert get_report(rid, w["u"]["admin"], w["db"])["note"] == "he keeps doing it"
    update_report(rid, UpdateReport(status="resolved", admin_note="spoke to them"), w["u"]["admin"], w["db"])
    assert list_reports("all", "active", w["u"]["admin"], w["db"])["reports"] == []
    assert list_reports("all", "resolved", w["u"]["admin"], w["db"])["reports"][0]["id"] == str(rid)
    entries = audit_log(100, w["u"]["admin"], w["db"])["entries"]
    assert entries[0]["action"] == "report_updated" and entries[0]["detail"]["status_to"] == "resolved"


def test_conversation_view_is_pair_only_and_audit_logged(w):
    w["say"]("alice", "to bob", whisper_to=["bob"])
    w["say"]("bob", "back to alice", whisper_to=["alice"])
    w["say"]("bob", "bob to carol", whisper_to=["carol"])      # not part of this pair: must never show
    w["say"]("carol", "carol to alice", whisper_to=["alice"])  # not from the pair: must never show
    w["say"]("bob", "a public line")
    _report(w, "alice", "bob")
    from backend.models import Report
    rid = w["db"].query(Report).one().id
    from routes.reports import audit_log, open_conversation
    out = open_conversation(rid, w["u"]["admin"], w["db"])
    texts = [m["text"] for m in out["messages"]]
    assert texts == ["to bob", "back to alice", "a public line"]
    assert [m["private"] for m in out["messages"]] == [True, True, False]
    log = audit_log(100, w["u"]["admin"], w["db"])["entries"]
    assert log[0]["action"] == "conversation_opened" and log[0]["report_id"] == str(rid)
    open_conversation(rid, w["u"]["admin"], w["db"])
    assert [e["action"] for e in audit_log(100, w["u"]["admin"], w["db"])["entries"]].count("conversation_opened") == 2


def test_no_conversation_for_a_bug_report(w):
    from routes.reports import BugReport, open_conversation, report_bug
    report_bug(BugReport(description="the dice button is stuck"), BackgroundTasks(), w["u"]["alice"], w["db"])
    from backend.models import Report
    with pytest.raises(HTTPException) as e:
        open_conversation(w["db"].query(Report).one().id, w["u"]["admin"], w["db"])
    assert e.value.status_code == 404
