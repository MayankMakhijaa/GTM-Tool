import os
import sys
import json

sys.path.append(os.getcwd())
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, UserTable

def main():
    print("Testing /api/extract-profile persistence...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("main_app", "app.py")
    main_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_app)
    
    main_app.app.config['WTF_CSRF_ENABLED'] = False
    
    # We need to simulate a logged-in user
    print("Launching LinkedIn connection flow. PLEASE LOG IN IF PROMPTED...")
    from legacy.profile_extractor import launch_interactive_linkedin_login
    res = launch_interactive_linkedin_login()
    if not res.get("success"):
        print("Failed to authenticate LinkedIn:", res)
        return
        
    print("LinkedIn authenticated! Now testing /api/extract-profile persistence...")
    
    with main_app.app.test_client() as client:
        # 1. Log in the test user
        # We know the latest user is ID 20, let's just query the DB for the last user
        li = db_session.query(UsersLinkedinDetails).order_by(UsersLinkedinDetails.user_id.desc()).first()
        if not li:
            print("No user found in DB!")
            return
            
        print(f"Testing with User ID {li.user_id} and Profile URL: {li.profile_url}")
        
        with client.session_transaction() as sess:
            sess['user_id'] = li.user_id
        
        # 2. Call the extract endpoint
        payload = {"profile_url": li.profile_url}
        try:
            print("Calling /api/extract-profile (this will take 15-30s because Playwright opens)...")
            r = client.post("/api/extract-profile", json=payload)
            print("Response Status:", r.status_code)
            
            data = r.json
            if data and data.get("success"):
                print("Extraction successful!")
                # Just print some keys of the response
                print("Response keys:", list(data.get("data", {}).get("profile", {}).keys()))
            else:
                print("Extraction failed:", r.text)
                return
        except Exception as e:
            print("Error calling endpoint:", e)
            return
            
    print("\n--- Verifying Database ---")
    
    li_updated = db_session.query(UsersLinkedinDetails).filter_by(user_id=li.user_id).first()
    
    print(f"Name: {li_updated.name}")
    print(f"Headline: {li_updated.headline}")
    print(f"About populated: {bool(li_updated.about)}")
    print(f"Location populated: {bool(li_updated.location)}")
    print(f"Current Position populated: {bool(li_updated.current_position)}")
    
    exp_len = len(li_updated.experience) if li_updated.experience else 0
    edu_len = len(li_updated.education) if li_updated.education else 0
    skills_len = len(li_updated.skills) if li_updated.skills else 0
    
    print(f"Experience Count: {exp_len}")
    print(f"Education Count: {edu_len}")
    print(f"Skills Count: {skills_len}")
    
    print("Profile Data Keys:", list(li_updated.profile_data.keys()) if li_updated.profile_data else [])
    print(f"LinkedIn ID (Voyager identity intact): {li_updated.linkedin_id}")
    print(f"Connection Status: {li_updated.connection_status}")

if __name__ == "__main__":
    main()
