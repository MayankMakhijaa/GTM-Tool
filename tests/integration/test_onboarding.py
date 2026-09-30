import pytest
from app_module import app

from app.database import db_session, Base, engine
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    from app.security.limiter import limiter
    limiter.enabled = False
    
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    with app.test_client() as client:
        with app.app_context():
            yield client
    
    db_session.remove()

def create_user_and_login(client, name, email, phone):
    client.post('/api/auth/signup', json={
        "name": name,
        "email": email,
        "phone": phone,
        "password": "password123"
    })
    res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": "password123"
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
    client.post('/api/auth/login', json={"identifier": "usera@example.com", "password": "password123"})
    
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
