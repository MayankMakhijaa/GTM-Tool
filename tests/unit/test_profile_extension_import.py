import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from app.database import db_session
from app.models.all_models import UserTable, UsersLinkedinDetails, UsersICP
from app.security.password import hash_password
from app_module import has_usable_profile_data


def get_or_create_user(email="ext_import_user@example.com"):
    user = db_session.query(UserTable).filter_by(email_id=email).first()
    if not user:
        unique_suffix = f"{abs(hash(email)) % 10000000:07d}"
        user = UserTable(
            name="Extension Test User",
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
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_import_extension_profile_requires_auth(client):
    """Unauthenticated requests must be rejected with 401."""
    res = client.post("/api/profile-optimization/import-extension-profile", json={"name": "Alex Mercer"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "UNAUTHORIZED"


def test_import_extension_profile_validation_empty_identity(client):
    """Requests without name or headline should be rejected with 400."""
    user = get_or_create_user("no_identity@example.com")
    login_client(client, user.user_id)

    # Empty body
    res = client.post("/api/profile-optimization/import-extension-profile", json={})
    assert res.status_code == 400
    assert res.get_json()["error"] == "INVALID_PAYLOAD"

    # Only empty strings
    res2 = client.post("/api/profile-optimization/import-extension-profile", json={"name": "", "headline": ""})
    assert res2.status_code == 400
    assert res2.get_json()["error"] == "INSUFFICIENT_IDENTITY"


def test_import_extension_profile_valid_payload_success(client):
    """Valid profile data from Chrome extension DOM is saved and marked with CHROME_EXTENSION_DOM."""
    user = get_or_create_user("valid_import@example.com")
    login_client(client, user.user_id)

    payload = {
        "name": "Sarah Connor",
        "headline": "Head of Operations & AI Systems at Cyberdyne",
        "about": "Passionate technology leader specializing in automation workflows.",
        "location": "Los Angeles, California, United States",
        "current_position": "Head of Operations & AI Systems",
        "profile_url": "https://www.linkedin.com/in/sarah-connor-ops",
        "experience": [
            {
                "title": "Head of Operations",
                "company": "Cyberdyne",
                "duration": "2021 - Present",
                "description": "Leading cross-functional automation and operations."
            },
            {
                "title": "Systems Lead",
                "company": "Tech Corp",
                "duration": "2018 - 2021",
                "description": "Architected distributed workflow engines."
            }
        ],
        "education": [
            {
                "school": "MIT",
                "degree": "B.S. Computer Science",
                "dates": "2014 - 2018"
            }
        ],
        "skills": ["Leadership", "Operations", "Python", "Automation"],
        "certifications": ["PMP Certified"],
        "_source": "DOM_PAGE_SCRAPE",
        "_warnings": []
    }

    # Call endpoint via alias
    res = client.post("/api/profile-optimization/import-extension-profile", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["sections_imported"] == ["name", "headline", "about", "location", "experience", "education", "skills", "certifications"]
    assert data["experience_count"] == 2
    assert data["skills_count"] == 4

    # Verify database persistence
    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert db_record is not None
    assert db_record.name == "Sarah Connor"
    assert db_record.headline == "Head of Operations & AI Systems at Cyberdyne"
    assert db_record.about == "Passionate technology leader specializing in automation workflows."
    assert db_record.location == "Los Angeles, California, United States"
    assert db_record.profile_source == "CHROME_EXTENSION_DOM"
    assert db_record.connection_status == "CONNECTED"
    assert isinstance(db_record.experience, list) and len(db_record.experience) == 2
    assert isinstance(db_record.skills, list) and len(db_record.skills) == 4
    assert has_usable_profile_data(db_record) is True


def test_import_extension_profile_field_sanitization_and_limits(client):
    """Payloads exceeding length bounds are safely truncated without crashing."""
    user = get_or_create_user("sanitize_limits@example.com")
    login_client(client, user.user_id)

    payload = {
        "name": "A" * 300,  # Max is 200
        "headline": "B" * 800,  # Max is 500
        "about": "C" * 6000,  # Max is 4000
        "location": "D" * 300,  # Max is 200
        "current_position": "E" * 400,  # Max is 300
        "experience": [
            {
                "title": "Manager " * 50,
                "company": "Company " * 50,
                "description": "Z" * 5000  # Max is 2000
            }
        ]
    }

    res = client.post("/api/profile-optimization/import-extension-profile", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    db_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    assert len(db_record.name) <= 200
    assert len(db_record.headline) <= 500
    assert len(db_record.about) <= 4000
    assert len(db_record.location) <= 200
    assert len(db_record.current_position) <= 300
    assert len(db_record.experience[0]["description"]) <= 2000


def test_imported_profile_enables_gemini_optimization(client):
    """After extension import, /api/optimize-profile runs directly without requiring legacy credentials."""
    user = get_or_create_user("gemini_handoff@example.com")
    login_client(client, user.user_id)

    # 1. Import profile DOM
    import_payload = {
        "name": "Marcus Aurelius",
        "headline": "Managing Partner at Stoic Ventures",
        "about": "Helping early-stage enterprise SaaS founders build resilient architectures.",
        "location": "Rome, Italy",
        "experience": [
            {"title": "Partner", "company": "Stoic Ventures", "duration": "2019 - Present"}
        ],
        "skills": ["Venture Capital", "Strategy", "Operations"]
    }
    imp_res = client.post("/api/profile-optimization/import-extension-profile", json=import_payload)
    assert imp_res.status_code == 200

    # 2. Mock Gemini optimizer to verify handoff
    mock_opt_result = {
        "overall_score": 88,
        "score_rationale": "Strong narrative tailored for founders.",
        "section_analysis": [
            {"section": "Headline", "rating": "Strong", "score": 90}
        ]
    }

    with patch("profile_optimizer.optimize_linkedin_profile", return_value=mock_opt_result) as mock_opt:
        opt_res = client.post("/api/optimize-profile", json={})
        assert opt_res.status_code == 200
        opt_data = opt_res.get_json()
        assert opt_data["success"] is True
        assert opt_data["data"]["overall_score"] == 88
        assert mock_opt.called

        # Verify arguments passed to Gemini
        args, kwargs = mock_opt.call_args
        extracted_arg = args[0]
        assert extracted_arg["name"] == "Marcus Aurelius"
        assert extracted_arg["headline"] == "Managing Partner at Stoic Ventures"
        assert extracted_arg["about"] == "Helping early-stage enterprise SaaS founders build resilient architectures."
