"""
Lead Enrichment Service.
Safe public-source enrichment for manually selected, Gemini-qualified leads.
Discovers:
- Explicitly published named business email vs generic company address.
- Explicitly published business phone (individual vs company line).
- Official company domain and website.
- DNS MX configuration (without false claim of email verification).

Strict Boundaries:
- NO email guessing or permutations.
- NO SMTP RCPT TO or mailbox probing.
- NO scraping beyond standard public HTTP GET / public search snippets.
- Preserves full source provenance, timestamps, and confidence classifications.
"""

import re
import time
import logging
import ipaddress
import socket
import ssl
import certifi
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from bs4 import BeautifulSoup
import dns.resolver

logger = logging.getLogger(__name__)

BLOCKED_HOSTNAMES = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "instance-data", "169.254.169.254"
}

GENERIC_EMAIL_PREFIXES = {
    "info", "support", "sales", "contact", "help", "hello", "press",
    "media", "team", "office", "careers", "jobs", "inquiries", "billing",
    "admin", "marketing", "hr", "general", "feedback", "service"
}

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "protonmail.com", "zoho.com", "mail.com", "gmx.com"
}

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Validates redirect targets against SSRF/private networks before allowing redirection.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not LeadEnrichmentService.is_safe_public_url(newurl):
            raise urllib.error.HTTPError(newurl, 403, f"Blocked unsafe redirect target: {newurl}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LeadEnrichmentService:
    @classmethod
    def is_safe_ip(cls, ip_str: str) -> bool:
        """
        Validates an IP address using Python's ipaddress library.
        Covers:
        - IPv4 private, loopback, link-local, unspecified, multicast, and reserved addresses.
        - IPv6 loopback, unique-local, link-local, unspecified, and multicast addresses.
        - IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1).
        - Any non-global destination address.
        """
        if not ip_str or not isinstance(ip_str, str):
            return False
        try:
            ip = ipaddress.ip_address(ip_str.strip())
            # Unpack IPv4-mapped IPv6 address (e.g., ::ffff:192.168.1.1)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped

            if not ip.is_global:
                return False
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
            return True
        except Exception:
            return False

    @classmethod
    def is_safe_public_url(cls, url: str) -> bool:
        """
        Validates that a URL is http/https and does NOT resolve to localhost, private IP,
        link-local, cloud metadata service, or multicast ranges.
        """
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            hostname_lower = hostname.lower().strip()
            if hostname_lower in BLOCKED_HOSTNAMES:
                return False

            # Check if hostname is a raw IP literal
            try:
                return cls.is_safe_ip(hostname_lower)
            except ValueError:
                pass

            # Not a raw IP literal; resolve DNS
            try:
                addr_info = socket.getaddrinfo(hostname_lower, None)
                if not addr_info:
                    return False
                for entry in addr_info:
                    sockaddr = entry[4]
                    ip_str = sockaddr[0]
                    if not cls.is_safe_ip(ip_str):
                        logger.warning(f"[Enrichment SSRF Guard] Blocked {url}: resolves to non-global IP {ip_str}")
                        return False
            except socket.gaierror:
                return False

            return True
        except Exception as e:
            logger.debug(f"[Enrichment SSRF Guard] Validation failed for {url}: {e}")
            return False
    @classmethod
    def check_domain_mx(cls, domain: str) -> Dict[str, Any]:
        """
        Performs DNS MX lookup to determine whether domain has mail servers configured.
        NOTE: Establishes domain mail readiness only; NEVER proves an individual mailbox exists.
        """
        if not domain or "." not in domain or len(domain) < 4:
            return {
                "status": "NOT_APPLICABLE",
                "configured": False,
                "records": [],
                "explanation": "No valid domain provided for MX check."
            }

        clean_domain = domain.lower().strip().lstrip("www.")
        try:
            answers = dns.resolver.resolve(clean_domain, 'MX', lifetime=5.0)
            mx_hosts = [str(r.exchange).rstrip(".") for r in answers]
            return {
                "status": "DOMAIN_MX_CONFIGURED",
                "configured": True,
                "records": mx_hosts[:3],
                "explanation": f"Domain '{clean_domain}' has {len(mx_hosts)} active MX record(s). Establishes domain mail server configuration only; does NOT verify individual address existence."
            }
        except dns.resolver.NoAnswer:
            return {
                "status": "NO_MX_RECORDS",
                "configured": False,
                "records": [],
                "explanation": f"Domain '{clean_domain}' has no active MX records."
            }
        except dns.resolver.NXDOMAIN:
            return {
                "status": "DOMAIN_NOT_FOUND",
                "configured": False,
                "records": [],
                "explanation": f"Domain '{clean_domain}' does not exist (NXDOMAIN)."
            }
        except Exception as e:
            return {
                "status": "LOOKUP_ERROR",
                "configured": False,
                "records": [],
                "explanation": f"DNS MX check failed: {str(e)}"
            }

    @classmethod
    def classify_email(cls, email: str, person_name: Optional[str] = None) -> Tuple[str, str]:
        """
        Classifies an email as:
        - NAMED_BUSINESS_EMAIL
        - GENERIC_COMPANY_EMAIL
        - PERSONAL_EMAIL
        """
        local_part, domain = email.lower().split("@", 1)
        if domain in GENERIC_EMAIL_DOMAINS:
            return "PERSONAL_EMAIL", "Email belongs to a public consumer webmail provider (e.g., Gmail, Yahoo)."

        if local_part in GENERIC_EMAIL_PREFIXES:
            return "GENERIC_COMPANY_EMAIL", f"Local part '{local_part}' is a known shared corporate department prefix."

        # Check if local part matches person's name tokens
        if person_name:
            name_tokens = [re.sub(r'[^a-z0-9]', '', t.lower()) for t in person_name.split() if len(t) >= 2]
            if any(tok in local_part for tok in name_tokens):
                return "NAMED_BUSINESS_EMAIL", f"Local part '{local_part}' matches tokens from prospect name '{person_name}' on corporate domain."

        return "NAMED_BUSINESS_EMAIL", f"Corporate address on domain '{domain}'."

    @classmethod
    def resolve_official_domain(
        cls,
        company_name: str,
        profile_evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Attempts to resolve official company website domain using credible evidence linking
        the company to the domain.
        STRICT RULES:
        - Never guesses or probes arbitrary candidate domains or TLD variations.
        - A company name that resembles a domain (e.g. 'sell.do') is NOT sufficient evidence of domain ownership.
        - Requires an explicitly supplied website/domain field with credible provenance (e.g., from verified candidate/company profile metadata).
        - Preserves source URL, source type, and confidence classification.
        - Leaves domain None if association cannot be established or is ambiguous.
        """
        if not company_name or len(company_name.strip()) < 2:
            return None

        clean_comp = company_name.strip().lower()
        if clean_comp in ("organization", "target company", "confidential", "stealth", "independent", "freelance", "self-employed"):
            return None

        # Check if profile_evidence provides an explicit official website or domain
        ev_url = None
        source_type = "OFFICIAL_PROFILE_METADATA"
        if profile_evidence and isinstance(profile_evidence, dict):
            ev_url = (
                profile_evidence.get("website_url")
                or profile_evidence.get("company_website")
                or profile_evidence.get("domain")
            )
            if profile_evidence.get("website_source"):
                source_type = profile_evidence["website_source"]

        if ev_url and isinstance(ev_url, str):
            ev_url_clean = ev_url.strip()
            if not ev_url_clean.startswith("http"):
                ev_url_clean = f"https://{ev_url_clean}"

            if cls.is_safe_public_url(ev_url_clean):
                parsed = urllib.parse.urlparse(ev_url_clean)
                hostname = parsed.hostname
                if hostname:
                    clean_dom = hostname.lower().lstrip("www.")
                    return {
                        "domain": clean_dom,
                        "website_url": ev_url_clean,
                        "source_type": source_type,
                        "confidence": "HIGH"
                    }

        # No credible external/profile evidence linking company to domain
        logger.debug(f"[Enrichment Service] No credible domain evidence for company '{company_name}'. Leaving domain null.")
        return None

    @classmethod
    def fetch_public_web_text(cls, url: str) -> Optional[str]:
        """
        Safely fetches public HTML and extracts visible text content.
        Enforces:
        - SSRF validation on initial URL and all redirect destinations.
        - Connection-time IP verification on socket.create_connection to neutralize DNS rebinding.
        - Strict timeout (6.0s).
        - Maximum response size (500KB).
        - Non-bypass restrictions.
        """
        if not cls.is_safe_public_url(url):
            logger.warning(f"[Enrichment Guard] Blocked unsafe or private URL fetch attempt: {url}")
            return None

        orig_create_connection = socket.create_connection

        def ssrf_safe_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
            host, port = address
            try:
                addr_info = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
                if not addr_info:
                    raise PermissionError(f"SSRF Guard: no address resolved for {host}")
                for entry in addr_info:
                    ip_str = entry[4][0]
                    if not cls.is_safe_ip(ip_str):
                        raise PermissionError(f"SSRF Guard: connection to non-global IP {ip_str} blocked at socket connect")
                af, socktype, proto, canonname, sa = addr_info[0]
                sock = socket.socket(af, socktype, proto)
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                sock.connect(sa)
                return sock
            except Exception as conn_err:
                logger.warning(f"[Enrichment SSRF Guard] Socket connection blocked or failed for {host}:{port} -> {conn_err}")
                raise

        try:
            # Install connection-time socket verification to prevent DNS rebinding
            socket.create_connection = ssrf_safe_create_connection

            # Configure SSL context with certifi roots if available
            ssl_context = None
            try:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                ssl_context = ssl.create_default_context()

            https_handler = urllib.request.HTTPSHandler(context=ssl_context)
            opener = urllib.request.build_opener(SafeRedirectHandler(), https_handler)

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with opener.open(req, timeout=6) as resp:
                final_url = resp.geturl()
                if not cls.is_safe_public_url(final_url):
                    logger.warning(f"[Enrichment Guard] Blocked unsafe final redirect destination: {final_url}")
                    return None

                status_code = getattr(resp, 'status', 200)
                if status_code != 200:
                    return None

                # Limit to 500KB
                raw = resp.read(500000)
                soup = BeautifulSoup(raw, 'html.parser')
                # Remove scripts and styles
                for s in soup(["script", "style", "noscript", "svg"]):
                    s.extract()
                return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.debug(f"[Enrichment Service] Fetch error for {url}: {e}")
            return None
        finally:
            socket.create_connection = orig_create_connection

    @classmethod
    def enrich_qualified_lead(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main enrichment executor for a single qualified lead.
        Extracts only explicitly published public business emails and phone numbers.
        """
        now_iso = datetime.utcnow().isoformat()
        person_name = lead.get("name")
        company_name = lead.get("company")
        profile_url = lead.get("profile_url")

        findings = {
            "enriched_at": now_iso,
            "prospect_name": person_name,
            "company_name": company_name,
            "official_domain": None,
            "domain_mx": None,
            "public_named_email": None,
            "public_generic_email": None,
            "public_business_phone": None,
            "sources": [],
            "status": "NOT_FOUND"
        }

        # 1. Company Domain & MX Configuration
        comp_info = cls.resolve_official_domain(company_name, profile_evidence=lead)
        if comp_info:
            domain = comp_info["domain"]
            findings["official_domain"] = {
                "domain": domain,
                "website_url": comp_info["website_url"],
                "source_type": comp_info["source_type"],
                "confidence": comp_info["confidence"],
                "discovered_at": now_iso
            }
            findings["sources"].append({
                "type": "COMPANY_HOMEPAGE",
                "url": comp_info["website_url"]
            })
            # DNS MX check
            findings["domain_mx"] = cls.check_domain_mx(domain)

            # 2. Check public contact / team page if official website exists
            for path in ["/contact", "/contact-us", "/about", "/team", "/leadership"]:
                contact_url = f"{comp_info['website_url'].rstrip('/')}{path}"
                page_text = cls.fetch_public_web_text(contact_url)
                if not page_text:
                    continue

                # Search explicitly published emails
                found_emails = EMAIL_REGEX.findall(page_text)
                for em in found_emails:
                    em_clean = em.strip().lower()
                    if em_clean.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
                        continue

                    classification, rationale = cls.classify_email(em_clean, person_name)
                    if classification == "NAMED_BUSINESS_EMAIL" and not findings["public_named_email"]:
                        findings["public_named_email"] = {
                            "email": em_clean,
                            "classification": "NAMED_BUSINESS_EMAIL",
                            "status": "PUBLICLY_PUBLISHED",
                            "source_url": contact_url,
                            "source_type": "OFFICIAL_SOURCE",
                            "rationale": rationale,
                            "extracted_at": now_iso
                        }
                    elif classification == "GENERIC_COMPANY_EMAIL" and not findings["public_generic_email"]:
                        findings["public_generic_email"] = {
                            "email": em_clean,
                            "classification": "GENERIC_COMPANY_EMAIL",
                            "status": "PUBLICLY_PUBLISHED",
                            "source_url": contact_url,
                            "source_type": "OFFICIAL_SOURCE",
                            "rationale": rationale,
                            "extracted_at": now_iso
                        }

                # Search explicitly published phone numbers
                if not findings["public_business_phone"]:
                    found_phones = PHONE_REGEX.findall(page_text)
                    for ph in found_phones:
                        ph_clean = ph.strip()
                        if len(re.sub(r'\D', '', ph_clean)) >= 8:
                            findings["public_business_phone"] = {
                                "phone": ph_clean,
                                "type": "COMPANY_BUSINESS_LINE",
                                "status": "PUBLICLY_PUBLISHED",
                                "source_url": contact_url,
                                "source_type": "OFFICIAL_SOURCE",
                                "extracted_at": now_iso
                            }
                            break

                if findings["public_named_email"] and findings["public_business_phone"]:
                    break

        # Status categorization
        if findings["public_named_email"]:
            findings["status"] = "ENRICHED_NAMED_CONTACT"
        elif findings["public_generic_email"] or findings["public_business_phone"]:
            findings["status"] = "ENRICHED_COMPANY_CONTACT"
        elif findings["official_domain"]:
            findings["status"] = "DOMAIN_RESOLVED_ONLY"
        else:
            findings["status"] = "NOT_FOUND"

        return findings

