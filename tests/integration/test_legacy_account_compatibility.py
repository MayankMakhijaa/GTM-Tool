import pytest
from datetime import datetime, timedelta
from app.database import db_session
from app.models.all_models import UserTable, UsersCompanyDetails
from app.services.email_service import get_last_test_otp, clear_test_captured_otps
from app.services.otp_service import is_user_email_verified
from app.security.password import hash_password

def create_legacy_user(email="legacy@nife.io", name="Legacy User", phone="+14155550001", password="StrongLegacyP@ssword123!", created_at=None, step="OPTIMIZATION"):
    """Creates a pre-OTP legacy user in the test database."""
    if created_at is None:
        created_at = datetime(2026, 10, 2, 12, 0, 0)
    user = UserTable(
        name=name,
        email_id=email,
        phone_no=phone,
        password_hash=hash_password(password),
        email_verified_at=None,  # Unset in pre-OTP accounts
        onboarding_step=step,
        created_at=created_at,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user

def test_legacy_account_is_considered_verified_by_helper():
    user = create_legacy_user(email="helper_legacy@example.com")
    # Helper must recognize pre-cutoff account as verified without updating DB
    assert is_user_email_verified(user) is True
    # DB email_verified_at must remain strictly NULL
    db_user = db_session.query(UserTable).filter_by(email_id="helper_legacy@example.com").first()
    assert db_user.email_verified_at is None

def test_legacy_account_allowed_to_login_and_access_onboarding(client):
    email = "legacy_user1@acmecorp.com"
    password = "StrongLegacyP@ssword123!"
    create_legacy_user(email=email, step="COMPANY")

    # 1. Legacy login must succeed (200) instead of 403
    res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # 2. Database row must remain UNCHANGED (email_verified_at is still NULL)
    db_user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert db_user.email_verified_at is None

    # 3. Access to onboarding (/company) must succeed without redirecting to /verify-email
    comp_res = client.get('/company')
    assert comp_res.status_code == 200
    assert "/verify-email" not in getattr(comp_res, "headers", {}).get("Location", "")

def test_legacy_account_not_redirected_to_verify_email(client):
    email = "legacy_opt@acmecorp.com"
    user = create_legacy_user(email=email, step="OPTIMIZATION")

    with client.session_transaction() as sess:
        sess['user_id'] = user.user_id

    # Accessing /verify-email directly as a grandfathered user redirects them onward to dashboard
    ve_res = client.get('/verify-email')
    assert ve_res.status_code == 302
    assert "/dashboard" in ve_res.headers["Location"]

    # Accessing /login or /signup while logged in also redirects to dashboard, not /verify-email
    log_res = client.get('/login')
    assert log_res.status_code == 302
    assert "/dashboard" in log_res.headers["Location"]

def test_new_account_with_null_email_verified_at_blocked_until_otp(client):
    clear_test_captured_otps()
    email = "newuser_blocked@newcorp.com"
    password = "StrongNewP@ssword123!"

    # New signup creates user with created_at = now (> cutoff) and email_verified_at = NULL
    res = client.post('/api/auth/signup', json={
        "name": "New User",
        "email": email,
        "phone": "+14155550099",
        "password": password
    })
    assert res.status_code == 201

    new_user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert new_user.email_verified_at is None
    # Helper must report False for new unverified accounts
    assert is_user_email_verified(new_user) is False

    # Login must be blocked with 403 EMAIL_NOT_VERIFIED
    login_res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res.status_code == 403
    ldata = login_res.get_json()
    assert ldata["error"] == "EMAIL_NOT_VERIFIED"
    assert ldata["redirect"] == "/verify-email"

def test_verified_new_account_allowed(client):
    clear_test_captured_otps()
    email = "newuser_verified@newcorp.com"
    password = "StrongNewP@ssword123!"

    client.post('/api/auth/signup', json={
        "name": "New Verified",
        "email": email,
        "phone": "+14155550098",
        "password": password
    })
    otp = get_last_test_otp(email)
    assert otp is not None

    # Verify OTP
    v_res = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": otp
    })
    assert v_res.status_code == 200

    # User now has email_verified_at populated
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert user.email_verified_at is not None
    assert is_user_email_verified(user) is True

    # Subsequent login works normally
    login_res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res.status_code == 200

def test_special_account_mayank_always_requires_otp_even_if_pre_cutoff(client):
    clear_test_captured_otps()
    # Create Mayank account with timestamp BEFORE OTP cutoff (October 2)
    email = "mayank@fameweb.in"
    password = "StrongMayankP@ssword123!"
    user = create_legacy_user(
        email=email,
        name="Mayank",
        phone="+919876543211",
        password=password,
        created_at=datetime(2026, 10, 2, 10, 0, 0),
        step="LINKEDIN"
    )

    # 1. SPECIAL EXCEPTION: Helper MUST report False for mayank@fameweb.in while unverified
    assert is_user_email_verified(user) is False

    # 2. Login must be BLOCKED with 403 EMAIL_NOT_VERIFIED and redirect to /verify-email
    login_res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res.status_code == 403
    ldata = login_res.get_json()
    assert ldata["error"] == "EMAIL_NOT_VERIFIED"
    assert ldata["redirect"] == "/verify-email"

    # 3. email_verified_at in DB must remain strictly NULL (not modified automatically)
    db_user = db_session.query(UserTable).filter_by(email_id=email).first()
    assert db_user.email_verified_at is None

    # 4. Access to protected onboarding while unverified must redirect to /verify-email
    with client.session_transaction() as sess:
        sess['user_id'] = user.user_id
    comp_res = client.get('/company')
    assert comp_res.status_code == 302
    assert "/verify-email" in comp_res.headers["Location"]

    # 5. When Mayank verifies a valid OTP, normal authenticated access is granted
    from app.services.otp_service import create_and_send_otp
    create_and_send_otp(user)
    mayank_otp = get_last_test_otp(email)
    assert mayank_otp is not None

    verify_res = client.post('/api/auth/verify-otp', json={
        "email": email,
        "otp": mayank_otp
    })
    assert verify_res.status_code == 200
    assert verify_res.get_json()["success"] is True

    # Now Mayank has verified timestamp and helper reports True
    db_session.refresh(user)
    assert user.email_verified_at is not None
    assert is_user_email_verified(user) is True

    # Login now succeeds
    login_res2 = client.post('/api/auth/login', json={
        "identifier": email,
        "password": password
    })
    assert login_res2.status_code == 200

def test_no_database_rows_modified_by_applying_compatibility_logic(client):
    # Verify that querying or checking legacy accounts leaves their DB rows untouched
    emails = ["legacy_check1@corp.com", "legacy_check2@corp.com"]
    for i, e in enumerate(emails):
        create_legacy_user(email=e, phone=f"+1415555008{i}")

    for e in emails:
        user = db_session.query(UserTable).filter_by(email_id=e).first()
        assert user.email_verified_at is None
        # Check helper
        assert is_user_email_verified(user) is True
        # Check again from DB
        db_session.refresh(user)
        assert user.email_verified_at is None
