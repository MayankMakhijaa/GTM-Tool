import socket
import ipaddress
import re
from typing import Tuple, Optional, Dict, Any

# Disallowed public domains for business sending accounts
DISALLOWED_FREE_DOMAINS = {
    'gmail.com', 'googlemail.com', 'yahoo.com', 'ymail.com', 'hotmail.com',
    'outlook.com', 'live.com', 'icloud.com', 'aol.com', 'mail.com', 'proton.me',
    'protonmail.com', 'zoho.com', 'gmx.com', 'yandex.com'
}

# Known enterprise providers heuristics
PROVIDER_CONFIGS = {
    'google': {
        'name': 'Google Workspace',
        'oauth_supported': False, # Planned follow-up
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use your Google Workspace email and an App Password (requires 2-Step Verification).'
    },
    'microsoft': {
        'name': 'Microsoft 365 / Outlook',
        'oauth_supported': False,
        'smtp_host': 'smtp.office365.com',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use your Microsoft 365 email and SMTP credentials or App Password.'
    },
    'zoho': {
        'name': 'Zoho Mail Workplace',
        'oauth_supported': False,
        'smtp_host': 'smtppro.zoho.com',
        'smtp_port': 465,
        'use_tls': False,
        'use_ssl': True,
        'auth_guide': 'Use your custom domain Zoho email and Application-Specific Password.'
    },
    'sendgrid': {
        'name': 'SendGrid SMTP',
        'oauth_supported': False,
        'smtp_host': 'smtp.sendgrid.net',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use username "apikey" and your SendGrid API Key as password.'
    },
    'postmark': {
        'name': 'Postmark SMTP',
        'oauth_supported': False,
        'smtp_host': 'smtp.postmarkapp.com',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use your Postmark Server API Token as both username and password.'
    },
    'mailgun': {
        'name': 'Mailgun SMTP',
        'oauth_supported': False,
        'smtp_host': 'smtp.mailgun.org',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use your Mailgun SMTP credentials from Domain Settings.'
    },
    'amazon_ses': {
        'name': 'Amazon SES',
        'oauth_supported': False,
        'smtp_host': 'email-smtp.us-east-1.amazonaws.com',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Use your AWS SES SMTP username and password generated from IAM/SES console.'
    }
}


import os
from flask import current_app

def is_personal_email_allowed() -> bool:
    """Checks if personal consumer email senders are temporarily permitted via ALLOW_PERSONAL_EMAIL_SENDERS."""
    env_val = os.environ.get('ALLOW_PERSONAL_EMAIL_SENDERS')
    if env_val is not None:
        return env_val.strip().lower() in ('true', '1', 'yes')
    try:
        if current_app and current_app.config.get('ALLOW_PERSONAL_EMAIL_SENDERS') is not None:
            return bool(current_app.config.get('ALLOW_PERSONAL_EMAIL_SENDERS'))
    except RuntimeError:
        pass
    return False


def is_free_email_domain(email_address: str, check_allow_flag: bool = True) -> bool:
    """
    Checks if the email domain is a free public consumer email service.
    If check_allow_flag is True and ALLOW_PERSONAL_EMAIL_SENDERS is enabled,
    returns False so that personal senders are permitted.
    """
    if not email_address or '@' not in email_address:
        return False

    domain = email_address.strip().split('@')[-1].lower()
    is_consumer = domain in DISALLOWED_FREE_DOMAINS

    if not is_consumer:
        return False

    if check_allow_flag and is_personal_email_allowed():
        return False

    return True


def detect_provider(email_address: str) -> Dict[str, Any]:
    """
    Detects likely provider based on email domain or MX heuristics.
    Returns provider suggestion and fallback configuration.
    """
    if not email_address or '@' not in email_address:
        return {'detected': False, 'provider': 'custom', 'name': 'Custom SMTP Server'}

    domain = email_address.strip().split('@')[-1].lower()

    if is_free_email_domain(email_address, check_allow_flag=True):
        return {
            'detected': False,
            'is_free_domain': True,
            'provider': 'free_consumer',
            'error': 'Personal/free email accounts (@gmail, @yahoo, @outlook) cannot be used as business sending accounts. Please use a custom business domain email.'
        }

    # Consumer domains when ALLOW_PERSONAL_EMAIL_SENDERS is active
    if domain in ('gmail.com', 'googlemail.com'):
        cfg = PROVIDER_CONFIGS['google']
        return {
            'detected': True,
            'provider': 'google',
            **cfg,
            'auth_guide': 'Use your Gmail address and a 16-character Google App Password (requires 2-Step Verification).'
        }

    if domain in ('yahoo.com', 'ymail.com', 'aol.com'):
        return {
            'detected': True,
            'provider': 'yahoo',
            'name': 'Yahoo Mail',
            'oauth_supported': False,
            'smtp_host': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'auth_guide': 'Use your Yahoo email and a Yahoo Generated App Password.'
        }

    if domain in ('outlook.com', 'hotmail.com', 'live.com'):
        return {
            'detected': True,
            'provider': 'microsoft',
            'name': 'Outlook / Hotmail',
            'oauth_supported': False,
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'auth_guide': 'Use your Outlook/Hotmail email address and App Password.'
        }

    # Common domain checks
    if domain in ('fameweb.com', 'fameweb.in', 'google.com'):
        cfg = PROVIDER_CONFIGS['google']
        return {'detected': True, 'provider': 'google', **cfg}

    # Domain name clues
    if 'zoho' in domain:
        return {'detected': True, 'provider': 'zoho', **PROVIDER_CONFIGS['zoho']}

    return {
        'detected': False,
        'provider': 'custom',
        'name': 'Custom Business SMTP',
        'smtp_host': f'smtp.{domain}',
        'smtp_port': 587,
        'use_tls': True,
        'use_ssl': False,
        'auth_guide': 'Enter your custom domain SMTP server host, port, and credentials.'
    }


def validate_smtp_host_ssrf(host: str, port: int) -> Tuple[bool, Optional[str]]:
    """
    Validates SMTP host to prevent SSRF against internal/private network addresses (RFC 1918, loopback, link-local, cloud metadata).
    Allowed ports: 25, 465, 587, 2525.
    """
    if not host or not str(host).strip():
        return False, "SMTP host is required."

    host = host.strip().lower()

    # Disallow common local names
    if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        return False, "Connections to localhost or loopback are strictly forbidden for security."

    # Validate port
    allowed_ports = {25, 465, 587, 2525}
    if port not in allowed_ports:
        return False, f"Port {port} is not permitted for SMTP. Allowed ports: {', '.join(map(str, sorted(allowed_ports)))}."

    # Resolve IP addresses
    try:
        resolved_ips = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return False, f"Unable to resolve host '{host}': {str(e)}"
    except Exception as e:
        return False, f"Host resolution error for '{host}': {str(e)}"

    for res in resolved_ips:
        sockaddr = res[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private:
                return False, f"Access to private IP address {ip_str} is forbidden (SSRF protection)."
            if ip_obj.is_loopback:
                return False, f"Access to loopback IP address {ip_str} is forbidden."
            if ip_obj.is_link_local:
                return False, f"Access to link-local IP address {ip_str} is forbidden."
            if ip_obj.is_reserved:
                return False, f"Access to reserved IP address {ip_str} is forbidden."
            if ip_obj.is_multicast:
                return False, f"Access to multicast IP address {ip_str} is forbidden."
            # Check for AWS/GCP/Azure link-local metadata address: 169.254.169.254
            if str(ip_obj) == "169.254.169.254":
                return False, "Access to cloud instance metadata service is forbidden."
        except ValueError:
            return False, f"Invalid IP address format: {ip_str}"

    return True, None
