import os
import json
import uuid
from datetime import datetime
import pytest
from unittest.mock import MagicMock, patch
from requests.exceptions import Timeout, ConnectionError
from requests.models import Response

from app_module import app
from app.database import db_session, Base, engine
from app.models.all_models import UserTable, UsersLinkedinDetails, OnboardingStep
from app.integrations.linkedin.voyager_client import (
    encrypt_credential,
    decrypt_credential,
    create_voyager_client_from_db,
    validate_user_session,
    validate_linkedin_connection,
    get_browser_profile_dir
)
from legacy.profile_extractor import (
    check_linkedin_session,
    logout_linkedin_session,
    launch_interactive_linkedin_login
)
from app.services.onboarding_service import save_linkedin_connection, save_company

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    db_session.rollback()

def test_encryption_decryption_roundtrip():
    payload = json.dumps({"li_at": "test_li_at_12345", "JSESSIONID": "ajax:987654321"})
    ciphertext = encrypt_credential(payload)
    assert ciphertext != payload
    assert isinstance(ciphertext, str)
    decrypted = decrypt_credential(ciphertext)
    assert decrypted == payload

def test_corrupted_ciphertext_fails_safely():
    with pytest.raises(Exception):
        decrypt_credential("corrupted_invalid_base64_data_xyz")

def test_cookie_validation_rejects_dummy_and_incomplete():
    uid = uuid.uuid4().hex[:8]
    # 1. Missing li_at
    user_1 = UserTable(name="Test 1", email_id=f"t1_{uid}@example.com", password_hash="hash")
    db_session.add(user_1)
    db_session.commit()

    li_1 = UsersLinkedinDetails(
        user_id=user_1.user_id,
        auth_data_encrypted=encrypt_credential(json.dumps({"JSESSIONID": "ajax:12345"}))
    )
    db_session.add(li_1)
    db_session.commit()

    assert create_voyager_client_from_db(user_1.user_id) is None

    # 2. Dummy JSESSIONID
    li_1.auth_data_encrypted = encrypt_credential(json.dumps({
        "li_at": "valid_li_at",
        "JSESSIONID": '"ajax:0000000000000000000"'
    }))
    db_session.commit()
    assert create_voyager_client_from_db(user_1.user_id) is None

    # 3. Valid cookies
    li_1.auth_data_encrypted = encrypt_credential(json.dumps({
        "li_at": "valid_li_at",
        "JSESSIONID": "ajax:9988776655"
    }))
    db_session.commit()
    client = create_voyager_client_from_db(user_1.user_id)
    assert client is not None
    assert client.client.session.cookies.get("li_at") == "valid_li_at"
    assert client.client.session.cookies.get("JSESSIONID") == "ajax:9988776655"

def test_multi_user_client_isolation():
    uid = uuid.uuid4().hex[:8]
    user_a = UserTable(name="Alice", email_id=f"alice_{uid}@example.com", password_hash="hash")
    user_b = UserTable(name="Bob", email_id=f"bob_{uid}@example.com", password_hash="hash")
    db_session.add_all([user_a, user_b])
    db_session.commit()

    li_a = UsersLinkedinDetails(
        user_id=user_a.user_id,
        auth_data_encrypted=encrypt_credential(json.dumps({"li_at": "cookie_alice", "JSESSIONID": "ajax:alice"}))
    )
    li_b = UsersLinkedinDetails(
        user_id=user_b.user_id,
        auth_data_encrypted=encrypt_credential(json.dumps({"li_at": "cookie_bob", "JSESSIONID": "ajax:bob"}))
    )
    db_session.add_all([li_a, li_b])
    db_session.commit()

    client_a = create_voyager_client_from_db(user_a.user_id)
    client_b = create_voyager_client_from_db(user_b.user_id)

    assert client_a.client.session.cookies.get("li_at") == "cookie_alice"
    assert client_b.client.session.cookies.get("li_at") == "cookie_bob"
    assert client_a.client.session.cookies.get("li_at") != client_b.client.session.cookies.get("li_at")

def test_multi_user_reconnection_isolation():
    uid = uuid.uuid4().hex[:8]
    user_a = UserTable(name="Alice", email_id=f"alice2_{uid}@example.com", password_hash="hash")
    user_b = UserTable(name="Bob", email_id=f"bob2_{uid}@example.com", password_hash="hash")
    db_session.add_all([user_a, user_b])
    db_session.commit()

    save_linkedin_connection(user_b.user_id, json.dumps({"li_at": "bob_original", "JSESSIONID": "ajax:bob"}))
    initial_bob_auth = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_b.user_id).first().auth_data_encrypted

    # Mock Playwright execution for Alice
    with patch("legacy.profile_extractor.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.url = "https://www.linkedin.com/feed/"
        mock_page.title.return_value = "LinkedIn Feed"
        mock_page.locator.return_value.count.return_value = 1
        mock_ctx.pages = [mock_page]
        mock_ctx.cookies.return_value = [
            {"name": "li_at", "value": "alice_new_cookie", "domain": ".linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": "ajax:alice_new", "domain": ".linkedin.com", "path": "/"}
        ]
        mock_pw.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_ctx

        with patch("time.sleep", return_value=None):
            res = launch_interactive_linkedin_login(user_a.user_id)
        assert res["success"] is True

    # Alice updated
    alice_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_a.user_id).first()
    assert alice_record is not None
    decrypted_alice = json.loads(decrypt_credential(alice_record.auth_data_encrypted))
    assert decrypted_alice["li_at"] == "alice_new_cookie"

    # Bob untouched
    bob_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_b.user_id).first()
    assert bob_record.auth_data_encrypted == initial_bob_auth

def test_session_validation_confirmed_expiration_preserves_ciphertext():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(name="Carol", email_id=f"carol_{uid}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    raw_cookie = json.dumps({"li_at": "cookie_carol", "JSESSIONID": "ajax:carol"})
    save_linkedin_connection(user.user_id, raw_cookie)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    saved_ciphertext = record.auth_data_encrypted
    assert record.connection_status == "CONNECTED"

    # Mock 302 redirecting to /uas/login
    mock_resp = Response()
    mock_resp.status_code = 302
    mock_resp.headers["Location"] = "https://www.linkedin.com/uas/login?from=xyz"

    with patch("requests.Session.get", return_value=mock_resp):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "expired"

    # Record updated non-destructively: status becomes EXPIRED, ciphertext is kept
    db_session.refresh(record)
    assert record.connection_status == "EXPIRED"
    assert record.auth_data_encrypted == saved_ciphertext

def test_session_validation_transient_and_rate_limit_errors_preserve_credentials_and_status():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(name="Dan", email_id=f"dan_{uid}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    raw_cookie = json.dumps({"li_at": "cookie_dan", "JSESSIONID": "ajax:dan"})
    save_linkedin_connection(user.user_id, raw_cookie)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    saved_ciphertext = record.auth_data_encrypted

    # 1. HTTP 429 Rate Limit
    mock_429 = Response()
    mock_429.status_code = 429
    with patch("requests.Session.get", return_value=mock_429):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "rate_limited"

    db_session.refresh(record)
    assert record.connection_status == "CONNECTED"
    assert record.auth_data_encrypted == saved_ciphertext

    # 2. Timeout
    with patch("requests.Session.get", side_effect=Timeout("Connection timed out")):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "network_error"

    db_session.refresh(record)
    assert record.connection_status == "CONNECTED"
    assert record.auth_data_encrypted == saved_ciphertext

    # 3. HTTP 500 Server Error
    mock_500 = Response()
    mock_500.status_code = 500
    with patch("requests.Session.get", return_value=mock_500):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "network_error"

    db_session.refresh(record)
    assert record.connection_status == "CONNECTED"
    assert record.auth_data_encrypted == saved_ciphertext

    # 4. Ambiguous Redirect (e.g. 302 to /checkpoint/challenge or temporary)
    mock_ambiguous = Response()
    mock_ambiguous.status_code = 302
    mock_ambiguous.headers["Location"] = "https://www.linkedin.com/check-status"
    with patch("requests.Session.get", return_value=mock_ambiguous):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "unknown_error"

    db_session.refresh(record)
    assert record.connection_status == "CONNECTED"
    assert record.auth_data_encrypted == saved_ciphertext

def test_legacy_routes_unauthenticated_and_user_scoped():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        # Unauthenticated calls should return 401 or safe unauthenticated data without launching Chromium
        r_open = client.post("/api/open-linkedin-session")
        assert r_open.status_code == 401
        assert r_open.get_json()["error"] == "UNAUTHORIZED"

        r_status = client.get("/api/linkedin-session-status")
        assert r_status.status_code == 200
        assert r_status.get_json()["data"]["authenticated"] is False

        r_logout = client.post("/api/logout-linkedin-session")
        assert r_logout.status_code == 200

def test_signup_onboarding_state_consistency():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(
        name="Eve",
        email_id=f"eve_{uid}@example.com",
        password_hash="hash",
        onboarding_step=OnboardingStep.LINKEDIN.value
    )
    db_session.add(user)
    db_session.commit()
    assert user.onboarding_step == "LINKEDIN"

    # Connecting LinkedIn advances to COMPANY
    save_linkedin_connection(user.user_id, json.dumps({"li_at": "eve_cookie", "JSESSIONID": "ajax:eve"}))
    db_session.refresh(user)
    assert user.onboarding_step == "COMPANY"

    # Saving company details advances to ICP
    save_company(user.user_id, {"website_url": "https://eve.com", "company_name": "Eve Corp"})
    db_session.refresh(user)
    assert user.onboarding_step == "ICP"

def test_session_validation_detects_self_redirect_as_expired():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(name="SelfRedir", email_id=f"redir_{uid}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    raw_cookie = json.dumps({"li_at": "cookie_redir", "JSESSIONID": "ajax:redir"})
    save_linkedin_connection(user.user_id, raw_cookie)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    saved_ciphertext = record.auth_data_encrypted

    mock_resp = Response()
    mock_resp.status_code = 302
    mock_resp.headers["Location"] = "https://www.linkedin.com/voyager/api/me"

    with patch("requests.Session.get", return_value=mock_resp):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "expired"

    db_session.refresh(record)
    assert record.connection_status == "EXPIRED"
    assert record.auth_data_encrypted == saved_ciphertext

def test_session_validation_detects_clear_site_data_header_as_expired():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(name="ClearData", email_id=f"cleardata_{uid}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    raw_cookie = json.dumps({"li_at": "cookie_clear", "JSESSIONID": "ajax:clear"})
    save_linkedin_connection(user.user_id, raw_cookie)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()

    mock_resp = Response()
    mock_resp.status_code = 302
    mock_resp.headers["Location"] = "https://www.linkedin.com/some/path"
    mock_resp.headers["Clear-Site-Data"] = '"storage"'

    with patch("requests.Session.get", return_value=mock_resp):
        res = validate_user_session(user.user_id)
        assert res["valid"] is False
        assert res["category"] == "expired"

    db_session.refresh(record)
    assert record.connection_status == "EXPIRED"

def test_reconnect_route_fails_when_validation_fails():
    uid = uuid.uuid4().hex[:8]
    user = UserTable(
        name="ReconFail",
        email_id=f"reconfail_{uid}@example.com",
        password_hash="hash",
        email_verified_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    user_id = user.user_id

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Mock interactive login returning success, but validate_user_session reporting invalid/expired
        with patch("legacy.profile_extractor.launch_interactive_linkedin_login", return_value={"success": True}), \
             patch("app.integrations.linkedin.voyager_client.validate_user_session", return_value={"valid": False, "category": "expired", "message": "Session expired"}):
            res = client.post('/api/auth/linkedin/reconnect')
            assert res.status_code == 400
            data = res.get_json()
            assert data["success"] is False
            assert data["connected"] is False
            assert data["error"] == "VALIDATION_FAILED"
