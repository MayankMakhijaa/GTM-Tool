import re
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from app.repositories.user_repository import create_user, get_user_by_email, get_user_by_phone
from app.security.password import hash_password, verify_password

DISALLOWED_PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.ca", "yahoo.com.br",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "aim.com",
    "proton.me", "protonmail.com", "protonmail.ch",
    "zoho.com", "zohomail.com",
    "mail.com", "gmx.com", "gmx.net",
    "yandex.com", "yandex.ru", "mail.ru",
    "comcast.net", "sbcglobal.net", "verizon.net", "cox.net", "rediffmail.com"
}

def normalize_email(email: str) -> str:
    if not email:
        return ""
    return email.strip().lower()

def validate_and_normalize_email(email: str, is_signup: bool = False) -> str:
    email = normalize_email(email)
    if not email:
        raise ValueError("Email is required")
    try:
        valid = validate_email(email, check_deliverability=False)
        norm_email = valid.normalized
    except EmailNotValidError:
        raise ValueError("Invalid email format")

    if is_signup:
        domain = norm_email.split("@")[-1].lower()
        if domain in DISALLOWED_PERSONAL_EMAIL_DOMAINS:
            raise ValueError(f"Please use your business email address. Personal email providers ({domain}) are not allowed.")

    return norm_email

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
    if not password:
        raise ValueError("Password is required")
    if len(password) < 9:
        raise ValueError("Password must be at least 9 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter (A-Z)")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter (a-z)")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one number (0-9)")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character")

def signup_user(name: str, email: str, phone: str, password: str):
    if not name or not name.strip():
        raise ValueError("Name is required")

    normalized_email = validate_and_normalize_email(email, is_signup=True)
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
            user = get_user_by_phone(identifier)

    if not user or not user.is_active:
        return None
        
    if verify_password(password, user.password_hash):
        return user
        
    return None
