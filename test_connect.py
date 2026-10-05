import os
import requests
from requests.sessions import Session
import time
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, UserTable, ConnectionStatus
from app.services.onboarding_service import get_encryption_key, decrypt_credential
import uuid
import random

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    session = Session()
    unique_id = uuid.uuid4().hex[:8]
    email = f"test_connect_{unique_id}@test.com"
    phone_digits = str(random.randint(1000, 9999))
    password = "Password123!"

    # First GET to get session cookie and CSRF
    res = session.get(f"{BASE_URL}/")
    csrf_token = ""
    for line in res.text.split("\n"):
        if 'name="csrf-token"' in line:
            parts = line.split('content="')
            if len(parts) > 1:
                csrf_token = parts[1].split('"')[0]
                break
    
    session.headers.update({"X-CSRFToken": csrf_token})

    print("1. Signup user")
    res = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Test Connect",
        "email": email,
        "phone": f"+1415555{phone_digits}",
        "password": password
    })
    
    if res.status_code != 201:
        print("Signup failed:", res.text)
        return
        
    user_id = res.json()["user"]["user_id"]
    print(f"Signup successful. User ID: {user_id}")

    print("\n2. Initial LinkedIn connection status")
    res = session.get(f"{BASE_URL}/api/onboarding/linkedin/status")
    print(res.json())
    assert res.json()["data"]["connected"] is False, "Should be false initially"

    print("\n3. Connect LinkedIn with mock cookie")
    mock_cookie = f"mock_li_at_cookie_{unique_id}"
    res = session.post(f"{BASE_URL}/api/onboarding/linkedin/connect", json={
        "session_cookie": mock_cookie
    })
    print(res.json())
    assert res.json()["data"]["connected"] is True, "Should be connected after POST"

    print("\n4. Verify backend database record")
    li_record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    assert li_record is not None, "Record should exist"
    assert li_record.connection_status == ConnectionStatus.CONNECTED.value, "Status should be connected"
    
    # Decrypt and verify
    decrypted = decrypt_credential(li_record.auth_data_encrypted)
    assert decrypted == mock_cookie, f"Decrypted cookie '{decrypted}' does not match '{mock_cookie}'"
    print("Database validation successful! Cookie encrypted properly.")
    
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    assert user.onboarding_step == "COMPANY", f"State should be COMPANY, got {user.onboarding_step}"
    print("User onboarding state correctly advanced to COMPANY.")

    print("\n5. Test unauthenticated request")
    unauth_session = Session()
    res = unauth_session.post(f"{BASE_URL}/api/onboarding/linkedin/connect", json={
        "session_cookie": "hacker_cookie"
    })
    print("Unauthenticated response:", res.status_code)
    assert res.status_code in [401, 403], "Should reject unauthenticated requests"

    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    run_tests()
