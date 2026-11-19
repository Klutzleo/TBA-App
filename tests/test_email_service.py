"""
Tests for backend/email_service.py's unsubscribe token.

Regression coverage for a real vulnerability found by review (2026-09-29): the
first version of this token was signed with the same SECRET_KEY as real login
tokens, with no expiry and no purpose check on the actual auth path — meaning
it functioned as a permanent, unrevoked Bearer token for the account, not just
a one-click preference toggle. The fix derives a distinct signing key and adds
a real expiry; these tests prove both halves of that fix, from both directions
(a real login token must not work as an unsubscribe token either).
"""
import pytest

from backend.email_service import create_unsubscribe_token, verify_unsubscribe_token
from backend.auth.jwt import create_access_token, verify_token


def test_unsubscribe_token_round_trips_correctly():
    token = create_unsubscribe_token("11111111-1111-1111-1111-111111111111")
    assert verify_unsubscribe_token(token) == "11111111-1111-1111-1111-111111111111"


def test_unsubscribe_token_is_rejected_by_the_real_login_auth_path():
    """The critical regression check: an unsubscribe token must NOT decode
    successfully through backend.auth.jwt.verify_token() — if it did, it would
    work as a real Bearer token via get_current_user() for every protected
    route, not just the unsubscribe endpoint."""
    token = create_unsubscribe_token("11111111-1111-1111-1111-111111111111")
    assert verify_token(token) is None


def test_real_login_token_is_rejected_by_verify_unsubscribe_token():
    """The other direction: a real login token must not be usable to flip
    someone's email preference via the unsubscribe link."""
    login_token = create_access_token("11111111-1111-1111-1111-111111111111", "a@example.com", "alice")
    assert verify_unsubscribe_token(login_token) is None


def test_unsubscribe_token_has_an_expiry():
    import jose.jwt as jose_jwt
    from backend.email_service import _UNSUBSCRIBE_SECRET_KEY, _ALGORITHM

    token = create_unsubscribe_token("11111111-1111-1111-1111-111111111111")
    payload = jose_jwt.decode(token, _UNSUBSCRIBE_SECRET_KEY, algorithms=[_ALGORITHM])
    assert "exp" in payload


def test_garbage_token_is_rejected():
    assert verify_unsubscribe_token("not.a.real.token") is None


def test_token_with_right_key_wrong_purpose_is_rejected():
    """Defense in depth: even a token signed with the correct unsubscribe key
    is rejected if it doesn't carry purpose=unsubscribe."""
    import jose.jwt as jose_jwt
    from backend.email_service import _UNSUBSCRIBE_SECRET_KEY, _ALGORITHM

    token = jose_jwt.encode({"sub": "x", "purpose": "something-else"}, _UNSUBSCRIBE_SECRET_KEY, algorithm=_ALGORITHM)
    assert verify_unsubscribe_token(token) is None


# ---------------------------------------------------------------- deliverability (2026-11-18)
# Reset emails were landing in spam. Two causes found in the code: every link pointed at a shared *.railway.app address (FRONTEND_URL was
# never set), and the messages were HTML-only. These tests keep both fixed.
class _Captured:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(json)

        class R:
            ok = True
            status_code = 200
            text = ""

        return R()


@pytest.fixture
def sent(monkeypatch):
    from backend import email_service
    cap = _Captured()
    monkeypatch.setattr(email_service.requests, "post", cap.post)
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("REPLY_TO_EMAIL", raising=False)
    return cap


def test_links_default_to_the_real_site_never_a_railway_address(sent):
    from backend.email_service import send_password_reset_email, send_digest_email, send_report_email
    send_password_reset_email("a@example.com", "tok123")
    send_digest_email("a@example.com", ["<b>Your turn</b> in Test"], "https://tba-rpg.com/api/profile/unsubscribe?token=x")
    send_report_email(["admin@example.com"], {"content_label": "a cover", "campaign_name": "C", "reason": "r", "note": "", "reporter": "p"})
    assert len(sent.calls) == 3
    for body in sent.calls:
        blob = body["html"] + body["text"]
        assert "railway.app" not in blob, body["subject"]
        assert "https://tba-rpg.com" in blob, body["subject"]


def test_frontend_url_env_is_respected_and_trailing_slash_is_trimmed(sent, monkeypatch):
    from backend.email_service import send_password_reset_email
    monkeypatch.setenv("FRONTEND_URL", "https://example.org/")
    send_password_reset_email("a@example.com", "tok123")
    assert "https://example.org/reset-password.html?token=tok123" in sent.calls[0]["text"]
    assert "example.org//" not in sent.calls[0]["html"]


def test_every_email_has_a_plain_text_part_with_the_link(sent):
    from backend.email_service import send_password_reset_email, send_digest_email, send_report_email
    send_password_reset_email("a@example.com", "tok123")
    send_digest_email("a@example.com", ['<a href="x">Beef</a>: it is <b>your turn</b> in Test'], "https://tba-rpg.com/u?token=x")
    send_report_email(["admin@example.com"], {"content_label": "a cover", "campaign_name": "C", "reason": "r", "note": "n", "reporter": "p"})
    reset, digest, report = sent.calls
    assert "reset-password.html?token=tok123" in reset["text"] and "<" not in reset["text"]
    assert "Beef: it is your turn in Test" in digest["text"] and "<b>" not in digest["text"] and "unsubscribe" in digest["text"].lower()
    assert "admin-reports.html" in report["text"]


def test_the_digest_carries_a_list_unsubscribe_header(sent):
    from backend.email_service import send_digest_email
    send_digest_email("a@example.com", ["x"], "https://tba-rpg.com/api/profile/unsubscribe?token=abc")
    assert sent.calls[0]["headers"]["List-Unsubscribe"] == "<https://tba-rpg.com/api/profile/unsubscribe?token=abc>"


def test_reply_to_is_only_set_when_configured(sent, monkeypatch):
    from backend.email_service import send_password_reset_email
    send_password_reset_email("a@example.com", "t")
    assert "reply_to" not in sent.calls[0]
    monkeypatch.setenv("REPLY_TO_EMAIL", "TBA@gameoctane.com")
    send_password_reset_email("a@example.com", "t")
    assert sent.calls[1]["reply_to"] == "TBA@gameoctane.com"


def test_email_copy_has_no_em_dashes(sent):
    from backend.email_service import send_password_reset_email, send_digest_email
    send_password_reset_email("a@example.com", "t")
    send_digest_email("a@example.com", ["x"], "https://tba-rpg.com/u")
    for body in sent.calls:
        assert "\u2014" not in body["subject"] + body["html"] + body["text"]
