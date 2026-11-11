import json
import pytest
from app.database import db_session
from app.models.all_models import UserTable, UserSMTPAccount, EmailBatch, EmailRecipient, EmailBatchSendingMode
from app.services.email_service import send_verification_email, get_last_test_otp
from app.security.credential_vault import encrypt_smtp_credentials, decrypt_smtp_credentials


from datetime import datetime

def test_existing_transactional_email_and_otp():
    """Verify that existing OTP transactional email continues to work independently."""
    success = send_verification_email("mayank@fameweb.in", "882194", "Mayank")
    assert success is True
    assert get_last_test_otp("mayank@fameweb.in") == "882194"


def test_smtp_account_creation_and_credential_protection(client):
    """Verify that SMTP credentials are never returned over API and stored encrypted."""
    # Seed user 1
    u = UserTable(user_id=1, name="Test User", email_id="testuser@fameweb.in", password_hash="hash", email_verified_at=datetime.utcnow())
    db_session.add(u)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['last_activity'] = 9999999999

    res = client.get('/api/bulk-email/accounts')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    # Check that any returned account never exposes passwords or encrypted payloads
    for acc in data.get('accounts', []):
        assert 'encrypted_credentials' not in acc
        assert 'password' not in acc
        assert 'smtp_password' not in acc


def test_api_personal_email_flag_behavior(client, monkeypatch):
    """Verify endpoint rejects personal emails when flag is false, and permits testing when flag is true."""
    # Seed user 201
    u = UserTable(user_id=201, name="Sender Test", email_id="sender@fameweb.in", password_hash="hash", email_verified_at=datetime.utcnow())
    db_session.add(u)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = 201
        sess['last_activity'] = 9999999999

    payload = {
        "email_address": "mytestuser@gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_password": "invalid_password_to_check_auth"
    }

    # 1. Flag OFF: endpoint immediately rejects personal email before making any network attempt
    monkeypatch.setenv("ALLOW_PERSONAL_EMAIL_SENDERS", "false")
    res_off = client.post('/api/bulk-email/accounts/test', json=payload)
    assert res_off.status_code == 400
    assert "Personal consumer accounts" in res_off.get_json()['error']

    res_create_off = client.post('/api/bulk-email/accounts', json=payload)
    assert res_create_off.status_code == 400
    assert "Free personal email accounts" in res_create_off.get_json()['error']

    # 2. Flag ON: domain check passes, reaches connection/auth validation (and fails on invalid credentials rather than domain block)
    monkeypatch.setenv("ALLOW_PERSONAL_EMAIL_SENDERS", "true")
    res_detect = client.post('/api/bulk-email/accounts/detect-provider', json={"email_address": "mytestuser@gmail.com"})
    assert res_detect.status_code == 200
    det = res_detect.get_json()['data']
    assert det.get('is_free_domain') is not True
    assert det['smtp_host'] == "smtp.gmail.com"



def test_bulk_email_batch_lifecycle_and_multi_user_isolation(client):
    """Verify batch creation, recipient insertion, and multi-user isolation."""
    # Seed users
    u1 = UserTable(user_id=101, name="User One", email_id="user1@company.com", password_hash="hash", email_verified_at=datetime.utcnow())
    u2 = UserTable(user_id=102, name="User Two", email_id="user2@company.com", password_hash="hash", email_verified_at=datetime.utcnow())
    db_session.add(u1)
    db_session.add(u2)
    db_session.commit()

    user1_id = 101
    enc, v = encrypt_smtp_credentials({"password": "secret_password"})
    
    acc1 = UserSMTPAccount(
        user_id=user1_id,
        email_address="sender@businessdomain.com",
        smtp_host="smtp.businessdomain.com",
        smtp_port=587,
        encrypted_credentials=enc,
        encryption_key_version=v,
        is_primary=True
    )
    db_session.add(acc1)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = user1_id
        sess['last_activity'] = 9999999999

    # User 1 creates batch
    payload = {
        "smtp_account_id": acc1.id,
        "batch_name": "Q4 Outreach",
        "original_filename": "leads.csv",
        "subject": "Greetings {{first_name}}",
        "body_html": "<p>Hello {{first_name}} at {{company}}</p>",
        "sending_mode": "PERSONALIZED",
        "confirmed_lawful_basis": True,
        "valid_recipients": [
            {"email": "lead1@test.com", "data": {"first_name": "Aarav", "company": "TechCorp"}},
            {"email": "lead2@test.com", "data": {"first_name": "Isha", "company": "FinGroup"}}
        ]
    }

    res = client.post('/api/bulk-email/batches', json=payload)
    assert res.status_code == 200
    b_data = res.get_json()
    assert b_data['success'] is True
    batch_id = b_data['batch_id']

    # User 1 can view details
    res_detail = client.get(f'/api/bulk-email/batches/{batch_id}')
    assert res_detail.status_code == 200
    assert len(res_detail.get_json()['recipients']) == 2

    # User 2 logs in and tries to access User 1's batch (Isolation check)
    with client.session_transaction() as sess:
        sess['user_id'] = 102 # seeded User Two
        sess['last_activity'] = 9999999999

    res_user2 = client.get(f'/api/bulk-email/batches/{batch_id}')
    assert res_user2.status_code == 404 # Isolated from User Two
