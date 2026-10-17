from datetime import datetime
import pytest
from app_module import app
from app.database import db_session, Base, engine
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP
from app.security.password import hash_password, verify_password
from app.security.session import login_required
from app.services.email_service import get_last_test_otp, clear_test_captured_otps

# Define protected route before first request if not already defined
if '/api/protected_test' not in [rule.rule for rule in app.url_map.iter_rules()]:
    @app.route('/api/protected_test', methods=['GET'])
    @login_required
    def protected_test():
        return "OK"

# Inherits `client` fixture from tests/conftest.py with DB isolation and safety guards

def test_password_hashing():
    pwd = "my_secure_password"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_signup_success(client):
    res = client.post('/api/auth/signup', json={
        "name": "Test User",
        "email": "test@acmecorp.com",
        "phone": "+14155552671",
        "password": "StrongP@ssword123!"
    })
    assert res.status_code == 201, res.get_json()
    data = res.get_json()
    assert data["success"] is True
    assert data["email"] == "test@acmecorp.com"
    assert data["requires_verification"] is True
    assert "password_hash" not in data
    assert "password" not in data
    
    # Confirm stored value in database is a hash, not plaintext
    user = db_session.query(UserTable).filter_by(email_id="test@acmecorp.com").first()
    assert user is not None
    assert user.password_hash != "StrongP@ssword123!"
    assert "$argon2id$" in user.password_hash or "argon2" in user.password_hash.lower()

def test_duplicate_email(client):
    client.post('/api/auth/signup', json={
        "name": "User One", "email": "dup@acmecorp.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    res = client.post('/api/auth/signup', json={
        "name": "User Two", "email": "dup@acmecorp.com", "phone": "+14155552672", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "Email already exists" in data["message"]

def test_duplicate_phone(client):
    client.post('/api/auth/signup', json={
        "name": "User One", "email": "one@acmecorp.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    res = client.post('/api/auth/signup', json={
        "name": "User Two", "email": "two@acmecorp.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 400
    assert "Phone already exists" in res.get_json()["message"]

# --- PASSWORD COMPLEXITY TESTS ---

def test_password_under_9_chars_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@acmecorp.com", "phone": "+14155552671", "password": "P@ssw0rd"
    })
    assert res.status_code == 400
    assert "at least 9 characters" in res.get_json()["message"]

def test_password_no_uppercase_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@acmecorp.com", "phone": "+14155552671", "password": "p@ssword123"
    })
    assert res.status_code == 400
    assert "uppercase letter" in res.get_json()["message"]

def test_password_no_lowercase_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@acmecorp.com", "phone": "+14155552671", "password": "P@SSWORD123"
    })
    assert res.status_code == 400
    assert "lowercase letter" in res.get_json()["message"]

def test_password_no_number_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@acmecorp.com", "phone": "+14155552671", "password": "StrongP@ssword"
    })
    assert res.status_code == 400
    assert "number" in res.get_json()["message"]

def test_password_no_special_char_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@acmecorp.com", "phone": "+14155552671", "password": "StrongPassword123"
    })
    assert res.status_code == 400
    assert "special character" in res.get_json()["message"]

def test_password_all_five_rules_accepted(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "valid5@acmecorp.com", "phone": "+14155552699", "password": "Valid123!Password"
    })
    assert res.status_code == 201
    assert res.get_json()["success"] is True

# --- BUSINESS EMAIL TESTS ---

def test_email_gmail_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@gmail.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 400
    assert "business email" in res.get_json()["message"].lower()

def test_email_yahoo_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@yahoo.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 400
    assert "business email" in res.get_json()["message"].lower()

def test_email_valid_company_domain_accepted(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "employee@innovatecorp.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 201
    assert res.get_json()["email"] == "employee@innovatecorp.com"

def test_email_uppercase_normalized(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "ALEX@BIGTECH.ORG", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 201
    assert res.get_json()["email"] == "alex@bigtech.org"

def test_email_whitespace_handled(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "  user@spacex.io  ", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 201
    assert res.get_json()["email"] == "user@spacex.io"

def test_email_malformed_rejected(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "not-an-email", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 400
    assert "Invalid email" in res.get_json()["message"]

def test_email_uncommon_business_domain_accepted(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "founder@quantum-ai.tech", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 201
    assert res.get_json()["email"] == "founder@quantum-ai.tech"

# --- COMBINED SIGNUP TESTS ---

def test_combined_strong_pwd_and_business_email_succeeds(client):
    res = client.post('/api/auth/signup', json={
        "name": "Combined User", "email": "cto@nextgen.ai", "phone": "+14155559988", "password": "SuperC0mplex#Password2026"
    })
    assert res.status_code == 201
    assert res.get_json()["success"] is True

def test_combined_weak_pwd_and_business_email_fails(client):
    res = client.post('/api/auth/signup', json={
        "name": "Combined User", "email": "cto@nextgen.ai", "phone": "+14155559988", "password": "simplepassword"
    })
    assert res.status_code == 400
    assert "uppercase" in res.get_json()["message"] or "special character" in res.get_json()["message"]

def test_combined_strong_pwd_and_personal_email_fails(client):
    res = client.post('/api/auth/signup', json={
        "name": "Combined User", "email": "personal@gmail.com", "phone": "+14155559988", "password": "SuperC0mplex#Password2026"
    })
    assert res.status_code == 400
    assert "business email" in res.get_json()["message"].lower()

def test_combined_weak_pwd_and_personal_email_fails(client):
    res = client.post('/api/auth/signup', json={
        "name": "Combined User", "email": "personal@outlook.com", "phone": "+14155559988", "password": "123"
    })
    assert res.status_code == 400
    assert res.get_json()["error"] == "VALIDATION_ERROR"

# --- EXISTING ACCOUNT COMPATIBILITY TESTS ---

def test_existing_account_simple_password_login_succeeds(client):
    # Create legacy user in database with simple 8-char password hash and verified email
    legacy_pwd = "simple8char"
    hashed = hash_password(legacy_pwd)
    legacy_user = UserTable(
        name="Legacy User",
        email_id="legacy@acmecorp.com",
        phone_no="+14155557711",
        password_hash=hashed,
        is_active=True,
        email_verified_at=datetime.utcnow()
    )
    db_session.add(legacy_user)
    db_session.commit()

    # Login with simple password must succeed
    res = client.post('/api/auth/login', json={
        "identifier": "legacy@acmecorp.com",
        "password": "simple8char"
    })
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Hash in DB must remain untouched
    reloaded = db_session.query(UserTable).filter_by(email_id="legacy@acmecorp.com").first()
    assert reloaded.password_hash == hashed

def test_existing_account_wrong_password_rejected(client):
    legacy_pwd = "simple8char"
    hashed = hash_password(legacy_pwd)
    legacy_user = UserTable(
        name="Legacy User 2",
        email_id="legacy2@acmecorp.com",
        phone_no="+14155557722",
        password_hash=hashed,
        is_active=True,
        email_verified_at=datetime.utcnow()
    )
    db_session.add(legacy_user)
    db_session.commit()

    res = client.post('/api/auth/login', json={
        "identifier": "legacy2@acmecorp.com",
        "password": "wronglegacypassword"
    })
    assert res.status_code == 401
    assert res.get_json()["error"] == "INVALID_CREDENTIALS"

def test_login_email(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "login@acmecorp.com", "phone": "+14155552671", "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp("login@acmecorp.com")
    client.post('/api/auth/verify-otp', json={"email": "login@acmecorp.com", "otp": otp})

    res = client.post('/api/auth/login', json={
        "identifier": "login@acmecorp.com", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["email_id"] == "login@acmecorp.com"

def test_login_phone(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "phone@acmecorp.com", "phone": "+14155552672", "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp("phone@acmecorp.com")
    client.post('/api/auth/verify-otp', json={"email": "phone@acmecorp.com", "otp": otp})

    res = client.post('/api/auth/login', json={
        "identifier": "+14155552672", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["success"] is True

def test_invalid_credentials(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "valid@acmecorp.com", "phone": "+14155552673", "password": "StrongP@ssword123!"
    })
    res = client.post('/api/auth/login', json={
        "identifier": "valid@acmecorp.com", "password": "WrongP@ssword123!"
    })
    assert res.status_code == 401
    assert res.get_json()["error"] == "INVALID_CREDENTIALS"

def test_inactive_user_cannot_login(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "inactive@acmecorp.com", "phone": "+14155552674", "password": "StrongP@ssword123!"
    })
    user = db_session.query(UserTable).filter_by(email_id="inactive@acmecorp.com").first()
    user.is_active = False
    db_session.commit()
    
    res = client.post('/api/auth/login', json={
        "identifier": "inactive@acmecorp.com", "password": "StrongP@ssword123!"
    })
    assert res.status_code == 401

def test_auth_me_authenticated(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "me@acmecorp.com", "phone": "+14155552675", "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp("me@acmecorp.com")
    client.post('/api/auth/verify-otp', json={"email": "me@acmecorp.com", "otp": otp})

    client.post('/api/auth/login', json={
        "identifier": "me@acmecorp.com", "password": "StrongP@ssword123!"
    })
    res = client.get('/api/auth/me')
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is True
    assert data["user"]["email_id"] == "me@acmecorp.com"
    assert "password_hash" not in data["user"]

def test_auth_me_unauthenticated(client):
    res = client.get('/api/auth/me')
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is False

def test_logout(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "logout@acmecorp.com", "phone": "+14155552676", "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp("logout@acmecorp.com")
    client.post('/api/auth/verify-otp', json={"email": "logout@acmecorp.com", "otp": otp})

    client.post('/api/auth/login', json={
        "identifier": "logout@acmecorp.com", "password": "StrongP@ssword123!"
    })
    res = client.post('/api/auth/logout')
    assert res.status_code == 200
    
    res = client.get('/api/auth/me')
    assert res.get_json()["authenticated"] is False

def test_protected_route_rejects_unauthenticated(client):
    res = client.get('/api/protected_test')
    assert res.status_code == 401
