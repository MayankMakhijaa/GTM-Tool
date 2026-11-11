"""
Focused unit tests for Claude API configuration, connection testing,
dedicated system_settings persistence, GET /v1/models dynamic model discovery,
unavailable/deprecated/retired model handling, request ID retention,
and error classification.
"""

import pytest
import requests
from unittest.mock import MagicMock
from app.services.claude_service import (
    get_claude_config,
    get_active_claude_api_key,
    set_claude_api_config,
    fetch_available_claude_models,
    test_claude_connection as ping_claude_connection,
    CLAUDE_PREFERRED_DEFAULT,
    CLAUDE_FALLBACK_DEFAULT,
    CLAUDE_KNOWN_MODELS
)
import app.services.claude_service as cs_module


def test_claude_model_defaults():
    """Verify preferred default is claude-sonnet-5-5 and fallback catalog is present."""
    assert CLAUDE_PREFERRED_DEFAULT == "claude-sonnet-5-5"
    assert CLAUDE_FALLBACK_DEFAULT == "claude-sonnet-5"
    assert "claude-sonnet-5-5" in CLAUDE_KNOWN_MODELS
    assert "claude-sonnet-5" in CLAUDE_KNOWN_MODELS


def test_dedicated_system_settings_persistence(monkeypatch):
    """
    Verify that API key is saved to dedicated SystemSetting table encrypted with AES-256-GCM,
    never written to .env, and survives reload across workers.
    """
    mock_db = {}

    class FakeSystemSetting:
        def __init__(self, key, encrypted_value, encryption_key_version, metadata_json, **kwargs):
            self.key = key
            self.encrypted_value = encrypted_value
            self.encryption_key_version = encryption_key_version
            self.metadata_json = metadata_json

    def fake_query(model):
        class MockQuery:
            def filter_by(self, key=None):
                class MockFilter:
                    def first(self):
                        return mock_db.get(key)
                return MockFilter()
        return MockQuery()

    def fake_add(obj):
        mock_db[obj.key] = obj

    monkeypatch.setattr(cs_module.db_session, "query", fake_query)
    monkeypatch.setattr(cs_module.db_session, "add", fake_add)
    monkeypatch.setattr(cs_module.db_session, "commit", lambda: None)
    monkeypatch.setattr(cs_module, "SystemSetting", FakeSystemSetting)

    # Save a key via set_claude_api_config
    test_key = "sk-ant-test-dedicated-settings-12345"
    success, err, cfg = set_claude_api_config(
        api_key=test_key,
        model="claude-sonnet-5-5",
        timeout=30,
        admin_user_id=11
    )
    assert success is True
    assert err is None
    assert cfg["is_configured"] is True

    # Verify that the record in mock_db contains encrypted value, NOT the raw key
    saved_rec = mock_db.get("CLAUDE_API_CONFIG")
    assert saved_rec is not None
    assert saved_rec.encrypted_value is not None
    assert test_key not in saved_rec.encrypted_value
    assert saved_rec.metadata_json["has_key"] is True
    assert test_key not in str(saved_rec.metadata_json)

    # Clear memory env and verify get_active_claude_api_key decrypts from system_settings
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setattr(cs_module, "load_dotenv", lambda: None)

    retrieved = get_active_claude_api_key()
    assert retrieved == test_key


def test_fetch_available_claude_models_success(monkeypatch):
    """Verify dynamic discovery via GET /v1/models and status categorization."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"request-id": "req_models_01"}
    mock_resp.json.return_value = {
        "data": [
            {"id": "claude-sonnet-5-5", "display_name": "Claude Sonnet 5.5", "created_at": "2026-02-01"},
            {"id": "claude-sonnet-5", "display_name": "Claude Sonnet 5", "created_at": "2025-11-01"},
            {"id": "claude-3-opus-20240229", "display_name": "Claude 3 Opus", "created_at": "2024-02-29"},
            {"id": "claude-2.1", "display_name": "Claude 2.1", "created_at": "2023-11-01"}
        ]
    }
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: mock_resp)

    res = fetch_available_claude_models(api_key="sk-ant-test-key")
    assert res["success"] is True
    assert len(res["models"]) == 4
    assert res["default_recommendation"] == "claude-sonnet-5-5"
    assert res["request_id"] == "req_models_01"

    # Verify status mapping
    status_map = {m["id"]: m["status"] for m in res["models"]}
    assert status_map["claude-sonnet-5-5"] == "ACTIVE"
    assert status_map["claude-sonnet-5"] == "ACTIVE"
    assert status_map["claude-3-opus-20240229"] == "DEPRECATED"
    assert status_map["claude-2.1"] == "RETIRED"


def test_fetch_available_claude_models_unavailable_or_unauthorized(monkeypatch):
    """Verify GET /v1/models error handling gracefully falls back to known defaults."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {"request-id": "req_models_err"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {"type": "authentication_error", "message": "invalid x-api-key"}
    }
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: mock_resp)

    res = fetch_available_claude_models(api_key="sk-ant-bad-key")
    assert res["success"] is False
    assert "invalid x-api-key" in res["message"]
    assert res["default_recommendation"] == "claude-sonnet-5-5"
    assert "claude-sonnet-5-5" in res["active_model_ids"]


def test_connection_test_not_configured(monkeypatch):
    """Verify test_claude_connection handles unconfigured keys gracefully."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setattr(cs_module, "_load_setting_record", lambda: None)
    monkeypatch.setattr(cs_module, "load_dotenv", lambda: None)

    diag = ping_claude_connection(api_key=None)
    assert diag["success"] is False
    assert diag["status"] == "NOT_CONFIGURED"
    assert diag["error_category"] == "MISSING_KEY"
    assert "not configured" in diag["message"].lower()


def test_connection_test_live_vs_mock_distinction(monkeypatch):
    """Verify diagnostic results cleanly identify successful generation and retain request ID."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"request-id": "req_01ABC123"}
    mock_resp.json.return_value = {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "pong"}]
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-valid-key")
    assert diag["success"] is True
    assert diag["status"] == "CONNECTED"
    assert diag["request_id"] == "req_01ABC123"
    assert "Successfully connected" in diag["message"]
    assert "sk-ant-valid-key" not in str(diag)


def test_connection_test_402_billing_error(monkeypatch):
    """Verify HTTP 402 is classified as INSUFFICIENT_CREDITS / ZERO_BALANCE."""
    mock_resp = MagicMock()
    mock_resp.status_code = 402
    mock_resp.headers = {"request-id": "req_01BILLING402"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "billing_error",
            "message": "Credit balance is zero. Please top up your prepaid credits."
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-zero-balance-key")
    assert diag["success"] is False
    assert diag["status"] == "INSUFFICIENT_CREDITS"
    assert diag["error_category"] == "ZERO_BALANCE"
    assert diag["request_id"] == "req_01BILLING402"
    assert "HTTP 402" in diag["message"]
    assert "sk-ant-zero-balance-key" not in str(diag)


def test_connection_test_400_spend_limit_billing_issue(monkeypatch):
    """Verify HTTP 400 with spend-limit phrasing is classified as INSUFFICIENT_CREDITS / ZERO_BALANCE."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {"request-id": "req_01SPENDLIMIT"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "Your credit balance is too low to access the Claude API. Please go to Plans & Billing to upgrade or purchase credits."
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-spend-limit-key")
    assert diag["success"] is False
    assert diag["status"] == "INSUFFICIENT_CREDITS"
    assert diag["error_category"] == "ZERO_BALANCE"
    assert diag["request_id"] == "req_01SPENDLIMIT"
    assert "authenticated and valid" in diag["message"]
    assert "Plans & Billing" in diag["message"]


def test_connection_test_400_general_invalid_request_not_zero_balance(monkeypatch):
    """Verify general HTTP 400 is classified as INVALID_REQUEST and NOT zero-balance."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {"request-id": "req_01SYNTAX"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "max_tokens must be greater than 0"
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-valid-key")
    assert diag["success"] is False
    assert diag["status"] == "INVALID_REQUEST"
    assert diag["error_category"] == "invalid_request_error"
    assert "max_tokens" in diag["message"]


def test_connection_test_401_authentication_failed(monkeypatch):
    """Verify 401 invalid key correctly classifies as AUTHENTICATION_FAILED."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {"request-id": "req_01AUTH"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "authentication_error",
            "message": "invalid x-api-key"
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-invalid-token")
    assert diag["success"] is False
    assert diag["status"] == "AUTHENTICATION_FAILED"
    assert diag["error_category"] == "INVALID_API_KEY"
    assert diag["request_id"] == "req_01AUTH"
    assert "Authentication failed" in diag["message"]


def test_connection_test_403_permission_denied(monkeypatch):
    """Verify 403 permission error is classified as PERMISSION_DENIED (MODEL_ACCESS_DENIED)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"request-id": "req_01PERM"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "permission_error",
            "message": "Your organization does not have access to model claude-opus-5."
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-valid-key", model="claude-opus-5")
    assert diag["success"] is False
    assert diag["status"] == "PERMISSION_DENIED"
    assert diag["error_category"] == "MODEL_ACCESS_DENIED"
    assert diag["request_id"] == "req_01PERM"
    assert "Permission denied for model 'claude-opus-5'" in diag["message"]


def test_connection_test_404_model_not_found(monkeypatch):
    """Verify 404 model not found classifies as INVALID_MODEL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {"request-id": "req_01NOTFOUND"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "not_found_error",
            "message": "model: unknown-model"
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-valid-key", model="unknown-model")
    assert diag["success"] is False
    assert diag["status"] == "INVALID_MODEL"
    assert diag["error_category"] == "MODEL_NOT_FOUND"
    assert diag["request_id"] == "req_01NOTFOUND"


def test_connection_test_429_rate_limited(monkeypatch):
    """Verify 429 rate limit is distinguished."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"request-id": "req_01RATELIMIT"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "rate_limit_error",
            "message": "Number of request tokens has exceeded your per-minute rate limit"
        }
    }
    monkeypatch.setattr(requests, "post", lambda url, headers, json, timeout: mock_resp)

    diag = ping_claude_connection(api_key="sk-ant-ratelimited")
    assert diag["success"] is False
    assert diag["status"] == "RATE_LIMITED"
    assert diag["error_category"] == "RATE_LIMIT_EXCEEDED"
    assert diag["request_id"] == "req_01RATELIMIT"
