import pytest
from app_module import app as flask_app

from app.database import db_session, Base, engine
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP

# Inherits `client` fixture from tests/conftest.py with PostgreSQL fameweb_test DB isolation and safety guards

def create_user_and_login(client, name, email, phone):
    client.post('/api/auth/signup', json={
        "name": name,
        "email": email,
        "phone": phone,
        "password": "StrongP@ssword123!"
    })
    res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": "StrongP@ssword123!"
    })
    return res

def test_unauth_company_get(client):
    res = client.get('/api/onboarding/company')
    assert res.status_code == 401

def test_auth_company_get_empty(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    res = client.get('/api/onboarding/company')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"] == {}

def test_company_create_and_update(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    
    # Create
    res = client.post('/api/onboarding/company', json={
        "website_url": "example.com",
        "company_name": "Example Inc",
        "description": "A great company"
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["website_url"] == "https://example.com"
    assert data["company_name"] == "Example Inc"
    assert "scrape_status" in data
    assert data["scrape_status"] == "MANUAL"
    
    # Update
    res = client.put('/api/onboarding/company', json={
        "website_url": "https://example.com/",
        "company_name": "Example Inc Updated",
        "description": "Updated desc"
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["company_name"] == "Example Inc Updated"
    assert "company_name" in data["edited_fields"]
    
def test_company_url_validation(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    res = client.post('/api/onboarding/company', json={
        "company_name": "No URL"
    })
    assert res.status_code == 400
    assert "website_url is required" in res.get_json()["message"]

def test_company_ownership_isolation(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    client.post('/api/onboarding/company', json={
        "website_url": "usera.com",
        "company_name": "User A Company"
    })
    
    # Logout and login as User B
    client.post('/api/auth/logout')
    create_user_and_login(client, "User B", "userb@example.com", "+14155552672")
    
    # User B should see empty company
    res = client.get('/api/onboarding/company')
    assert res.get_json()["data"] == {}
    
    # User B updating shouldn't affect User A
    client.post('/api/onboarding/company', json={
        "website_url": "userb.com",
        "company_name": "User B Company"
    })
    
    # Logout B, Login A
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={"identifier": "usera@example.com", "password": "StrongP@ssword123!"})
    
    res = client.get('/api/onboarding/company')
    assert res.get_json()["data"]["company_name"] == "User A Company"

def test_icp_create_update_and_versioning(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    
    # Create ICP - Version 1
    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Startups",
        "tone": "CASUAL"
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["version"] == 1
    assert data["tone"] == "CASUAL"
    
    # Update Qualification Field - Version 2
    res = client.put('/api/onboarding/icp', json={
        "target_customer": "Enterprise",
        "tone": "CASUAL"
    })
    data = res.get_json()["data"]
    assert data["version"] == 2
    
    # Update Tone only - Version should remain 2
    res = client.put('/api/onboarding/icp', json={
        "target_customer": "Enterprise",
        "tone": "FORMAL"
    })
    data = res.get_json()["data"]
    assert data["version"] == 2
    assert data["tone"] == "FORMAL"

def test_onboarding_status(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    
    res = client.get('/api/onboarding/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data["onboarding_step"] == "LINKEDIN"
    assert data["company_completed"] is False
    assert data["icp_completed"] is False
    
    client.post('/api/onboarding/company', json={"website_url": "test.com"})
    res = client.get('/api/onboarding/status')
    data = res.get_json()
    assert data["onboarding_step"] == "ICP"
    assert data["company_completed"] is True
    
    client.post('/api/onboarding/icp', json={"target_customer": "Test"})
    res = client.get('/api/onboarding/status')
    data = res.get_json()
    assert data["onboarding_step"] == "OPTIMIZATION"
    assert data["icp_completed"] is True

def test_inactive_user_cannot_access_onboarding(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    
    # Deactivate user
    user = db_session.query(UserTable).filter_by(email_id="usera@example.com").first()
    user.is_active = False
    db_session.commit()
    
    res = client.get('/api/onboarding/company')
    # Because @login_required checks is_active
    assert res.status_code == 401

def test_icp_malformed_json_fallback(client):
    create_user_and_login(client, "User A", "usera@example.com", "+14155552671")
    res = client.post('/api/onboarding/icp', json={
        "signals": "not a list"
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["signals"] is None


# Step 7: Company Discovery & Scraping Integration Tests

def test_unauthenticated_scrape_endpoint_rejected(client):
    res = client.post('/api/onboarding/company/scrape', json={"website_url": "https://fameweb.in"})
    assert res.status_code == 401


def test_authenticated_user_identify_and_scrape_flow(client):
    from unittest.mock import patch

    create_user_and_login(client, "Shreyas", "shreyas@fameweb.in", "+919876543210")

    mock_discovery = {
        "success": True,
        "email_domain": "fameweb.in",
        "company_name": "Fameweb",
        "official_website": "https://fameweb.in/",
        "identification_status": "CONFIRMED",
        "requires_user_confirmation": False,
        "message": "Company identified successfully."
    }

    mock_scrape = {
        "status": "SUCCESS",
        "scraped_data": {
            "company_name": "Fameweb",
            "website_url": "https://fameweb.in/",
            "description": "Growth & GTM partner agency",
            "what_company_sells": "Go-to-market strategy consulting",
            "products_services": ["Strategy", "Brand", "GTM"],
            "industry": "Marketing & Advertising",
            "company_size": "11–50 employees",
            "revenue": "< $1M annual revenue",
            "location": "India",
            "rating": None,
            "other_details": "Targets ambitious teams and startups."
        },
        "source_urls": ["https://fameweb.in/"],
        "warnings": [],
        "message": "Company website scraped and extracted successfully."
    }

    with patch('app.routes.onboarding.discover_company_for_user', return_value=mock_discovery):
        with patch('app.services.scraping_service.scrape_official_company_website', return_value=mock_scrape):
            # 1. Test Identify endpoint
            id_res = client.get('/api/onboarding/company/identify')
            assert id_res.status_code == 200
            id_data = id_res.get_json()
            assert id_data["success"] is True
            assert id_data["identification_status"] == "CONFIRMED"
            assert id_data["official_website"] == "https://fameweb.in/"

            # Verify NO DB writes occurred during identify
            db_company = db_session.query(UsersCompanyDetails).first()
            assert db_company is None

            # 2. Test Scrape endpoint
            scr_res = client.post('/api/onboarding/company/scrape', json={
                "website_url": "https://fameweb.in/",
                "identification_status": "CONFIRMED",
                "confirmed_by_user": True
            })
            assert scr_res.status_code == 200
            scr_data = scr_res.get_json()
            assert scr_data["success"] is True
            assert scr_data["scraped_data"]["company_size"] == "11–50 employees"
            assert scr_data["scraped_data"]["location"] == "India"

            # Verify NO DB writes occurred during scraping
            db_company = db_session.query(UsersCompanyDetails).first()
            assert db_company is None


def test_identification_uncertainty_requires_confirmation(client):
    from unittest.mock import patch

    create_user_and_login(client, "User", "user@ambiguous.com", "+14155552999")

    mock_discovery = {
        "success": True,
        "email_domain": "ambiguous.com",
        "company_name": "Ambiguous Corp",
        "official_website": "https://ambiguouscorp.org",
        "identification_status": "NEEDS_CONFIRMATION",
        "requires_user_confirmation": True,
        "message": "Please confirm your company's official website."
    }

    with patch('app.routes.onboarding.discover_company_for_user', return_value=mock_discovery):
        id_res = client.get('/api/onboarding/company/identify')
        assert id_res.status_code == 200
        id_data = id_res.get_json()
        assert id_data["identification_status"] == "NEEDS_CONFIRMATION"
        assert id_data["requires_user_confirmation"] is True

        # Unconfirmed scrape attempt should fail
        scr_res = client.post('/api/onboarding/company/scrape', json={
            "website_url": "https://ambiguouscorp.org",
            "identification_status": "NEEDS_CONFIRMATION",
            "confirmed_by_user": False
        })
        assert scr_res.status_code == 400
        assert scr_res.get_json()["success"] is False


def test_scraping_failure_recovers_gracefully(client):
    from unittest.mock import patch

    create_user_and_login(client, "User", "user@unreachable.com", "+14155552888")

    mock_scrape = {
        "status": "FAILED",
        "scraped_data": None,
        "source_urls": [],
        "warnings": ["Website unreachable or timed out."],
        "message": "Scraping failed: Unable to connect to company website."
    }

    with patch('app.services.scraping_service.scrape_official_company_website', return_value=mock_scrape):
        scr_res = client.post('/api/onboarding/company/scrape', json={
            "website_url": "https://unreachable.com",
            "identification_status": "CONFIRMED",
            "confirmed_by_user": True
        })
        assert scr_res.status_code == 400
        scr_data = scr_res.get_json()
        assert scr_data["success"] is False
        assert "Unable to connect" in scr_data["message"]


def test_partial_extraction_populates_available_fields(client):
    from unittest.mock import patch

    create_user_and_login(client, "User", "user@partial.com", "+14155552777")

    mock_scrape = {
        "status": "PARTIAL",
        "scraped_data": {
            "company_name": "Partial Corp",
            "website_url": "https://partial.com",
            "description": "Minimal description",
            "what_company_sells": None,
            "products_services": [],
            "industry": "Software & SaaS",
            "company_size": None,
            "revenue": None,
            "location": None,
            "rating": None,
            "other_details": None
        },
        "source_urls": ["https://partial.com"],
        "warnings": ["Partial data extracted"],
        "message": "Company website scraped with partial details extracted."
    }

    with patch('app.services.scraping_service.scrape_official_company_website', return_value=mock_scrape):
        scr_res = client.post('/api/onboarding/company/scrape', json={
            "website_url": "https://partial.com",
            "identification_status": "CONFIRMED",
            "confirmed_by_user": True
        })
        assert scr_res.status_code == 200
        data = scr_res.get_json()
        assert data["success"] is True
        assert data["status"] == "PARTIAL"
        assert data["scraped_data"]["company_name"] == "Partial Corp"
        assert data["scraped_data"]["revenue"] is None


def test_save_company_persists_other_details_and_edited_fields(client):
    create_user_and_login(client, "Shreyas", "shreyas@fameweb.in", "+919876543210")

    # Save company profile
    res = client.post('/api/onboarding/company', json={
        "company_name": "Fameweb",
        "website_url": "https://fameweb.in",
        "description": "Growth & GTM partner agency",
        "what_company_sells": "Go-to-market consulting",
        "products_services": ["Strategy", "Brand", "GTM"],
        "industry": "Marketing & Advertising",
        "company_size": "11–50 employees",
        "revenue": "< $1M annual revenue",
        "location": "India",
        "rating": "Not available",
        "other_details": "Targets ambitious teams and startups."
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["company_name"] == "Fameweb"
    assert data["products_services"] == "Strategy, Brand, GTM"
    assert data["other_details"] == "Targets ambitious teams and startups."

    # Update one field and verify edited_fields tracking
    res_update = client.put('/api/onboarding/company', json={
        "company_name": "Fameweb",
        "website_url": "https://fameweb.in",
        "description": "Growth & GTM partner agency",
        "what_company_sells": "Go-to-market consulting",
        "products_services": "Strategy, Brand, GTM",
        "industry": "Marketing & Advertising",
        "company_size": "11–50 employees",
        "revenue": "< $1M annual revenue",
        "location": "India",
        "rating": "4.8/5",
        "other_details": "Targets ambitious teams and startups updated."
    })
    assert res_update.status_code == 200
    updated_data = res_update.get_json()["data"]
    assert "rating" in updated_data["edited_fields"]
    assert "other_details" in updated_data["edited_fields"]
    assert updated_data["rating"] == "4.8/5"


def test_saved_company_data_precedence_on_get(client):
    create_user_and_login(client, "Shreyas", "shreyas@fameweb.in", "+919876543210")

    # Initially GET returns empty
    res1 = client.get('/api/onboarding/company')
    assert res1.get_json()["data"] == {}

    # Save company details
    client.post('/api/onboarding/company', json={
        "website_url": "https://fameweb.in",
        "company_name": "Fameweb Saved"
    })

    # Subsequent GET returns saved details
    res2 = client.get('/api/onboarding/company')
    assert res2.status_code == 200
    assert res2.get_json()["data"]["company_name"] == "Fameweb Saved"


def test_step1_to_step2_page_access_and_transition(client):
    """
    Verifies that a newly registered user loads Step 1 (/company),
    identifies company domain without stalling, completes Step 1,
    and transitions smoothly to Step 2 (/icp) with full page access.
    """
    create_user_and_login(client, "Alex Founder", "alex@innovatech-ai.io", "+14155551234")

    # 1. Step 1 HTML page access
    comp_page = client.get('/company')
    assert comp_page.status_code == 200
    assert b"understand your business" in comp_page.data or b"STAGE // 01" in comp_page.data

    # 2. Company domain identification endpoint responds cleanly
    id_resp = client.get('/api/onboarding/company/identify')
    assert id_resp.status_code == 200
    id_data = id_resp.get_json()
    assert id_data.get("success") is True
    assert id_data.get("email_domain") == "innovatech-ai.io"

    # 3. Save company details (completing Step 1)
    save_resp = client.post('/api/onboarding/company', json={
        "company_name": "InnovaTech AI",
        "website_url": "https://innovatech-ai.io",
        "description": "Enterprise AI workflow automation platform.",
        "industry": "Software & SaaS",
        "what_company_does": "AI Automation",
        "products_services": "Engine, Analytics",
        "is_draft": False
    })
    assert save_resp.status_code == 200
    assert save_resp.get_json()["success"] is True

    # 4. Status reflects completion of Step 1 and transition to ICP
    status_resp = client.get('/api/onboarding/status')
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["company_completed"] is True
    assert status_data["onboarding_step"] == "ICP"

    # 5. Access Step 2 HTML page (/icp)
    icp_page = client.get('/icp', follow_redirects=False)
    assert icp_page.status_code == 200
    assert b"Persona Constructor" in icp_page.data or b"Questionnaire" in icp_page.data

