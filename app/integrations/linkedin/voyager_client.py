import os
import sys
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests
from requests.cookies import RequestsCookieJar
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright

load_dotenv()

# Add Voyager to path
voyager_path = os.path.join(os.getcwd(), 'Voyager_api', 'open-linkedin-api-main')
if voyager_path not in sys.path:
    sys.path.append(voyager_path)

from open_linkedin_api.linkedin import Linkedin
import open_linkedin_api.client as open_voyager_client

def _get_cipher_suite() -> Fernet:
    key = os.environ.get("LINKEDIN_SESSION_ENCRYPTION_KEY")
    if not key:
        load_dotenv()
        key = os.environ.get("LINKEDIN_SESSION_ENCRYPTION_KEY")
    if not key:
        raise ValueError("LINKEDIN_SESSION_ENCRYPTION_KEY environment variable is not set. Persistent session encryption requires a permanent key.")
    return Fernet(key.encode("utf-8"))

def encrypt_credential(value: str) -> str:
    return _get_cipher_suite().encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_credential(encrypted_value: str) -> str:
    return _get_cipher_suite().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")

def extract_cookies_from_browser(profile_dir: str) -> Optional[RequestsCookieJar]:
    """
    Extracts authenticated LinkedIn cookies from a persistent Playwright browser profile.
    Rejects dummy placeholders and validates that required cookies exist.
    """
    if not os.path.exists(profile_dir):
        return None

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            cookies = context.cookies()
            context.close()

            jar = RequestsCookieJar()
            has_li_at = False
            has_jsessionid = False

            for c in cookies:
                c_name = c.get('name')
                c_val = (c.get('value') or "").strip()
                domain = c.get('domain', '.linkedin.com')
                path = c.get('path', '/')

                if c_name == 'li_at' and c_val:
                    jar.set(c_name, c_val, domain=domain, path=path)
                    has_li_at = True
                elif c_name == 'JSESSIONID' and c_val:
                    cleaned_val = c_val.strip('"')
                    if cleaned_val and not cleaned_val.startswith("ajax:0000000000000000000"):
                        jar.set(c_name, cleaned_val, domain=domain, path=path)
                        has_jsessionid = True

            if has_li_at and has_jsessionid:
                return jar
    except Exception as e:
        print(f"[Voyager Adapter] Error extracting cookies: {e}")
    return None

def get_browser_profile_dir(user_id: int) -> str:
    """Returns the persistent Playwright profile directory for a given user."""
    return os.path.join(os.getcwd(), "browser_profiles", str(user_id))

def create_voyager_client_from_db(user_id: int) -> Optional[Linkedin]:
    """
    Creates an authenticated Voyager client using the user's PostgreSQL encrypted credentials.
    Runs entirely in memory and never launches Chromium.
    """
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails

    try:
        record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if not record or not record.auth_data_encrypted:
            return None

        decrypted = decrypt_credential(record.auth_data_encrypted)
        try:
            cookie_dict = json.loads(decrypted)
        except Exception:
            return None

        li_at = (cookie_dict.get("li_at") or "").strip()
        jsessionid = (cookie_dict.get("JSESSIONID") or "").strip().strip('"')

        if not li_at or not jsessionid or jsessionid.startswith("ajax:0000000000000000000"):
            return None

        jar = RequestsCookieJar()
        jar.set("li_at", li_at, domain=".linkedin.com", path="/")
        jar.set("JSESSIONID", jsessionid, domain=".linkedin.com", path="/")

        client = Linkedin(username="", password="", authenticate=True, cookies=jar)
        return client
    except Exception as e:
        print(f"[Voyager Adapter] Error initializing Voyager client from DB for user {user_id}: {e}")
        return None

def create_voyager_client_from_browser(user_id: int) -> Optional[Linkedin]:
    """
    Creates an authenticated Voyager client from the local browser profile directory.
    Fallback helper used when inspecting or validating initial local capture.
    """
    profile_dir = get_browser_profile_dir(user_id)
    jar = extract_cookies_from_browser(profile_dir)
    if not jar:
        return None

    try:
        client = Linkedin(username="", password="", authenticate=True, cookies=jar)
        return client
    except Exception as e:
        print(f"[Voyager Adapter] Error initializing Voyager client from browser for user {user_id}: {e}")
        return None

def _update_connection_status(user_id: int, status: str):
    """Safely updates UsersLinkedinDetails.connection_status without altering auth_data_encrypted."""
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails
    try:
        record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if record:
            record.connection_status = status
            db_session.commit()
    except Exception as e:
        db_session.rollback()
        print(f"[Voyager Adapter] Failed to update connection status for user {user_id}: {e}")

def validate_user_session(user_id: int) -> Dict[str, Any]:
    """
    Validates the user's stored LinkedIn session non-destructively.
    Distinguishes: authenticated, expired, rate_limited, network_error, unknown_error, no_connection.
    """
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails

    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    if not record or not record.auth_data_encrypted:
        return {"valid": False, "category": "no_connection", "message": "No LinkedIn connection found."}

    client = create_voyager_client_from_db(user_id)
    if not client:
        return {"valid": False, "category": "corrupted_session", "message": "Stored session could not be decrypted or parsed."}

    try:
        # Voyager client.client.session is the underlying requests.Session
        res = client.client.session.get(
            "https://www.linkedin.com/voyager/api/me",
            headers=getattr(client.client, "REQUEST_HEADERS", {}),
            allow_redirects=False,
            timeout=12
        )

        if res.status_code == 200:
            # Active session confirmed
            if record.connection_status != "CONNECTED":
                _update_connection_status(user_id, "CONNECTED")
            return {"valid": True, "category": "authenticated", "message": "Session is active."}

        elif res.status_code == 429:
            # Rate limited: preserve credentials and status
            return {"valid": False, "category": "rate_limited", "message": "LinkedIn rate limit encountered."}

        elif res.status_code in (401, 403):
            # Confirmed expired: update status non-destructively
            _update_connection_status(user_id, "EXPIRED")
            return {"valid": False, "category": "expired", "message": "LinkedIn session has expired or was revoked."}

        elif res.status_code in (301, 302, 303, 307, 308):
            location = res.headers.get("Location", "").lower()
            if any(k in location for k in ["/uas/login", "/authwall", "login", "checkpoint"]):
                _update_connection_status(user_id, "EXPIRED")
                return {"valid": False, "category": "expired", "message": "LinkedIn session redirected to login."}
            else:
                # Ambiguous redirect: preserve credentials and status
                return {"valid": False, "category": "unknown_error", "message": f"Unexpected redirect encountered: {location}"}

        elif 500 <= res.status_code < 600:
            # Transient server error: preserve credentials
            return {"valid": False, "category": "network_error", "message": f"LinkedIn server error ({res.status_code})."}

        else:
            return {"valid": False, "category": "unknown_error", "message": f"Unexpected status code {res.status_code}."}

    except (requests.Timeout, requests.ConnectionError) as e:
        return {"valid": False, "category": "network_error", "message": f"Network error connecting to LinkedIn: {str(e)}"}
    except Exception as e:
        return {"valid": False, "category": "unknown_error", "message": str(e)}

def validate_linkedin_connection(user_id: int) -> bool:
    """
    Backwards-compatible boolean check used by existing callers.
    Uses fast DB-backed session validation without launching Chromium.
    """
    result = validate_user_session(user_id)
    return result.get("valid", False)
