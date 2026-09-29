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
