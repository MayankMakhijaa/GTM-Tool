import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
from requests.exceptions import Timeout

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UsersCompanyDetails,
    UsersICP,
    UsersLinkedinDetails,
    GlobalProfiles,
    UsersProfiles,
    ResearchJobs,
    ResearchJobStatus
)
from app.services.gtm_pipeline_service import (
    get_user_gtm_context,
    generate_search_plan,
    discover_candidates_via_voyager,
    discover_candidates_via_public_web,
    enrich_company_public_web,
    read_public_url_agent_reach,
    merge_and_deduplicate_candidates,
    normalize_linkedin_identifier,
    qualify_candidates_with_gemini,
    persist_qualified_opportunities,
    get_user_opportunities,
    _execute_gtm_pipeline_worker,
    CandidateList
)


def _create_mock_user(verified=True):
    user = UserTable(
        name="Test Founder",
        email_id="founder@testscale.io",
        phone_no="+15550001234",
        password_hash="hashed_pw_123",
        email_verified_at=datetime.utcnow() if verified else None,
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


def _setup_user_onboarding(user_id):
    company = UsersCompanyDetails(
        user_id=user_id,
        company_name="ScaleFlow AI",
        website_url="https://scaleflow.io",
        description="Autonomous sales prospecting and lead routing platform.",
        what_company_sells="AI sales agents that qualify inbound and outbound B2B leads.",
        products_services="ScaleFlow Agent Suite",
        industry="B2B SaaS / DevTools",
        company_size="11-50 employees"
    )
    icp = UsersICP(
        user_id=user_id,
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


# ====================================================================
# 1. UNIT & SERVICE TESTS
# ====================================================================

def test_get_user_gtm_context_incomplete(clean_db):
    user = _create_mock_user()
    ctx = get_user_gtm_context(user.user_id)
    assert ctx["onboarding_completed"] is False
    assert ctx["session_valid"] is False


def test_get_user_gtm_context_complete(clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)

    ctx = get_user_gtm_context(user.user_id)
    assert ctx["onboarding_completed"] is True
    assert ctx["company_name"] == "ScaleFlow AI"
    assert "VP of Sales" in ctx["target_icp"]
    assert "AI sales agents" in ctx["offer"]


@patch("app.services.gtm_pipeline_service._call_gemini_with_fallback")
def test_generate_search_plan_with_gemini(mock_gemini, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)
    context = get_user_gtm_context(user.user_id)

    mock_gemini.return_value = json.dumps({
        "search_keywords": "B2B SaaS RevOps",
        "keyword_title": "VP of Sales, Head of RevOps",
        "target_industries": ["Enterprise Software"],
        "target_company_types": ["Cloud Software"]
    })

    plan = generate_search_plan(context)
    assert plan["search_keywords"] == "B2B SaaS RevOps"
    assert "VP of Sales" in plan["keyword_title"]


@patch("app.services.gtm_pipeline_service.create_voyager_client_from_db")
def test_discover_candidates_via_voyager(mock_create_client, clean_db):
    user = _create_mock_user()
    mock_client = MagicMock()
    mock_client.search_people.return_value = [
        {
            "urn_id": "ACoAAB12345",
            "name": "Alex Mercer",
            "jobtitle": "VP of Revenue Operations at CloudScale Inc",
            "location": "Austin, Texas",
            "distance": "DISTANCE_2"
        },
        {
            "urn_id": "ACoAAB67890",
            "name": "Sarah Connor",
            "jobtitle": "Chief Revenue Officer @ Cyberdyne AI",
            "location": "San Francisco, CA",
            "distance": "DISTANCE_1"
        }
    ]
    mock_create_client.return_value = mock_client

    plan = {"search_keywords": "RevOps", "keyword_title": "VP Sales"}
    candidates = discover_candidates_via_voyager(user.user_id, plan, limit=5)

    assert len(candidates) == 2
    assert candidates[0]["name"] == "Alex Mercer"
    assert candidates[0]["role"] == "VP of Revenue Operations"
    assert candidates[0]["company"] == "CloudScale Inc"
    assert candidates[1]["company"] == "Cyberdyne AI"


@patch("requests.get")
def test_enrich_company_public_web_jina_reader(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "# CloudScale Inc\nNext generation cloud infrastructure management and automated cost optimization."
    mock_get.return_value = mock_response

    res = enrich_company_public_web("CloudScale Inc", "https://cloudscale.io")
    assert res["status"] == "OK"
    assert res["source"] == "JINA_READER"
    assert "automated cost optimization" in res["summary"]

    # Verify no cookies or auth headers leaked to Jina
    headers_used = mock_get.call_args[1].get("headers", {})
    assert "Cookie" not in headers_used
    assert "Authorization" not in headers_used


@patch("app.services.gtm_pipeline_service._call_gemini_with_fallback")
def test_qualify_candidates_with_gemini(mock_gemini, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)
    context = get_user_gtm_context(user.user_id)

    candidates = [
        {
            "urn_id": "ACoAAB12345",
            "name": "Alex Mercer",
            "role": "VP Revenue Ops",
            "company": "CloudScale Inc",
            "location": "Austin, TX",
            "profile_url": "https://linkedin.com/in/alex-mercer"
        }
    ]
    enrichment = {"CloudScale Inc": {"summary": "Cloud software company with 200 employees."}}

    mock_gemini.return_value = json.dumps([
        {
            "urn_id": "ACoAAB12345",
            "fit_score": 93,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "High title match for RevOps and target company size.",
            "intent_signals": "Active SDR recruitment and tool consolidation.",
            "recommended_angle": "Discuss automating lead qualification to shorten SDR cycles."
        }
    ])

    qualified = qualify_candidates_with_gemini(candidates, context, enrichment)
    assert len(qualified) == 1
    assert qualified[0]["fit_score"] == 93
    assert qualified[0]["tier"] == "Tier 1 Priority Match"
    assert "RevOps" in qualified[0]["qualification_reason"]
    assert qualified[0]["public_contact"]["verified"] is True


def test_persistence_deduplication_and_isolation(clean_db):
    user_a = _create_mock_user()
    _setup_user_onboarding(user_a.user_id)

    user_b = UserTable(
        name="User B", email_id="user_b@test.com", phone_no="+15550005555",
        password_hash="pw", email_verified_at=datetime.utcnow(), is_active=True
    )
    db_session.add(user_b)
    db_session.commit()

    candidates = [
        {
            "urn_id": "ACoAAB12345",
            "name": "Alex Mercer",
            "role": "VP Revenue Ops",
            "raw_headline": "VP Revenue Ops at CloudScale",
            "company": "CloudScale Inc",
            "location": "Austin, TX",
            "profile_url": "https://linkedin.com/in/alex-mercer",
            "fit_score": 93,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Matches target role and ARR band.",
            "intent_signals": "Hiring 3 SDRs",
            "recommended_angle": "Automate SDR routing",
            "public_contact": {"linkedin": "https://linkedin.com/in/alex-mercer", "verified": True}
        }
    ]

    # Save for User A
    count_a = persist_qualified_opportunities(user_a.user_id, job_id=1, qualified_candidates=candidates)
    assert count_a == 1

    # Verify GlobalProfiles has 1 entry
    gp_rows = db_session.query(GlobalProfiles).filter_by(linkedin_id="ACoAAB12345").all()
    assert len(gp_rows) == 1

    # Save for User B with same URN (deduplication check)
    count_b = persist_qualified_opportunities(user_b.user_id, job_id=2, qualified_candidates=candidates)
    assert count_b == 1

    # Still only 1 entry in GlobalProfiles
    gp_rows_after = db_session.query(GlobalProfiles).filter_by(linkedin_id="ACoAAB12345").all()
    assert len(gp_rows_after) == 1
    assert gp_rows_after[0].recommended_no_of_times == 2

    # But each user has their own isolated row in UsersProfiles
    opps_a = get_user_opportunities(user_a.user_id)
    opps_b = get_user_opportunities(user_b.user_id)
    assert len(opps_a) == 1
    assert len(opps_b) == 1
    assert opps_a[0]["name"] == "Alex Mercer"
    assert opps_a[0]["score"] == 93


# ====================================================================
# 2. END-TO-END HTTP API TESTS
# ====================================================================

def test_api_gtm_context_unauthenticated(client):
    res = client.get('/api/gtm-context')
    assert res.status_code == 401


def test_api_gtm_context_authenticated(client, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)

    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    res = client.get('/api/gtm-context')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["company_name"] == "ScaleFlow AI"
    assert "VP of Sales" in data["data"]["target_icp"]


@patch("app.services.gtm_pipeline_service._execute_gtm_pipeline_worker")
def test_api_find_gtm_opportunities_starts_async_job(mock_worker, client, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)

    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    res = client.post('/api/gtm-opportunities/find', json={
        "target_leads": 15,
        "persona_filter": "VP of Sales"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "job_id" in data
    assert data["status"] == "QUEUED"

    # Check job created in database
    job = db_session.query(ResearchJobs).filter_by(id=data["job_id"]).first()
    assert job is not None
    assert job.user_id == user.user_id


def test_api_get_gtm_job_status(client, clean_db):
    user = _create_mock_user()
    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    job = ResearchJobs(
        user_id=user.user_id,
        status=ResearchJobStatus.RUNNING.value,
        progress={"step": "DISCOVERY", "pct": 45, "message": "Searching LinkedIn profiles"},
        results_count=10
    )
    db_session.add(job)
    db_session.commit()

    res = client.get(f'/api/gtm/jobs/{job.id}/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["status"] == "RUNNING"
    assert data["progress"]["pct"] == 45
    assert data["results_count"] == 10


def test_api_get_gtm_opportunities(client, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)

    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    candidates = [
        {
            "urn_id": "ACoAAB_LEAD_1",
            "name": "Jane Lead",
            "role": "VP Commercial Strategy",
            "raw_headline": "VP Commercial Strategy @ Acme Corp",
            "company": "Acme Corp",
            "location": "Boston, MA",
            "profile_url": "https://linkedin.com/in/jane-lead",
            "fit_score": 91,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "High priority ICP match.",
            "intent_signals": "Evaluating sales intelligence tools",
            "recommended_angle": "Demonstrate ROI on lead qualification",
            "public_contact": {"linkedin": "https://linkedin.com/in/jane-lead", "verified": True}
        }
    ]
    persist_qualified_opportunities(user.user_id, job_id=None, qualified_candidates=candidates)

    res = client.get('/api/gtm-opportunities')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] == 1
    assert data["opportunities"][0]["name"] == "Jane Lead"
    assert data["opportunities"][0]["score"] == 91
    assert data["opportunities"][0]["tier"] == "Tier 1 Priority Match"
    assert "Acme Corp" in data["opportunities"][0]["company"]


@patch("app.services.gtm_pipeline_service.create_voyager_client_from_db")
@patch("app.services.gtm_pipeline_service._call_gemini_with_fallback")
@patch("requests.get")
def test_full_gtm_async_worker_run_end_to_end(mock_jina, mock_gemini, mock_voyager, client, clean_db):
    """
    Validates end-to-end execution of the asynchronous GTM pipeline worker:
    Query Planning -> Voyager LinkedIn Discovery -> Jina Web Enrichment ->
    Gemini Qualification -> PostgreSQL GlobalProfiles & UsersProfiles Persistence.
    """
    user = _create_mock_user()
    target_uid = user.user_id
    _setup_user_onboarding(target_uid)

    # 1. Mock Voyager
    mock_client = MagicMock()
    mock_client.search_people.return_value = [
        {
            "urn_id": "ACoAAB_E2E_LEAD",
            "name": "Marcus Vance",
            "jobtitle": "VP Revenue Operations at Nordix Cloud Systems",
            "location": "Seattle, WA",
            "distance": "DISTANCE_2"
        }
    ]
    mock_voyager.return_value = mock_client

    # 2. Mock Gemini Planning & Qualification
    def gemini_side_effect(prompt, response_json=True):
        if "Translate the following user company offering" in prompt:
            return json.dumps({
                "search_keywords": "B2B SaaS RevOps",
                "keyword_title": "VP Revenue Operations",
                "target_industries": ["Enterprise Cloud"],
                "target_company_types": ["B2B SaaS"]
            })
        elif "Evaluate the following prospects" in prompt:
            return json.dumps([
                {
                    "urn_id": "ACoAAB_E2E_LEAD",
                    "fit_score": 96,
                    "tier": "Tier 1 Priority Match",
                    "qualification_reason": "Matches company size and target RevOps role.",
                    "intent_signals": "Active postings for 4 SDRs.",
                    "recommended_angle": "Automate inbound lead triage with AI workflows."
                }
            ])
        return "{}"
    mock_gemini.side_effect = gemini_side_effect

    # 3. Mock Jina Reader Web Enrichment
    mock_jina_resp = MagicMock()
    mock_jina_resp.status_code = 200
    mock_jina_resp.text = "# Nordix Cloud Systems\nEnterprise cloud infrastructure and CRM routing automation."
    mock_jina.return_value = mock_jina_resp

    with client.session_transaction() as sess:
        sess["user_id"] = target_uid

    # Trigger job
    res = client.post('/api/gtm-opportunities/find', json={"target_leads": 10})
    assert res.status_code == 200
    job_id = res.get_json()["job_id"]

    # Execute worker synchronously for deterministic assertion
    from app.services.gtm_pipeline_service import _execute_gtm_pipeline_worker
    from flask import current_app
    _execute_gtm_pipeline_worker(current_app._get_current_object(), target_uid, job_id, 10, None)

    # Verify job status transitioned to COMPLETED
    job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert job.status == ResearchJobStatus.COMPLETED.value
    assert job.results_count == 1
    assert job.completed_at is not None

    # Verify persisted lead in database
    opps = get_user_opportunities(target_uid)
    assert len(opps) == 1
    assert opps[0]["name"] == "Marcus Vance"
    assert opps[0]["company"] == "Nordix Cloud Systems"
    assert opps[0]["score"] == 96
    assert opps[0]["tier"] == "Tier 1 Priority Match"
    assert "Nordix Cloud Systems" in opps[0]["need"] or "inbound lead triage" in opps[0]["need"]

    # Verify API retrieval endpoint
    res_get = client.get('/api/gtm-opportunities')
    assert res_get.status_code == 200
    data = res_get.get_json()
    assert data["count"] == 1
    assert data["opportunities"][0]["name"] == "Marcus Vance"


@patch("app.services.gtm_pipeline_service.validate_user_session")
def test_session_expired_reconnect_status(mock_val_session, client, clean_db):
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)

    # Attach encrypted linkedin record
    link = UsersLinkedinDetails(
        user_id=user.user_id,
        auth_data_encrypted="mock_encrypted_data",
        connection_status="EXPIRED"
    )
    db_session.add(link)
    db_session.commit()

    mock_val_session.return_value = {
        "valid": False,
        "category": "expired",
        "message": "LinkedIn session has expired or was revoked."
    }

    with client.session_transaction() as sess:
        sess["user_id"] = user.user_id

    res = client.get('/api/gtm-context')
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["session_valid"] is False
    assert data["session_category"] == "expired"
    assert "expired" in data["session_message"].lower()


def test_gtm_worker_session_cleanup_on_success_and_failure(flask_app, clean_db):
    """Verify that background worker cleans up scoped db_session in finally block on success and failure."""
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    # 1. Success case
    job_success = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job_success)
    db_session.commit()
    job_id_success = job_success.id

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=[]), \
         patch("app.services.gtm_pipeline_service.generate_search_plan", return_value={"keywords": ["SaaS"]}), \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=[]), \
         patch.object(db_session, "remove", wraps=db_session.remove) as spy_cleanup:

        _execute_gtm_pipeline_worker(flask_app, uid, job_id_success, target_leads=5, persona_filter=None)
        assert spy_cleanup.call_count >= 1

    # Reload from DB and verify completed status
    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id_success).first()
    assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
    assert reloaded_job.completed_at is not None

    # 2. Failure case
    job_failure = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job_failure)
    db_session.commit()
    job_id_failure = job_failure.id

    with patch("app.services.gtm_pipeline_service.generate_search_plan", side_effect=RuntimeError("Search plan generation timed out")), \
         patch.object(db_session, "remove", wraps=db_session.remove) as spy_cleanup_fail:

        _execute_gtm_pipeline_worker(flask_app, uid, job_id_failure, target_leads=5, persona_filter=None)
        assert spy_cleanup_fail.call_count >= 1

    reloaded_fail_job = db_session.query(ResearchJobs).filter_by(id=job_id_failure).first()
    assert reloaded_fail_job.status == ResearchJobStatus.FAILED.value
    assert "timed out" in reloaded_fail_job.error_message


def test_gtm_context_active_job_resumption_and_ownership(client, clean_db):
    """Verify active research job is exposed via /api/gtm-context with ownership isolation and status filtering."""
    user_a = _create_mock_user()
    _setup_user_onboarding(user_a.user_id)

    user_b = UserTable(
        name="User B",
        email_id="user_b@company.com",
        phone_no="+15550005678",
        password_hash="hashed_pw_b",
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add(user_b)
    db_session.commit()
    _setup_user_onboarding(user_b.user_id)

    # 1. Initially no active job
    ctx_a = get_user_gtm_context(user_a.user_id)
    assert ctx_a["active_job"] is None

    # 2. Create active RUNNING job for User A
    job_a = ResearchJobs(
        user_id=user_a.user_id,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 20},
        progress={"step": "DISCOVERY", "pct": 40, "message": "Discovering prospects"},
        created_at=datetime.utcnow()
    )
    db_session.add(job_a)
    db_session.commit()

    # User A context has active_job
    ctx_a_active = get_user_gtm_context(user_a.user_id)
    assert ctx_a_active["active_job"] is not None
    assert ctx_a_active["active_job"]["id"] == job_a.id
    assert ctx_a_active["active_job"]["status"] == "RUNNING"
    assert ctx_a_active["active_job"]["progress"]["pct"] == 40

    # User B context MUST NOT see User A's active job (ownership isolation)
    ctx_b = get_user_gtm_context(user_b.user_id)
    assert ctx_b["active_job"] is None

    # Verify API endpoint exposes active_job to authenticated User A
    with client.session_transaction() as sess:
        sess["user_id"] = user_a.user_id

    res_api_a = client.get('/api/gtm-context')
    assert res_api_a.status_code == 200
    data_a = res_api_a.get_json()["data"]
    assert data_a["active_job"] is not None
    assert data_a["active_job"]["id"] == job_a.id

    # Verify API endpoint does not expose active_job to authenticated User B
    with client.session_transaction() as sess:
        sess["user_id"] = user_b.user_id

    res_api_b = client.get('/api/gtm-context')
    assert res_api_b.status_code == 200
    data_b = res_api_b.get_json()["data"]
    assert data_b["active_job"] is None

    # 3. Once job is completed, active_job is None
    job_a.status = ResearchJobStatus.COMPLETED.value
    job_a.completed_at = datetime.utcnow()
    db_session.commit()

    ctx_a_completed = get_user_gtm_context(user_a.user_id)
    assert ctx_a_completed["active_job"] is None


def test_multi_query_generation_and_validation(clean_db):
    """Verifies that search plan generates structured, bounded, deduplicated queries with deterministic fallbacks."""
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)
    ctx = get_user_gtm_context(user.user_id)

    # 1. Fallback generation when Gemini is unavailable
    with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=None):
        plan = generate_search_plan(ctx)
        assert "queries" in plan
        assert len(plan["queries"]) >= 1
        assert len(plan["queries"]) <= 4
        # Each query must have structured fields
        for q in plan["queries"]:
            assert "id" in q
            assert "title" in q
            assert "keywords" in q

    # 2. Structured output parsing and query limit enforcement
    mock_gemini_json = json.dumps({
        "search_keywords": "B2B SaaS RevOps",
        "keyword_title": "VP of Sales, CRO",
        "target_industries": ["Cloud Software"],
        "target_company_types": ["B2B SaaS"],
        "queries": [
            {"id": "q1", "title": "VP of Sales", "keywords": "B2B SaaS"},
            {"id": "q2", "title": "Chief Revenue Officer", "keywords": "Enterprise Software"},
            {"id": "q3", "title": "Head of RevOps", "keywords": "Pipeline Automation"},
            {"id": "q4", "title": "VP Growth", "keywords": "SaaS Scaling"},
            {"id": "q5", "title": "Excess Query", "keywords": "Should be capped"}
        ]
    })
    with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=mock_gemini_json):
        plan = generate_search_plan(ctx)
        assert len(plan["queries"]) == 4  # Capped at max 4 queries
        assert plan["queries"][0]["id"] == "q1"


def test_voyager_error_taxonomy_and_outcomes(clean_db):
    """Verifies typed error categorization (rate limited, auth expired, network error, zero results)."""
    user = _create_mock_user()
    plan = {"search_keywords": "SaaS", "keyword_title": "VP Sales"}

    # 1. Rate limiting (429)
    mock_client_429 = MagicMock()
    mock_client_429.search_people.side_effect = RuntimeError("HTTP 429 Too Many Requests: Rate limit exceeded")
    with patch("app.services.gtm_pipeline_service.create_voyager_client_from_db", return_value=mock_client_429):
        res = discover_candidates_via_voyager(user.user_id, plan)
        assert res.status == "RATE_LIMITED"
        assert res.error_category == "rate_limited"

    # 2. Auth expired (401)
    mock_client_401 = MagicMock()
    mock_client_401.search_people.side_effect = RuntimeError("HTTP 401 Unauthorized: Session revoked")
    with patch("app.services.gtm_pipeline_service.create_voyager_client_from_db", return_value=mock_client_401):
        res = discover_candidates_via_voyager(user.user_id, plan)
        assert res.status == "AUTH_EXPIRED"
        assert res.error_category == "expired"

    # 3. Network timeout
    mock_client_net = MagicMock()
    mock_client_net.search_people.side_effect = ConnectionError("HTTPSConnectionPool: Connection timed out")
    with patch("app.services.gtm_pipeline_service.create_voyager_client_from_db", return_value=mock_client_net):
        res = discover_candidates_via_voyager(user.user_id, plan)
        assert res.status == "NETWORK_ERROR"
        assert res.error_category == "network_error"

    # 4. Zero results (genuine search returning empty)
    mock_client_empty = MagicMock()
    mock_client_empty.search_people.return_value = []
    with patch("app.services.gtm_pipeline_service.create_voyager_client_from_db", return_value=mock_client_empty):
        res = discover_candidates_via_voyager(user.user_id, plan)
        assert res.status == "ZERO_RESULTS"
        assert len(res) == 0


def test_agent_reach_jina_adapter_handling():
    """Verifies Agent-Reach Jina Reader adapter handles success, bot challenges, and timeouts safely."""
    # 1. Successful markdown retrieval
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "# Acme Corp Overview\nLeading enterprise workflow software."
    with patch("requests.get", return_value=mock_resp):
        res = read_public_url_agent_reach("https://acme.com")
        assert res["status"] == "OK"
        assert "workflow software" in res["summary"]

    # 2. Bot challenge detection
    mock_bot = MagicMock()
    mock_bot.status_code = 200
    mock_bot.text = "<html><body><form id='challenge-form'></form></body></html>"
    with patch("requests.get", return_value=mock_bot):
        res_bot = read_public_url_agent_reach("https://protected.com")
        assert res_bot["status"] == "BOT_CHALLENGE"

    # 3. Timeout / error handling
    with patch("requests.get", side_effect=Timeout("Request timed out")):
        res_err = read_public_url_agent_reach("https://timeout.com")
        assert res_err["status"] == "ERROR"


def test_public_web_discovery_independent_of_voyager(clean_db):
    """Verifies public search engine discovery extracts valid LinkedIn profile candidates."""
    user = _create_mock_user()
    _setup_user_onboarding(user.user_id)
    ctx = get_user_gtm_context(user.user_id)
    plan = {"queries": [{"id": "q1", "title": "VP of Sales", "keywords": "B2B SaaS"}]}

    mock_search_results = [
        {
            "title": "Elena Rostova - VP of Sales - DataSphere | LinkedIn",
            "snippet": "Experienced VP of Sales at DataSphere driving enterprise expansion.",
            "url": "https://www.linkedin.com/in/elena-rostova-sales"
        },
        {
            "title": "Random Blog Post",
            "snippet": "Irrelevant article without LinkedIn profile.",
            "url": "https://randomblog.com/article"
        }
    ]

    with patch("app.services.gtm_pipeline_service.is_google_search_configured", return_value=True), \
         patch("app.services.gtm_pipeline_service.perform_public_web_search", return_value=mock_search_results):
        candidates = discover_candidates_via_public_web(ctx, plan, limit=5)
        assert len(candidates) == 1
        assert candidates[0]["name"] == "Elena Rostova"
        assert candidates[0]["role"] == "VP of Sales"
        assert candidates[0]["company"] == "DataSphere"
        assert candidates[0]["urn_id"] == "elena-rostova-sales"
        assert candidates[0]["provider"] == "PUBLIC_WEB"


def test_deduplication_across_queries_and_providers():
    """Verifies that duplicate profiles across Voyager and Public Web merge cleanly with DUAL provenance."""
    voyager_candidates = [
        {
            "urn_id": "marcus-vance",
            "name": "Marcus Vance",
            "role": "VP RevOps",
            "company": "Nordix Systems",
            "location": "Seattle, WA",
            "profile_url": "https://www.linkedin.com/in/marcus-vance?trk=pub_search",
            "provider": "VOYAGER",
            "source_query": "q1"
        }
    ]

    public_web_candidates = [
        {
            "urn_id": "marcus-vance",
            "name": "Marcus Vance",
            "role": "VP of Revenue Operations",
            "company": "Nordix Systems",
            "location": "Seattle, Washington",
            "profile_url": "https://www.linkedin.com/in/marcus-vance/",
            "provider": "PUBLIC_WEB",
            "source_query": "q2"
        },
        {
            "urn_id": "sarah-connor",
            "name": "Sarah Connor",
            "role": "CRO",
            "company": "Cyberdyne",
            "location": "San Francisco, CA",
            "profile_url": "https://www.linkedin.com/in/sarah-connor",
            "provider": "PUBLIC_WEB",
            "source_query": "q2"
        }
    ]

    merged = merge_and_deduplicate_candidates([voyager_candidates, public_web_candidates])
    assert len(merged) == 2  # marcus-vance deduplicated, sarah-connor preserved
    marcus = next(c for c in merged if c["urn_id"] == "marcus-vance")
    assert marcus["provider"] == "DUAL"
    assert "VOYAGER" in marcus["sources"]
    assert "PUBLIC_WEB" in marcus["sources"]
    assert "q1" in marcus["queries"]
    assert "q2" in marcus["queries"]


def test_deterministic_exclusions_in_qualification():
    """Verifies negative keywords/roles (intern, student, freelancer) are deterministically disqualified."""
    user_context = {
        "offer": "AI sales prospecting suite",
        "target_icp": "VP of Sales, CRO",
        "icp_raw": {"exclusions": "agency, contractor"}
    }

    candidates = [
        {
            "urn_id": "lead-exec",
            "name": "David Wallace",
            "role": "Chief Financial Officer",
            "raw_headline": "CFO at Dunder Mifflin",
            "company": "Dunder Mifflin",
            "location": "New York, NY",
            "profile_url": "https://linkedin.com/in/david-wallace"
        },
        {
            "urn_id": "lead-intern",
            "name": "Ryan Howard",
            "role": "Sales Intern",
            "raw_headline": "Business Development Intern",
            "company": "Dunder Mifflin",
            "location": "Scranton, PA",
            "profile_url": "https://linkedin.com/in/ryan-howard"
        }
    ]

    mock_gemini_qual = json.dumps([
        {
            "urn_id": "lead-exec",
            "fit_score": 88,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Executive leadership with P&L authority.",
            "intent_signals": "Evaluating sales tech.",
            "recommended_angle": "Discuss ROI improvements."
        }
    ])

    with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=mock_gemini_qual):
        results = qualify_candidates_with_gemini(candidates, user_context, {})

    ryan = next(c for c in results if c["urn_id"] == "lead-intern")
    assert ryan["is_excluded"] is True
    assert ryan["fit_score"] == 15
    assert "intern" in ryan["qualification_reason"].lower()

    david = next(c for c in results if c["urn_id"] == "lead-exec")
    assert david["is_excluded"] is False
    assert david["fit_score"] == 88


def test_invalid_gemini_output_graceful_fallback():
    """Verifies fallback scoring and explainable reasons when Gemini output is unparseable or fails."""
    user_context = {"offer": "Platform", "target_icp": "VP Sales", "icp_raw": {}}
    candidates = [
        {
            "urn_id": "candidate-1",
            "name": "Alex Mercer",
            "role": "VP Sales",
            "company": "CloudScale",
            "location": "Austin",
            "profile_url": "https://linkedin.com/in/alex-mercer"
        }
    ]

    # Malformed non-JSON Gemini response
    with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value="Here is the evaluation: not json"):
        results = qualify_candidates_with_gemini(candidates, user_context, {})
        assert len(results) == 1
        assert results[0]["fit_score"] >= 70
        assert "Matches role" in results[0]["qualification_reason"]


def test_voyager_terminal_auth_failure_halts_discovery_cleanly(flask_app, clean_db):
    """Verifies that when Voyager discovery encounters terminal auth failure, GTM worker fails cleanly without invoking public web."""
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    # Voyager returns AUTH_EXPIRED
    mock_voyager_fail = CandidateList([], status="AUTH_EXPIRED", error_category="expired", provider="VOYAGER")

    with patch("app.services.gtm_pipeline_service.generate_search_plan", return_value={"queries": [{"id": "q1", "title": "Head of RevOps", "keywords": "SaaS"}]}), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_voyager_fail), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_public_web") as mock_public_web:

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    assert mock_public_web.call_count == 0

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert "reconnect" in reloaded_job.error_message.lower()
    assert reloaded_job.results_count == 0


def test_linkedin_id_constraint_and_null_skipping(clean_db):
    """Verifies that candidates missing an extractable LinkedIn identifier are skipped, satisfying the non-null constraint."""
    user = _create_mock_user()

    candidates_with_missing_id = [
        {
            "name": "Anonymous Person",
            "role": "Consultant",
            "profile_url": "https://someotherwebsite.com/user/123",  # No linkedin slug
            "urn_id": None
        },
        {
            "name": "Valid Candidate",
            "role": "VP Sales",
            "profile_url": "https://www.linkedin.com/in/valid-vp-sales",
            "urn_id": "valid-vp-sales",
            "fit_score": 85,
            "qualification_reason": "Target role match."
        }
    ]

    saved = persist_qualified_opportunities(user.user_id, None, candidates_with_missing_id)
    assert saved == 1  # Only the valid candidate was persisted; the invalid one was safely skipped

    persisted = db_session.query(GlobalProfiles).filter_by(linkedin_id="valid-vp-sales").first()
    assert persisted is not None


def test_job_status_distinguishes_zero_results_from_failure(flask_app, clean_db):
    """Verifies that a genuine zero-result search completes with status COMPLETED and results_count=0."""
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_empty_voyager = CandidateList([], status="ZERO_RESULTS", provider="VOYAGER")
    mock_empty_public = CandidateList([], status="ZERO_RESULTS", provider="PUBLIC_WEB")

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_empty_voyager), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_public_web", return_value=mock_empty_public):

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
    assert reloaded_job.results_count == 0
    assert "0 candidates matched" in reloaded_job.progress.get("message", "")


def test_voyager_redirect_stops_immediately_without_following_30_redirects():
    """
    Verifies that open_linkedin_api._fetch stops immediately on 302/redirect
    without blindly following 30 redirect loops, raising UnauthorizedException with sanitized path.
    """
    from open_linkedin_api.client import UnauthorizedException
    from requests.cookies import RequestsCookieJar
    from open_linkedin_api.linkedin import Linkedin

    jar = RequestsCookieJar()
    jar.set("li_at", "mock_li_at", domain=".linkedin.com", path="/")
    jar.set("JSESSIONID", "ajax:12345", domain=".linkedin.com", path="/")
    client = Linkedin(username="", password="", authenticate=True, cookies=jar)

    # Mock response returning 302 redirect with set-cookie li_at=delete me
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {
        "Location": "https://www.linkedin.com/voyager/api/me",
        "Set-Cookie": "li_at=delete me; Expires=Thu, 01-Jan-1970 00:00:00 GMT"
    }

    with patch.object(client.client.session, "get", return_value=mock_resp) as mock_get:
        with pytest.raises(UnauthorizedException) as exc_info:
            client._fetch("/graphql?variables=test")

        # Verify only 1 request was issued with allow_redirects=False (no 30-redirect loop)
        assert mock_get.call_count == 1
        _, kwargs = mock_get.call_args
        assert kwargs.get("allow_redirects") is False

        # Verify sanitized exception message contains category without sensitive tokens
        err_text = str(exc_info.value)
        assert "302" in err_text
        assert "cookie_invalidated" in err_text
        assert "mock_li_at" not in err_text


def test_discover_candidates_via_voyager_stops_early_on_expired_session(clean_db):
    """
    Verifies that discover_candidates_via_voyager validates session first and does NOT
    fire multiple search queries when the stored session is expired.
    """
    user = _create_mock_user()
    uid = user.user_id

    from app.integrations.linkedin.voyager_client import encrypt_credential
    # Create expired LinkedIn details in DB
    li = UsersLinkedinDetails(
        user_id=uid,
        auth_data_encrypted=encrypt_credential(json.dumps({"li_at": "expired_token", "JSESSIONID": "ajax:9999"})),
        connection_status="EXPIRED"
    )
    db_session.add(li)
    db_session.commit()

    search_plan = {
        "search_keywords": "B2B SaaS",
        "keyword_title": "VP Sales",
        "queries": [
            {"id": "q1", "title": "VP Sales", "keywords": "SaaS"},
            {"id": "q2", "title": "Head of Sales", "keywords": "SaaS"},
            {"id": "q3", "title": "CRO", "keywords": "SaaS"}
        ]
    }

    # Mock validate_user_session returning expired
    with patch("app.services.gtm_pipeline_service.validate_user_session") as mock_val:
        mock_val.return_value = {"valid": False, "category": "expired", "message": "Session expired or revoked."}
        with patch("app.services.gtm_pipeline_service.create_voyager_client_from_db") as mock_create:
            res = discover_candidates_via_voyager(uid, search_plan)

            assert res.status == "AUTH_EXPIRED"
            assert res.error_category == "expired"
            assert len(res) == 0
            # create_voyager_client_from_db was never called because validation failed pre-flight
            assert mock_create.call_count == 0


def test_public_web_http_202_classified_as_bot_challenge_not_zero_results():
    """
    Verifies that when DuckDuckGo returns HTTP 202 bot challenges,
    discover_candidates_via_public_web classifies the outcome honestly as BOT_CHALLENGE,
    never masking the failure as ZERO_RESULTS.
    """
    from app.services.scraping_service import SearchEngineUnavailableError

    context = {"target_icp": "B2B SaaS"}
    plan = {
        "queries": [{"id": "q1", "title": "VP Sales", "keywords": "Enterprise Cloud"}]
    }

    with patch("app.services.gtm_pipeline_service.is_google_search_configured", return_value=True), \
         patch("app.services.gtm_pipeline_service.perform_public_web_search") as mock_search:
        mock_search.side_effect = SearchEngineUnavailableError(
            "External public search engines unavailable: DuckDuckGo Lite HTTP 202, DuckDuckGo HTML HTTP 202"
        )
        res = discover_candidates_via_public_web(context, plan)

        assert res.status == "BOT_CHALLENGE"
        assert res.error_category == "search_engine_challenge"
        assert "202" in res.raw_error
        assert len(res) == 0


def test_worker_fails_honestly_when_voyager_session_invalid(flask_app, clean_db):
    """
    Verifies that if Voyager session is AUTH_EXPIRED,
    the background worker transitions the job to FAILED, surfacing a clear actionable
    reconnect instruction and never falsely marking COMPLETED with 0 leads.
    """
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 10},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_failed_voyager = CandidateList([], status="AUTH_EXPIRED", error_category="expired", provider="VOYAGER")

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_failed_voyager):
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=10, persona_filter=None)

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.FAILED.value
    assert reloaded_job.results_count == 0
    assert "LinkedIn session expired or disconnected" in (reloaded_job.error_message or "")
    progress = reloaded_job.progress or {}
    assert progress.get("step") == "FAILED"
    assert progress.get("provider_outcomes", {}).get("VOYAGER") == "FAILED_AUTH_EXPIRED"


def test_worker_completes_when_voyager_succeeds(flask_app, clean_db):
    """
    Verifies that when native Voyager discovery succeeds,
    the pipeline completes successfully with VOYAGER discovery mode and persisted leads.
    """
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_voyager_leads = CandidateList([
        {
            "urn_id": "ACoAAB_VOYAGER_LEAD",
            "name": "Jordan Bell",
            "role": "VP Revenue Operations",
            "raw_headline": "VP Revenue Operations at Apex Systems",
            "company": "Apex Systems",
            "location": "Boston, MA",
            "profile_url": "https://www.linkedin.com/in/jordan-bell",
            "distance": "DISTANCE_1",
            "provider": "VOYAGER",
            "source_query": "q1"
        }
    ], status="SUCCESS", provider="VOYAGER")

    mock_scored = [
        {
            "urn_id": "ACoAAB_VOYAGER_LEAD",
            "name": "Jordan Bell",
            "role": "VP Revenue Operations",
            "raw_headline": "VP Revenue Operations at Apex Systems",
            "company": "Apex Systems",
            "location": "Boston, MA",
            "profile_url": "https://www.linkedin.com/in/jordan-bell",
            "provider": "VOYAGER",
            "fit_score": 88,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "High ICP alignment.",
            "intent_signals": "Growing outbound team",
            "recommended_angle": "AI lead routing"
        }
    ]

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_voyager_leads), \
         patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=mock_scored):

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
    assert reloaded_job.results_count == 1
    progress = reloaded_job.progress or {}
    assert progress.get("discovery_mode") == "VOYAGER"
    assert progress.get("provider_outcomes", {}).get("VOYAGER") == "SUCCESS"


def test_worker_completes_with_zero_results_when_voyager_finds_no_profiles(flask_app, clean_db):
    """
    Verifies that when Voyager discovery executes without error but finds zero profiles,
    the job completes as COMPLETED with 0 results and an explanatory message.
    """
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_empty_voyager = CandidateList([], status="ZERO_RESULTS", provider="VOYAGER")

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_empty_voyager):
        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

    reloaded_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded_job.status == ResearchJobStatus.COMPLETED.value
    assert reloaded_job.results_count == 0
    progress = reloaded_job.progress or {}
    assert "0 candidates matched your ICP" in progress.get("message", "")
    assert progress.get("provider_outcomes", {}).get("VOYAGER") == "ZERO_RESULTS"


def test_worker_does_not_invoke_public_web_search(flask_app, clean_db):
    """
    Verifies Phase 4 requirement: the GTM worker does NOT invoke public web discovery,
    ensuring discovery is strictly native LinkedIn Voyager.
    """
    user = _create_mock_user()
    uid = user.user_id
    _setup_user_onboarding(uid)

    job = ResearchJobs(
        user_id=uid,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_empty_voyager = CandidateList([], status="ZERO_RESULTS", provider="VOYAGER")

    with patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_empty_voyager), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_public_web") as mock_public:

        _execute_gtm_pipeline_worker(flask_app, uid, job_id, target_leads=5, persona_filter=None)

        assert mock_public.call_count == 0


def test_public_web_not_configured_when_credentials_absent():
    """
    Verifies that when Google Custom Search credentials are not set,
    discover_candidates_via_public_web keeps the provider disabled with NOT_CONFIGURED status,
    never attempting unauthenticated scraping or falsely reporting ZERO_RESULTS.
    """
    context = {"target_icp": "B2B SaaS"}
    plan = {
        "queries": [{"id": "q1", "title": "VP Sales", "keywords": "Enterprise Cloud"}]
    }

    with patch("app.services.gtm_pipeline_service.is_google_search_configured", return_value=False), \
         patch("app.services.gtm_pipeline_service.perform_public_web_search") as mock_search:

        res = discover_candidates_via_public_web(context, plan)

        assert res.status == "NOT_CONFIGURED"
        assert res.error_category == "not_configured"
        assert len(res) == 0
        assert mock_search.call_count == 0


def test_public_web_classifies_google_quota_and_auth_errors():
    """
    Verifies that Google Custom Search HTTP 429 is classified as QUOTA_EXCEEDED,
    and HTTP 403 is classified as AUTH_ERROR.
    """
    from app.services.scraping_service import SearchEngineUnavailableError

    context = {"target_icp": "B2B SaaS"}
    plan = {"queries": [{"id": "q1", "title": "VP Sales", "keywords": "SaaS"}]}

    # 1. Test Quota Exceeded (429)
    with patch("app.services.gtm_pipeline_service.is_google_search_configured", return_value=True), \
         patch("app.services.gtm_pipeline_service.perform_public_web_search") as mock_search:
        mock_search.side_effect = SearchEngineUnavailableError("Google Custom Search quota exceeded (HTTP 429)")
        res_quota = discover_candidates_via_public_web(context, plan)
        assert res_quota.status == "QUOTA_EXCEEDED"
        assert res_quota.error_category == "quota_exceeded"
        assert len(res_quota) == 0

    # 2. Test Auth Error (403)
    with patch("app.services.gtm_pipeline_service.is_google_search_configured", return_value=True), \
         patch("app.services.gtm_pipeline_service.perform_public_web_search") as mock_search:
        mock_search.side_effect = SearchEngineUnavailableError("Google Custom Search authentication or permission error (HTTP 403)")
        res_auth = discover_candidates_via_public_web(context, plan)
        assert res_auth.status == "AUTH_ERROR"
        assert res_auth.error_category == "auth_error"
        assert len(res_auth) == 0






