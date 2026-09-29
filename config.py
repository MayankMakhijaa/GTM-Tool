import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql+psycopg://postgres:root@localhost:5432/fameweb')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Other configs
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
