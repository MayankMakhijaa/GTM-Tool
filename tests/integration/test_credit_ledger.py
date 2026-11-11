import pytest
import threading
from decimal import Decimal
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.database import db_session, engine
from app.models.all_models import (
    UserTable,
    UserRole,
    FeaturePricing,
    UserCreditWallet,
    CreditReservation,
    CreditTransaction,
    ReservationStatus,
    TransactionType
)
from app.services.credit_service import (
    CreditService,
    InsufficientCreditsError,
    IdempotencyConflictError,
    ReservationStateError
)

@pytest.fixture
def test_user(clean_db):
    """Creates a standard verified customer."""
    user = UserTable(
        name="Credit Test User",
        email_id="credit_test@businesscorp.com",
        phone_no="+12025550201",
        password_hash="TestPasswordHash123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def ensure_pricing(clean_db):
    """Ensures standard GTM pricing exists with clean initial state."""
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
        pricing.version = 1
        pricing.is_active = True
    db_session.commit()
    return pricing


def test_wallet_creation_starts_at_zero(test_user):
    """Wallet creation defaults to 0 balance."""
    wallet = CreditService.get_or_create_wallet(test_user.user_id)
    assert wallet.total_balance == Decimal("0.00")
    assert wallet.reserved_balance == Decimal("0.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("0.00")
    assert bal["reserved_balance"] == Decimal("0.00")
    assert bal["available_balance"] == Decimal("0.00")


def test_database_constraint_rejects_negative_or_invalid_balances(test_user):
    """Database check constraints enforce non-negativity and reserved <= total."""
    wallet = CreditService.get_or_create_wallet(test_user.user_id)

    # Negative total_balance rejected
    wallet.total_balance = Decimal("-10.00")
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Reserved > total rejected
    wallet = db_session.query(UserCreditWallet).filter_by(user_id=test_user.user_id).first()
    wallet.total_balance = Decimal("10.00")
    wallet.reserved_balance = Decimal("20.00")
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_grant_credits_updates_wallet_and_ledger_atomically(test_user):
    """Granting credits updates wallet and creates append-only ledger transaction."""
    res = CreditService.grant_credits(
        user_id=test_user.user_id,
        amount=100.00,
        idempotency_key="grant_key_001",
        reason="Purchase Starter Package",
        actor_user_id=test_user.user_id
    )
    assert res["amount"] == Decimal("100.00")
    assert res["balance_after"] == Decimal("100.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("100.00")
    assert bal["available_balance"] == Decimal("100.00")

    tx = db_session.query(CreditTransaction).filter_by(idempotency_key="grant_key_001").first()
    assert tx is not None
    assert tx.transaction_type == TransactionType.ADMIN_GRANT.value
    assert tx.amount == Decimal("100.00")


def test_valid_positive_and_negative_adjustments(test_user):
    """Administrative adjustments can safely increase or decrease balance."""
    CreditService.grant_credits(test_user.user_id, 50.00, "grant_adj_init", "Initial funds")

    # Positive adjustment
    res_pos = CreditService.adjust_credits(test_user.user_id, 20.00, "adj_pos_001", "Promo top-up")
    assert res_pos["balance_after"] == Decimal("70.00")

    # Negative adjustment
    res_neg = CreditService.adjust_credits(test_user.user_id, -30.00, "adj_neg_001", "Billing correction")
    assert res_neg["balance_after"] == Decimal("40.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("40.00")


def test_invalid_adjustment_leaves_no_partial_changes(test_user):
    """Adjustment dropping balance below 0 fails without partial state change."""
    CreditService.grant_credits(test_user.user_id, 10.00, "adj_fail_init", "Initial funds")

    with pytest.raises(ValueError, match="negative total balance"):
        CreditService.adjust_credits(test_user.user_id, -20.00, "adj_fail_too_much", "Invalid deduction")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("10.00")
    assert db_session.query(CreditTransaction).filter_by(idempotency_key="adj_fail_too_much").first() is None


def test_reservation_and_insufficient_balance(test_user, ensure_pricing):
    """Reservation decreases available balance without changing total balance; rejects insufficient balance."""
    CreditService.grant_credits(test_user.user_id, 20.00, "res_test_init", "Initial funds")

    # 1. Reject overspending
    with pytest.raises(InsufficientCreditsError):
        # 15 leads @ 2.00 = 30.00 > available 20.00
        CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 15, "op_overspend")

    # 2. Valid reservation: 5 leads @ 2.00 = 10.00
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 5, "op_valid_01")
    assert res["reserved_amount"] == Decimal("10.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("20.00")
    assert bal["reserved_balance"] == Decimal("10.00")
    assert bal["available_balance"] == Decimal("10.00")


def test_full_settlement_charges_expected_amount_and_clears_reservation(test_user, ensure_pricing):
    """Full settlement charges all reserved quantity and clears reservation."""
    CreditService.grant_credits(test_user.user_id, 50.00, "full_set_init", "Initial funds")
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 10, "op_full_set")
    res_id = res["reservation_id"]

    # Settle full 10 leads (10 @ 2.00 = 20.00)
    set_res = CreditService.settle_reservation(res_id, 10, "set_key_full_001")
    assert set_res["charged_amount"] == Decimal("20.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("30.00")  # 50 - 20
    assert bal["reserved_balance"] == Decimal("0.00")
    assert bal["available_balance"] == Decimal("30.00")

    res_record = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert res_record.status == ReservationStatus.SETTLED.value
    assert res_record.charged_amount == Decimal("20.00")


def test_partial_settlement_charges_only_billable_and_releases_unused(test_user, ensure_pricing):
    """Partial settlement charges only completed leads and returns unused reservation to available balance."""
    CreditService.grant_credits(test_user.user_id, 100.00, "part_set_init", "Initial funds")
    # Reserve 25 leads @ 2.00 = 50.00 reserved
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 25, "op_part_set")
    res_id = res["reservation_id"]

    # Worker only discovered 8 leads (8 @ 2.00 = 16.00)
    set_res = CreditService.settle_reservation(res_id, 8, "set_key_part_001")
    assert set_res["charged_amount"] == Decimal("16.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("84.00")  # 100 - 16
    assert bal["reserved_balance"] == Decimal("0.00")
    assert bal["available_balance"] == Decimal("84.00")


def test_release_returns_all_reserved_credits_without_charging(test_user, ensure_pricing):
    """Release clears reservation with zero charge (e.g. fatal Voyager error or zero results)."""
    CreditService.grant_credits(test_user.user_id, 40.00, "rel_init", "Initial funds")
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 10, "op_release")
    res_id = res["reservation_id"]

    rel_res = CreditService.release_reservation(res_id, "rel_key_001", "LinkedIn session expired")
    assert rel_res["released_amount"] == Decimal("20.00")

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("40.00")
    assert bal["reserved_balance"] == Decimal("0.00")
    assert bal["available_balance"] == Decimal("40.00")

    res_record = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert res_record.status == ReservationStatus.RELEASED.value


def test_idempotency_safe_replay_and_conflict_detection(test_user):
    """Identical idempotency key replays safely; conflicting parameters raise typed conflict."""
    # 1. Grant with key
    res1 = CreditService.grant_credits(test_user.user_id, 25.00, "idem_grant_key", "Grant A")
    assert res1["is_idempotent_replay"] is False

    # 2. Replay with identical parameters
    res2 = CreditService.grant_credits(test_user.user_id, 25.00, "idem_grant_key", "Grant A")
    assert res2["is_idempotent_replay"] is True
    assert res2["transaction_id"] == res1["transaction_id"]

    # Balance was only updated once
    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("25.00")

    # 3. Conflict: same key with different amount
    with pytest.raises(IdempotencyConflictError):
        CreditService.grant_credits(test_user.user_id, 50.00, "idem_grant_key", "Grant Different Amount")


def test_duplicate_settlement_or_release_rejected(test_user, ensure_pricing):
    """Settled or released reservations cannot be modified again."""
    CreditService.grant_credits(test_user.user_id, 50.00, "dup_set_init", "Initial funds")
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 5, "op_dup_set")
    res_id = res["reservation_id"]

    CreditService.settle_reservation(res_id, 5, "dup_set_tx_1")

    # Attempting to settle again with new key raises ReservationStateError
    with pytest.raises(ReservationStateError, match="cannot be settled"):
        CreditService.settle_reservation(res_id, 5, "dup_set_tx_2")

    # Attempting to release a settled reservation raises ReservationStateError
    with pytest.raises(ReservationStateError, match="cannot be released"):
        CreditService.release_reservation(res_id, "dup_rel_tx_1")


def test_pricing_changes_do_not_mutate_existing_reservation_snapshots(test_user, ensure_pricing):
    """Changing feature pricing does not alter price snapshot locked onto active reservation."""
    CreditService.grant_credits(test_user.user_id, 50.00, "snap_init", "Initial funds")
    # Reserve at 2.00
    res = CreditService.reserve_credits(test_user.user_id, "GTM_RESEARCH_LEAD", 5, "op_snapshot")
    res_id = res["reservation_id"]

    try:
        # Admin changes price to 5.00
        pricing = db_session.query(FeaturePricing).filter_by(feature_code="GTM_RESEARCH_LEAD").first()
        pricing.credit_cost = Decimal("5.00")
        pricing.version = 2
        db_session.commit()

        # Settle reservation - must charge at original snapshot 2.00, NOT 5.00
        CreditService.settle_reservation(res_id, 5, "set_snap_tx")

        bal = CreditService.get_wallet_balance(test_user.user_id)
        # Charged 5 * 2.00 = 10.00, so remaining is 40.00 (NOT 50 - 25 = 25.00)
        assert bal["total_balance"] == Decimal("40.00")
    finally:
        # Restore standard pricing for any subsequent tests
        pricing = db_session.query(FeaturePricing).filter_by(feature_code="GTM_RESEARCH_LEAD").first()
        if pricing:
            pricing.credit_cost = Decimal("2.00")
            pricing.version = 1
            db_session.commit()


def test_concurrent_reservations_cannot_overspend(test_user, ensure_pricing):
    """Pessimistic row locking ensures two concurrent threads cannot overspend available balance."""
    # User has 20.00 credits
    CreditService.grant_credits(test_user.user_id, 20.00, "conc_init", "Initial funds")

    # Two concurrent requests both try to reserve 8 leads @ 2.00 = 16.00 (Total 32.00 > 20.00)
    results = []
    errors = []

    def run_reservation(op_id):
        # Dedicated thread session using engine
        from sqlalchemy.orm import sessionmaker
        thread_session = sessionmaker(bind=engine)()
        try:
            res = CreditService.reserve_credits(
                user_id=test_user.user_id,
                feature_code="GTM_RESEARCH_LEAD",
                requested_quantity=8,
                billing_operation_id=op_id,
                session=thread_session
            )
            results.append(res)
        except Exception as e:
            errors.append(e)
        finally:
            thread_session.close()

    t1 = threading.Thread(target=run_reservation, args=("op_conc_1",))
    t2 = threading.Thread(target=run_reservation, args=("op_conc_2",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly 1 thread must succeed and 1 must fail with InsufficientCreditsError
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InsufficientCreditsError)

    bal = CreditService.get_wallet_balance(test_user.user_id)
    assert bal["total_balance"] == Decimal("20.00")
    assert bal["reserved_balance"] == Decimal("16.00")
    assert bal["available_balance"] == Decimal("4.00")
