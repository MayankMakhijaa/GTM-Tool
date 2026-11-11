import pytest
import json
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UserRole,
    UsersCompanyDetails,
    UsersICP,
    FeaturePricing,
    UserCreditWallet,
    CreditReservation,
    CreditTransaction,
    ReservationStatus,
    TransactionType,
    GlobalProfiles,
    UsersProfiles,
    ResearchJobs,
    ResearchJobStatus,
    LeadStatus
)
from app.services.credit_service import (
    CreditService,
    InsufficientCreditsError
)
from app.services.gtm_pipeline_service import (
    start_gtm_research_job,
    _execute_gtm_pipeline_worker,
    find_existing_global_candidates,
    persist_qualified_opportunities,
    reconcile_stale_research_jobs,
    CandidateList
)


def _setup_customer(verified=True, credits=100):
    user = UserTable(
        name="GTM Customer",
        email_id=f"gtm_customer_{datetime.utcnow().timestamp()}@scaleflow.io",
        phone_no="+15550009999",
        password_hash="TestPasswordHash123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow() if verified else None,
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    company = UsersCompanyDetails(
        user_id=user.user_id,
        company_name="ScaleFlow AI",
        website_url="https://scaleflow.io",
        description="Autonomous sales prospecting and lead routing platform.",
        what_company_sells="AI sales agents that qualify inbound and outbound B2B leads.",
        products_services="ScaleFlow Agent Suite",
        industry="B2B SaaS / DevTools",
        company_size="11-50 employees"
    )
    icp = UsersICP(
        user_id=user.user_id,
        target_customer="Mid-Market B2B SaaS companies",
        target_jobs_roles="VP of Sales, CRO, Head of RevOps",
        company_size="50-500 employees",
        revenue_range="$5M-$50M ARR",
        industry="Enterprise Software, Cloud Services",
        location="North America, EMEA",
        keywords="sales velocity, inbound triage, HubSpot migration",
        version=1
    )
    db_session.add(company)
    db_session.add(icp)
    db_session.commit()

    if credits > 0:
        CreditService.grant_credits(
            user_id=user.user_id,
            amount=Decimal(str(credits)),
            idempotency_key=f"init_cust_cred_{user.user_id}",
            reason="Initial customer credit balance",
            session=db_session
        )

    return user


# ====================================================================
# 1. REQUEST & RESERVATION TESTS
# ====================================================================

def test_gtm_start_reserves_credits_based_on_active_pricing(flask_app, clean_db):
    """
    Verifies that a valid GTM job start reserves requested_quantity * active unit price,
    recording reservation status RESERVED and updating wallet reserved_balance.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Active pricing is 2.00 per lead; requested 10 leads = 20.00 credits
    result = start_gtm_research_job(flask_app, user_id=uid, target_leads=10)
    assert result["status"] == "QUEUED"
    job_id = result["job_id"]

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("20.00")
    assert wallet["available_balance"] == Decimal("80.00")

    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    assert res_rec is not None
    assert res_rec.status == ReservationStatus.RESERVED.value
    assert res_rec.requested_quantity == 10
    assert res_rec.unit_price_snapshot == Decimal("2.00")
    assert res_rec.reserved_amount == Decimal("20.00")


def test_gtm_start_rejects_insufficient_credits_without_creating_job_or_worker(flask_app, client, clean_db):
    """
    Verifies that if user available credits are insufficient,
    the request returns 402 INSUFFICIENT_CREDITS, no active job is created,
    and no worker is launched.
    """
    user = _setup_customer(credits=10) # 10 credits < 20 required for 10 leads
    uid = user.user_id

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    res = client.post('/api/gtm-opportunities/find', json={"target_leads": 10})
    assert res.status_code == 402
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "INSUFFICIENT_CREDITS"

    # Verify no active or queued job remains
    active_jobs = db_session.query(ResearchJobs).filter_by(user_id=uid).all()
    assert len(active_jobs) == 0

    # Verify no reservation created
    res_count = db_session.query(CreditReservation).filter_by(user_id=uid).count()
    assert res_count == 0


def test_gtm_start_rejects_invalid_lead_counts(client, clean_db):
    """
    Verifies server-side rejection of zero, negative, malformed, non-integer, and out-of-range requests.
    """
    user = _setup_customer(credits=100)
    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    for bad_qty in [0, -5, "ten", 3, 51, 100]:
        res = client.post('/api/gtm-opportunities/find', json={"target_leads": bad_qty})
        assert res.status_code == 400


def test_pricing_change_after_reservation_does_not_affect_snapshot(flask_app, clean_db):
    """
    Verifies that changing feature_pricing after reservation does NOT alter the reservation's
    price snapshot or settlement calculations.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    res = start_gtm_research_job(flask_app, user_id=uid, target_leads=10)
    job_id = res["job_id"]

    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    assert res_rec.unit_price_snapshot == Decimal("2.00")

    # Super Admin increases price to 5.00
    pricing = db_session.query(FeaturePricing).filter_by(feature_code="GTM_RESEARCH_LEAD").first()
    pricing.credit_cost = Decimal("5.00")
    pricing.version = 2
    db_session.commit()

    # Re-query reservation; unit_price_snapshot must still be 2.00
    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    assert res_rec.unit_price_snapshot == Decimal("2.00")
    assert res_rec.pricing_version_snapshot == 1


# ====================================================================
# 2. EXISTING-LEAD-FIRST RESEARCH TESTS
# ====================================================================

def test_existing_global_profiles_sourced_before_new_discovery(flask_app, clean_db):
    """
    Verifies that matching existing GlobalProfiles are sourced and qualified first.
    If existing leads satisfy target_leads, new discovery via Voyager is skipped completely.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Seed 5 matching GlobalProfiles
    for i in range(5):
        gp = GlobalProfiles(
            linkedin_id=f"dir_lead_{i}",
            name=f"Directory Lead {i}",
            role="VP of Sales",
            headline="VP of Sales at SaaS Cloud",
            company=f"CloudScale {i}",
            location="San Francisco, CA",
            profile_url=f"https://www.linkedin.com/in/dir_lead_{i}",
            recommended_no_of_times=1,
            last_updated=datetime.utcnow()
        )
        db_session.add(gp)
    db_session.commit()

    mock_qual = [
        {
            "urn_id": f"dir_lead_{i}",
            "name": f"Directory Lead {i}",
            "role": "VP of Sales",
            "company": f"CloudScale {i}",
            "profile_url": f"https://www.linkedin.com/in/dir_lead_{i}",
            "fit_score": 90,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Matches target role and ICP.",
            "intent_signals": "Active outbound motion",
            "recommended_angle": "Discuss sales velocity"
        }
        for i in range(5)
    ]

    with patch("app.services.gtm_pipeline_service.threading.Thread") as mock_thread, \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=mock_qual), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager") as mock_voyager:

        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)
        job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
        job_id = job.id
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

        assert mock_voyager.call_count == 0

        # Verify job completed with 5 leads delivered from directory
        reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
        assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
        assert reloaded_job.results_count == 5
        assert "5 qualified leads delivered (5 from directory)" in reloaded_job.progress.get("message", "")


def test_discovery_seeks_only_remaining_deficit(flask_app, clean_db):
    """
    Verifies that if existing directory yields 2 leads and requested count is 5,
    Voyager discovery is called seeking at most the deficit (3 leads).
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Seed 2 matching GlobalProfiles
    for i in range(2):
        gp = GlobalProfiles(
            linkedin_id=f"dir_lead_deficit_{i}",
            name=f"Directory Lead {i}",
            role="VP of Sales",
            headline="VP of Sales at SaaS",
            company=f"CloudScale {i}",
            location="San Francisco, CA",
            profile_url=f"https://www.linkedin.com/in/dir_lead_deficit_{i}",
            recommended_no_of_times=1,
            last_updated=datetime.utcnow()
        )
        db_session.add(gp)
    db_session.commit()

    mock_dir_qual = [
        {
            "urn_id": f"dir_lead_deficit_{i}",
            "name": f"Directory Lead {i}",
            "role": "VP of Sales",
            "company": f"CloudScale {i}",
            "profile_url": f"https://www.linkedin.com/in/dir_lead_deficit_{i}",
            "fit_score": 85,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "High ICP alignment.",
            "intent_signals": "Hiring sales reps",
            "recommended_angle": "Lead enrichment"
        }
        for i in range(2)
    ]

    mock_voyager_leads = CandidateList([
        {
            "urn_id": f"voyager_lead_{j}",
            "name": f"Voyager Lead {j}",
            "role": "Head of RevOps",
            "company": f"Voyager Co {j}",
            "location": "New York, NY",
            "profile_url": f"https://www.linkedin.com/in/voyager_lead_{j}",
            "provider": "VOYAGER",
            "source_query": "q1"
        }
        for j in range(3)
    ], status="SUCCESS", provider="VOYAGER")

    mock_voyager_qual = [
        {
            "urn_id": f"voyager_lead_{j}",
            "name": f"Voyager Lead {j}",
            "role": "Head of RevOps",
            "company": f"Voyager Co {j}",
            "profile_url": f"https://www.linkedin.com/in/voyager_lead_{j}",
            "fit_score": 88,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "RevOps ICP match.",
            "intent_signals": "Evaluating sales stack",
            "recommended_angle": "CRM automation"
        }
        for j in range(3)
    ]

    def mock_qualify(candidates, context, cache):
        if any("dir_lead" in c.get("urn_id", "") for c in candidates):
            return mock_dir_qual
        return mock_voyager_qual

    with patch("app.services.gtm_pipeline_service.threading.Thread") as mock_thread, \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", side_effect=mock_qualify), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_voyager_leads) as mock_voyager:

        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)
        job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
        job_id = job.id
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

        # Voyager must have been invoked with limit equal to deficit (5 - 2 = 3)
        assert mock_voyager.call_count == 1
        _, kwargs = mock_voyager.call_args
        assert kwargs.get("limit") == 3

        # Settle charges 5 total leads (2 from directory + 3 from discovery)
        reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
        assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
        assert reloaded_job.results_count == 5


def test_existing_associations_for_same_user_are_not_re_billed(flask_app, clean_db):
    """
    Verifies that a global profile already associated with this user in UsersProfiles
    is excluded from directory candidate sourcing and cannot be re-billed.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Create a GlobalProfile
    gp = GlobalProfiles(
        linkedin_id="already_associated_lead",
        name="Already Associated",
        role="VP of Sales",
        company="Old Match Corp",
        profile_url="https://www.linkedin.com/in/already_associated_lead"
    )
    db_session.add(gp)
    db_session.flush()

    # Pre-associate with user
    up = UsersProfiles(
        user_id=uid,
        global_id=gp.global_id,
        match_score=95,
        qualification_reason="Original qualification reason",
        lead_status=LeadStatus.QUALIFIED.value,
        first_seen_at=datetime.utcnow()
    )
    db_session.add(up)
    db_session.commit()

    # Calling find_existing_global_candidates must NOT return this profile
    candidates = find_existing_global_candidates(uid, {"icp_raw": {"target_jobs_roles": "VP of Sales"}}, limit=10)
    candidate_ids = [c["urn_id"] for c in candidates]
    assert "already_associated_lead" not in candidate_ids


# ====================================================================
# 3. SETTLEMENT & RELEASE TESTS
# ====================================================================

def test_full_success_settles_and_clears_reservation(flask_app, clean_db):
    """
    Verifies that when all requested leads are delivered:
    - Actual charge = Q * P
    - total_balance decreases by charge
    - reserved_balance clears to 0
    - Reservation status becomes SETTLED
    - Settlement ledger transaction is recorded
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res_rec.id

    mock_leads = CandidateList([
        {
            "urn_id": f"lead_full_{i}",
            "name": f"Lead {i}",
            "role": "VP of Sales",
            "company": f"Corp {i}",
            "profile_url": f"https://www.linkedin.com/in/lead_full_{i}",
            "provider": "VOYAGER"
        }
        for i in range(5)
    ], status="SUCCESS", provider="VOYAGER")

    mock_qual = [
        {
            "urn_id": f"lead_full_{i}",
            "name": f"Lead {i}",
            "role": "VP of Sales",
            "company": f"Corp {i}",
            "profile_url": f"https://www.linkedin.com/in/lead_full_{i}",
            "fit_score": 85,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Strong ICP fit."
        }
        for i in range(5)
    ]

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_leads), \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=mock_qual):

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    # 5 leads * 2.00 = 10.00 charged
    assert wallet["total_balance"] == Decimal("90.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("90.00")

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.SETTLED.value
    assert reloaded_res.charged_amount == Decimal("10.00")

    # Check ledger transaction
    tx = db_session.query(CreditTransaction).filter_by(reservation_id=res_id, transaction_type=TransactionType.SETTLEMENT.value).first()
    assert tx is not None
    assert tx.amount == Decimal("-10.00")
    assert tx.quantity == 5


def test_partial_success_charges_only_persisted_leads_and_releases_remainder(flask_app, clean_db):
    """
    Verifies that when only 2 of 5 requested leads are delivered:
    - Actual charge = 2 * 2.00 = 4.00
    - Total balance decreases by 4.00 (from 100 to 96)
    - Full reservation of 10.00 is cleared from reserved_balance
    - Unused 6.00 reserved credits become available again
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res_rec.id

    mock_leads = CandidateList([
        {
            "urn_id": f"lead_partial_{i}",
            "name": f"Lead {i}",
            "role": "VP of Sales",
            "company": f"Corp {i}",
            "profile_url": f"https://www.linkedin.com/in/lead_partial_{i}",
            "provider": "VOYAGER"
        }
        for i in range(2) # Only 2 discovered
    ], status="SUCCESS", provider="VOYAGER")

    mock_qual = [
        {
            "urn_id": f"lead_partial_{i}",
            "name": f"Lead {i}",
            "role": "VP of Sales",
            "company": f"Corp {i}",
            "profile_url": f"https://www.linkedin.com/in/lead_partial_{i}",
            "fit_score": 85,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Strong ICP fit."
        }
        for i in range(2)
    ]

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_leads), \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=mock_qual):

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("96.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("96.00")

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.SETTLED.value
    assert reloaded_res.charged_amount == Decimal("4.00")


def test_zero_results_releases_full_reservation_without_charge(flask_app, clean_db):
    """
    Verifies that when zero leads are qualified:
    - Total balance remains unchanged (100.00)
    - Reserved balance is released back to 0.00
    - Reservation status becomes RELEASED
    - Release ledger transaction is recorded
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res_rec.id

    mock_empty = CandidateList([], status="ZERO_RESULTS", provider="VOYAGER")

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_empty):
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("100.00")

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.RELEASED.value
    assert reloaded_res.charged_amount == Decimal("0.00")

    tx = db_session.query(CreditTransaction).filter_by(reservation_id=res_id, transaction_type=TransactionType.RELEASE.value).first()
    assert tx is not None
    assert tx.amount == Decimal("0.00")
    assert tx.reserved_delta == Decimal("-10.00")


def test_worker_exception_releases_held_reservation_safely(flask_app, clean_db):
    """
    Verifies that an unhandled worker exception does not leave credits stranded in reserved_balance;
    the reservation is safely released.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res_rec = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res_rec.id

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", side_effect=RuntimeError("Simulated unhandled worker crash")):
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("100.00")

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.RELEASED.value


def test_duplicate_worker_execution_does_not_double_charge(flask_app, clean_db):
    """
    Verifies that repeated/duplicate execution of worker on the same job uses
    stable idempotency keys and cannot charge customer twice.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id

    mock_leads = CandidateList([
        {
            "urn_id": "duplicate_test_lead",
            "name": "Dup Lead",
            "role": "VP Sales",
            "company": "Dup Corp",
            "profile_url": "https://www.linkedin.com/in/dup-lead",
            "provider": "VOYAGER"
        }
    ], status="SUCCESS", provider="VOYAGER")

    mock_qual = [
        {
            "urn_id": "duplicate_test_lead",
            "name": "Dup Lead",
            "role": "VP Sales",
            "company": "Dup Corp",
            "profile_url": "https://www.linkedin.com/in/dup-lead",
            "fit_score": 90,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "ICP fit."
        }
    ]

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_leads), \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=mock_qual):

        # First worker execution: delivers 1 lead -> charges 2.00
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)
        wallet_1 = CreditService.get_wallet_balance(uid, session=db_session)
        assert wallet_1["total_balance"] == Decimal("98.00")

        # Second worker execution on same job
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)
        wallet_2 = CreditService.get_wallet_balance(uid, session=db_session)
        # Total balance must remain 98.00; NO double charge!
        assert wallet_2["total_balance"] == Decimal("98.00")
        assert wallet_2["reserved_balance"] == Decimal("0.00")


# ====================================================================
# 4. TICKET 3D.2 RECONCILIATION & SAFE RECOVERY TESTS
# ====================================================================

from datetime import timedelta

def test_reconcile_stale_queued_job_releases_reservation(flask_app, clean_db):
    """
    1. Stale queued job, no results: reservation is released and the job reaches the correct terminal state (FAILED).
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res.id

    # Simulate hard crash: job left QUEUED with heartbeat_at 25 minutes ago
    stale_time = datetime.utcnow() - timedelta(minutes=25)
    job.heartbeat_at = stale_time
    job.created_at = stale_time
    db_session.commit()

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["examined"] >= 1
    assert stats["recovered"] >= 1
    assert stats["failed_to_reconcile"] == 0

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "Job interrupted: stale worker heartbeat" in (reloaded_job.error_message or "")

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.RELEASED.value
    assert reloaded_res.charged_amount == Decimal("0.00")

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("100.00")


def test_reconcile_stale_running_job_settles_partial_results(flask_app, clean_db):
    """
    2. Stale running job, partial results: only eligible, job-attributed qualified associations are charged;
    unused reservation is cleared.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res.id

    # Create 2 durable qualified results attached to this job
    for i in range(2):
        gp = GlobalProfiles(
            linkedin_id=f"stale_partial_lead_{i}",
            name=f"Partial Lead {i}",
            role="Director of Growth",
            company="Acme",
            profile_url=f"https://linkedin.com/in/partial-{i}"
        )
        db_session.add(gp)
        db_session.flush()

        up = UsersProfiles(
            user_id=uid,
            global_id=gp.global_id,
            match_score=85,
            lead_status=LeadStatus.QUALIFIED.value,
            research_job_id=job_id
        )
        db_session.add(up)

    # Simulate hard crash while RUNNING
    stale_time = datetime.utcnow() - timedelta(minutes=30)
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = stale_time
    db_session.commit()

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] >= 1

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "recovery settled 2 durable qualified lead(s)" in reloaded_job.error_message

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.SETTLED.value
    assert reloaded_res.charged_amount == Decimal("4.00")  # 2 leads * 2.00

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("96.00")
    assert wallet["reserved_balance"] == Decimal("0.00")
    assert wallet["available_balance"] == Decimal("96.00")


def test_reconcile_stale_job_with_zero_eligible_results_releases_reservation(flask_app, clean_db):
    """
    3. Stale job with zero eligible results (e.g. leads have match_score < 70 or REJECTED):
    no charge; reservation released.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()
    res_id = res.id

    # Create lead with match_score 50 (<70) and REJECTED
    gp = GlobalProfiles(
        linkedin_id="disqualified_lead_1",
        name="Disqualified Lead",
        profile_url="https://linkedin.com/in/disqualified-1"
    )
    db_session.add(gp)
    db_session.flush()

    up = UsersProfiles(
        user_id=uid,
        global_id=gp.global_id,
        match_score=50,
        lead_status=LeadStatus.REJECTED.value,
        research_job_id=job_id
    )
    db_session.add(up)

    stale_time = datetime.utcnow() - timedelta(minutes=20)
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = stale_time
    db_session.commit()

    reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res_id).first()
    assert reloaded_res.status == ReservationStatus.RELEASED.value
    assert reloaded_res.charged_amount == Decimal("0.00")

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("0.00")


def test_reconcile_already_settled_reservation_preserves_state(flask_app, clean_db):
    """
    4. Already-settled reservation: recovery does not double-charge or release it.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()

    # Pre-settle reservation
    CreditService.settle_reservation(
        reservation_id=res.id,
        actual_quantity=2,
        idempotency_key=f"gtm_job_settle_{job_id}",
        session=db_session
    )

    # Make job stale RUNNING
    stale_time = datetime.utcnow() - timedelta(minutes=40)
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = stale_time
    db_session.commit()

    wallet_before = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet_before["total_balance"] == Decimal("96.00")

    reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)

    wallet_after = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet_after["total_balance"] == Decimal("96.00")
    assert wallet_after["reserved_balance"] == Decimal("0.00")

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "previous settlement" in reloaded_job.error_message


def test_reconcile_already_released_reservation_preserves_state(flask_app, clean_db):
    """
    5. Already-released reservation: recovery does not charge it.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()

    CreditService.release_reservation(
        reservation_id=res.id,
        idempotency_key=f"gtm_job_rel_{job_id}",
        session=db_session
    )

    stale_time = datetime.utcnow() - timedelta(minutes=30)
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = stale_time
    db_session.commit()

    reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")
    assert wallet["reserved_balance"] == Decimal("0.00")

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "previous release" in reloaded_job.error_message


def test_reconcile_skips_fresh_running_heartbeat(flask_app, clean_db):
    """
    6. Fresh running heartbeat: recovery skips the job.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=2)  # Fresh: 2 min ago
    db_session.commit()

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    # The fresh job is not picked up as a candidate for recovery
    assert stats["recovered"] == 0
    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job.id).first()
    assert reloaded_job.status == ResearchJobStatus.RUNNING.value


def test_reconcile_skips_fresh_queued_job_with_null_or_recent_heartbeat(flask_app, clean_db):
    """
    7. Fresh queued job: recovery skips the job.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    # Ensure fresh queued job with NULL heartbeat to verify null-heartbeat handling
    job.heartbeat_at = None
    job.created_at = datetime.utcnow() - timedelta(minutes=2)
    db_session.commit()

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 0

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job.id).first()
    assert reloaded_job.status == ResearchJobStatus.QUEUED.value


def test_reconcile_terminal_job_left_unchanged(flask_app, clean_db):
    """
    8. Terminal job: recovery leaves it unchanged.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.COMPLETED.value,
        budget={"target_leads": 5},
        heartbeat_at=datetime.utcnow() - timedelta(hours=2),
        created_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(job)
    db_session.commit()

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 0

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job.id).first()
    assert reloaded_job.status == ResearchJobStatus.COMPLETED.value


def test_reconcile_foreign_job_results_not_charged(flask_app, clean_db):
    """
    9. Foreign-job results: results attributed to another job are not charged.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Create job 1 (interrupted stale job)
    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job1 = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job1_id = job1.id
    res1 = db_session.query(CreditReservation).filter_by(job_id=job1_id).first()

    # Create another job to act as valid foreign job ID
    job_other = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.COMPLETED.value,
        budget={"target_leads": 5},
        heartbeat_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    db_session.add(job_other)
    db_session.flush()

    # Create foreign lead belonging to job_other.id
    gp = GlobalProfiles(
        linkedin_id="foreign_lead_1",
        name="Foreign Lead",
        profile_url="https://linkedin.com/in/foreign-1"
    )
    db_session.add(gp)
    db_session.flush()

    up = UsersProfiles(
        user_id=uid,
        global_id=gp.global_id,
        match_score=95,
        lead_status=LeadStatus.QUALIFIED.value,
        research_job_id=job_other.id  # foreign job ID!
    )
    db_session.add(up)

    stale_time = datetime.utcnow() - timedelta(minutes=25)
    job1.status = ResearchJobStatus.RUNNING.value
    job1.heartbeat_at = stale_time
    db_session.commit()

    reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)

    # Job 1 has 0 eligible results for itself, so reservation is released, not settled!
    reloaded_res1 = db_session.query(CreditReservation).filter_by(id=res1.id).first()
    assert reloaded_res1.status == ReservationStatus.RELEASED.value
    assert reloaded_res1.charged_amount == Decimal("0.00")

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("100.00")


def test_reconcile_target_limit_caps_charges(flask_app, clean_db):
    """
    10. Target limit: eligible durable results above the job target cannot cause an overcharge.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Job target is 5 leads (minimum allowed target_leads)
    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()

    # Persist 8 durable results for this job (more than target 5)
    for i in range(8):
        gp = GlobalProfiles(
            linkedin_id=f"excess_lead_{i}",
            name=f"Excess Lead {i}",
            profile_url=f"https://linkedin.com/in/excess-{i}"
        )
        db_session.add(gp)
        db_session.flush()

        up = UsersProfiles(
            user_id=uid,
            global_id=gp.global_id,
            match_score=85,
            lead_status=LeadStatus.QUALIFIED.value,
            research_job_id=job_id
        )
        db_session.add(up)

    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)

    reloaded_res = db_session.query(CreditReservation).filter_by(id=res.id).first()
    # Capped at target 5 leads * 2.00 = 10.00, not 8 leads * 2.00 = 16.00!
    assert reloaded_res.charged_amount == Decimal("10.00")
    assert reloaded_res.status == ReservationStatus.SETTLED.value

    wallet = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet["total_balance"] == Decimal("90.00")
    assert wallet["reserved_balance"] == Decimal("0.00")


def test_reconcile_repeated_calls_idempotency(flask_app, clean_db):
    """
    11. Repeated reconciliation: running recovery twice produces no duplicate charge, release, or ledger transaction.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id

    # 1 durable result
    gp = GlobalProfiles(linkedin_id="idemp_lead_1", name="Idemp Lead", profile_url="https://linkedin.com/in/idemp-1")
    db_session.add(gp)
    db_session.flush()
    up = UsersProfiles(user_id=uid, global_id=gp.global_id, match_score=90, lead_status=LeadStatus.QUALIFIED.value, research_job_id=job_id)
    db_session.add(up)

    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    # Call 1
    stats1 = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats1["recovered"] == 1

    wallet1 = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet1["total_balance"] == Decimal("98.00")

    tx_count_1 = db_session.query(CreditTransaction).filter_by(user_id=uid).count()

    # Call 2
    stats2 = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    # The job is now FAILED (terminal), so it is not picked up
    assert stats2["recovered"] == 0

    wallet2 = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet2["total_balance"] == Decimal("98.00")
    tx_count_2 = db_session.query(CreditTransaction).filter_by(user_id=uid).count()
    assert tx_count_1 == tx_count_2


def test_reconcile_concurrent_execution_skip_locked(flask_app, clean_db):
    """
    12. Concurrent recovery: verify that row-locking prevents concurrent recovery workers from colliding on the same job.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    # Establish two independent database sessions from engine to verify row locking
    from app.database import engine
    from sqlalchemy.orm import sessionmaker
    sm = sessionmaker(bind=engine)
    sess1 = sm()
    sess2 = sm()

    try:
        # sess1 locks the job row
        locked_job = sess1.query(ResearchJobs).filter_by(id=job_id).with_for_update().first()
        assert locked_job is not None

        # sess2 runs recovery with SKIP LOCKED
        stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=sess2)
        # Because sess1 holds the row lock, sess2 skips it
        assert stats["recovered"] == 0
        assert stats["skipped"] >= 1

        sess1.rollback()
    finally:
        sess1.close()
        sess2.close()


def test_reconcile_missing_reservation_handled_safely(flask_app, clean_db):
    """
    13. Unexpected/missing reservation: no fabricated credit changes; diagnostic behavior is tested.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    # Create job without reservation
    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 5},
        heartbeat_at=datetime.utcnow() - timedelta(minutes=30),
        created_at=datetime.utcnow() - timedelta(minutes=30)
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    wallet_before = CreditService.get_wallet_balance(uid, session=db_session)

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 1

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "NO_RESERVATION_FOUND" in reloaded_job.error_message

    wallet_after = CreditService.get_wallet_balance(uid, session=db_session)
    # Balances must NOT have changed at all
    assert wallet_after["total_balance"] == wallet_before["total_balance"]
    assert wallet_after["reserved_balance"] == wallet_before["reserved_balance"]


def test_reconcile_failure_between_settlement_and_terminal_update(flask_app, clean_db):
    """
    14. Failure between settlement and terminal job update:
    a subsequent reconciliation repairs the job state without charging twice.
    """
    user = _setup_customer(credits=100)
    uid = user.user_id

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(flask_app, user_id=uid, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=uid).first()
    job_id = job.id
    res = db_session.query(CreditReservation).filter_by(job_id=job_id).first()

    # Pre-settle reservation (simulating settlement succeeded in CreditService, but app crashed before marking job FAILED)
    CreditService.settle_reservation(
        reservation_id=res.id,
        actual_quantity=1,
        idempotency_key=f"gtm_job_settle_{job_id}",
        session=db_session
    )

    # Job is still marked RUNNING with stale heartbeat
    job.status = ResearchJobStatus.RUNNING.value
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    wallet_after_settle = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet_after_settle["total_balance"] == Decimal("98.00")

    # Reconciliation runs now
    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 1

    # Job is now cleanly moved to FAILED
    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "previous settlement" in reloaded_job.error_message

    # Wallet is still 98.00, NOT double charged!
    wallet_final = CreditService.get_wallet_balance(uid, session=db_session)
    assert wallet_final["total_balance"] == Decimal("98.00")
    assert wallet_final["reserved_balance"] == Decimal("0.00")


def test_super_admin_operational_reconcile_endpoint(client, clean_db):
    """
    Verifies that the Super Admin operational reconciliation endpoint
    POST /api/admin/gtm/reconcile functions correctly with admin privileges.
    """
    # 1. Create super admin
    admin = UserTable(
        name="Super Admin",
        email_id="super_admin_reconcile@test.com",
        phone_no="+15551112222",
        password_hash="TestPassword123!",
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    # 2. Create customer with stale job
    cust = _setup_customer(credits=100)
    db_session.add(admin)
    db_session.commit()

    with patch("app.services.gtm_pipeline_service.threading.Thread"):
        start_gtm_research_job(client.application, user_id=cust.user_id, target_leads=5)

    job = db_session.query(ResearchJobs).filter_by(user_id=cust.user_id).first()
    job.heartbeat_at = datetime.utcnow() - timedelta(minutes=30)
    db_session.commit()

    # Log in as admin
    with client.session_transaction() as sess:
        sess["user_id"] = admin.user_id
        sess["user_role"] = UserRole.SUPER_ADMIN.value

    resp = client.post("/api/admin/gtm/reconcile", json={"max_stale_minutes": 15})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["success"] is True
    assert "stats" in data
    assert data["stats"]["recovered"] >= 1



