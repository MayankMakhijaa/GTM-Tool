from datetime import datetime
import re
import pytest
from app.models.all_models import UserTable
from app.services.auth_service import signup_user
from app.database import db_session

@pytest.fixture
def client(flask_app):
    orig_testing = flask_app.config.get('TESTING')
    orig_csrf = flask_app.config.get('WTF_CSRF_ENABLED')
    orig_ratelimit = flask_app.config.get('RATELIMIT_ENABLED')

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = True
    flask_app.config['RATELIMIT_ENABLED'] = False
    with flask_app.test_client() as test_client:
        yield test_client

    flask_app.config['TESTING'] = orig_testing
    flask_app.config['WTF_CSRF_ENABLED'] = orig_csrf
    flask_app.config['RATELIMIT_ENABLED'] = orig_ratelimit

@pytest.fixture
def existing_user():
    email = "registered_user@fameweb.in"
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    if not user:
        user = signup_user(
            name="Registered User",
            email=email,
            phone="+14155559000",
            password="ValidPassword123!"
        )
    user.email_verified_at = datetime.utcnow()
    user.onboarding_step = "OPTIMIZATION"
    db_session.commit()
    return {"user_id": user.user_id, "email": email, "password": "ValidPassword123!"}

def get_csrf_token(client):
    res = client.get('/login')
    html = res.get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else ""

def test_login_page_renders_and_toggle_element_exists(client):
    """Test Case 5: Verify password visibility toggle element exists and login page loads."""
    res = client.get('/login')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'id="togglePassword"' in html
    assert 'id="password"' in html
    assert 'href="/signup"' in html

def test_login_with_existing_registered_account(client, existing_user):
    """Test Case 1 & 4 & 7: Login with registered account, establish session, and verify page access."""
    csrf_token = get_csrf_token(client)
    
    # Perform login POST request
    res = client.post('/api/auth/login', json={
        "identifier": existing_user["email"],
        "password": existing_user["password"]
    }, headers={'X-CSRFToken': csrf_token})

    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["message"] == "Login successful"
    assert data["user"]["email_id"] == existing_user["email"]

    # Verify session is authenticated
    res_me = client.get('/api/auth/me')
    assert res_me.status_code == 200
    me_data = res_me.get_json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["email_id"] == existing_user["email"]

    # Verify user can access protected dashboard
    res_dash = client.get('/dashboard')
    assert res_dash.status_code == 200

def test_login_with_incorrect_password(client, existing_user):
    """Test Case 2: Login with incorrect password returns HTTP 401 Invalid credentials."""
    csrf_token = get_csrf_token(client)
    
    res = client.post('/api/auth/login', json={
        "identifier": existing_user["email"],
        "password": "WrongPassword999!"
    }, headers={'X-CSRFToken': csrf_token})

    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "INVALID_CREDENTIALS"
    assert data["message"] == "Invalid credentials"

def test_login_with_unregistered_email(client):
    """Test Case 3: Login with unregistered email returns HTTP 401 Invalid credentials."""
    csrf_token = get_csrf_token(client)
    
    res = client.post('/api/auth/login', json={
        "identifier": "completely_unregistered_email@fameweb.in",
        "password": "ValidPassword123!"
    }, headers={'X-CSRFToken': csrf_token})

    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "INVALID_CREDENTIALS"
    assert data["message"] == "Invalid credentials"

def test_csrf_token_preserved_after_login(client, existing_user):
    """Test Case 6: Verify CSRF token is not wiped during set_user_session."""
    csrf_token = get_csrf_token(client)

    # Login
    res_login = client.post('/api/auth/login', json={
        "identifier": existing_user["email"],
        "password": existing_user["password"]
    }, headers={'X-CSRFToken': csrf_token})
    assert res_login.status_code == 200

    # Perform another POST action immediately using same CSRF token to prove CSRF token was preserved
    res_logout = client.post('/api/auth/logout', headers={'X-CSRFToken': csrf_token})
    assert res_logout.status_code == 200
    assert res_logout.get_json()["success"] is True


# ====================================================================
# TICKET 3G.1: CSRF EXPIRATION & CONFIGURATION REGRESSION TESTS
# ====================================================================

def test_csrf_time_limit_configuration_is_finite_and_24h(flask_app):
    """
    Ticket 3G.1 Requirement 6:
    Verify that WTF_CSRF_TIME_LIMIT is explicitly set to 86400 (24 hours),
    finite, and matches the permanent session lifetime.
    """
    assert flask_app.config.get('WTF_CSRF_TIME_LIMIT') == 86400
    assert flask_app.config.get('PERMANENT_SESSION_LIFETIME') == 86400


def test_login_without_csrf_token_is_rejected_with_csrf_error(client, existing_user):
    """
    Ticket 3G.1 Requirement 5:
    Verify request without CSRF token is rejected with status 400 and structured CSRF_ERROR.
    """
    res = client.post('/api/auth/login', json={
        "identifier": existing_user["email"],
        "password": existing_user["password"]
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "CSRF_ERROR"
    assert "The CSRF token is missing." in data["message"]


def test_login_with_expired_csrf_token_returns_structured_csrf_error(client, existing_user, flask_app):
    """
    Ticket 3G.1 Requirements 1, 2, 5:
    Simulate an expired token by setting WTF_CSRF_TIME_LIMIT to a 1-second window.
    Verify that Flask-WTF catches expiration and returns 400 {"success": False, "error": "CSRF_ERROR", "message": "The CSRF token has expired."}.
    """
    import time

    # Initialize a valid session and get current token
    csrf_token = get_csrf_token(client)
    assert csrf_token

    # Temporarily set time limit to -1 to simulate token expiration
    old_time_limit = flask_app.config.get('WTF_CSRF_TIME_LIMIT')
    try:
        flask_app.config['WTF_CSRF_TIME_LIMIT'] = -1

        res_expired = client.post('/api/auth/login', json={
            "identifier": existing_user["email"],
            "password": existing_user["password"]
        }, headers={'X-CSRFToken': csrf_token})

        assert res_expired.status_code == 400
        data = res_expired.get_json()
        assert data["success"] is False
        assert data["error"] == "CSRF_ERROR"
        assert data["message"] == "The CSRF token has expired."
    finally:
        flask_app.config['WTF_CSRF_TIME_LIMIT'] = old_time_limit


def test_invalid_credentials_not_confused_with_csrf_error(client, existing_user):
    """
    Ticket 3G.1 Requirement 4:
    Verify normal invalid credential handling remains HTTP 401 INVALID_CREDENTIALS.
    """
    csrf_token = get_csrf_token(client)
    res = client.post('/api/auth/login', json={
        "identifier": existing_user["email"],
        "password": "IncorrectPassword123!"
    }, headers={'X-CSRFToken': csrf_token})

    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "INVALID_CREDENTIALS"
    assert data["message"] == "Invalid credentials"

