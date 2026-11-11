import os
import time
import json
from unittest.mock import patch, MagicMock
import pytest

from app.database import db_session
from app.models.all_models import (
    UserTable,
    UsersICP,
    UsersCompanyDetails,
    UsersLinkedinDetails,
    ResearchJobs,
    ResearchJobStatus,
    GlobalProfiles,
    UsersProfiles,
    LeadStatus
)
import sys
from app_module import app as flask_app
from app.services.gtm_pipeline_service import (
    start_gtm_research_job,
    _execute_gtm_pipeline_worker,
    get_user_opportunities
)


from datetime import datetime

@pytest.fixture
def test_user(clean_db):
    user = UserTable(
        name="Test Founder",
        email_id="test_gtm_orchestrator@example.com",
        phone_no="+15550001234",
        password_hash="fakehash",
        email_verified_at=datetime.utcnow(),
        onboarding_step="DONE",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()

    # Company details
    comp = UsersCompanyDetails(
        user_id=user.user_id,
        company_name="ScaleFlow AI",
        website_url="https://scaleflow.io",
        description="Autonomous sales prospecting and lead routing platform.",
        what_company_sells="AI sales agents that qualify inbound and outbound B2B leads.",
        products_services="ScaleFlow Agent Suite",
        industry="B2B SaaS / DevTools",
        company_size="11-50 employees"
    )
    db_session.add(comp)

    # ICP details
    icp = UsersICP(
        user_id=user.user_id,
        target_customer="Mid-Market B2B SaaS companies",
        target_jobs_roles="VP of Sales, CRO, Head of RevOps",
        company_size="50-500 employees",
        revenue_range="$5M-$50M ARR",
        industry="Enterprise Software, Cloud Services",
        location="United States, India",
        keywords="sales velocity, inbound triage, HubSpot migration",
        version=1
    )
    db_session.add(icp)

    db_session.commit()
    return user


def test_gtm_pipeline_executes_openserp_when_feature_flag_active(test_user):
    """
    Verify that when GTM_USE_OPENSERP=true, the worker executes the SinglePromptMultiEngineOrchestrator
    path, qualifies leads, persists them to GlobalProfiles and UsersProfiles, and exposes them
    via get_user_opportunities.
    """
    user_id = test_user.user_id
    job = ResearchJobs(
        user_id=user_id,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        attempts=1
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_search_plan = {
        "queries": [
            {"id": "q1", "title": "VP of Sales", "keywords": "B2B SaaS", "location": "United States"}
        ],
        "keyword_title": "VP of Sales",
        "search_keywords": "B2B SaaS"
    }

    mock_engine_items = [
        {
            "title": "Rajesh Nair - VP of Sales - TechCorp | LinkedIn",
            "url": "https://in.linkedin.com/in/rajesh-nair-vp-sales",
            "snippet": "Rajesh Nair. VP of Sales at TechCorp in Bengaluru, India."
        }
    ]

    mock_gemini_qual = [
        {
            "urn_id": "rajesh-nair-vp-sales",
            "fit_score": 92,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Direct role and B2B SaaS alignment.",
            "intent_signals": "Active hiring in outbound sales.",
            "recommended_angle": "Discuss automating prospecting pipeline."
        }
    ]

    with patch.dict(os.environ, {"GTM_USE_OPENSERP": "true"}), \
         patch("app.services.gtm_pipeline_service.generate_search_plan", return_value=mock_search_plan), \
         patch("app.services.discovery.providers.OpenSerpClient.search") as mock_search, \
         patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=json.dumps(mock_gemini_qual)), \
         patch("app.services.gtm_pipeline_service.enrich_company_public_web", return_value={"summary": "TechCorp cloud"}):

        # Configure mock search response for OpenSerpClient
        mock_search.return_value = {
            "engine": "google",
            "status": "SUCCESS",
            "items": [
                {
                    "title": "Rajesh Nair - VP of Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/rajesh-nair-vp-sales",
                    "description": "Rajesh Nair. VP of Sales at TechCorp in Bengaluru, India.",
                    "snippet": "Rajesh Nair. VP of Sales at TechCorp in Bengaluru, India.",
                    "domain": "in.linkedin.com",
                    "engine": "google",
                    "rank": 1
                }
            ],
            "count": 1,
            "latency_ms": 120.0,
            "error_message": None,
            "cooldown_seconds": 0.0
        }

        # Run worker directly
        _execute_gtm_pipeline_worker(flask_app, user_id, job_id, target_leads=5, persona_filter=None)

    # Check job state
    completed_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert completed_job.status == ResearchJobStatus.COMPLETED.value
    assert completed_job.progress["discovery_mode"] == "OPENSERP_MULTI_ENGINE"
    assert completed_job.results_count >= 1

    # Check opportunities API
    opps = get_user_opportunities(user_id)
    assert len(opps) >= 1
    rajesh = next((o for o in opps if "rajesh-nair" in o["profile_url"]), None)
    assert rajesh is not None
    assert rajesh["name"] == "Rajesh Nair"
    assert rajesh["company"] == "TechCorp"
    assert rajesh["score"] == 92
    assert rajesh["tier"] == "Tier 1 Priority Match"


def test_durable_late_provenance_persisted_to_database(test_user):
    """
    CRITICAL INTEGRATION TEST:
    1. Early engine (Google) discovers and persists candidate to GlobalProfiles.
    2. Late engine (Bing) discovers the same candidate within the same prompt.
    3. Verify that GlobalProfiles.company_data['sources'] in PostgreSQL contains BOTH 'google' and 'bing'.
    4. Verify that other company_data fields (tier, intent_signals, etc.) remain intact.
    5. Verify Gemini qualification was called only ONCE (no requalification).
    6. Verify only ONE UsersProfiles opportunity was created (no duplicate lead/billing).
    """
    user_id = test_user.user_id
    job = ResearchJobs(
        user_id=user_id,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        attempts=1
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_search_plan = {
        "queries": [
            {"id": "q1", "title": "VP of Sales", "keywords": "B2B SaaS", "location": "United States"}
        ],
        "keyword_title": "VP of Sales",
        "search_keywords": "B2B SaaS"
    }

    mock_gemini_qual = [
        {
            "urn_id": "rajesh-nair-vp-sales",
            "fit_score": 92,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Direct role and B2B SaaS alignment.",
            "intent_signals": "Active hiring in outbound sales.",
            "recommended_angle": "Discuss automating prospecting pipeline."
        }
    ]

    gemini_call_count = 0
    def mock_gemini_call(*args, **kwargs):
        nonlocal gemini_call_count
        gemini_call_count += 1
        return json.dumps(mock_gemini_qual)

    # Provider search returns Google first, then Bing with the exact same candidate
    search_call_count = 0
    def mock_openserp_search(engine, query, limit=10, timeout=None):
        nonlocal search_call_count
        search_call_count += 1
        eng = engine.lower()
        if eng in ("google", "bing"):
            return {
                "engine": eng,
                "status": "SUCCESS",
                "items": [{
                    "title": "Rajesh Nair - VP of Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/rajesh-nair-vp-sales",
                    "description": "Rajesh Nair. VP of Sales at TechCorp in Bengaluru, India.",
                    "snippet": "Rajesh Nair. VP of Sales at TechCorp in Bengaluru, India.",
                    "domain": "in.linkedin.com",
                    "engine": eng,
                    "rank": 1
                }],
                "count": 1,
                "latency_ms": 50.0,
                "error_message": None,
                "cooldown_seconds": 0.0
            }
        return {
            "engine": eng,
            "status": "EMPTY_RESPONSE",
            "items": [],
            "count": 0,
            "latency_ms": 10.0,
            "error_message": None,
            "cooldown_seconds": 0.0
        }

    with patch.dict(os.environ, {"GTM_USE_OPENSERP": "true"}), \
         patch("app.services.gtm_pipeline_service.generate_search_plan", return_value=mock_search_plan), \
         patch("app.services.discovery.providers.OpenSerpClient.search", side_effect=mock_openserp_search), \
         patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", side_effect=mock_gemini_call), \
         patch("app.services.gtm_pipeline_service.enrich_company_public_web", return_value={"summary": "TechCorp cloud"}):

        _execute_gtm_pipeline_worker(flask_app, user_id, job_id, target_leads=5, persona_filter=None)

    # 1. Verify Gemini was called exactly ONCE (no requalification of duplicate)
    assert gemini_call_count == 1

    # 2. Verify only 1 UsersProfiles record was created for this user
    user_opps = db_session.query(UsersProfiles).filter_by(user_id=user_id).all()
    assert len(user_opps) == 1

    # 3. CRITICAL PROOF: GlobalProfiles.company_data['sources'] contains BOTH google and bing!
    gp = db_session.query(GlobalProfiles).filter_by(linkedin_id="rajesh-nair-vp-sales").first()
    assert gp is not None
    c_data = gp.company_data or {}
    assert "google" in c_data.get("sources", [])
    assert "bing" in c_data.get("sources", [])
    assert len(c_data["sources"]) == 2

    # 4. Verify existing company_data fields were preserved
    assert c_data.get("tier") == "Tier 1 Priority Match"
    assert c_data.get("intent_signals") == "Active hiring in outbound sales."
    assert c_data.get("recommended_angle") == "Discuss automating prospecting pipeline."


def test_gtm_pipeline_fallback_to_voyager_when_flag_inactive(test_user):
    """
    Verify that when GTM_USE_OPENSERP=false, the worker falls back 100% to Voyager discovery.
    """
    user_id = test_user.user_id
    job = ResearchJobs(
        user_id=user_id,
        status=ResearchJobStatus.QUEUED.value,
        budget={"target_leads": 5},
        attempts=1
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_search_plan = {
        "queries": [{"id": "q1", "title": "VP Sales", "keywords": "SaaS"}],
        "keyword_title": "VP Sales",
        "search_keywords": "SaaS"
    }

    mock_voyager_candidates = [
        {
            "urn_id": "sarah-connor-cro",
            "name": "Sarah Connor",
            "role": "Chief Revenue Officer",
            "raw_headline": "Chief Revenue Officer at Cyberdyne",
            "company": "Cyberdyne Systems",
            "location": "Los Angeles, CA",
            "profile_url": "https://www.linkedin.com/in/sarah-connor-cro",
            "distance": "DISTANCE_1",
            "provider": "VOYAGER",
            "source_query": "q1",
            "source_evidence": "Voyager"
        }
    ]

    mock_gemini_qual = [
        {
            "urn_id": "sarah-connor-cro",
            "fit_score": 95,
            "tier": "Tier 1 Priority Match",
            "qualification_reason": "Strategic fit.",
            "intent_signals": "High intent.",
            "recommended_angle": "Connect on scaling."
        }
    ]

    with patch.dict(os.environ, {"GTM_USE_OPENSERP": "false"}), \
         patch("app.services.gtm_pipeline_service.generate_search_plan", return_value=mock_search_plan), \
         patch("app.services.gtm_pipeline_service.discover_candidates_via_voyager", return_value=mock_voyager_candidates), \
         patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=json.dumps(mock_gemini_qual)), \
         patch("app.services.gtm_pipeline_service.enrich_company_public_web", return_value={"summary": "Cyberdyne"}):

        _execute_gtm_pipeline_worker(flask_app, test_user.user_id, job_id, target_leads=5, persona_filter=None)

    db_session.expire_all()
    completed_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert completed_job.status == ResearchJobStatus.COMPLETED.value
    # Verified fallback mode was VOYAGER
    assert completed_job.progress["discovery_mode"] == "VOYAGER"


# ==============================================================================
# Phase 1.1.2.3.2 Regression Tests: Association Success & Commit Hardening
# ==============================================================================

def test_phase11232_scenario_a_user_profile_association_failure(test_user):
    """
    Scenario A: UsersProfiles association failure
    - GlobalProfiles creation succeeds.
    - UsersProfiles creation/retrieval fails (simulated via mock or exception).
    - saved_count does not increase.
    - Candidate is absent from persisted_urns.
    """
    from app.services.gtm_pipeline_service import persist_qualified_opportunities
    from app.models.all_models import GlobalProfiles, UsersProfiles

    user_id = test_user.user_id
    candidate_slug = f"assoc-fail-{int(time.time() * 1000)}"
    candidates = [{
        "urn_id": candidate_slug,
        "name": "Association Test Lead",
        "role": "VP Engineering",
        "raw_headline": "VP Engineering at Acme",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "profile_url": f"https://www.linkedin.com/in/{candidate_slug}",
        "fit_score": 90,
        "tier": "Tier 1 Priority Match",
        "qualification_reason": "Role match.",
        "provider": "OPENSERP_GOOGLE"
    }]

    # Patch query on UsersProfiles to simulate failure to find or create
    orig_query = db_session.query
    def mock_query(model, *args, **kwargs):
        q = orig_query(model, *args, **kwargs)
        if model == UsersProfiles:
            mock_q = MagicMock()
            mock_q.filter_by.return_value.first.return_value = None
            return mock_q
        return q

    # Simulate UsersProfiles savepoint failing specifically while GlobalProfiles nested savepoint succeeds
    orig_begin_nested = db_session.begin_nested
    nested_call_count = 0
    class FailNested:
        def __enter__(self):
            raise Exception("Database lock error on users_profiles")
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_begin_nested():
        nonlocal nested_call_count
        nested_call_count += 1
        # First call is for GlobalProfiles -> let it succeed
        if nested_call_count == 1:
            return orig_begin_nested()
        # Second call is for UsersProfiles -> simulate error
        return FailNested()

    with patch.object(db_session, "query", side_effect=mock_query), \
         patch.object(db_session, "begin_nested", side_effect=mock_begin_nested):
        res = persist_qualified_opportunities(user_id, job_id=None, qualified_candidates=candidates)

    assert int(res) == 0
    assert res.saved_count == 0
    assert candidate_slug not in res.persisted_urns
    assert len(res.persisted_urns) == 0

    # Verify GlobalProfiles record was created but UsersProfiles was not
    gp = db_session.query(GlobalProfiles).filter_by(linkedin_id=candidate_slug).first()
    assert gp is not None
    up = db_session.query(UsersProfiles).filter_by(user_id=user_id, global_id=gp.global_id).first()
    assert up is None


def test_phase11232_scenario_b_successful_association(test_user):
    """
    Scenario B: Successful association
    - Both GlobalProfiles and UsersProfiles are successfully persisted.
    - Candidate is included exactly once in persisted_urns.
    - saved_count increments exactly once.
    """
    from app.services.gtm_pipeline_service import persist_qualified_opportunities
    from app.models.all_models import GlobalProfiles, UsersProfiles

    user_id = test_user.user_id
    candidate_slug = f"assoc-success-{int(time.time() * 1000)}"
    candidates = [{
        "urn_id": candidate_slug,
        "name": "Success Association Lead",
        "role": "Chief Technology Officer",
        "raw_headline": "CTO at InnovateCo",
        "company": "InnovateCo",
        "location": "New York, NY",
        "profile_url": f"https://www.linkedin.com/in/{candidate_slug}",
        "fit_score": 88,
        "tier": "Tier 1 Priority Match",
        "qualification_reason": "Perfect match.",
        "provider": "OPENSERP_BING"
    }]

    res = persist_qualified_opportunities(user_id, job_id=None, qualified_candidates=candidates)

    assert int(res) == 1
    assert res.saved_count == 1
    assert res.persisted_urns == [candidate_slug]

    # Verify both records exist and are linked in DB
    gp = db_session.query(GlobalProfiles).filter_by(linkedin_id=candidate_slug).first()
    assert gp is not None
    up = db_session.query(UsersProfiles).filter_by(user_id=user_id, global_id=gp.global_id).first()
    assert up is not None
    assert up.match_score == 88


def test_phase11232_scenario_c_commit_failure_triggers_rollback_and_reraises(test_user):
    """
    Scenario C: Commit failure
    - Simulate db_session.commit() failure.
    - Verify rollback is called.
    - Verify exception propagates and no PersistenceResult is returned.
    """
    from app.services.gtm_pipeline_service import persist_qualified_opportunities

    user_id = test_user.user_id
    candidate_slug = f"commit-fail-{int(time.time() * 1000)}"
    candidates = [{
        "urn_id": candidate_slug,
        "name": "Commit Fail Lead",
        "role": "VP Operations",
        "raw_headline": "VP Ops at GlobalTech",
        "company": "GlobalTech",
        "location": "Austin, TX",
        "profile_url": f"https://www.linkedin.com/in/{candidate_slug}",
        "fit_score": 85,
        "tier": "Tier 1 Priority Match",
        "provider": "OPENSERP_ECOSIA"
    }]

    rollback_called = False
    orig_rollback = db_session.rollback
    def tracking_rollback():
        nonlocal rollback_called
        rollback_called = True
        return orig_rollback()

    with patch.object(db_session, "commit", side_effect=RuntimeError("Disk I/O error during commit")), \
         patch.object(db_session, "rollback", side_effect=tracking_rollback):
        with pytest.raises(RuntimeError, match="Disk I/O error during commit"):
            persist_qualified_opportunities(user_id, job_id=None, qualified_candidates=candidates)

    assert rollback_called is True

