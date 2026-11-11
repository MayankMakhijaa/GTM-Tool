"""
Service module for Google Gemini API integration, credential management,
model discovery, and connection diagnostics.

Strict Boundaries:
- Never hardcodes or logs API keys.
- Never prints decrypted secrets or sensitive tokens in exception traces.
- Uses AES-256-GCM from app.security.credential_vault for persistent encryption.
- Stores secrets in dedicated `system_settings` table (key='GEMINI_API_CONFIG').
- Never uses audit_logs as primary secret storage (audit logs strictly record actor, action, timestamp, and safe metadata).
- Never writes secrets into repository `.env` from Superadmin.
- Dynamically retrieves live account models via Google GenAI SDK's `client.models.list()`.
- Supports default fallback models: `gemini-2.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.8-flash`.
- Accurately classifies authentication (400/403 API_KEY_INVALID), quota exhaustion (RESOURCE_EXHAUSTED / 429),
  permission errors (PERMISSION_DENIED), model not found (NOT_FOUND / 404), and network errors.
- Never exposes API keys through API responses, templates, or client-side assets.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from dotenv import load_dotenv

from google import genai
from google.genai import types, errors

from app.database import db_session
from app.models.all_models import SystemSetting
from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials

logger = logging.getLogger(__name__)

# Settings Key in system_settings table
SYSTEM_SETTING_GEMINI_KEY = "GEMINI_API_CONFIG"

# Baseline fallback model catalog
GEMINI_PREFERRED_DEFAULT = "gemini-2.5-flash"
GEMINI_KNOWN_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-pro"
]

GEMINI_DEFAULT_TIMEOUT = 15  # seconds


def _load_gemini_setting_record() -> Optional[SystemSetting]:
    """Retrieves the Gemini system setting record from system_settings table."""
    try:
        return db_session.query(SystemSetting).filter_by(key=SYSTEM_SETTING_GEMINI_KEY).first()
    except Exception as e:
        logger.warning(f"[Gemini Config] Error querying system_settings: {e}")
        return None


def get_active_gemini_api_key() -> Optional[str]:
    """
    Returns the active raw Gemini API key from:
    1. Dedicated encrypted system_settings record in PostgreSQL (decrypted on demand in memory).
    2. Environment variable GEMINI_API_KEY.
    Never logs or exposes the key in plaintext.
    """
    # 1. Check dedicated encrypted database record first
    rec = _load_gemini_setting_record()
    if rec and rec.encrypted_value:
        try:
            decrypted = decrypt_smtp_credentials(rec.encrypted_value, rec.encryption_key_version)
            key = decrypted.get("api_key")
            if key and str(key).strip():
                return str(key).strip()
        except Exception as e:
            logger.warning(f"[Gemini Config] Failed to decrypt system setting API key: {e}")

    # 2. Check environment variable fallback
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()

    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()

    return None


def get_gemini_config() -> Dict[str, Any]:
    """
    Retrieves current Gemini configuration status without exposing raw secrets.
    Returns:
        {
            "is_configured": bool,
            "masked_key": Optional[str],
            "model": str,
            "supported_models": list[str],
            "timeout_seconds": int
        }
    """
    raw_key = get_active_gemini_api_key()
    rec = _load_gemini_setting_record()
    meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}

    model = meta.get("model") or os.environ.get("GEMINI_MODEL") or GEMINI_PREFERRED_DEFAULT
    try:
        timeout_sec = int(meta.get("timeout_seconds") or os.environ.get("GEMINI_API_TIMEOUT", GEMINI_DEFAULT_TIMEOUT))
    except (ValueError, TypeError):
        timeout_sec = GEMINI_DEFAULT_TIMEOUT

    masked = None
    if raw_key and len(raw_key) > 8:
        masked = f"{raw_key[:6]}...{raw_key[-4:]}"
    elif raw_key:
        masked = "***configured***"

    supported_models = meta.get("available_models") or GEMINI_KNOWN_MODELS

    return {
        "is_configured": bool(raw_key),
        "masked_key": masked,
        "model": model,
        "supported_models": supported_models,
        "timeout_seconds": timeout_sec
    }


def set_gemini_api_config(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
    admin_user_id: Optional[int] = None
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Saves or updates Gemini API configuration in the dedicated `system_settings` table.
    - Encrypts API key with AES-256-GCM via credential_vault.
    - Never writes secrets to repository `.env`.
    - Never puts secrets in audit_logs.
    - Syncs runtime process os.environ for immediate worker availability.
    Returns: (success: bool, error_msg: Optional[str], config_summary: Dict[str, Any])
    """
    cleaned_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
    cleaned_model = model.strip() if isinstance(model, str) and model.strip() else None

    # Load existing setting
    rec = _load_gemini_setting_record()
    existing_meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}

    effective_model = cleaned_model or existing_meta.get("model") or os.environ.get("GEMINI_MODEL", GEMINI_PREFERRED_DEFAULT)
    effective_timeout = timeout if (timeout and isinstance(timeout, int) and timeout > 0) else int(existing_meta.get("timeout_seconds") or os.environ.get("GEMINI_API_TIMEOUT", GEMINI_DEFAULT_TIMEOUT))
    effective_timeout = min(60, max(5, effective_timeout))

    # Determine key to persist
    key_to_save = cleaned_key or get_active_gemini_api_key()

    encrypted_payload = rec.encrypted_value if rec else None
    key_ver = rec.encryption_key_version if rec else 1

    if cleaned_key:
        try:
            encrypted_payload, key_ver = encrypt_smtp_credentials({"api_key": cleaned_key})
        except Exception as e:
            logger.error(f"[Gemini Config] AES-256-GCM encryption failed: {e}")
            return False, f"Failed to securely encrypt API key: {str(e)}", {}

    # Build sanitized metadata dictionary (zero secrets)
    updated_meta = {
        **existing_meta,
        "model": effective_model,
        "timeout_seconds": effective_timeout,
        "is_configured": bool(key_to_save),
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by_user_id": admin_user_id
    }

    try:
        if not rec:
            rec = SystemSetting(
                key=SYSTEM_SETTING_GEMINI_KEY,
                encrypted_value=encrypted_payload,
                encryption_key_version=key_ver,
                metadata_json=updated_meta,
                description="Google Gemini API Configuration (Superadmin-managed)"
            )
            db_session.add(rec)
        else:
            if cleaned_key:
                rec.encrypted_value = encrypted_payload
                rec.encryption_key_version = key_ver
            rec.metadata_json = updated_meta
            rec.updated_at = datetime.utcnow()

        db_session.commit()

        # Sync runtime os.environ for immediate worker use without writing to .env disk file
        if key_to_save:
            os.environ["GEMINI_API_KEY"] = key_to_save
        os.environ["GEMINI_MODEL"] = effective_model
        os.environ["GEMINI_API_TIMEOUT"] = str(effective_timeout)

        # Return sanitized summary
        masked = None
        if key_to_save and len(key_to_save) > 8:
            masked = f"{key_to_save[:6]}...{key_to_save[-4:]}"
        elif key_to_save:
            masked = "***configured***"

        return True, None, {
            "is_configured": bool(key_to_save),
            "masked_key": masked,
            "model": effective_model,
            "supported_models": updated_meta.get("available_models") or GEMINI_KNOWN_MODELS,
            "timeout_seconds": effective_timeout
        }
    except Exception as e:
        db_session.rollback()
        logger.error(f"[Gemini Config] Failed to commit Gemini config to system_settings: {e}")
        return False, f"Database persistence failure: {str(e)}", {}


def fetch_available_gemini_models(api_key: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Queries Google GenAI SDK's `client.models.list()` to discover available Gemini models
    for the configured or supplied API key.
    Persists discovered models list into metadata_json of the system_settings record.
    Returns:
        {
            "success": bool,
            "active_model": str,
            "models": list[str],
            "total_count": int,
            "error": Optional[str]
        }
    """
    key = api_key or get_active_gemini_api_key()
    if not key:
        return {
            "success": False,
            "active_model": GEMINI_PREFERRED_DEFAULT,
            "models": GEMINI_KNOWN_MODELS,
            "total_count": 0,
            "error": "Gemini API key is not configured."
        }

    try:
        client = genai.Client(api_key=key)
        discovered_models: List[str] = []

        # List models using official GenAI SDK
        pager = client.models.list()
        for m in pager:
            name = getattr(m, "name", None) or ""
            # Strip models/ prefix if present (e.g. models/gemini-2.5-flash -> gemini-2.5-flash)
            clean_name = name.split("/")[-1] if "/" in name else name
            if "gemini" in clean_name.lower():
                discovered_models.append(clean_name)

        if not discovered_models:
            discovered_models = list(GEMINI_KNOWN_MODELS)

        # Ensure known models are represented if appropriate
        merged_catalog = []
        for m in discovered_models:
            if m not in merged_catalog:
                merged_catalog.append(m)

        # Check existing preferred selection
        rec = _load_gemini_setting_record()
        current_meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}
        selected_model = current_meta.get("model") or os.environ.get("GEMINI_MODEL") or GEMINI_PREFERRED_DEFAULT

        # If current selected_model is not in merged_catalog, keep or add it
        if selected_model not in merged_catalog:
            merged_catalog.insert(0, selected_model)

        # Persist discovered models into system_settings metadata
        if rec:
            try:
                updated_meta = {
                    **current_meta,
                    "available_models": merged_catalog,
                    "models_discovered_at": datetime.utcnow().isoformat()
                }
                rec.metadata_json = updated_meta
                db_session.commit()
            except Exception as e_save:
                logger.warning(f"[Gemini Models] Failed to cache models into system_settings: {e_save}")
                db_session.rollback()

        return {
            "success": True,
            "active_model": selected_model,
            "models": merged_catalog,
            "total_count": len(merged_catalog),
            "error": None
        }

    except Exception as e:
        err_msg = str(e)
        logger.warning(f"[Gemini Models] Failed to query Gemini models: {err_msg}")
        return {
            "success": False,
            "active_model": GEMINI_PREFERRED_DEFAULT,
            "models": GEMINI_KNOWN_MODELS,
            "total_count": len(GEMINI_KNOWN_MODELS),
            "error": f"Failed to discover models from Google API: {err_msg}"
        }


def test_gemini_connection(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = GEMINI_DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Executes a real minimal network diagnostic ping against the Google Gemini API.
    A minimal prompt 'ping' with max_output_tokens=1 is sent using the GenAI SDK.
    Accurately classifies outcomes into:
    - LIVE_CONNECTION_SUCCESS
    - INSUFFICIENT_CREDITS / QUOTA_EXCEEDED
    - AUTHENTICATION_FAILED
    - MODEL_ACCESS_DENIED
    - INVALID_MODEL
    - RATE_LIMITED
    - NOT_CONFIGURED
    - PROVIDER_ERROR
    Never exposes raw API keys in response or logs.
    """
    effective_key = api_key or get_active_gemini_api_key()
    tested_at_iso = datetime.utcnow().isoformat()

    if not effective_key:
        return {
            "success": False,
            "status": "NOT_CONFIGURED",
            "error_category": "MISSING_API_KEY",
            "message": "Gemini API key is not configured. Please supply an API key in Superadmin.",
            "model_used": model or GEMINI_PREFERRED_DEFAULT,
            "latency_ms": 0,
            "request_id": None,
            "tested_at": tested_at_iso
        }

    rec = _load_gemini_setting_record()
    meta = rec.metadata_json if (rec and isinstance(rec.metadata_json, dict)) else {}
    effective_model = model or meta.get("model") or os.environ.get("GEMINI_MODEL") or GEMINI_PREFERRED_DEFAULT

    start_time = time.monotonic()

    try:
        client = genai.Client(api_key=effective_key)
        # Smallest suitable diagnostic request: disable automatic function calling to prevent SDK warnings
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )

        resp = client.models.generate_content(
            model=effective_model,
            contents="ping",
            config=config
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Successful call
        result = {
            "success": True,
            "status": "LIVE_CONNECTION_SUCCESS",
            "error_category": None,
            "message": f"Successfully connected to Gemini API ({effective_model}). Generation verified.",
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": None,
            "tested_at": tested_at_iso
        }

        # Cache last diagnostic result in system_settings
        if rec:
            try:
                rec.metadata_json = {
                    **meta,
                    "last_diagnostic": result,
                    "last_successful_connection": tested_at_iso
                }
                db_session.commit()
            except Exception as e_db:
                logger.warning(f"[Gemini Diagnostic] Error saving last diagnostic: {e_db}")
                db_session.rollback()

        return result

    except errors.APIError as api_err:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        code = getattr(api_err, "code", None)
        err_msg = str(getattr(api_err, "message", None) or api_err)
        err_lower = err_msg.lower()

        logger.warning(f"[Gemini Diagnostic] APIError encountered: code={code}, msg={err_msg}")

        # Classify errors accurately
        # 1. Temporary provider unavailability / overload (503 / 500 / 504 / high demand)
        if code in (503, 502, 504) or "high demand" in err_lower or "temporarily unavailable" in err_lower or "service unavailable" in err_lower:
            status = "PROVIDER_UNAVAILABLE"
            cat = "TEMPORARY_OVERLOAD"
            user_msg = f"Google Gemini is temporarily experiencing high demand (HTTP {code}): {err_msg}. Please retry shortly."
        # 2. Authentication failure (invalid API key)
        elif (code in (400, 401, 403) and ("api_key_invalid" in err_lower or "api key not valid" in err_lower or "invalid api key" in err_lower or "unauthenticated" in err_lower)) or "api_key_invalid" in err_lower or "api key not valid" in err_lower or "invalid api key" in err_lower:
            status = "AUTHENTICATION_FAILED"
            cat = "INVALID_API_KEY"
            user_msg = f"Gemini API authentication failed (HTTP {code}): {err_msg}"
        # 3. Model access restricted / permission denied
        elif code == 403 or "permission_denied" in err_lower:
            status = "MODEL_ACCESS_DENIED"
            cat = "PERMISSION_DENIED"
            user_msg = f"Gemini model access restricted (HTTP 403): {err_msg}"
        # 4. Quota exhausted or rate limited (429)
        elif code == 429 or "resource_exhausted" in err_lower:
            if "quota" in err_lower:
                status = "QUOTA_EXCEEDED"
                cat = "QUOTA_EXCEEDED"
                user_msg = f"Gemini API quota exhausted (HTTP 429): {err_msg}"
            else:
                status = "RATE_LIMITED"
                cat = "RATE_LIMIT_EXCEEDED"
                user_msg = f"Gemini API concurrency or rate limit reached (HTTP 429): {err_msg}"
        # 5. Invalid / unrecognized model (404)
        elif code == 404 or "not found" in err_lower:
            status = "INVALID_MODEL"
            cat = "MODEL_NOT_FOUND"
            user_msg = f"Gemini model '{effective_model}' not found or unavailable (HTTP 404): {err_msg}"
        # 6. General API error
        else:
            status = "PROVIDER_ERROR"
            cat = f"HTTP_{code}" if code else "API_ERROR"
            user_msg = f"Gemini API returned error (HTTP {code}): {err_msg}"

        result = {
            "success": False,
            "status": status,
            "error_category": cat,
            "message": user_msg,
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": None,
            "tested_at": tested_at_iso
        }

        if rec:
            try:
                rec.metadata_json = {
                    **meta,
                    "last_diagnostic": result
                }
                db_session.commit()
            except Exception:
                db_session.rollback()

        return result

    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        err_msg = str(exc)
        err_lower = err_msg.lower()

        logger.warning(f"[Gemini Diagnostic] General error: {err_msg}")

        if "503" in err_lower or "high demand" in err_lower or "unavailable" in err_lower:
            status = "PROVIDER_UNAVAILABLE"
            cat = "TEMPORARY_OVERLOAD"
            user_msg = f"Google Gemini is temporarily experiencing high demand: {err_msg}. Please retry shortly."
        elif "timeout" in err_lower:
            status = "NETWORK_ERROR"
            cat = "TIMEOUT"
            user_msg = f"Gemini connection timed out: {err_msg}"
        elif "api_key" in err_lower or "api key" in err_lower:
            status = "AUTHENTICATION_FAILED"
            cat = "INVALID_API_KEY"
            user_msg = f"Gemini API key error: {err_msg}"
        elif "quota" in err_lower or "429" in err_lower or "resource_exhausted" in err_lower:
            status = "QUOTA_EXCEEDED"
            cat = "RATE_OR_QUOTA_EXHAUSTED"
            user_msg = f"Gemini quota exhausted: {err_msg}"
        else:
            status = "PROVIDER_ERROR"
            cat = "EXCEPTION"
            user_msg = f"Gemini diagnostic exception: {err_msg}"

        result = {
            "success": False,
            "status": status,
            "error_category": cat,
            "message": user_msg,
            "model_used": effective_model,
            "latency_ms": latency_ms,
            "request_id": None,
            "tested_at": tested_at_iso
        }

        if rec:
            try:
                rec.metadata_json = {
                    **meta,
                    "last_diagnostic": result
                }
                db_session.commit()
            except Exception:
                db_session.rollback()

        return result

