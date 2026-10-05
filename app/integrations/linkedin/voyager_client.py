import os
import sys
from typing import Optional
from cryptography.fernet import Fernet
from requests.cookies import RequestsCookieJar
from playwright.sync_api import sync_playwright

# Add Voyager to path
voyager_path = os.path.join(os.getcwd(), 'Voyager_api', 'open-linkedin-api-main')
if voyager_path not in sys.path:
    sys.path.append(voyager_path)

from open_linkedin_api.linkedin import Linkedin
import open_linkedin_api.client as voyager_client

# Define encryption key for session material
# In production, this should be set in the environment.
_ENCRYPTION_KEY = os.environ.get("LINKEDIN_SESSION_ENCRYPTION_KEY")
if not _ENCRYPTION_KEY:
    raise ValueError("LINKEDIN_SESSION_ENCRYPTION_KEY environment variable is not set. Persistent session encryption requires a permanent key.")
_cipher_suite = Fernet(_ENCRYPTION_KEY.encode("utf-8"))

def encrypt_credential(value: str) -> str:
    return _cipher_suite.encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_credential(encrypted_value: str) -> str:
    return _cipher_suite.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")

def extract_cookies_from_browser(profile_dir: str) -> Optional[RequestsCookieJar]:
    """
    Extracts the authenticated LinkedIn cookies from a persistent Playwright browser profile.
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
            cookies = context.cookies("https://www.linkedin.com")
            print(f"[Voyager Adapter] Found {len(cookies)} cookies for https://www.linkedin.com")
            context.close()

            jar = RequestsCookieJar()
            has_li_at = False
            has_jsessionid = False

            for c in cookies:
                if c['name'] == 'li_at':
                    jar.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
                    has_li_at = True
                elif c['name'] == 'JSESSIONID':
                    jar.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
                    has_jsessionid = True
            
            if has_li_at and not has_jsessionid:
                jar.set("JSESSIONID", '"ajax:0000000000000000000"', domain=".www.linkedin.com", path="/")
                has_jsessionid = True
                print("[Voyager Adapter] Injected dummy JSESSIONID")
            
            if has_li_at and has_jsessionid:
                print(f"[Voyager Adapter] Successfully extracted li_at and JSESSIONID")
                return jar
            else:
                print(f"[Voyager Adapter] Missing required cookies. has_li_at={has_li_at}, has_jsessionid={has_jsessionid}")
    except Exception as e:
        print(f"[Voyager Adapter] Error extracting cookies: {e}")
    return None

def create_voyager_client_from_browser(profile_dir: str = None) -> Optional[Linkedin]:
    """
    Creates an authenticated Voyager client using the local persistent browser session.
    """
    if not profile_dir:
        profile_dir = os.path.join(os.getcwd(), "browser_profile")
        
    jar = extract_cookies_from_browser(profile_dir)
    if not jar:
        return None
        
    try:
        # Prevent Voyager from writing a cookie pickle file by passing a dummy directory or it might error
        # Voyager's cookie repository uses CookieRepository(cookies_dir)
        client = Linkedin(username="", password="", authenticate=True, cookies=jar)
        return client
    except Exception as e:
        print(f"[Voyager Adapter] Error initializing Voyager client: {e}")
        return None

def validate_linkedin_connection(profile_dir: str = None) -> bool:
    """
    Validates that the LinkedIn session is actually authenticated by making a minimal Voyager request.
    """
    client = create_voyager_client_from_browser(profile_dir)
    if not client:
        return False
        
    try:
        # Fetch metadata to see if authentication is active (throws on 401)
        client.client._fetch_metadata()
        return True
    except voyager_client.UnauthorizedException:
        return False
    except Exception as e:
        print(f"[Voyager Adapter] Validation request failed: {e}")
        return False
