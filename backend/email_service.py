"""
Email Service
Sends transactional emails via Resend API (https://resend.com).

Required environment variables:
    RESEND_API_KEY — API key from Resend dashboard
    FROM_EMAIL     — verified sender, e.g. no-reply@gameoctane.com
    FRONTEND_URL   — defaults to https://tba-app-production.up.railway.app
"""

import os
import sys
import logging
import requests
from jose import jwt

logger = logging.getLogger(__name__)


def _safe_print(s: str) -> None:
    """print(), but never crash on a console codepage that can't encode some
    character (e.g. an emoji on Windows' default cp1252 console) — this only
    feeds the dev-mode fallback prints below, never the actual email payload."""
    try:
        print(s)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(s.encode(enc, errors="replace").decode(enc))

# Reuses the same signing key/algorithm as backend/auth/jwt.py, but this token
# has its own "purpose" claim and no expiry — it needs to keep working for as
# long as an old digest email might still be sitting in someone's inbox.
_SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
_ALGORITHM = "HS256"


def create_unsubscribe_token(user_id: str) -> str:
    return jwt.encode({"sub": str(user_id), "purpose": "unsubscribe"}, _SECRET_KEY, algorithm=_ALGORITHM)


def verify_unsubscribe_token(token: str) -> str | None:
    """Returns the user_id if valid, else None."""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except Exception:
        return None
    if payload.get("purpose") != "unsubscribe":
        return None
    return payload.get("sub")


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    api_key      = os.getenv("RESEND_API_KEY", "")
    from_email   = os.getenv("FROM_EMAIL", "no-reply@gameoctane.com")
    frontend_url = os.getenv("FRONTEND_URL", "https://tba-app-production.up.railway.app")

    reset_url = f"{frontend_url}/reset-password.html?token={reset_token}"

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
        <strong>⚠️ This link expires in 1 hour.</strong>
      </p>
    </div>
    <p style="color:#999;font-size:13px;">
      If you didn't request a password reset, you can safely ignore this email.
    </p>
  </div>
  <div style="text-align:center;padding:16px;color:#999;font-size:12px;">
    TBA App — This is an automated email, please do not reply.
  </div>
</body>
</html>"""

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
            json={
                "from": f"TBA App <{from_email}>",
                "to": [to_email],
                "subject": "Reset Your TBA Password",
                "html": html_content,
            },
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
    frontend_url = os.getenv("FRONTEND_URL", "https://tba-app-production.up.railway.app")

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
    TBA App — automated, at most twice a day.
    <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe from these emails</a>
  </div>
</body>
</html>"""

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
            json={
                "from": f"TBA App <{from_email}>",
                "to": [to_email],
                "subject": "While you were away — TBA",
                "html": html_content,
            },
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        logger.info(f"Digest email sent to {to_email} (status {resp.status_code})")
    except Exception as e:
        logger.error(f"Failed to send digest email: {e}")
        raise
