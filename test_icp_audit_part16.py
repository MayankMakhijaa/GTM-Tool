import os
import sys

# Setup paths to import app
import importlib.util
spec = importlib.util.spec_from_file_location("main_app", "app.py")
main_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_app)
app = main_app.app

from app.database import db_session
from app.models.all_models import UserTable, UsersICP

import time
def run_test():
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        # Create user
        unique_id = int(time.time())
        email = f"audit_icp_{unique_id}@test.com"
        phone = f"+1415555{str(unique_id)[-4:]}"
        signup_payload = {
            "name": "Audit Tester",
            "email": email,
            "phone": phone,
            "password": "Password123"
        }
        res_signup = client.post('/api/auth/signup', json=signup_payload)
        print(f"Signup: {res_signup.status_code}, data: {res_signup.get_json()}")
        
        # Login
        res = client.post('/api/auth/login', json={"identifier": email, "password": "Password123"})
        print(f"Login Response: {res.status_code}, data: {res.get_json()}")
        
        # Ensure company is created so we can advance
        client.post('/api/onboarding/company', json={"website_url": "audit.com"})
        
        icp_payload = {
            "target_customer": "B2B SaaS Companies, Mid-Market Growth Teams, Audit Custom Tag",
            "company_size": "11-50, 51-200",
            "revenue_range": '{"label": "Growth Scale", "range": "$2M - $25M ARR"}',
            "target_jobs_roles": "VP of Sales, Head of Revenue Operations, Chief Commercial Officer, Growth Lead, Custom Audit Role",
            "industry": "FinTech, DevTools & Infrastructure, B2B SaaS, Custom Audit Sector",
            "location": "North America (US & Canada), Western Europe, Singapore",
            "keywords": "outbound automation, lead enrichment, sales capacity, inbound response time, custom audit keyword",
            "exclusions": "B2C / Consumer, Agency / Freelance, < $1M ARR, custom audit exclusion",
            "signals": {
                "active_hiring": {"enabled": True, "window": "90d Window"},
                "web_traffic_surge": {"enabled": True, "threshold": "+15% QoQ"}
            },
            "tone": "FRIENDLY"
        }
        
        print(f"\nSending payload: {icp_payload}\n")
        
        res = client.post('/api/onboarding/icp', json=icp_payload)
        
        print(f"ICP Submission Status: {res.status_code}")
        data = res.get_json()
        print(f"Response data: {data}")
        
        if res.status_code != 200:
            print("TEST FAILED")
            return
            
        print("\nVerifying DB contents...")
        
        with app.app_context():
            user = db_session.query(UserTable).filter_by(email_id=email).first()
            icp = db_session.query(UsersICP).filter_by(user_id=user.user_id).first()
            
            print(f"target_customer: {icp.target_customer}")
            print(f"company_size: {icp.company_size}")
            print(f"revenue_range: {icp.revenue_range}")
            print(f"target_jobs_roles: {icp.target_jobs_roles}")
            print(f"industry: {icp.industry}")
            print(f"location: {icp.location}")
            print(f"keywords: {icp.keywords}")
            print(f"exclusions: {icp.exclusions}")
            print(f"signals: {icp.signals}")
            print(f"tone: {icp.tone}")
            print(f"User state advanced to: {user.onboarding_step}")
            print("\nTEST SUCCESSFUL")

if __name__ == '__main__':
    run_test()
