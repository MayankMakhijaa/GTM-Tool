import os
import sys
import time
import json
import atexit
import logging
import threading
from urllib.parse import quote
from datetime import datetime
from typing import Optional, Dict, Any, List

from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright

from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, ConnectionStatus
from app.integrations.linkedin.voyager_client import get_browser_profile_dir

logger = logging.getLogger(__name__)

class ManagedBrowserSession:
    """
    Maintains an active, persistent, isolated Chromium browser context for a single user.
    Serializes all interactions via a per-user lock, preventing profile-lock conflicts.
    Reuses the context across GTM discovery jobs without repeatedly launching/closing Chromium.
    """
    def __init__(self, user_id: int, profile_dir: Optional[str] = None):
        self.user_id = user_id
        self.profile_dir = profile_dir or get_browser_profile_dir(user_id)
        self.lock = threading.Lock()
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._authenticated = False
        self._last_verified = 0.0

    def is_alive(self) -> bool:
        """Checks if the Playwright context and page are active and not closed."""
        try:
            return (
                self._context is not None and
                self._page is not None and
                not self._page.is_closed()
            )
        except Exception:
            return False

    def ensure_active(self, headless: bool = True) -> bool:
        """
        Launches or restores the user's persistent Chromium context if not already active.
        Ensures the active page is on a valid LinkedIn origin.
        """
        if self.is_alive():
            return True

        os.makedirs(self.profile_dir, exist_ok=True)
        try:
            logger.info(f"[ManagedBrowserSession] Starting Chromium persistent context for user {self.user_id}")
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=headless,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

            # Ensure page is on feed
            curr_url = self._page.url or ""
            if "linkedin.com" not in curr_url:
                self._page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=45000)
                self._page.wait_for_timeout(2000)

            return True
        except Exception as e:
            logger.error(f"[ManagedBrowserSession] Failed to initialize context for user {self.user_id}: {e}")
            self.close()
            return False

    def _get_csrf_token(self) -> Optional[str]:
        """Extracts the live JSESSIONID CSRF token directly from the persistent context cookies."""
        if not self._context:
            return None
        for c in self._context.cookies():
            if c.get("name") == "JSESSIONID":
                val = (c.get("value") or "").strip('"')
                if val:
                    return val
        return None

    def verify_authentication(self, force: bool = False) -> Dict[str, Any]:
        """
        Validates authentication state using live browser navigation and in-context API response.
        Never relies on a captured cookie or HTTP 200 alone.
        """
        with self.lock:
            now = time.time()
            if not force and self._authenticated and (now - self._last_verified < 300) and self.is_alive():
                return {"valid": True, "category": "authenticated", "message": "Session is active (cached)."}

            if not self.ensure_active():
                return {"valid": False, "category": "browser_error", "message": "Failed to launch browser session."}

            try:
                # 1. URL and DOM check
                curr_url = self._page.url or ""
                if "feed" not in curr_url.lower():
                    self._page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
                    self._page.wait_for_timeout(2000)
                    curr_url = self._page.url

                is_login_redirect = any(x in curr_url.lower() for x in ["login", "checkpoint", "authwall", "challenge"])
                if is_login_redirect:
                    self._authenticated = False
                    self._update_db_status("EXPIRED")
                    return {"valid": False, "category": "expired", "message": "LinkedIn redirected to authentication challenge."}

                # 2. In-context API check with live CSRF token
                csrf = self._get_csrf_token()
                if not csrf:
                    self._authenticated = False
                    self._update_db_status("EXPIRED")
                    return {"valid": False, "category": "expired", "message": "No active JSESSIONID CSRF token found in session."}

                api_check_js = f"""
                async () => {{
                    try {{
                        const csrf = "{csrf}";
                        const r = await fetch('/voyager/api/me', {{
                            headers: {{
                                'accept': 'application/vnd.linkedin.normalized+json+2.1',
                                'csrf-token': csrf,
                                'x-restli-protocol-version': '2.0.0'
                            }}
                        }});
                        const text = await r.text();
                        let parsed = null;
                        try {{ parsed = JSON.parse(text); }} catch(e) {{}}
                        return {{
                            status: r.status,
                            has_plain_id: Boolean(parsed?.data?.plainId),
                            plain_id: parsed?.data?.plainId || null
                        }};
                    }} catch(e) {{
                        return {{ status: 0, error: e.toString() }};
                    }}
                }}
                """
                res = self._page.evaluate(api_check_js)
                status = res.get("status")

                if status == 200 and res.get("has_plain_id"):
                    self._authenticated = True
                    self._last_verified = now
                    self._update_db_status("CONNECTED")
                    return {
                        "valid": True,
                        "category": "authenticated",
                        "message": "Session verified active.",
                        "plain_id": res.get("plain_id")
                    }
                elif status in (401, 403):
                    self._authenticated = False
                    self._update_db_status("EXPIRED")
                    return {"valid": False, "category": "expired", "message": "LinkedIn session expired or unauthorized."}
                elif status == 429:
                    return {"valid": False, "category": "rate_limited", "message": "LinkedIn rate limit encountered."}
                else:
                    return {"valid": False, "category": "unknown_error", "message": f"Unexpected in-context verification status: {status}"}

            except Exception as e:
                logger.error(f"[ManagedBrowserSession] Verification error for user {self.user_id}: {e}")
                return {"valid": False, "category": "network_error", "message": str(e)}

    def search_people(
        self,
        keywords: Optional[str] = None,
        keyword_title: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Executes an in-context GraphQL discovery query through the managed authenticated browser.
        Returns parsed candidate profiles and structured metadata without raw-cookie exports.
        """
        with self.lock:
            # Verify session first
            auth_res = self.verify_authentication()
            if not auth_res.get("valid"):
                return {
                    "status": "AUTH_EXPIRED" if auth_res.get("category") == "expired" else "FAILED",
                    "error_category": auth_res.get("category"),
                    "candidates": [],
                    "raw_error": auth_res.get("message")
                }

            csrf = self._get_csrf_token() or ""
            kw_clean = (keywords or "").strip()
            title_clean = (keyword_title or "").strip()

            combined_query = kw_clean
            if title_clean:
                combined_query = f"{kw_clean} {title_clean}".strip() if kw_clean else title_clean

            encoded_kw = quote(combined_query)

            # Query GraphQL voyagerSearchDashClusters
            graphql_url = (
                f"/voyager/api/graphql?variables=("
                f"start:{offset},"
                f"origin:GLOBAL_SEARCH_HEADER,"
                f"query:(keywords:{encoded_kw},flagshipSearchIntent:SEARCH_SRP,"
                f"queryParameters:List((key:resultType,value:List(PEOPLE))),"
                f"includeFiltersInResponse:false))&"
                f"queryId=voyagerSearchDashClusters.b0928897b71bd00a5a7291755dcd64f0"
            )

            fetch_js = f"""
            async () => {{
                try {{
                    const csrf = "{csrf}";
                    const r = await fetch('{graphql_url}', {{
                        headers: {{
                            'accept': 'application/vnd.linkedin.normalized+json+2.1',
                            'csrf-token': csrf,
                            'x-restli-protocol-version': '2.0.0'
                        }}
                    }});
                    const text = await r.text();
                    let parsed = null;
                    try {{ parsed = JSON.parse(text); }} catch(e) {{}}
                    return {{
                        status: r.status,
                        statusText: r.statusText,
                        redirected: r.redirected,
                        data: parsed
                    }};
                }} catch(e) {{
                    return {{ status: 0, error: e.toString() }};
                }}
            }}
            """
            try:
                res = self._page.evaluate(fetch_js)
                status = res.get("status")

                if status != 200:
                    if status in (401, 403):
                        self._authenticated = False
                        self._update_db_status("EXPIRED")
                        return {"status": "AUTH_EXPIRED", "error_category": "expired", "candidates": [], "raw_error": f"HTTP {status}"}
                    elif status == 429:
                        return {"status": "RATE_LIMITED", "error_category": "rate_limited", "candidates": [], "raw_error": "HTTP 429"}
                    else:
                        return {"status": "FAILED", "error_category": "network_error", "candidates": [], "raw_error": f"HTTP {status}"}

                parsed = res.get("data") or {}
                included = parsed.get("included") or []

                candidates = []
                for item in included:
                    if item.get("$type") == "com.linkedin.voyager.dash.search.EntityResultViewModel":
                        title_obj = item.get("title") or {}
                        sub_obj = item.get("primarySubtitle") or {}
                        sec_obj = item.get("secondarySubtitle") or {}

                        name = title_obj.get("text") or "LinkedIn Member"
                        raw_headline = sub_obj.get("text") or ""
                        location = sec_obj.get("text") or ""
                        nav_url = item.get("navigationUrl") or ""

                        # Parse clean profile URL and URN
                        clean_url = nav_url.split("?")[0] if nav_url else ""
                        urn_id = None
                        if "miniProfileUrn=" in nav_url:
                            urn_part = nav_url.split("miniProfileUrn=")[1].split("&")[0]
                            urn_id = urn_part.split("%3A")[-1].split(":")[-1]

                        role = raw_headline
                        company = ""
                        for sep in [" at ", " @ ", " | ", " - "]:
                            if sep in raw_headline:
                                parts = raw_headline.split(sep, 1)
                                role = parts[0].strip()
                                company = parts[1].strip()
                                break

                        candidates.append({
                            "urn_id": urn_id or f"urn:li:member:{abs(hash(name + raw_headline)) % 10000000}",
                            "name": name,
                            "role": role,
                            "raw_headline": raw_headline,
                            "company": company or "Target Company",
                            "location": location,
                            "profile_url": clean_url,
                            "distance": item.get("badgeText") or "DISTANCE_2",
                            "provider": "VOYAGER",
                            "source_query": combined_query,
                            "source_evidence": f"LinkedIn In-Browser Discovery: {combined_query}".strip()
                        })

                        if len(candidates) >= limit:
                            break

                if candidates:
                    return {"status": "SUCCESS", "candidates": candidates, "error_category": None}
                else:
                    return {"status": "ZERO_RESULTS", "candidates": [], "error_category": None}

            except Exception as e:
                logger.error(f"[ManagedBrowserSession] Discovery query execution error for user {self.user_id}: {e}")
                return {"status": "FAILED", "error_category": "unknown_error", "candidates": [], "raw_error": str(e)}

    def _update_db_status(self, status: str):
        """Updates the UsersLinkedinDetails record non-destructively."""
        try:
            record = db_session.query(UsersLinkedinDetails).filter_by(user_id=self.user_id).first()
            if record and record.connection_status != status:
                record.connection_status = status
                db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.warning(f"[ManagedBrowserSession] Failed to update DB connection status for user {self.user_id}: {e}")

    def close(self):
        """Safely shuts down the context and stops Playwright."""
        with self.lock:
            try:
                if self._context:
                    self._context.close()
            except Exception:
                pass
            try:
                if self._playwright:
                    self._playwright.stop()
            except Exception:
                pass
            self._context = None
            self._page = None
            self._playwright = None
            self._authenticated = False


class BrowserSessionService:
    """
    Singleton service managing lifecycle, serialization, and isolation of per-user browser sessions.
    - Maintains at most one managed browser context per user.
    - Serializes access to each user's context and prevents profile-lock conflicts.
    - Reuses the context across GTM jobs instead of launching a browser for each query.
    - Cleans up resources safely on shutdown.
    - Never shares a context or profile between users.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BrowserSessionService, cls).__new__(cls)
                cls._instance._sessions: Dict[int, ManagedBrowserSession] = {}
                atexit.register(cls._instance.shutdown_all)
            return cls._instance

    def get_session(self, user_id: int) -> ManagedBrowserSession:
        """Retrieves or creates the serialized ManagedBrowserSession for a user."""
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = ManagedBrowserSession(user_id)
            return self._sessions[user_id]

    def has_active_session(self, user_id: int) -> bool:
        """Returns True if the user has an active, running browser context."""
        with self._lock:
            session = self._sessions.get(user_id)
            return session.is_alive() if session else False

    def close_session(self, user_id: int):
        """Gracefully closes a user's session and removes it from the registry."""
        with self._lock:
            session = self._sessions.pop(user_id, None)
            if session:
                session.close()

    def shutdown_all(self):
        """Shuts down all managed browser contexts cleanly."""
        with self._lock:
            for uid, session in list(self._sessions.items()):
                try:
                    session.close()
                except Exception:
                    pass
            self._sessions.clear()

    def get_service_status(self) -> Dict[str, Any]:
        """
        Reports operational metrics, resource footprint, and deployment limitations.
        """
        with self._lock:
            active_count = sum(1 for s in self._sessions.values() if s.is_alive())
            return {
                "active_sessions": active_count,
                "managed_users": list(self._sessions.keys()),
                "resource_requirements": {
                    "estimated_ram_per_user_mb": 90,
                    "estimated_cpu_idle_pct": 0.1,
                    "disk_per_profile_mb": 45
                },
                "deployment_limitations": [
                    "Requires persistent volume for browser_profiles/ in containerized environments",
                    "Requires single-process affinity (or dedicated worker service) to prevent multi-process profile directory lock contention",
                    "Linux deployments require Playwright Chromium OS dependencies (libnss3, libasound2, etc.)"
                ]
            }

# Global singleton accessor
browser_session_service = BrowserSessionService()
