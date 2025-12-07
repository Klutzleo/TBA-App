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
