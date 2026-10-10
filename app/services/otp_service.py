import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Tuple, Optional
from app.database import db_session
from app.models.all_models import UserTable, EmailVerificationOTP
from app.services.email_service import send_verification_email

from config import Config

OTP_LIFETIME_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

def get_otp_cutoff_timestamp() -> datetime:
    """Retrieves the OTP rollout cutoff timestamp from application configuration."""
    val = None
    try:
        from flask import current_app
        if current_app:
            val = current_app.config.get('OTP_CUTOFF_TIMESTAMP')
    except RuntimeError:
        pass
    if not val:
        val = getattr(Config, 'OTP_CUTOFF_TIMESTAMP', None)

    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            val_clean = val.rstrip('Z').replace('T', ' ')
            return datetime.fromisoformat(val_clean)
        except Exception:
            pass
    return datetime(2026, 10, 6, 0, 0, 0)

def get_otp_force_verification_emails() -> set:
    """Retrieves list/set of emails that must ALWAYS undergo OTP verification."""
    emails = None
    try:
        from flask import current_app
        if current_app:
            emails = current_app.config.get('OTP_FORCE_VERIFICATION_EMAILS')
    except RuntimeError:
        pass
    if emails is None:
        emails = getattr(Config, 'OTP_FORCE_VERIFICATION_EMAILS', None)
    if isinstance(emails, (list, set, tuple)):
        return {str(e).strip().lower() for e in emails if e}
    if isinstance(emails, str):
        return {e.strip().lower() for e in emails.split(',') if e.strip()}
    return {"mayank@fameweb.in"}

def is_user_email_verified(user: Optional[UserTable]) -> bool:
    """
    Determines whether a user is considered email-verified for access and onboarding.

    1. If user is None -> False.
    2. If user.email_verified_at is not None -> True (explicitly verified).
    3. Special Test Accounts (e.g. mayank@fameweb.in):
       If user.email_id is in OTP_FORCE_VERIFICATION_EMAILS, they are NEVER grandfathered
       and must complete OTP verification (returning False while email_verified_at is None).
    4. Legacy accounts:
       If user was created before the OTP rollout cutoff (or created_at is None),
       they are grandfathered and treated as verified without updating their database row.
    5. New accounts (created on or after the cutoff):
       Return False until they successfully verify their OTP.
    """
    if not user:
        return False

    if user.email_verified_at is not None:
        return True

    user_email = (user.email_id or "").strip().lower()

    force_verify_emails = get_otp_force_verification_emails()
    if user_email in force_verify_emails:
        return False

    cutoff = get_otp_cutoff_timestamp()
    if user.created_at is None or user.created_at < cutoff:
        return True

    return False

def hash_otp(otp: str) -> str:
    """Computes SHA-256 hash of the 6-digit OTP."""
    return hashlib.sha256(otp.strip().encode('utf-8')).hexdigest()

def generate_secure_otp() -> str:
    """Generates a cryptographically secure 6-digit OTP with leading zeros."""
    number = secrets.randbelow(1_000_000)
    return f"{number:06d}"

def invalidate_existing_otps(user_id: int):
    """Deletes any pending OTPs for the user."""
    db_session.query(EmailVerificationOTP).filter_by(user_id=user_id).delete()
    db_session.commit()

def create_and_send_otp(user: UserTable) -> bool:
    """
    Invalidates any prior OTP, generates a new 6-digit OTP, stores its SHA-256 hash,
    and dispatches the verification email.
    """
    invalidate_existing_otps(user.user_id)

    raw_otp = generate_secure_otp()
    hashed = hash_otp(raw_otp)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_LIFETIME_MINUTES)

    otp_record = EmailVerificationOTP(
        user_id=user.user_id,
        otp_hash=hashed,
        expires_at=expires_at,
        attempts=0,
        created_at=datetime.utcnow()
    )
    db_session.add(otp_record)
    db_session.commit()

    # Send email
    send_verification_email(user.email_id, raw_otp, user.name)
    return True

def verify_user_otp(email: str, candidate_otp: str) -> Tuple[bool, str, Optional[UserTable]]:
    """
    Validates a submitted 6-digit OTP against the active record for the given email.
    Returns (success, message, user).
    """
    normalized_email = email.strip().lower()
    user = db_session.query(UserTable).filter_by(email_id=normalized_email).first()
    if not user:
        return False, "Invalid verification code or email.", None

    if is_user_email_verified(user):
        return True, "Email is already verified.", user

    # Retrieve most recent active OTP record
    otp_record = db_session.query(EmailVerificationOTP)\
        .filter_by(user_id=user.user_id)\
        .order_by(EmailVerificationOTP.created_at.desc())\
        .first()

    if not otp_record:
        return False, "No active verification code found. Please request a new code.", None

    # Check attempt threshold
    if otp_record.attempts >= MAX_ATTEMPTS:
        db_session.delete(otp_record)
        db_session.commit()
        return False, "Maximum verification attempts exceeded. Please request a new code.", None

    # Check expiration
    if datetime.utcnow() > otp_record.expires_at:
        db_session.delete(otp_record)
        db_session.commit()
        return False, "Verification code has expired. Please request a new code.", None

    # Constant-time comparison
    candidate_hash = hash_otp(candidate_otp)
    if not hmac.compare_digest(otp_record.otp_hash, candidate_hash):
        otp_record.attempts += 1
        if otp_record.attempts >= MAX_ATTEMPTS:
            db_session.delete(otp_record)
            db_session.commit()
            return False, "Maximum verification attempts exceeded. Please request a new code.", None
        db_session.commit()
        remaining = MAX_ATTEMPTS - otp_record.attempts
        return False, f"Invalid verification code. {remaining} attempt(s) remaining.", None

    # Successful verification
    user.email_verified_at = datetime.utcnow()
    db_session.delete(otp_record)
    db_session.commit()

    return True, "Email verified successfully.", user

def resend_user_otp(email: str) -> Tuple[bool, str, Optional[int]]:
    """
    Resends OTP to the user if eligible. Enforces 60-second cooldown.
    Returns (success, message, retry_after_seconds).
    """
    normalized_email = email.strip().lower()
    user = db_session.query(UserTable).filter_by(email_id=normalized_email).first()
    if not user:
        # Return generic safe message to prevent email enumeration
        return True, "If an account exists with this email, a new verification code has been sent.", None

    if is_user_email_verified(user):
        return False, "This email is already verified. You can log in.", None

    # Check existing OTP for cooldown
    existing_otp = db_session.query(EmailVerificationOTP)\
        .filter_by(user_id=user.user_id)\
        .order_by(EmailVerificationOTP.created_at.desc())\
        .first()

    if existing_otp:
        elapsed = (datetime.utcnow() - existing_otp.created_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            retry_after = int(RESEND_COOLDOWN_SECONDS - elapsed)
            return False, f"Please wait {retry_after} seconds before requesting a new code.", retry_after

    create_and_send_otp(user)
    return True, "A new 6-digit verification code has been sent to your email.", None
