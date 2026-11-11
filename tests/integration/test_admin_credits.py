import pytest
from decimal import Decimal
from datetime import datetime

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UserRole,
    UserCreditWallet,
    FeaturePricing,
    CreditTransaction,
    CreditReservation,
    AuditLog
)
from app.services.credit_service import CreditService
from app.security.password import hash_password

@pytest.fixture
def admin_test_users(clean_db):
    """
    Creates test accounts:
    - 1 Super Admin
    - 1 Standard Admin
    - 1 Customer with wallet
    - 1 Customer without wallet
    """
    super_admin = UserTable(
        name="Super Admin User",
        email_id="superadmin@fameweb.in",
        phone_no="+12025550301",
        password_hash=hash_password("SuperSecure123!"),
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    admin = UserTable(
        name="Standard Admin User",
        email_id="admin@fameweb.in",
        phone_no="+12025550302",
        password_hash=hash_password("AdminSecure123!"),
        role=UserRole.ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    customer_with_wallet = UserTable(
        name="Customer With Wallet",
        email_id="customer_wallet@clientcorp.com",
        phone_no="+12025550303",
        password_hash=hash_password("CustomerSecure123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    customer_no_wallet = UserTable(
        name="Customer No Wallet",
        email_id="customer_nowallet@clientcorp.com",
        phone_no="+12025550304",
        password_hash=hash_password("CustomerSecure123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add_all([super_admin, admin, customer_with_wallet, customer_no_wallet])
    db_session.commit()

    # Pre-grant initial balance to customer_with_wallet (50 total, 10 reserved)
    CreditService.grant_credits(
        user_id=customer_with_wallet.user_id,
        amount=50.00,
        idempotency_key="init_grant_for_tests",
        reason="Setup balance",
        actor_user_id=super_admin.user_id
    )

    # Ensure Feature Pricing exists
    pricing = db_session.query(FeaturePricing).filter_by(feature_code="GTM_RESEARCH_LEAD").first()
    if not pricing:
        pricing = FeaturePricing(
            feature_code="GTM_RESEARCH_LEAD",
            name="GTM Qualified Lead Discovery",
            unit_name="qualified_lead",
            credit_cost=Decimal("2.00"),
            is_active=True,
            version=1
        )
        db_session.add(pricing)
    else:
        pricing.credit_cost = Decimal("2.00")
        pricing.is_active = True
        pricing.version = 1
    db_session.commit()

    # Reserve 10 credits (5 leads @ 2.00)
    CreditService.reserve_credits(
        user_id=customer_with_wallet.user_id,
        feature_code="GTM_RESEARCH_LEAD",
        requested_quantity=5,
        billing_operation_id="init_res_for_tests"
    )

    return {
        "super_admin": super_admin,
        "admin": admin,
        "customer_with_wallet": customer_with_wallet,
        "customer_no_wallet": customer_no_wallet
    }


# ==============================================================================
# 1. Authorization Tests
# ==============================================================================

def test_unauthenticated_requests_to_credit_endpoints_rejected(client):
    """Unauthenticated requests receive 401 Unauthorized."""
    res = client.get("/api/admin/credits/overview")
    assert res.status_code == 401
    assert res.get_json()["error"] == "UNAUTHORIZED"

    res_post = client.post("/api/admin/credits/users/1/grant", json={
        "amount": 10.00,
        "reason": "Grant test",
        "idempotency_key": "unauth_key"
    })
    assert res_post.status_code == 401


def test_customer_and_standard_admin_cannot_access_credit_endpoints(client, admin_test_users):
    """Ordinary customers and standard admins receive 403 Forbidden on credit endpoints."""
    # 1. Customer
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["customer_with_wallet"].user_id

    res = client.get("/api/admin/credits/overview")
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"

    res_grant = client.post(f"/api/admin/credits/users/{admin_test_users['customer_with_wallet'].user_id}/grant", json={
        "amount": 20.00,
        "reason": "Unauthorized grant",
        "idempotency_key": "cust_grant_attempt"
    })
    assert res_grant.status_code == 403

    # 2. Standard Admin (only SUPER_ADMIN allowed)
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["admin"].user_id

    res_admin = client.get("/api/admin/credits/overview")
    assert res_admin.status_code == 403


# ==============================================================================
# 2. Credit Overview & Directory Tests
# ==============================================================================

def test_credit_overview_aggregations(client, admin_test_users):
    """Super Admin can access aggregated metrics across all customer wallets."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    res = client.get("/api/admin/credits/overview")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    metrics = data["metrics"]

    assert metrics["wallets_count"] >= 1
    assert Decimal(metrics["total_balance"]) == Decimal("50.00")
    assert Decimal(metrics["reserved_balance"]) == Decimal("10.00")
    assert Decimal(metrics["available_balance"]) == Decimal("40.00")
    assert len(data["pricing"]) >= 1


def test_credit_users_left_join_includes_users_without_wallets(client, admin_test_users):
    """Users without wallets are displayed with 0.00 balances via LEFT JOIN without inserting rows."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    # Check database: customer_no_wallet must NOT have a wallet row yet
    wallet_before = db_session.query(UserCreditWallet).filter_by(user_id=admin_test_users["customer_no_wallet"].user_id).first()
    assert wallet_before is None

    res = client.get("/api/admin/credits/users")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    users = data["users"]

    # Locate customer_no_wallet
    user_no_wallet_entry = next((u for u in users if u["user_id"] == admin_test_users["customer_no_wallet"].user_id), None)
    assert user_no_wallet_entry is not None
    assert user_no_wallet_entry["total_balance"] == "0.00"
    assert user_no_wallet_entry["reserved_balance"] == "0.00"
    assert user_no_wallet_entry["available_balance"] == "0.00"

    # Verify no wallet row was silently created just by reading directory
    wallet_after = db_session.query(UserCreditWallet).filter_by(user_id=admin_test_users["customer_no_wallet"].user_id).first()
    assert wallet_after is None


def test_credit_users_filtering_and_nonzero_filter(client, admin_test_users):
    """Filtering by search and nonzero credits works accurately."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    # Nonzero credits only
    res = client.get("/api/admin/credits/users?nonzero_only=true")
    assert res.status_code == 200
    data = res.get_json()
    for u in data["users"]:
        assert Decimal(u["total_balance"]) > Decimal("0.00")

    # Search query
    res_search = client.get("/api/admin/credits/users?search=customer_wallet")
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert len(data_search["users"]) == 1
    assert data_search["users"][0]["user_id"] == admin_test_users["customer_with_wallet"].user_id


# ==============================================================================
# 3. Grants & Adjustments Tests
# ==============================================================================

def test_admin_grant_credits_success_and_audit(client, admin_test_users):
    """Valid grant increments wallet balance, logs ledger entry, and writes AuditLog."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id
    idemp_key = "grant_test_001"

    res = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": 25.50,
        "reason": "Enterprise Bonus Tier",
        "idempotency_key": idemp_key
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert Decimal(data["amount"]) == Decimal("25.50")
    assert Decimal(data["balance_after"]) == Decimal("75.50")
    assert data["is_idempotent_replay"] is False

    # Verify AuditLog created
    audit = db_session.query(AuditLog).filter_by(
        action="ADMIN_GRANT_CREDITS",
        target_user_id=target_uid
    ).order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert audit.admin_user_id == admin_test_users["super_admin"].user_id
    assert audit.metadata_json["amount"] == "25.50"
    assert audit.metadata_json["idempotency_key"] == idemp_key


def test_admin_grant_idempotent_replay_and_conflict(client, admin_test_users):
    """Replaying identical grant returns original outcome; conflicting parameters raise 409."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id
    idemp_key = "grant_idemp_key_100"

    # First call
    res1 = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": 15.00,
        "reason": "Quarterly Incentive",
        "idempotency_key": idemp_key
    })
    assert res1.status_code == 200
    assert res1.get_json()["is_idempotent_replay"] is False

    # Second call (identical) -> Replay
    res2 = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": 15.00,
        "reason": "Quarterly Incentive",
        "idempotency_key": idemp_key
    })
    assert res2.status_code == 200
    assert res2.get_json()["is_idempotent_replay"] is True
    assert res2.get_json()["transaction_id"] == res1.get_json()["transaction_id"]

    # Third call (different amount with same key) -> Conflict 409
    res3 = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": 30.00,
        "reason": "Conflicting amount",
        "idempotency_key": idemp_key
    })
    assert res3.status_code == 409
    assert res3.get_json()["error"] == "IDEMPOTENCY_CONFLICT"


def test_admin_adjustment_valid_positive_and_negative(client, admin_test_users):
    """Admin can apply signed positive and negative adjustments."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id

    # Balance is currently 50.00 total, 10.00 reserved, 40.00 available.
    # Positive adjustment: +10.00 -> total 60.00
    res_pos = client.post(f"/api/admin/credits/users/{target_uid}/adjust", json={
        "amount": 10.00,
        "reason": "Credit balance correction +10",
        "idempotency_key": "adj_pos_001"
    })
    assert res_pos.status_code == 200
    assert Decimal(res_pos.get_json()["balance_after"]) == Decimal("60.00")

    # Negative adjustment: -20.00 -> total 40.00 (still >= reserved 10.00)
    res_neg = client.post(f"/api/admin/credits/users/{target_uid}/adjust", json={
        "amount": -20.00,
        "reason": "Reversing courtesy credit",
        "idempotency_key": "adj_neg_001"
    })
    assert res_neg.status_code == 200
    assert Decimal(res_neg.get_json()["balance_after"]) == Decimal("40.00")


def test_admin_adjustment_rejects_reducing_below_reserved_balance(client, admin_test_users):
    """Negative adjustment cannot reduce total balance below active reserved holds."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id

    # Total is 50.00, reserved is 10.00.
    # An adjustment of -45.00 would drop total to 5.00 < 10.00 reserved -> Must reject!
    res = client.post(f"/api/admin/credits/users/{target_uid}/adjust", json={
        "amount": -45.00,
        "reason": "Over-deduction attempt",
        "idempotency_key": "adj_invalid_neg_001"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "reserved balance" in data["message"].lower()

    # Verify wallet was not modified
    wallet = db_session.query(UserCreditWallet).filter_by(user_id=target_uid).first()
    assert wallet.total_balance == Decimal("50.00")


def test_admin_grant_and_adjust_validation_errors(client, admin_test_users):
    """Invalid amounts, missing reasons, and non-existent users return appropriate 400/404."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id

    # 1. Negative amount on grant
    res_grant_neg = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": -10.00,
        "reason": "Negative grant",
        "idempotency_key": "neg_grant_key"
    })
    assert res_grant_neg.status_code == 400

    # 2. Blank reason
    res_blank_reason = client.post(f"/api/admin/credits/users/{target_uid}/grant", json={
        "amount": 10.00,
        "reason": "   ",
        "idempotency_key": "blank_reason_key"
    })
    assert res_blank_reason.status_code == 400
    assert "reason" in res_blank_reason.get_json()["message"].lower()

    # 3. Non-existent user
    res_404 = client.post("/api/admin/credits/users/999999/grant", json={
        "amount": 10.00,
        "reason": "Missing user",
        "idempotency_key": "missing_user_key"
    })
    assert res_404.status_code == 404


# ==============================================================================
# 4. Transaction History Tests
# ==============================================================================

def test_user_transaction_history_paginated_and_filtered(client, admin_test_users):
    """Super Admin can retrieve paginated ledger history and filter by transaction type."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    target_uid = admin_test_users["customer_with_wallet"].user_id

    res = client.get(f"/api/admin/credits/users/{target_uid}/transactions")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    txs = data["transactions"]
    assert len(txs) >= 2 # Setup grant + reservation

    # Filter by RESERVATION
    res_filter = client.get(f"/api/admin/credits/users/{target_uid}/transactions?type=RESERVATION")
    assert res_filter.status_code == 200
    data_filter = res_filter.get_json()
    for t in data_filter["transactions"]:
        assert t["transaction_type"] == "RESERVATION"


# ==============================================================================
# 5. Feature Pricing Management Tests
# ==============================================================================

def test_feature_pricing_list_and_update(client, admin_test_users):
    """Super Admin can list feature pricing and update unit cost with atomic version increment."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    # 1. List pricing
    res_list = client.get("/api/admin/credits/pricing")
    assert res_list.status_code == 200
    data_list = res_list.get_json()
    assert data_list["success"] is True
    pricing_entry = next(p for p in data_list["pricing"] if p["feature_code"] == "GTM_RESEARCH_LEAD")
    assert pricing_entry["credit_cost"] == "2.00"
    old_version = pricing_entry["version"]

    try:
        # 2. Update unit cost to 3.50
        res_update = client.patch("/api/admin/credits/pricing/GTM_RESEARCH_LEAD", json={
            "credit_cost": 3.50,
            "description": "Updated pricing description"
        })
        assert res_update.status_code == 200
        data_update = res_update.get_json()
        assert data_update["success"] is True
        updated = data_update["pricing"]
        assert updated["credit_cost"] == "3.50"
        assert updated["version"] == old_version + 1
        assert updated["updated_by_user_id"] == admin_test_users["super_admin"].user_id

        # Verify AuditLog created
        audit = db_session.query(AuditLog).filter_by(action="ADMIN_UPDATE_PRICING").order_by(AuditLog.id.desc()).first()
        assert audit is not None
        assert audit.metadata_json["feature_code"] == "GTM_RESEARCH_LEAD"
        assert audit.metadata_json["new_cost"] == "3.50"

        # 3. Existing reservation snapshots remain unaffected
        res_record = db_session.query(CreditReservation).filter_by(billing_operation_id="init_res_for_tests").first()
        assert res_record.unit_price_snapshot == Decimal("2.00")
        assert res_record.pricing_version_snapshot == 1

    finally:
        # Cleanly restore standard pricing
        p = db_session.query(FeaturePricing).filter_by(feature_code="GTM_RESEARCH_LEAD").first()
        if p:
            p.credit_cost = Decimal("2.00")
            p.version = 1
            db_session.commit()


def test_feature_pricing_rejects_negative_or_invalid_costs(client, admin_test_users):
    """Negative or non-numeric costs are rejected with 400 validation error."""
    with client.session_transaction() as sess:
        sess["user_id"] = admin_test_users["super_admin"].user_id

    # Negative cost
    res_neg = client.patch("/api/admin/credits/pricing/GTM_RESEARCH_LEAD", json={
        "credit_cost": -5.00
    })
    assert res_neg.status_code == 400
    assert res_neg.get_json()["error"] == "VALIDATION_ERROR"

    # Malformed text
    res_invalid = client.patch("/api/admin/credits/pricing/GTM_RESEARCH_LEAD", json={
        "credit_cost": "not-a-number"
    })
    assert res_invalid.status_code == 400
    assert res_invalid.get_json()["error"] == "VALIDATION_ERROR"
