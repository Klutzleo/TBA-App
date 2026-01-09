"""
Tests for Character and Party CRUD endpoints (Phase 1).
"""

import os
import pytest
from fastapi.testclient import TestClient


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
    return {"X-API-Key": os.environ.get("API_KEY", "devkey")}


# ============================================================================
# CHARACTER CRUD TESTS
# ============================================================================

def test_create_character_valid(test_client, auth_headers):
    """Create a valid character with level 5."""
    payload = {
        "name": "TestHero",
        "owner_id": "user_test",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "3d4"
    }
    
    resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    body = resp.json()
    
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


def test_create_character_invalid_stats_sum(test_client, auth_headers):
    """Reject character with stats that don't sum to 6."""
    payload = {
        "name": "BadStats",
        "owner_id": "user_test",
        "level": 1,
        "pp": 3,
        "ip": 3,
        "sp": 3,  # 3 + 3 + 3 = 9 (invalid)
        "attack_style": "1d4"
    }
    
    resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    assert resp.status_code in {400, 422}


def test_create_character_invalid_attack_style(test_client, auth_headers):
    """Reject character with attack style not available for their level."""
    payload = {
        "name": "OverpoweredLevel1",
        "owner_id": "user_test",
        "level": 1,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "3d8"  # Not available at level 1
    }
    
    resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    assert resp.status_code == 400


def test_list_characters(test_client, auth_headers):
    """List all characters for a user."""
    # Create a character first
    payload = {
        "name": "ListTest",
        "owner_id": "user_list_test",
        "level": 3,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "2d4"
    }
    test_client.post("/api/characters", headers=auth_headers, json=payload)
    
    # List characters
    resp = test_client.get("/api/characters?owner_id=user_list_test", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert any(c["name"] == "ListTest" for c in body)


def test_get_character_by_id(test_client, auth_headers):
    """Get a single character by ID."""
    # Create character
    payload = {
        "name": "GetTest",
        "owner_id": "user_get_test",
        "level": 2,
        "pp": 3,
        "ip": 1,
        "sp": 2,
        "attack_style": "1d4"
    }
    create_resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    character_id = create_resp.json()["id"]
    
    # Get character
    resp = test_client.get(f"/api/characters/{character_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == character_id
    assert body["name"] == "GetTest"


def test_update_character_level_up(test_client, auth_headers):
    """Level up a character and verify stats auto-recalculate."""
    # Create level 1 character
    payload = {
        "name": "LevelUpTest",
        "owner_id": "user_levelup_test",
        "level": 1,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "1d4"
    }
    create_resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    character_id = create_resp.json()["id"]
    
    # Level up to 6
    update_payload = {"level": 6}
    resp = test_client.patch(f"/api/characters/{character_id}", headers=auth_headers, json=update_payload)
    assert resp.status_code == 200
    body = resp.json()
    
    assert body["level"] == 6
    assert body["edge"] == 3  # Level 6 → Edge 3
    assert body["bap"] == 3  # Level 6 → BAP 3
    assert body["max_dp"] == 35  # Level 6 → 35 DP
    assert body["dp"] == 35  # Healed to full on level up
    assert body["defense_die"] == "1d8"  # Level 6 → 1d8


def test_update_character_dp(test_client, auth_headers):
    """Manually adjust a character's DP."""
    # Create character
    payload = {
        "name": "DPTest",
        "owner_id": "user_dp_test",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "3d4"
    }
    create_resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    character_id = create_resp.json()["id"]
    
    # Reduce DP to 15
    update_payload = {"dp": 15}
    resp = test_client.patch(f"/api/characters/{character_id}", headers=auth_headers, json=update_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dp"] == 15


def test_delete_character(test_client, auth_headers):
    """Delete a character."""
    # Create character
    payload = {
        "name": "DeleteTest",
        "owner_id": "user_delete_test",
        "level": 1,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d4"
    }
    create_resp = test_client.post("/api/characters", headers=auth_headers, json=payload)
    character_id = create_resp.json()["id"]
    
    # Delete character
    resp = test_client.delete(f"/api/characters/{character_id}", headers=auth_headers)
    assert resp.status_code == 204
    
    # Verify deleted
    get_resp = test_client.get(f"/api/characters/{character_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# ============================================================================
# PARTY CRUD TESTS
# ============================================================================

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
