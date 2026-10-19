import pytest
from datetime import datetime, timedelta
from app.database import db_session
from app.models.all_models import UserTable, EmailVerificationOTP
from app.services.email_service import get_last_test_otp, clear_test_captured_otps
from app.services.otp_service import hash_otp

def test_signup_creates_unverified_user_and_sends_hashed_otp(client):
    clear_test_captured_otps()
    email = "testuser@acmecorp.com"
    
    # 1. Signup
    res = client.post('/api/auth/signup', json={
        "name": "Test User",
        "email": email,
        "phone": "+14155551234",
        "password": "StrongPassword123!"
    })
    
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["requires_verification"] is True
    
    # Requirement 18: OTP is NEVER returned in signup API response
    assert "otp" not in data
    assert "code" not in data
    
    # Requirement 1: User exists with email_verified_at IS NULL
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert user is not None
    assert user.email_verified_at is None
    
    # Requirement 2: Signup does not create normal session
    me_res = client.get('/api/auth/me')
    assert me_res.status_code == 200
    assert me_res.get_json()["authenticated"] is False
    
    # Requirement 3 & 4: OTP is generated and stored as SHA-256 hash (never plaintext)
    otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
    assert otp_record is not None
    assert otp_record.attempts == 0
    assert len(otp_record.otp_hash) == 64  # SHA-256 length
    
    # Check captured test OTP
    dispatched_otp = get_last_test_otp(email)
    assert dispatched_otp is not None
    assert len(dispatched_otp) == 6
    assert hash_otp(dispatched_otp) == otp_record.otp_hash
    assert dispatched_otp != otp_record.otp_hash  # Plaintext is NOT the stored hash


def test_correct_otp_verifies_successfully_and_creates_session(client):
    clear_test_captured_otps()
    email = "verifyme@acmecorp.com"
    
    client.post('/api/auth/signup', json={
        "name": "Verify Me",
        "email": email,
        "phone": "+14155551235",
        "password": "StrongPassword123!"
    })
    
    dispatched_otp = get_last_test_otp(email)
    assert dispatched_otp is not None
    
    # Requirement 5, 6, 7: Verify OTP
    verify_res = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": dispatched_otp
    })
    assert verify_res.status_code == 200
    vdata = verify_res.get_json()
    assert vdata["success"] is True
    assert vdata["redirect"] == "/connect-linkedin"
    
    # User is now verified in DB
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert user.email_verified_at is not None
    
    # OTP record is deleted / invalidated
    otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
    assert otp_record is None
    
    # Normal authenticated session is now created
    me_res = client.get('/api/auth/me')
    assert me_res.status_code == 200
    assert me_res.get_json()["authenticated"] is True
    assert me_res.get_json()["user"]["email_id"] == email


def test_expired_otp_fails(client):
    clear_test_captured_otps()
    email = "expired@acmecorp.com"
    
    client.post('/api/auth/signup', json={
        "name": "Expired User",
        "email": email,
        "phone": "+14155551236",
        "password": "StrongPassword123!"
    })
    
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
    
    # Requirement 8: Expire the OTP
    otp_record.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    
    dispatched_otp = get_last_test_otp(email)
    res = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": dispatched_otp
    })
    assert res.status_code == 400
    assert "expired" in res.get_json()["message"].lower()
    assert user.email_verified_at is None


def test_incorrect_otp_increments_attempts_and_locks_after_5_attempts(client):
    clear_test_captured_otps()
    email = "attempts@acmecorp.com"
    
    client.post('/api/auth/signup', json={
        "name": "Attempt User",
        "email": email,
        "phone": "+14155551237",
        "password": "StrongPassword123!"
    })
    
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    
    # Requirement 9: Incorrect OTP increments attempts
    for attempt_num in range(1, 5):
        res = client.post('/api/auth/verify-otp', json={
            "email": email,
            "otp": "000000"
        })
        assert res.status_code == 400
        assert "invalid" in res.get_json()["message"].lower()
        otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
        assert otp_record is not None
        assert otp_record.attempts == attempt_num

    # Requirement 10: 5th incorrect attempt invalidates the OTP
    res_5 = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": "000000"
    })
    assert res_5.status_code == 400
    assert "maximum" in res_5.get_json()["message"].lower()
    
    # OTP record is deleted / invalidated
    otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
    assert otp_record is None


def test_resend_otp_invalidates_old_and_respects_cooldown(client):
    clear_test_captured_otps()
    email = "resend@acmecorp.com"
    
    client.post('/api/auth/signup', json={
        "name": "Resend User",
        "email": email,
        "phone": "+14155551238",
        "password": "StrongPassword123!"
    })
    
    first_otp = get_last_test_otp(email)
    
    # Requirement 12: Resend cooldown (immediate resend blocked)
    resend_1 = client.post('/api/auth/resend-otp', json={"email": email})
    assert resend_1.status_code == 429
    assert "wait" in resend_1.get_json()["message"].lower()
    
    # Simulate cooldown elapsed (65 seconds ago)
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    otp_record = db_session.query(EmailVerificationOTP).filter_by(user_id=user.user_id).first()
    otp_record.created_at = datetime.utcnow() - timedelta(seconds=65)
    db_session.commit()
    
    # Successful resend
    resend_2 = client.post('/api/auth/resend-otp', json={"email": email})
    assert resend_2.status_code == 200
    assert resend_2.get_json()["success"] is True
    
    second_otp = get_last_test_otp(email)
    assert second_otp is not None
    
    # Requirement 11: Old OTP is now invalid
    invalid_verify = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": first_otp
    })
    # If first_otp != second_otp, it should fail
    if first_otp != second_otp:
        assert invalid_verify.status_code == 400


def test_unverified_login_is_blocked_and_verified_login_works(client):
    clear_test_captured_otps()
    email = "login_check@acmecorp.com"
    password = "StrongPassword123!"
    
    client.post('/api/auth/signup', json={
        "name": "Login Check",
        "email": email,
        "phone": "+14155551239",
        "password": password
    })
    
    # Requirement 14: Unverified login is blocked
    login_res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res.status_code == 403
    ldata = login_res.get_json()
    assert ldata["error"] == "EMAIL_NOT_VERIFIED"
    assert ldata["redirect"] == "/verify-email"
    
    # Session is NOT created
    me_res = client.get('/api/auth/me')
    assert me_res.get_json()["authenticated"] is False
    
    # Verify the user
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    user.email_verified_at = datetime.utcnow()
    db_session.commit()
    
    # Requirement 15 & 16: Verified login works
    login_res_2 = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res_2.status_code == 200
    assert login_res_2.get_json()["success"] is True
    
    # Session is now authenticated
    me_res_2 = client.get('/api/auth/me')
    assert me_res_2.get_json()["authenticated"] is True


def test_direct_access_to_onboarding_blocks_unverified_users(client):
    clear_test_captured_otps()
    email = "unverified_guard@acmecorp.com"
    password = "StrongPassword123!"
    
    client.post('/api/auth/signup', json={
        "name": "Guard User",
        "email": email,
        "phone": "+14155551240",
        "password": password
    })
    
    # Without session, direct access returns unauthorized
    res = client.get('/company')
    assert res.status_code in (302, 401, 403)
    
    # Even if somehow an unverified user has a session created, enforce_onboarding blocks them
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    with client.session_transaction() as sess:
        sess['user_id'] = user.user_id
        
    # Requirement 17: Direct access redirects unverified users to /verify-email
    comp_res = client.get('/company')
    assert comp_res.status_code == 302
    assert "/verify-email" in comp_res.headers["Location"]
    
    dash_res = client.get('/dashboard')
    assert dash_res.status_code == 302
    assert "/verify-email" in dash_res.headers["Location"]
    
    # But /verify-email itself is accessible!
    ve_res = client.get('/verify-email')
    assert ve_res.status_code == 200
    assert "Verify your email" in ve_res.data.decode('utf-8')
