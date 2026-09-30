"""
Tests for LBA (routes/lba.py + routes/public_lba.py).

Focus: the two-tier visibility split (teaser public, full tier login-gated),
ownership scoping (can't reference someone else's NPC/item in your own
package), and the Start Campaign cloning logic — the highest-risk piece,
since a clone missing its abilities would be a shell, not a runnable NPC.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_client():
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_lba.db")
    os.environ.setdefault("API_KEY", "devkey")
    from backend.app import application
    from backend.db import init_db
    init_db()
    with TestClient(application) as client:
        yield client


@pytest.fixture(scope="session")
def world(test_client):
    """Two SWs, each running their own campaign with one NPC (+ ability) and
    one item, plus an outsider with no campaign at all."""
    from backend.auth.jwt import create_access_token
    from backend.db import SessionLocal
    from backend.models import Ability, Campaign, CampaignMembership, Character, InventoryItem, User

    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:8]

        def make_user(name):
            u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com",
                      username=f"{name}_{tag}", hashed_password="x")
            db.add(u)
            db.commit()
            return u

        sw1, sw2, outsider = make_user("sw1"), make_user("sw2"), make_user("outsider")

        def make_campaign(sw):
            c = Campaign(id=uuid.uuid4(), name=f"Campaign {tag}", description="x",
                         created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id)
            db.add(c)
            db.commit()
            db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=sw.id, role="story_weaver"))
            db.commit()
            return c

        camp1, camp2 = make_campaign(sw1), make_campaign(sw2)

        def make_npc(campaign, name):
            npc = Character(id=uuid.uuid4(), name=name, owner_id=str(campaign.story_weaver_id),
                            campaign_id=campaign.id, is_npc=True, pp=2, ip=2, sp=2, dp=10, max_dp=10,
                            attack_style="melee", defense_die="1d6")
            db.add(npc)
            db.commit()
            db.add(Ability(id=uuid.uuid4(), character_id=npc.id, slot_number=1, ability_type="technique",
                          display_name="Cleave", macro_command="/cleave", power_source="PP",
                          effect_type="damage", die="2d6"))
            db.commit()
            return npc

        npc1 = make_npc(camp1, "Scalelord")
        npc2 = make_npc(camp2, "Beef")  # belongs to sw2, sw1 should never be able to reference this

        item1 = InventoryItem(id=uuid.uuid4(), campaign_id=camp1.id, name="Rusty Sword", item_type="equipment")
        db.add(item1)
        db.commit()

        def bearer(user):
            return {"Authorization": f"Bearer {create_access_token(str(user.id), user.email, user.username)}"}

        return {
            "sw1": bearer(sw1), "sw2": bearer(sw2), "outsider": bearer(outsider),
            "sw1_id": str(sw1.id),
            "npc1_id": str(npc1.id), "npc2_id": str(npc2.id), "item1_id": str(item1.id),
        }
    finally:
        db.close()


def _package_payload(world, **overrides):
    payload = {
        "title": "The Scorched Path",
        "tagline": "A one-shot about regret.",
        "format": "one_shot",
        "suggested_party_size": "small",
        "content_rating": "teen",
        "genres": ["horror", "mystery"],
        "tags": ["revenge"],
        "story_text": "Deep in the ash fields, a bell tolls.",
        "world_text": "The Ashlands were once a garden.",
        "core_npc_character_ids": [world["npc1_id"]],
        "core_item_ids": [world["item1_id"]],
        "side_quests": [{"title": "The Lost Bell", "hook": "Find the bell before nightfall."}],
        "is_public": True,
    }
    payload.update(overrides)
    return payload


def test_create_package_requires_login(test_client):
    resp = test_client.post("/api/lba/packages", json={"title": "No Auth Test"})
    assert resp.status_code in (401, 403)


def test_create_and_fetch_full_package(test_client, world):
    resp = test_client.post("/api/lba/packages", headers=world["sw1"], json=_package_payload(world))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "The Scorched Path"
    assert len(body["core_npcs"]) == 1
    assert body["core_npcs"][0]["name"] == "Scalelord"
    assert len(body["core_items"]) == 1


def test_teaser_list_has_no_spoiler_fields(test_client, world):
    test_client.post("/api/lba/packages", headers=world["sw1"], json=_package_payload(world, title="Teaser Test"))
    resp = test_client.get("/api/public/lba/entries")
    assert resp.status_code == 200
    entries = resp.json()
    match = [e for e in entries if e["title"] == "Teaser Test"]
    assert len(match) == 1
    entry = match[0]
    # Only teaser fields — nothing spoiler-tier leaks into the public list
    assert set(entry.keys()) == {
        "id", "title", "tagline", "format", "suggested_party_size",
        "content_rating", "genres", "tags", "adoption_count", "created_at",
    }


def test_multi_select_filters_are_or_not_and(test_client, world):
    """Checking several boxes for one filter means 'any of these', not 'all
    of these' — e.g. Solo + Small together should surface both, not neither."""
    test_client.post("/api/lba/packages", headers=world["sw1"],
                     json=_package_payload(world, title="Solo Story", suggested_party_size="solo", genres=["horror"]))
    test_client.post("/api/lba/packages", headers=world["sw1"],
                     json=_package_payload(world, title="Large Story", suggested_party_size="large", genres=["comedy"]))

    resp = test_client.get("/api/public/lba/entries?party_size=solo&party_size=small")
    titles = {e["title"] for e in resp.json()}
    assert "Solo Story" in titles
    assert "Large Story" not in titles

    # Genre filter matches on ANY overlap, not requiring every selected genre present
    resp = test_client.get("/api/public/lba/entries?genre=horror&genre=comedy")
    titles = {e["title"] for e in resp.json()}
    assert "Solo Story" in titles
    assert "Large Story" in titles


def test_full_tier_requires_login_even_for_a_public_package(test_client, world):
    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Gate Test"))
    package_id = create.json()["id"]

    anon = test_client.get(f"/api/lba/packages/{package_id}/full")
    assert anon.status_code in (401, 403)

    logged_in = test_client.get(f"/api/lba/packages/{package_id}/full", headers=world["outsider"])
    assert logged_in.status_code == 200
    assert logged_in.json()["story_text"] == "Deep in the ash fields, a bell tolls."


def test_full_tier_404s_for_a_private_package_even_when_logged_in(test_client, world):
    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Private Test", is_public=False))
    package_id = create.json()["id"]

    resp = test_client.get(f"/api/lba/packages/{package_id}/full", headers=world["outsider"])
    assert resp.status_code == 404


def test_cannot_reference_another_sws_npc_in_your_own_package(test_client, world):
    """sw1 tries to sneak sw2's NPC into their package — should be silently
    dropped, not included, not a validation error that would reveal it exists."""
    resp = test_client.post(
        "/api/lba/packages", headers=world["sw1"],
        json=_package_payload(world, title="Sneaky Test", core_npc_character_ids=[world["npc2_id"]]),
    )
    assert resp.status_code == 201
    assert resp.json()["core_npcs"] == []


def test_only_owner_can_edit_or_delete(test_client, world):
    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Ownership Test"))
    package_id = create.json()["id"]

    edit_attempt = test_client.patch(f"/api/lba/packages/{package_id}", headers=world["sw2"],
                                     json=_package_payload(world, title="Hijacked"))
    assert edit_attempt.status_code == 404  # not found, not 403 — doesn't confirm it exists to a non-owner

    delete_attempt = test_client.delete(f"/api/lba/packages/{package_id}", headers=world["sw2"])
    assert delete_attempt.status_code == 404


def test_start_campaign_requires_login(test_client, world):
    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Adopt Test"))
    package_id = create.json()["id"]
    resp = test_client.post(f"/api/lba/packages/{package_id}/start-campaign")
    assert resp.status_code in (401, 403)


def test_start_campaign_clones_npc_with_its_ability_and_the_item(test_client, world):
    from backend.db import SessionLocal
    from backend.models import Ability, Campaign, Character, InventoryItem, LbaPackage

    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Clone Test"))
    package_id = create.json()["id"]

    resp = test_client.post(f"/api/lba/packages/{package_id}/start-campaign", headers=world["outsider"])
    assert resp.status_code == 200, resp.text
    new_campaign_id = resp.json()["campaign_id"]

    db = SessionLocal()
    try:
        from backend.models import LoreEntry

        campaign = db.query(Campaign).filter(Campaign.id == new_campaign_id).first()
        assert campaign is not None
        # World/setting text (spoiler-free) goes to the Lore tab — visible to every
        # campaign member, not just the SW.
        lore_entries = db.query(LoreEntry).filter(LoreEntry.campaign_id == new_campaign_id).all()
        assert any("Ashlands" in (le.content or "") for le in lore_entries)
        # Story/twists/side-quests are spoiler-sensitive — must stay in SW notes,
        # never in the Lore tab that every campaign member can read.
        assert "bell tolls" in (campaign.sw_notes or "")
        assert "Lost Bell" in (campaign.sw_notes or "")
        assert not any("bell tolls" in (le.content or "") for le in lore_entries)

        clones = db.query(Character).filter(Character.campaign_id == new_campaign_id, Character.is_npc == True).all()
        assert len(clones) == 1
        clone = clones[0]
        assert clone.name == "Scalelord"
        assert str(clone.id) != world["npc1_id"]  # a real new row, not a reference to the original

        clone_abilities = db.query(Ability).filter(Ability.character_id == clone.id).all()
        assert len(clone_abilities) == 1
        assert clone_abilities[0].display_name == "Cleave"  # the detail that makes it actually runnable

        cloned_items = db.query(InventoryItem).filter(InventoryItem.campaign_id == new_campaign_id).all()
        assert len(cloned_items) == 1
        assert cloned_items[0].name == "Rusty Sword"

        package = db.query(LbaPackage).filter(LbaPackage.id == package_id).first()
        assert package.adoption_count == 1
    finally:
        db.close()


def test_start_campaign_rejects_a_private_package(test_client, world):
    create = test_client.post("/api/lba/packages", headers=world["sw1"],
                              json=_package_payload(world, title="Private Adopt Test", is_public=False))
    package_id = create.json()["id"]
    resp = test_client.post(f"/api/lba/packages/{package_id}/start-campaign", headers=world["outsider"])
    assert resp.status_code == 404
