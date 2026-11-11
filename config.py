import os
import sys
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()
if not os.environ.get('GEMINI_API_KEY') and os.path.exists('.env.example'):
    load_dotenv('.env.example')

class Config:
    _raw_env = (os.environ.get('FLASK_ENV') or os.environ.get('ENV') or '').strip().lower()
    _is_testing = bool(os.environ.get('FLASK_TESTING')) or 'pytest' in os.environ.get('_', '') or any('pytest' in arg for arg in sys.argv)
    IS_PRODUCTION = (_raw_env == 'production') and not _is_testing

    _raw_secret = os.environ.get('SECRET_KEY')
    INSECURE_DEV_SECRET = 'dev_secret_key'

    @staticmethod
    def validate_production_secrets(raw_secret: Any = ..., is_production: Optional[bool] = None) -> bool:
        """Validates that a production deployment does not run with missing, blank, or insecure fallback secrets."""
        prod = Config.IS_PRODUCTION if is_production is None else is_production
        sec = Config.SECRET_KEY if raw_secret is ... else (raw_secret or '')
        if prod:
            if not sec or not str(sec).strip():
                raise RuntimeError(
                    "CRITICAL CONFIGURATION ERROR: SECRET_KEY environment variable is required and cannot be blank in production."
                )
            if str(sec).strip() == Config.INSECURE_DEV_SECRET:
                raise RuntimeError(
                    "CRITICAL CONFIGURATION ERROR: Production cannot use the insecure development fallback SECRET_KEY ('dev_secret_key'). Please set a strong, unique secret key."
                )
        return True

    if IS_PRODUCTION:
        validate_production_secrets(raw_secret=_raw_secret, is_production=True)
        SECRET_KEY = _raw_secret.strip() if _raw_secret else ''
    else:
        SECRET_KEY = _raw_secret.strip() if (_raw_secret and _raw_secret.strip()) else INSECURE_DEV_SECRET

    if _is_testing:
        _db_uri = os.environ.get('TEST_DATABASE_URL') or os.environ.get('DATABASE_URL')
        if not _db_uri or _db_uri.split('/')[-1].split('?')[0].lower() == 'fameweb':
            _db_uri = 'postgresql+psycopg://postgres:postgres@localhost:5432/fameweb_test'
        SQLALCHEMY_DATABASE_URI = _db_uri
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/fameweb')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session and CSRF configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable secure cookies in production, safe for development without HTTPS
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    PERMANENT_SESSION_LIFETIME = 86400  # 1 day
    WTF_CSRF_TIME_LIMIT = 86400  # 24 hours finite token lifetime

    RATELIMIT_ENABLED = not os.environ.get('FLASK_TESTING')
    
    # Other configs
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY') or os.environ.get('GOOGLE_MAPS_API_KEY')
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY') or os.environ.get('GOOGLE_PLACES_API_KEY')
    GOOGLE_SEARCH_KEY = os.environ.get('GOOGLE_SEARCH_KEY')
    GOOGLE_SEARCH_CX = os.environ.get('GOOGLE_SEARCH_CX')

    # SMTP Email Configuration
    SMTP_HOST = None if _is_testing else os.environ.get('SMTP_HOST')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', 'no-reply@fameweb.com')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')

    # Temporary testing configuration: permit consumer email providers as sender accounts
    ALLOW_PERSONAL_EMAIL_SENDERS = os.environ.get('ALLOW_PERSONAL_EMAIL_SENDERS', 'false').strip().lower() in ('true', '1', 'yes')

    # Signup OTP Configuration
    # Accounts created before this cutoff timestamp are treated as grandfathered legacy accounts
    OTP_CUTOFF_TIMESTAMP = os.environ.get('OTP_CUTOFF_TIMESTAMP', '2026-10-06T00:00:00Z')
    # Specific accounts that must ALWAYS require OTP regardless of creation timestamp (e.g. e2e test accounts)
    OTP_FORCE_VERIFICATION_EMAILS = [
        email.strip().lower()
        for email in os.environ.get('OTP_FORCE_VERIFICATION_EMAILS', 'mayank@fameweb.in').split(',')
        if email.strip()
    ]

