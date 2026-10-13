import os
import smtplib
import logging
from email.message import EmailMessage
from typing import Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Test/development registry for capturing sent OTPs in memory for test verification
# ONLY populated in testing or non-production when SMTP is not configured
_test_captured_otps = {}

def get_last_test_otp(email: str) -> Optional[str]:
    """Helper for automated testing environments to inspect the last OTP dispatched."""
    return _test_captured_otps.get(email.strip().lower())

def clear_test_captured_otps():
    """Clear captured OTPs in test environment."""
    _test_captured_otps.clear()

def is_test_or_dev() -> bool:
    try:
        if current_app and current_app.config.get('TESTING'):
            return True
    except RuntimeError:
        pass
    if os.environ.get('FLASK_TESTING') or 'pytest' in os.environ.get('_', ''):
        return True
    return os.environ.get('FLASK_ENV') != 'production'

def send_verification_email(to_email: str, otp: str, user_name: Optional[str] = None) -> bool:
    """
    Sends the 6-digit verification code to the recipient email.
    Uses smtplib and standard library email.message.
    """
    smtp_host = None
    smtp_port = 587
    smtp_user = None
    smtp_password = None
    smtp_from = 'no-reply@fameweb.com'
    smtp_use_tls = True

    try:
        if current_app:
            smtp_host = current_app.config.get('SMTP_HOST')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_user = current_app.config.get('SMTP_USER')
            smtp_password = current_app.config.get('SMTP_PASSWORD')
            smtp_from = current_app.config.get('SMTP_FROM_EMAIL', 'no-reply@fameweb.com')
            smtp_use_tls = current_app.config.get('SMTP_USE_TLS', True)
    except RuntimeError:
        pass

    if not smtp_host:
        smtp_host = os.environ.get('SMTP_HOST')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        smtp_from = os.environ.get('SMTP_FROM_EMAIL', 'no-reply@fameweb.com')
        smtp_use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')

    # Production safety guard
    if not smtp_host:
        if is_test_or_dev():
            # In testing/dev without SMTP, capture in memory for automated test assertions
            normalized = to_email.strip().lower()
            _test_captured_otps[normalized] = otp
            logger.info(f"[DEV/TEST] Verification code simulated for recipient: {normalized}")
            return True
        else:
            logger.error("Production email delivery failed: SMTP_HOST is not configured.")
            raise RuntimeError("Email service is currently unavailable. Please contact support.")

    # Build standard MIME message
    msg = EmailMessage()
    msg['Subject'] = 'Your Fameweb Verification Code'
    msg['From'] = smtp_from
    msg['To'] = to_email

    greeting = f"Hello {user_name}," if user_name else "Hello,"

    plain_content = f"""{greeting}

Your 6-digit Fameweb verification code is: {otp}

This code will expire in 10 minutes. If you did not create a Fameweb account, please ignore this email.

Best regards,
The Fameweb Team
"""
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background-color: #faf8ff; padding: 24px; color: #131b2e;">
  <div style="max-width: 480px; margin: 0 auto; background-color: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #eaedff;">
    <h2 style="color: #004ac6; margin-top: 0;">Verify your business email</h2>
    <p>{greeting}</p>
    <p>Please use the following 6-digit verification code to complete your Fameweb registration:</p>
    <div style="font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #004ac6; background: #eaedff; padding: 16px; text-align: center; border-radius: 8px; margin: 24px 0;">
      {otp}
    </div>
    <p style="font-size: 13px; color: #737686;">This code is valid for <strong>10 minutes</strong>. If you did not request this, you can safely ignore this email.</p>
    <hr style="border: none; border-top: 1px solid #eaedff; margin: 24px 0;" />
    <p style="font-size: 12px; color: #737686; margin-bottom: 0;">Fameweb Intelligence Inc.</p>
  </div>
</body>
</html>
"""
    msg.set_content(plain_content)
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
            logger.info(f"Verification email successfully dispatched to {to_email}")
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        raise RuntimeError(f"Unable to deliver verification email: {str(e)}")
