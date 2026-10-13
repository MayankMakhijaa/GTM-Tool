import os
import json
import uuid
import requests
from requests.sessions import Session
import time
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, UserTable, ConnectionStatus
from app.integrations.linkedin import voyager_client

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    session = Session()
    unique_id = uuid.uuid4().hex[:8]
    email = f"test_signup_{unique_id}@test.com"
    password = "Password123!"

    # First GET to get session cookie and CSRF
    res = session.get(f"{BASE_URL}/signup")
    csrf_token = ""
    for line in res.text.split("\n"):
        if 'name="csrf-token"' in line:
            parts = line.split('content="')
            if len(parts) > 1:
                csrf_token = parts[1].split('"')[0]
                break
    
    session.headers.update({"X-CSRFToken": csrf_token})

    print("1. Testing GET /api/auth/linkedin/status")
    # This will likely return False if the headless browser isn't authenticated
    res = session.get(f"{BASE_URL}/api/auth/linkedin/status")
    print(res.json())

    # We will just verify the endpoint didn't crash.
    assert res.status_code == 200

    print("\n2. Testing POST /api/auth/signup")
    res = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Test Signup",
        "email": email,
        "phone": f"+14155551234",
        "password": password
    })
    
    if res.status_code == 201:
        user_id = res.json()["user"]["user_id"]
        print(f"Success! User signed up with user_id={user_id}")
        
        # Now create the persistent browser profile for this user_id
        profile_dir = os.path.join(os.getcwd(), "browser_profiles", str(user_id))
        os.makedirs(profile_dir, exist_ok=True)
        print(f"Created browser profile directory at: {profile_dir}")
        
        # We simulate a UI calling reconnect which will extract from the directory
        res2 = session.post(f"{BASE_URL}/api/auth/linkedin/reconnect")
        print("Reconnect response:", res2.json())
    else:
        print("Unexpected status:", res.status_code)
        print(res.text)

if __name__ == "__main__":
    run_tests()
