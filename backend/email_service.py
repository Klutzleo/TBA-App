"""
Email Service
Sends transactional emails via Resend API (https://resend.com).

Required environment variables:
    RESEND_API_KEY — API key from Resend dashboard
    FROM_EMAIL     — verified sender, e.g. no-reply@gameoctane.com
    FRONTEND_URL   — defaults to https://tba-app-production.up.railway.app
"""

import os
import logging
import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)


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

    payload = json.dumps({
        "from": f"TBA App <{from_email}>",
        "to": [to_email],
        "subject": "Reset Your TBA Password",
        "html": html_content,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"Password reset email sent to {to_email} (status {resp.status})")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error(f"Resend API error {e.code}: {body}")
        raise
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        raise
