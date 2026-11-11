import pytest
import uuid
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UserRole,
    UsersCompanyDetails,
    UsersICP,
    ResearchJobs,
    ResearchJobStatus,
    AIProviderUsageLog
)
from app.services.gtm_pipeline_service import (
    _call_gemini_with_fallback,
    calculate_gemini_cost,
    log_ai_provider_usage,
    generate_search_plan,
    qualify_candidates_with_gemini,
    GEMINI_MODELS_FALLBACK,
    GEMINI_VERIFIED_PRICING,
    GEMINI_HISTORICAL_PRICING
)


def _setup_test_user():
    unique_suffix = str(uuid.uuid4())[:8]
    user = UserTable(
        name="Telemetry User",
        email_id=f"telemetry_user_{unique_suffix}@test.com",
        phone_no=f"+1555{int(time.time()*1000)%10000000:07d}",
        password_hash="TestPassword123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    company = UsersCompanyDetails(
        user_id=user.user_id,
        company_name="Telemetry Corp",
        website_url="https://telemetrycorp.com",
        description="AI telemetry software",
        what_company_sells="Observability suite",
        industry="B2B SaaS"
    )
    icp = UsersICP(
        user_id=user.user_id,
        target_customer="Enterprise SaaS",
        target_jobs_roles="VP Engineering",
        industry="Software",
        version=1
    )
    db_session.add(company)
    db_session.add(icp)
    db_session.commit()
    return user


# ====================================================================
# TICKET 3E: AI PROVIDER USAGE & COST TRACKING TESTS
# ====================================================================

import time

def test_successful_gemini_call_records_usage_telemetry(clean_db):
    """
    1. Successful Gemini call records provider, model, operation, duration, and token counts.
    """
    user = _setup_test_user()
    uid = user.user_id

    # Create real research job to satisfy foreign key constraint
    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 5}
    )
    db_session.add(job)
    db_session.commit()

    mock_response = MagicMock()
    mock_response.text = '{"status": "ok"}'
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 1500
    mock_usage.candidates_token_count = 350
    mock_usage.total_token_count = 1850
    mock_usage.cached_content_token_count = None
    mock_response.usage_metadata = mock_usage

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        res = _call_gemini_with_fallback(
            prompt="Hello Gemini",
            response_json=True,
            user_id=uid,
            job_id=job.id,
            operation="UNIT_TEST_OP"
        )
        assert res == '{"status": "ok"}'

    log = db_session.query(AIProviderUsageLog).filter_by(user_id=uid).first()
    assert log is not None
    assert log.provider == "GEMINI"
    assert log.model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]
    assert log.operation == "UNIT_TEST_OP"
    assert log.job_id == job.id
    assert log.prompt_tokens == 1500
    assert log.completion_tokens == 350
    assert log.total_tokens == 1850
    assert log.status == "SUCCESS"
    assert log.duration_ms is not None
    assert log.duration_ms >= 0


def test_fallback_models_are_all_active_and_priced():
    """
    Verifies that shut-down models (gemini-1.5-flash, gemini-2.0-flash) are NOT in the active fallback list,
    and every configured production fallback model has a verified pricing entry.
    """
    # gemini-2.0-flash is shut down and must NOT be configured
    assert "gemini-2.0-flash" not in GEMINI_MODELS_FALLBACK

    # gemini-1.5-flash was shut down on Sept 29, 2025 and must NOT be in active fallback
    assert "gemini-1.5-flash" not in GEMINI_MODELS_FALLBACK
    assert "gemini-1.5-flash" in GEMINI_HISTORICAL_PRICING
    assert GEMINI_HISTORICAL_PRICING["gemini-1.5-flash"]["shutdown_date"] == "2025-09-29"

    # Exactly active documented models must be configured
    assert GEMINI_MODELS_FALLBACK == [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-2.5-flash"
    ]

    # Every active fallback model must have a verified pricing configuration
    for model_name in GEMINI_MODELS_FALLBACK:
        assert model_name in GEMINI_VERIFIED_PRICING, f"Model {model_name} missing verified pricing!"
        rates = GEMINI_VERIFIED_PRICING[model_name]
        assert "input" in rates and rates["input"] > Decimal("0")
        assert "output" in rates and rates["output"] > Decimal("0")
        assert "cached_input" in rates and rates["cached_input"] > Decimal("0")


def test_missing_usage_metadata_handled_gracefully(clean_db):
    """
    2. Usage fields missing from a response are handled gracefully (recorded as None, not crash or fabricated zero).
    """
    user = _setup_test_user()
    uid = user.user_id

    mock_response = MagicMock()
    mock_response.text = '{"status": "no_usage"}'
    mock_response.usage_metadata = None  # Missing usage metadata

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        res = _call_gemini_with_fallback(
            prompt="No usage metadata test",
            response_json=True,
            user_id=uid,
            job_id=None,
            operation="NO_USAGE_OP"
        )
        assert res == '{"status": "no_usage"}'

    log = db_session.query(AIProviderUsageLog).filter_by(user_id=uid, operation="NO_USAGE_OP").first()
    assert log is not None
    assert log.status == "SUCCESS"
    assert log.prompt_tokens is None
    assert log.completion_tokens is None
    assert log.total_tokens is None
    assert log.estimated_cost_usd is None


def test_verified_pricing_calculates_expected_cost():
    """
    3. Verified pricing calculates the expected provider cost with exact decimal arithmetic.
    Tests verified rates for gemini-3.5-flash-lite, gemini-3.8-flash, and gemini-2.5-flash.
    Confirms gemini-2.5-flash Standard paid rates are $0.30 input, $2.50 output, $0.03 cached input.
    """
    # gemini-3.5-flash-lite: $0.30 / 1M prompt, $2.50 / 1M completion
    # 10,000 prompt tokens = 10,000 * 0.30 / 1,000,000 = $0.003
    # 2,000 completion tokens = 2,000 * 2.50 / 1,000,000 = $0.005
    # Total = $0.008000
    cost_35 = calculate_gemini_cost(
        model_name="gemini-3.5-flash-lite",
        prompt_tokens=10000,
        completion_tokens=2000
    )
    assert cost_35 == Decimal("0.008000")

    # gemini-3.8-flash: $0.75 / 1M prompt, $3.75 / 1M completion (introductory through 2026-12-31)
    # 10,000 prompt tokens = 10,000 * 0.75 / 1,000,000 = $0.0075
    # 2,000 completion tokens = 2,000 * 3.75 / 1,000,000 = $0.0075
    # Total = $0.015000
    cost_38 = calculate_gemini_cost(
        model_name="gemini-3.8-flash",
        prompt_tokens=10000,
        completion_tokens=2000
    )
    assert cost_38 == Decimal("0.015000")

    # gemini-2.5-flash (Standard paid text/image/video): $0.30 / 1M prompt, $2.50 / 1M completion
    # 10,000 prompt tokens = 10,000 * 0.30 / 1,000,000 = $0.003000
    # 2,000 completion tokens = 2,000 * 2.50 / 1,000,000 = $0.005000
    # Total = $0.008000
    cost_25 = calculate_gemini_cost(
        model_name="gemini-2.5-flash",
        prompt_tokens=10000,
        completion_tokens=2000
    )
    assert cost_25 == Decimal("0.008000")

    # Verify that gemini-2.5-flash pricing is NOT assigned the gemini-2.5-flash-lite rates ($0.10/$0.40)
    assert cost_25 != Decimal("0.001800")


def test_unknown_and_shutdown_pricing_produces_unknown_cost_not_zero():
    """
    4. Unknown and shut-down models produce an unknown cost (None), never fabricated zero.
    """
    # gemini-1.5-flash was shut down on Sept 29, 2025; active pricing lookup must return None
    cost_15_active = calculate_gemini_cost(
        model_name="gemini-1.5-flash",
        prompt_tokens=5000,
        completion_tokens=1000
    )
    assert cost_15_active is None

    # When allow_historical=True, historical rates may be retrieved for audit purposes
    cost_15_hist = calculate_gemini_cost(
        model_name="gemini-1.5-flash",
        prompt_tokens=1000000,
        completion_tokens=1000000,
        allow_historical=True
    )
    assert cost_15_hist == Decimal("0.375000")

    # gemini-2.0-flash is shut down and not in active pricing
    cost_shutdown = calculate_gemini_cost(
        model_name="gemini-2.0-flash",
        prompt_tokens=5000,
        completion_tokens=1000
    )
    assert cost_shutdown is None

    # Custom or unknown models return None
    cost_unknown = calculate_gemini_cost(
        model_name="custom-unverified-llm",
        prompt_tokens=5000,
        completion_tokens=1000
    )
    assert cost_unknown is None


def test_negative_tokens_do_not_produce_negative_cost():
    """
    Confirm negative token inputs are bounded to 0 and cannot produce negative cost.
    """
    cost_neg = calculate_gemini_cost(
        model_name="gemini-2.5-flash",
        prompt_tokens=-500,
        completion_tokens=-200
    )
    assert cost_neg == Decimal("0.000000")


def test_cached_tokens_priced_at_cached_rate():
    """
    5. Cached token categories are priced at verified cached rates rather than full prompt rates,
    and are NOT double-charged.
    """
    # gemini-3.5-flash-lite: standard prompt $0.30/1M, cached prompt $0.03/1M, output $2.50/1M
    # Total prompt tokens = 10,000, of which 8,000 are cached:
    # Standard prompt: 2,000 * 0.30 / 1M = $0.000600
    # Cached prompt: 8,000 * 0.03 / 1M = $0.000240
    # Completion: 1,000 * 2.50 / 1M = $0.002500
    # Expected total = 0.000600 + 0.000240 + 0.002500 = $0.003340
    cost_35 = calculate_gemini_cost(
        model_name="gemini-3.5-flash-lite",
        prompt_tokens=10000,
        completion_tokens=1000,
        cached_tokens=8000
    )
    assert cost_35 == Decimal("0.003340")

    # gemini-3.8-flash: standard prompt $0.75/1M, cached prompt $0.075/1M, output $3.75/1M
    # Total prompt tokens = 10,000, of which 8,000 are cached:
    # Standard prompt: 2,000 * 0.75 / 1M = $0.001500
    # Cached prompt: 8,000 * 0.075 / 1M = $0.000600
    # Completion: 1,000 * 3.75 / 1M = $0.003750
    # Expected total = 0.001500 + 0.000600 + 0.003750 = $0.005850
    cost_38 = calculate_gemini_cost(
        model_name="gemini-3.8-flash",
        prompt_tokens=10000,
        completion_tokens=1000,
        cached_tokens=8000
    )
    assert cost_38 == Decimal("0.005850")


def test_failed_provider_call_with_usage_records_usage(clean_db):
    """
    6. Failed provider call that carries usage metadata records usage and error status.
    """
    user = _setup_test_user()
    uid = user.user_id

    mock_exc = RuntimeError("Quota exceeded mid-generation")
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 450
    mock_usage.candidates_token_count = 50
    mock_usage.total_token_count = 500
    mock_usage.cached_content_token_count = None
    mock_exc.usage_metadata = mock_usage

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = mock_exc

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        res = _call_gemini_with_fallback(
            prompt="Trigger failure",
            user_id=uid,
            operation="FAILED_CALL_OP"
        )
        assert res is None

    # Fallback iterates through models; check first failed log
    log = db_session.query(AIProviderUsageLog).filter_by(user_id=uid, operation="FAILED_CALL_OP").first()
    assert log is not None
    assert log.status == "FAILED"
    assert log.prompt_tokens == 450
    assert log.completion_tokens == 50
    assert "Quota exceeded" in (log.error_category or "")


def test_failed_provider_call_without_usage_does_not_fabricate_tokens(clean_db):
    """
    7. Failed provider call without usage metadata records status FAILED with None tokens (no fabrication).
    """
    user = _setup_test_user()
    uid = user.user_id

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ConnectionError("DNS resolution failed")

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        res = _call_gemini_with_fallback(
            prompt="Connection failure",
            user_id=uid,
            operation="CONN_FAIL_OP"
        )
        assert res is None

    log = db_session.query(AIProviderUsageLog).filter_by(user_id=uid, operation="CONN_FAIL_OP").first()
    assert log is not None
    assert log.status == "FAILED"
    assert log.prompt_tokens is None
    assert log.completion_tokens is None
    assert log.total_tokens is None
    assert log.estimated_cost_usd is None
    assert "DNS resolution failed" in (log.error_category or "")


def test_fallback_attempts_produce_distinct_usage_records_under_one_correlation_id(clean_db):
    """
    8. Retries/fallback attempts each produce an individual usage record tied by correlation_id.
    """
    user = _setup_test_user()
    uid = user.user_id

    # Model 1 fails with 429, Model 2 succeeds
    mock_resp = MagicMock()
    mock_resp.text = '{"success": true}'
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 600
    mock_usage.candidates_token_count = 100
    mock_usage.total_token_count = 700
    mock_usage.cached_content_token_count = None
    mock_resp.usage_metadata = mock_usage

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        RuntimeError("429 Resource Exhausted"),
        mock_resp
    ]

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        res = _call_gemini_with_fallback(
            prompt="Fallback test",
            user_id=uid,
            operation="FALLBACK_OP"
        )
        assert res == '{"success": true}'

    logs = db_session.query(AIProviderUsageLog).filter_by(user_id=uid, operation="FALLBACK_OP").order_by(AIProviderUsageLog.id.asc()).all()
    assert len(logs) == 2

    # Both share the same correlation_id
    assert logs[0].correlation_id == logs[1].correlation_id

    # Attempt 1 failed
    assert logs[0].status == "FAILED"
    assert "429" in (logs[0].error_category or "")

    # Attempt 2 succeeded
    assert logs[1].status == "SUCCESS"
    assert logs[1].prompt_tokens == 600
    assert logs[1].completion_tokens == 100


def test_usage_persistence_failure_does_not_break_caller(clean_db):
    """
    9. A database logging failure is non-fatal: does not raise to caller and does not abort AI response.
    """
    user = _setup_test_user()
    uid = user.user_id

    mock_resp = MagicMock()
    mock_resp.text = '{"pipeline": "continues"}'
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50, total_token_count=150, cached_content_token_count=None)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client), \
         patch("app.services.gtm_pipeline_service.log_ai_provider_usage", side_effect=Exception("Database connection dropped")):
        # Must not raise exception!
        res = _call_gemini_with_fallback(
            prompt="Telemetry failure test",
            user_id=uid,
            operation="SAFE_CALL_OP"
        )
        # Pipeline still gets its valid AI response!
        assert res == '{"pipeline": "continues"}'


def test_user_and_job_attribution(clean_db):
    """
    10. Correct user_id and job_id attribution is recorded in usage logs.
    """
    user1 = _setup_test_user()
    user2 = _setup_test_user()

    job1 = ResearchJobs(user_id=user1.user_id, status=ResearchJobStatus.RUNNING.value, budget={"target_leads": 5})
    job2 = ResearchJobs(user_id=user2.user_id, status=ResearchJobStatus.RUNNING.value, budget={"target_leads": 5})
    db_session.add(job1)
    db_session.add(job2)
    db_session.commit()

    log_entry1 = log_ai_provider_usage(
        user_id=user1.user_id,
        job_id=job1.id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-2.0-flash",
        operation="SEARCH_PLANNING",
        prompt_tokens=100,
        completion_tokens=50,
        session=db_session
    )

    log_entry2 = log_ai_provider_usage(
        user_id=user2.user_id,
        job_id=job2.id,
        correlation_id=str(uuid.uuid4()),
        provider="GEMINI",
        model_name="gemini-2.0-flash",
        operation="SEARCH_PLANNING",
        prompt_tokens=200,
        completion_tokens=80,
        session=db_session
    )

    log1_id = log_entry1.id
    log2_id = log_entry2.id

    reloaded1 = db_session.query(AIProviderUsageLog).filter_by(id=log1_id).first()
    reloaded2 = db_session.query(AIProviderUsageLog).filter_by(id=log2_id).first()

    assert reloaded1.user_id == user1.user_id
    assert reloaded1.job_id == job1.id

    assert reloaded2.user_id == user2.user_id
    assert reloaded2.job_id == job2.id


def test_no_prompts_completions_or_api_keys_persisted(clean_db):
    """
    11. Verify that no prompt text, completions, or API keys are stored in the usage log table.
    """
    user = _setup_test_user()
    uid = user.user_id

    mock_resp = MagicMock()
    mock_resp.text = '{"super_secret_payload": "TOP_SECRET_VALUE_12345"}'
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50, total_token_count=150, cached_content_token_count=None)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    prompt_with_secrets = "PROMPT_WITH_SECRET_API_KEY_AIzaSyFakeKey123"

    with patch("app.services.gtm_pipeline_service._get_gemini_client", return_value=mock_client):
        _call_gemini_with_fallback(
            prompt=prompt_with_secrets,
            user_id=uid,
            operation="AUDIT_PRIVACY_OP"
        )

    log = db_session.query(AIProviderUsageLog).filter_by(user_id=uid, operation="AUDIT_PRIVACY_OP").first()
    assert log is not None

    # Inspect all attributes of the row
    for col in AIProviderUsageLog.__table__.columns:
        val = getattr(log, col.name)
        if isinstance(val, str):
            assert "TOP_SECRET" not in val
            assert "AIzaSy" not in val
            assert "PROMPT_WITH_SECRET" not in val


def test_instrumentation_does_not_affect_customer_credits(flask_app, clean_db):
    """
    12. Instrumentation does not alter customer credits, reservations, or ledger transactions.
    """
    from app.services.credit_service import CreditService
    user = _setup_test_user()
    uid = user.user_id

    CreditService.grant_credits(
        user_id=uid,
        amount=Decimal("100.00"),
        idempotency_key=f"init_cust_{uid}",
        reason="Testing",
        session=db_session
    )

    wallet_before = CreditService.get_wallet_balance(uid, session=db_session)

    # Perform multiple logged operations
    for i in range(5):
        log_ai_provider_usage(
            user_id=uid,
            job_id=None,
            correlation_id=str(uuid.uuid4()),
            provider="GEMINI",
            model_name="gemini-3.5-flash-lite",
            operation="BILLING_ISOLATION_TEST",
            prompt_tokens=5000,
            completion_tokens=2000,
            estimated_cost_usd=Decimal("0.006500")
        )

    wallet_after = CreditService.get_wallet_balance(uid, session=db_session)
    # Balances must be 100% untouched by provider cost logging!
    assert wallet_after["total_balance"] == wallet_before["total_balance"]
    assert wallet_after["available_balance"] == wallet_before["available_balance"]
    assert wallet_after["reserved_balance"] == wallet_before["reserved_balance"]
