import pytest
from unittest.mock import patch
from app.database import db_session
from app.models.all_models import UserTable, UsersCompanyDetails
from scripts.backfill_company_ratings import backfill_company_ratings
from app.security.password import hash_password

def setup_test_company(
    user_id=888,
    company_name="Acme Tech",
    website_url="https://acmetech.io",
    rating=None,
    edited_fields=None,
    description="Software company"
):
    """Helper to set up a test user and company details in fameweb_test."""
    # Ensure user exists for foreign key
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if not user:
        user = UserTable(
            user_id=user_id,
            name="Test Owner",
            email_id=f"owner_{user_id}@acmetech.io",
            phone_no=f"+1415555{user_id:04d}",
            password_hash=hash_password("StrongP@ssword123!"),
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

    company = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    if not company:
        company = UsersCompanyDetails(
            user_id=user_id,
            company_name=company_name,
            website_url=website_url,
            rating=rating,
            edited_fields=edited_fields,
            description=description,
            industry="Technology",
            company_size="10-50"
        )
        db_session.add(company)
    else:
        company.company_name = company_name
        company.website_url = website_url
        company.rating = rating
        company.edited_fields = edited_fields
        company.description = description
    db_session.commit()
    return company


def test_backfill_dry_run_does_not_modify_database(client):
    """Dry-run must simulate research without updating the database."""
    setup_test_company(user_id=801, company_name="DryRun Corp", rating=None)

    mock_res_map = {
        "rating": {
            "value": "4.8 / 5 (AmbitionBox)",
            "score": 4.8,
            "source_name": "AmbitionBox",
            "verification_status": "VERIFIED"
        }
    }

    with patch("scripts.backfill_company_ratings.research_public_company_ratings", return_value=(mock_res_map, {"status": "SUCCESS"})):
        stats = backfill_company_ratings(dry_run=True, delay=0.0, user_id=801)

    assert stats["total_candidates"] == 1
    assert stats["updated"] == 1

    # Verify database remains UNMODIFIED (rating still None)
    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=801).first()
    assert comp.rating is None


def test_backfill_live_run_updates_only_rating(client):
    """Live run must update the rating column and leave all other fields untouched."""
    setup_test_company(
        user_id=802,
        company_name="LiveRun Corp",
        website_url="https://liverun.io",
        rating=None,
        description="Original Description"
    )

    mock_res_map = {
        "rating": {
            "value": "4.9 / 5 (GoodFirms)",
            "score": 4.9,
            "source_name": "GoodFirms",
            "verification_status": "VERIFIED"
        }
    }

    with patch("scripts.backfill_company_ratings.research_public_company_ratings", return_value=(mock_res_map, {"status": "SUCCESS"})):
        stats = backfill_company_ratings(dry_run=False, delay=0.0, user_id=802)

    assert stats["total_candidates"] == 1
    assert stats["updated"] == 1

    # Verify database rating is updated
    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=802).first()
    assert comp.rating == "4.9 / 5 (GoodFirms)"
    # Other fields must remain untouched
    assert comp.company_name == "LiveRun Corp"
    assert comp.website_url == "https://liverun.io"
    assert comp.description == "Original Description"
    assert comp.industry == "Technology"
    assert comp.company_size == "10-50"


def test_backfill_skips_when_rating_is_not_found(client):
    """When public research returns NOT_FOUND, rating column remains None."""
    setup_test_company(user_id=803, company_name="NotFound Corp", rating=None)

    mock_res_map = {
        "rating": {
            "value": "Not available",
            "verification_status": "NOT_FOUND"
        }
    }

    with patch("scripts.backfill_company_ratings.research_public_company_ratings", return_value=(mock_res_map, {"status": "NO_RATING_FOUND"})):
        stats = backfill_company_ratings(dry_run=False, delay=0.0, user_id=803)

    assert stats["total_candidates"] == 1
    assert stats["skipped_not_found"] == 1
    assert stats["updated"] == 0

    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=803).first()
    assert comp.rating is None


def test_backfill_respects_manual_edited_fields(client):
    """If edited_fields includes 'rating', backfill must not overwrite it."""
    setup_test_company(
        user_id=804,
        company_name="Manual Corp",
        rating="",  # Empty string candidate
        edited_fields=["rating", "description"]
    )

    with patch("scripts.backfill_company_ratings.research_public_company_ratings") as mock_research:
        stats = backfill_company_ratings(dry_run=False, delay=0.0, user_id=804)
        mock_research.assert_not_called()

    assert stats["skipped_manual_edit"] == 1
    assert stats["updated"] == 0

    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=804).first()
    assert comp.rating == ""  # Unchanged


def test_backfill_never_selects_existing_non_empty_ratings(client):
    """Records with pre-existing ratings must never be selected for backfill."""
    setup_test_company(
        user_id=805,
        company_name="Existing Corp",
        rating="4.5 / 5 (Google)"
    )

    with patch("scripts.backfill_company_ratings.research_public_company_ratings") as mock_research:
        stats = backfill_company_ratings(dry_run=False, delay=0.0, user_id=805)
        mock_research.assert_not_called()

    assert stats["total_candidates"] == 0
    assert stats["updated"] == 0


def test_backfill_handles_search_unavailable_as_retry_later(client):
    """When public research returns SEARCH_UNAVAILABLE, backfill logs RETRY_LATER without modifying DB."""
    setup_test_company(user_id=806, company_name="TemporaryUnavailable Corp", rating=None)

    mock_res_map = {
        "rating": {
            "value": "Search unavailable",
            "source_name": "Public Sources",
            "source_url": "https://temporaryunavailable.com",
            "evidence": "Public search engines unavailable due to anti-bot challenge or network timeout.",
            "verification_status": "SEARCH_UNAVAILABLE"
        }
    }

    with patch("scripts.backfill_company_ratings.research_public_company_ratings", return_value=(mock_res_map, {"status": "SEARCH_UNAVAILABLE"})):
        stats = backfill_company_ratings(dry_run=False, delay=0.0, user_id=806)

    assert stats["total_candidates"] == 1
    assert stats["retry_later"] == 1
    assert stats["skipped_not_found"] == 0
    assert stats["updated"] == 0

    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=806).first()
    assert comp.rating is None  # Database remains untouched
