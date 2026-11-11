import pytest
import json
import base64
from app.models.all_models import UserTable, UserSMTPAccount, EmailBatch, EmailRecipient
from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials
from app.services.smtp_validator import validate_smtp_host_ssrf, is_free_email_domain, detect_provider
from app.services.csv_parser import parse_csv_content
from app.services.template_renderer import render_email_preview, sanitize_email_html, render_template_string


def test_credential_vault_aes_256_gcm():
    """Verify SMTP credentials are encrypted with AES-256-GCM and decrypted accurately."""
    creds = {"password": "test_app_password_12345"}
    enc, version = encrypt_smtp_credentials(creds)
    assert version >= 1
    assert isinstance(enc, str)
    assert enc != creds["password"]
    
    # Decrypt and verify
    decrypted = decrypt_smtp_credentials(enc, version)
    assert decrypted["password"] == "test_app_password_12345"


def test_smtp_ssrf_protection():
    """Verify private IPs, localhost, and cloud metadata IPs are blocked."""
    assert validate_smtp_host_ssrf("127.0.0.1", 587)[0] is False
    assert validate_smtp_host_ssrf("localhost", 587)[0] is False
    assert validate_smtp_host_ssrf("169.254.169.254", 587)[0] is False
    assert validate_smtp_host_ssrf("smtp.gmail.com", 8080)[0] is False # Disallowed port


import os

def test_free_email_domain_blocking(monkeypatch):
    """Verify consumer domains are blocked when flag is false, and permitted when flag is true."""
    # 1. Default (flag disabled): consumer accounts blocked, business accounts allowed
    monkeypatch.delenv("ALLOW_PERSONAL_EMAIL_SENDERS", raising=False)
    assert is_free_email_domain("test@gmail.com") is True
    assert is_free_email_domain("test@yahoo.com") is True
    assert is_free_email_domain("test@hotmail.com") is True
    assert is_free_email_domain("founder@fameweb.in") is False
    assert is_free_email_domain("alex@acmecorp.com") is False
    assert detect_provider("test@gmail.com")['is_free_domain'] is True

    # 2. Flag enabled: consumer accounts permitted for testing
    monkeypatch.setenv("ALLOW_PERSONAL_EMAIL_SENDERS", "true")
    assert is_free_email_domain("test@gmail.com") is False
    assert is_free_email_domain("test@yahoo.com") is False
    assert is_free_email_domain("test@outlook.com") is False
    # Business accounts still permitted
    assert is_free_email_domain("founder@fameweb.in") is False

    # Provider detection resolves configuration for Gmail when flag is enabled
    det_gmail = detect_provider("test@gmail.com")
    assert det_gmail.get('is_free_domain') is not True
    assert det_gmail['detected'] is True
    assert det_gmail['smtp_host'] == "smtp.gmail.com"

    # 3. Explicitly disable flag: restores strict blocking
    monkeypatch.setenv("ALLOW_PERSONAL_EMAIL_SENDERS", "false")
    assert is_free_email_domain("test@gmail.com") is True
    assert is_free_email_domain("test@yahoo.com") is True
    assert is_free_email_domain("founder@fameweb.in") is False



def test_csv_parser_with_arbitrary_headers():
    """Test CSV with minimal headers vs arbitrary custom headers and deduplication."""
    # CSV A: name, email
    csv_a = b"""name,email
Rahul,rahul@example.com
Aarav,aarav@example.com
Rahul Duplicate,rahul@example.com
"""
    parsed_a = parse_csv_content(csv_a)
    assert parsed_a['valid_count'] == 2
    assert parsed_a['invalid_count'] == 1 # duplicate detected
    assert '{{name}}' in parsed_a['placeholders']
    assert '{{email}}' in parsed_a['placeholders']

    # CSV B: arbitrary headers with quoted commas
    csv_b = b"""email,company_name,designation,custom_crm_id,"location, notes"
rahul@example.com,"ABC, Corp",CTO,CRM-9921,Bengaluru Office
"""
    parsed_b = parse_csv_content(csv_b)
    assert parsed_b['valid_count'] == 1
    assert parsed_b['valid_recipients'][0]['data']['company_name'] == "ABC, Corp"
    assert '{{custom_crm_id}}' in parsed_b['placeholders']


def test_template_rendering_and_missing_placeholder_flags():
    """Verify personalized interpolation, missing value flagging, and fallback safety."""
    subj = "Hello {{first_name}} at {{company}}"
    body = "<p>Hi {{first_name}},</p><p>We saw {{company}} in {{location}}.</p>"
    
    rec_data = {'first_name': 'Rahul', 'company': 'ABC Corp'} # location missing
    
    preview = render_email_preview(
        subject_template=subj,
        body_html_template=body,
        body_text_template=None,
        recipient_data=rec_data,
        fallback_value='[Unspecified]'
    )

    assert preview['rendered_subject'] == "Hello Rahul at ABC Corp"
    assert "Rahul" in preview['rendered_body_html']
    assert "ABC Corp" in preview['rendered_body_html']
    assert "[Unspecified]" in preview['rendered_body_html']
    assert preview['has_missing_values'] is True
    assert 'location' in preview['missing_placeholders']


def test_html_sanitization():
    """Verify script tags, on* event handlers, and malicious protocols are stripped."""
    dirty_html = '<p onclick="alert(1)">Click me</p><script>evil()</script><a href="javascript:alert(2)">Link</a>'
    clean = sanitize_email_html(dirty_html)
    assert '<script>' not in clean
    assert 'onclick' not in clean
    assert 'javascript:' not in clean
    assert '<p>' in clean


import smtplib
from unittest.mock import MagicMock
from app.services.smtp_client import test_smtp_connection as verify_smtp_conn
import app.services.smtp_client as smtp_client_module

def test_smtp_auth_error_handling(monkeypatch):
    """Verify SMTPAuthenticationError produces an authentication-specific error."""
    monkeypatch.setattr(smtp_client_module, "validate_smtp_host_ssrf", lambda host, port: (True, None))
    mock_smtp = MagicMock()
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")
    monkeypatch.setattr(smtplib, "SMTP", lambda host, port, timeout: mock_smtp)

    secret_pwd = "secret_test_token_12345"
    success, err = verify_smtp_conn("smtp.example.com", 587, "user@example.com", secret_pwd, use_tls=True)
    assert success is False
    assert "Authentication failed: Check your username" in err
    assert "535" in err
    assert secret_pwd not in err


def test_smtp_server_disconnected_during_login(monkeypatch):
    """Verify SMTPServerDisconnected during login produces the clear authentication-phase message."""
    monkeypatch.setattr(smtp_client_module, "validate_smtp_host_ssrf", lambda host, port: (True, None))
    mock_smtp = MagicMock()
    mock_smtp.login.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
    monkeypatch.setattr(smtplib, "SMTP", lambda host, port, timeout: mock_smtp)

    secret_pwd = "secret_test_token_12345"
    success, err = verify_smtp_conn("smtp.example.com", 587, "user@example.com", secret_pwd, use_tls=True)
    assert success is False
    assert "SMTP authentication failed or the provider closed the connection during login" in err
    assert "Verify your username, App Password" in err
    assert secret_pwd not in err


def test_smtp_server_disconnected_before_login(monkeypatch):
    """Verify SMTPServerDisconnected during initial connection/ehlo remains a connection error."""
    monkeypatch.setattr(smtp_client_module, "validate_smtp_host_ssrf", lambda host, port: (True, None))
    mock_smtp = MagicMock()
    mock_smtp.ehlo.side_effect = smtplib.SMTPServerDisconnected("Connection closed on greeting")
    monkeypatch.setattr(smtplib, "SMTP", lambda host, port, timeout: mock_smtp)

    success, err = verify_smtp_conn("smtp.example.com", 587, "user@example.com", "secret_test_token_12345", use_tls=True)
    assert success is False
    assert "SMTP server smtp.example.com:587 disconnected unexpectedly." in err


def test_smtp_whitespace_stripping(monkeypatch):
    """Verify accidental leading/trailing whitespace is stripped without altering internal characters."""
    monkeypatch.setattr(smtp_client_module, "validate_smtp_host_ssrf", lambda host, port: (True, None))
    mock_smtp = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", lambda host, port, timeout: mock_smtp)

    # Pass username and password with whitespace and internal spaces/dashes
    raw_user = "  testuser@gmail.com \n"
    raw_pass = " abcd efgh ijkl mnop \t"
    success, err = verify_smtp_conn("smtp.example.com", 587, raw_user, raw_pass, use_tls=True)
    assert success is True
    # Verify mock_smtp.login was called with stripped versions preserving internal spacing
    mock_smtp.login.assert_called_once_with("testuser@gmail.com", "abcd efgh ijkl mnop")


def test_bulk_sending_halts_on_auth_failure(monkeypatch):
    """Verify that authentication failure prevents batch sending worker from starting dispatch."""
    from app.services.bulk_email_sender import _connect_and_login_smtp
    mock_account = MagicMock()
    mock_account.smtp_host = "smtp.gmail.com"
    mock_account.smtp_port = 587
    mock_account.use_tls = True
    mock_account.use_ssl = False
    mock_account.smtp_username = "test@gmail.com"

    # Mock credential decryption and ssrf
    import app.services.bulk_email_sender as sender_module
    monkeypatch.setattr(sender_module, "validate_smtp_host_ssrf", lambda host, port: (True, None))
    monkeypatch.setattr(sender_module, "decrypt_smtp_credentials", lambda enc, ver: {"password": "secret-pass"})

    # Mock smtplib to simulate SMTPServerDisconnected during login
    mock_smtp = MagicMock()
    mock_smtp.login.side_effect = smtplib.SMTPServerDisconnected("Connection closed during login")
    monkeypatch.setattr(smtplib, "SMTP", lambda host, port, timeout: mock_smtp)

    server, err = _connect_and_login_smtp(mock_account)
    assert server is None
    assert "SMTP Authentication failed: Provider closed connection during login" in err





