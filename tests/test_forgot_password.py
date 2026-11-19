"""
Forgot-password must give the same answer whether or not the email exists, and whether or not the email provider works. A 500 only for real
accounts (when sending fails) would tell a stranger which addresses are registered.
"""
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_forgot_password.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.app import application
    from backend.db import init_db
    init_db()
    return TestClient(application)


@pytest.fixture(autouse=True)
def _reset_limiter():
    from routes.auth import limiter
    limiter.reset()


def _make_user(client):
    tag = uuid.uuid4().hex[:8]
    body = {"email": f"fp_{tag}@example.com", "username": f"fp_{tag}", "password": "A-good-password-1"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    return body


def test_a_failing_email_provider_gives_the_same_generic_answer_as_an_unknown_email(client, monkeypatch):
    import routes.auth as auth

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(auth, "send_password_reset_email", boom)
    real = _make_user(client)
    ok_real = client.post("/api/auth/forgot-password", json={"email": real["email"]})
    ok_unknown = client.post("/api/auth/forgot-password", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"})
    assert ok_real.status_code == ok_unknown.status_code == 200
    assert ok_real.json() == ok_unknown.json()


def test_a_working_provider_is_called_with_the_username(client, monkeypatch):
    import routes.auth as auth
    calls = []
    monkeypatch.setattr(auth, "send_password_reset_email", lambda **k: calls.append(k))
    real = _make_user(client)
    r = client.post("/api/auth/forgot-password", json={"email": real["email"]})
    assert r.status_code == 200 and len(calls) == 1
    assert calls[0]["to_email"] == real["email"] and calls[0]["username"] == real["username"]
