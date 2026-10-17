import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from app.database import db_session
from app.models.all_models import UserTable, UsersLinkedinDetails, UsersICP
from app.security.password import hash_password
from app_module import persist_extracted_linkedin_profile, has_usable_profile_data
from profile_optimizer import optimize_linkedin_profile


def create_test_user(email="opt_user@acmecorp.com"):
    """Helper to create an active, verified test user."""
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    if not user:
        unique_suffix = f"{abs(hash(email)) % 10000000:07d}"
        user = UserTable(
            name="Optimization Test User",
            email_id=email,
            phone_no=f"+1415{unique_suffix}",
            password_hash=hash_password("Valid123!Password"),
            is_active=True,
            email_verified_at=datetime.utcnow(),
            onboarding_step="OPTIMIZATION"
        )
        db_session.add(user)
        db_session.commit()
    return user


def login_client(client, user_id):
    """Sets session user_id on client."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


# ---------------------------------------------------------------------------
# 1. Validation & Persistence Unit / Functional Tests
# ---------------------------------------------------------------------------

def test_has_usable_profile_data():
    """Verifies that has_usable_profile_data requires both identity and substantive content."""
    assert has_usable_profile_data(None) is False

    empty_li = UsersLinkedinDetails(user_id=999)
    assert has_usable_profile_data(empty_li) is False

    # Identity only (no content)
    name_only = UsersLinkedinDetails(user_id=999, name="Jane Doe")
    assert has_usable_profile_data(name_only) is False

    headline_only = UsersLinkedinDetails(user_id=999, headline="Founder & CEO")
    assert has_usable_profile_data(headline_only) is False

    # Content only (no identity)
    about_only = UsersLinkedinDetails(user_id=999, about="Experienced leader in AI and growth.")
    assert has_usable_profile_data(about_only) is False

    # Usable combinations
    usable_with_exp = UsersLinkedinDetails(
        user_id=999,
        name="Jane Doe",
        experience=[{"title": "Founder", "company": "Acme"}]
    )
    assert has_usable_profile_data(usable_with_exp) is True

    usable_with_headline_about = UsersLinkedinDetails(
        user_id=999,
        headline="Founder & CEO",
        about="Passionate entrepreneur."
    )
    assert has_usable_profile_data(usable_with_headline_about) is True

    usable_with_skills = UsersLinkedinDetails(
        user_id=999,
        name="Jane Doe",
        skills=["B2B Sales", "Go-To-Market"]
    )
    assert has_usable_profile_data(usable_with_skills) is True


def test_persist_extracted_linkedin_profile_normalizes_and_saves():
    """Verifies normalization and persistence of all canonical fields to PostgreSQL."""
    user = create_test_user("persist_norm@acmecorp.com")

    sample_extraction = {
        "source_url": "https://www.linkedin.com/in/alex-smith-12345",
        "profile": {
            "name": "Alex Smith",
            "headline": "VP of Revenue Operations",
            "location": "New York, NY",
            "current_position": "VP RevOps @ GrowthCo",
            "about": "Building predictable outbound pipelines.",
            "experience": [{"title": "VP RevOps", "company": "GrowthCo", "dates": "2022 - Present"}],
            "education": [{"school": "Columbia University", "degree": "BS"}],
            "skills": ["Revenue Operations", "Sales Strategy", "CRM"],
            "certifications": [{"title": "HubSpot Certified"}],
            "languages": [{"language": "English", "proficiency": "Native"}],
            "profile_photo_url": "https://media.licdn.com/dms/image/photo.jpg"
        }
    }

    record = persist_extracted_linkedin_profile(user.user_id, sample_extraction)
    assert record is not None
    assert record.user_id == user.user_id
    assert record.name == "Alex Smith"
    assert record.headline == "VP of Revenue Operations"
    assert record.location == "New York, NY"
    assert record.current_position == "VP RevOps @ GrowthCo"
    assert record.about == "Building predictable outbound pipelines."
    assert len(record.experience) == 1
    assert len(record.education) == 1
    assert len(record.skills) == 3
    assert record.profile_url == "https://www.linkedin.com/in/alex-smith-12345"
    assert record.linkedin_id == "alex-smith-12345"
    assert "certifications" in record.profile_data
    assert "languages" in record.profile_data
    assert record.profile_data["profile_photo_url"] == "https://media.licdn.com/dms/image/photo.jpg"


def test_persist_preserves_existing_data_non_destructively():
    """Verifies that non-empty existing DB values are preserved when incoming fields are empty."""
    user = create_test_user("nondestructive@acmecorp.com")

    # Initial state with existing fields
    initial_extraction = {
        "source_url": "https://www.linkedin.com/in/existing-user",
        "profile": {
            "name": "Original Name",
            "headline": "Original Headline",
            "about": "Original About section.",
            "skills": ["Leadership", "Management"],
            "certifications": [{"title": "PMP"}]
        }
    }
    persist_extracted_linkedin_profile(user.user_id, initial_extraction)

    # Subsequent extraction with empty/omitted headline, about, and skills, but updated name and new project
    partial_extraction = {
        "source_url": "",
        "profile": {
            "name": "Updated Name",
            "headline": "",        # empty string should NOT overwrite existing
            "about": None,         # None should NOT overwrite existing
            "skills": [],          # empty list should NOT overwrite existing
            "projects": [{"title": "Project Alpha"}]
        }
    }
    updated_record = persist_extracted_linkedin_profile(user.user_id, partial_extraction)

    assert updated_record.name == "Updated Name"
    assert updated_record.headline == "Original Headline"  # preserved!
    assert updated_record.about == "Original About section."  # preserved!
    assert updated_record.skills == ["Leadership", "Management"]  # preserved!
    # Rich fields merged in profile_data
    assert "certifications" in updated_record.profile_data
    assert "projects" in updated_record.profile_data


def test_persist_no_duplicate_rows():
    """Verifies that repeated extraction updates the existing row without creating duplicates."""
    user = create_test_user("no_dup@acmecorp.com")

    data1 = {"source_url": "https://www.linkedin.com/in/user1", "profile": {"name": "User 1", "headline": "HL 1"}}
    data2 = {"source_url": "https://www.linkedin.com/in/user1", "profile": {"name": "User 1 Updated", "headline": "HL 2"}}

    persist_extracted_linkedin_profile(user.user_id, data1)
    persist_extracted_linkedin_profile(user.user_id, data2)

    count = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).count()
    assert count == 1
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert record.name == "User 1 Updated"


# ---------------------------------------------------------------------------
# 2. Endpoint Authorization & Error State Tests
# ---------------------------------------------------------------------------

def test_optimize_profile_unauthorized(client):
    """POST /api/optimize-profile requires an active session."""
    res = client.post("/api/optimize-profile", json={})
    assert res.status_code == 401
    assert res.get_json()["error"] == "UNAUTHORIZED"


def test_optimize_profile_no_connection_returns_404(client):
    """POST /api/optimize-profile returns 404 if no LinkedIn record exists for the user."""
    user = create_test_user("noconn@acmecorp.com")
    # Ensure no UsersLinkedinDetails
    db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).delete()
    db_session.commit()

    login_client(client, user.user_id)
    res = client.post("/api/optimize-profile", json={})
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "NO_LINKEDIN_CONNECTION"


def test_optimize_profile_no_credentials_returns_400(client):
    """POST /api/optimize-profile returns 400 if user has a record but no encrypted credentials."""
    user = create_test_user("nocreds@acmecorp.com")
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = None
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    login_client(client, user.user_id)
    res = client.post("/api/optimize-profile", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "NO_LINKEDIN_CREDENTIALS"


def test_optimize_profile_expired_session_returns_401(client):
    """POST /api/optimize-profile detects expired session and returns 401 SESSION_EXPIRED without calling Gemini."""
    user = create_test_user("expired_sess@acmecorp.com")
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = "dummy_encrypted_data"
    li.profile_url = "https://www.linkedin.com/in/expired-user"
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    login_client(client, user.user_id)

    with patch("app.integrations.linkedin.voyager_client.validate_user_session") as mock_val, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:
        mock_val.return_value = {"valid": False, "category": "expired", "message": "Session redirected to login."}

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 401
        data = res.get_json()
        assert data["success"] is False
        assert data["error"] == "SESSION_EXPIRED"
        # Gemini must NOT be called with an empty/unauthenticated profile
        mock_opt.assert_not_called()


def test_optimize_profile_extraction_failure_returns_400(client):
    """POST /api/optimize-profile handles extraction failure gracefully with clear error."""
    user = create_test_user("extract_fail@acmecorp.com")
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = "valid_token"
    li.profile_url = "https://www.linkedin.com/in/fail-user"
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    login_client(client, user.user_id)

    with patch("app.integrations.linkedin.voyager_client.validate_user_session") as mock_val, \
         patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:
        mock_val.return_value = {"valid": True, "category": "authenticated"}
        mock_extract.side_effect = RuntimeError("Navigation timeout waiting for DOM")

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert data["error"] == "EXTRACTION_FAILED"
        mock_opt.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Successful Data-Flow Integration Tests (Automatic Extraction + Optimization)
# ---------------------------------------------------------------------------

def test_optimize_profile_triggers_extraction_and_optimizes_with_icp(client):
    """
    When profile data is empty, optimize-profile automatically triggers extraction,
    normalizes/persists it, and passes real profile data and ICP to the optimizer.
    """
    user = create_test_user("auto_extract_opt@acmecorp.com")

    # Set up ICP context for user
    icp = db_session.query(UsersICP).filter_by(user_id=user.user_id).first()
    if not icp:
        icp = UsersICP(user_id=user.user_id)
        db_session.add(icp)
    icp.target_customer = "B2B SaaS Founders"
    icp.industry = "Software / FinTech"
    icp.target_jobs_roles = "CEO, CTO, VP Sales"
    icp.company_size = "11-50 employees"
    db_session.commit()

    # User has connected LinkedIn session but empty profile fields
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = "valid_session_token"
    li.profile_url = "https://www.linkedin.com/in/target-founder"
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    mock_extracted_data = {
        "source_url": "https://www.linkedin.com/in/target-founder",
        "profile": {
            "name": "Sarah Connor",
            "headline": "Founder & CEO @ Cyberdyne Security",
            "location": "Austin, TX",
            "current_position": "Founder @ Cyberdyne",
            "about": "Protecting enterprise infrastructure from advanced cyber threats.",
            "experience": [{"title": "Founder", "company": "Cyberdyne Security", "start_date": "2021"}],
            "education": [{"school": "MIT"}],
            "skills": ["Cloud Security", "Enterprise Sales", "DevSecOps"],
            "top_skills": ["Cloud Security", "Executive Leadership"]
        }
    }

    mock_gemini_output = {
        "analyzed_at": "2026-10-15T12:00:00",
        "overall_score": 88,
        "score_rationale": "Strong alignment with B2B SaaS positioning.",
        "section_analysis": [
            {
                "section": "headline",
                "status": "PRESENT_STRONG",
                "relevance": "HIGH",
                "score": 90,
                "reason": "Directly mentions cybersecurity and founder authority.",
                "issues": [],
                "suggestions": ["Add measurable metrics"]
            }
        ],
        "recommendations": [
            {
                "priority": "HIGH",
                "section": "headline",
                "problem": "Could be punchier for FinTech buyers",
                "why_it_matters": "Higher acceptance rate from financial buyers",
                "recommended_action": "Incorporate compliance keywords",
                "original_content": "Founder & CEO @ Cyberdyne Security",
                "suggested_content": "Protecting Enterprise FinTech Infrastructure | Founder & CEO @ Cyberdyne Security",
                "reason": "Clearer ICP hook"
            }
        ]
    }

    login_client(client, user.user_id)

    with patch("app.integrations.linkedin.voyager_client.validate_user_session") as mock_val, \
         patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:

        mock_val.return_value = {"valid": True, "category": "authenticated"}
        mock_extract.return_value = mock_extracted_data
        mock_opt.return_value = mock_gemini_output

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["overall_score"] == 88

        # 1. Verify extraction was called with correct URL and session
        mock_extract.assert_called_once()
        args, kwargs = mock_extract.call_args
        assert args[0] == "https://www.linkedin.com/in/target-founder"

        # 2. Verify optimizer received real extracted profile and ICP context
        mock_opt.assert_called_once()
        opt_extracted_profile, opt_gtm_context = mock_opt.call_args[0]
        assert opt_extracted_profile["name"] == "Sarah Connor"
        assert opt_extracted_profile["headline"] == "Founder & CEO @ Cyberdyne Security"
        assert opt_extracted_profile["about"] == "Protecting enterprise infrastructure from advanced cyber threats."
        assert len(opt_extracted_profile["experience"]) == 1
        assert opt_gtm_context["target_customer"] == "B2B SaaS Founders"
        assert opt_gtm_context["industry"] == "Software / FinTech"

        # 3. Verify DB persistence of both extracted profile and optimization suggestions
        db_li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
        assert db_li.name == "Sarah Connor"
        assert db_li.headline == "Founder & CEO @ Cyberdyne Security"
        assert db_li.optimization_suggestions["overall_score"] == 88


def test_optimize_profile_with_existing_usable_profile_skips_extraction(client):
    """When the DB already contains a complete, usable profile, extraction is skipped."""
    user = create_test_user("skip_extract@acmecorp.com")

    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.name = "Existing David"
    li.headline = "VP Engineering"
    li.about = "Engineering leadership with 15+ years experience."
    li.experience = [{"title": "VP Eng", "company": "Tech Corp"}]
    li.skills = ["Python", "Architecture"]
    db_session.commit()

    login_client(client, user.user_id)

    mock_gemini_output = {
        "analyzed_at": "2026-10-15T12:00:00",
        "overall_score": 85,
        "score_rationale": "Solid profile",
        "section_analysis": [],
        "recommendations": []
    }

    with patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:
        mock_opt.return_value = mock_gemini_output

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 200

        # Extraction should NOT be called
        mock_extract.assert_not_called()
        # Optimizer should be called with existing profile
        mock_opt.assert_called_once()
        passed_profile = mock_opt.call_args[0][0]
        assert passed_profile["name"] == "Existing David"
        assert passed_profile["headline"] == "VP Engineering"


# ---------------------------------------------------------------------------
# 4. Profile Optimizer Resilient JSON Parsing Tests
# ---------------------------------------------------------------------------

def test_profile_optimizer_handles_markdown_and_malformed_json():
    """Verifies that optimize_linkedin_profile parses markdown-fenced responses and handles errors."""
    sample_profile = {
        "name": "Jane Doe",
        "headline": "Growth Marketer",
        "about": "Helping SaaS scale.",
        "experience": [{"title": "Growth Lead", "company": "SaaS Inc"}],
        "skills": ["Growth Marketing"]
    }

    # Case 1: Markdown code fences in response
    mock_resp = MagicMock()
    mock_resp.text = '```json\n{"overall_score": 92, "score_rationale": "High relevance", "section_analysis": [], "recommendations": []}\n```'

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_test_key"}), \
         patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_resp

        result = optimize_linkedin_profile(sample_profile)
        assert result["overall_score"] == 92
        assert result["score_rationale"] == "High relevance"

    # Case 2: Malformed / non-JSON response raises ValueError with clean message
    mock_resp_bad = MagicMock()
    mock_resp_bad.text = "This is not valid JSON at all."

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_test_key"}), \
         patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_resp_bad

        with pytest.raises(ValueError, match="Gemini output could not be parsed as JSON"):
            optimize_linkedin_profile(sample_profile)


# ---------------------------------------------------------------------------
# 5. Targeted Edge Cases & Reliability Tests
# ---------------------------------------------------------------------------

def test_optimize_profile_voyager_me_fallback(client):
    """
    When profile_url is None on UsersLinkedinDetails, create_voyager_client_from_db
    is invoked to query /me and resolve publicIdentifier, successfully continuing
    extraction and optimization.
    """
    user = create_test_user("voyager_fallback@acmecorp.com")
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = "valid_session_token"
    li.profile_url = None
    li.linkedin_id = None
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    login_client(client, user.user_id)

    mock_voyager = MagicMock()
    mock_voyager.get_user_profile.return_value = {
        "miniProfile": {
            "publicIdentifier": "fallback-executive"
        }
    }

    mock_extracted_data = {
        "source_url": "https://www.linkedin.com/in/fallback-executive",
        "profile": {
            "name": "Fallback Executive",
            "headline": "Managing Director",
            "about": "Decades of leadership experience.",
            "experience": [{"title": "MD", "company": "Global Corp"}]
        }
    }

    mock_gemini_output = {
        "overall_score": 85,
        "score_rationale": "Strong background",
        "section_analysis": [],
        "recommendations": []
    }

    with patch("app.integrations.linkedin.voyager_client.validate_user_session") as mock_val, \
         patch("app.integrations.linkedin.voyager_client.create_voyager_client_from_db") as mock_vclient, \
         patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:

        mock_val.return_value = {"valid": True, "category": "authenticated"}
        mock_vclient.return_value = mock_voyager
        mock_extract.return_value = mock_extracted_data
        mock_opt.return_value = mock_gemini_output

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

        # Assert voyager client was created and get_user_profile queried
        mock_vclient.assert_called_once_with(user.user_id)
        mock_voyager.get_user_profile.assert_called_once()

        # Assert extraction was called with the resolved fallback URL
        mock_extract.assert_called_once()
        args, _ = mock_extract.call_args
        assert args[0] == "https://www.linkedin.com/in/fallback-executive"

        # Assert optimizer was called
        mock_opt.assert_called_once()


def test_extract_profile_db_rollback_on_failure(client):
    """
    POST /api/extract-profile rolls back db_session when extraction encounters an exception.
    """
    user = create_test_user("rollback_test@acmecorp.com")
    login_client(client, user.user_id)

    with patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("app.database.db_session.rollback") as mock_rollback:

        mock_extract.side_effect = RuntimeError("Extraction crashed unexpectedly")

        res = client.post("/api/extract-profile", json={
            "profile_url": "https://www.linkedin.com/in/crashed-user"
        })

        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False
        assert "Profile extraction failed" in data["error"]
        mock_rollback.assert_called()


def test_optimize_profile_empty_extracted_data_never_triggers_gemini(client):
    """
    When profile extraction succeeds but returns insufficient/empty profile data,
    the endpoint returns 400 and NEVER invokes Gemini (optimize_linkedin_profile).
    """
    user = create_test_user("empty_extracted@acmecorp.com")
    li = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li:
        li = UsersLinkedinDetails(user_id=user.user_id)
        db_session.add(li)
    li.auth_data_encrypted = "valid_token"
    li.profile_url = "https://www.linkedin.com/in/empty-user"
    li.name = None
    li.headline = None
    li.about = None
    li.experience = None
    db_session.commit()

    login_client(client, user.user_id)

    # Extraction returns empty dictionary
    empty_extraction = {
        "source_url": "https://www.linkedin.com/in/empty-user",
        "profile": {}
    }

    with patch("app.integrations.linkedin.voyager_client.validate_user_session") as mock_val, \
         patch("legacy.profile_extractor.extract_linkedin_profile") as mock_extract, \
         patch("profile_optimizer.optimize_linkedin_profile") as mock_opt:

        mock_val.return_value = {"valid": True, "category": "authenticated"}
        mock_extract.return_value = empty_extraction

        res = client.post("/api/optimize-profile", json={})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert data["error"] == "EXTRACTION_FAILED"
        assert "insufficient data" in data["message"].lower()

        # Crucial check: Gemini is NEVER invoked
        mock_opt.assert_not_called()
