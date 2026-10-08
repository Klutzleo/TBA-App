"""
Tests for "Use as cover" (POST /api/campaigns/{id}/banner/from-image): a Story Weaver turns one of the campaign's
Images-tab pictures into the cover.

The risky parts: the image is found by message id (never a browser-supplied URL), it must live in THIS campaign's images
folder, it is re-encoded like any upload, and it never exposes or alters the original chat image.
"""
import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

CDN = "https://cdn.example.com"


def png(size=(1600, 400), color=(40, 110, 160)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_cover_from_image.db")
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
    from backend.models import Campaign, CampaignMembership, Message, User

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
        c = Campaign(id=uuid.uuid4(), name=f"Camp {uuid.uuid4().hex[:6]}", description="x" * 12,
                     created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id, **kw)
        db.add(c)
        db.commit()
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=sw.id, role="story_weaver"))
        db.commit()
        return c

    def image_message(c, url=None, message_type="image_upload", deleted=False):
        from datetime import datetime
        m = Message(id=uuid.uuid4(), campaign_id=c.id, sender_id=c.story_weaver_id, sender_name="Someone",
                    content="img", message_type=message_type,
                    extra_data={"url": url if url is not None else f"{CDN}/campaigns/{c.id}/images/{uuid.uuid4()}.png", "filename": "x.png"},
                    deleted_at=datetime.utcnow() if deleted else None)
        db.add(m)
        db.commit()
        return m

    sw, player, other_sw = user("sw"), user("pl"), user("other")
    data = dict(db=db, sw=sw, player=player, other_sw=other_sw, campaign=campaign, image_message=image_message,
                h_sw=bearer(sw), h_pl=bearer(player), h_other=bearer(other_sw))
    yield data
    db.close()


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    """Fake storage: records what is stored/deleted/fetched, serves a chosen image for any fetch."""
    import routes.upload as up
    monkeypatch.setenv("R2_PUBLIC_URL", CDN)
    calls = {"uploaded": [], "deleted": [], "fetched": [], "serve": png(), "fail": False}

    def fake_fetch(key, max_bytes):
        calls["fetched"].append(key)
        if calls["fail"]:
            raise RuntimeError("storage down")
        return calls["serve"]

    def fake_upload(contents, key, content_type):
        calls["uploaded"].append((key, content_type, contents))
        return f"{CDN}/{key}"

    monkeypatch.setattr(up, "fetch_r2_object", fake_fetch)
    monkeypatch.setattr(up, "upload_to_r2", fake_upload)
    monkeypatch.setattr(up, "delete_banner_from_r2", lambda url: calls["deleted"].append(url) or True)
    return calls


def fresh(world, c):
    from backend.models import Campaign
    world["db"].expire_all()
    return world["db"].query(Campaign).filter_by(id=c.id).one()


def use(client, headers, c, message):
    return client.post(f"/api/campaigns/{c.id}/banner/from-image", headers=headers, json={"message_id": str(message.id)})


def test_sw_can_make_an_images_tab_picture_the_cover(client, world, storage):
    old = f"{CDN}/campaigns/x/banner/old.jpg"
    c = world["campaign"](world["sw"], banner_url=old, banner_focus_y=10)
    m = world["image_message"](c)
    r = use(client, world["h_sw"], c, m)
    assert r.status_code == 200, r.text
    after = fresh(world, c)
    key, content_type, body = storage["uploaded"][-1]
    assert key.startswith(f"campaigns/{c.id}/banner/") and key.endswith(".jpg")  # its own cover file, not the original
    assert content_type == "image/jpeg" and body[:3] == b"\xff\xd8\xff"          # re-encoded, never copied as-is
    assert after.banner_url == f"{CDN}/{key}" and after.banner_focus_y == 50
    assert old in storage["deleted"]                                            # the previous cover is cleaned up
    assert storage["fetched"] == [m.extra_data["url"].replace(CDN + "/", "")]
    # the original picture is untouched: still listed in the Images tab, still its own file
    listing = client.get(f"/api/campaigns/{c.id}/images", headers=world["h_sw"]).json()["images"]
    assert any(i["id"] == str(m.id) and "/images/" in i["url"] for i in listing)


def test_only_the_sw_can_do_it(client, world, storage):
    c = world["campaign"](world["sw"])
    from backend.models import CampaignMembership
    import uuid as _u
    world["db"].add(CampaignMembership(id=_u.uuid4(), campaign_id=c.id, user_id=world["player"].id, role="player"))
    world["db"].commit()
    m = world["image_message"](c)
    assert use(client, world["h_pl"], c, m).status_code == 403
    assert use(client, world["h_other"], c, m).status_code == 403
    assert client.post(f"/api/campaigns/{c.id}/banner/from-image", json={"message_id": str(m.id)}).status_code in (401, 403)
    assert storage["fetched"] == [] and fresh(world, c).banner_url is None


def test_an_image_from_another_campaign_cannot_be_used(client, world, storage):
    mine = world["campaign"](world["sw"])
    theirs = world["campaign"](world["other_sw"])
    foreign = world["image_message"](theirs)
    r = use(client, world["h_sw"], mine, foreign)
    assert r.status_code == 404
    assert storage["fetched"] == [] and fresh(world, mine).banner_url is None


def test_deleted_or_non_image_messages_are_not_found(client, world, storage):
    c = world["campaign"](world["sw"])
    assert use(client, world["h_sw"], c, world["image_message"](c, deleted=True)).status_code == 404
    assert use(client, world["h_sw"], c, world["image_message"](c, message_type="chat")).status_code == 404
    assert storage["fetched"] == []


@pytest.mark.parametrize("bad_url", [
    "https://evil.example.org/campaigns/{cid}/images/x.png",          # not our storage
    CDN + "/portraits/someone/x.png",                                  # someone's portrait
    CDN + "/campaigns/{other}/images/x.png",                           # another campaign's folder
    CDN + "/campaigns/{cid}/banner/x.jpg",                             # an existing cover, not a chat image
    CDN + "/campaigns/{cid}/images/../banner/x.jpg",                   # path tricks
    CDN + "/campaigns/{cid}/images/..",                                # right depth, but the last part is a path trick
    CDN + "/campaigns/{cid}/images/sub/dir/x.png",                     # wrong depth
    "",
])
def test_only_this_campaigns_images_folder_is_ever_read(client, world, storage, bad_url):
    c = world["campaign"](world["sw"])
    url = bad_url.replace("{cid}", str(c.id)).replace("{other}", str(uuid.uuid4()))
    m = world["image_message"](c, url=url)
    r = use(client, world["h_sw"], c, m)
    assert r.status_code == 400, (url, r.text)
    assert storage["fetched"] == []  # nothing was read from storage
    assert fresh(world, c).banner_url is None


def test_too_small_image_is_refused_with_a_clear_message(client, world, storage):
    c = world["campaign"](world["sw"], banner_url=f"{CDN}/campaigns/x/banner/old.jpg")
    storage["serve"] = png((600, 150))
    r = use(client, world["h_sw"], c, world["image_message"](c))
    assert r.status_code == 400 and "600 px wide" in r.json()["detail"]
    assert fresh(world, c).banner_url == f"{CDN}/campaigns/x/banner/old.jpg"  # the existing cover is kept


def test_a_locked_campaign_cannot_set_a_cover(client, world, storage):
    c = world["campaign"](world["sw"], banner_locked=True)
    assert use(client, world["h_sw"], c, world["image_message"](c)).status_code == 403
    assert storage["fetched"] == []


def test_storage_failure_is_reported_not_crashed(client, world, storage):
    c = world["campaign"](world["sw"])
    storage["fail"] = True
    r = use(client, world["h_sw"], c, world["image_message"](c))
    assert r.status_code == 502
    assert fresh(world, c).banner_url is None


def test_helpers_only_recognise_our_own_urls(monkeypatch):
    import routes.upload as up
    monkeypatch.setenv("R2_PUBLIC_URL", CDN + "/")
    assert up.r2_key_from_url(CDN + "/campaigns/a/images/b.png") == "campaigns/a/images/b.png"
    for other in ("", None, "https://other.example.com/campaigns/a/images/b.png", "http://cdn.example.com/campaigns/a/images/b.png"):
        assert up.r2_key_from_url(other) is None
    monkeypatch.delenv("R2_PUBLIC_URL")
    assert up.r2_key_from_url(CDN + "/campaigns/a/images/b.png") is None
