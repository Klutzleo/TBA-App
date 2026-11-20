"""
Email Service
Sends transactional emails via Resend API (https://resend.com).

Required environment variables:
    RESEND_API_KEY — API key from Resend dashboard
    FROM_EMAIL     — verified sender, e.g. no-reply@gameoctane.com
    FRONTEND_URL   — the site's public address, used for every link in an email. Defaults to https://tba-rpg.com. It must be the
                     real domain: links to a shared host like *.railway.app are a spam signal and don't match the sender.
    REPLY_TO_EMAIL — optional; a monitored inbox people can reply to. Unset means no Reply-To header.
    MODERATION_EMAIL — optional; where content-report emails go (comma separated). If unset, they go to the
                       email on each account listed in ADMIN_USER_IDS.
"""

import hashlib
import os
import sys
import logging
from datetime import datetime, timedelta

import requests
from jose import jwt

from backend.auth.jwt import SECRET_KEY as _AUTH_SECRET_KEY  # one source for the secret (fails closed in prod)

logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_URL = "https://tba-rpg.com"


def get_frontend_url() -> str:
    """Base address for links inside emails (no trailing slash). Always the real site, never a shared railway.app address."""
    return (os.getenv("FRONTEND_URL") or DEFAULT_FRONTEND_URL).rstrip("/")


def _html_to_text(s: str) -> str:
    """A readable plain-text version of a small HTML snippet (a digest line)."""
    import html as _h
    import re as _re
    s = _re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>", "\n", s or "")
    s = _re.sub(r"<[^>]+>", "", s)
    s = _h.unescape(s)
    s = _re.sub(r"[ \t]+", " ", s)
    return _re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _email_payload(to, subject: str, html_body: str, text_body: str, headers: dict = None) -> dict:
    """The Resend request body. Every email carries a plain-text part as well as the HTML (an HTML-only message scores worse with
    spam filters), and an optional Reply-To so a real person can answer."""
    payload = {
        "from": f"TBA App <{os.getenv('FROM_EMAIL', 'no-reply@gameoctane.com')}>",
        "to": to,
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    reply_to = os.getenv("REPLY_TO_EMAIL", "").strip()
    if reply_to:
        payload["reply_to"] = reply_to
    if headers:
        payload["headers"] = headers
    return payload


def _safe_print(s: str) -> None:
    """print(), but never crash on a console codepage that can't encode some
    character (e.g. an emoji on Windows' default cp1252 console) — this only
    feeds the dev-mode fallback prints below, never the actual email payload."""
    try:
        print(s)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(s.encode(enc, errors="replace").decode(enc))

# SECURITY: this must NOT be signed with the same key as real login tokens (backend/auth/jwt.py's
# SECRET_KEY). backend.auth.jwt.verify_token()/get_current_user() — the dependency every
# protected route uses — decodes with that same SECRET_KEY and never checks a "purpose" claim
# or requires an expiry, so a token signed with SECRET_KEY would decode there too and function
# as a permanent, unrevoked Bearer token for the account, regardless of what this module
# intends it for. Deriving a distinct key means it can never validate against the real auth
# path at all, independent of any purpose-checking logic (defense at the right layer, not
# just a convention every future call site has to remember to honor).
_UNSUBSCRIBE_SECRET_KEY = hashlib.sha256(
    (_AUTH_SECRET_KEY + "|unsubscribe-token|v1").encode()
).hexdigest()
_ALGORITHM = "HS256"
_UNSUBSCRIBE_TOKEN_DAYS = 90  # bounds exposure if a token ever leaks (mail-relay logs, forwarded email, etc.)


def create_unsubscribe_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": "unsubscribe",
        "exp": datetime.utcnow() + timedelta(days=_UNSUBSCRIBE_TOKEN_DAYS),
    }
    return jwt.encode(payload, _UNSUBSCRIBE_SECRET_KEY, algorithm=_ALGORITHM)


def verify_unsubscribe_token(token: str) -> str | None:
    """Returns the user_id if valid (right key, right purpose, not expired), else None."""
    from backend.auth.jwt import decode_with_key

    payload = decode_with_key(token, _UNSUBSCRIBE_SECRET_KEY, _ALGORITHM)
    if not payload or payload.get("purpose") != "unsubscribe":
        return None
    return payload.get("sub")


def send_password_reset_email(to_email: str, reset_token: str, username: str = None) -> None:
    api_key      = os.getenv("RESEND_API_KEY", "")
    from_email   = os.getenv("FROM_EMAIL", "no-reply@gameoctane.com")
    frontend_url = get_frontend_url()

    reset_url = f"{frontend_url}/reset-password.html?token={reset_token}"
    # Greeting by name: a message addressed to a real person looks far less like a phishing template to spam filters
    import html as _html_mod
    hello_html = f"<p>Hi {_html_mod.escape(username)},</p>" if username else ""
    hello_text = f"Hi {username},\n\n" if username else ""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#1a1d29;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
    <h1 style="color:#d4a017;margin:0;font-size:28px;">TBA</h1>
    <p style="color:#aaa;margin:8px 0 0;font-size:15px;">Tools for the Bad Ass</p>
  </div>
  <div style="background:#fff;padding:30px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 10px 10px;">
    <h2 style="color:#d4a017;margin-top:0;">Password Reset Request</h2>
    {hello_html}
    <p>We received a request to reset your password. Click the button below to set a new one:</p>
    <div style="text-align:center;margin:30px 0;">
      <a href="{reset_url}"
         style="background:#d4a017;color:#1a1d29;padding:14px 30px;text-decoration:none;
                border-radius:6px;font-weight:bold;display:inline-block;">
        Reset Password
      </a>
    </div>
    <p style="color:#666;font-size:13px;">Or copy and paste this link into your browser:</p>
    <p style="background:#f5f5f5;padding:12px;border-radius:5px;word-break:break-all;font-size:12px;color:#555;">
      {reset_url}
    </p>
    <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:15px;margin:25px 0;border-radius:4px;">
      <p style="margin:0;color:#856404;font-size:14px;">
        <strong>This link expires in 1 hour.</strong>
      </p>
    </div>
    <p style="color:#999;font-size:13px;">
      If you didn't request a password reset, you can safely ignore this email.
    </p>
  </div>
  <div style="text-align:center;padding:16px;color:#999;font-size:12px;">
    TBA App. This is an automated email.
  </div>
</body>
</html>"""
    text_content = (
        "Reset your TBA password\n\n"
        f"{hello_text}"
        "We received a request to reset your password. Open this link to set a new one:\n"
        f"{reset_url}\n\n"
        "This link expires in 1 hour.\n\n"
        "If you didn't request a password reset, you can safely ignore this email.\n\n"
        "TBA App. This is an automated email."
    )

    if not api_key:
        logger.warning("RESEND_API_KEY not set — printing reset link to console")
        print("\n" + "="*60)
        print(f"PASSWORD RESET for {to_email}")
        print(f"Link: {reset_url}")
        print("="*60 + "\n")
        return

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=_email_payload([to_email], "Reset Your TBA Password", html_content, text_content),
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        logger.info(f"Password reset email sent to {to_email} (status {resp.status_code})")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        raise


def send_digest_email(to_email: str, lines: list, unsubscribe_url: str) -> None:
    """
    Sends the twice-daily notification digest: 'your turn' / '@mention' items that
    happened while the recipient was away. `lines` is a list of already-rendered
    HTML strings (one per item), built by backend/notification_digest.py — this
    function only handles the email envelope, not the gating/bundling logic.
    """
    api_key      = os.getenv("RESEND_API_KEY", "")
    from_email   = os.getenv("FROM_EMAIL", "no-reply@gameoctane.com")
    frontend_url = get_frontend_url()

    items_html = "".join(
        f'<div style="padding:12px 0;border-bottom:1px solid #eee;">{line}</div>' for line in lines
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#1a1d29;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
    <h1 style="color:#d4a017;margin:0;font-size:28px;">TBA</h1>
    <p style="color:#aaa;margin:8px 0 0;font-size:15px;">Tools for the Bad Ass</p>
  </div>
  <div style="background:#fff;padding:30px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 10px 10px;">
    <h2 style="color:#d4a017;margin-top:0;">While you were away</h2>
    {items_html}
    <div style="text-align:center;margin:30px 0;">
      <a href="{frontend_url}/game.html"
         style="background:#d4a017;color:#1a1d29;padding:14px 30px;text-decoration:none;
                border-radius:6px;font-weight:bold;display:inline-block;">
        Open TBA
      </a>
    </div>
  </div>
  <div style="text-align:center;padding:16px;color:#999;font-size:12px;">
    TBA App. Automated, at most twice a day.
    <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe from these emails</a>
  </div>
</body>
</html>"""
    text_content = (
        "While you were away\n\n"
        + "\n".join("- " + _html_to_text(line) for line in lines)
        + f"\n\nOpen TBA: {frontend_url}/game.html\n\n"
        f"TBA App. Automated, at most twice a day.\nUnsubscribe from these emails: {unsubscribe_url}"
    )

    if not api_key:
        logger.warning("RESEND_API_KEY not set — printing digest to console instead")
        _safe_print("\n" + "="*60)
        _safe_print(f"DIGEST EMAIL for {to_email}")
        for line in lines:
            _safe_print(f"  - {line}")
        _safe_print(f"Unsubscribe: {unsubscribe_url}")
        _safe_print("="*60 + "\n")
        return

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=_email_payload([to_email], "While you were away on TBA", html_content, text_content,
                                headers={"List-Unsubscribe": f"<{unsubscribe_url}>"}),
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        logger.info(f"Digest email sent to {to_email} (status {resp.status_code})")
    except Exception as e:
        logger.error(f"Failed to send digest email: {e}")
        raise


def send_report_email(to_emails: list, report: dict) -> None:
    """
    Tells the admin(s) that someone reported content. `report` holds plain strings:
    content_label, campaign_name, reason, note, reporter. Everything user-controlled is
    HTML-escaped. The reported image is deliberately a link, not an inline <img>, so an
    offensive image never loads into an inbox preview; review happens on the admin page.
    """
    import html as _html

    if not to_emails:
        logger.warning("Report email skipped: no admin recipients configured (set ADMIN_USER_IDS)")
        return

    api_key      = os.getenv("RESEND_API_KEY", "")
    from_email   = os.getenv("FROM_EMAIL", "no-reply@gameoctane.com")
    frontend_url = get_frontend_url()
    esc = lambda v: _html.escape(str(v or ""))
    review_url = f"{frontend_url}/admin-reports.html"

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="color:#b91c1c;margin-top:0;">New report: {esc(report.get("content_label"))}</h2>
  <p><strong>Campaign:</strong> {esc(report.get("campaign_name"))}</p>
  <p><strong>Reason:</strong> {esc(report.get("reason"))}</p>
  <p><strong>Note:</strong> {esc(report.get("note")) or "(none)"}</p>
  <p><strong>Reported by:</strong> {esc(report.get("reporter"))}</p>
  <p><a href="{esc(review_url)}" style="background:#d4a017;color:#1a1d29;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">Review reports</a></p>
  <p style="color:#999;font-size:12px;">Sign in as an admin to see the image and act on it. Nothing in this email changes anything.</p>
</body>
</html>"""

    text_content = (
        f"New report: {report.get('content_label') or ''}\n\n"
        f"Campaign: {report.get('campaign_name') or ''}\nReason: {report.get('reason') or ''}\n"
        f"Note: {report.get('note') or '(none)'}\nReported by: {report.get('reporter') or ''}\n\n"
        f"Review it: {review_url}\n\nSign in as an admin to see the image and act on it. Nothing in this email changes anything."
    )

    if not api_key:
        logger.warning("RESEND_API_KEY not set - printing report email to console instead")
        _safe_print(f"REPORT EMAIL to {to_emails}: {report}")
        return

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=_email_payload(list(to_emails), "TBA report: " + str(report.get("content_label") or "content"), html_content, text_content),
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        logger.info(f"Report email sent to {len(to_emails)} admin(s)")
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        raise


def send_admin_alert_email(to_emails: list, subject: str, lines: list, link_path: str = "/admin.html") -> None:
    """A short heads-up to the admin about a new report. `lines` are plain strings (HTML-escaped here). The email carries a link, never the
    evidence itself: private chat stays behind the admin sign-in. Raises on a provider error so the caller can log it."""
    import html as _html
    if not to_emails:
        logger.warning("Admin alert skipped: no admin recipients configured")
        return
    api_key = os.getenv("RESEND_API_KEY", "")
    url = f"{get_frontend_url()}{link_path}"
    esc = lambda v: _html.escape(str(v or ""))
    body = "".join(f"<p>{esc(l)}</p>" for l in lines)
    html_content = (f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;'
                    f'max-width:600px;margin:0 auto;padding:20px;"><h2 style="color:#b91c1c;margin-top:0;">{esc(subject)}</h2>{body}'
                    f'<p><a href="{esc(url)}" style="background:#d4a017;color:#1a1d29;padding:12px 24px;text-decoration:none;border-radius:6px;'
                    f'font-weight:bold;display:inline-block;">Open the inbox</a></p><p style="color:#999;font-size:12px;">Sign in as an admin to read it. '
                    f'Nothing in this email changes anything.</p></body></html>')
    text_content = "\n\n".join([subject] + list(lines) + [f"Open the inbox: {url}"])
    if not api_key:
        logger.warning("RESEND_API_KEY not set - printing admin alert to console instead")
        _safe_print(f"ADMIN ALERT to {to_emails}: {subject} {lines}")
        return
    resp = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                         json=_email_payload(list(to_emails), subject, html_content, text_content), timeout=10)
    if not resp.ok:
        logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()


def send_admin_message_email(to_email: str, subject: str, body: str) -> None:
    """A message from the site admin to one player. The text is the admin's own, so it is HTML-escaped and sent as paragraphs; the email says
    plainly who it is from and that replies reach the admin when REPLY_TO_EMAIL is set. Raises on a provider error so the caller can log it."""
    import html as _html
    api_key = os.getenv("RESEND_API_KEY", "")
    url = get_frontend_url()
    esc = lambda v: _html.escape(str(v or ""))
    paras = "".join(f"<p>{esc(p)}</p>" for p in str(body).split("\n\n") if p.strip())
    html_content = (f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;'
                    f'max-width:600px;margin:0 auto;padding:20px;"><h2 style="color:#1a1d29;margin-top:0;">{esc(subject)}</h2>{paras}'
                    f'<p><a href="{esc(url)}" style="background:#d4a017;color:#1a1d29;padding:12px 24px;text-decoration:none;border-radius:6px;'
                    f'font-weight:bold;display:inline-block;">Open TBA</a></p>'
                    f'<p style="color:#999;font-size:12px;">This message is from the TBA site admin.</p></body></html>')
    text_content = f"{subject}\n\n{body}\n\nOpen TBA: {url}\n\nThis message is from the TBA site admin."
    if not api_key:
        logger.warning("RESEND_API_KEY not set - printing admin message to console instead")
        _safe_print(f"ADMIN MESSAGE to {to_email}: {subject}")
        return
    resp = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                         json=_email_payload([to_email], subject, html_content, text_content), timeout=10)
    if not resp.ok:
        logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()


# ---- Email verification ----------------------------------------------------------------------------------------------------------------------
# Same safety design as the unsubscribe token: a key derived from SECRET_KEY but different from it, so this token can never validate as a login
# token (and a login token can never validate here), plus a purpose claim, an expiry, and the address it was issued for, so a link for an old
# address stops working if the address ever changes.
_VERIFY_SECRET_KEY = hashlib.sha256((_AUTH_SECRET_KEY + "|verify-email-token|v1").encode()).hexdigest()
_VERIFY_TOKEN_DAYS = 3


def create_verify_email_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": "verify_email",
        "email": (email or "").lower(),
        "exp": datetime.utcnow() + timedelta(days=_VERIFY_TOKEN_DAYS),
    }
    return jwt.encode(payload, _VERIFY_SECRET_KEY, algorithm=_ALGORITHM)


def verify_email_token(token: str) -> tuple[str, str] | None:
    """Returns (user_id, email) if the token is valid (right key, right purpose, not expired), else None."""
    from backend.auth.jwt import decode_with_key

    payload = decode_with_key(token, _VERIFY_SECRET_KEY, _ALGORITHM)
    if not payload or payload.get("purpose") != "verify_email" or not payload.get("sub") or not payload.get("email"):
        return None
    return payload["sub"], payload["email"]


def send_verification_email(to_email: str, token: str, username: str = None) -> None:
    """The confirmation link. It opens a page with a button rather than confirming on load, because mail scanners open links before a person does.
    Raises on a provider error so the caller can decide what to do (signup never fails because of it)."""
    import html as _html

    api_key = os.getenv("RESEND_API_KEY", "")
    url = f"{get_frontend_url()}/verify-email.html?token={token}"
    esc = lambda v: _html.escape(str(v or ""))
    hello_html = f"<p>Hi {esc(username)},</p>" if username else ""
    hello_text = f"Hi {username},\n\n" if username else ""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#1a1d29;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
    <h1 style="color:#d4a017;margin:0;font-size:28px;">TBA</h1>
    <p style="color:#aaa;margin:8px 0 0;font-size:15px;">Tools for the Bad Ass</p>
  </div>
  <div style="background:#fff;padding:30px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 10px 10px;">
    <h2 style="color:#d4a017;margin-top:0;">Confirm your email</h2>
    {hello_html}
    <p>Welcome to TBA. Please confirm that this is your email address so we can reach you about your campaigns and help you if you ever lose your password.</p>
    <p style="text-align:center;margin:28px 0;"><a href="{esc(url)}" style="background:#d4a017;color:#1a1d29;padding:14px 32px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">Confirm my email</a></p>
    <p style="color:#666;font-size:13px;">This link works for {_VERIFY_TOKEN_DAYS} days. If you did not create a TBA account, you can ignore this email and nothing will happen.</p>
    <p style="color:#999;font-size:12px;">Button not working? Copy this link into your browser:<br>{esc(url)}</p>
  </div>
</body>
</html>"""

    text_content = (
        f"{hello_text}Welcome to TBA. Please confirm that this is your email address so we can reach you about your campaigns "
        f"and help you if you ever lose your password.\n\nConfirm my email: {url}\n\n"
        f"This link works for {_VERIFY_TOKEN_DAYS} days. If you did not create a TBA account, you can ignore this email and nothing will happen."
    )

    if not api_key:
        logger.warning("RESEND_API_KEY not set - printing verification email to console instead")
        _safe_print(f"VERIFICATION EMAIL to {to_email}: {url}")
        return

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=_email_payload([to_email], "Confirm your email for TBA", html_content, text_content),
        timeout=10,
    )
    if not resp.ok:
        logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
