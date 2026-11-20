"""
Backup watchdog: GitHub does not run this repo's scheduled workflows reliably (the 10:17 UTC backup never fired), so the app starts a job through
the workflow_dispatch API when it is due. These tests cover the decision, the API calls, and that the token never leaks.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_backup_watchdog.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import backup_watchdog as bw  # noqa: E402

UTC = timezone.utc
BACKUP = bw.JOBS[0]
DRILL = bw.JOBS[1]
SECRET = "github_pat_SECRETVALUE123"


def at(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def run(when, conclusion="success", status="completed"):
    return {"created_at": when.isoformat().replace("+00:00", "Z"), "conclusion": conclusion, "status": status}


# ---------------------------------------------------------------- the schedule maths
def test_daily_boundary_is_today_after_the_time_and_yesterday_before_it():
    assert bw.due_boundary(BACKUP, at(2026, 11, 20, 17, 25)) == at(2026, 11, 20, 10, 17)
    assert bw.due_boundary(BACKUP, at(2026, 11, 20, 10, 17)) == at(2026, 11, 20, 10, 17)
    assert bw.due_boundary(BACKUP, at(2026, 11, 20, 3, 0)) == at(2026, 11, 19, 10, 17)


def test_monthly_boundary_across_month_and_year_edges():
    assert bw.due_boundary(DRILL, at(2026, 11, 20, 8, 0)) == at(2026, 11, 1, 11, 43)
    assert bw.due_boundary(DRILL, at(2026, 11, 1, 11, 0)) == at(2026, 10, 1, 11, 43)   # the day, but before the time
    assert bw.due_boundary(DRILL, at(2027, 1, 1, 0, 5)) == at(2026, 12, 1, 11, 43)
    assert bw.due_boundary(DRILL, at(2026, 3, 1, 12, 0)) == at(2026, 3, 1, 11, 43)


# ---------------------------------------------------------------- the decision
def test_due_when_nothing_ran_since_the_boundary():
    now = at(2026, 11, 20, 17, 25)
    start, why = bw.decide(BACKUP, [run(at(2026, 11, 19, 19, 38))], now)   # only yesterday's manual run
    assert start is True and why == "due"


def test_not_due_when_a_success_exists_since_the_boundary():
    now = at(2026, 11, 20, 17, 25)
    assert bw.decide(BACKUP, [run(at(2026, 11, 20, 10, 40))], now)[0] is False
    assert bw.decide(BACKUP, [run(at(2026, 11, 20, 12, 0))], now)[0] is False      # a manual run after the boundary counts too


def test_not_due_before_the_time_if_yesterdays_ran():
    assert bw.decide(BACKUP, [run(at(2026, 11, 19, 10, 20))], at(2026, 11, 20, 3, 0))[0] is False


def test_a_run_in_progress_blocks_a_second_start():
    now = at(2026, 11, 20, 17, 25)
    start, why = bw.decide(BACKUP, [run(at(2026, 11, 20, 17, 10), conclusion=None, status="in_progress")], now)
    assert start is False and "in progress" in why


def test_a_stuck_old_run_does_not_block_forever():
    now = at(2026, 11, 20, 17, 25)
    assert bw.decide(BACKUP, [run(at(2026, 11, 20, 5, 0), conclusion=None, status="in_progress")], now)[0] is True


def test_a_recent_failure_is_not_retried_in_a_loop():
    now = at(2026, 11, 20, 17, 25)
    start, why = bw.decide(BACKUP, [run(at(2026, 11, 20, 14, 0), conclusion="failure")], now)
    assert start is False and "6 hours" in why
    assert bw.decide(BACKUP, [run(at(2026, 11, 20, 10, 40), conclusion="failure")], now)[0] is True   # but a failure from this morning is retried


def test_no_runs_at_all_means_due():
    assert bw.decide(BACKUP, [], at(2026, 11, 20, 17, 25))[0] is True


# ---------------------------------------------------------------- the API calls
class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", SECRET)
    bw.STATE.update(enabled=False, last_check=None, last_started={}, last_error=None)
    calls = {"get": [], "post": []}
    runs = {"backup.yml": [run(at(2026, 11, 19, 19, 38))], "restore-drill.yml": [run(at(2026, 11, 5, 11, 50))]}
    post_status = {"code": 204}

    def fake_get(url, **kw):
        calls["get"].append((url, kw))
        wf = url.split("/workflows/")[1].split("/")[0]
        return Resp(200, {"workflow_runs": runs[wf]})

    def fake_post(url, **kw):
        calls["post"].append((url, kw))
        return Resp(post_status["code"])

    monkeypatch.setattr(bw.requests, "get", fake_get)
    monkeypatch.setattr(bw.requests, "post", fake_post)
    return dict(calls=calls, runs=runs, post_status=post_status)


def test_starts_the_overdue_backup_and_leaves_the_drill_alone(api):
    acts = bw.check_once(at(2026, 11, 20, 17, 25))
    assert ("backup.yml", "started", "due") in acts
    assert [a[1] for a in acts if a[0] == "restore-drill.yml"] == ["skip"]       # the drill ran after Nov 1
    assert len(api["calls"]["post"]) == 1
    url, kw = api["calls"]["post"][0]
    assert url.endswith("/actions/workflows/backup.yml/dispatches") and kw["json"] == {"ref": "main"}
    assert bw.STATE["last_started"]["backup.yml"].startswith("2026-11-20T17:25")


def test_does_nothing_without_a_token(api, monkeypatch):
    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN")
    assert bw.check_once(at(2026, 11, 20, 17, 25)) == []
    assert api["calls"]["get"] == [] and api["calls"]["post"] == []
    assert bw.status()["enabled"] is False


def test_a_second_pass_does_not_start_it_again(api):
    bw.check_once(at(2026, 11, 20, 17, 25))
    api["runs"]["backup.yml"].insert(0, run(at(2026, 11, 20, 17, 26), conclusion=None, status="queued"))
    acts = bw.check_once(at(2026, 11, 20, 18, 25))
    assert len(api["calls"]["post"]) == 1 and ("backup.yml", "skip", "a run is already in progress") in acts


def test_a_refused_start_is_reported_not_raised(api):
    api["post_status"]["code"] = 403
    acts = bw.check_once(at(2026, 11, 20, 17, 25))
    assert any(a[0] == "backup.yml" and a[1] == "error" and "403" in a[2] for a in acts)
    assert "403" in bw.status()["last_error"]


def test_a_network_error_never_kills_the_pass(api, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down " + SECRET)

    monkeypatch.setattr(bw.requests, "get", boom)
    acts = bw.check_once(at(2026, 11, 20, 17, 25))
    assert len(acts) == 2 and all(a[1] == "error" for a in acts)


def test_the_token_is_only_sent_as_a_bearer_header_and_never_leaks(api, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)

    def boom(*a, **k):
        raise RuntimeError("network down " + SECRET)

    bw.check_once(at(2026, 11, 20, 17, 25))                                  # a normal pass
    for _url, kw in api["calls"]["get"] + api["calls"]["post"]:
        assert kw["headers"]["Authorization"] == f"Bearer {SECRET}"
        assert SECRET not in str(kw.get("params", "")) and SECRET not in str(kw.get("json", ""))
    monkeypatch.setattr(bw.requests, "get", boom)
    bw.check_once(at(2026, 11, 20, 18, 25))                                  # and a failing pass whose error text contains the token
    assert SECRET not in caplog.text
    assert SECRET not in json.dumps(bw.status()) and SECRET not in str(bw.STATE)


def test_only_api_github_com_is_called(api):
    bw.check_once(at(2026, 11, 20, 17, 25))
    assert all(u.startswith("https://api.github.com/") for u, _ in api["calls"]["get"] + api["calls"]["post"])


def test_status_page_reports_the_watchdog_without_the_token(api):
    from backend.db import SessionLocal, init_db
    from backend.models import User
    import uuid
    from routes import admin_status
    init_db()
    db = SessionLocal()
    try:
        admin = User(id=uuid.uuid4(), email=f"a_{uuid.uuid4().hex[:6]}@example.com", username=f"a_{uuid.uuid4().hex[:6]}", hashed_password="x")
        admin_status._CACHE.update(at=0.0, data=[])
        out = admin_status.system_status(admin, db)
        assert out["watchdog"]["enabled"] is True and SECRET not in json.dumps(out)
    finally:
        db.close()
