"""
Signup protection (added 2026-11-18). Signup had no email check and nothing but a per-IP rate limit, so a bot could create accounts freely.

Three cheap layers, none of which needs a person to confirm an email:
  1. A honeypot field the form hides from people. Bots fill every field; a filled one means a bot.
  2. A block on well-known throwaway-email domains. Best effort: the list can never be complete, but it stops the lazy cases.
  3. Cloudflare Turnstile, a free human check that is mostly invisible. It switches on only when BOTH TURNSTILE_SECRET_KEY and
     TURNSTILE_SITE_KEY are set, so shipping this code changes nothing until those two settings exist, and a half-configured setup
     (a secret with no site key, so no widget on the page) can never lock real players out.

Turnstile verifies the token with Cloudflare. If Cloudflare itself cannot be reached we let the signup through (and log it) rather
than lock every real player out during their outage; an explicitly invalid or missing token is always refused.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Throwaway and disposable-inbox services. A match on the domain or any parent of it (so mail.mailinator.com is caught too).
DISPOSABLE_DOMAINS = frozenset("""
mailinator.com guerrillamail.com guerrillamail.net guerrillamail.org guerrillamail.biz guerrillamail.de guerrillamailblock.com
sharklasers.com grr.la spam4.me 10minutemail.com 10minutemail.net 20minutemail.com 10minemail.com minuteinbox.com
tempmail.com temp-mail.org temp-mail.io tempmail.net tempmailo.com tempail.com tempr.email tempinbox.com tmpmail.org tmpmail.net tmail.ws
yopmail.com yopmail.net yopmail.fr trashmail.com trashmail.net trashmail.de throwawaymail.com getnada.com nada.email dispostable.com
maildrop.cc fakeinbox.com mintemail.com mohmal.com emailondeck.com mailnesia.com mytemp.email burnermail.io discard.email discardmail.com
spambox.us spamgourmet.com mailcatch.com moakt.com mail.tm inboxkitten.com harakirimail.com instantemailaddress.com jetable.org
mailforspam.com fakemail.net emailfake.com crazymailing.com dropmail.me 1secmail.com 1secmail.net 1secmail.org linshiyouxiang.net
trbvm.com mailpoof.com luxusmail.org anonbox.net smailpro.com emltmp.com byom.de owlymail.com wegwerfmail.de wegwerfemail.de einrot.com
cuvox.de dayrep.com armyspy.com fleckens.hu gustr.com jourrapide.com rhyta.com superrito.com teleworm.us
""".split())


def is_disposable_email(email: str) -> bool:
    """True when the address is on a known throwaway-email domain (or a subdomain of one)."""
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].strip().lower().rstrip(".")
    parts = domain.split(".")
    return any(".".join(parts[i:]) in DISPOSABLE_DOMAINS for i in range(len(parts) - 1))


def turnstile_enabled() -> bool:
    """The human check is on only when both keys exist."""
    return bool(os.getenv("TURNSTILE_SECRET_KEY", "").strip() and os.getenv("TURNSTILE_SITE_KEY", "").strip())


def turnstile_site_key() -> str | None:
    """The public site key the page needs, or None when the human check is off."""
    return os.getenv("TURNSTILE_SITE_KEY", "").strip() if turnstile_enabled() else None


async def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    """True when the human check passes or is switched off. Only the token and the visitor's IP go to Cloudflare."""
    if not turnstile_enabled():
        return True
    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data={"secret": secret, "response": token, "remoteip": remote_ip or ""})
        if resp.status_code >= 500:
            logger.warning("Turnstile: Cloudflare answered %s, letting this signup through", resp.status_code)
            return True
        return bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Turnstile: could not reach Cloudflare (%s), letting this signup through", type(e).__name__)
        return True
