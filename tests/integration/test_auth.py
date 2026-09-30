import pytest
from app_module import app
from app.database import db_session, Base, engine
from app.models.all_models import UserTable
from app.security.password import hash_password, verify_password
from app.security.session import login_required

# Define protected route before first request
@app.route('/api/protected_test', methods=['GET'])
@login_required
def protected_test():
    return "OK"

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    from app.security.limiter import limiter
    limiter.enabled = False  # Disable rate limiting in tests
    
    # We must reset DB to ensure tests are isolated
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    with app.test_client() as client:
        with app.app_context():
            yield client
    
    db_session.remove()

def test_password_hashing():
    pwd = "my_secure_password"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_signup_success(client):
    res = client.post('/api/auth/signup', json={
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+14155552671",
        "password": "strongpassword"
    })
    assert res.status_code == 201, res.get_json()
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["email_id"] == "test@example.com"
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]

def test_duplicate_email(client):
    client.post('/api/auth/signup', json={
        "name": "User One", "email": "dup@example.com", "phone": "+14155552671", "password": "password123"
    })
    res = client.post('/api/auth/signup', json={
        "name": "User Two", "email": "dup@example.com", "phone": "+14155552672", "password": "password123"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "Email already exists" in data["message"]

def test_duplicate_phone(client):
    client.post('/api/auth/signup', json={
        "name": "User One", "email": "one@example.com", "phone": "+14155552671", "password": "password123"
    })
    res = client.post('/api/auth/signup', json={
        "name": "User Two", "email": "two@example.com", "phone": "+14155552671", "password": "password123"
    })
    assert res.status_code == 400
    assert "Phone already exists" in res.get_json()["message"]

def test_invalid_email(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "not-an-email", "phone": "+14155552671", "password": "password123"
    })
    assert res.status_code == 400
    assert "Invalid email" in res.get_json()["message"]

def test_invalid_phone(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@example.com", "phone": "invalid-phone", "password": "password123"
    })
    assert res.status_code == 400
    assert "Invalid phone number" in res.get_json()["message"]

def test_invalid_password(client):
    res = client.post('/api/auth/signup', json={
        "name": "User", "email": "user@example.com", "phone": "+14155552671", "password": "short"
    })
    assert res.status_code == 400
    assert "least 8 characters" in res.get_json()["message"]

def test_login_email(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "login@example.com", "phone": "+14155552671", "password": "password123"
    })
    res = client.post('/api/auth/login', json={
        "identifier": "login@example.com", "password": "password123"
    })
    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["email_id"] == "login@example.com"

def test_login_phone(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "phone@example.com", "phone": "+14155552672", "password": "password123"
    })
    res = client.post('/api/auth/login', json={
        "identifier": "+14155552672", "password": "password123"
    })
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["success"] is True

def test_invalid_credentials(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "valid@example.com", "phone": "+14155552673", "password": "password123"
    })
    res = client.post('/api/auth/login', json={
        "identifier": "valid@example.com", "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert res.get_json()["error"] == "INVALID_CREDENTIALS"

def test_inactive_user_cannot_login(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "inactive@example.com", "phone": "+14155552674", "password": "password123"
    })
    # Manually deactivate user
    user = db_session.query(UserTable).filter_by(email_id="inactive@example.com").first()
    user.is_active = False
    db_session.commit()
    
    res = client.post('/api/auth/login', json={
        "identifier": "inactive@example.com", "password": "password123"
    })
    assert res.status_code == 401

def test_auth_me_authenticated(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "me@example.com", "phone": "+14155552675", "password": "password123"
    })
    # Login sets the session
    client.post('/api/auth/login', json={
        "identifier": "me@example.com", "password": "password123"
    })
    res = client.get('/api/auth/me')
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is True
    assert data["user"]["email_id"] == "me@example.com"
    assert "password_hash" not in data["user"]

def test_auth_me_unauthenticated(client):
    res = client.get('/api/auth/me')
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is False

def test_logout(client):
    client.post('/api/auth/signup', json={
        "name": "User", "email": "logout@example.com", "phone": "+14155552676", "password": "password123"
    })
    client.post('/api/auth/login', json={
        "identifier": "logout@example.com", "password": "password123"
    })
    # Logout
    res = client.post('/api/auth/logout')
    assert res.status_code == 200
    
    # Check /me
    res = client.get('/api/auth/me')
    assert res.get_json()["authenticated"] is False

def test_protected_route_rejects_unauthenticated(client):
    res = client.get('/api/protected_test')
    assert res.status_code == 401
