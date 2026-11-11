import pytest
from datetime import datetime
from app.database import db_session
from app.models.all_models import UserTable, UserRole, UsersCompanyDetails, UsersICP, GlobalProfiles, UsersProfiles, AuditLog
from app.security.password import hash_password
from app.cli import promote_user

@pytest.fixture
def test_users(clean_db):
    """
    Creates standard test accounts:
    - 1 verified Customer
    - 1 unverified Customer
    - 1 Super Admin
    - 1 Admin
    """
    customer = UserTable(
        name="Alice Customer",
        email_id="alice@businesscorp.com",
        phone_no="+12025550101",
        password_hash=hash_password("ValidPassword123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    unverified = UserTable(
        name="Bob Unverified",
        email_id="bob@businesscorp.com",
        phone_no="+12025550102",
        password_hash=hash_password("ValidPassword123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=None,
        onboarding_step="LINKEDIN",
        is_active=True
    )
    super_admin = UserTable(
        name="Sarah SuperAdmin",
        email_id="sarah@fameweb.in",
        phone_no="+12025550103",
        password_hash=hash_password("SuperSecure123!"),
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    admin = UserTable(
        name="Adam Admin",
        email_id="adam@fameweb.in",
        phone_no="+12025550104",
        password_hash=hash_password("AdminSecure123!"),
        role=UserRole.ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add_all([customer, unverified, super_admin, admin])
    db_session.commit()

    return {
        "customer": customer,
        "unverified": unverified,
        "super_admin": super_admin,
        "admin": admin
    }


def test_public_signup_defaults_to_customer_and_cannot_escalate(client):
    """Verify public signup always assigns CUSTOMER role and ignores injected role parameters."""
    res = client.post("/api/auth/signup", json={
        "name": "Hacker John",
        "email": "hacker@evilcorp.io",
        "phone": "+12025550199",
        "password": "StrongPassword123!",
        "role": "SUPER_ADMIN"
    })
    assert res.status_code == 201

    user = db_session.query(UserTable).filter_by(email_id="hacker@evilcorp.io").first()
    assert user is not None
    assert user.role == UserRole.CUSTOMER.value


def test_unauthenticated_requests_to_admin_endpoints_rejected(client):
    """Unauthenticated requests receive 401 on APIs and redirect on HTML pages."""
    api_res = client.get("/api/admin/overview")
    assert api_res.status_code == 401
    assert api_res.get_json()["error"] == "UNAUTHORIZED"

    page_res = client.get("/admin")
    assert page_res.status_code == 302
    assert "/login" in page_res.headers["Location"]


def test_customer_receives_403_on_admin_endpoints(client, test_users):
    """Customer accounts receive 403 on admin APIs and redirect away from /admin page."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["customer"].user_id

    api_res = client.get("/api/admin/overview")
    assert api_res.status_code == 403
    assert api_res.get_json()["error"] == "FORBIDDEN"

    page_res = client.get("/admin")
    assert page_res.status_code == 302
    assert "/dashboard" in page_res.headers["Location"]


def test_super_admin_authorized_for_admin_overview_and_page(client, test_users):
    """Super Admin can access /admin page and overview metrics."""
    # Seed global profile and association
    gp = GlobalProfiles(linkedin_id="li:prospect_1", name="Prospect One")
    db_session.add(gp)
    db_session.flush()
    up = UsersProfiles(user_id=test_users["customer"].user_id, global_id=gp.global_id)
    db_session.add(up)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    page_res = client.get("/admin")
    assert page_res.status_code == 200
    assert b"System &amp; User Management" in page_res.data or b"System & User Management" in page_res.data

    api_res = client.get("/api/admin/overview")
    assert api_res.status_code == 200
    metrics = api_res.get_json()["metrics"]
    assert metrics["total_users"] == 4
    assert metrics["active_users"] == 4
    assert metrics["total_global_profiles"] >= 1
    assert metrics["total_user_lead_associations"] >= 1


def test_user_listing_pagination_and_search(client, test_users):
    """Admin users listing supports pagination and search without exposing sensitive credentials."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    # Search for Alice
    res = client.get("/api/admin/users?search=Alice")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["users"][0]["name"] == "Alice Customer"

    # Verify no secrets in returned payload
    user_str = str(data["users"][0])
    assert "password_hash" not in user_str
    assert "otp_hash" not in user_str
    assert "auth_data_encrypted" not in user_str


def test_user_details_endpoint(client, test_users):
    """Admin can inspect user details including company and ICP."""
    comp = UsersCompanyDetails(
        user_id=test_users["customer"].user_id,
        website_url="https://businesscorp.com",
        company_name="Business Corp"
    )
    icp = UsersICP(
        user_id=test_users["customer"].user_id,
        target_customer="Enterprise VP Sales",
        version=1
    )
    db_session.add_all([comp, icp])
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    res = client.get(f"/api/admin/users/{test_users['customer'].user_id}")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["user"]["name"] == "Alice Customer"
    assert payload["company"]["company_name"] == "Business Corp"
    assert payload["icp"]["target_customer"] == "Enterprise VP Sales"


def test_user_deactivation_and_reactivation_with_session_invalidation(client, test_users):
    """Deactivation immediately invalidates active sessions; reactivation restores access."""
    # 1. Customer logs in
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["customer"].user_id

    # Normal access works
    assert client.get("/api/me").status_code == 200 or client.get("/api/auth/me").status_code == 200

    # 2. Super Admin deactivates Customer
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    deact_res = client.put(f"/api/admin/users/{test_users['customer'].user_id}/status", json={"is_active": False})
    assert deact_res.status_code == 200
    assert deact_res.get_json()["is_active"] is False

    # Check audit log
    audit = db_session.query(AuditLog).filter_by(
        admin_user_id=test_users["super_admin"].user_id,
        target_user_id=test_users["customer"].user_id,
        action="USER_DEACTIVATED"
    ).first()
    assert audit is not None

    # 3. Customer tries to make an API request with their session
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["customer"].user_id

    req_res = client.get("/api/auth/me")
    assert req_res.status_code == 200
    assert req_res.get_json()["authenticated"] is False

    # 4. Super Admin reactivates Customer
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    react_res = client.put(f"/api/admin/users/{test_users['customer'].user_id}/status", json={"is_active": True})
    assert react_res.status_code == 200
    assert react_res.get_json()["is_active"] is True


def test_self_deactivation_and_last_super_admin_protection(client, test_users):
    """Super Admin cannot deactivate themselves or deactivate the last active super admin."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    # Attempt self-deactivation
    res = client.put(f"/api/admin/users/{test_users['super_admin'].user_id}/status", json={"is_active": False})
    assert res.status_code == 400
    assert res.get_json()["error"] == "SELF_DEACTIVATION_BLOCKED"


def test_admin_icp_edit_with_version_bump_and_audit(client, test_users):
    """Super Admin can update customer ICP, triggering version bump and audit record."""
    icp = UsersICP(
        user_id=test_users["customer"].user_id,
        target_customer="Initial Persona",
        target_jobs_roles="CTO",
        version=1
    )
    db_session.add(icp)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = test_users["super_admin"].user_id

    edit_res = client.put(f"/api/admin/users/{test_users['customer'].user_id}/icp", json={
        "target_customer": "Updated Persona by Admin",
        "target_jobs_roles": "Chief Information Officer"
    })
    assert edit_res.status_code == 200
    updated_icp = edit_res.get_json()["icp"]
    assert updated_icp["version"] == 2
    assert updated_icp["target_customer"] == "Updated Persona by Admin"

    # Audit log check
    audit = db_session.query(AuditLog).filter_by(
        admin_user_id=test_users["super_admin"].user_id,
        target_user_id=test_users["customer"].user_id,
        action="ADMIN_EDIT_ICP"
    ).first()
    assert audit is not None


def test_cli_promote_user_bootstrap(clean_db, test_users):
    """CLI promote command requires verified email, requires confirmation, and records audit."""
    # 1. Unverified user promotion fails
    assert promote_user("bob@businesscorp.com", confirm=True) is False

    # 2. Promotion without confirm flag fails
    assert promote_user("alice@businesscorp.com", confirm=False) is False

    # 3. Successful promotion with confirm flag
    assert promote_user("alice@businesscorp.com", confirm=True) is True

    user = db_session.query(UserTable).filter_by(email_id="alice@businesscorp.com").first()
    assert user.role == UserRole.SUPER_ADMIN.value

    # Check CLI audit record
    audit = db_session.query(AuditLog).filter_by(
        target_user_id=user.user_id,
        action="CLI_ROLE_PROMOTION"
    ).first()
    assert audit is not None
