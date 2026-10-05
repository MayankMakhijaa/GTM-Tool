import re
import socket
import ipaddress
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import requests
from config import Config

logger = logging.getLogger(__name__)

# Common public/personal email domains to reject for automated company identification
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "aim.com",
    "proton.me", "protonmail.com", "zoho.com", "mail.com", "gmx.com",
    "gmx.net", "yandex.com", "fastmail.com", "hushmail.com", "tutanota.com"
}


def extract_and_normalize_domain(email: str) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Extracts and normalizes the domain from an email address.
    Returns (domain, is_personal_provider, error_message).
    """
    if not email or not isinstance(email, str):
        return None, False, "Email address is required"

    email = email.strip().lower()
    if "@" not in email:
        return None, False, "Invalid email format"

    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, False, "Invalid email format"

    domain = parts[1].strip()

    # Reject IP address domains
    try:
        ipaddress.ip_address(domain)
        return None, False, "IP addresses are not valid email domains"
    except ValueError:
        pass

    # Domain syntax check
    domain_regex = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$"
    if not re.match(domain_regex, domain):
        return None, False, "Invalid domain syntax"

    # Check for personal email domain
    if domain in PERSONAL_EMAIL_DOMAINS:
        return domain, True, None

    return domain, False, None


def is_safe_ip(ip_str: str) -> bool:
    """
    Checks if an IP address is safe to connect to (not private, loopback, link-local, or metadata endpoint).
    """
    try:
        ip = ipaddress.ip_address(ip_str)

        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False

        # Additional explicit checks for Cloud Metadata (169.254.169.254) and 0.0.0.0
        str_val = str(ip)
        if str_val in ("169.254.169.254", "0.0.0.0"):
            return False

        return True
    except ValueError:
        return False


def resolve_and_validate_hostname(hostname: str) -> Tuple[bool, Optional[str]]:
    """
    Resolves hostname DNS and checks all resulting IP addresses against SSRF rules.
    """
    try:
        # Strip port if present
        if ":" in hostname:
            hostname = hostname.split(":")[0]

        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False, None

        primary_ip = None
        for item in addr_info:
            ip_str = item[4][0]
            if not is_safe_ip(ip_str):
                logger.warning(f"SSRF block: Hostname {hostname} resolved to unsafe IP {ip_str}")
                return False, ip_str
            if not primary_ip:
                primary_ip = ip_str

        return True, primary_ip
    except Exception as e:
        logger.warning(f"DNS resolution failed for hostname {hostname}: {str(e)}")
        return False, None


def fetch_domain_homepage(domain: str) -> Dict[str, Any]:
    """
    Safely fetches a domain's homepage following redirects with SSRF protections.
    """
    protocols = ["https://", "http://"]
    
    for proto in protocols:
        current_url = f"{proto}{domain}"
        max_redirects = 5
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "FamewebBot/1.0 (+https://fameweb.ai)"
        })

        redirect_count = 0
        success = False
        final_url = current_url
        response_text = ""
        status_code = 0

        while redirect_count < max_redirects:
            parsed = urlparse(current_url)
            if parsed.scheme not in ("http", "https"):
                break

            hostname = parsed.hostname
            if not hostname:
                break

            # Validate IP address before connecting
            safe, ip = resolve_and_validate_hostname(hostname)
            if not safe:
                logger.warning(f"Blocked request to unsafe hostname: {hostname}")
                break

            try:
                res = session.get(current_url, timeout=5.0, allow_redirects=False, stream=True)
                status_code = res.status_code

                # Handle redirect
                if status_code in (301, 302, 303, 307, 308):
                    location = res.headers.get("Location")
                    if not location:
                        break
                    
                    # Resolve relative redirect URLs
                    if location.startswith("/"):
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"
                    elif not location.startswith(("http://", "https://")):
                        location = f"{parsed.scheme}://{location}"

                    current_url = location
                    redirect_count += 1
                    continue

                if status_code == 200:
                    content_type = res.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type and "text/plain" not in content_type:
                        logger.warning(f"Non-HTML content type received from {current_url}: {content_type}")
                        break

                    # Limit read size to max 1MB
                    content_bytes = bytearray()
                    for chunk in res.iter_content(chunk_size=8192):
                        content_bytes.extend(chunk)
                        if len(content_bytes) > 1024 * 1024:
                            break

                    response_text = content_bytes.decode("utf-8", errors="ignore")
                    final_url = current_url
                    success = True
                    break
                else:
                    break

            except requests.RequestException as req_err:
                logger.debug(f"Request failed for {current_url}: {str(req_err)}")
                break
            except Exception as err:
                logger.warning(f"Unexpected error fetching {current_url}: {str(err)}")
                break

        if success:
            title, meta_desc, og_site_name = parse_html_metadata(response_text)
            return {
                "success": True,
                "final_url": final_url,
                "status_code": status_code,
                "title": title,
                "meta_description": meta_desc,
                "og_site_name": og_site_name,
                "html_snippet": clean_html_snippet(response_text)
            }

    return {"success": False, "message": "Website unreachable or inaccessible"}


def parse_html_metadata(html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extracts title, meta description, and og:site_name from HTML text using regex.
    """
    title = None
    meta_desc = None
    og_site_name = None

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()

    meta_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
    if not meta_match:
        meta_match = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    if meta_match:
        meta_desc = re.sub(r"\s+", " ", meta_match.group(1)).strip()

    og_match = re.search(r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
    if not og_match:
        og_match = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*property=["\']og:site_name["\']', html, re.IGNORECASE)
    if og_match:
        og_site_name = re.sub(r"\s+", " ", og_match.group(1)).strip()

    return title, meta_desc, og_site_name


def clean_html_snippet(html: str, max_chars: int = 1500) -> str:
    """
    Strips scripts, styles, and tags to create a clean text snippet.
    """
    # Remove script and style elements
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# Set of common country-code second-level public suffixes
COMMON_TWO_PART_TLDS = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "net.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in",
    "co.jp", "or.jp", "ne.jp", "ac.jp", "ad.jp", "ed.jp", "go.jp",
    "co.nz", "net.nz", "org.nz", "ac.nz", "govt.nz",
    "com.br", "net.br", "org.br", "gov.br",
    "com.sg", "net.sg", "org.sg", "edu.sg", "gov.sg",
    "com.tw", "org.tw", "net.tw", "edu.tw",
    "co.za", "net.za", "org.za", "web.za",
    "com.mx", "org.mx", "net.mx", "edu.mx",
    "com.ar", "net.ar", "org.ar",
    "com.my", "net.my", "org.my",
    "com.tr", "net.tr", "org.tr",
    "co.kr", "ne.kr", "or.kr", "re.kr",
    "com.hk", "org.hk", "net.hk",
    "com.ph", "org.ph", "net.ph",
    "com.vn", "net.vn", "org.vn",
    "com.co", "net.co", "nom.co",
    "com.ua", "net.ua", "org.ua"
}


def get_root_domain(domain_or_url: str) -> str:
    """
    Extracts the base organizational domain (e.g. acme.com from www.acme.com,
    or acme.co.uk from mail.acme.co.uk).
    """
    if not domain_or_url:
        return ""
    if "://" in domain_or_url:
        domain = urlparse(domain_or_url).netloc
    else:
        domain = domain_or_url
    domain = domain.split(":")[0].lower().strip()
    parts = [p for p in domain.split(".") if p]
    if len(parts) <= 2:
        return domain

    # Check for known 2-part TLD (e.g. acme.co.uk -> co.uk)
    two_part_tld = f"{parts[-2]}.{parts[-1]}"
    if two_part_tld in COMMON_TWO_PART_TLDS and len(parts) >= 3:
        return f"{parts[-3]}.{two_part_tld}"

    # Default fallback: last 2 parts (e.g., www.acme.com -> acme.com)
    return f"{parts[-2]}.{parts[-1]}"


def analyze_company_with_gemini(domain: str, fetch_res: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Uses Gemini API to infer company name, official website, and identification status.
    Returns (company_name, official_website, identification_status).
    """
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        return heuristic_company_analysis(domain, fetch_res)

    try:
        from google import genai
        from google.genai import types
        import json

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are a corporate entity recognition system.
Analyze the following webpage discovery metadata for the domain "{domain}".

METADATA:
Final URL: {fetch_res.get('final_url')}
Title: {fetch_res.get('title')}
OG Site Name: {fetch_res.get('og_site_name')}
Meta Description: {fetch_res.get('meta_description')}
Page Text Snippet: {fetch_res.get('html_snippet')}

TASK:
1. Determine the official Company Name for this website/domain.
2. Determine the official public website URL.
3. Assess whether the domain explicitly represents a legitimate business company website:
   - "CONFIRMED": Only if the relationship between email domain ("{domain}") and official company website is 100% verified and clear.
   - "NEEDS_CONFIRMATION": If the association is ambiguous, the website domain is different from the email domain, or the brand identity requires user confirmation.

Return a JSON object matching this EXACT schema:
{{
  "company_name": "Official Company Name",
  "official_website": "https://officialcompany.com",
  "identification_status": "CONFIRMED" | "NEEDS_CONFIRMATION"
}}
"""

        models_to_try = ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
        result_text = None
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        seed=42,
                        response_mime_type="application/json"
                    )
                )
                result_text = response.text
                if result_text:
                    break
            except Exception:
                continue
        if result_text:
            data = json.loads(result_text)
            comp_name = data.get("company_name")
            web_url = data.get("official_website") or fetch_res.get("final_url")
            status = data.get("identification_status", "NEEDS_CONFIRMATION")

            # Cross-Domain Association Check:
            # If email domain root != website root URL, force NEEDS_CONFIRMATION
            email_root = get_root_domain(domain)
            web_root = get_root_domain(web_url)
            if email_root and web_root and email_root != web_root:
                logger.info(f"Cross-domain detected ({email_root} vs {web_root}). Forcing NEEDS_CONFIRMATION.")
                status = "NEEDS_CONFIRMATION"

            if status not in ("CONFIRMED", "NEEDS_CONFIRMATION"):
                status = "NEEDS_CONFIRMATION"
            return comp_name, web_url, status
    except Exception as e:
        logger.warning(f"Gemini API call failed during domain discovery: {str(e)}")

    return heuristic_company_analysis(domain, fetch_res)


def heuristic_company_analysis(domain: str, fetch_res: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Fallback heuristic company identification.
    Distinguishes between verified metadata matches and unverified suggested names.
    Weak titles and synthesized names NEVER produce a CONFIRMED identity.
    """
    final_url = fetch_res.get("final_url") or f"https://{domain}"
    og_name = fetch_res.get("og_site_name")
    title = fetch_res.get("title")

    email_root = get_root_domain(domain)
    web_root = get_root_domain(final_url)

    # Cross-domain check: if email domain root != website root, require user confirmation
    if email_root and web_root and email_root != web_root:
        company_name = og_name or (re.split(r"[|\-:]", title)[0].strip() if title else domain.split(".")[0].capitalize())
        return company_name, final_url, "NEEDS_CONFIRMATION"

    # In heuristic mode, treat OpenGraph as supporting evidence, but require confirmation unless exact brand name match
    if og_name and (email_root.split(".")[0] in og_name.lower() or og_name.lower() in email_root):
        return og_name, final_url, "CONFIRMED"
    elif title:
        # Title snippet is only a suggested name, requiring user confirmation
        company_name = re.split(r"[|\-:]", title)[0].strip()
        return company_name, final_url, "NEEDS_CONFIRMATION"
    else:
        # Capitalized domain is only a synthesized suggestion, requiring user confirmation
        company_name = domain.split(".")[0].capitalize()
        return company_name, final_url, "NEEDS_CONFIRMATION"


def identify_company_from_email(email: str) -> Dict[str, Any]:
    """
    Main entry point for domain identification from a given email address.
    """
    domain, is_personal, error_msg = extract_and_normalize_domain(email)

    if error_msg or not domain:
        return {
            "success": False,
            "email_domain": None,
            "company_name": None,
            "official_website": None,
            "identification_status": "FAILED",
            "requires_user_confirmation": True,
            "message": error_msg or "Invalid or unusable email domain."
        }

    if is_personal:
        return {
            "success": True,
            "email_domain": domain,
            "company_name": None,
            "official_website": None,
            "identification_status": "NOT_FOUND",
            "requires_user_confirmation": True,
            "message": "Registered email uses a public email provider. Please enter your company's official website manually."
        }

    # Fetch homepage safely
    fetch_res = fetch_domain_homepage(domain)

    if not fetch_res.get("success"):
        return {
            "success": True,
            "email_domain": domain,
            "company_name": None,
            "official_website": None,
            "identification_status": "NOT_FOUND",
            "requires_user_confirmation": True,
            "message": "No accessible public website found for domain. Please enter your company website manually."
        }

    # Perform analysis (Gemini or heuristic)
    company_name, official_website, status = analyze_company_with_gemini(domain, fetch_res)

    requires_confirmation = (status != "CONFIRMED")
    message = "Company identified successfully." if status == "CONFIRMED" else "Please confirm your company's official website."

    return {
        "success": True,
        "email_domain": domain,
        "company_name": company_name,
        "official_website": official_website,
        "identification_status": status,
        "requires_user_confirmation": requires_confirmation,
        "message": message
    }


def discover_company_for_user(user_id: int) -> Dict[str, Any]:
    """
    Retrieves the authenticated user's email from database and runs company domain identification.
    """
    from app.repositories.user_repository import get_user_by_id

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Authenticated user not found")

    return identify_company_from_email(user.email_id)
