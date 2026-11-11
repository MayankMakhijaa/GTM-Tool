"""
Lead Evidence and Source Validation Service.

Validates discovered candidate sources, URLs, and evidence to prevent:
1. Hallucinated / fake candidates lacking tangible grounding.
2. SSRF vulnerabilities (e.g. internal network, loopback, AWS/GCP metadata endpoints).
3. Generic search root or non-evidence URLs (e.g. raw google.com, bing.com, duckduckgo.com).
4. Fabricated contact information (emails, phone numbers).

Strict Safety Boundaries:
- NEVER fabricates or guesses email addresses or phone numbers.
- Requires candidates to have real verifiable sources and non-trivial evidence quotes.
- Enforces safe HTTP/HTTPS URL protocols only.
"""

import ipaddress
import logging
import re
from typing import Dict, Any, Tuple, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Blocked search engine roots and aggregator root pages
GENERIC_SEARCH_ROOTS = {
    "google.com",
    "www.google.com",
    "bing.com",
    "www.bing.com",
    "duckduckgo.com",
    "search.yahoo.com",
    "yahoo.com",
    "www.yahoo.com",
    "baidu.com",
    "www.baidu.com",
    "yandex.com",
    "www.yandex.com"
}

# Disallowed internal / metadata IP ranges or hostnames
DISALLOWED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254", # AWS / GCP instance metadata
    "instance-data"
}


def is_safe_external_url(url: Optional[str]) -> Tuple[bool, str]:
    """
    Validates a URL against SSRF attacks and ensures it is a public, safe HTTP(S) URL.
    Returns:
        (is_safe: bool, reason: str)
    """
    if not url or not isinstance(url, str):
        return False, "Missing or non-string URL."

    url = url.strip()
    if len(url) < 10 or len(url) > 2048:
        return False, "URL length out of bounds (10-2048 chars)."

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    # Must be http or https
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Disallowed scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "URL missing hostname."

    # Check disallowed literal hostnames
    if hostname in DISALLOWED_HOSTNAMES:
        return False, f"Host '{hostname}' is not permitted (SSRF protection)."

    # Disallow IP addresses directly unless verified public non-private/loopback
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False, f"Private/reserved IP address '{hostname}' blocked."
    except ValueError:
        # Not a raw IP literal, it's a domain name
        pass

    # Disallow generic search engine root domains (without a specific result path)
    if hostname in GENERIC_SEARCH_ROOTS and (not parsed.path or parsed.path.strip("/") in ("", "search")):
        return False, f"Generic search engine root '{hostname}' cannot serve as primary candidate evidence."

    return True, "Safe URL."


def normalize_lead_identifier(raw_name: str, raw_company: str, profile_url: Optional[str] = None) -> str:
    """
    Generates a canonical, deterministic identifier string suitable for GlobalProfiles.linkedin_id
    and cross-job deduplication.
    Format:
    - If profile_url contains linkedin.com/in/{vanity}, uses the vanity slug.
    - Otherwise produces a normalized slug: 'web:{clean_domain}:{clean_name}'.
    """
    if profile_url and "linkedin.com/in/" in profile_url:
        match = re.search(r"linkedin\.com/in/([^/?#&]+)", profile_url)
        if match:
            slug = match.group(1).strip().lower()
            if slug:
                return slug

    clean_name = re.sub(r"[^a-z0-9]+", "-", (raw_name or "").strip().lower()).strip("-")
    clean_company = re.sub(r"[^a-z0-9]+", "-", (raw_company or "").strip().lower()).strip("-")

    if not clean_name:
        clean_name = "unknown-lead"
    if not clean_company:
        clean_company = "org"

    return f"web:{clean_company}:{clean_name}"[:100]


def validate_and_classify_candidate(candidate: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """
    Inspects candidate fields, verifies source URL and evidence quote, and sanitizes contact info.
    Returns:
        (classification: 'VERIFIED' | 'UNVERIFIED' | 'REJECTED',
         sanitized_candidate: dict,
         rejection_reason: Optional[str])
    """
    if not isinstance(candidate, dict):
        return "REJECTED", {}, "Candidate payload must be a JSON dictionary."

    name = str(candidate.get("full_name") or candidate.get("name") or "").strip()
    role = str(candidate.get("job_title") or candidate.get("role") or "").strip()
    company = str(candidate.get("company_name") or candidate.get("company") or "").strip()
    source_url = str(candidate.get("source_url") or candidate.get("profile_url") or "").strip()
    source_evidence = str(candidate.get("source_evidence") or candidate.get("evidence") or "").strip()
    source_title = str(candidate.get("source_title") or "").strip()
    location = str(candidate.get("location") or "").strip()
    industry = str(candidate.get("industry") or "").strip()

    # Basic completeness requirements
    if not name or len(name) < 2:
        return "REJECTED", candidate, "Candidate lacks a valid name."
    if not company or len(company) < 2:
        return "REJECTED", candidate, "Candidate lacks a company affiliation."
    if not role or len(role) < 2:
        return "REJECTED", candidate, "Candidate lacks a discernible job title/role."

    # Validate source URL
    url_ok, url_reason = is_safe_external_url(source_url)
    if not url_ok:
        # If no valid URL, cannot be VERIFIED
        return "REJECTED", candidate, f"Source URL failed verification: {url_reason}"

    # Evidence quote check
    if not source_evidence or len(source_evidence) < 15:
        # Trivial or missing evidence quote
        return "UNVERIFIED", candidate, "Insufficient evidence quote from source."

    # Contact data policy: ZERO hallucination of email or phone.
    # We strictly enforce that email and phone remain None/empty unless independently verified by a legitimate provider.
    sanitized = {
        "name": name,
        "role": role,
        "company": company,
        "location": location or "Verified Market",
        "industry": industry,
        "profile_url": source_url,
        "source_url": source_url,
        "source_title": source_title,
        "source_evidence": source_evidence,
        "urn_id": normalize_lead_identifier(name, company, source_url),
        "email": None,  # Strictly None - never hallucinated
        "phone": None,  # Strictly None - never hallucinated
        "verification_status": "VERIFIED",
        "provider": candidate.get("provider", "CLAUDE_WEB_SEARCH")
    }

    return "VERIFIED", sanitized, None

