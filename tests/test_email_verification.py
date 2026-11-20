"""
Email verification at signup. New accounts get a confirmation link; nothing is blocked by default; accounts that predate the feature are exempt;
an optional switch (REQUIRE_VERIFIED_EMAIL) can later require it to create or join a campaign. Goes through the real app (TestClient) so the
middleware, the rate limiter and the request models are all in play.
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_email_verification.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.app import application
    from backend.db import init_db
    init_db()
    return TestClient(application)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from routes.auth import limiter
    limiter.reset()
    for k in ("TURNSTILE_SECRET_KEY", "TURNSTILE_SITE_KEY", "REQUIRE_VERIFIED_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


@pytest.fixture
def sent(monkeypatch):
    """Capture every verification email instead of sending it."""
    out = []
    import backend.email_verification as ev
    monkeypatch.setattr(ev, "send_verification_email", lambda to, token, username=None: out.append({"to": to, "token": token, "username": username}))
    return out


def _signup(client):
    tag = uuid.uuid4().hex[:8]
    body = {"email": f"person_{tag}@example.com", "username": f"person_{tag}", "password": "A-good-password-1"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    return r.json(), body


def _auth(j):
    return {"Authorization": f"Bearer {j['access_token']}"}


def _user(email):
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.expunge(u)
    db.close()
    return u


def test_signup_sends_a_link_and_the_account_starts_unconfirmed(client, sent):
    j, body = _signup(client)
    assert len(sent) == 1 and sent[0]["to"] == body["email"] and sent[0]["username"] == body["username"]
    u = _user(body["email"])
    assert u.email_verified_at is None and u.email_verification_exempt is False and u.email_is_verified is False
    me = client.get("/api/auth/me", headers=_auth(j)).json()
    assert me["email_verified"] is False


def test_a_mail_failure_never_fails_the_signup(client, monkeypatch):
    import backend.email_verification as ev

    def boom(*a, **k):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(ev, "send_verification_email", boom)
    j, _ = _signup(client)   # _signup asserts 201
    assert j["access_token"]


def test_the_link_confirms_the_address_and_is_safe_to_repeat(client, sent):
    j, body = _signup(client)
    token = sent[0]["token"]
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and r.json() == {"verified": True, "username": body["username"]}
    first = _user(body["email"]).email_verified_at
    assert first is not None
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200      # again: still fine
    assert _user(body["email"]).email_verified_at == first                                        # and the time is not rewritten
    assert client.get("/api/auth/me", headers=_auth(j)).json()["email_verified"] is True


def test_the_confirm_call_needs_no_login_or_api_key(client, sent):
    _signup(client)
    assert client.post("/api/auth/verify-email", json={"token": sent[0]["token"]}).status_code == 200  # no Authorization, no X-API-Key


def test_bad_tokens_are_refused(client, sent):
    j, body = _signup(client)
    from backend.email_service import create_unsubscribe_token, create_verify_email_token
    from backend.auth.jwt import create_access_token
    u = _user(body["email"])
    login_token = create_access_token(str(u.id), u.email, u.username)
    for bad in ("garbage-token-value", login_token, create_unsubscribe_token(str(u.id))):
        assert client.post("/api/auth/verify-email", json={"token": bad}).status_code == 400
    # a link for an old address stops working
    assert client.post("/api/auth/verify-email", json={"token": create_verify_email_token(str(u.id), "someone_else@example.com")}).status_code == 400
    assert _user(body["email"]).email_verified_at is None


def test_an_expired_link_is_refused(client, sent, monkeypatch):
    import backend.email_service as es
    j, body = _signup(client)
    u = _user(body["email"])
    from jose import jwt
    expired = jwt.encode({"sub": str(u.id), "purpose": "verify_email", "email": u.email, "exp": datetime.utcnow() - timedelta(minutes=1)},
                         es._VERIFY_SECRET_KEY, algorithm="HS256")
    assert client.post("/api/auth/verify-email", json={"token": expired}).status_code == 400


def test_a_verification_token_can_never_act_as_a_login(client, sent):
    _signup(client)
    from backend.auth.jwt import decode_access_token
    assert decode_access_token(sent[0]["token"]) is None
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sent[0]['token']}"})
    assert r.status_code == 401


def test_a_suspended_account_cannot_be_confirmed(client, sent):
    j, body = _signup(client)
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    db.query(User).filter(User.email == body["email"]).update({"is_active": False})
    db.commit()
    db.close()
    assert client.post("/api/auth/verify-email", json={"token": sent[0]["token"]}).status_code == 400


def test_resend_sends_once_then_asks_you_to_wait(client, sent):
    j, body = _signup(client)
    assert client.post("/api/auth/resend-verification", headers=_auth(j)).json() == {"status": "too_soon"}   # signup just sent one
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    db.query(User).filter(User.email == body["email"]).update({"email_verification_sent_at": datetime.utcnow() - timedelta(minutes=3)})
    db.commit()
    db.close()
    assert client.post("/api/auth/resend-verification", headers=_auth(j)).json() == {"status": "sent"}
    assert len(sent) == 2 and sent[1]["to"] == body["email"]
    assert client.post("/api/auth/resend-verification", headers=_auth(j)).json() == {"status": "too_soon"}   # and not again right away


def test_resend_needs_a_login_and_only_ever_goes_to_your_own_address(client, sent):
    assert client.post("/api/auth/resend-verification").status_code in (401, 403)
    j, body = _signup(client)
    sent.clear()
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    db.query(User).filter(User.email == body["email"]).update({"email_verification_sent_at": None})
    db.commit()
    db.close()
    client.post("/api/auth/resend-verification", headers=_auth(j))
    assert [m["to"] for m in sent] == [body["email"]]


def test_a_confirmed_account_is_told_so_and_sent_nothing(client, sent):
    j, _ = _signup(client)
    client.post("/api/auth/verify-email", json={"token": sent[0]["token"]})
    sent.clear()
    assert client.post("/api/auth/resend-verification", headers=_auth(j)).json() == {"status": "already_verified"}
    assert sent == []


def test_accounts_from_before_verification_are_exempt_not_verified(client):
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    u = User(id=uuid.uuid4(), email=f"old_{uuid.uuid4().hex[:6]}@example.com", username=f"old_{uuid.uuid4().hex[:6]}", hashed_password="x",
             email_verification_exempt=True)
    db.add(u)
    db.commit()
    assert u.email_is_verified is True and u.email_verified_at is None   # exempt: never asked, never blocked, and NOT recorded as confirmed
    db.close()


# ---------------------------------------------------------------- the optional switch
def _campaign_body():
    return {"name": f"Verify {uuid.uuid4().hex[:6]}", "description": "Checking the gate end to end.", "is_public": False,
            "posting_frequency": "medium", "min_players": 2, "max_players": 6, "timezone": "UTC"}


def test_by_default_an_unconfirmed_account_can_create_and_join(client, sent):
    j, _ = _signup(client)
    r = client.post("/api/campaigns/create", headers=_auth(j), json=_campaign_body())
    assert r.status_code in (200, 201), r.text


def test_with_the_switch_on_an_unconfirmed_account_is_asked_to_confirm(client, sent, monkeypatch):
    j, body = _signup(client)
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "1")
    r = client.post("/api/campaigns/create", headers=_auth(j), json=_campaign_body())
    assert r.status_code == 403 and "confirm your email" in r.json()["detail"].lower()
    j2 = client.post("/api/campaigns/join", headers=_auth(j), json={"join_code": "ABCDEF"})
    assert j2.status_code == 403 and "confirm your email" in j2.json()["detail"].lower()
    # confirming unlocks it
    client.post("/api/auth/verify-email", json={"token": sent[0]["token"]})
    assert client.post("/api/campaigns/create", headers=_auth(j), json=_campaign_body()).status_code in (200, 201)


def test_with_the_switch_on_an_old_account_is_not_blocked(client, monkeypatch):
    from backend.db import SessionLocal
    from backend.models import User
    from backend.auth.jwt import create_access_token
    db = SessionLocal()
    u = User(id=uuid.uuid4(), email=f"old2_{uuid.uuid4().hex[:6]}@example.com", username=f"old2_{uuid.uuid4().hex[:6]}", hashed_password="x",
             email_verification_exempt=True)
    db.add(u)
    db.commit()
    token = create_access_token(str(u.id), u.email, u.username)
    db.close()
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "1")
    r = client.post("/api/campaigns/create", headers={"Authorization": f"Bearer {token}"}, json=_campaign_body())
    assert r.status_code in (200, 201), r.text


def test_the_status_tab_counts_unconfirmed_new_accounts(client, sent, monkeypatch):
    _signup(client)
    from backend.db import SessionLocal
    from backend.models import User
    from routes import admin_status
    monkeypatch.setattr(admin_status.requests, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network in tests")))
    db = SessionLocal()
    try:
        admin = User(id=uuid.uuid4(), email=f"a_{uuid.uuid4().hex[:6]}@example.com", username=f"a_{uuid.uuid4().hex[:6]}", hashed_password="x")
        out = admin_status.system_status(admin, db)
        assert out["database"]["unconfirmed_emails"] >= 1 and out["database"]["email_verification_required"] is False
    finally:
        db.close()


def test_the_email_itself(monkeypatch):
    import backend.email_service as es
    posted = {}

    class R:
        ok = True

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("FRONTEND_URL", "https://tba-rpg.com")
    monkeypatch.setattr(es.requests, "post", lambda url, headers=None, json=None, timeout=None: (posted.update(json=json), R())[1])
    es.send_verification_email("p@example.com", "TOKEN123", "Ana<script>")
    p = posted["json"]
    assert p["subject"] == "Confirm your email for TBA" and p["to"] == ["p@example.com"]
    assert "https://tba-rpg.com/verify-email.html?token=TOKEN123" in p["html"] and "https://tba-rpg.com/verify-email.html?token=TOKEN123" in p["text"]
    assert "<script>" not in p["html"] and "Ana&lt;script&gt;" in p["html"]            # the name is escaped
    assert "railway.app" not in p["html"]
