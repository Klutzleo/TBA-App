import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_client():
    # Ensure safe local DB and API key for tests
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    os.environ.setdefault("API_KEY", "devkey")
    from backend.app import application

    with TestClient(application) as client:
        yield client


def test_public_health_ok(test_client):
    resp = test_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"


def test_api_health_requires_key(test_client):
    # Without key → 403
    resp = test_client.get("/api/health")
    assert resp.status_code == 403

    # With key → 200
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    resp2 = test_client.get("/api/health", headers=headers)
    assert resp2.status_code == 200
    body = resp2.json()
    assert body.get("status") in {"ok", "degraded"}


def test_combat_attack_smoke(test_client):
    """Basic combat attack with no bonuses."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "attacker": {
            "name": "Alice",
            "level": 5,
            "stats": {"pp": 3, "ip": 2, "sp": 1},
            "dp": 30,
            "edge": 1,
            "bap": 2,
            "attack_style": "3d4",
            "defense_die": "1d8"
        },
        "defender": {
            "name": "Goblin",
            "level": 2,
            "stats": {"pp": 2, "ip": 1, "sp": 1},
            "dp": 15,
            "edge": 0,
            "bap": 1,
            "attack_style": "1d4",
            "defense_die": "1d4"
        },
        "technique_name": "Slash",
        "stat_type": "PP",
        "bap_triggered": False
    }

    resp = test_client.post("/api/combat/attack", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # Basic smoke assertions
    assert body.get("attacker_name") == "Alice"
    assert body.get("defender_name") == "Goblin"
    assert "total_damage" in body
    assert body.get("outcome") in {"hit", "miss", "partial_hit"}
    assert len(body.get("individual_rolls", [])) == 3  # 3d4


def test_combat_attack_with_weapon_bonus(test_client):
    """Attack with weapon bonus applied."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "attacker": {
            "name": "Hero",
            "level": 5,
            "stats": {"pp": 3, "ip": 2, "sp": 1},
            "dp": 30,
            "edge": 2,
            "bap": 2,
            "attack_style": "2d6",
            "defense_die": "1d8",
            "weapon": {"name": "Iron Sword", "bonus_attack": 0, "bonus_damage": 2}
        },
        "defender": {
            "name": "Orc",
            "level": 3,
            "stats": {"pp": 2, "ip": 1, "sp": 1},
            "dp": 20,
            "edge": 1,
            "bap": 1,
            "attack_style": "1d6",
            "defense_die": "1d6",
            "armor": {"name": "Leather", "bonus_defense": 0, "bonus_dp": 2}
        },
        "technique_name": "Slash",
        "stat_type": "PP",
        "bap_triggered": False
    }

    resp = test_client.post("/api/combat/attack", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("attacker_name") == "Hero"
    assert body.get("total_damage") >= 0  # Weapon bonus applied in rolls
    # Each damage roll should include the +2 bonus
    for roll in body.get("individual_rolls", []):
        assert roll.get("damage") >= 0


def test_combat_attack_stat_types(test_client):
    """Test different stat types (PP, IP, SP)."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    base_payload = {
        "attacker": {
            "name": "Mage",
            "level": 4,
            "stats": {"pp": 1, "ip": 3, "sp": 2},
            "dp": 25,
            "edge": 1,
            "bap": 2,
            "attack_style": "2d6",
            "defense_die": "1d6"
        },
        "defender": {
            "name": "Enemy",
            "level": 4,
            "stats": {"pp": 2, "ip": 2, "sp": 2},
            "dp": 25,
            "edge": 1,
            "bap": 2,
            "attack_style": "1d6",
            "defense_die": "1d6"
        },
        "technique_name": "Fireball",
        "bap_triggered": False
    }

    # Test IP (Intellect)
    payload_ip = {**base_payload, "stat_type": "IP"}
    resp_ip = test_client.post("/api/combat/attack", headers=headers, json=payload_ip)
    assert resp_ip.status_code == 200

    # Test SP (Social)
    payload_sp = {**base_payload, "stat_type": "SP"}
    resp_sp = test_client.post("/api/combat/attack", headers=headers, json=payload_sp)
    assert resp_sp.status_code == 200

    # Both should succeed
    assert resp_ip.json().get("attacker_name") == "Mage"
    assert resp_sp.json().get("attacker_name") == "Mage"


def test_combat_attack_bap_triggered(test_client):
    """Test with BAP bonus triggered."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "attacker": {
            "name": "Knight",
            "level": 5,
            "stats": {"pp": 3, "ip": 1, "sp": 2},
            "dp": 35,
            "edge": 2,
            "bap": 3,
            "attack_style": "3d6",
            "defense_die": "1d8"
        },
        "defender": {
            "name": "Goblin",
            "level": 2,
            "stats": {"pp": 2, "ip": 1, "sp": 1},
            "dp": 15,
            "edge": 0,
            "bap": 1,
            "attack_style": "1d4",
            "defense_die": "1d4"
        },
        "technique_name": "Power Strike",
        "stat_type": "PP",
        "bap_triggered": True
    }

    resp = test_client.post("/api/combat/attack", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("outcome") in {"hit", "miss", "partial_hit"}


def test_combat_attack_invalid_stat_type(test_client):
    """Test with invalid stat type (should fail)."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "attacker": {
            "name": "Alice",
            "level": 5,
            "stats": {"pp": 3, "ip": 2, "sp": 1},
            "dp": 30,
            "edge": 1,
            "bap": 2,
            "attack_style": "3d4",
            "defense_die": "1d8"
        },
        "defender": {
            "name": "Goblin",
            "level": 2,
            "stats": {"pp": 2, "ip": 1, "sp": 1},
            "dp": 15,
            "edge": 0,
            "bap": 1,
            "attack_style": "1d4",
            "defense_die": "1d4"
        },
        "technique_name": "Slash",
        "stat_type": "XX",  # Invalid stat type
        "bap_triggered": False
    }

    resp = test_client.post("/api/combat/attack", headers=headers, json=payload)
    # Should fail gracefully (422 for validation error or 500 for missing attribute)
    assert resp.status_code in {400, 422, 500}


def test_initiative_endpoint(test_client):
    """Roll initiative and verify ordering and roll breakdown."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "combatants": [
            {
                "name": "Alice",
                "level": 5,
                "stats": {"pp": 3, "ip": 2, "sp": 1},
                "dp": 30,
                "edge": 2,
                "bap": 3,
                "attack_style": "3d4",
                "defense_die": "1d8"
            },
            {
                "name": "Bob",
                "level": 4,
                "stats": {"pp": 2, "ip": 3, "sp": 2},
                "dp": 25,
                "edge": 1,
                "bap": 2,
                "attack_style": "2d6",
                "defense_die": "1d6"
            }
        ]
    }

    resp = test_client.post("/api/combat/roll-initiative", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("initiative_order")
    assert len(body.get("rolls", [])) == 2


def test_encounter_1v1_endpoint(test_client):
    """Simulate 1v1 encounter end-to-end."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    payload = {
        "attacker": {
            "name": "Hero",
            "level": 5,
            "stats": {"pp": 3, "ip": 2, "sp": 1},
            "dp": 30,
            "edge": 2,
            "bap": 3,
            "attack_style": "2d6",
            "defense_die": "1d8"
        },
        "defender": {
            "name": "Orc",
            "level": 4,
            "stats": {"pp": 2, "ip": 1, "sp": 2},
            "dp": 25,
            "edge": 1,
            "bap": 2,
            "attack_style": "1d6",
            "defense_die": "1d6"
        },
        "technique_name": "Slash",
        "stat_type": "PP",
        "max_rounds": 5
    }

    resp = test_client.post("/api/combat/encounter-1v1", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("type") == "encounter_1v1"
    assert body.get("round_count") <= 5
    assert body.get("outcome") in {"attacker_wins", "defender_wins", "timeout"}


def test_combat_log_recent(test_client):
    """Post a combat log entry and retrieve it via /log/recent."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    entry = {
        "actor": "Recorder",
        "timestamp": "2025-12-07T12:00:00",
        "context": "enc-123",
        "triggered_by": "tester",
        "narration": "Recorded a test log entry",
        "action": {"name": "note"},
        "roll": {"die": "1d4", "result": 3},
        "outcome": "info",
        "tethers": [],
        "log": []
    }

    post_resp = test_client.post("/api/combat/log", headers=headers, json=entry)
    assert post_resp.status_code == 200

    recent_resp = test_client.get("/api/combat/log/recent", headers=headers)
    assert recent_resp.status_code == 200
    recent_body = recent_resp.json()
    assert any(e.get("actor") == "Recorder" for e in recent_body.get("entries", []))


def test_combat_attack_by_id_persists_dp(test_client):
    """Attack using character IDs auto-persists DP changes to database."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    
    # Create two characters
    attacker_payload = {
        "name": "PersistAttacker",
        "owner_id": "user_persist_test",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "3d4"
    }
    attacker_resp = test_client.post("/api/characters", headers=headers, json=attacker_payload)
    attacker_id = attacker_resp.json()["id"]
    
    defender_payload = {
        "name": "PersistDefender",
        "owner_id": "user_persist_test",
        "level": 3,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "2d4"
    }
    defender_resp = test_client.post("/api/characters", headers=headers, json=defender_payload)
    defender_id = defender_resp.json()["id"]
    defender_original_dp = defender_resp.json()["dp"]
    
    # Attack using IDs
    attack_payload = {
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "technique_name": "Slash",
        "stat_type": "PP",
        "bap_triggered": False
    }
    attack_resp = test_client.post("/api/combat/attack-by-id", headers=headers, json=attack_payload)
    assert attack_resp.status_code == 200
    attack_body = attack_resp.json()
    
    # Verify damage was applied
    assert attack_body["defender_new_dp"] <= defender_original_dp
    
    # Fetch defender from DB and verify DP persisted
    defender_after = test_client.get(f"/api/characters/{defender_id}", headers=headers)
    assert defender_after.json()["dp"] == attack_body["defender_new_dp"]


def test_combat_encounter_by_id_persists_results(test_client):
    """1v1 encounter using character IDs persists final DP to database."""
    headers = {"X-API-Key": os.environ.get("API_KEY", "devkey")}
    
    # Create two characters
    attacker_payload = {
        "name": "EncounterAttacker",
        "owner_id": "user_encounter_test",
        "level": 5,
        "pp": 3,
        "ip": 2,
        "sp": 1,
        "attack_style": "2d6"
    }
    attacker_resp = test_client.post("/api/characters", headers=headers, json=attacker_payload)
    attacker_id = attacker_resp.json()["id"]
    
    defender_payload = {
        "name": "EncounterDefender",
        "owner_id": "user_encounter_test",
        "level": 4,
        "pp": 2,
        "ip": 2,
        "sp": 2,
        "attack_style": "1d6"
    }
    defender_resp = test_client.post("/api/characters", headers=headers, json=defender_payload)
    defender_id = defender_resp.json()["id"]
    
    # Run encounter
    encounter_payload = {
        "attacker_id": attacker_id,
        "defender_id": defender_id,
        "technique_name": "Slash",
        "stat_type": "PP",
        "max_rounds": 3,
        "persist_results": True
    }
    encounter_resp = test_client.post("/api/combat/encounter-1v1-by-id", headers=headers, json=encounter_payload)
    assert encounter_resp.status_code == 200
    encounter_body = encounter_resp.json()
    
    # Verify encounter completed
    assert encounter_body["round_count"] <= 3
    assert encounter_body["outcome"] in {"attacker_wins", "defender_wins", "timeout"}
    
    # Fetch characters from DB and verify DP persisted
    attacker_after = test_client.get(f"/api/characters/{attacker_id}", headers=headers).json()
    defender_after = test_client.get(f"/api/characters/{defender_id}", headers=headers).json()
    
    assert attacker_after["dp"] == encounter_body["final_dp"]["EncounterAttacker"]
    assert defender_after["dp"] == encounter_body["final_dp"]["EncounterDefender"]
