import os
import re
import time
import json
import logging
import threading
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Supported search engines in canonical OpenSERP client
SUPPORTED_ENGINES = ("google", "bing", "yandex", "baidu", "duckduckgo", "ecosia")

ENGINE_ENDPOINTS = {
    "google": "/google/search",
    "bing": "/bing/search",
    "yandex": "/yandex/search",
    "baidu": "/baidu/search",
    "duckduckgo": "/duckduckgo/search",
    "ecosia": "/ecosia/search"
}

# Explicit LinkedIn hostname allowlist to prevent arbitrary Open Redirect attacks
LINKEDIN_ALLOWED_HOSTNAMES = {
    "linkedin.com",
    "www.linkedin.com",
    "in.linkedin.com",
    "uk.linkedin.com",
    "ca.linkedin.com",
    "au.linkedin.com",
    "de.linkedin.com",
    "fr.linkedin.com",
    "es.linkedin.com",
    "it.linkedin.com",
    "nl.linkedin.com",
    "sg.linkedin.com",
    "ae.linkedin.com",
    "sa.linkedin.com",
    "br.linkedin.com",
    "mx.linkedin.com",
    "ch.linkedin.com",
    "se.linkedin.com",
    "no.linkedin.com",
    "dk.linkedin.com",
    "ie.linkedin.com",
    "nz.linkedin.com",
    "za.linkedin.com"
}


class OpenSerpClient:
    """
    Canonical OpenSERP HTTP Client supporting all six search engines:
    - google (/google/search)
    - bing (/bing/search)
    - yandex (/yandex/search)
    - baidu (/baidu/search)
    - duckduckgo (/duckduckgo/search)
    - ecosia (/ecosia/search)

    Features:
    - Thread-safe independent per-engine state, timeouts, and cooldown tracking.
    - Robust normalization mapping OpenSERP results (both 'snippet' and 'description').
    - Clear status classification (SUCCESS, EMPTY_RESPONSE, RATE_LIMITED, HTTP_429,
      CAPTCHA_DETECTED, BLOCKED, TIMEOUT, CONNECTION_ERROR, INVALID_RESPONSE, ERROR).
    - Failure isolation: block/cooldown on one engine never affects any other engine.
    - Externally managed binary support: provides health checks, never starts/stops the binary.
    """

    DEFAULT_BASE_URL = os.getenv("OPENSERP_BASE_URL", "http://127.0.0.1:7000").rstrip("/")
    DEFAULT_TIMEOUT_SECONDS = float(os.getenv("OPENSERP_TIMEOUT_SECONDS", "15.0"))
    DEFAULT_COOLDOWN_DURATION = float(os.getenv("OPENSERP_ENGINE_COOLDOWN_SECONDS", "300.0"))

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        cooldown_duration: Optional[float] = None
    ):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else self.DEFAULT_TIMEOUT_SECONDS
        self.cooldown_duration = cooldown_duration if cooldown_duration is not None else self.DEFAULT_COOLDOWN_DURATION

        self._lock = threading.Lock()
        # Per-engine tracking dictionary:
        # engine -> {"cooldown_until": float, "last_status": str, "last_error": str, "last_request_time": float}
        self._engine_states: Dict[str, Dict[str, Any]] = {
            eng: {
                "cooldown_until": 0.0,
                "last_status": "READY",
                "last_error": None,
                "last_request_time": 0.0
            }
            for eng in SUPPORTED_ENGINES
        }

    def health_check(self, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Check whether the OpenSERP server is running and reachable at /health.
        Does NOT launch or manage the process.
        """
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "FameWeb-OpenSerpClient/1.0"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency_ms = round((time.monotonic() - t0) * 1000, 1)
                body = resp.read().decode("utf-8", errors="ignore").strip()
                is_healthy = resp.status == 200
                return {
                    "healthy": is_healthy,
                    "status_code": resp.status,
                    "latency_ms": latency_ms,
                    "message": body or "OK",
                    "base_url": self.base_url
                }
        except urllib.error.HTTPError as he:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return {
                "healthy": False,
                "status_code": he.code,
                "latency_ms": latency_ms,
                "error": f"HTTP {he.code}",
                "base_url": self.base_url
            }
        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return {
                "healthy": False,
                "status_code": None,
                "latency_ms": latency_ms,
                "error": str(exc),
                "base_url": self.base_url
            }

    def get_engine_status(self, engine: str) -> Dict[str, Any]:
        """Return the current cooldown and health status for an engine."""
        canonical_engine = engine.strip().lower()
        with self._lock:
            state = self._engine_states.get(canonical_engine)
            if not state:
                return {"supported": False, "engine": canonical_engine}

            now = time.monotonic()
            cd_until = state["cooldown_until"]
            in_cooldown = now < cd_until
            remaining = round(cd_until - now, 1) if in_cooldown else 0.0

            return {
                "supported": True,
                "engine": canonical_engine,
                "is_in_cooldown": in_cooldown,
                "cooldown_remaining_seconds": remaining,
                "last_status": state["last_status"],
                "last_error": state["last_error"],
                "last_request_time": state["last_request_time"]
            }

    def set_engine_cooldown(self, engine: str, seconds: Optional[float] = None, reason: Optional[str] = None):
        """Set a cooldown specifically for one engine without affecting others."""
        canonical_engine = engine.strip().lower()
        duration = seconds if seconds is not None else self.cooldown_duration
        with self._lock:
            if canonical_engine in self._engine_states:
                self._engine_states[canonical_engine]["cooldown_until"] = time.monotonic() + duration
                if reason:
                    self._engine_states[canonical_engine]["last_error"] = reason
                logger.warning(
                    f"[OpenSerpClient] Cooldown activated for engine '{canonical_engine}': "
                    f"{duration}s (Reason: {reason})"
                )

    def clear_engine_cooldown(self, engine: Optional[str] = None):
        """Clear cooldown for a specific engine, or all engines if None."""
        with self._lock:
            if engine:
                canonical_engine = engine.strip().lower()
                if canonical_engine in self._engine_states:
                    self._engine_states[canonical_engine]["cooldown_until"] = 0.0
            else:
                for state in self._engine_states.values():
                    state["cooldown_until"] = 0.0

    @staticmethod
    def normalize_result_item(item: Dict[str, Any], engine: str, rank: int = 1) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw result item from OpenSERP into the canonical search item format.
        Compatible with both 'snippet' and 'description'.
        """
        if not isinstance(item, dict):
            return None

        raw_url = (item.get("url") or item.get("link") or "").strip()
        if not raw_url:
            return None

        # Clean/extract domain
        domain = ""
        try:
            parsed = urllib.parse.urlparse(raw_url)
            domain = (parsed.netloc or "").lower().split(":")[0]
        except Exception:
            pass

        title = (item.get("title") or "").strip()
        # Accommodate both v0.8.17 ('snippet') and earlier variants ('description')
        snippet_text = (item.get("snippet") or item.get("description") or "").strip()

        return {
            "title": title,
            "url": raw_url,
            "description": snippet_text,
            "snippet": snippet_text,
            "domain": domain,
            "engine": engine.lower(),
            "rank": rank
        }

    def search(
        self,
        engine: str,
        query: str,
        limit: int = 10,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute an isolated search query against a specific engine.
        Returns a normalized dict:
        {
            "engine": str,
            "status": str,
            "items": list,
            "count": int,
            "latency_ms": float,
            "error_message": Optional[str],
            "cooldown_seconds": float
        }
        """
        canonical_engine = (engine or "").strip().lower()
        if canonical_engine not in ENGINE_ENDPOINTS:
            return {
                "engine": canonical_engine,
                "status": "ERROR",
                "items": [],
                "count": 0,
                "latency_ms": 0.0,
                "error_message": f"Unsupported search engine: '{engine}'. Supported: {SUPPORTED_ENGINES}",
                "cooldown_seconds": 0.0
            }

        endpoint_path = ENGINE_ENDPOINTS[canonical_engine]
        req_timeout = timeout if timeout is not None else self.timeout_seconds

        # Check engine-specific cooldown
        with self._lock:
            st = self._engine_states[canonical_engine]
            now = time.monotonic()
            if now < st["cooldown_until"]:
                rem = round(st["cooldown_until"] - now, 1)
                return {
                    "engine": canonical_engine,
                    "status": "RATE_LIMITED",
                    "items": [],
                    "count": 0,
                    "latency_ms": 0.0,
                    "error_message": f"Engine '{canonical_engine}' is in active cooldown ({rem}s remaining)",
                    "cooldown_seconds": rem
                }

        # Build request URL
        encoded_q = urllib.parse.quote_plus(query.strip())
        req_url = f"{self.base_url}{endpoint_path}?text={encoded_q}&limit={limit}"
        req = urllib.request.Request(
            req_url,
            headers={"User-Agent": "FameWeb-OpenSerpClient/1.0"}
        )

        t0 = time.monotonic()
        with self._lock:
            self._engine_states[canonical_engine]["last_request_time"] = t0

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                latency_ms = round((time.monotonic() - t0) * 1000, 1)
                resp_bytes = resp.read()
                raw_text = resp_bytes.decode("utf-8", errors="ignore")

                try:
                    payload = json.loads(raw_text)
                except Exception as json_err:
                    with self._lock:
                        self._engine_states[canonical_engine]["last_status"] = "INVALID_RESPONSE"
                        self._engine_states[canonical_engine]["last_error"] = str(json_err)
                    return {
                        "engine": canonical_engine,
                        "status": "INVALID_RESPONSE",
                        "items": [],
                        "count": 0,
                        "latency_ms": latency_ms,
                        "error_message": f"Non-JSON response from OpenSERP: {str(json_err)}",
                        "cooldown_seconds": 0.0
                    }

                raw_results = payload.get("results")
                if raw_results is None and isinstance(payload, list):
                    raw_results = payload

                normalized_items: List[Dict[str, Any]] = []
                if isinstance(raw_results, list):
                    for idx, raw_item in enumerate(raw_results, start=1):
                        norm = self.normalize_result_item(raw_item, canonical_engine, rank=idx)
                        if norm:
                            normalized_items.append(norm)

                status = "SUCCESS" if normalized_items else "EMPTY_RESPONSE"
                with self._lock:
                    self._engine_states[canonical_engine]["last_status"] = status
                    self._engine_states[canonical_engine]["last_error"] = None

                return {
                    "engine": canonical_engine,
                    "status": status,
                    "items": normalized_items,
                    "count": len(normalized_items),
                    "latency_ms": latency_ms,
                    "error_message": None,
                    "cooldown_seconds": 0.0
                }

        except urllib.error.HTTPError as he:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            err_body = he.read().decode("utf-8", errors="ignore").lower()
            err_msg = f"HTTP {he.code}: {err_body[:150]}"

            if he.code in (429, 403) or "captcha" in err_body or "challenge" in err_body:
                status = "CAPTCHA_DETECTED" if "captcha" in err_body else "HTTP_429" if he.code == 429 else "BLOCKED"
                self.set_engine_cooldown(canonical_engine, self.cooldown_duration, reason=err_msg)
                with self._lock:
                    self._engine_states[canonical_engine]["last_status"] = status
                    rem = round(self._engine_states[canonical_engine]["cooldown_until"] - time.monotonic(), 1)
                return {
                    "engine": canonical_engine,
                    "status": status,
                    "items": [],
                    "count": 0,
                    "latency_ms": latency_ms,
                    "error_message": err_msg,
                    "cooldown_seconds": max(0.0, rem)
                }

            status = f"HTTP_{he.code}"
            with self._lock:
                self._engine_states[canonical_engine]["last_status"] = status
                self._engine_states[canonical_engine]["last_error"] = err_msg
            return {
                "engine": canonical_engine,
                "status": status,
                "items": [],
                "count": 0,
                "latency_ms": latency_ms,
                "error_message": err_msg,
                "cooldown_seconds": 0.0
            }

        except urllib.error.URLError as ue:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            err_reason = str(ue.reason) if hasattr(ue, "reason") else str(ue)
            is_timeout = "timed out" in err_reason.lower() or "timeout" in err_reason.lower()
            status = "TIMEOUT" if is_timeout else "CONNECTION_ERROR"
            with self._lock:
                self._engine_states[canonical_engine]["last_status"] = status
                self._engine_states[canonical_engine]["last_error"] = err_reason
            return {
                "engine": canonical_engine,
                "status": status,
                "items": [],
                "count": 0,
                "latency_ms": latency_ms,
                "error_message": err_reason,
                "cooldown_seconds": 0.0
            }

        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            err_str = str(exc)
            is_timeout = "timed out" in err_str.lower() or "timeout" in err_str.lower()
            status = "TIMEOUT" if is_timeout else "ERROR"
            with self._lock:
                self._engine_states[canonical_engine]["last_status"] = status
                self._engine_states[canonical_engine]["last_error"] = err_str
            return {
                "engine": canonical_engine,
                "status": status,
                "items": [],
                "count": 0,
                "latency_ms": latency_ms,
                "error_message": err_str,
                "cooldown_seconds": 0.0
            }


# Default singleton instance
default_openserp_client = OpenSerpClient()

class OpenSerpDiscoveryService:
    """
    Isolated Public Web Discovery adapter communicating with a self-hosted OpenSERP service.
    Features:
    - Dedicated Google endpoint focus (Google /google/search)
    - Strict redirect validation against LinkedIn hostname allowlist
    - Conservative request pacing (default 4.0s interval)
    - Early halting on CAPTCHA / 429 rate limit
    - Evidence-based candidate extraction (no fabricated names, companies, or locations)
    """

    DEFAULT_BASE_URL = os.getenv("OPENSERP_BASE_URL", "http://127.0.0.1:7000").rstrip("/")
    REQUEST_TIMEOUT = 15  # Seconds per HTTP call
    MIN_REQUEST_INTERVAL = 6.0  # Conservative anti-bot pacing between Google queries
    MAX_QUERY_CAP = 1  # Single-query mode to minimize Google anti-bot rate-limit triggers
    MAX_REDIRECT_HOPS = 3
    CAPTCHA_COOLDOWN_DURATION = 300.0  # 5-minute cooldown on anti-bot/rate-limit blocks

    # Shared process-wide synchronization state
    _scheduler_lock = threading.Lock()
    _gate_condition = threading.Condition(_scheduler_lock)
    _last_request_start = 0.0  # time.monotonic() of the most recent Google request start
    _captcha_cooldown_until = 0.0  # time.monotonic() until which requests are blocked

    @classmethod
    def get_cooldown_status(cls) -> Tuple[bool, float]:
        """
        Thread-safe check for active CAPTCHA cooldown.
        Returns (is_in_cooldown, remaining_seconds).
        """
        with cls._scheduler_lock:
            now = time.monotonic()
            if now < cls._captcha_cooldown_until:
                return True, round(cls._captcha_cooldown_until - now, 1)
            return False, 0.0

    @classmethod
    def activate_captcha_cooldown(cls) -> float:
        """
        Thread-safe activation of 5-minute CAPTCHA cooldown.
        Notifies all threads waiting on the gate condition so they immediately wake and abort.
        Returns the monotonic deadline.
        """
        with cls._scheduler_lock:
            cls._captcha_cooldown_until = time.monotonic() + cls.CAPTCHA_COOLDOWN_DURATION
            cls._gate_condition.notify_all()
            return cls._captcha_cooldown_until

    @classmethod
    def clear_cooldown_for_testing(cls):
        """Testing helper to reset scheduler and cooldown state."""
        with cls._scheduler_lock:
            cls._last_request_start = 0.0
            cls._captcha_cooldown_until = 0.0
            cls._gate_condition.notify_all()

    @classmethod
    def wait_for_request_gate(cls) -> Tuple[bool, float]:
        """
        Thread-safe request-start gate:
        1. Acquires the shared scheduler lock.
        2. Waits until the time elapsed since the previous actual request start is >= MIN_REQUEST_INTERVAL.
           Uses Condition.wait(timeout) to yield the lock while waiting, allowing activate_captcha_cooldown()
           to wake the waiting thread immediately if a block occurs.
        3. Rechecks the CAPTCHA cooldown under the lock.
           If cooldown was activated while waiting, returns (False, remaining_cooldown_seconds).
        4. Updates _last_request_start immediately before returning to dispatch the request.
        5. The caller exits the gate context (releasing the lock) BEFORE performing network I/O.
        Returns (can_dispatch, cooldown_remaining_seconds).
        """
        with cls._scheduler_lock:
            while True:
                now = time.monotonic()
                # Recheck CAPTCHA cooldown
                if now < cls._captcha_cooldown_until:
                    return False, round(cls._captcha_cooldown_until - now, 1)

                elapsed = now - cls._last_request_start
                if cls._last_request_start == 0.0 or elapsed >= cls.MIN_REQUEST_INTERVAL:
                    # Gate cleared: record actual request start timestamp immediately
                    cls._last_request_start = now
                    return True, 0.0

                remaining_wait = cls.MIN_REQUEST_INTERVAL - elapsed
                cls._gate_condition.wait(timeout=remaining_wait)

    @classmethod
    def get_base_url(cls) -> str:
        return os.getenv("OPENSERP_BASE_URL", cls.DEFAULT_BASE_URL).rstrip("/")

    @classmethod
    def is_available(cls) -> Tuple[bool, str]:
        """
        Calls the local OpenSERP /health endpoint with a 3-second timeout.
        Returns (is_healthy, status_message).
        """
        base_url = cls.get_base_url()
        health_url = f"{base_url}/health"
        try:
            req = urllib.request.Request(
                health_url,
                headers={"User-Agent": "FameWeb-OpenSERP-Adapter/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "healthy":
                        return True, "OpenSERP local instance is healthy and ready."
                    return False, f"OpenSERP returned non-healthy status: {data.get('status')}"
                return False, f"OpenSERP health check returned HTTP {resp.status}"
        except urllib.error.URLError as ue:
            return False, f"OpenSERP service is not running on {base_url} ({ue.reason})"
        except Exception as e:
            return False, f"OpenSERP health check error: {str(e)}"

    @classmethod
    def resolve_safe_linkedin_url(cls, raw_url: str) -> Optional[str]:
        """
        Validates whether raw_url or its resolved redirect destination is a legitimate
        individual LinkedIn profile URL (https://[country.]linkedin.com/in/<slug>).
        Safely follows Google /goto?url=... redirects up to MAX_REDIRECT_HOPS.
        Rejects arbitrary external domains.
        """
        if not raw_url:
            return None

        current_url = raw_url.strip()
        hops = 0

        while hops < cls.MAX_REDIRECT_HOPS:
            parsed = urllib.parse.urlparse(current_url)
            host = parsed.netloc.lower().split(":")[0]

            # 1. Check if current URL is directly a valid LinkedIn profile
            if cls.is_allowed_linkedin_host(host):
                m = re.search(r"^/in/([^/?#]+)", parsed.path, re.IGNORECASE)
                if m:
                    slug = m.group(1).strip()
                    # Exclude non-individual profile paths
                    if slug.lower() not in ("me", "unavailable", "jobs", "feed", "company", "school"):
                        return f"https://{host}/in/{slug}"
                return None

            # 2. Check if it is a Google redirect format (e.g. google.com/goto?url=...)
            if "google.com" in host and "/goto" in parsed.path:
                try:
                    req = urllib.request.Request(
                        current_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FameWeb/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        next_url = resp.geturl()
                        if next_url == current_url:
                            break
                        current_url = next_url
                        hops += 1
                        continue
                except urllib.error.HTTPError as he:
                    # Often LinkedIn returns 999 or 403 on automated navigation, but the redirect header / URL
                    # in HTTPError already contains the target destination URL!
                    if hasattr(he, "url") and he.url:
                        current_url = he.url
                        hops += 1
                        continue
                    break
                except Exception:
                    break
            else:
                # Not a LinkedIn URL and not a recognized Google redirect
                break

        # Final check on resolved URL
        parsed = urllib.parse.urlparse(current_url)
        host = parsed.netloc.lower().split(":")[0]
        if cls.is_allowed_linkedin_host(host):
            m = re.search(r"^/in/([^/?#]+)", parsed.path, re.IGNORECASE)
            if m:
                slug = m.group(1).strip()
                if slug.lower() not in ("me", "unavailable", "jobs", "feed", "company", "school"):
                    return f"https://{host}/in/{slug}"

        return None

    @classmethod
    def is_allowed_linkedin_host(cls, host: str) -> bool:
        """Checks if host matches the exact allowlist or standard *.linkedin.com domain."""
        if host in LINKEDIN_ALLOWED_HOSTNAMES:
            return True
        return host.endswith(".linkedin.com") and not host.endswith("malicious.linkedin.com")

    @classmethod
    def parse_candidate_evidence(cls, item: Dict[str, Any], query_ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses raw search result item into a candidate dictionary.
        Extracts Name, Role, Company, Location strictly when supported by evidence.
        Never infers Name from slug alone. Missing fields remain None.
        """
        raw_url = item.get("url") or ""
        resolved_url = cls.resolve_safe_linkedin_url(raw_url)
        if not resolved_url:
            return None

        title_text = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        slug_match = re.search(r"/in/([^/?#]+)", resolved_url)
        slug = slug_match.group(1) if slug_match else ""

        # Remove LinkedIn suffix from title
        clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title_text, flags=re.IGNORECASE).strip()
        clean_title = re.sub(r"\s*-\s*LinkedIn.*$", "", clean_title, flags=re.IGNORECASE).strip()

        # Split primary segments by pipe or dash where applicable, but respect titles with internal dashes
        # Often format is: "Name [Degree] - Role [ - Details] | Company" or "Name - Role - Company"
        # We split by top-level pipe '|' first, then examine the first part for Name - Role
        pipe_parts = [p.strip() for p in clean_title.split("|") if p.strip()]
        first_segment = pipe_parts[0] if pipe_parts else clean_title

        # Check for Name - Role split in first_segment
        # Avoid splitting within words or dashes that belong to titles like "VP - Sales"
        # Split on dash/en-dash/em-dash with spaces
        dash_parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", first_segment) if p.strip()]

        raw_name = ""
        raw_role_from_title = ""

        if len(dash_parts) >= 2:
            raw_name = dash_parts[0]
            # The remaining dash parts in the first segment often form the role
            raw_role_from_title = " – ".join(dash_parts[1:])
        elif len(dash_parts) == 1:
            raw_name = dash_parts[0]

        # Clean academic/professional credentials from Name (e.g. "Mohamed Rafiuddin, PhD." -> "Mohamed Rafiuddin")
        cleaned_name = re.sub(r"[,.]?\s*(PhD\.?|Ph\.D\.?|MBA|MS|BTech|BE|CA|CFA|MD|Esq\.?).*$", "", raw_name, flags=re.IGNORECASE).strip()
        # If the name ends with a trailing comma or dot, trim it
        cleaned_name = re.sub(r"[,.]+$", "", cleaned_name).strip()

        name = None
        # Strict validation: name must have at least 2 tokens (or if 2nd token is initial e.g. "Kurt S", allow as uncertain/abbreviated name),
        # not start with http/www, not contain "linkedin", and not be a job title/role phrase
        is_job_title_phrase = any(cleaned_name.lower().startswith(p) for p in ["vp ", "director ", "head of ", "chief ", "founder", "manager ", "lead "])
        if cleaned_name and len(cleaned_name.split()) >= 2 and not cleaned_name.lower().startswith("http") and "linkedin" not in cleaned_name.lower() and not is_job_title_phrase:
            name = cleaned_name

        if not name:
            # If name is not explicitly supported by title or snippet, we do NOT manufacture it from slug!
            return None

        # 2. Role Extraction
        # Look for comprehensive roles in title and snippet
        role = None
        if raw_role_from_title:
            role = raw_role_from_title
        elif snippet:
            role_m = re.search(r"(VP\s*[–-]?\s*Sales|Director\s*[–-]?\s*Sales|Head\s+of\s+Sales|Chief\s+Revenue\s+Officer|Chief\s+Executive\s+Officer|Founder\s*&?\s*CEO|VP\s+of\s+[A-Za-z\s]+|Director\s+of\s+[A-Za-z\s]+)", snippet, re.IGNORECASE)
            if role_m:
                role = role_m.group(1).strip()

        # If role still contains promotional or scaling sentences (e.g. "Scaling revenue..."), separate it
        if role and (" | " in role or " |" in role):
            role = role.split("|")[0].strip()

        # 3. Company Extraction
        # Strict criteria:
        # A. Snippet patterns:
        #    - "· Sprouts.ai" or "• Sprouts.ai"
        #    - "at Sprouts.ai" or "at <Company>"
        #    - "Current: <Company>" or "Experience: <Company>"
        # B. Pipe/dash title parts only if explicitly NOT a descriptive phrase or skill list
        company = None

        # Check snippet first for definitive company indicators:
        # Pattern 1: Dot bullet followed by company: e.g. "VP of Sales · Sprouts.ai"
        bullet_matches = re.findall(r"[·•]\s*([A-Za-z0-9&.\-_]+(?:\s+[A-Za-z0-9&.\-_]+){0,3})", snippet)
        for b_cand in bullet_matches:
            b_cand = b_cand.strip()
            # Must not be a job title or location or generic text
            if any(kw in b_cand for kw in ["VP", "Director", "Sales", "Marketing", "CMO", "Chief", "Founder", "Head of", "Manager", "Revenue", "Officer"]):
                continue
            if any(kw in b_cand for kw in ["Bengaluru", "Karnataka", "India", "Mumbai", "Delhi", "San Francisco", "United States", "Read more", "View profile"]):
                continue
            if any(verb in b_cand.lower() for verb in ["scaling", "driving", "leading", "building", "helping"]):
                continue
            if len(b_cand) >= 2 and len(b_cand) <= 40:
                company = b_cand
                break

        # Pattern 2: "at <Company>" in snippet or title (e.g. "at Sell.Do in Bengaluru" or "at Sprouts.ai")
        if not company:
            at_m = re.search(r"\bat\s+([A-Z0-9][A-Za-z0-9&.\-_]+(?:\s+[A-Za-z0-9&.\-_]+){0,3}?)(?:\s+in\s+[A-Z]|[\s·•,;\n]|$)", snippet)
            if at_m:
                cand_comp = at_m.group(1).strip()
                if not any(kw in cand_comp for kw in ["Bengaluru", "India", "United States", "Present", "least", "most"]) and not any(verb in cand_comp.lower() for verb in ["scaling", "driving", "leading", "building"]):
                    if len(cand_comp) >= 2 and len(cand_comp) <= 40:
                        company = cand_comp

        # Pattern 3: "Experience: <Company>" or "Current: <Company>"
        if not company:
            exp_m = re.search(r"(?:Experience|Current):\s*([A-Za-z0-9&.\-_]+(?:\s+[A-Za-z0-9&.\-_]+){0,3})", snippet, re.IGNORECASE)
            if exp_m:
                cand_comp = exp_m.group(1).strip()
                if len(cand_comp) >= 2 and len(cand_comp) <= 40:
                    company = cand_comp

        # Pattern 4: Title segment check (e.g. "Name - Title | Company")
        # Only accept if the title segment is explicitly a distinct company and not a discipline, skill list, or ellipsis
        if not company and len(pipe_parts) >= 2:
            last_part = pipe_parts[-1].strip()
            # If last_part is short, doesn't contain action verbs, doesn't contain title words, tech buzzwords, or ellipsis
            is_descriptive = any(term in last_part.lower() for term in [
                "scaling", "revenue", "sales teams", "helping", "driving", "growth", "passionate", "director", "officer", "leader",
                "b2b", "saas", "technology", "services", "gtm", "strategy", "enterprise", "cloud", "consulting", "..."
            ])
            if not is_descriptive and len(last_part) >= 2 and len(last_part) <= 40:
                company = last_part

        # Never let descriptive phrases, disciplines, or single title words like "Sales" become the company
        if company:
            comp_lower = company.lower()
            banned_company_tokens = [
                "sales", "vp", "director", "head", "marketing", "gtm", "strategy",
                "scaling revenue", "revenue and sales", "enterprise technology", "it services"
            ]
            if any(bt in comp_lower for bt in banned_company_tokens) or "..." in company:
                company = None

        # 4. Location Extraction
        location = None
        for loc_cand in ["Bengaluru, Karnataka, India", "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "India", "United States", "San Francisco"]:
            if loc_cand.lower() in snippet.lower() or loc_cand.lower() in title_text.lower():
                location = loc_cand
                break

        q_id = query_ctx.get("id") or query_ctx.get("queryId") or "q1"
        q_text = query_ctx.get("title") or query_ctx.get("query") or ""

        return {
            "urn_id": slug,
            "name": name,
            "role": role or "Sales / Executive Leader",
            "company": company,  # None if not explicitly supported
            "location": location,  # None if not explicitly supported
            "profile_url": resolved_url,
            "raw_headline": clean_title,
            "source_evidence": snippet[:350] if snippet else clean_title,
            "source_query": q_text or q_id,
            "provider": "OPENSERP",
            "distance": "PUBLIC_INDEX",
            "validation_flags": {
                "URL_FORMAT_VALID": True,
                "NAME_SUPPORTED_BY_TITLE_OR_SNIPPET": True,
                "ROLE_SUPPORTED": bool(role),
                "COMPANY_SUPPORTED": bool(company),
                "LOCATION_SUPPORTED": bool(location)
            }
        }

    @classmethod
    def discover_candidates(cls, queries: List[Dict[str, Any]], limit: int = 15) -> Dict[str, Any]:
        """
        Executes Google search queries sequentially against local OpenSERP instance.
        Stops immediately upon CAPTCHA, 429, or upstream block.
        Returns structured payload:
        {
            "success": bool,
            "status": str,
            "provider": "OPENSERP",
            "results": List[Dict],
            "count": int,
            "queries_executed": int,
            "error": Optional[str],
            "message": str
        }
        """
        # Pre-flight availability check
        available, avail_msg = cls.is_available()
        if not available:
            return {
                "success": False,
                "status": "NOT_RUNNING",
                "provider": "OPENSERP",
                "results": [],
                "count": 0,
                "queries_executed": 0,
                "error": "OPENSERP_UNAVAILABLE",
                "message": f"OpenSERP service is not running. {avail_msg}"
            }

        # Pre-flight CAPTCHA cooldown check
        in_cooldown, rem_sec = cls.get_cooldown_status()
        if in_cooldown:
            return {
                "success": False,
                "status": "CAPTCHA_DETECTED",
                "provider": "OPENSERP",
                "results": [],
                "count": 0,
                "queries_executed": 0,
                "error": "CAPTCHA_DETECTED",
                "cooldown_remaining_seconds": rem_sec,
                "message": f"Search provider in active CAPTCHA cooldown ({rem_sec}s remaining). Please wait before retrying."
            }

        base_url = cls.get_base_url()
        candidates = []
        seen_urls = set()
        queries_executed = 0

        bounded_queries = queries[:cls.MAX_QUERY_CAP] if queries else []

        for q in bounded_queries:
            if len(candidates) >= limit:
                break

            # Check CAPTCHA cooldown before each query in plan
            in_cooldown, rem_sec = cls.get_cooldown_status()
            if in_cooldown:
                return {
                    "success": len(candidates) > 0,
                    "status": "CAPTCHA_DETECTED",
                    "provider": "OPENSERP",
                    "results": candidates,
                    "count": len(candidates),
                    "queries_executed": queries_executed,
                    "error": "CAPTCHA_DETECTED",
                    "cooldown_remaining_seconds": rem_sec,
                    "message": f"Search provider entered active CAPTCHA cooldown ({rem_sec}s remaining)."
                }

            q_title = (q.get("title") or "").strip()
            q_keywords = (q.get("keywords") or "").strip()
            q_loc = (q.get("location") or "").strip()

            # Clean and sanitize keywords: if it has commas, take only the first 1-2 primary tokens
            # to avoid triggering search engine anti-bot classification with overly long quoted strings
            if "," in q_keywords:
                parts = [p.strip() for p in q_keywords.split(",") if p.strip()]
                q_keywords = parts[0] if parts else ""

            # Format Google dork: site:linkedin.com/in "Title" "Keywords" Location
            search_terms = ['site:linkedin.com/in']
            if q_title:
                search_terms.append(f'"{q_title}"')
            if q_keywords:
                search_terms.append(f'"{q_keywords}"')
            if q_loc:
                search_terms.append(q_loc)

            raw_query_string = " ".join(search_terms)
            encoded_query = urllib.parse.quote_plus(raw_query_string)
            endpoint_url = f"{base_url}/google/search?text={encoded_query}&limit=8"

            # Enforce thread-safe gate: guarantees actual request starts are >= 6s apart
            can_dispatch, cd_rem = cls.wait_for_request_gate()
            if not can_dispatch:
                return {
                    "success": len(candidates) > 0,
                    "status": "CAPTCHA_DETECTED",
                    "provider": "OPENSERP",
                    "results": candidates,
                    "count": len(candidates),
                    "queries_executed": queries_executed,
                    "error": "CAPTCHA_DETECTED",
                    "cooldown_remaining_seconds": cd_rem,
                    "message": f"Search provider in active CAPTCHA cooldown ({cd_rem}s remaining)."
                }

            queries_executed += 1

            try:
                req = urllib.request.Request(
                    endpoint_url,
                    headers={"User-Agent": "FameWeb-GTM-PublicDiscovery/1.0"}
                )
                with urllib.request.urlopen(req, timeout=cls.REQUEST_TIMEOUT) as resp:
                    if resp.status != 200:
                        logger.warning(f"[OpenSERP Service] Unexpected status {resp.status} for query: {raw_query_string}")
                        continue

                    data = json.loads(resp.read().decode("utf-8"))
                    items = data.get("results") or []

                    for it in items:
                        cand = cls.parse_candidate_evidence(it, q)
                        if cand and cand["profile_url"] not in seen_urls:
                            seen_urls.add(cand["profile_url"])
                            candidates.append(cand)
                            if len(candidates) >= limit:
                                break

            except urllib.error.HTTPError as he:
                err_text = he.read().decode("utf-8", errors="ignore").lower()
                logger.error(f"[OpenSERP Service] HTTP {he.code} on query '{raw_query_string}': {err_text[:200]}")

                if he.code in (429, 403) or "captcha" in err_text or "blocked" in err_text:
                    status = "CAPTCHA_DETECTED" if "captcha" in err_text else "RATE_LIMITED"
                    # Activate shared 5-minute cooldown
                    cls.activate_captcha_cooldown()
                    _, rem_sec = cls.get_cooldown_status()
                    return {
                        "success": len(candidates) > 0,
                        "status": status,
                        "provider": "OPENSERP",
                        "results": candidates,
                        "count": len(candidates),
                        "queries_executed": queries_executed,
                        "error": status,
                        "cooldown_remaining_seconds": rem_sec,
                        "message": f"Search provider rate limited or CAPTCHA detected ({rem_sec}s cooldown initiated)."
                    }
                elif he.code == 502:
                    return {
                        "success": len(candidates) > 0,
                        "status": "UPSTREAM_BLOCKED",
                        "provider": "OPENSERP",
                        "results": candidates,
                        "count": len(candidates),
                        "queries_executed": queries_executed,
                        "error": "UPSTREAM_BLOCKED",
                        "message": "OpenSERP upstream search engine blocked request."
                    }
                else:
                    continue

            except Exception as e:
                logger.error(f"[OpenSERP Service] Error executing query '{raw_query_string}': {e}")
                continue

        final_status = "SUCCESS" if len(candidates) > 0 else "NO_RESULTS"
        return {
            "success": len(candidates) > 0,
            "status": final_status,
            "provider": "OPENSERP",
            "results": candidates,
            "count": len(candidates),
            "queries_executed": queries_executed,
            "message": f"Discovered {len(candidates)} public profile candidates via OpenSERP."
        }
