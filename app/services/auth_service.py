import re
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from app.repositories.user_repository import create_user, get_user_by_email, get_user_by_phone
from app.security.password import hash_password, verify_password

def normalize_email(email: str) -> str:
    if not email:
        return ""
    return email.strip().lower()

def validate_and_normalize_email(email: str) -> str:
    email = normalize_email(email)
    try:
        valid = validate_email(email, check_deliverability=False)
        return valid.normalized
    except EmailNotValidError:
        raise ValueError("Invalid email format")

def validate_and_normalize_phone(phone: str) -> str:
    if not phone:
        raise ValueError("Phone number required")
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        raise ValueError("Invalid phone number format")

def validate_password(password: str):
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

def signup_user(name: str, email: str, phone: str, password: str):
    if not name or not name.strip():
        raise ValueError("Name is required")
        
    normalized_email = validate_and_normalize_email(email)
    normalized_phone = validate_and_normalize_phone(phone)
    validate_password(password)
    
    if get_user_by_email(normalized_email):
        raise ValueError("Email already exists")
        
    if get_user_by_phone(normalized_phone):
        raise ValueError("Phone already exists")
        
    hashed_pwd = hash_password(password)
    
    user = create_user(
        name=name.strip(),
        email=normalized_email,
        phone=normalized_phone,
        password_hash=hashed_pwd
    )
    if not user:
        raise ValueError("Failed to create user, possible duplicate")
    return user

def authenticate_user(identifier: str, password: str):
    if not identifier or not password:
        return None
        
    identifier = identifier.strip()
    user = None
    
    # Check if identifier is email or phone
    if "@" in identifier:
        # treat as email
        email = normalize_email(identifier)
        user = get_user_by_email(email)
    else:
        # treat as phone
        try:
            phone = validate_and_normalize_phone(identifier)
            user = get_user_by_phone(phone)
        except ValueError:
            user = None

    if not user or not user.is_active:
        return None
        
    if verify_password(password, user.password_hash):
        return user
        
    return None
