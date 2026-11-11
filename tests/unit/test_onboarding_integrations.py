import pytest
import json
from unittest.mock import patch, MagicMock

from app.models.all_models import UserTable, UsersLinkedinDetails, UserSMTPAccount, ConnectionStatus
from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials


# ====================================================================
# 1. Signup, OTP Verification & Integrations Redirect
# ====================================================================

def test_verify_otp_redirects_to_integrations(client):
    """After entering valid OTP, the response must redirect to /onboarding/integrations."""
    with patch("app.routes.auth.verify_user_otp") as mock_verify:
        mock_user = MagicMock()
        mock_user.user_id = 101
        mock_user.name = "Test Founder"
        mock_user.email_id = "founder@acme.com"
        mock_user.onboarding_step = "LINKEDIN"
        mock_verify.return_value = (True, "Email verified successfully.", mock_user)

        with patch("app.routes.auth.set_user_session"):
            res = client.post("/api/auth/verify-otp", json={
                "email": "founder@acme.com",
                "otp": "123456"
            })
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert data["redirect"] == "/onboarding/integrations"


# ====================================================================
# 2. Integrations Status API & Isolation
# ====================================================================

def test_integrations_status_endpoint_never_leaks_secrets(client):
    """GET /api/onboarding/integrations/status returns sanitized status without passwords."""
    mock_user = MagicMock()
    mock_user.user_id = 102
    mock_user.is_active = True
    mock_user.email_verified_at = "2026-01-01"
    mock_user.role = "USER"

    with patch("app.security.session.get_user_by_id", return_value=mock_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 102
                sess["role"] = "USER"

            with patch("app.database.db_session") as mock_db:
                # Mock SMTP query
                mock_smtp = MagicMock()
                mock_smtp.email_address = "sender@acme.com"
                mock_smtp.smtp_host = "smtp.acme.com"
                mock_smtp.smtp_port = 587
                mock_smtp.smtp_username = "sender@acme.com"
                mock_smtp.use_tls = True
                mock_smtp.use_ssl = False
                mock_smtp.connection_status = "CONNECTED"
                mock_smtp.last_tested_at = None

                # Mock LinkedIn query
                mock_li = MagicMock()
                mock_li.connection_status = ConnectionStatus.CONNECTED.value
                mock_li.profile_url = "https://linkedin.com/in/founder"
                mock_li.name = "Founder"
                mock_li.last_verified_at = None
                mock_li.profile_source = "CHROME_EXTENSION_LOCAL"

                # Setup query filter_by returns
                def query_side_effect(model):
                    m = MagicMock()
                    if model == UsersLinkedinDetails:
                        m.filter_by.return_value.first.return_value = mock_li
                    else:
                        m.filter_by.return_value.first.return_value = mock_smtp
                        m.filter_by.return_value.order_by.return_value.first.return_value = mock_smtp
                    return m

                mock_db.query.side_effect = query_side_effect

                res = client.get("/api/onboarding/integrations/status")
                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["smtp"]["configured"] is True
                assert data["smtp"]["email_address"] == "sender@acme.com"
                assert "password" not in json.dumps(data)
                assert "encrypted_credentials" not in json.dumps(data)
                assert "li_at" not in json.dumps(data)
                assert data["linkedin"]["connected"] is True


# ====================================================================
# 3. Extension LinkedIn Verification Handshake (Zero Raw Cookies)
# ====================================================================

def test_verify_extension_session_connected(client):
    """Extension reports CONNECTED status signal; backend updates UsersLinkedinDetails without cookies."""
    mock_user = MagicMock()
    mock_user.user_id = 103
    mock_user.is_active = True
    mock_user.email_verified_at = "2026-01-01"
    mock_user.role = "USER"
    mock_user.onboarding_step = "LINKEDIN"

    with patch("app.security.session.get_user_by_id", return_value=mock_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 103
                sess["role"] = "USER"

            with patch("app.database.db_session") as mock_db:
                mock_li = MagicMock()
                mock_li.connection_status = "DISCONNECTED"

                mock_user_db = MagicMock()
                mock_user_db.onboarding_step = "LINKEDIN"

                def query_side_effect(model):
                    m = MagicMock()
                    if model == UsersLinkedinDetails:
                        m.filter_by.return_value.first.return_value = mock_li
                    elif model == UserTable:
                        m.filter_by.return_value.first.return_value = mock_user_db
                    return m

                mock_db.query.side_effect = query_side_effect

                # Post verification from extension
                res = client.post("/api/onboarding/linkedin/verify-extension-session", json={
                    "status": "CONNECTED",
                    "authenticated": True,
                    "profile_url": "https://www.linkedin.com/in/verified-founder",
                    "name": "Verified Founder"
                })

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["connected"] is True
                assert data["status"] == "CONNECTED"
                assert mock_li.connection_status == ConnectionStatus.CONNECTED.value
                assert mock_li.profile_source == "CHROME_EXTENSION_LOCAL"
                assert mock_user_db.onboarding_step == "COMPANY"
                assert mock_db.commit.called


def test_verify_extension_session_not_logged_in(client):
    """Extension reports NOT_LOGGED_IN status signal; backend marks DISCONNECTED."""
    mock_user = MagicMock()
    mock_user.user_id = 104
    mock_user.is_active = True
    mock_user.email_verified_at = "2026-01-01"
    mock_user.role = "USER"

    with patch("app.security.session.get_user_by_id", return_value=mock_user):
        with patch("app.security.session.is_user_email_verified", return_value=True):
            with client.session_transaction() as sess:
                sess["user_id"] = 104
                sess["role"] = "USER"

            with patch("app.database.db_session") as mock_db:
                mock_li = MagicMock()
                mock_db.query.return_value.filter_by.return_value.first.return_value = mock_li

                res = client.post("/api/onboarding/linkedin/verify-extension-session", json={
                    "status": "NOT_LOGGED_IN",
                    "authenticated": False
                })

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["connected"] is False
                assert data["status"] == "NOT_LOGGED_IN"
                assert mock_li.connection_status == ConnectionStatus.DISCONNECTED.value


# ====================================================================
# 4. SMTP Credential Encryption
# ====================================================================

def test_smtp_credential_encryption_isolation():
    """Verify that SMTP credentials are AES-256-GCM encrypted and never stored in plaintext."""
    raw_creds = {"password": "AppSpecificPassword123!"}
    encrypted, version = encrypt_smtp_credentials(raw_creds)

    assert encrypted != "AppSpecificPassword123!"
    assert "AppSpecificPassword123!" not in encrypted

    decrypted = decrypt_smtp_credentials(encrypted, version)
    assert decrypted["password"] == "AppSpecificPassword123!"


# ====================================================================
# 5. Onboarding Integrations Page Route Access
# ====================================================================

def test_onboarding_integrations_page_accessible(client):
    """Authenticated user can load /onboarding/integrations HTML page."""
    mock_user = MagicMock()
    mock_user.user_id = 105
    mock_user.name = "Founder"
    mock_user.email_id = "founder@company.com"
    mock_user.is_active = True
    mock_user.email_verified_at = "2026-01-01"
    mock_user.role = "USER"
    mock_user.onboarding_step = "LINKEDIN"

    with patch("app.routes.pages.get_current_user", return_value=mock_user):
        with patch("app.security.session.get_user_by_id", return_value=mock_user):
            with patch("app.security.session.is_user_email_verified", return_value=True):
                with patch("app.routes.pages.is_user_email_verified", return_value=True):
                    with patch("app.database.db_session") as mock_db:
                        mock_db.query.return_value.filter_by.return_value.first.return_value = None
                        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None

                        with client.session_transaction() as sess:
                            sess["user_id"] = 105
                            sess["role"] = "USER"

                        res = client.get("/onboarding/integrations")
                        assert res.status_code == 200
                        html = res.get_data(as_text=True)
                        assert "Authentication &amp; Integrations" in html or "Authentication & Integrations" in html
                        assert "Business Email (SMTP)" in html
                        assert "LinkedIn Verification" in html
                        assert "FameWeb Integrator Extension" in html
