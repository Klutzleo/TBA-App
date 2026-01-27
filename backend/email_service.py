"""
Email Service

Handles sending transactional emails (password resets, etc.)
Uses SendGrid in production, console output in development.
"""

import os
from typing import Optional


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """
    Send a password reset email to the user.

    In production (when SENDGRID_API_KEY is set):
        Sends email via SendGrid

    In development (when SENDGRID_API_KEY is not set):
        Prints reset link to console

    Args:
        to_email: Recipient email address
        reset_token: Password reset token

    Raises:
        Exception: If SendGrid API call fails
    """
    # Get configuration from environment
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "noreply@tba-app.com")
    frontend_url = os.getenv("FRONTEND_URL", "https://tba-app-production.up.railway.app")

    # Build reset URL
    reset_url = f"{frontend_url}/reset-password?token={reset_token}"

    # Email content
    subject = "Reset Your TBA Password"
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">TBA App</h1>
        <p style="color: #f0f0f0; margin: 10px 0 0 0; font-size: 16px;">Password Reset Request</p>
    </div>

    <div style="background-color: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        <h2 style="color: #667eea; margin-top: 0;">Reset Your Password</h2>

        <p>We received a request to reset your password. Click the button below to create a new password:</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white;
                      padding: 14px 30px;
                      text-decoration: none;
                      border-radius: 5px;
                      font-weight: bold;
                      display: inline-block;
                      box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                Reset Password
            </a>
        </div>

        <p style="color: #666; font-size: 14px;">Or copy and paste this link into your browser:</p>
        <p style="background-color: #f5f5f5; padding: 12px; border-radius: 5px; word-break: break-all; font-size: 12px; color: #555;">
            {reset_url}
        </p>

        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 25px 0; border-radius: 4px;">
            <p style="margin: 0; color: #856404; font-size: 14px;">
                <strong>⚠️ Important:</strong> This link will expire in <strong>1 hour</strong>.
            </p>
        </div>

        <p style="color: #999; font-size: 13px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
            If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
        </p>

        <p style="color: #999; font-size: 13px; margin-top: 10px;">
            If you're having trouble clicking the button, copy and paste the URL above into your web browser.
        </p>
    </div>

    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p style="margin: 5px 0;">TBA App - The Calling Awaits</p>
        <p style="margin: 5px 0;">This is an automated email, please do not reply.</p>
    </div>
</body>
</html>
"""

    plain_text_content = f"""
Reset Your TBA Password

We received a request to reset your password.

Click the link below to create a new password:
{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email. Your password will remain unchanged.

---
TBA App - The Calling Awaits
This is an automated email, please do not reply.
"""

    # Check if SendGrid is configured (production mode)
    if sendgrid_api_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            # Create email message
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", plain_text_content),
                html_content=Content("text/html", html_content)
            )

            # Send email via SendGrid
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)

            print(f"✅ Password reset email sent to {to_email} (Status: {response.status_code})")

        except Exception as e:
            print(f"❌ Failed to send email via SendGrid: {e}")
            # Fall back to console output in case of error
            _print_reset_email_to_console(to_email, subject, reset_url)
            raise

    else:
        # Development mode - print to console
        _print_reset_email_to_console(to_email, subject, reset_url)


def _print_reset_email_to_console(to_email: str, subject: str, reset_url: str) -> None:
    """
    Print password reset email to console (development mode).

    Args:
        to_email: Recipient email address
        subject: Email subject
        reset_url: Password reset URL
    """
    print("\n")
    print("═" * 80)
    print("📧 PASSWORD RESET EMAIL (DEV MODE)")
    print("═" * 80)
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print()
    print("Reset Link:")
    print(reset_url)
    print()
    print("⏰ This link expires in 1 hour.")
    print("═" * 80)
    print("\n")
