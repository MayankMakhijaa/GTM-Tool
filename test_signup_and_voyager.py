import os
import sys
import json
import time
import requests

sys.path.append(os.getcwd())
from legacy.profile_extractor import launch_interactive_linkedin_login
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, UserTable

def main():
    print("Launching LinkedIn connection flow. PLEASE LOG IN IF PROMPTED...")
    res = launch_interactive_linkedin_login()
    
    if not res.get("success"):
        print("Failed to authenticate LinkedIn:", res)
        return
        
    print("LinkedIn connection succeeded! Attempting signup...")
    
    # Send a request to the local server to signup
    signup_data = {
        "name": "Demo User 3",
        "email": "demo3@example.com",
        "phone": "+12345678903",
        "password": "Password123!"
    }
    import importlib.util
    spec = importlib.util.spec_from_file_location("main_app", "app.py")
    main_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_app)
    
    main_app.app.config['WTF_CSRF_ENABLED'] = False
    
    with main_app.app.test_client() as client:
        try:
            r = client.post("/api/auth/signup", json=signup_data)
            print("Signup Response:", r.status_code, r.text)
        except Exception as e:
            print("Error calling signup:", e)
            return
        
    print("\n--- Verifying Database ---")
    user = db_session.query(UserTable).filter_by(email_id="demo@example.com").first()
    if not user:
        print("User was not created in DB!")
        return
        
    print(f"User ID: {user.user_id}")
    
    li_details = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    if not li_details:
        print("UsersLinkedinDetails was not created!")
        return
        
    print(f"\nConnection Status: {li_details.connection_status}")
    print(f"Auth Data Present: {bool(li_details.auth_data_encrypted)}")
    print(f"LinkedIn ID: {li_details.linkedin_id}")
    print(f"Profile URL: {li_details.profile_url}")
    print(f"Name: {li_details.name}")
    print(f"Headline: {li_details.headline}")
    print(f"Location: {li_details.location}")
    print(f"Current Position: {li_details.current_position}")
    print(f"Experience Count: {len(li_details.experience) if li_details.experience else 0}")
    print(f"Education Count: {len(li_details.education) if li_details.education else 0}")
    print(f"Skills Count: {len(li_details.skills) if li_details.skills else 0}")
    print(f"Profile Source: {li_details.profile_source}")

if __name__ == "__main__":
    main()
