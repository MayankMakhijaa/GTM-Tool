import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UserRole,
    ResearchJobs,
    ResearchJobStatus,
    AIProviderUsageLog
)
from app.security.password import hash_password
from app.services.credit_service import CreditService


@pytest.fixture
def admin_rbac_users(clean_db):
    """
    Creates standard test accounts:
    - 1 Super Admin
    - 1 Standard Admin
    - 1 Customer
    """
    suffix = str(uuid.uuid4())[:8]
    super_admin = UserTable(
        name="Super Admin Telemetry",
        email_id=f"superadmin_{suffix}@fameweb.in",
        phone_no=f"+1202555{suffix[:4]}",
        password_hash=hash_password("SuperSecure123!"),
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    admin = UserTable(
        name="Standard Admin Telemetry",
        email_id=f"admin_{suffix}@fameweb.in",
        phone_no=f"+1202556{suffix[:4]}",
        password_hash=hash_password("AdminSecure123!"),
        role=UserRole.ADMIN.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    customer = UserTable(
        name="Customer Telemetry",
        email_id=f"customer_{suffix}@client.com",
        phone_no=f"+1202557{suffix[:4]}",
        password_hash=hash_password("Customer123!"),
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add_all([super_admin, admin, customer])
    db_session.commit()

    return {
        "super_admin": super_admin,
        "admin": admin,
        "customer": customer
    }


def _seed_sample_ai_usage_logs(user_id, job_id=None):
    """
    Seeds diverse AI usage records for testing aggregations, filters, nulls, and statuses.
    """
    now = datetime.utcnow()
    corr_1 = str(uuid.uuid4())
    corr_2 = str(uuid.uuid4())

    logs = [
        # Log 1: Success with full metadata and known cost
        AIProviderUsageLog(
            user_id=user_id,
            job_id=job_id,
            correlation_id=corr_1,
            provider="GEMINI",
            model_name="gemini-3.5-flash-lite",
            operation="SEARCH_PLANNING",
            status="SUCCESS",
            prompt_tokens=1000,
            completion_tokens=200,
            total_tokens=1200,
            duration_ms=450,
            estimated_cost_usd=Decimal("0.000800"),
            provider_currency="USD",
            created_at=now - timedelta(hours=2)
        ),
        # Log 2: Success with known cost
        AIProviderUsageLog(
            user_id=user_id,
            job_id=job_id,
            correlation_id=corr_1,
            provider="GEMINI",
            model_name="gemini-3.8-flash",
            operation="CANDIDATE_QUALIFICATION",
            status="SUCCESS",
            prompt_tokens=2000,
            completion_tokens=500,
            total_tokens=2500,
            duration_ms=800,
            estimated_cost_usd=Decimal("0.003375"),
            provider_currency="USD",
            created_at=now - timedelta(hours=5)
        ),
        # Log 3: Failed attempt with known cost from partial usage
        AIProviderUsageLog(
            user_id=user_id,
            job_id=job_id,
            correlation_id=corr_2,
            provider="GEMINI",
            model_name="gemini-2.5-flash",
            operation="SEARCH_PLANNING",
            status="FAILED",
            prompt_tokens=500,
            completion_tokens=50,
            total_tokens=550,
            duration_ms=300,
            estimated_cost_usd=Decimal("0.000275"),
            error_category="429 Resource Exhausted",
            provider_currency="USD",
            created_at=now - timedelta(days=1)
        ),
        # Log 4: Failed attempt with missing usage metadata and unknown cost (NULL)
        AIProviderUsageLog(
            user_id=user_id,
            job_id=job_id,
            correlation_id=corr_2,
            provider="GEMINI",
            model_name="gemini-3.5-flash-lite",
            operation="CANDIDATE_QUALIFICATION",
            status="FAILED",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            duration_ms=120,
            estimated_cost_usd=None,
            error_category="ConnectionError",
            provider_currency="USD",
            created_at=now - timedelta(days=2)
        ),
        # Log 5: Older record outside 24h window, within 7d
        AIProviderUsageLog(
            user_id=user_id,
            job_id=job_id,
            correlation_id=str(uuid.uuid4()),
            provider="GEMINI",
            model_name="gemini-3.5-flash-lite",
            operation="SEARCH_PLANNING",
            status="SUCCESS",
            prompt_tokens=1500,
            completion_tokens=300,
            total_tokens=1800,
            duration_ms=500,
            estimated_cost_usd=Decimal("0.001200"),
            provider_currency="USD",
            created_at=now - timedelta(days=4)
        )
    ]
    db_session.add_all(logs)
    db_session.commit()
    return logs


# ====================================================================
# TICKET 3F: SUPER ADMIN AI COST & USAGE DASHBOARD TESTS
# ====================================================================

def test_super_admin_can_access_endpoints(client, admin_rbac_users):
    """
    1. Super Admin can access the overview, records, and filter endpoints.
    """
    sa = admin_rbac_users["super_admin"]
    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Overview
    res = client.get('/api/admin/ai-usage/overview')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "summary" in data
    assert "breakdowns" in data
    assert data["currency"] == "USD"

    # Records
    res_rec = client.get('/api/admin/ai-usage/records')
    assert res_rec.status_code == 200
    data_rec = res_rec.get_json()
    assert data_rec["success"] is True
    assert "records" in data_rec
    assert "pagination" in data_rec

    # Filters
    res_filt = client.get('/api/admin/ai-usage/filters')
    assert res_filt.status_code == 200
    data_filt = res_filt.get_json()
    assert data_filt["success"] is True
    assert "models" in data_filt
    assert "operations" in data_filt


def test_unauthenticated_and_non_super_admin_rejected(client, admin_rbac_users):
    """
    2. Unauthenticated users, standard Admins, and Customers are rejected.
    """
    # Unauthenticated -> redirect or 401
    res = client.get('/api/admin/ai-usage/overview')
    assert res.status_code in (302, 401, 403)

    # Customer -> 403
    with client.session_transaction() as sess:
        sess["user_id"] = admin_rbac_users["customer"].user_id
    res_cust = client.get('/api/admin/ai-usage/overview')
    assert res_cust.status_code == 403

    # Standard Admin -> 403 (Super Admin only!)
    with client.session_transaction() as sess:
        sess["user_id"] = admin_rbac_users["admin"].user_id
    res_admin = client.get('/api/admin/ai-usage/overview')
    assert res_admin.status_code == 403

    res_rec = client.get('/api/admin/ai-usage/records')
    assert res_rec.status_code == 403

    res_filt = client.get('/api/admin/ai-usage/filters')
    assert res_filt.status_code == 403


def test_overview_aggregations_and_known_vs_unknown_costs(client, admin_rbac_users):
    """
    5, 6, 7. Known costs are aggregated correctly; NULL costs are counted separately
    and never treated as confirmed zero; missing token counts do not fabricate totals.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]
    _seed_sample_ai_usage_logs(cust.user_id)

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    res = client.get('/api/admin/ai-usage/overview')
    assert res.status_code == 200
    data = res.get_json()

    s = data["summary"]
    # Total seeded logs within last 7 days = 5
    assert s["total_attempts"] == 5
    assert s["successful_attempts"] == 3
    assert s["failed_attempts"] == 2
    assert s["success_rate"] == 60.0

    # Token totals: 1000 + 2000 + 500 + 1500 = 5000 prompt
    assert s["tokens"]["prompt_tokens"] == 5000
    # 200 + 500 + 50 + 300 = 1050 comp
    assert s["tokens"]["completion_tokens"] == 1050
    # 1200 + 2500 + 550 + 1800 = 6050 total
    assert s["tokens"]["total_tokens"] == 6050
    # Missing token metadata count: exactly 1 log has NULL tokens
    assert s["tokens"]["missing_metadata_count"] == 1

    # Known cost: 0.000800 + 0.003375 + 0.000275 + 0.001200 = 0.005650
    assert Decimal(s["costs"]["total_estimated_usd"]) == Decimal("0.005650")
    # Unknown cost count: exactly 1 log has NULL cost
    assert s["costs"]["unknown_cost_count"] == 1

    # Latency
    assert s["latency"]["avg_duration_ms"] > 0
    assert s["latency"]["median_duration_ms"] > 0

    # Breakdowns exist
    assert len(data["breakdowns"]["by_model"]) > 0
    assert len(data["breakdowns"]["by_operation"]) > 0


def test_filters_and_pagination(client, admin_rbac_users):
    """
    3, 4. Date, status, provider, model, operation, user, and job filters work correctly;
    pagination is bounded, stable, and deterministic.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    job = ResearchJobs(user_id=cust.user_id, status=ResearchJobStatus.COMPLETED.value, budget={"target_leads": 5})
    db_session.add(job)
    db_session.commit()

    _seed_sample_ai_usage_logs(cust.user_id, job_id=job.id)

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Filter by model
    res_m = client.get('/api/admin/ai-usage/records?model=gemini-3.8-flash')
    data_m = res_m.get_json()
    assert data_m["success"] is True
    assert len(data_m["records"]) == 1
    assert data_m["records"][0]["model_name"] == "gemini-3.8-flash"

    # Filter by status: FAILED
    res_f = client.get('/api/admin/ai-usage/records?status=FAILED')
    data_f = res_f.get_json()
    assert len(data_f["records"]) == 2
    for r in data_f["records"]:
        assert r["status"] == "FAILED"

    # Filter by user_id and job_id
    res_uj = client.get(f'/api/admin/ai-usage/records?user_id={cust.user_id}&job_id={job.id}')
    data_uj = res_uj.get_json()
    assert len(data_uj["records"]) == 5

    # Pagination: limit=2, page=1
    res_p1 = client.get('/api/admin/ai-usage/records?limit=2&page=1')
    data_p1 = res_p1.get_json()
    assert len(data_p1["records"]) == 2
    assert data_p1["pagination"]["total_count"] == 5
    assert data_p1["pagination"]["total_pages"] == 3
    assert data_p1["pagination"]["has_next"] is True
    assert data_p1["pagination"]["has_prev"] is False

    # Page 2
    res_p2 = client.get('/api/admin/ai-usage/records?limit=2&page=2')
    data_p2 = res_p2.get_json()
    assert len(data_p2["records"]) == 2
    # Ensure disjoint records across pages (deterministic ordering)
    ids_p1 = [r["id"] for r in data_p1["records"]]
    ids_p2 = [r["id"] for r in data_p2["records"]]
    assert set(ids_p1).isdisjoint(set(ids_p2))


def test_empty_telemetry_produces_valid_empty_responses(client, admin_rbac_users):
    """
    9. Empty telemetry produces valid empty dashboard responses without crashing.
    """
    sa = admin_rbac_users["super_admin"]
    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Overview with no data in date range
    res = client.get('/api/admin/ai-usage/overview?start_date=2020-01-01T00:00:00Z&end_date=2020-01-02T00:00:00Z')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["summary"]["total_attempts"] == 0
    assert Decimal(data["summary"]["costs"]["total_estimated_usd"]) == Decimal("0.000000")
    assert data["summary"]["costs"]["unknown_cost_count"] == 0
    assert data["breakdowns"]["by_model"] == []

    # Records with no data
    res_rec = client.get('/api/admin/ai-usage/records?start_date=2020-01-01T00:00:00Z&end_date=2020-01-02T00:00:00Z')
    assert res_rec.status_code == 200
    data_rec = res_rec.get_json()
    assert data_rec["records"] == []
    assert data_rec["pagination"]["total_count"] == 0

    # Filters return safe fallback lists
    res_filt = client.get('/api/admin/ai-usage/filters')
    assert res_filt.status_code == 200
    data_filt = res_filt.get_json()
    assert len(data_filt["models"]) > 0


def test_malformed_inputs_handled_safely(client, admin_rbac_users):
    """
    10. Malformed dates, inverted ranges, oversized page sizes, and invalid filters handled safely.
    """
    sa = admin_rbac_users["super_admin"]
    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Inverted date range (start > end) -> handled by swapping bounds
    res = client.get('/api/admin/ai-usage/overview?start_date=2026-10-24T00:00:00Z&end_date=2026-10-01T00:00:00Z')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Garbage date strings -> fall back to default window
    res_bad = client.get('/api/admin/ai-usage/overview?start_date=NOT_A_DATE&end_date=GARBAGE')
    assert res_bad.status_code == 200
    assert res_bad.get_json()["success"] is True

    # Oversized limit -> capped at 100
    res_limit = client.get('/api/admin/ai-usage/records?limit=999999&page=-5')
    assert res_limit.status_code == 200
    pag = res_limit.get_json()["pagination"]
    assert pag["limit"] == 100
    assert pag["page"] == 1

    # Invalid user_id filter (non-integer) -> ignored safely
    res_uid = client.get('/api/admin/ai-usage/records?user_id=DROP_TABLE_USERS')
    assert res_uid.status_code == 200


def test_sensitive_payloads_never_exposed(client, admin_rbac_users):
    """
    11. Sensitive payloads and credentials never appear in API responses.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    log = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="FAILED",
        error_category="Invalid API key payload: [REDACTED_API_KEY]",
        created_at=datetime.utcnow()
    )
    db_session.add(log)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    res = client.get(f'/api/admin/ai-usage/records?correlation_id={log.correlation_id}')
    assert res.status_code == 200
    rec = res.get_json()["records"][0]

    # Verify field whitelist: no prompt, completion, or credentials
    assert "prompt" not in rec
    assert "completion" not in rec
    assert "api_key" not in rec
    assert "cookie" not in rec


def test_dashboard_does_not_affect_customer_credits(client, admin_rbac_users):
    """
    12. Dashboard reads never modify customer-credit balances, reservations, or ledger entries.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    CreditService.grant_credits(
        user_id=cust.user_id,
        amount=Decimal("50.00"),
        idempotency_key=f"init_cust_dash_{cust.user_id}",
        reason="Testing",
        session=db_session
    )

    wallet_before = CreditService.get_wallet_balance(cust.user_id, session=db_session)

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Call dashboard endpoints repeatedly
    for _ in range(3):
        client.get('/api/admin/ai-usage/overview')
        client.get('/api/admin/ai-usage/records')
        client.get('/api/admin/ai-usage/filters')

    wallet_after = CreditService.get_wallet_balance(cust.user_id, session=db_session)
    assert wallet_after["total_balance"] == wallet_before["total_balance"]
    assert wallet_after["available_balance"] == wallet_before["available_balance"]
    assert wallet_after["reserved_balance"] == wallet_before["reserved_balance"]


# ====================================================================
# TICKET 3F.1: COMPLETENESS & AGGREGATION AUDIT TESTS
# ====================================================================

def test_provider_filter_options_and_records_api(client, admin_rbac_users):
    """
    Ticket 3F.1 Requirement 1 & 2:
    - Provider options appear in GET /api/admin/ai-usage/filters.
    - Records API filters by provider correctly and combines with model, status, pagination.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    # Seed logs with different providers
    log_gemini = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="SUCCESS",
        prompt_tokens=500,
        completion_tokens=100,
        total_tokens=600,
        estimated_cost_usd=Decimal("0.000400"),
        created_at=datetime.utcnow() - timedelta(hours=1)
    )
    log_voyager = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="VOYAGER",
        model_name="voyager-api",
        operation="VOYAGER_SEARCH",
        status="SUCCESS",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost_usd=None,
        created_at=datetime.utcnow() - timedelta(hours=2)
    )
    log_jina = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="JINA",
        model_name="jina-reader",
        operation="PAGE_FETCH",
        status="FAILED",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost_usd=None,
        created_at=datetime.utcnow() - timedelta(hours=3)
    )
    db_session.add_all([log_gemini, log_voyager, log_jina])
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # 1. Filters endpoint returns all providers
    res_filt = client.get('/api/admin/ai-usage/filters')
    assert res_filt.status_code == 200
    providers = res_filt.get_json()["providers"]
    assert "GEMINI" in providers
    assert "VOYAGER" in providers
    assert "JINA" in providers

    # 2. Filter records by provider=GEMINI
    res_gemini = client.get('/api/admin/ai-usage/records?provider=GEMINI')
    assert res_gemini.status_code == 200
    data_g = res_gemini.get_json()
    assert all(r["provider"] == "GEMINI" for r in data_g["records"])
    assert any(r["id"] == log_gemini.id for r in data_g["records"])
    assert not any(r["id"] in (log_voyager.id, log_jina.id) for r in data_g["records"])

    # 3. Filter records by provider=VOYAGER
    res_voy = client.get('/api/admin/ai-usage/records?provider=VOYAGER')
    assert res_voy.status_code == 200
    data_v = res_voy.get_json()
    assert len(data_v["records"]) == 1
    assert data_v["records"][0]["id"] == log_voyager.id

    # 4. Composition of provider with model and status
    res_combo = client.get('/api/admin/ai-usage/records?provider=GEMINI&model=gemini-3.5-flash-lite&status=SUCCESS')
    assert res_combo.status_code == 200
    data_c = res_combo.get_json()
    assert any(r["id"] == log_gemini.id for r in data_c["records"])

    # Non-matching combo returns 0
    res_no_match = client.get('/api/admin/ai-usage/records?provider=GEMINI&status=FAILED')
    assert res_no_match.status_code == 200
    assert not any(r["id"] == log_gemini.id for r in res_no_match.get_json()["records"])


def test_daily_trends_time_series_data_and_ui_completeness(client, admin_rbac_users):
    """
    Ticket 3F.1 Requirement 3 & 4:
    - Time-series visualizations: cost-over-time and token-usage-over-time driven by daily_trends.
    - Unknown-cost records are visibly separated via unknown_cost_count.
    - Single-day and empty date ranges render safely.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    now = datetime.utcnow()
    # Log with known cost
    log_priced = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="SUCCESS",
        prompt_tokens=1000,
        completion_tokens=200,
        total_tokens=1200,
        estimated_cost_usd=Decimal("0.000800"),
        created_at=now
    )
    # Log with unknown cost (NULL) on the same day
    log_unpriced = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-fallback-unknown",
        operation="CANDIDATE_QUALIFICATION",
        status="SUCCESS",
        prompt_tokens=500,
        completion_tokens=100,
        total_tokens=600,
        estimated_cost_usd=None,
        created_at=now
    )
    db_session.add_all([log_priced, log_unpriced])
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Overview returns daily_trends with unknown_cost_count separated
    res = client.get('/api/admin/ai-usage/overview')
    assert res.status_code == 200
    data = res.get_json()
    daily_trends = data["breakdowns"]["daily_trends"]
    assert len(daily_trends) >= 1

    today_str = now.strftime('%Y-%m-%d')
    today_trend = next((d for d in daily_trends if d["date"] == today_str), None)
    assert today_trend is not None
    assert today_trend["attempts"] >= 2
    assert today_trend["total_tokens"] >= 1800
    assert Decimal(today_trend["estimated_cost_usd"]) >= Decimal("0.000800")
    # Unknown-cost records are counted and separated!
    assert today_trend["unknown_cost_count"] >= 1

    # Single-day date range
    single_day_start = now.strftime('%Y-%m-%dT00:00:00Z')
    single_day_end = now.strftime('%Y-%m-%dT23:59:59Z')
    res_single = client.get(f'/api/admin/ai-usage/overview?start_date={single_day_start}&end_date={single_day_end}')
    assert res_single.status_code == 200
    data_single = res_single.get_json()
    assert data_single["success"] is True
    assert len(data_single["breakdowns"]["daily_trends"]) <= 1


def test_utc_daily_grouping_around_midnight(client, admin_rbac_users):
    """
    Ticket 3F.1 Requirement 6:
    UTC daily grouping is consistent around midnight boundaries (23:59:30 UTC vs 00:00:30 UTC).
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    # Pick an explicit fixed date at UTC midnight
    day1_night = datetime(2026, 6, 15, 23, 59, 30)
    day2_morn = datetime(2026, 6, 16, 0, 0, 30)

    log_day1 = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="SUCCESS",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        estimated_cost_usd=Decimal("0.000100"),
        created_at=day1_night
    )
    log_day2 = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="SUCCESS",
        prompt_tokens=200,
        completion_tokens=40,
        total_tokens=240,
        estimated_cost_usd=Decimal("0.000200"),
        created_at=day2_morn
    )
    db_session.add_all([log_day1, log_day2])
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    # Query overview covering these two days in UTC
    res = client.get('/api/admin/ai-usage/overview?start_date=2026-06-15T00:00:00Z&end_date=2026-06-16T23:59:59Z')
    assert res.status_code == 200
    trends = res.get_json()["breakdowns"]["daily_trends"]

    day1_entry = next((d for d in trends if d["date"] == "2026-06-15"), None)
    day2_entry = next((d for d in trends if d["date"] == "2026-06-16"), None)

    assert day1_entry is not None, "Day 1 (2026-06-15) must be grouped as 2026-06-15"
    assert day2_entry is not None, "Day 2 (2026-06-16) must be grouped as 2026-06-16"
    assert day1_entry["total_tokens"] == 120
    assert day2_entry["total_tokens"] == 240


def test_missing_token_and_null_cost_aggregation_semantics(client, admin_rbac_users):
    """
    Ticket 3F.1 Requirement 5 & 7:
    - Missing token metadata does not fabricate token totals.
    - NULL estimated costs are counted separately and never presented as confirmed $0.00.
    - Failed attempts remain included in attempt counts and in known usage totals when telemetry
      contains usage and a known estimated cost.
    """
    sa = admin_rbac_users["super_admin"]
    cust = admin_rbac_users["customer"]

    now = datetime(2026, 7, 10, 12, 0, 0)

    # 1. Successful attempt with known cost and tokens
    log_ok = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="SUCCESS",
        prompt_tokens=1000,
        completion_tokens=200,
        total_tokens=1200,
        estimated_cost_usd=Decimal("0.000800"),
        created_at=now
    )
    # 2. Failed attempt that has usage and known cost (e.g. rate limit after partial streaming)
    log_fail_with_cost = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="FAILED",
        prompt_tokens=500,
        completion_tokens=50,
        total_tokens=550,
        estimated_cost_usd=Decimal("0.000350"),
        error_category="RateLimitError",
        created_at=now + timedelta(minutes=10)
    )
    # 3. Failed attempt with NULL tokens and NULL cost (e.g. Connection refused before request)
    log_fail_null_metadata = AIProviderUsageLog(
        user_id=cust.user_id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-3.5-flash-lite",
        operation="SEARCH_PLANNING",
        status="FAILED",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost_usd=None,
        error_category="NetworkTimeout",
        created_at=now + timedelta(minutes=20)
    )

    db_session.add_all([log_ok, log_fail_with_cost, log_fail_null_metadata])
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = sa.user_id

    res = client.get('/api/admin/ai-usage/overview?start_date=2026-07-10T00:00:00Z&end_date=2026-07-10T23:59:59Z')
    assert res.status_code == 200
    s = res.get_json()["summary"]

    # Attempts
    assert s["total_attempts"] == 3
    assert s["successful_attempts"] == 1
    assert s["failed_attempts"] == 2

    # Token totals: 1000 + 500 = 1500 prompt, 200 + 50 = 250 comp, 1200 + 550 = 1750 total
    # (NULL tokens from 3rd log are NOT fabricated or counted as 0)
    assert s["tokens"]["prompt_tokens"] == 1500
    assert s["tokens"]["completion_tokens"] == 250
    assert s["tokens"]["total_tokens"] == 1750
    assert s["tokens"]["missing_metadata_count"] == 1

    # Cost: 0.000800 + 0.000350 = 0.001150
    # Failed attempt's known cost IS included in total known cost
    assert Decimal(s["costs"]["total_estimated_usd"]) == Decimal("0.001150")
    # NULL cost is counted in unknown_cost_count and NOT treated as 0.00
    assert s["costs"]["unknown_cost_count"] == 1

