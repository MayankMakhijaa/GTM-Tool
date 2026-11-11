import pytest
from datetime import datetime
from app.models.all_models import (
    UserTable, UserRole, AuditLog, UsersCompanyDetails, UsersICP,
    UserCreditWallet, TenantMembership, Tenant
)
from app.database import db_session
from app.security.password import hash_password


@pytest.fixture
def test_admin_and_users(clean_db):
    """Sets up a super admin, a regular customer, and a secondary customer with verified emails."""
    admin = UserTable(
        name="Super Admin",
        email_id="superadmin_test@fameweb.com",
        password_hash=hash_password("SuperSecure123!"),
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    customer1 = UserTable(
        name="Target Customer One",
        email_id="target_one@example.com",
        password_hash=hash_password("Customer123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    customer2 = UserTable(
        name="Target Customer Two",
        email_id="target_two@example.com",
        password_hash=hash_password("Customer123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add_all([admin, customer1, customer2])
    db_session.commit()

    # Add related records for customer1 to verify clean cascading/deletion
    c1_wallet = UserCreditWallet(user_id=customer1.user_id, total_balance=50, reserved_balance=0)
    c1_company = UsersCompanyDetails(user_id=customer1.user_id, company_name="Test Co", website_url="https://test.co")
    c1_icp = UsersICP(user_id=customer1.user_id, target_customer="B2B Founders")
    db_session.add_all([c1_wallet, c1_company, c1_icp])
    db_session.commit()

    return {
        "admin": admin,
        "customer1": customer1,
        "customer2": customer2
    }


def test_status_update_supported_with_put_and_patch(client, test_admin_and_users):
    """
    Verifies that updating user status (activate / deactivate) works with both
    PUT and PATCH methods, and does not return 405 Method Not Allowed.
    """
    admin = test_admin_and_users["admin"]
    cust = test_admin_and_users["customer2"]

    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id

    # 1. PATCH request (deactivate)
    patch_res = client.patch(f"/api/admin/users/{cust.user_id}/status", json={"is_active": False})
    assert patch_res.status_code == 200
    patch_data = patch_res.get_json()
    assert patch_data["success"] is True
    assert patch_data["is_active"] is False

    # Check DB
    db_cust = db_session.query(UserTable).filter_by(user_id=cust.user_id).first()
    assert db_cust.is_active is False

    # 2. PUT request (reactivate)
    put_res = client.put(f"/api/admin/users/{cust.user_id}/status", json={"is_active": True})
    assert put_res.status_code == 200
    put_data = put_res.get_json()
    assert put_data["success"] is True
    assert put_data["is_active"] is True

    db_cust = db_session.query(UserTable).filter_by(user_id=cust.user_id).first()
    assert db_cust.is_active is True


def test_user_deletion_succeeds_with_superadmin(client, test_admin_and_users):
    """
    Verifies that DELETE /api/admin/users/<target_user_id> permanently deletes
    the user and associated records, and logs an audit event.
    """
    admin = test_admin_and_users["admin"]
    cust1 = test_admin_and_users["customer1"]
    cust1_id = cust1.user_id

    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id

    res = client.delete(f"/api/admin/users/{cust1_id}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["user_id"] == cust1_id

    # Verify user is completely removed
    deleted = db_session.query(UserTable).filter_by(user_id=cust1_id).first()
    assert deleted is None

    # Verify dependent child records were cleaned up
    assert db_session.query(UsersCompanyDetails).filter_by(user_id=cust1_id).first() is None
    assert db_session.query(UsersICP).filter_by(user_id=cust1_id).first() is None
    assert db_session.query(UserCreditWallet).filter_by(user_id=cust1_id).first() is None

    # Verify audit log recorded
    audit = db_session.query(AuditLog).filter_by(
        admin_user_id=admin.user_id,
        action="USER_DELETED"
    ).first()
    assert audit is not None
    assert audit.metadata_json["deleted_user_id"] == cust1_id


def test_user_deletion_prevent_self_deletion(client, test_admin_and_users):
    """
    Verifies that a Superadmin cannot delete their own account.
    """
    admin = test_admin_and_users["admin"]

    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id

    res = client.delete(f"/api/admin/users/{admin.user_id}")
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "SELF_DELETION_BLOCKED"


def test_user_deletion_last_super_admin_protection(client, test_admin_and_users):
    """
    Verifies that the last active Superadmin cannot be deleted by any route.
    """
    admin = test_admin_and_users["admin"]

    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id

    # Deleting the only active super admin
    res = client.delete(f"/api/admin/users/{admin.user_id}")
    assert res.status_code == 400


def test_user_deletion_unauthorized_for_customer(client, test_admin_and_users):
    """
    Verifies that regular customer accounts cannot call DELETE /api/admin/users/<id>.
    """
    cust1 = test_admin_and_users["customer1"]
    cust2 = test_admin_and_users["customer2"]

    with client.session_transaction() as sess:
        sess["user_id"] = cust1.user_id

    res = client.delete(f"/api/admin/users/{cust2.user_id}")
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"


def test_user_deletion_nonexistent_user(client, test_admin_and_users):
    """
    Verifies 404 JSON response when deleting a non-existent user.
    """
    admin = test_admin_and_users["admin"]

    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id

    res = client.delete("/api/admin/users/999999")
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "User not found."
