"""
Tests for Character CRUD endpoints (Phase 1).

Character routes take a JWT (`Authorization: Bearer`) and check the caller against the
campaign (owner, campaign member, or Story Weaver), so these tests build a real campaign
with a Story Weaver, a player and an outsider, each holding a real token.

The /api/parties router is legacy and is not mounted (see backend/app.py); its tests are
kept below but skipped.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

LEGACY_PARTIES = pytest.mark.skip(reason="The /api/parties router is legacy and not mounted (see backend/app.py)")


@pytest.fixture(scope="session")
def test_client():
    # Ensure safe local DB and API key for tests
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_characters.db")
    os.environ.setdefault("API_KEY", "devkey")

    # Initialize DB before creating app (triggers lifespan + init_db)
    from backend.app import application
    from backend.db import init_db

    # Force DB init (in case lifespan doesn't run in TestClient)
    init_db()

    with TestClient(application) as client:
        yield client


@pytest.fixture
def auth_headers():
    """Legacy API-key header. Only the skipped party tests still use it."""
    return {"X-API-Key": os.environ.get("API_KEY", "devkey")}


@pytest.fixture(scope="session")
def world(test_client):
    """A campaign with a Story Weaver and a player who belong to it, plus an outsider who does not.

    Returns the campaign id and a ready-to-use Authorization header for each person.
    Unique names per run, because the SQLite test database persists between runs.
    """
    from backend.auth.jwt import create_access_token
    from backend.db import SessionLocal
    from backend.models import Campaign, CampaignMembership, User

    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:8]

        def make_user(name):
            user = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com",
                        username=f"{name}_{tag}", hashed_password="x")
            db.add(user)
            db.commit()
            return user

        sw, player, outsider = make_user("sw"), make_user("player"), make_user("outsider")
        campaign = Campaign(id=uuid.uuid4(), name=f"Test Campaign {tag}", description="character tests",
                            created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id)
        db.add(campaign)
        db.commit()
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=campaign.id, user_id=sw.id, role="story_weaver"))
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=campaign.id, user_id=player.id, role="player"))
        db.commit()

        def bearer(user):
            return {"Authorization": f"Bearer {create_access_token(str(user.id), user.email, user.username)}"}

        return {"campaign_id": str(campaign.id), "sw": bearer(sw), "player": bearer(player), "outsider": bearer(outsider)}
    finally:
        db.close()


def _character(world, **overrides):
    """A valid level-1 character payload for this campaign. owner_id holds the campaign id."""
    payload = {
        "name": "TestHero",
        "owner_id": world["campaign_id"],
        "campaign_id": world["campaign_id"],
        "level": 1,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "1d4",
    }
    payload.update(overrides)
    return payload


def _create(test_client, world, who="player", **overrides):
    resp = test_client.post("/api/characters", headers=world[who], json=_character(world, **overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ============================================================================
# CHARACTER CRUD TESTS
# ============================================================================

def test_create_character_valid(test_client, world):
    """Create a valid character with level 5, owned by the caller."""
    body = _create(test_client, world, name="TestHero", level=5, attack_style="3d4")

    assert body["name"] == "TestHero"
    assert body["level"] == 5
    assert body["pp"] == 3
    assert body["ip"] == 2
    assert body["sp"] == 1
    assert body["edge"] == 2  # Level 5 → Edge 2
    assert body["bap"] == 3  # Level 5 → BAP 3
    assert body["max_dp"] == 30  # Level 5 → 30 DP
    assert body["dp"] == 30  # Starts at full HP
    assert body["defense_die"] == "1d8"  # Level 5 → 1d8
    assert body["attack_style"] == "3d4"
    assert "id" in body


def test_create_character_invalid_stats_sum(test_client, world):
    """Reject character with stats that don't sum to 6."""
    payload = _character(world, name="BadStats", pp=3, ip=3, sp=3)  # 3 + 3 + 3 = 9 (invalid)
    resp = test_client.post("/api/characters", headers=world["player"], json=payload)
    assert resp.status_code in {400, 422}


def test_create_character_invalid_attack_style(test_client, world):
    """Reject character with attack style not available for their level."""
    payload = _character(world, name="OverpoweredLevel1", attack_style="3d8")  # Not available at level 1
    resp = test_client.post("/api/characters", headers=world["player"], json=payload)
    assert resp.status_code == 400


def test_list_characters(test_client, world):
    """A campaign member can list the campaign's characters."""
    _create(test_client, world, name="ListTest", level=3, pp=2, ip=2, sp=2, attack_style="2d4")

    resp = test_client.get(f"/api/characters?owner_id={world['campaign_id']}", headers=world["player"])
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert any(c["name"] == "ListTest" for c in body)


def test_get_character_by_id(test_client, world):
    """The owner can fetch their character by ID."""
    created = _create(test_client, world, name="GetTest", level=2, pp=3, ip=1, sp=2)

    resp = test_client.get(f"/api/characters/{created['id']}", headers=world["player"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "GetTest"


def test_update_character_level_up(test_client, world):
    """Level up a character and verify stats auto-recalculate."""
    created = _create(test_client, world, name="LevelUpTest", level=1)

    resp = test_client.patch(f"/api/characters/{created['id']}", headers=world["player"], json={"level": 6})
    assert resp.status_code == 200
    body = resp.json()

    assert body["level"] == 6
    assert body["edge"] == 3  # Level 6 → Edge 3
    assert body["bap"] == 3  # Level 6 → BAP 3
    assert body["max_dp"] == 35  # Level 6 → 35 DP
    assert body["dp"] == 35  # Healed to full on level up
    assert body["defense_die"] == "1d8"  # Level 6 → 1d8


def test_update_character_dp(test_client, world):
    """Manually adjust a character's DP."""
    created = _create(test_client, world, name="DPTest", level=5, attack_style="3d4")

    resp = test_client.patch(f"/api/characters/{created['id']}", headers=world["player"], json={"dp": 15})
    assert resp.status_code == 200
    assert resp.json()["dp"] == 15


def test_delete_character(test_client, world):
    """The Story Weaver can delete a character."""
    created = _create(test_client, world, name="DeleteTest", pp=2, ip=2, sp=2)

    resp = test_client.delete(f"/api/characters/{created['id']}", headers=world["sw"])
    assert resp.status_code == 204

    # Verify deleted
    get_resp = test_client.get(f"/api/characters/{created['id']}", headers=world["sw"])
    assert get_resp.status_code == 404


# ============================================================================
# ACCESS RULES (the security hardening these routes rely on)
# ============================================================================

def test_characters_require_a_login(test_client, world):
    """No token, no access. The old shared API key is not enough."""
    resp = test_client.get(f"/api/characters?owner_id={world['campaign_id']}",
                           headers={"X-API-Key": os.environ.get("API_KEY", "devkey")})
    assert resp.status_code in {401, 403}


def test_outsider_cannot_list_a_campaigns_characters(test_client, world):
    resp = test_client.get(f"/api/characters?owner_id={world['campaign_id']}", headers=world["outsider"])
    assert resp.status_code == 403


def test_outsider_cannot_edit_someone_elses_character(test_client, world):
    created = _create(test_client, world, name="NotYours")
    resp = test_client.patch(f"/api/characters/{created['id']}", headers=world["outsider"], json={"dp": 1})
    assert resp.status_code == 403


def test_player_cannot_delete_a_character(test_client, world):
    """Deleting is Story Weaver only, even for the character's own owner."""
    created = _create(test_client, world, name="KeepMe")
    resp = test_client.delete(f"/api/characters/{created['id']}", headers=world["player"])
    assert resp.status_code == 403


# ============================================================================
# PARTY CRUD TESTS
# ============================================================================

@LEGACY_PARTIES
def test_create_party(test_client, auth_headers):
    """Create a new party."""
    # First create a character to be the Story Weaver
    char_payload = {
        "name": "Alice",
        "owner_id": "user_alice",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "2d6"
    }
    char_resp = test_client.post("/api/characters", headers=auth_headers, json=char_payload)
    character_id = char_resp.json()["id"]

    # Create party with this character as creator
    payload = {
        "name": "The Crimson Dawn",
        "description": "A brave party of adventurers",
        "creator_character_id": character_id
    }

    resp = test_client.post("/api/parties", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    body = resp.json()

    assert body["name"] == "The Crimson Dawn"
    assert body["description"] == "A brave party of adventurers"
    assert body["story_weaver_id"] == character_id
    assert body["created_by_id"] == character_id
    assert "id" in body


@LEGACY_PARTIES
def test_list_parties(test_client, auth_headers):
    """List all parties for a Story Weaver."""
    # Create character
    char_payload = {
        "name": "Bob",
        "owner_id": "user_bob",
        "level": 3,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d8"
    }
    char_resp = test_client.post("/api/characters", headers=auth_headers, json=char_payload)
    character_id = char_resp.json()["id"]

    # Create party
    payload = {
        "name": "ListPartyTest",
        "creator_character_id": character_id
    }
    test_client.post("/api/parties", headers=auth_headers, json=payload)

    # List parties
    resp = test_client.get(f"/api/parties?story_weaver_id={character_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert any(p["name"] == "ListPartyTest" for p in body)


@LEGACY_PARTIES
def test_add_character_to_party(test_client, auth_headers):
    """Add a character to a party."""
    # Create Story Weaver character (Level 5)
    sw_payload = {
        "name": "StoryWeaver",
        "owner_id": "user_sw",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "1d8"
    }
    sw_resp = test_client.post("/api/characters", headers=auth_headers, json=sw_payload)
    sw_id = sw_resp.json()["id"]

    # Create another character to add (Level 3)
    char_payload = {
        "name": "PartyMember",
        "owner_id": "user_party_test",
        "level": 3,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d6"
    }
    char_resp = test_client.post("/api/characters", headers=auth_headers, json=char_payload)
    character_id = char_resp.json()["id"]

    # Create party with SW as creator
    party_payload = {
        "name": "TestParty",
        "creator_character_id": sw_id
    }
    party_resp = test_client.post("/api/parties", headers=auth_headers, json=party_payload)
    party_id = party_resp.json()["id"]

    # Add character to party
    add_payload = {"character_id": character_id}
    resp = test_client.post(f"/api/parties/{party_id}/members", headers=auth_headers, json=add_payload)
    assert resp.status_code == 201


@LEGACY_PARTIES
def test_list_party_members(test_client, auth_headers):
    """List all members of a party."""
    # Create Story Weaver character (Level 2)
    sw_payload = {
        "name": "SW_Member",
        "owner_id": "user_sw_member",
        "level": 2,
        "pp": 3,
        "ip": 1,
        "sp": 2,
        "attack_style": "1d4"
    }
    sw_resp = test_client.post("/api/characters", headers=auth_headers, json=sw_payload)
    sw_id = sw_resp.json()["id"]

    # Create another character
    char_payload = {
        "name": "MemberListTest",
        "owner_id": "user_member_test",
        "level": 2,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d4"
    }
    char_resp = test_client.post("/api/characters", headers=auth_headers, json=char_payload)
    character_id = char_resp.json()["id"]

    # Create party
    party_payload = {
        "name": "MemberTestParty",
        "creator_character_id": sw_id
    }
    party_resp = test_client.post("/api/parties", headers=auth_headers, json=party_payload)
    party_id = party_resp.json()["id"]

    # Add character to party
    add_payload = {"character_id": character_id}
    test_client.post(f"/api/parties/{party_id}/members", headers=auth_headers, json=add_payload)

    # List members (should have 2: SW + added character)
    resp = test_client.get(f"/api/parties/{party_id}/members", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 2  # SW auto-added + manually added character
    character_names = [m["character"]["name"] for m in body]
    assert "MemberListTest" in character_names


@LEGACY_PARTIES
def test_remove_character_from_party(test_client, auth_headers):
    """Remove a character from a party."""
    # Create Story Weaver character (Level 1)
    sw_payload = {
        "name": "SW_Remove",
        "owner_id": "user_sw_remove",
        "level": 1,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "1d4"
    }
    sw_resp = test_client.post("/api/characters", headers=auth_headers, json=sw_payload)
    sw_id = sw_resp.json()["id"]

    # Create character to remove
    char_payload = {
        "name": "RemoveTest",
        "owner_id": "user_remove_test",
        "level": 1,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d4"
    }
    char_resp = test_client.post("/api/characters", headers=auth_headers, json=char_payload)
    character_id = char_resp.json()["id"]

    # Create party
    party_payload = {
        "name": "RemoveTestParty",
        "creator_character_id": sw_id
    }
    party_resp = test_client.post("/api/parties", headers=auth_headers, json=party_payload)
    party_id = party_resp.json()["id"]

    # Add character to party
    add_payload = {"character_id": character_id}
    test_client.post(f"/api/parties/{party_id}/members", headers=auth_headers, json=add_payload)

    # Remove character from party
    resp = test_client.delete(f"/api/parties/{party_id}/members/{character_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify removed
    members_resp = test_client.get(f"/api/parties/{party_id}/members", headers=auth_headers)
    members = members_resp.json()
    assert not any(m["character"]["id"] == character_id for m in members)
