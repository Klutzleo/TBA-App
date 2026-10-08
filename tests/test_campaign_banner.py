"""
Tests for the campaign banner, browse tags, "Based on" credit and the browse refresh
(routes/campaigns.py, routes/lba.py Start Campaign).

The risky parts: banner_url can only ever come from the upload endpoint (never a settings PATCH),
uploads are validated by real bytes, a locked campaign can't upload, the source story stays hidden
from players unless the SW opts in, and browse no longer lists archived campaigns.
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

CDN = "https://cdn.example.com"


def make_image(fmt="PNG", size=(1600, 400), color=(40, 110, 160)):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


PNG = make_image("PNG")
JPEG = make_image("JPEG")
WEBP = make_image("WEBP")


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_banner.db")
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

    def campaign(sw, **kw):
        c = Campaign(id=uuid.uuid4(), name=kw.pop("name", f"Camp {uuid.uuid4().hex[:6]}"), description="x" * 12,
                     created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id, **kw)
        db.add(c)
        db.commit()
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=sw.id, role="story_weaver"))
        db.commit()
        return c

    def add_member(c, u, role="player"):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=u.id, role=role))
        db.commit()

    sw, player, outsider = user("sw"), user("pl"), user("out")
    data = dict(db=db, sw=sw, player=player, outsider=outsider, make_campaign=campaign, add_member=add_member,
                h_sw=bearer(sw), h_pl=bearer(player), h_out=bearer(outsider))
    yield data
    db.close()


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    import routes.upload as up
    calls = {"uploaded": [], "deleted": [], "bodies": []}

    def fake_upload(contents, key, content_type):
        calls["uploaded"].append((key, content_type, len(contents)))
        calls["bodies"].append(contents)
        return f"{CDN}/{key}"

    monkeypatch.setattr(up, "upload_to_r2", fake_upload)
    monkeypatch.setattr(up, "delete_banner_from_r2", lambda url: calls["deleted"].append(url) or True)
    return calls


def fresh(world, campaign):
    from backend.models import Campaign
    world["db"].expire_all()
    return world["db"].query(Campaign).filter_by(id=campaign.id).one()


def put_banner(client, headers, campaign, data=PNG, name="b.png", ctype="image/png"):
    return client.post(f"/api/campaigns/{campaign.id}/banner", headers=headers, files={"file": (name, data, ctype)})


# ------------------------------------------------------------------ upload

def test_sw_can_upload_png_jpeg_and_webp_and_it_is_stored_as_a_small_jpeg(client, world, fake_storage):
    c = world["make_campaign"](world["sw"])
    for data in (PNG, JPEG, WEBP):
        r = put_banner(client, world["h_sw"], c, data=data)
        assert r.status_code == 200, r.text
        assert r.json()["banner_url"].endswith(".jpg")
        assert r.json()["banner_focus_y"] == 50
    key, content_type, _ = fake_storage["uploaded"][-1]
    assert key.startswith(f"campaigns/{c.id}/banner/") and key.endswith(".jpg")
    assert content_type == "image/jpeg"
    assert fake_storage["bodies"][-1][:3] == b"\xff\xd8\xff"  # what we store is the re-encoded JPEG, not the upload
    assert fresh(world, c).banner_url.endswith(".jpg")


def test_stored_cover_is_resized_and_has_no_metadata(client, world, fake_storage):
    import io
    from PIL import Image
    c = world["make_campaign"](world["sw"])
    big = Image.new("RGB", (3600, 900), (10, 20, 30))
    exif = Image.Exif()
    exif[0x010F] = "SomeCamera"            # Make
    exif[0x8825] = {1: "N", 2: (40.0, 44.0, 0.0)}  # a GPS block, like a phone photo
    buf = io.BytesIO()
    big.save(buf, format="JPEG", exif=exif)
    assert b"Exif" in buf.getvalue()  # the test image really carries metadata
    r = put_banner(client, world["h_sw"], c, data=buf.getvalue(), name="photo.jpg", ctype="image/jpeg")
    assert r.status_code == 200, r.text
    stored = fake_storage["bodies"][-1]
    out = Image.open(io.BytesIO(stored))
    assert out.size == (1920, 480)          # shrunk to the widest place it is ever shown, same proportions
    assert b"Exif" not in stored and not out.getexif()  # location and camera data are gone
    assert len(stored) < len(buf.getvalue())


def test_replacing_a_banner_deletes_the_old_file(client, world, fake_storage):
    c = world["make_campaign"](world["sw"])
    first = put_banner(client, world["h_sw"], c).json()["banner_url"]
    put_banner(client, world["h_sw"], c, data=JPEG)
    assert first in fake_storage["deleted"]


def test_only_the_sw_can_upload_or_remove(client, world):
    c = world["make_campaign"](world["sw"])
    world["add_member"](c, world["player"])
    for who in ("h_pl", "h_out"):
        assert put_banner(client, world[who], c).status_code == 403
        assert client.delete(f"/api/campaigns/{c.id}/banner", headers=world[who]).status_code == 403
    assert client.post(f"/api/campaigns/{c.id}/banner", files={"file": ("b.png", PNG, "image/png")}).status_code in (401, 403)
    assert fresh(world, c).banner_url is None


def test_uploads_are_checked_by_real_bytes_not_the_claimed_type(client, world):
    c = world["make_campaign"](world["sw"])
    bad = {
        "text posing as png": (b"just some text, not an image", "b.png", "image/png"),
        "gif": (b"GIF89a" + b"0" * 40, "b.gif", "image/gif"),
        "svg": (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "b.svg", "image/svg+xml"),
        "html posing as jpeg": (b"<html><script>alert(1)</script></html>", "b.jpg", "image/jpeg"),
        "empty": (b"", "b.png", "image/png"),
    }
    for label, (data, name, ctype) in bad.items():
        r = put_banner(client, world["h_sw"], c, data=data, name=name, ctype=ctype)
        assert r.status_code == 400, label
    assert fresh(world, c).banner_url is None


def test_oversize_upload_is_rejected(client, world):
    c = world["make_campaign"](world["sw"])
    from routes.campaigns import BANNER_UPLOAD_MAX_BYTES
    r = put_banner(client, world["h_sw"], c, data=PNG + b"0" * BANNER_UPLOAD_MAX_BYTES)
    assert r.status_code == 400 and "10MB" in r.json()["detail"]
    assert fresh(world, c).banner_url is None


def test_image_that_is_too_narrow_or_corrupt_is_rejected_with_a_clear_message(client, world):
    c = world["make_campaign"](world["sw"])
    narrow = put_banner(client, world["h_sw"], c, data=make_image("PNG", size=(640, 160)))
    assert narrow.status_code == 400 and "640 px wide" in narrow.json()["detail"]
    # looks like a PNG by its first bytes, but is not one
    corrupt = put_banner(client, world["h_sw"], c, data=b"\x89PNG\r\n\x1a\n" + b"not really a png" * 20)
    assert corrupt.status_code == 400 and "could not be read" in corrupt.json()["detail"]
    assert fresh(world, c).banner_url is None


def test_new_upload_resets_the_focus_to_the_middle(client, world):
    c = world["make_campaign"](world["sw"])
    put_banner(client, world["h_sw"], c)
    client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={"banner_focus_y": 10})
    assert fresh(world, c).banner_focus_y == 10
    put_banner(client, world["h_sw"], c, data=JPEG)
    assert fresh(world, c).banner_focus_y == 50


def test_focus_is_validated_and_sw_only(client, world):
    c = world["make_campaign"](world["sw"])
    world["add_member"](c, world["player"])
    for bad in (-1, 101, 5.5, "abc"):
        assert client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={"banner_focus_y": bad}).status_code == 422
    assert client.patch(f"/api/campaigns/{c.id}", headers=world["h_pl"], json={"banner_focus_y": 20}).status_code == 403
    ok = client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={"banner_focus_y": 0})
    assert ok.status_code == 200 and ok.json()["banner_focus_y"] == 0
    assert fresh(world, c).banner_focus_y == 0


def test_focus_is_sent_with_the_campaign_so_every_card_and_header_can_use_it(client, world):
    c = world["make_campaign"](world["sw"], is_public=True, banner_url=f"{CDN}/campaigns/x/banner/a.jpg", banner_focus_y=70)
    row = browse(client, world["h_out"])[str(c.id)]
    assert row["banner_focus_y"] == 70


def test_locked_campaign_cannot_upload_but_can_clear(client, world, fake_storage):
    c = world["make_campaign"](world["sw"], banner_locked=True, banner_url=f"{CDN}/campaigns/x/banner/old.png")
    assert put_banner(client, world["h_sw"], c).status_code == 403
    r = client.delete(f"/api/campaigns/{c.id}/banner", headers=world["h_sw"])
    assert r.status_code == 200 and fresh(world, c).banner_url is None
    assert f"{CDN}/campaigns/x/banner/old.png" in fake_storage["deleted"]


def test_banner_url_cannot_be_set_through_a_settings_patch(client, world):
    c = world["make_campaign"](world["sw"])
    r = client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={
        "name": "Renamed ok", "banner_url": "https://evil.example.org/x.png", "banner_locked": False,
        "source_title": "Forged credit", "source_package_id": str(uuid.uuid4()),
    })
    assert r.status_code == 200
    after = fresh(world, c)
    assert after.name == "Renamed ok"
    assert after.banner_url is None and after.source_title is None and after.source_package_id is None


# ------------------------------------------------------------------ tags

def test_sw_can_set_and_clear_genres_and_rating(client, world):
    c = world["make_campaign"](world["sw"])
    r = client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"],
                     json={"genres": ["horror", "mystery", "horror"], "content_rating": "teen"})
    assert r.status_code == 200
    assert r.json()["genres"] == ["horror", "mystery"] and r.json()["content_rating"] == "teen"
    r = client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={"content_rating": None, "genres": []})
    assert r.json()["content_rating"] is None and r.json()["genres"] == []


def test_invalid_tags_are_rejected(client, world):
    c = world["make_campaign"](world["sw"])
    for body in ({"genres": ["horror", "not_a_genre"]}, {"content_rating": "adults_only_xxx"},
                 {"genres": ["fantasy", "horror", "scifi", "mystery", "political", "western"]}):
        assert client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json=body).status_code == 422
    assert fresh(world, c).genres == []


def test_a_player_cannot_change_tags(client, world):
    c = world["make_campaign"](world["sw"])
    world["add_member"](c, world["player"])
    assert client.patch(f"/api/campaigns/{c.id}", headers=world["h_pl"], json={"genres": ["horror"]}).status_code == 403


# ------------------------------------------------------------------ browse

def browse(client, headers):
    r = client.get("/api/campaigns/browse", headers=headers)
    assert r.status_code == 200
    return {x["id"]: x for x in r.json()}


def test_browse_hides_archived_and_private_but_shows_on_break(client, world):
    active = world["make_campaign"](world["sw"], is_public=True, status="active")
    on_break = world["make_campaign"](world["sw"], is_public=True, status="on_break")
    archived = world["make_campaign"](world["sw"], is_public=True, status="archived")
    private = world["make_campaign"](world["sw"], is_public=False)
    got = browse(client, world["h_out"])
    assert str(active.id) in got and str(on_break.id) in got
    assert str(archived.id) not in got and str(private.id) not in got
    assert got[str(on_break.id)]["status"] == "on_break"


def test_browse_carries_banner_tags_activity_and_correct_counts(client, world):
    from backend.models import Message
    c = world["make_campaign"](world["sw"], is_public=True, banner_url=f"{CDN}/campaigns/x/banner/a.png",
                               genres=["horror"], content_rating="mature")
    world["add_member"](c, world["player"])
    old, new = datetime.utcnow() - timedelta(days=3), datetime.utcnow() - timedelta(minutes=6)
    for when in (old, new):
        world["db"].add(Message(id=uuid.uuid4(), campaign_id=c.id, sender_id=world["sw"].id, sender_name="SW",
                                content="hi", created_at=when))
    world["db"].commit()

    row = browse(client, world["h_out"])[str(c.id)]
    assert row["banner_url"].endswith("a.png") and row["genres"] == ["horror"] and row["content_rating"] == "mature"
    assert row["member_count"] == 2  # SW + player
    got_time = datetime.fromisoformat(row["last_activity_at"]).replace(tzinfo=None)
    assert abs((got_time - new).total_seconds()) < 2  # the newest message, not the oldest
    assert "banner_locked" not in row or row["banner_locked"] is None  # SW-only fields never leak to browsers


def test_campaign_with_no_messages_has_no_activity_time(client, world):
    c = world["make_campaign"](world["sw"], is_public=True)
    assert browse(client, world["h_out"])[str(c.id)]["last_activity_at"] is None


# ------------------------------------------------------------------ "Based on" credit

def source_campaign(world):
    return world["make_campaign"](
        world["sw"], is_public=True, source_title="The Scorched Lands", source_author_user_id=world["outsider"].id,
        show_source_in_game=False,
    )


def test_browse_always_shows_the_credit_with_the_authors_username(client, world):
    c = source_campaign(world)
    row = browse(client, world["h_pl"])[str(c.id)]
    assert row["source_title"] == "The Scorched Lands"
    assert row["source_author_username"] == world["outsider"].username


def test_players_inside_the_game_dont_see_the_source_unless_the_sw_opts_in(client, world):
    c = source_campaign(world)
    world["add_member"](c, world["player"])
    assert client.get(f"/api/campaigns/{c.id}", headers=world["h_pl"]).json()["source_title"] is None
    assert client.get(f"/api/campaigns/{c.id}", headers=world["h_sw"]).json()["source_title"] == "The Scorched Lands"

    client.patch(f"/api/campaigns/{c.id}", headers=world["h_sw"], json={"show_source_in_game": True})
    assert client.get(f"/api/campaigns/{c.id}", headers=world["h_pl"]).json()["source_title"] == "The Scorched Lands"


def test_my_campaigns_list_applies_the_same_spoiler_rule(client, world):
    c = source_campaign(world)
    world["add_member"](c, world["player"])
    mine = {x["id"]: x for x in client.get("/api/campaigns", headers=world["h_pl"]).json()}
    assert mine[str(c.id)]["source_title"] is None
    sws = {x["id"]: x for x in client.get("/api/campaigns", headers=world["h_sw"]).json()}
    assert sws[str(c.id)]["source_title"] == "The Scorched Lands"
    assert sws[str(c.id)]["show_source_in_game"] is False and sws[str(c.id)]["banner_locked"] is False


def test_sw_only_fields_are_not_sent_to_players(client, world):
    c = source_campaign(world)
    world["add_member"](c, world["player"])
    body = client.get(f"/api/campaigns/{c.id}", headers=world["h_pl"]).json()
    assert body.get("banner_locked") is None and body.get("show_source_in_game") is None


# ------------------------------------------------------------------ Start Campaign

def test_start_campaign_copies_tags_and_credit_from_the_story(client, world):
    from backend.models import LbaPackage
    pkg = LbaPackage(id=uuid.uuid4(), author_user_id=world["outsider"].id, title="Ashes of Eldrow", is_public=True,
                     content_rating="teen", genres=["fantasy", "mystery"])
    world["db"].add(pkg)
    world["db"].commit()
    r = client.post(f"/api/lba/packages/{pkg.id}/start-campaign", headers=world["h_pl"])
    assert r.status_code == 200, r.text
    campaign_id = r.json().get("campaign_id") or r.json().get("id")

    from backend.models import Campaign
    world["db"].expire_all()
    c = world["db"].query(Campaign).filter_by(id=uuid.UUID(str(campaign_id))).one()
    assert c.genres == ["fantasy", "mystery"] and c.content_rating == "teen"
    assert c.source_package_id == pkg.id and c.source_title == "Ashes of Eldrow"
    assert c.source_author_user_id == world["outsider"].id
    assert c.show_source_in_game is False  # spoiler guard defaults on
    assert c.banner_url is None  # covers are not shared between LBA and campaigns (yet)
    assert c.is_public is False  # not in Browse until the SW chooses to publish it
    assert str(c.id) not in browse(client, world["h_out"])
