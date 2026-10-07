"""
Tests for routes/moderation.py: reporting a campaign banner and the admin review/removal flow.

The risky parts: who can report what (no probing private campaigns, no self-reports, no spam),
reporter identity staying admin-only, admin endpoints being locked to ADMIN_USER_IDS, and a removal
never deleting a newer image than the one that was reported.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

BANNER_BASE = "https://cdn.example.com/campaigns"


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_moderation.db")
    os.environ.setdefault("API_KEY", "devkey")
    from backend.app import application
    from backend.db import init_db
    init_db()
    with TestClient(application) as c:
        yield c


@pytest.fixture(scope="module")
def world(client):
    from backend.auth.jwt import create_access_token
    from backend.db import SessionLocal
    from backend.models import Campaign, CampaignMembership, User

    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    def bearer(u):
        return {"Authorization": f"Bearer {create_access_token(str(u.id), u.email, u.username)}"}

    def campaign(sw, banner=True, public=True, name=None):
        cid = uuid.uuid4()
        c = Campaign(id=cid, name=name or f"Camp {cid.hex[:6]}", description="x" * 12,
                     created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id,
                     is_public=public, banner_url=f"{BANNER_BASE}/{cid}/banner/{uuid.uuid4()}.png" if banner else None)
        db.add(c)
        db.commit()
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=sw.id, role="story_weaver"))
        db.commit()
        return c

    sw, reporter, other, admin = user("sw"), user("rep"), user("other"), user("admin")
    data = dict(
        db=db, sw=sw, reporter=reporter, other=other, admin=admin, make_campaign=campaign,
        h_sw=bearer(sw), h_rep=bearer(reporter), h_other=bearer(other), h_admin=bearer(admin),
    )
    yield data
    db.close()


@pytest.fixture(autouse=True)
def admin_env(world, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", str(world["admin"].id))


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Never send real email or touch real storage."""
    import routes.moderation as mod
    calls = {"emails": [], "deleted": []}
    monkeypatch.setattr(mod, "send_report_email", lambda to, report: calls["emails"].append((to, report)))
    monkeypatch.setattr(mod, "delete_banner_from_r2", lambda url: calls["deleted"].append(url) or True)
    return calls


def report(client, headers, campaign, reason="spam", note=None):
    body = {"content_type": "campaign_banner", "content_id": str(campaign.id), "reason": reason}
    if note is not None:
        body["note"] = note
    return client.post("/api/moderation/report", json=body, headers=headers)


# ---------------------------------------------------------------- reporting

def test_endpoints_require_login(client):
    assert client.get("/api/moderation/reasons").status_code in (401, 403)
    assert client.post("/api/moderation/report", json={}).status_code in (401, 403)
    assert client.get("/api/moderation/reports").status_code in (401, 403)


def test_reasons_list_comes_from_the_server(client, world):
    r = client.get("/api/moderation/reasons", headers=world["h_rep"])
    assert r.status_code == 200
    values = [x["value"] for x in r.json()]
    assert "sexual_explicit" in values and "other" in values


def test_report_success_stores_a_snapshot_and_emails_admins(client, world, fakes):
    c = world["make_campaign"](world["sw"], name="Scorched <b>Lands</b>")
    r = report(client, world["h_rep"], c, reason="hate_harassment", note="  gross  ")
    assert r.status_code == 200 and r.json()["status"] == "reported"
    assert len(fakes["emails"]) == 1
    to, payload = fakes["emails"][0]
    assert to == [world["admin"].email]
    assert payload["reporter"] == world["reporter"].username and payload["note"] == "gross"

    from backend.models import ContentReport
    row = world["db"].query(ContentReport).filter_by(content_id=c.id).one()
    assert row.snapshot["banner_url"] == c.banner_url


def test_unknown_reason_and_other_without_note_are_rejected(client, world):
    c = world["make_campaign"](world["sw"])
    assert report(client, world["h_rep"], c, reason="made_up").status_code == 422
    assert report(client, world["h_rep"], c, reason="other").status_code == 422
    assert report(client, world["h_rep"], c, reason="other", note="   ").status_code == 422
    assert report(client, world["h_rep"], c, reason="other", note="weird").status_code == 200


def test_same_person_cannot_report_the_same_banner_twice(client, world):
    c = world["make_campaign"](world["sw"])
    assert report(client, world["h_rep"], c).json()["status"] == "reported"
    assert report(client, world["h_rep"], c).json()["status"] == "already_reported"
    from backend.models import ContentReport
    assert world["db"].query(ContentReport).filter_by(content_id=c.id).count() == 1


def test_missing_banner_private_campaign_and_unknown_id_all_look_the_same(client, world):
    no_banner = world["make_campaign"](world["sw"], banner=False)
    private = world["make_campaign"](world["sw"], public=False)

    class Ghost:
        id = uuid.uuid4()

    codes = {
        report(client, world["h_rep"], no_banner).status_code,
        report(client, world["h_rep"], private).status_code,
        report(client, world["h_rep"], Ghost).status_code,
    }
    assert codes == {404}


def test_a_member_can_report_a_private_campaigns_banner(client, world):
    from backend.models import CampaignMembership
    private = world["make_campaign"](world["sw"], public=False)
    world["db"].add(CampaignMembership(id=uuid.uuid4(), campaign_id=private.id,
                                       user_id=world["other"].id, role="player"))
    world["db"].commit()
    assert report(client, world["h_other"], private).status_code == 200


def test_cannot_report_your_own_banner(client, world):
    c = world["make_campaign"](world["sw"])
    assert report(client, world["h_sw"], c).status_code == 400


def test_daily_report_limit(client, world):
    from routes.moderation import REPORTS_PER_DAY
    from backend.auth.jwt import create_access_token
    from backend.models import User
    u = User(id=uuid.uuid4(), email=f"spam_{uuid.uuid4().hex[:6]}@example.com", username=f"spam_{uuid.uuid4().hex[:6]}", hashed_password="x")
    world["db"].add(u)
    world["db"].commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(u.id), u.email, u.username)}"}
    codes = [report(client, headers, world["make_campaign"](world["sw"])).status_code for _ in range(REPORTS_PER_DAY + 1)]
    assert codes[:REPORTS_PER_DAY] == [200] * REPORTS_PER_DAY
    assert codes[-1] == 429


# ---------------------------------------------------------------- admin review

def test_only_admins_can_list_reports_and_the_campaign_sw_is_not_one(client, world):
    for who in ("h_rep", "h_sw", "h_other"):
        assert client.get("/api/moderation/reports", headers=world[who]).status_code == 403
    assert client.get("/api/moderation/reports", headers=world["h_admin"]).status_code == 200


def test_nobody_is_admin_when_the_env_var_is_unset(client, world, monkeypatch):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    assert client.get("/api/moderation/reports", headers=world["h_admin"]).status_code == 403


def test_reporter_identity_only_appears_in_the_admin_listing(client, world):
    c = world["make_campaign"](world["sw"])
    report(client, world["h_rep"], c)
    admin_rows = client.get("/api/moderation/reports", headers=world["h_admin"]).json()
    mine = [r for r in admin_rows if r["content_id"] == str(c.id)]
    assert mine and mine[0]["reporter_username"] == world["reporter"].username
    # the SW (owner) can't read the list at all, and no owner-facing endpoint carries it
    assert client.get("/api/moderation/reports", headers=world["h_sw"]).status_code == 403


def test_non_admin_cannot_resolve(client, world):
    c = world["make_campaign"](world["sw"])
    report(client, world["h_rep"], c)
    rid = [r for r in client.get("/api/moderation/reports", headers=world["h_admin"]).json() if r["content_id"] == str(c.id)][0]["id"]
    for who in ("h_rep", "h_sw", "h_other"):
        assert client.post(f"/api/moderation/reports/{rid}/resolve", json={"action": "remove"}, headers=world[who]).status_code == 403


def _open_report_id(client, world, campaign, reason=None):
    rows = client.get("/api/moderation/reports", headers=world["h_admin"]).json()
    return [r for r in rows if r["content_id"] == str(campaign.id) and (reason is None or r["reason"] == reason)][0]["id"]


def _fresh(world, campaign):
    from backend.models import Campaign
    world["db"].expire_all()
    return world["db"].query(Campaign).filter_by(id=campaign.id).one()


def test_remove_clears_banner_deletes_file_notifies_sw_and_closes_all_reports(client, world, fakes):
    from backend.models import ContentReport, Notification
    c = world["make_campaign"](world["sw"])
    original = c.banner_url
    report(client, world["h_rep"], c, reason="sexual_explicit")
    report(client, world["h_other"], c, reason="spam")
    rid = _open_report_id(client, world, c, reason="sexual_explicit")

    r = client.post(f"/api/moderation/reports/{rid}/resolve",
                    json={"action": "remove", "message": "Please keep banners all-ages."}, headers=world["h_admin"])
    assert r.status_code == 200 and r.json() == {"outcome": "removed", "file_deleted": True}
    assert fakes["deleted"] == [original]

    fresh = _fresh(world, c)
    assert fresh.banner_url is None and fresh.banner_locked is False
    rows = world["db"].query(ContentReport).filter_by(content_id=c.id).all()
    assert {x.status for x in rows} == {"resolved"} and {x.resolution for x in rows} == {"removed"}

    note = world["db"].query(Notification).filter_by(user_id=world["sw"].id).order_by(Notification.created_at.desc()).first()
    assert "Banner removed" in note.title
    assert "Sexual or explicit content" in note.body and "all-ages" in note.body
    # the notice must never reveal who reported
    assert world["reporter"].username not in (note.body or "") and world["other"].username not in (note.body or "")

    # resolving twice is refused
    assert client.post(f"/api/moderation/reports/{rid}/resolve", json={"action": "dismiss"}, headers=world["h_admin"]).status_code == 409


def test_remove_and_lock_sets_the_lock(client, world):
    c = world["make_campaign"](world["sw"])
    report(client, world["h_rep"], c)
    rid = _open_report_id(client, world, c)
    r = client.post(f"/api/moderation/reports/{rid}/resolve", json={"action": "remove_and_lock"}, headers=world["h_admin"])
    assert r.json()["outcome"] == "removed_locked"
    fresh = _fresh(world, c)
    assert fresh.banner_url is None and fresh.banner_locked is True


def test_dismiss_leaves_the_banner_alone(client, world, fakes):
    c = world["make_campaign"](world["sw"])
    original = c.banner_url
    report(client, world["h_rep"], c)
    rid = _open_report_id(client, world, c)
    assert client.post(f"/api/moderation/reports/{rid}/resolve", json={"action": "dismiss"}, headers=world["h_admin"]).json()["outcome"] == "dismissed"
    assert _fresh(world, c).banner_url == original
    assert original not in fakes["deleted"]


def test_removal_never_deletes_a_newer_banner_than_the_one_reported(client, world, fakes):
    c = world["make_campaign"](world["sw"])
    report(client, world["h_rep"], c)
    rid = _open_report_id(client, world, c)
    # the SW swaps the image after the report was filed
    fresh = _fresh(world, c)
    newer = f"{BANNER_BASE}/{c.id}/banner/{uuid.uuid4()}.png"
    fresh.banner_url = newer
    world["db"].commit()

    r = client.post(f"/api/moderation/reports/{rid}/resolve", json={"action": "remove"}, headers=world["h_admin"])
    assert r.json() == {"outcome": "stale", "file_deleted": False}
    assert _fresh(world, c).banner_url == newer
    assert newer not in fakes["deleted"]


def test_r2_delete_helper_only_touches_campaign_banner_keys(monkeypatch):
    import routes.upload as up
    deleted = []

    class FakeClient:
        def delete_object(self, Bucket, Key):
            deleted.append(Key)

    monkeypatch.setenv("R2_PUBLIC_URL", "https://cdn.example.com")
    monkeypatch.setattr(up, "get_r2_client", lambda: FakeClient())
    cid, name = uuid.uuid4(), uuid.uuid4()
    assert up.delete_banner_from_r2(f"https://cdn.example.com/campaigns/{cid}/banner/{name}.png") is True
    # portraits, chat images, other hosts, traversal and junk are all refused
    for bad in (
        f"https://cdn.example.com/portraits/{cid}/{name}.png",
        f"https://cdn.example.com/campaigns/{cid}/images/{name}.png",
        f"https://evil.example.org/campaigns/{cid}/banner/{name}.png",
        f"https://cdn.example.com/campaigns/{cid}/banner/../images/{name}.png",
        "", None,
    ):
        assert up.delete_banner_from_r2(bad) is False
    assert len(deleted) == 1
