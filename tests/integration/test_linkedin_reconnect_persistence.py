import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UsersLinkedinDetails,
    ConnectionStatus,
    ResearchJobs,
    ResearchJobStatus
)
from app.services.onboarding_service import (
    save_linkedin_connection,
    get_linkedin_connection_status
)
from app.integrations.linkedin.voyager_client import (
    encrypt_credential,
    decrypt_credential,
    validate_user_session
)
from app.services.gtm_pipeline_service import (
    discover_candidates_via_voyager,
    CandidateList
)


def _create_test_user():
    user = UserTable(
        name="Reconnect Test Founder",
        email_id="reconnect_test@scaleflow.io",
        phone_no="+15551239999",
        password_hash="test_secret_hash",
        email_verified_at=datetime.utcnow(),
        onboarding_step="LINKEDIN",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


# ====================================================================
# 1. Successful cookie extraction and encrypted persistence
# ====================================================================

def test_successful_cookie_extraction_and_encrypted_persistence(clean_db):
    user = _create_test_user()
    valid_payload = json.dumps({
        "li_at": "AQEDAQC123456789_valid_token",
        "JSESSIONID": "ajax:9876543210123456789"
    })

    result = save_linkedin_connection(user.user_id, valid_payload)
    assert result["connected"] is True
    assert result["status"] == ConnectionStatus.CONNECTED.value

    # Verify DB persistence directly
    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert db_record is not None
    assert db_record.connection_status == ConnectionStatus.CONNECTED.value
    assert db_record.auth_data_encrypted is not None

    # Verify decryption matches
    decrypted = decrypt_credential(db_record.auth_data_encrypted)
    data = json.loads(decrypted)
    assert data["li_at"] == "AQEDAQC123456789_valid_token"
    assert data["JSESSIONID"] == "ajax:9876543210123456789"

    # Verify user advanced from LINKEDIN to COMPANY
    refreshed_user = db_session.query(UserTable).filter_by(user_id=user.user_id).first()
    assert refreshed_user.onboarding_step == "COMPANY"


# ====================================================================
# 2. Missing or invalid required cookies
# ====================================================================

@pytest.mark.parametrize("invalid_payload", [
    json.dumps({"JSESSIONID": "ajax:9876543210"}),  # missing li_at
    json.dumps({"li_at": "AQEDAQC12345"}),           # missing JSESSIONID
    json.dumps({"li_at": "AQEDAQC12345", "JSESSIONID": "ajax:0000000000000000000"}),  # dummy JSESSIONID
    json.dumps({"li_at": "", "JSESSIONID": "ajax:9876543210"}),  # empty li_at
    json.dumps({}),                                  # empty JSON
    "not-a-json-string",                             # malformed string
    ""                                               # empty string
])
def test_missing_or_invalid_required_cookies(clean_db, invalid_payload):
    user = _create_test_user()
    with pytest.raises(ValueError):
        save_linkedin_connection(user.user_id, invalid_payload)

    # Ensure no connection was created
    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert db_record is None or db_record.connection_status != ConnectionStatus.CONNECTED.value


# ====================================================================
# 3. Login completed but database persistence failed
# ====================================================================

def test_login_completed_but_database_persistence_fails(clean_db):
    user = _create_test_user()
    valid_payload = json.dumps({
        "li_at": "AQEDAQC_login_done",
        "JSESSIONID": "ajax:5555555555555555555"
    })

    with patch("app.services.onboarding_service.db_session.commit", side_effect=RuntimeError("Simulated database disk failure")):
        with pytest.raises(RuntimeError) as exc_info:
            save_linkedin_connection(user.user_id, valid_payload)
        assert "Simulated database disk failure" in str(exc_info.value)

    # Verify database was rolled back and no corrupted connection exists
    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert db_record is None or db_record.connection_status != ConnectionStatus.CONNECTED.value


# ====================================================================
# 4. Reconnect failure preserving existing encrypted credentials
# ====================================================================

def test_reconnect_failure_preserves_existing_encrypted_credentials(clean_db, client):
    user = _create_test_user()
    initial_payload = json.dumps({
        "li_at": "AQEDAQC_INITIAL_VALID",
        "JSESSIONID": "ajax:1111222233334444555"
    })
    save_linkedin_connection(user.user_id, initial_payload)

    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    original_encrypted = db_record.auth_data_encrypted
    original_consent_at = db_record.consent_at

    # 1. Test service level preservation on invalid payload
    with pytest.raises(ValueError):
        save_linkedin_connection(user.user_id, json.dumps({"li_at": "new_partial_cookie"}))

    db_session.refresh(db_record)
    assert db_record.auth_data_encrypted == original_encrypted
    assert db_record.connection_status == ConnectionStatus.CONNECTED.value
    assert db_record.consent_at == original_consent_at

    # 2. Test route level preservation when interactive login fails
    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    mock_fail = {
        "success": False,
        "message": "Browser window was closed before LinkedIn authentication completed.",
        "error": "WINDOW_CLOSED"
    }

    with patch("legacy.profile_extractor.launch_interactive_linkedin_login", return_value=mock_fail):
        res = client.post("/api/auth/linkedin/reconnect")
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert data["connected"] is False
        assert data["error"] in ("WINDOW_CLOSED", "RECONNECT_FAILED")
        assert "closed" in data["message"].lower()

    # Re-verify DB credentials are completely unchanged
    db_session.refresh(db_record)
    assert db_record.auth_data_encrypted == original_encrypted
    assert db_record.connection_status == ConnectionStatus.CONNECTED.value


# ====================================================================
# 5. Successful post-save validation
# ====================================================================

def test_successful_post_save_validation(clean_db):
    user = _create_test_user()
    valid_payload = json.dumps({
        "li_at": "AQEDAQC_VALID_POST_SAVE",
        "JSESSIONID": "ajax:8888777766665555444"
    })

    # Normal save succeeds because post-save decryption validation passes
    result = save_linkedin_connection(user.user_id, valid_payload)
    assert result["connected"] is True

    # If post-save decryption fails or returns missing fields, RuntimeError must be raised
    with patch("app.services.onboarding_service.decrypt_credential", return_value=json.dumps({"li_at": "AQEDAQC"})):
        with pytest.raises(RuntimeError) as exc_info:
            save_linkedin_connection(user.user_id, valid_payload)
        assert "Post-save verification failed" in str(exc_info.value)


# ====================================================================
# 6. Session expiry detected before GTM discovery begins
# ====================================================================

def test_session_expiry_detected_before_gtm_discovery_begins(clean_db):
    user = _create_test_user()
    valid_payload = json.dumps({
        "li_at": "AQEDAQC_PRE_FLIGHT_TEST",
        "JSESSIONID": "ajax:9999000011112222333"
    })
    save_linkedin_connection(user.user_id, valid_payload)

    search_plan = {
        "queries": [
            {"id": "q1", "title": "VP of Sales", "keywords": "VP Sales B2B SaaS", "priority": 1}
        ]
    }

    mock_expired_validation = {
        "valid": False,
        "category": "expired",
        "message": "LinkedIn session has expired or was revoked. Please reconnect your account."
    }

    with patch("app.services.gtm_pipeline_service.validate_user_session", return_value=mock_expired_validation) as mock_validate, \
         patch("app.services.gtm_pipeline_service.create_voyager_client_from_db") as mock_create_client:

        candidates = discover_candidates_via_voyager(user.user_id, search_plan, limit=5)

        # Pre-flight check must have been called
        mock_validate.assert_called_once_with(user.user_id)
        # Client creation / network search must NOT have been called
        mock_create_client.assert_not_called()

        assert isinstance(candidates, CandidateList)
        assert len(candidates) == 0
        assert candidates.status == "AUTH_EXPIRED"
        assert candidates.error_category in ("expired", "auth_expired")


# ====================================================================
# 7. Authentication transition: destination URL and DOM required
# ====================================================================

def test_interactive_login_requires_authenticated_destination_and_dom(clean_db):
    from legacy.profile_extractor import launch_interactive_linkedin_login

    user = _create_test_user()

    # Create mock page that progresses:
    # Step 1: On checkpoint/login-submit with cookies present -> must NOT capture
    # Step 2: On root linkedin.com/ without DOM -> must NOT capture
    # Step 3: On feed with nav DOM -> MUST capture
    mock_page = MagicMock()
    mock_page.is_closed.return_value = False
    mock_page.title.return_value = "LinkedIn Feed"

    states = [
        ("https://www.linkedin.com/checkpoint/lg/login-submit", False),
        ("https://www.linkedin.com/", False),
        ("https://www.linkedin.com/feed/", True),
    ]
    state_iter = iter(states)

    def side_effect_url():
        nonlocal current_state
        return current_state[0]

    current_state = states[0]

    def advance_state():
        nonlocal current_state
        try:
            current_state = next(state_iter)
        except StopIteration:
            pass

    mock_locator = MagicMock()
    mock_locator.count.side_effect = lambda: 1 if current_state[1] else 0
    mock_page.locator.return_value = mock_locator
    type(mock_page).url = property(lambda self: current_state[0])

    mock_context = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "li_at", "value": "AQEDAQC_PROGRESSIVE_TRANSITION"},
        {"name": "JSESSIONID", "value": '"ajax:1122334455667788990"'}
    ]

    # Patch playwright inside launch_interactive_linkedin_login
    with patch("legacy.profile_extractor.sync_playwright") as mock_sp:
        mock_p_instance = MagicMock()
        mock_sp.return_value.__enter__.return_value = mock_p_instance
        mock_p_instance.chromium.launch_persistent_context.return_value = mock_context
        mock_context.pages = [mock_page]

        # Patch time.sleep to advance state
        with patch("time.sleep", side_effect=lambda s: advance_state()), \
             patch("app.services.onboarding_service.save_linkedin_connection") as mock_save:

            res = launch_interactive_linkedin_login(user.user_id)
            assert res["success"] is True
            # Verify save_linkedin_connection was called only after reaching feed with DOM
            assert mock_save.called
            saved_payload = mock_save.call_args[0][1]
            data = json.loads(saved_payload)
            assert data["li_at"] == "AQEDAQC_PROGRESSIVE_TRANSITION"
            assert data["JSESSIONID"] == "ajax:1122334455667788990"

