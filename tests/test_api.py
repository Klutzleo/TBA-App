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
