import os
import json
import uuid
import random
import pytest
from unittest.mock import MagicMock, patch
from requests.models import Response

from app_module import app
from app.database import db_session, Base, engine
from app.models.all_models import UserTable, UsersLinkedinDetails, OnboardingStep, ConnectionStatus
from app.integrations.linkedin.voyager_client import (
    encrypt_credential,
    decrypt_credential,
    create_voyager_client_from_db,
    validate_user_session
)
from legacy.profile_extractor import launch_interactive_linkedin_login
from app.services.onboarding_service import save_linkedin_connection

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    db_session.rollback()

@pytest.fixture
def test_client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    from app.security.limiter import limiter
    limiter.enabled = False
    with app.test_client() as client:
        yield client

_phone_counter = random.randint(1000, 5000)
def _random_phone():
    global _phone_counter
    _phone_counter += 1
    return f"+1415555{_phone_counter:04d}"

def test_1_signup_succeeds_without_linkedin_connection(test_client):
    """1. User creates account without requiring prior LinkedIn connection."""
    uid = uuid.uuid4().hex[:8]
    res = test_client.post('/api/auth/signup', json={
        "name": f"New User {uid}",
        "email": f"newuser_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["onboarding_step"] == "LINKEDIN"

    # Verify no LinkedIn connection exists yet
    user_id = data["user"]["user_id"]
    linkedin_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    assert linkedin_record is None

def test_2_and_3_linkedin_onboarding_page_renders_connect_button(test_client):
    """2 & 3. User visits /connect-linkedin and sees the genuine Connect LinkedIn button."""
    uid = uuid.uuid4().hex[:8]
    test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"u_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })

    res = test_client.get('/connect-linkedin')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Connect your LinkedIn Account' in html
    assert 'id="connect-linkedin-btn"' in html
    assert 'Connect LinkedIn' in html
    assert 'id="btn-continue"' in html
    assert '/static/js/onboarding_new/connect_linkedin.js' in html

def test_4_and_5_successful_connection_persists_credentials_and_advances_onboarding(test_client):
    """4 & 5. Authenticated connect endpoint succeeds, persists encrypted credentials and advances step to COMPANY."""
    uid = uuid.uuid4().hex[:8]
    signup_res = test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"connect_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    user_id = signup_res.get_json()["user"]["user_id"]

    # Mock Playwright session capture
    with patch("legacy.profile_extractor.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.url = "https://www.linkedin.com/feed/"
        mock_page.title.return_value = "LinkedIn Feed"
        mock_ctx.pages = [mock_page]
        mock_ctx.cookies.return_value = [
            {"name": "li_at", "value": f"cookie_{uid}", "domain": ".linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": f"ajax:{uid}", "domain": ".linkedin.com", "path": "/"}
        ]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_ctx

        # Mock Voyager validation succeeding
        mock_voyager_resp = Response()
        mock_voyager_resp.status_code = 200
        mock_voyager_resp._content = b'{"data": "active"}'

        with patch("requests.Session.get", return_value=mock_voyager_resp):
            res = test_client.post('/api/auth/linkedin/reconnect')
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert data["connected"] is True
            assert data["status"] == "authenticated"

    # Verify database persistence & onboarding advancement
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    assert record is not None
    assert record.connection_status == ConnectionStatus.CONNECTED.value
    assert record.auth_data_encrypted is not None

    decrypted = json.loads(decrypt_credential(record.auth_data_encrypted))
    assert decrypted["li_at"] == f"cookie_{uid}"
    assert decrypted["JSESSIONID"] == f"ajax:{uid}"

    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    assert user.onboarding_step == "COMPANY"

def test_6_failed_and_cancelled_connection_does_not_advance_onboarding(test_client):
    """6. When user cancels or login fails, onboarding does NOT advance and remains at LINKEDIN."""
    uid = uuid.uuid4().hex[:8]
    signup_res = test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"fail_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    user_id = signup_res.get_json()["user"]["user_id"]

    # Mock Playwright session where page was closed before feed navigation
    with patch("legacy.profile_extractor.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_page.is_closed.return_value = True  # Closed by user
        mock_page.url = "https://www.linkedin.com/login"
        mock_page.title.return_value = "Sign in to LinkedIn"
        mock_ctx.pages = [mock_page]
        mock_ctx.cookies.return_value = []
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_ctx

        res = test_client.post('/api/auth/linkedin/reconnect')
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False

    # User remains on LINKEDIN step
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    assert user.onboarding_step == "LINKEDIN"

    # No valid connection saved
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    assert record is None or record.connection_status != ConnectionStatus.CONNECTED.value

def test_7_expired_session_preserves_encrypted_credentials(test_client):
    """7. Expired session marks status EXPIRED non-destructively while preserving ciphertext."""
    uid = uuid.uuid4().hex[:8]
    signup_res = test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"exp_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    user_id = signup_res.get_json()["user"]["user_id"]

    raw_cookie = json.dumps({"li_at": f"exp_cookie_{uid}", "JSESSIONID": f"ajax:{uid}"})
    save_linkedin_connection(user_id, raw_cookie)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    saved_ciphertext = record.auth_data_encrypted

    # Mock redirect to /uas/login indicating expiration
    mock_resp = Response()
    mock_resp.status_code = 302
    mock_resp.headers["Location"] = "https://www.linkedin.com/uas/login?from=checkpoint"

    with patch("requests.Session.get", return_value=mock_resp):
        res = test_client.get('/api/auth/linkedin/status')
        assert res.status_code == 200
        data = res.get_json()
        assert data["connected"] is False
        assert data["status"] == "expired"

    updated_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    assert updated_record.connection_status == "EXPIRED"
    assert updated_record.auth_data_encrypted == saved_ciphertext

def test_8_reloading_page_restores_connection_state_from_backend(test_client):
    """8. Page status endpoint reconstructs connected state from the database on reload."""
    uid = uuid.uuid4().hex[:8]
    signup_res = test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"reload_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    user_id = signup_res.get_json()["user"]["user_id"]

    # Initially disconnected
    res1 = test_client.get('/api/auth/linkedin/status')
    assert res1.get_json()["connected"] is False

    # Connect
    raw_cookie = json.dumps({"li_at": f"reload_c_{uid}", "JSESSIONID": f"ajax:{uid}"})
    save_linkedin_connection(user_id, raw_cookie)

    # Mock active session
    mock_active = Response()
    mock_active.status_code = 200
    with patch("requests.Session.get", return_value=mock_active):
        res2 = test_client.get('/api/auth/linkedin/status')
        assert res2.get_json()["connected"] is True
        assert res2.get_json()["status"] == "authenticated"

def test_9_protected_routes_cannot_bypass_onboarding(test_client):
    """9. A user with onboarding_step='LINKEDIN' attempting to access protected routes is redirected to /connect-linkedin."""
    uid = uuid.uuid4().hex[:8]
    res_signup = test_client.post('/api/auth/signup', json={
        "name": f"User {uid}",
        "email": f"guard_{uid}@example.com",
        "phone": _random_phone(),
        "password": "Password123!"
    })
    assert res_signup.status_code == 201

    # Cannot bypass to company
    r_company = test_client.get('/company', follow_redirects=False)
    assert r_company.status_code == 302
    assert '/connect-linkedin' in r_company.headers['Location']

    # Cannot bypass to icp
    r_icp = test_client.get('/icp', follow_redirects=False)
    assert r_icp.status_code == 302
    assert '/connect-linkedin' in r_icp.headers['Location']

    # Cannot bypass to profile-optimization
    r_opt = test_client.get('/profile-optimization', follow_redirects=False)
    assert r_opt.status_code == 302
    assert '/connect-linkedin' in r_opt.headers['Location']

    # Cannot bypass to dashboard
    r_dash = test_client.get('/dashboard', follow_redirects=False)
    assert r_dash.status_code == 302
    assert '/connect-linkedin' in r_dash.headers['Location']

def test_10_multi_user_connection_isolation(test_client):
    """10. User A connecting cannot affect User B's record or browser profile directory."""
    uid = uuid.uuid4().hex[:8]

    # User A
    res_a = test_client.post('/api/auth/signup', json={
        "name": f"Alice {uid}", "email": f"alice_{uid}@example.com", "phone": _random_phone(), "password": "Password123!"
    })
    assert res_a.status_code == 201
    user_a_id = res_a.get_json()["user"]["user_id"]
    test_client.post('/api/auth/logout')

    # User B
    res_b = test_client.post('/api/auth/signup', json={
        "name": f"Bob {uid}", "email": f"bob_{uid}@example.com", "phone": _random_phone(), "password": "Password123!"
    })
    assert res_b.status_code == 201
    user_b_id = res_b.get_json()["user"]["user_id"]

    # Bob connects
    raw_b = json.dumps({"li_at": f"bob_cookie_{uid}", "JSESSIONID": f"ajax:bob_{uid}"})
    save_linkedin_connection(user_b_id, raw_b)
    bob_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_b_id).first()
    assert bob_record is not None
    bob_ciphertext = bob_record.auth_data_encrypted

    # Log in as Alice and attempt connect
    test_client.post('/api/auth/logout')
    login_a = test_client.post('/api/auth/login', json={"identifier": f"alice_{uid}@example.com", "password": "Password123!"})
    assert login_a.status_code == 200

    with patch("legacy.profile_extractor.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.url = "https://www.linkedin.com/feed/"
        mock_page.title.return_value = "LinkedIn Feed"
        mock_ctx.pages = [mock_page]
        mock_ctx.cookies.return_value = [
            {"name": "li_at", "value": f"alice_cookie_{uid}", "domain": ".linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": f"ajax:alice_{uid}", "domain": ".linkedin.com", "path": "/"}
        ]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_ctx

        mock_voyager_resp = Response()
        mock_voyager_resp.status_code = 200
        mock_voyager_resp._content = b'{"data": "active"}'

        with patch("requests.Session.get", return_value=mock_voyager_resp):
            res_connect = test_client.post('/api/auth/linkedin/reconnect')
            assert res_connect.status_code == 200

    # Alice updated
    alice_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_a_id).first()
    assert alice_record is not None
    decrypted_alice = json.loads(decrypt_credential(alice_record.auth_data_encrypted))
    assert decrypted_alice["li_at"] == f"alice_cookie_{uid}"

    # Bob completely untouched
    bob_record_after = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_b_id).first()
    assert bob_record_after.auth_data_encrypted == bob_ciphertext
    decrypted_bob = json.loads(decrypt_credential(bob_record_after.auth_data_encrypted))
    assert decrypted_bob["li_at"] == f"bob_cookie_{uid}"
    assert decrypted_alice["li_at"] != decrypted_bob["li_at"]
