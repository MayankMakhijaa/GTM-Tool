import pytest
import os
import json
from unittest.mock import patch, MagicMock

from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials
from app.models.all_models import AuditLog
from app.services.gemini_service import (
    get_gemini_config,
    set_gemini_api_config,
    get_active_gemini_api_key,
    test_gemini_connection as run_gemini_connection_test,
    fetch_available_gemini_models
)
from app.services.claude_service import (
    get_claude_config,
    test_claude_connection as run_claude_connection_test
)


# ====================================================================
# 1. Gemini Configuration Save & Update
# ====================================================================

@patch("app.services.gemini_service.db_session")
@patch("app.services.gemini_service._load_gemini_setting_record")
def test_gemini_config_save_and_update(mock_load, mock_db):
    """Test saving new Gemini config and subsequently updating model/timeout."""
    mock_load.return_value = None

    # Initial save
    success, err, summary = set_gemini_api_config(
        api_key="AIzaSyInitialSecretKey12345678",
        model="gemini-2.5-flash",
        timeout=15,
        admin_user_id=1
    )
    assert success is True
    assert err is None
    assert summary["model"] == "gemini-2.5-flash"
    assert summary["timeout_seconds"] == 15
    assert "AIzaSyInitialSecretKey12345678" not in json.dumps(summary)
    assert mock_db.commit.called

    # Mock record existing for update without re-passing raw key
    mock_rec = MagicMock()
    mock_rec.encrypted_value, mock_rec.encryption_key_version = encrypt_smtp_credentials(
        {"api_key": "AIzaSyInitialSecretKey12345678"}
    )
    mock_rec.metadata_json = {
        "model": "gemini-2.5-flash",
        "timeout_seconds": 15
    }
    mock_load.return_value = mock_rec

    # Update model and timeout only
    success_up, err_up, summary_up = set_gemini_api_config(
        api_key=None,  # Leave blank to preserve existing key
        model="gemini-3.8-flash",
        timeout=30,
        admin_user_id=1
    )
    assert success_up is True
    assert err_up is None
    assert summary_up["model"] == "gemini-3.8-flash"
    assert summary_up["timeout_seconds"] == 30
    assert summary_up["is_configured"] is True


# ====================================================================
# 2. Connection Diagnostics (Success, 503 Overload, Invalid Key)
# ====================================================================

@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_mocked_success(mock_client_cls):
    """Valid key and response yields LIVE_CONNECTION_SUCCESS without function-calling warnings."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyValidKeyMock123456", model="gemini-2.5-flash")
    assert diag["success"] is True
    assert diag["status"] == "LIVE_CONNECTION_SUCCESS"
    assert diag["model_used"] == "gemini-2.5-flash"
    assert "AIzaSyValidKeyMock123456" not in json.dumps(diag)

    # Verify automatic_function_calling was disabled in GenerateContentConfig
    call_args = mock_client.models.generate_content.call_args
    cfg = call_args[1].get("config") or call_args[0][2]
    assert cfg.automatic_function_calling.disable is True


@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_503_overloaded(mock_client_cls):
    """HTTP 503 / high demand is accurately classified as PROVIDER_UNAVAILABLE, not invalid key."""
    from google.genai import errors
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        503,
        {"error": {"message": "This model is currently experiencing high demand. Please try again later.", "status": "UNAVAILABLE"}}
    )
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyValidKeyOverloaded", model="gemini-2.5-flash")
    assert diag["success"] is False
    assert diag["status"] == "PROVIDER_UNAVAILABLE"
    assert diag["error_category"] == "TEMPORARY_OVERLOAD"
    assert "high demand" in diag["message"].lower()
    assert "503" in diag["message"]


@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_invalid_api_key(mock_client_cls):
    """HTTP 400 with invalid API key is accurately classified as AUTHENTICATION_FAILED."""
    from google.genai import errors
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        400,
        {"error": {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
    )
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyBadKey", model="gemini-2.5-flash")
    assert diag["success"] is False
    assert diag["status"] == "AUTHENTICATION_FAILED"
    assert diag["error_category"] == "INVALID_API_KEY"


# ====================================================================
# 3. Superadmin Endpoints & Audit Logging (No NameError)
# ====================================================================

def test_admin_gemini_endpoints_audit_logging(client):
    """Verify update and test-connection routes record AuditLog using proper model and don't throw NameError."""
    mock_admin_user = MagicMock()
    mock_admin_user.user_id = 1
    mock_admin_user.is_active = True
    mock_admin_user.email_verified_at = "2026-01-01"
    mock_admin_user.role = "SUPER_ADMIN"

    with patch("app.security.session.get_user_by_id", return_value=mock_admin_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["role"] = "SUPER_ADMIN"

            # 1. Update config endpoint
            with patch("app.services.gemini_service.set_gemini_api_config") as mock_set:
                mock_set.return_value = (True, None, {
                    "is_configured": True,
                    "masked_key": "AIzaSy...7890",
                    "model": "gemini-2.5-flash",
                    "timeout_seconds": 15
                })
                with patch("app.routes.admin.db_session") as mock_db:
                    res = client.post("/api/admin/gemini/config", json={
                        "api_key": "AIzaSyNewSuperadminKey7890",
                        "model": "gemini-2.5-flash",
                        "timeout": 15
                    })
                    assert res.status_code == 200
                    data = res.get_json()
                    assert data["success"] is True
                    assert "AIzaSyNewSuperadminKey7890" not in json.dumps(data)

                    # Verify AuditLog was instantiated and committed
                    assert mock_db.add.called
                    audit_entry = mock_db.add.call_args[0][0]
                    assert isinstance(audit_entry, AuditLog)
                    assert audit_entry.action == "ADMIN_UPDATE_GEMINI_CONFIG"
                    assert audit_entry.admin_user_id == 1
                    assert "AIzaSyNewSuperadminKey7890" not in json.dumps(audit_entry.metadata_json)
                    assert audit_entry.metadata_json["has_key"] is True

            # 2. Test connection endpoint
            with patch("app.services.gemini_service.test_gemini_connection") as mock_diag:
                mock_diag.return_value = {
                    "success": False,
                    "status": "PROVIDER_UNAVAILABLE",
                    "error_category": "TEMPORARY_OVERLOAD",
                    "message": "Google Gemini is temporarily experiencing high demand (HTTP 503).",
                    "model_used": "gemini-2.5-flash",
                    "latency_ms": 120,
                    "tested_at": "2026-11-05T00:00:00"
                }
                with patch("app.routes.admin.db_session") as mock_db:
                    res = client.post("/api/admin/gemini/test-connection", json={
                        "model": "gemini-2.5-flash"
                    })
                    assert res.status_code == 200
                    data = res.get_json()
                    assert data["success"] is True
                    assert data["diagnostic"]["status"] == "PROVIDER_UNAVAILABLE"

                    # Verify AuditLog was instantiated and committed
                    assert mock_db.add.called
                    audit_entry = mock_db.add.call_args[0][0]
                    assert isinstance(audit_entry, AuditLog)
                    assert audit_entry.action == "ADMIN_TEST_GEMINI_CONNECTION"
                    assert audit_entry.metadata_json["status"] == "PROVIDER_UNAVAILABLE"


def test_admin_gemini_audit_failure_is_non_destructive(client):
    """If audit log persistence fails, the configuration update still succeeds."""
    mock_admin_user = MagicMock()
    mock_admin_user.user_id = 1
    mock_admin_user.is_active = True
    mock_admin_user.email_verified_at = "2026-01-01"
    mock_admin_user.role = "SUPER_ADMIN"

    with patch("app.security.session.get_user_by_id", return_value=mock_admin_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["role"] = "SUPER_ADMIN"

            with patch("app.services.gemini_service.set_gemini_api_config") as mock_set:
                mock_set.return_value = (True, None, {
                    "is_configured": True,
                    "masked_key": "AIzaSy...7890",
                    "model": "gemini-2.5-flash",
                    "timeout_seconds": 15
                })
                with patch("app.routes.admin.db_session") as mock_db:
                    # Simulate audit log commit failure
                    mock_db.commit.side_effect = Exception("Audit DB constraint error")

                    res = client.post("/api/admin/gemini/config", json={
                        "api_key": "AIzaSyNewSuperadminKey7890",
                        "model": "gemini-2.5-flash"
                    })
                    # Config save must still return success
                    assert res.status_code == 200
                    assert res.get_json()["success"] is True


# ====================================================================
# 4. Existing Claude Configuration Regression
# ====================================================================

def test_claude_configuration_unaffected():
    """Ensure Claude configuration and diagnostics remain fully functional."""
    with patch("app.services.claude_service.get_active_claude_api_key", return_value=None):
        diag = run_claude_connection_test()
        assert diag["success"] is False
        assert diag["status"] == "NOT_CONFIGURED"

    config = get_claude_config()
    assert "model" in config
    assert "supported_models" in config

