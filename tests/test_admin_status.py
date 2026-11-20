"""Admin center, phase F: the read-only status page. It must never report a check as healthy when it could not tell, and never return a secret."""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_admin_status.db")
os.environ.setdefault("API_KEY", "devkey")


class FakeResp:
    def __init__(self, runs=None, ok=True):
        self.ok, self._runs = ok, runs

    def json(self):
        return {"workflow_runs": self._runs or []}


def _run(age, conclusion="success", status="completed"):
    return {"created_at": (datetime.now(timezone.utc) - age).isoformat().replace("+00:00", "Z"), "conclusion": conclusion, "status": status,
            "html_url": "https://github.com/x/y/actions/runs/1"}


@pytest.fixture
def w(monkeypatch):
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, Encounter, Message, Report, SecurityEvent, User
    from routes import admin_status
    init_db()
    db = SessionLocal()
    admin_status._CACHE.update(at=0.0, data=None)
    tag = uuid.uuid4().hex[:8]
    u = {n: User(id=uuid.uuid4(), email=f"{n}_{tag}@example.com", username=f"{n}_{tag}", hashed_password="x") for n in ("admin", "sw", "p1")}
    db.add_all(u.values())
    db.commit()
    monkeypatch.setenv("ADMIN_USER_IDS", str(u["admin"].id))
    camp = Campaign(id=uuid.uuid4(), name=f"Health {tag}", description="x" * 12, created_by_user_id=u["sw"].id, created_by_id=str(u["sw"].id),
                    story_weaver_id=u["sw"].id, join_code=tag[:6].upper())
    db.add(camp)
    db.commit()
    for n in ("sw", "p1"):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u[n].id, role="story_weaver" if n == "sw" else "player"))
    db.add(Message(id=uuid.uuid4(), campaign_id=camp.id, sender_id=u["p1"].id, sender_name="p1", message_type="chat", mode="IC", content="hi"))
    db.add(Encounter(id=uuid.uuid4(), campaign_id=camp.id, is_active=True))
    db.add(Character(id=uuid.uuid4(), name=f"Pend {tag}", owner_id=str(u["p1"].id), user_id=u["p1"].id, campaign_id=camp.id, level=1, pp=2, ip=2, sp=2, dp=10,
                     max_dp=10, edge=1, attack_style="1d6", defense_die="1d4", status="pending_approval"))
    db.add(Report(kind="bug", reporter_user_id=u["p1"].id, campaign_id=camp.id, reason="bug", note="x" * 12, snapshot={}))
    db.commit()
    yield dict(db=db, u=u, camp=camp)
    db.close()


def _status(w):
    from routes.admin_status import system_status
    return system_status(w["u"]["admin"], w["db"])


def _github(monkeypatch, backup, restore, uptime):
    seq = iter([backup, restore, uptime])
    import routes.admin_status as m
    monkeypatch.setattr(m.requests, "get", lambda *a, **k: next(seq))


def test_checks_show_good_bad_and_overdue(monkeypatch, w):
    _github(monkeypatch, FakeResp([_run(timedelta(hours=5))]), FakeResp([_run(timedelta(days=3), conclusion="failure")]), FakeResp([_run(timedelta(hours=5))]))
    c = {x["name"]: x for x in _status(w)["checks"]}
    assert c["Nightly backup"]["state"] == "good"
    assert c["Restore drill"]["state"] == "bad" and "failure" in c["Restore drill"]["detail"]
    assert c["Uptime check"]["state"] == "bad" and "overdue" in c["Uptime check"]["detail"]  # a 5 hour old uptime check means the monitor stopped


def test_unreachable_github_is_unknown_never_healthy(monkeypatch, w):
    import routes.admin_status as m

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(m.requests, "get", boom)
    checks = _status(w)["checks"]
    assert [c["state"] for c in checks] == ["unknown"] * 3
    monkeypatch.setattr(m.requests, "get", lambda *a, **k: FakeResp(ok=False))
    m._CACHE.update(at=0.0, data=None)
    assert all(c["state"] == "unknown" for c in _status(w)["checks"])


def test_a_running_check_is_not_called_overdue_or_failed(monkeypatch, w):
    _github(monkeypatch, FakeResp([_run(timedelta(minutes=2), conclusion=None, status="in_progress")]), FakeResp(), FakeResp())
    assert _status(w)["checks"][0]["state"] == "running"


def test_github_results_are_cached(monkeypatch, w):
    calls = []
    import routes.admin_status as m
    monkeypatch.setattr(m.requests, "get", lambda *a, **k: (calls.append(1), FakeResp([_run(timedelta(hours=1))]))[1])
    _status(w)
    n = len(calls)
    _status(w)
    assert n == 3 and len(calls) == 3


def test_campaign_health_row(monkeypatch, w):
    _github(monkeypatch, FakeResp(), FakeResp(), FakeResp())
    from routes import campaign_websocket as cw

    class WS:
        pass
    cw.manager.active_connections[w["camp"].id] = [(WS(), w["u"]["p1"].id, "p1", "p1"), (WS(), w["u"]["p1"].id, "p1", "p1")]  # two tabs, one person
    try:
        s = _status(w)
    finally:
        cw.manager.active_connections.pop(w["camp"].id, None)
    row = next(r for r in s["campaigns"] if r["id"] == str(w["camp"].id))
    assert row["members"] == 2 and row["online_now"] == 1 and row["active_encounter"] is True
    assert row["pending_characters"] == 1 and row["open_reports"] == 1 and row["last_message_at"]
    assert s["online_now"] >= 1 and s["open_reports"] >= 1


def test_database_and_counts(monkeypatch, w):
    _github(monkeypatch, FakeResp(), FakeResp(), FakeResp())
    from backend.models import SecurityEvent
    w["db"].add(SecurityEvent(kind="server_error", detail={}))
    w["db"].commit()
    s = _status(w)
    assert s["database"]["ok"] is True and s["database"]["ping_ms"] >= 0 and s["database"]["accounts"] >= 3
    assert s["last_24h"]["server_errors"] >= 1 and s["last_24h"]["last_server_error_at"]


def test_no_secret_is_ever_returned(monkeypatch, w):
    _github(monkeypatch, FakeResp(), FakeResp(), FakeResp())
    for k, v in (("RESEND_API_KEY", "re_SECRETKEY123"), ("TURNSTILE_SECRET_KEY", "ts_SECRET456"), ("TURNSTILE_SITE_KEY", "site789"),
                 ("VAPID_PRIVATE_KEY", "vapid_SECRET000"), ("SECRET_KEY", "jwt_SECRET111"), ("MODERATION_EMAIL", "boss@example.com"),
                 ("FROM_EMAIL", "no-reply@tba-rpg.com")):
        monkeypatch.setenv(k, v)
    s = _status(w)
    blob = json.dumps(s)
    for secret in ("re_SECRETKEY123", "ts_SECRET456", "site789", "vapid_SECRET000", "jwt_SECRET111", "boss@example.com"):
        assert secret not in blob
    assert s["config"]["email_configured"] is True and s["config"]["human_check_on"] is True and s["config"]["from_email"] == "tba-rpg.com"


def test_status_is_admin_only(w):
    from fastapi import HTTPException
    from routes.moderation import require_admin
    with pytest.raises(HTTPException):
        require_admin(w["u"]["p1"])


def test_version_shows_only_the_first_line_of_the_commit_message(monkeypatch, w):
    _github(monkeypatch, FakeResp(), FakeResp(), FakeResp())
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_MESSAGE", "fix: a thing\n\nA long body.\n\nCo-Authored-By: Someone <x@example.com>")
    assert _status(w)["version"]["message"] == "fix: a thing"
