import os
import sys
from dotenv import load_dotenv

load_dotenv()
if not os.environ.get('GEMINI_API_KEY') and os.path.exists('.env.example'):
    load_dotenv('.env.example')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')
    _is_testing = bool(os.environ.get('FLASK_TESTING')) or 'pytest' in os.environ.get('_', '') or any('pytest' in arg for arg in sys.argv)
    if _is_testing:
        _db_uri = os.environ.get('TEST_DATABASE_URL') or os.environ.get('DATABASE_URL')
        if not _db_uri or _db_uri.split('/')[-1].split('?')[0].lower() == 'fameweb':
            _db_uri = 'postgresql+psycopg://postgres:postgres@localhost:5432/fameweb_test'
        SQLALCHEMY_DATABASE_URI = _db_uri
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/fameweb')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable secure cookies in production, safe for development without HTTPS
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = 86400  # 1 day
    
    RATELIMIT_ENABLED = not os.environ.get('FLASK_TESTING')
    
    # Other configs
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY') or os.environ.get('GOOGLE_MAPS_API_KEY')
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY') or os.environ.get('GOOGLE_PLACES_API_KEY')
    GOOGLE_SEARCH_KEY = os.environ.get('GOOGLE_SEARCH_KEY')
    GOOGLE_SEARCH_CX = os.environ.get('GOOGLE_SEARCH_CX')

    # SMTP Email Configuration
    SMTP_HOST = os.environ.get('SMTP_HOST')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', 'no-reply@fameweb.com')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
