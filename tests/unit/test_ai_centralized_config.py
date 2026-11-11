import pytest
import os
import json
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials
from app.services.claude_service import (
    get_claude_config,
    set_claude_api_config,
    get_active_claude_api_key,
    test_claude_connection as run_claude_connection_test
)
from app.services.gemini_service import (
    get_gemini_config,
    set_gemini_api_config,
    get_active_gemini_api_key,
    test_gemini_connection as run_gemini_connection_test,
    fetch_available_gemini_models
)


# ====================================================================
# 1. Encryption and Decryption Tests (Claude & Gemini)
# ====================================================================

def test_claude_and_gemini_encryption_isolated():
    """Verify AES-256-GCM encryption and decryption roundtrips independently."""
    claude_key = "sk-ant-api03-test-secret-key-1234567890"
    gemini_key = "AIzaSyTestSecretGeminiKey1234567890"

    enc_c, ver_c = encrypt_smtp_credentials({"api_key": claude_key})
    enc_g, ver_g = encrypt_smtp_credentials({"api_key": gemini_key})

    assert enc_c != enc_g
    assert enc_c != claude_key
    assert enc_g != gemini_key

    dec_c = decrypt_smtp_credentials(enc_c, ver_c)
    dec_g = decrypt_smtp_credentials(enc_g, ver_g)

    assert dec_c.get("api_key") == claude_key
    assert dec_g.get("api_key") == gemini_key


# ====================================================================
# 2. Configuration Persistence and Masking (Zero Raw Key Leakage)
# ====================================================================

@patch("app.services.gemini_service.db_session")
@patch("app.services.gemini_service._load_gemini_setting_record")
def test_gemini_config_masking(mock_load, mock_db):
    """Ensure get_gemini_config masks raw keys and never returns raw plaintext."""
    mock_rec = MagicMock()
    mock_rec.encrypted_value, mock_rec.encryption_key_version = encrypt_smtp_credentials(
        {"api_key": "AIzaSyTestVeryLongSecretKeyForGeminiAPI99"}
    )
    mock_rec.metadata_json = {
        "model": "gemini-2.5-flash",
        "timeout_seconds": 20,
        "available_models": ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
    }
    mock_load.return_value = mock_rec

    config = get_gemini_config()
    assert config["is_configured"] is True
    assert config["model"] == "gemini-2.5-flash"
    assert config["timeout_seconds"] == 20
    assert "AIzaSyTestVeryLongSecretKeyForGeminiAPI99" not in json.dumps(config)
    assert config["masked_key"].startswith("AIzaSy")
    assert config["masked_key"].endswith("PI99")


@patch("app.services.claude_service.db_session")
@patch("app.services.claude_service._load_setting_record")
def test_claude_config_masking(mock_load, mock_db):
    """Ensure get_claude_config masks raw keys and never returns raw plaintext."""
    mock_rec = MagicMock()
    mock_rec.encrypted_value, mock_rec.encryption_key_version = encrypt_smtp_credentials(
        {"api_key": "sk-ant-api03-verylongsecretkeytest9999"}
    )
    mock_rec.metadata_json = {
        "model": "claude-sonnet-5-5",
        "timeout_seconds": 15,
        "available_models": ["claude-sonnet-5-5"]
    }
    mock_load.return_value = mock_rec

    config = get_claude_config()
    assert config["is_configured"] is True
    assert "sk-ant-api03-verylongsecretkeytest9999" not in json.dumps(config)
    assert config["masked_key"].startswith("sk-ant-")


# ====================================================================
# 3. Independent Provider Configuration
# ====================================================================

@patch("app.services.gemini_service.db_session")
@patch("app.services.gemini_service._load_gemini_setting_record")
def test_set_gemini_api_config_persists_without_claude(mock_load, mock_db):
    """Gemini can be configured completely independently of Claude."""
    mock_load.return_value = None

    success, err, summary = set_gemini_api_config(
        api_key="AIzaSyIndependentKey12345",
        model="gemini-3.8-flash",
        timeout=25,
        admin_user_id=1
    )

    assert success is True
    assert err is None
    assert summary["model"] == "gemini-3.8-flash"
    assert summary["timeout_seconds"] == 25
    assert "AIzaSyIndependentKey12345" not in json.dumps(summary)
    assert mock_db.commit.called


# ====================================================================
# 4. Diagnostics & Network Classifications (Gemini)
# ====================================================================

def test_gemini_diagnostics_unconfigured():
    """Unconfigured key returns NOT_CONFIGURED."""
    with patch("app.services.gemini_service.get_active_gemini_api_key", return_value=None):
        diag = run_gemini_connection_test(api_key=None)
        assert diag["success"] is False
        assert diag["status"] == "NOT_CONFIGURED"


@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_live_success(mock_client_cls):
    """Valid key and response yields LIVE_CONNECTION_SUCCESS."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyValidKeyMock123456", model="gemini-2.5-flash")
    assert diag["success"] is True
    assert diag["status"] == "LIVE_CONNECTION_SUCCESS"
    assert diag["model_used"] == "gemini-2.5-flash"
    assert "AIzaSyValidKeyMock123456" not in json.dumps(diag)


@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_auth_failure(mock_client_cls):
    """Invalid API key yields AUTHENTICATION_FAILED."""
    from google.genai import errors
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        400,
        {"error": {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
    )
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyInvalidKeyMock", model="gemini-2.5-flash")
    assert diag["success"] is False
    assert diag["status"] == "AUTHENTICATION_FAILED"
    assert diag["error_category"] == "INVALID_API_KEY"


@patch("app.services.gemini_service.genai.Client")
def test_gemini_diagnostics_quota_exhausted(mock_client_cls):
    """Resource exhausted / 429 yields QUOTA_EXCEEDED."""
    from google.genai import errors
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        429,
        {"error": {"message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}
    )
    mock_client_cls.return_value = mock_client

    diag = run_gemini_connection_test(api_key="AIzaSyValidKeyNoQuota", model="gemini-2.5-flash")
    assert diag["success"] is False
    assert diag["status"] == "QUOTA_EXCEEDED"
    assert diag["error_category"] in ("QUOTA_EXCEEDED", "RATE_OR_QUOTA_EXHAUSTED")


# ====================================================================
# 5. Gemini Model Discovery
# ====================================================================

@patch("app.services.gemini_service.genai.Client")
@patch("app.services.gemini_service._load_gemini_setting_record")
def test_fetch_available_gemini_models(mock_load, mock_client_cls):
    """Models API query extracts live model catalog and preserves selected model."""
    mock_client = MagicMock()
    m1 = MagicMock(); m1.name = "models/gemini-2.5-flash"
    m2 = MagicMock(); m2.name = "models/gemini-3.5-flash-lite"
    m3 = MagicMock(); m3.name = "models/gemini-3.8-flash"
    m4 = MagicMock(); m4.name = "models/embedding-001" # non-gemini model should be filtered
    mock_client.models.list.return_value = [m1, m2, m3, m4]
    mock_client_cls.return_value = mock_client

    mock_load.return_value = None

    res = fetch_available_gemini_models(api_key="AIzaSyValidKey123")
    assert res["success"] is True
    assert "gemini-2.5-flash" in res["models"]
    assert "gemini-3.5-flash-lite" in res["models"]
    assert "gemini-3.8-flash" in res["models"]
    assert "embedding-001" not in res["models"]


# ====================================================================
# 6. RBAC & Superadmin Route Security
# ====================================================================

def test_admin_routes_superadmin_enforcement(client):
    """Regular unauthenticated / non-superadmin users are denied access to provider config endpoints."""
    # 1. Unauthenticated requests are rejected with 401
    res1 = client.get("/api/admin/gemini/config")
    assert res1.status_code == 401

    res2 = client.post("/api/admin/gemini/config", json={"api_key": "test"})
    assert res2.status_code == 401

    res3 = client.post("/api/admin/gemini/test-connection", json={})
    assert res3.status_code == 401

    res4 = client.get("/api/admin/gemini/models")
    assert res4.status_code == 401

    # 2. Authenticated active regular user without SUPER_ADMIN role is rejected with 403
    mock_regular_user = MagicMock()
    mock_regular_user.user_id = 999
    mock_regular_user.is_active = True
    mock_regular_user.email_verified_at = "2026-01-01"
    mock_regular_user.role = "USER"

    with patch("app.security.session.get_user_by_id", return_value=mock_regular_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 999
                sess["role"] = "USER"

            res_user = client.get("/api/admin/gemini/config")
            assert res_user.status_code == 403
            data = res_user.get_json()
            assert data["error"] == "FORBIDDEN"
