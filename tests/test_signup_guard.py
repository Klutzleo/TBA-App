"""
Signup protection: a honeypot field, a throwaway-email-domain block, and Cloudflare Turnstile that is OFF until its keys are configured.
Signup used to have nothing but a per-IP rate limit.
"""
import os
import uuid

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_signup_guard.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import signup_guard  # noqa: E402


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.app import application
    from backend.db import init_db
    init_db()
    return TestClient(application)


@pytest.fixture(autouse=True)
def _fresh_limiter_and_env(monkeypatch):
    from routes.auth import limiter
    limiter.reset()          # the signup limit is 10 an hour per IP and every test client shares one
    for k in ("TURNSTILE_SECRET_KEY", "TURNSTILE_SITE_KEY"):
        monkeypatch.delenv(k, raising=False)


def _signup(client, **extra):
    tag = uuid.uuid4().hex[:8]
    body = {"email": f"person_{tag}@example.com", "username": f"person_{tag}", "password": "A-good-password-1"}
    body.update(extra)
    return client.post("/api/auth/register", json=body), body


# ---------------------------------------------------------------- throwaway domains
@pytest.mark.parametrize("email", ["a@mailinator.com", "A@MAILINATOR.COM", "x@mail.mailinator.com", "z@guerrillamail.com", "q@yopmail.com"])
def test_throwaway_domains_are_recognised(email):
    assert signup_guard.is_disposable_email(email)


@pytest.mark.parametrize("email", ["a@gmail.com", "a@hotmail.com", "a@ucmerced.edu", "a@notmailinator.com", "a@mailinator.com.au", "a@b", "nope", ""])
def test_ordinary_domains_are_not_blocked(email):
    assert not signup_guard.is_disposable_email(email)


# ---------------------------------------------------------------- the route
def test_a_normal_signup_still_works_with_no_extra_fields(client):
    r, _ = _signup(client)
    assert r.status_code == 201 and r.json()["access_token"]


def test_a_normal_signup_works_with_an_empty_honeypot(client):
    r, _ = _signup(client, website="", turnstile_token=None)
    assert r.status_code == 201


def test_a_filled_honeypot_is_refused_and_creates_no_account(client):
    r, body = _signup(client, website="http://buy-pills.example")
    assert r.status_code == 400 and "Unable to create account" in r.json()["detail"]
    from backend.db import SessionLocal
    from backend.models import User
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == body["email"].lower()).count() == 0
    finally:
        db.close()


def test_a_throwaway_email_is_refused_with_a_clear_message(client):
    r, _ = _signup(client, email=f"bot_{uuid.uuid4().hex[:6]}@mailinator.com")
    assert r.status_code == 400 and "permanent email" in r.json()["detail"]


# ---------------------------------------------------------------- Cloudflare Turnstile
class _FakeClient:
    """Stands in for httpx.AsyncClient: records the call and answers (or fails) as told."""
    calls = []
    answer = {"success": True}
    status = 200
    error = None

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, data=None, **k):
        _FakeClient.calls.append((url, data))
        if _FakeClient.error:
            raise _FakeClient.error

        class R:
            status_code = _FakeClient.status

            def json(self_inner):
                return _FakeClient.answer

        return R()


@pytest.fixture
def turnstile_on(monkeypatch):
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "secret-for-tests")
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "0xSITEKEY-for-tests")
    monkeypatch.setattr(signup_guard.httpx, "AsyncClient", _FakeClient)
    _FakeClient.calls, _FakeClient.answer, _FakeClient.status, _FakeClient.error = [], {"success": True}, 200, None


def test_with_the_check_off_no_token_is_needed(client):
    r, _ = _signup(client)
    assert r.status_code == 201


def test_with_the_check_on_a_missing_token_is_refused_without_calling_cloudflare(client, turnstile_on):
    r, _ = _signup(client)
    assert r.status_code == 400 and "human check" in r.json()["detail"]
    assert _FakeClient.calls == []


def test_with_the_check_on_a_valid_token_gets_through_and_only_token_and_ip_are_sent(client, turnstile_on):
    r, body = _signup(client, turnstile_token="good-token")
    assert r.status_code == 201
    url, data = _FakeClient.calls[0]
    assert url == signup_guard.TURNSTILE_VERIFY_URL
    assert set(data) == {"secret", "response", "remoteip"}, "nothing about the person (email, username) goes to Cloudflare"
    assert body["email"] not in str(data) and body["username"] not in str(data)


def test_with_the_check_on_a_rejected_token_is_refused(client, turnstile_on):
    _FakeClient.answer = {"success": False, "error-codes": ["invalid-input-response"]}
    r, _ = _signup(client, turnstile_token="forged")
    assert r.status_code == 400 and "human check" in r.json()["detail"]


def test_if_cloudflare_is_unreachable_real_players_are_not_locked_out(client, turnstile_on):
    _FakeClient.error = httpx.ConnectError("down")
    r, _ = _signup(client, turnstile_token="anything")
    assert r.status_code == 201


def test_if_cloudflare_errors_with_a_5xx_real_players_are_not_locked_out(client, turnstile_on):
    _FakeClient.status = 503
    r, _ = _signup(client, turnstile_token="anything")
    assert r.status_code == 201


def test_the_honeypot_and_throwaway_block_run_before_cloudflare_is_asked(client, turnstile_on):
    _signup(client, website="x", turnstile_token="t")
    _signup(client, email=f"b_{uuid.uuid4().hex[:6]}@yopmail.com", turnstile_token="t")
    assert _FakeClient.calls == []


# ---------------------------------------------------------------- the page and its config
def test_signup_config_is_null_until_configured(client, monkeypatch):
    assert client.get("/api/public/signup-config").json() == {"turnstile_site_key": None}
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "0xSITEKEY")
    assert client.get("/api/public/signup-config").json() == {"turnstile_site_key": None}, "a site key alone does not turn the check on"
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "s")
    assert client.get("/api/public/signup-config").json() == {"turnstile_site_key": "0xSITEKEY"}


def test_signup_config_is_public(client):
    assert client.get("/api/public/signup-config").status_code == 200       # no token, no API key


def test_the_signup_page_has_the_honeypot_and_the_human_check_wiring():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "auth.html"), encoding="utf-8").read()
    for needle in ('id="register-website"', 'tabindex="-1"', 'id="turnstile-box"', "signup-config", "challenges.cloudflare.com/turnstile",
                   "turnstile_token", "website,"):
        assert needle in html, needle


def test_a_secret_without_a_site_key_does_not_lock_anyone_out(client, monkeypatch):
    """Half-configured: the page would show no widget, so the server must not demand a token either."""
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "secret-only")
    monkeypatch.delenv("TURNSTILE_SITE_KEY", raising=False)
    assert client.get("/api/public/signup-config").json() == {"turnstile_site_key": None}
    r, _ = _signup(client)
    assert r.status_code == 201
