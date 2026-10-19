import socket
import pytest
from unittest.mock import patch, MagicMock
from app_module import app as flask_app
from app.database import db_session, Base, engine
from app.services.email_service import get_last_test_otp
from app.services.company_discovery_service import (
    extract_and_normalize_domain,
    is_safe_ip,
    resolve_and_validate_hostname,
    identify_company_from_email
)


# Inherits `client` fixture from tests/conftest.py with PostgreSQL fameweb_test DB isolation and safety guards


def create_user_and_login(client, name, email, phone):
    client.post('/api/auth/signup', json={
        "name": name,
        "email": email,
        "phone": phone,
        "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp(email)
    if otp:
        client.post('/api/auth/verify-otp', json={"email": email, "otp": otp})
    res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": "StrongP@ssword123!"
    })
    return res


# 1. Domain Extraction Unit Tests

def test_domain_extraction_valid_business_email():
    domain, is_personal, error = extract_and_normalize_domain("  ALEX@ACME.COM  ")
    assert domain == "acme.com"
    assert is_personal is False
    assert error is None


def test_domain_extraction_subdomain_email():
    domain, is_personal, error = extract_and_normalize_domain("emp@corp.acme.co.uk")
    assert domain == "corp.acme.co.uk"
    assert is_personal is False
    assert error is None


def test_domain_extraction_personal_email():
    domain, is_personal, error = extract_and_normalize_domain("user@gmail.com")
    assert domain == "gmail.com"
    assert is_personal is True
    assert error is None


def test_domain_extraction_invalid_email():
    domain, is_personal, error = extract_and_normalize_domain("notanemail")
    assert domain is None
    assert error == "Invalid email format"


def test_domain_extraction_ip_domain():
    domain, is_personal, error = extract_and_normalize_domain("user@192.168.1.1")
    assert domain is None
    assert "IP addresses are not valid" in error


# 2. SSRF Protection Unit Tests

def test_ssrf_ip_guard_private_ips():
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("10.0.0.1") is False
    assert is_safe_ip("172.16.0.1") is False
    assert is_safe_ip("192.168.1.100") is False
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("0.0.0.0") is False
    assert is_safe_ip("::1") is False


def test_ssrf_ip_guard_public_ips():
    assert is_safe_ip("8.8.8.8") is True
    assert is_safe_ip("93.184.216.34") is True


def test_ssrf_ip_guard_nat64_public():
    # RFC 6052 well-known prefix with public embedded IPv4 addresses
    assert is_safe_ip("64:ff9b::b9e6:3f6b") is True  # Embedded 185.230.63.107 (Wix)
    assert is_safe_ip("64:ff9b::1f2b:a006") is True  # Embedded 31.43.160.6 (Hostinger)


def test_ssrf_ip_guard_nat64_prohibited():
    # RFC 6052 well-known prefix with unsafe embedded IPv4 destinations
    assert is_safe_ip("64:ff9b::7f00:0001") is False  # Loopback 127.0.0.1
    assert is_safe_ip("64:ff9b::a9fe:a9fe") is False  # Cloud metadata 169.254.169.254
    assert is_safe_ip("64:ff9b::0a00:0001") is False  # RFC 1918 Private 10.0.0.1
    assert is_safe_ip("64:ff9b::c0a8:0101") is False  # RFC 1918 Private 192.168.1.1
    assert is_safe_ip("64:ff9b::") is False           # Unspecified 0.0.0.0
    # Unsupported translation prefixes (RFC 8215 local-use /48) must remain blocked
    assert is_safe_ip("64:ff9b:1::b9e6:3f6b") is False


def test_ssrf_ip_guard_native_ipv6():
    # Public native IPv6 destinations
    assert is_safe_ip("2606:4700:4700::1111") is True  # Cloudflare
    assert is_safe_ip("2001:4860:4860::8888") is True  # Google
    # Prohibited native IPv6 destinations
    assert is_safe_ip("::1") is False                  # Loopback
    assert is_safe_ip("::") is False                   # Unspecified
    assert is_safe_ip("fe80::1") is False              # Link-local
    assert is_safe_ip("fc00::1") is False              # Unique local (ULA / private)


def test_ssrf_ip_guard_ipv4_mapped():
    # IPv4-mapped IPv6 (::ffff:0:0/96)
    assert is_safe_ip("::ffff:93.184.216.34") is True
    assert is_safe_ip("::ffff:127.0.0.1") is False
    assert is_safe_ip("::ffff:169.254.169.254") is False
    assert is_safe_ip("::ffff:10.0.0.1") is False


@patch("socket.getaddrinfo")
def test_resolve_and_validate_hostname_ssrf(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (2, 1, 6, '', ('127.0.0.1', 80))
    ]
    safe, ip = resolve_and_validate_hostname("localhost")
    assert safe is False
    assert ip == "127.0.0.1"


@patch("socket.getaddrinfo")
def test_resolve_and_validate_hostname_nat64_public(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('64:ff9b::b9e6:3f6b', 443, 0, 0))
    ]
    safe, ip = resolve_and_validate_hostname("amceducation.in")
    assert safe is True
    assert ip == "64:ff9b::b9e6:3f6b"


@patch("socket.getaddrinfo")
def test_resolve_and_validate_hostname_mixed_dns_rejects(mock_getaddrinfo):
    # Hostname resolves to both a permitted NAT64 IP and a prohibited loopback IP
    mock_getaddrinfo.return_value = [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('64:ff9b::b9e6:3f6b', 443, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))
    ]
    safe, ip = resolve_and_validate_hostname("mixed-domain.example")
    assert safe is False
    assert ip == "127.0.0.1"


# 3. Company Identification Service Tests

def test_identify_personal_email():
    res = identify_company_from_email("user@gmail.com")
    assert res["success"] is True
    assert res["email_domain"] == "gmail.com"
    assert res["identification_status"] == "NOT_FOUND"
    assert res["requires_user_confirmation"] is True
    assert "public email provider" in res["message"]


@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_identify_inaccessible_website(mock_fetch):
    mock_fetch.return_value = {"success": False, "message": "Website unreachable"}
    res = identify_company_from_email("user@offlinecompany.com")
    assert res["success"] is True
    assert res["email_domain"] == "offlinecompany.com"
    assert res["identification_status"] == "NOT_FOUND"
    assert res["requires_user_confirmation"] is True
    assert "No accessible public website" in res["message"]


@patch("app.services.company_discovery_service.analyze_company_with_gemini")
@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_identify_confirmed_company(mock_fetch, mock_gemini):
    mock_fetch.return_value = {
        "success": True,
        "final_url": "https://www.acme.com",
        "title": "Acme Corp - Global Solutions",
        "og_site_name": "Acme",
        "meta_description": "Official homepage of Acme Corp",
        "html_snippet": "Welcome to Acme Corp"
    }
    mock_gemini.return_value = ("Acme Corp", "https://www.acme.com", "CONFIRMED")

    res = identify_company_from_email("employee@acme.com")
    assert res["success"] is True
    assert res["email_domain"] == "acme.com"
    assert res["company_name"] == "Acme Corp"
    assert res["official_website"] == "https://www.acme.com"
    assert res["identification_status"] == "CONFIRMED"
    assert res["requires_user_confirmation"] is False
    assert res["message"] == "Company identified successfully."


@patch("app.services.company_discovery_service.analyze_company_with_gemini")
@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_identify_uncertain_company(mock_fetch, mock_gemini):
    mock_fetch.return_value = {
        "success": True,
        "final_url": "https://acmegroup.in",
        "title": "Acme India",
        "og_site_name": None,
        "meta_description": "Regional portal",
        "html_snippet": "Acme Group India"
    }
    mock_gemini.return_value = ("Acme Group", "https://acme.com", "NEEDS_CONFIRMATION")

    res = identify_company_from_email("employee@acmegroup.in")
    assert res["success"] is True
    assert res["email_domain"] == "acmegroup.in"
    assert res["identification_status"] == "NEEDS_CONFIRMATION"
    assert res["requires_user_confirmation"] is True
    assert res["message"] == "Please confirm your company's official website."


@patch("app.services.company_discovery_service.Config")
@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_identify_cross_domain_forces_confirmation(mock_fetch, mock_config):
    mock_config.GEMINI_API_KEY = None
    mock_fetch.return_value = {
        "success": True,
        "final_url": "https://differentbrand.com",
        "title": "Different Brand Inc",
        "og_site_name": "Different Brand",
        "meta_description": "Unrelated portal",
        "html_snippet": "Welcome to Different Brand"
    }

    res = identify_company_from_email("user@originaldomain.com")
    assert res["success"] is True
    assert res["email_domain"] == "originaldomain.com"
    assert res["official_website"] == "https://differentbrand.com"
    assert res["identification_status"] == "NEEDS_CONFIRMATION"
    assert res["requires_user_confirmation"] is True


@patch("app.services.company_discovery_service.Config")
@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_heuristic_weak_name_requires_confirmation(mock_fetch, mock_config):
    mock_config.GEMINI_API_KEY = None
    mock_fetch.return_value = {
        "success": True,
        "final_url": "https://somecompany.com",
        "title": "Home | Welcome to somecompany",
        "og_site_name": None,
        "meta_description": "",
        "html_snippet": "Home page text"
    }

    res = identify_company_from_email("user@somecompany.com")
    assert res["success"] is True
    assert res["email_domain"] == "somecompany.com"
    assert res["company_name"] == "Home"
    assert res["identification_status"] == "NEEDS_CONFIRMATION"
    assert res["requires_user_confirmation"] is True


# 4. API Endpoint Integration Tests

def test_unauthenticated_identify_endpoint(client):
    res = client.get('/api/onboarding/company/identify')
    assert res.status_code == 401


@patch("app.services.company_discovery_service.analyze_company_with_gemini")
@patch("app.services.company_discovery_service.fetch_domain_homepage")
def test_authenticated_identify_endpoint_success(mock_fetch, mock_gemini, client):
    create_user_and_login(client, "Jane Doe", "jane@starkindustries.com", "+14155558888")

    mock_fetch.return_value = {
        "success": True,
        "final_url": "https://starkindustries.com",
        "title": "Stark Industries",
        "og_site_name": "Stark Industries",
        "meta_description": "Advanced Technology Solutions",
        "html_snippet": "Stark Industries Homepage"
    }
    mock_gemini.return_value = ("Stark Industries", "https://starkindustries.com", "CONFIRMED")

    res = client.get('/api/onboarding/company/identify')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["email_domain"] == "starkindustries.com"
    assert data["company_name"] == "Stark Industries"
    assert data["official_website"] == "https://starkindustries.com"
    assert data["identification_status"] == "CONFIRMED"
    assert data["requires_user_confirmation"] is False
