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
    
    print(res.json())
    # Note: If we don't have a valid linkedin session on the local browser, this will fail with 400.
    # That is the EXPECTED BEHAVIOR of the security constraints we just implemented!
    if res.status_code == 400 and res.json().get("error") == "LINKEDIN_NOT_CONNECTED":
        print("Success! Security correctly blocked unauthenticated signup.")
    elif res.status_code == 201:
        print("Success! User signed up (local browser was authenticated).")
    else:
        print("Unexpected status:", res.status_code)

if __name__ == "__main__":
    run_tests()
