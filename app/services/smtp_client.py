import smtplib
import ssl
import logging
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from app.services.smtp_validator import validate_smtp_host_ssrf

logger = logging.getLogger(__name__)

# Alias for socket timeout
import socket
socket_timeout = socket.timeout

def test_smtp_connection(
    host: str,
    port: int,
    username: Optional[str],
    password: Optional[str],
    use_tls: bool = True,
    use_ssl: bool = False,
    timeout: int = 15
) -> Tuple[bool, Optional[str]]:
    """
    Attempts to establish an SMTP connection and authenticate without sending an email.
    Validates SSRF safety first.
    Returns (success: bool, error_message: Optional[str]).
    Never returns or logs the password.
    """
    # 1. SSRF and port checks
    is_safe, ssrf_err = validate_smtp_host_ssrf(host, port)
    if not is_safe:
        return False, ssrf_err

    # Strip accidental leading/trailing whitespace from credentials without modifying internal characters
    clean_username = username.strip() if isinstance(username, str) else None
    clean_password = password.strip() if isinstance(password, str) else None

    server = None
    try:
        # Phase 1: Connection & TLS handshake
        if use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host=host, port=port, timeout=timeout, context=context)
        else:
            server = smtplib.SMTP(host=host, port=port, timeout=timeout)
            server.ehlo()
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()

        # Phase 2: Authentication
        if clean_username and clean_password:
            try:
                server.login(clean_username, clean_password)
            except smtplib.SMTPAuthenticationError as auth_err:
                logger.warning(f"SMTP authentication rejected for host {host}:{port}")
                err_text = auth_err.smtp_error.decode('utf-8', errors='ignore') if isinstance(auth_err.smtp_error, bytes) else str(auth_err.smtp_error)
                return False, f"Authentication failed: Check your username and password/app-password. (Provider response: {auth_err.smtp_code} {err_text})"
            except smtplib.SMTPServerDisconnected:
                # Provider (such as Gmail or Outlook) dropped the socket after rejecting the first auth mechanism
                logger.warning(f"SMTP server {host}:{port} dropped socket during authentication")
                return False, "SMTP authentication failed or the provider closed the connection during login. Verify your username, App Password and provider security settings."

        return True, None

    except smtplib.SMTPConnectError:
        return False, f"Could not connect to SMTP server {host}:{port}."
    except smtplib.SMTPServerDisconnected:
        return False, f"SMTP server {host}:{port} disconnected unexpectedly."
    except (socket_timeout, TimeoutError):
        return False, f"Connection to {host}:{port} timed out after {timeout} seconds."
    except Exception as e:
        return False, f"SMTP connection failed: {str(e)}"
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

