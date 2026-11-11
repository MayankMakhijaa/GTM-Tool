"""
Service module for Claude (Anthropic) API integration, credential management,
model discovery, and connection diagnostics.

Strict Boundaries:
- Never hardcodes or logs API keys.
- Never prints decrypted secrets or sensitive tokens in exception traces.
- Uses AES-256-GCM from app.security.credential_vault for persistent encryption.
- Stores secrets in dedicated `system_settings` table (key='CLAUDE_API_CONFIG').
- Never uses audit_logs as primary secret storage (audit logs strictly record actor, action, timestamp, and safe metadata).
- Never writes secrets into repository `.env` from Superadmin.
- Dynamically retrieves live account models via Anthropic's `GET /v1/models` endpoint.
- Prefers `claude-sonnet-5-5` as default discovery candidate, gracefully falling back to known models.
- Accurately classifies authentication, zero-credit / billing errors (402 & 400 spend-limits),
  permission errors (403), invalid model (404/not_found), rate limits (429), and network errors.
- Retains original provider request ID.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
import requests
from dotenv import load_dotenv
from app.database import db_session
from app.models.all_models import SystemSetting
from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials

logger = logging.getLogger(__name__)

# Settings Key in system_settings table
SYSTEM_SETTING_CLAUDE_KEY = "CLAUDE_API_CONFIG"

# Baseline fallback model catalog
CLAUDE_PREFERRED_DEFAULT = "claude-sonnet-5-5"
CLAUDE_FALLBACK_DEFAULT = "claude-sonnet-5"
CLAUDE_KNOWN_MODELS = [
    "claude-sonnet-5-5",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-5"
]

CLAUDE_API_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_MODELS_URL = "https://api.anthropic.com/v1/models"
CLAUDE_API_VERSION = "2023-06-01"
CLAUDE_DEFAULT_TIMEOUT = 15  # seconds


def _load_setting_record() -> Optional[SystemSetting]:
    """Retrieves the Claude system setting record from system_settings table."""
    try:
        return db_session.query(SystemSetting).filter_by(key=SYSTEM_SETTING_CLAUDE_KEY).first()
    except Exception as e:
        logger.warning(f"[Claude Config] Error querying system_settings: {e}")
        return None


def get_active_claude_api_key() -> Optional[str]:
    """
    Returns the active raw Claude API key from:
    1. Dedicated encrypted system_settings record in PostgreSQL (decrypted on demand)
    2. Environment variable ANTHROPIC_API_KEY / CLAUDE_API_KEY
    Never logs or exposes the key in plaintext.
    """
    # 1. Check dedicated encrypted database record first
    rec = _load_setting_record()
    if rec and rec.encrypted_value:
        try:
            decrypted = decrypt_smtp_credentials(rec.encrypted_value, rec.encryption_key_version)
            key = decrypted.get("api_key")
            if key and str(key).strip():
                return str(key).strip()
        except Exception as e:
            logger.warning(f"[Claude Config] Failed to decrypt system setting API key: {e}")

    # 2. Check environment variable fallback
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if key and key.strip():
        return key.strip()

    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if key and key.strip():
        return key.strip()

    return None


def get_claude_config() -> Dict[str, Any]:
    """
    Retrieves current Claude configuration status without exposing raw secrets.
    Returns:
        {
            "is_configured": bool,
            "masked_key": Optional[str],
            "model": str,
            "supported_models": list[str],
            "timeout_seconds": int
        }
    """
    raw_key = get_active_claude_api_key()
    rec = _load_setting_record()
    meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}

    model = meta.get("model") or os.environ.get("CLAUDE_MODEL") or CLAUDE_PREFERRED_DEFAULT
    try:
        timeout_sec = int(meta.get("timeout_seconds") or os.environ.get("CLAUDE_API_TIMEOUT", CLAUDE_DEFAULT_TIMEOUT))
    except (ValueError, TypeError):
        timeout_sec = CLAUDE_DEFAULT_TIMEOUT

    masked = None
    if raw_key and len(raw_key) > 8:
        masked = f"{raw_key[:7]}...{raw_key[-4:]}"
    elif raw_key:
        masked = "***configured***"

    # Supported models list includes known models plus any discovered models stored in metadata
    supported_models = meta.get("available_models") or CLAUDE_KNOWN_MODELS

    return {
        "is_configured": bool(raw_key),
        "masked_key": masked,
        "model": model,
        "supported_models": supported_models,
        "timeout_seconds": timeout_sec
    }


def set_claude_api_config(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
    admin_user_id: Optional[int] = None
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Saves or updates Claude API configuration in the dedicated `system_settings` table.
    - Encrypts API key with AES-256-GCM via credential_vault.
    - Never writes secrets to repository `.env`.
    - Never puts secrets in audit_logs.
    - Syncs runtime process os.environ for immediate worker availability.
    Returns: (success: bool, error_msg: Optional[str], config_summary: Dict[str, Any])
    """
    cleaned_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
    cleaned_model = model.strip() if isinstance(model, str) and model.strip() else None

    # Load existing setting
    rec = _load_setting_record()
    existing_meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}

    effective_model = cleaned_model or existing_meta.get("model") or os.environ.get("CLAUDE_MODEL", CLAUDE_PREFERRED_DEFAULT)
    effective_timeout = timeout if (timeout and isinstance(timeout, int) and timeout > 0) else int(existing_meta.get("timeout_seconds") or os.environ.get("CLAUDE_API_TIMEOUT", CLAUDE_DEFAULT_TIMEOUT))
    effective_timeout = min(60, max(5, effective_timeout))

    # Determine key to persist
    key_to_save = cleaned_key or get_active_claude_api_key()

    encrypted_payload = rec.encrypted_value if rec else None
    key_ver = rec.encryption_key_version if rec else 1

    if cleaned_key:
        encrypted_payload, key_ver = encrypt_smtp_credentials({"api_key": cleaned_key})

    # Prepare updated metadata (strictly non-secret metadata)
    new_meta = dict(existing_meta)
    new_meta.update({
        "has_key": bool(key_to_save),
        "model": effective_model,
        "timeout_seconds": effective_timeout,
        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    })

    try:
        if not rec:
            rec = SystemSetting(
                key=SYSTEM_SETTING_CLAUDE_KEY,
                encrypted_value=encrypted_payload,
                encryption_key_version=key_ver,
                metadata_json=new_meta,
                is_secret=True,
                description="Anthropic Claude API configuration and encrypted credentials",
                updated_by_user_id=admin_user_id
            )
            db_session.add(rec)
        else:
            rec.encrypted_value = encrypted_payload
            rec.encryption_key_version = key_ver
            rec.metadata_json = new_meta
            rec.updated_by_user_id = admin_user_id
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"[Claude Config] Error saving to system_settings: {e}", exc_info=True)
        return False, f"Failed to persist configuration: {str(e)}", {}

    # Update current process os.environ for immediate worker availability
    if cleaned_key:
        os.environ["ANTHROPIC_API_KEY"] = cleaned_key
    os.environ["CLAUDE_MODEL"] = effective_model
    os.environ["CLAUDE_API_TIMEOUT"] = str(effective_timeout)

    return True, None, get_claude_config()


def fetch_available_claude_models(api_key: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Calls Anthropic's GET /v1/models endpoint to retrieve the list of models
    currently enabled and provisioned for this specific API key/account.
    Categorizes models into active, deprecated, and retired.
    Returns:
        {
            "success": bool,
            "models": list[dict], # [{id, display_name, created_at, status}]
            "active_model_ids": list[str],
            "default_recommendation": str,
            "message": Optional[str],
            "request_id": Optional[str]
        }
    """
    effective_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else get_active_claude_api_key()
    if not effective_key:
        return {
            "success": False,
            "models": [],
            "active_model_ids": CLAUDE_KNOWN_MODELS,
            "default_recommendation": CLAUDE_PREFERRED_DEFAULT,
            "message": "Claude API key not configured.",
            "request_id": None
        }

    headers = {
        "x-api-key": effective_key,
        "anthropic-version": CLAUDE_API_VERSION
    }

    try:
        response = requests.get(CLAUDE_API_MODELS_URL, headers=headers, timeout=timeout)
        req_id = response.headers.get("request-id")
        status_code = response.status_code
        try:
            body = response.json()
        except Exception:
            body = {}

        if status_code == 200 and isinstance(body.get("data"), list):
            discovered = []
            active_ids = []
            for item in body["data"]:
                m_id = item.get("id")
                if not m_id:
                    continue
                # Status categorization
                is_retired = any(ret in m_id.lower() for ret in ["claude-1", "claude-2", "claude-2.0", "claude-2.1"])
                is_deprecated = any(dep in m_id.lower() for dep in ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"])
                status = "RETIRED" if is_retired else ("DEPRECATED" if is_deprecated else "ACTIVE")

                discovered.append({
                    "id": m_id,
                    "display_name": item.get("display_name") or m_id,
                    "created_at": item.get("created_at"),
                    "status": status
                })
                if status == "ACTIVE":
                    active_ids.append(m_id)

            # Determine best default recommendation: prefer claude-sonnet-5-5, then claude-sonnet-5, then first active
            recommendation = CLAUDE_PREFERRED_DEFAULT
            if CLAUDE_PREFERRED_DEFAULT in active_ids:
                recommendation = CLAUDE_PREFERRED_DEFAULT
            elif CLAUDE_FALLBACK_DEFAULT in active_ids:
                recommendation = CLAUDE_FALLBACK_DEFAULT
            elif active_ids:
                recommendation = active_ids[0]

            # Cache discovered models in system_settings metadata
            rec = _load_setting_record()
            if rec and isinstance(rec.metadata_json, dict):
                rec.metadata_json["available_models"] = [d["id"] for d in discovered]
                try:
                    db_session.commit()
                except Exception:
                    db_session.rollback()

            return {
                "success": True,
                "models": discovered,
                "active_model_ids": active_ids or [d["id"] for d in discovered],
                "default_recommendation": recommendation,
                "message": f"Successfully retrieved {len(discovered)} models from Anthropic account.",
                "request_id": req_id
            }

        # Handle errors
        err_data = body.get("error") if isinstance(body.get("error"), dict) else {}
        err_msg = err_data.get("message") or f"HTTP {status_code}"
        return {
            "success": False,
            "models": [],
            "active_model_ids": CLAUDE_KNOWN_MODELS,
            "default_recommendation": CLAUDE_PREFERRED_DEFAULT,
            "message": f"Unable to fetch models from Anthropic: {err_msg}",
            "request_id": req_id
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "models": [],
            "active_model_ids": CLAUDE_KNOWN_MODELS,
            "default_recommendation": CLAUDE_PREFERRED_DEFAULT,
            "message": f"Network transport error connecting to Anthropic /v1/models: {str(e)}",
            "request_id": None
        }


def test_claude_connection(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Executes a minimal test request against the Claude Messages API.
    Identifies:
    1. HTTP 200: Successful generation (healthy connection, positive balance)
    2. HTTP 402 or billing_error: Zero balance / credit depletion
    3. HTTP 400 with spend-limit message: Insufficient balance / credit cap
    4. HTTP 401 / authentication_error: Invalid API key
    5. HTTP 403 / permission_error: Model permission / account access denied
    6. HTTP 404 / not_found_error: Model ID invalid or unavailable
    7. HTTP 429 / rate_limit_error: Rate limit or concurrency limit exceeded
    8. Network / timeout error
    9. HTTP 500 / 529: Provider server / overload error

    Retains the Anthropic request_id for tracking without exposing secrets.
    """
    effective_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else get_active_claude_api_key()
    effective_model = model.strip() if isinstance(model, str) and model.strip() else os.environ.get("CLAUDE_MODEL", CLAUDE_PREFERRED_DEFAULT)
    
    try:
        effective_timeout = int(timeout) if timeout else int(os.environ.get("CLAUDE_API_TIMEOUT", CLAUDE_DEFAULT_TIMEOUT))
    except (ValueError, TypeError):
        effective_timeout = CLAUDE_DEFAULT_TIMEOUT

    tested_at_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    if not effective_key:
        return {
            "success": False,
            "status": "NOT_CONFIGURED",
            "error_category": "MISSING_KEY",
            "message": "Claude API key is not configured. Please supply a valid Anthropic API key.",
            "model_used": effective_model,
            "latency_ms": 0,
            "request_id": None,
            "tested_at": tested_at_iso
        }

    headers = {
        "x-api-key": effective_key,
        "anthropic-version": CLAUDE_API_VERSION,
        "content-type": "application/json"
    }

    payload = {
        "model": effective_model,
        "max_tokens": 1,
        "messages": [
            {"role": "user", "content": "ping"}
        ]
    }

    start_time = time.monotonic()
    try:
        response = requests.post(
            CLAUDE_API_MESSAGES_URL,
            headers=headers,
            json=payload,
            timeout=effective_timeout
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)
    except requests.exceptions.Timeout:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "success": False,
            "status": "NETWORK_ERROR",
            "error_category": "TIMEOUT",
            "message": f"Connection timed out after {effective_timeout}s while contacting Anthropic API.",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": None,
            "tested_at": tested_at_iso
        }
    except requests.exceptions.RequestException as req_err:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "success": False,
            "status": "NETWORK_ERROR",
            "error_category": "CONNECTION_FAILED",
            "message": f"Network transport error while reaching Anthropic API: {type(req_err).__name__}",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": None,
            "tested_at": tested_at_iso
        }

    # Extract response body and provider request_id
    status_code = response.status_code
    provider_req_id = response.headers.get("request-id")
    try:
        body = response.json()
    except Exception:
        body = {}

    if not provider_req_id and isinstance(body, dict):
        provider_req_id = body.get("request_id")

    err_data = body.get("error") if isinstance(body.get("error"), dict) else {}
    err_type = str(err_data.get("type") or "").strip().lower()
    err_message = str(err_data.get("message") or "").strip()

    # Case 1: HTTP 200 OK
    if status_code == 200:
        return {
            "success": True,
            "status": "CONNECTED",
            "error_category": None,
            "message": f"Successfully connected to Claude API ({effective_model}). Generation verified.",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 2: HTTP 402 Billing Error / Zero Balance
    if status_code == 402 or err_type == "billing_error":
        return {
            "success": False,
            "status": "INSUFFICIENT_CREDITS",
            "error_category": "ZERO_BALANCE",
            "message": (
                "Claude API key is authenticated and valid, but account has a billing issue or zero balance (HTTP 402). "
                f"Provider message: '{err_message or 'Credit balance too low'}'. Top up credits at console.anthropic.com."
            ),
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 3: HTTP 400 Spend-limit or credit-balance exceptions
    is_400_billing_issue = (
        status_code == 400 and (
            "credit balance" in err_message.lower()
            or "plans & billing" in err_message.lower()
            or "purchase credits" in err_message.lower()
            or "balance is too low" in err_message.lower()
            or "insufficient credits" in err_message.lower()
            or "spend limit" in err_message.lower()
        )
    )
    if is_400_billing_issue:
        return {
            "success": False,
            "status": "INSUFFICIENT_CREDITS",
            "error_category": "ZERO_BALANCE",
            "message": (
                "Claude API key is authenticated and valid, but has zero balance / insufficient credits. "
                f"Provider message: '{err_message}'. Top up credits at console.anthropic.com to enable generations."
            ),
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 4: HTTP 401 Unauthorized / Authentication Error
    if status_code == 401 or err_type == "authentication_error":
        return {
            "success": False,
            "status": "AUTHENTICATION_FAILED",
            "error_category": "INVALID_API_KEY",
            "message": f"Authentication failed: The provided API key is invalid or unrecognized by Anthropic ({err_message or 'invalid x-api-key'}).",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 5: HTTP 403 Permission Error / Model Access Denied
    if status_code == 403 or err_type == "permission_error":
        return {
            "success": False,
            "status": "PERMISSION_DENIED",
            "error_category": "MODEL_ACCESS_DENIED",
            "message": (
                f"Permission denied for model '{effective_model}' (HTTP 403). Your API key does not have permission "
                f"to access this model or feature: {err_message or 'Forbidden'}"
            ),
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 6: HTTP 404 Model Not Found / Resource Not Found
    if status_code == 404 or "not_found_error" in err_type or ("model" in err_message.lower() and "not found" in err_message.lower()):
        return {
            "success": False,
            "status": "INVALID_MODEL",
            "error_category": "MODEL_NOT_FOUND",
            "message": f"Claude model '{effective_model}' was not found or is unavailable (HTTP 404): {err_message}",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 7: Rate limit (HTTP 429)
    if status_code == 429 or err_type == "rate_limit_error":
        return {
            "success": False,
            "status": "RATE_LIMITED",
            "error_category": "RATE_LIMIT_EXCEEDED",
            "message": f"Claude API rate limit or concurrency cap reached (HTTP 429): {err_message or 'Too many requests'}. Retry after delay.",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 8: Server Overloaded / Upstream Error (500, 502, 503, 504, 529)
    if status_code in (500, 502, 503, 504, 529) or err_type in ("overloaded_error", "api_error"):
        return {
            "success": False,
            "status": "SERVER_ERROR",
            "error_category": "PROVIDER_OVERLOADED",
            "message": f"Anthropic upstream server error (HTTP {status_code}): {err_message or 'Provider temporarily overloaded'}",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 9: General 400 Invalid Request (Non-billing)
    if status_code == 400:
        return {
            "success": False,
            "status": "INVALID_REQUEST",
            "error_category": err_type or "INVALID_REQUEST_ERROR",
            "message": f"Anthropic rejected request (HTTP 400): {err_message or 'Invalid request syntax or parameter.'}",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": provider_req_id,
            "tested_at": tested_at_iso
        }

    # Case 10: Generic unclassified error
    return {
        "success": False,
        "status": f"HTTP_{status_code}",
        "error_category": err_type or "UNKNOWN_ERROR",
        "message": f"Claude API returned HTTP {status_code}: {err_message or 'Unexpected response from Anthropic.'}",
        "model_used": effective_model,
        "latency_ms": latency_ms,
        "request_id": provider_req_id,
        "tested_at": tested_at_iso
    }


def _classify_claude_response(response: requests.Response, latency_ms: int, effective_model: str) -> Dict[str, Any]:
    """Helper to classify Claude API responses into standardized diagnostic outcomes."""
    status_code = response.status_code
    provider_req_id = response.headers.get("request-id")
    try:
        body = response.json()
    except Exception:
        body = {}

    if not provider_req_id and isinstance(body, dict):
        provider_req_id = body.get("request_id")

    err_data = body.get("error") if isinstance(body.get("error"), dict) else {}
    err_type = str(err_data.get("type") or "").strip().lower()
    err_message = str(err_data.get("message") or "").strip()

    if status_code == 200:
        return {
            "success": True,
            "status": "SUCCESS",
            "error_category": None,
            "message": "Claude call successful.",
            "request_id": provider_req_id
        }

    # Billing / Zero balance (402 or 400 credit balance message)
    if status_code == 402 or err_type == "billing_error":
        return {
            "success": False,
            "status": "INSUFFICIENT_CREDITS",
            "error_category": "ZERO_BALANCE",
            "message": f"Claude billing error (HTTP 402): {err_message or 'Credit balance too low'}.",
            "request_id": provider_req_id
        }

    if status_code == 400 and ("credit balance" in err_message.lower() or "plans & billing" in err_message.lower() or "purchase credits" in err_message.lower() or "spend limit" in err_message.lower()):
        return {
            "success": False,
            "status": "INSUFFICIENT_CREDITS",
            "error_category": "CREDIT_BALANCE_EXHAUSTED",
            "message": f"Anthropic credit limit reached (HTTP 400): {err_message}",
            "request_id": provider_req_id
        }

    # Auth error (401)
    if status_code == 401 or err_type == "authentication_error":
        return {
            "success": False,
            "status": "AUTHENTICATION_FAILED",
            "error_category": "INVALID_API_KEY",
            "message": f"Claude API authentication failed (HTTP 401): {err_message or 'Invalid API key.'}",
            "request_id": provider_req_id
        }

    # Permission (403)
    if status_code == 403 or err_type == "permission_error":
        return {
            "success": False,
            "status": "PERMISSION_DENIED",
            "error_category": "FORBIDDEN",
            "message": f"Claude API access denied (HTTP 403): {err_message or 'API key lacks permission.'}",
            "request_id": provider_req_id
        }

    # Model not found (404)
    if status_code == 404 or "not_found" in err_type:
        return {
            "success": False,
            "status": "INVALID_MODEL",
            "error_category": "MODEL_NOT_FOUND",
            "message": f"Claude model '{effective_model}' not found (HTTP 404): {err_message}",
            "request_id": provider_req_id
        }

    # Rate limit (429)
    if status_code == 429 or err_type == "rate_limit_error":
        return {
            "success": False,
            "status": "RATE_LIMITED",
            "error_category": "RATE_LIMIT_EXCEEDED",
            "message": f"Claude rate limit exceeded (HTTP 429): {err_message}",
            "request_id": provider_req_id
        }

    # Upstream server error (500, 502, 503, 504, 529)
    if status_code in (500, 502, 503, 504, 529):
        return {
            "success": False,
            "status": "SERVER_ERROR",
            "error_category": "PROVIDER_OVERLOADED",
            "message": f"Anthropic upstream server error (HTTP {status_code}): {err_message}",
            "request_id": provider_req_id
        }

    return {
        "success": False,
        "status": f"HTTP_{status_code}",
        "error_category": err_type or "UNKNOWN_ERROR",
        "message": f"Claude API error (HTTP {status_code}): {err_message}",
        "request_id": provider_req_id
    }


def discover_candidates_with_claude(
    structured_icp: Dict[str, Any],
    user_company: Dict[str, Any],
    count_needed: int = 10,
    user_id: Optional[int] = None,
    job_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Leverages Claude's analytical and discovery capabilities to search for and identify
    grounded candidate leads that strictly match the given ICP and target criteria.

    Strict Requirements:
    - Never hallucinates contact details (email/phone must remain empty/null).
    - Returns structured candidate objects with full_name, job_title, company_name, location,
      source_url, and source_evidence.
    - Accurately captures errors (e.g. INSUFFICIENT_CREDITS, RATE_LIMITED) without crashing.
    - Records telemetry into AIProviderUsageLog.
    """
    raw_api_key = get_active_claude_api_key()
    if not raw_api_key:
        return {
            "success": False,
            "status": "NOT_CONFIGURED",
            "message": "Claude API key is not configured.",
            "candidates": []
        }

    config = get_claude_config()
    model = config.get("model") or CLAUDE_PREFERRED_DEFAULT
    correlation_id = f"claude_disc_{uuid.uuid4().hex[:12]}" if "uuid" in globals() else f"claude_disc_{int(time.time())}"

    # Prepare structured prompt
    roles = structured_icp.get("keyword_title") or structured_icp.get("target_jobs_roles") or "Leadership / Decision Maker"
    industries = structured_icp.get("target_industries") or [structured_icp.get("industry") or "Technology"]
    exclusions = structured_icp.get("exclusions") or []
    locations = structured_icp.get("location") or "United States, North America, Global"

    system_prompt = (
        "You are an expert B2B lead generation researcher. Your mission is to identify real, verifiable executive and "
        "decision-maker candidates strictly matching the requested Ideal Customer Profile (ICP). "
        "IMPORTANT RULES:\n"
        "1. Ground every candidate in reality with a verifiable professional web source URL (e.g. corporate leadership page, company press release, or professional profile URL).\n"
        "2. Provide an authentic source_evidence quote substantiating their current role and organization.\n"
        "3. NEVER fabricate or guess contact information like personal emails or direct telephone numbers.\n"
        "4. Respond ONLY with a valid JSON array of objects without conversational markdown or text."
    )

    user_prompt = f"""
Find up to {count_needed} high-relevance professional leads matching these criteria:
Target Roles: {roles}
Target Industries: {industries}
Target Geography: {locations}
Exclusions / Negative criteria: {exclusions}
User's Business / Offer context: {user_company.get('offer', 'B2B Solutions')} (Company: {user_company.get('company_name', 'B2B Provider')})

For each candidate, output a JSON object with:
- "full_name": string
- "job_title": string
- "company_name": string
- "location": string
- "industry": string
- "source_url": string (Valid HTTP or HTTPS link to company leadership page, blog, news, or public professional profile)
- "source_title": string (Page title or publication name)
- "source_evidence": string (Specific quote or excerpt confirming their role at this company)

Output Format:
[
  {{
    "full_name": "Jane Doe",
    "job_title": "VP of Sales",
    "company_name": "Acme SaaS",
    "location": "San Francisco, CA",
    "industry": "Software",
    "source_url": "https://example.com/team/jane-doe",
    "source_title": "Acme Leadership Team",
    "source_evidence": "Jane Doe serves as Vice President of Global Sales at Acme SaaS leading enterprise expansion."
  }}
]
"""

    headers = {
        "x-api-key": raw_api_key,
        "anthropic-version": CLAUDE_API_VERSION,
        "content-type": "application/json"
    }

    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    }

    start_time = time.monotonic()
    status_str = "FAILED"
    candidates = []
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    error_cat = None
    res_msg = ""

    try:
        resp = requests.post(
            CLAUDE_API_MESSAGES_URL,
            headers=headers,
            json=payload,
            timeout=config.get("timeout_seconds") or 30
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Classify status using existing diagnostic logic
        diag = _classify_claude_response(resp, latency_ms, model)
        if not diag["success"]:
            error_cat = diag.get("error_category")
            res_msg = diag.get("message", "Discovery failed")
            logger.warning(f"[Claude Discovery] Provider call failed: {diag['status']} - {res_msg}")
            return {
                "success": False,
                "status": diag["status"],
                "error_category": error_cat,
                "message": res_msg,
                "candidates": []
            }

        # Successful response
        status_str = "SUCCESS"
        data = resp.json()
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

        content_list = data.get("content") or []
        raw_text = "".join(item.get("text", "") for item in content_list if item.get("type") == "text").strip()

        # Clean JSON markdown blocks if present
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        try:
            import json
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                candidates = parsed
            elif isinstance(parsed, dict) and "candidates" in parsed:
                candidates = parsed["candidates"]
        except Exception as e_json:
            logger.warning(f"[Claude Discovery] Failed to parse candidate JSON response: {e_json} - raw: {raw_text[:200]}")
            candidates = []

        return {
            "success": True,
            "status": "SUCCESS",
            "candidates": candidates,
            "count": len(candidates),
            "model_used": model,
            "latency_ms": latency_ms
        }

    except requests.exceptions.Timeout:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_cat = "TIMEOUT"
        res_msg = "Claude request timed out."
        return {
            "success": False,
            "status": "NETWORK_TIMEOUT",
            "error_category": error_cat,
            "message": res_msg,
            "candidates": []
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_cat = "EXCEPTION"
        res_msg = str(e)
        return {
            "success": False,
            "status": "ERROR",
            "error_category": error_cat,
            "message": res_msg,
            "candidates": []
        }
    finally:
        # Telemetry logging to AIProviderUsageLog
        if user_id:
            try:
                from app.models.all_models import AIProviderUsageLog
                from decimal import Decimal
                # Rough estimate for Claude Sonnet (~$3/1M in, $15/1M out)
                est_cost = None
                if prompt_tokens or completion_tokens:
                    p_cost = (Decimal(prompt_tokens or 0) / Decimal(1000000)) * Decimal("3.00")
                    c_cost = (Decimal(completion_tokens or 0) / Decimal(1000000)) * Decimal("15.00")
                    est_cost = (p_cost + c_cost).quantize(Decimal("0.000001"))

                log_entry = AIProviderUsageLog(
                    user_id=user_id,
                    job_id=job_id,
                    correlation_id=correlation_id if isinstance(correlation_id, str) else "claude_disc",
                    provider="CLAUDE",
                    model_name=model,
                    operation="CANDIDATE_DISCOVERY",
                    status=status_str,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    duration_ms=latency_ms,
                    estimated_cost_usd=est_cost,
                    error_category=error_cat
                )
                db_session.add(log_entry)
                db_session.commit()
            except Exception as e_log:
                logger.warning(f"[Claude Telemetry] Failed to record AI usage log: {e_log}")
                db_session.rollback()

