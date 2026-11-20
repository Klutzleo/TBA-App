"""
Email verification at signup.

New accounts are sent a confirmation link. Confirming sets users.email_verified_at. Nothing is blocked by default: after the junk-folder trouble
with some mail providers, locking a real player out because the email landed in spam would do more harm than good. REQUIRE_VERIFIED_EMAIL=1
(an environment variable, off by default) makes creating or joining a campaign require a confirmed address once Jason decides the mail is
reliable. Accounts that existed before this feature are exempt, so the switch can never lock out someone who is already playing.
"""
import logging
import os
from datetime import datetime, timedelta

from fastapi import HTTPException

from backend.email_service import create_verify_email_token, send_verification_email

logger = logging.getLogger(__name__)

RESEND_GAP = timedelta(minutes=2)  # one confirmation email per account per two minutes, however the button is pressed

UNVERIFIED_MESSAGE = ("Please confirm your email address first. We sent you a link when you signed up, "
                      "and you can send it again from the banner at the top of the page.")


def enforced() -> bool:
    """Read on every call so a Railway change and tests take effect immediately."""
    return os.getenv("REQUIRE_VERIFIED_EMAIL", "").strip().lower() in ("1", "true", "yes", "on")


def require_verified(user) -> None:
    """Gate for creating or joining a campaign. Does nothing unless the switch is on."""
    if enforced() and not user.email_is_verified:
        raise HTTPException(status_code=403, detail=UNVERIFIED_MESSAGE)


def can_send_again(user, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return user.email_verification_sent_at is None or now - user.email_verification_sent_at >= RESEND_GAP


def send_link(user) -> None:
    """Build and send the link. Blocking (a network call); run it in a background task. A provider failure is logged, never raised to a player."""
    try:
        send_verification_email(user.email, create_verify_email_token(str(user.id), user.email), user.username)
    except Exception as e:
        logger.error(f"Could not send a verification email: {type(e).__name__}")
