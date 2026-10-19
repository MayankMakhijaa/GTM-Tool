import pytest
from app_module import app as flask_app
from app.database import db_session
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP
from app.services.email_service import get_last_test_otp

def create_user_and_login(client, name, email, phone):
    client.post('/api/auth/signup', json={
        "name": name,
        "email": email,
        "phone": phone,
        "password": "StrongP@ssword123!"
    })
    otp = get_last_test_otp(email)
    if otp:
        client.post('/api/auth/verify-otp', json={"email": email, "otp": otp})
    res = client.post('/api/auth/login', json={
        "identifier": email,
        "password": "StrongP@ssword123!"
    })
    return res

def test_exit_and_save_company_draft_incomplete(client):
    create_user_and_login(client, "Draft User", "draftuser@acme-corp.com", "+14155559981")
    
    # Save draft without website_url
    res = client.post('/api/onboarding/company', json={
        "company_name": "Draft Enterprise",
        "description": "Partial draft description",
        "industry": "SaaS",
        "is_draft": True
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["company_name"] == "Draft Enterprise"
    assert data["data"]["description"] == "Partial draft description"
    assert data["data"]["website_url"] == ""

def test_resume_company_onboarding_draft(client):
    create_user_and_login(client, "Resume User", "resumeuser@acme-corp.com", "+14155559982")
    
    # Save initial partial draft
    client.post('/api/onboarding/company', json={
        "company_name": "Resume Corp",
        "industry": "Fintech",
        "is_draft": True
    })
    
    # Resume onboarding by fetching company details
    res = client.get('/api/onboarding/company')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["company_name"] == "Resume Corp"
    assert data["data"]["industry"] == "Fintech"

def test_exit_and_save_icp_draft_and_resume(client):
    create_user_and_login(client, "ICP Draft User", "icpdraft@acme-corp.com", "+14155559983")
    
    # Save ICP draft
    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Mid-Market B2B SaaS",
        "company_size": "11-50, 51-200",
        "tone": "FORMAL"
    })
    assert res.status_code == 200
    
    # Resume by fetching ICP
    res_get = client.get('/api/onboarding/icp')
    assert res_get.status_code == 200
    icp_data = res_get.get_json()["data"]
    assert icp_data["target_customer"] == "Mid-Market B2B SaaS"
    assert icp_data["company_size"] == "11-50, 51-200"
    assert icp_data["tone"] == "FORMAL"

def test_back_navigation_preserves_data(client):
    create_user_and_login(client, "Nav User", "navuser@acme-corp.com", "+14155559984")
    
    # Step 1: Save company
    client.post('/api/onboarding/company', json={
        "website_url": "acme-corp.com",
        "company_name": "Acme Global",
        "is_draft": False
    })
    
    # Step 2: Save ICP
    client.post('/api/onboarding/icp', json={
        "target_customer": "Enterprise CTOs",
        "industry": "DevTools"
    })
    
    # Navigate backward to Step 1
    company_res = client.get('/api/onboarding/company')
    assert company_res.status_code == 200
    assert company_res.get_json()["data"]["company_name"] == "Acme Global"
    
    # Navigate forward to Step 2
    icp_res = client.get('/api/onboarding/icp')
    assert icp_res.status_code == 200
    assert icp_res.get_json()["data"]["target_customer"] == "Enterprise CTOs"

def test_optimization_settings_persistence(client):
    create_user_and_login(client, "Opt User", "optuser@acme-corp.com", "+14155559985")
    
    # Save optimization settings and applied suggestion
    post_res = client.post('/api/onboarding/optimization', json={
        "optimization_status": "ACCEPTED",
        "applied_suggestion": "Headline updated in draft",
        "settings": {
            "priority_filter": "high",
            "auto_save": True
        }
    })
    assert post_res.status_code == 200
    
    # Reload settings
    get_res = client.get('/api/onboarding/optimization')
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["success"] is True
    assert data["optimization_status"] == "ACCEPTED"
    assert "Headline updated in draft" in data["applied_suggestions"]
    assert data["settings"]["priority_filter"] == "high"
