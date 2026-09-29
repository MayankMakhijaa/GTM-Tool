import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql+psycopg://postgres:root@localhost:5432/fameweb')
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
