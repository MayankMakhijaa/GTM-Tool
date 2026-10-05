import sys
import os
sys.path.insert(0, os.getcwd())

import re
import importlib.util
from app.models.all_models import UserTable
from app.database import db_session

spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

client = app_module.app.test_client()

# GET login page to obtain CSRF token and session
res_get = client.get('/login')
html = res_get.get_data(as_text=True)
match = re.search(r'name="csrf-token" content="([^"]+)"', html)
csrf_token = match.group(1) if match else ""
print(f"Retrieved CSRF token: {csrf_token[:10]}...")

# 1. Cleanup any prior test user with this email
prior_user = db_session.query(UserTable).filter_by(email_id="jane.smith@company.com").first()
if prior_user:
    db_session.delete(prior_user)
    db_session.commit()

# 2. Signup user
signup_payload = {
    "name": "Jane Smith",
    "email": "jane.smith@company.com",
    "phone": "+14155557777",
    "password": "Password123!"
}
res_signup = client.post('/api/auth/signup', json=signup_payload, headers={'X-CSRFToken': csrf_token})
print(f"Signup response status: {res_signup.status_code}")
print(f"Signup payload response: {res_signup.get_json()}")

# 3. Login with correct credentials
login_payload_ok = {
    "identifier": "jane.smith@company.com",
    "password": "Password123!"
}
res_login_ok = client.post('/api/auth/login', json=login_payload_ok, headers={'X-CSRFToken': csrf_token})
print(f"Login OK status: {res_login_ok.status_code}")
print(f"Login OK payload response: {res_login_ok.get_json()}")

# 4. Login with wrong password
login_payload_wrong_pwd = {
    "identifier": "jane.smith@company.com",
    "password": "WrongPassword!"
}
res_login_wrong_pwd = client.post('/api/auth/login', json=login_payload_wrong_pwd, headers={'X-CSRFToken': csrf_token})
print(f"Login Wrong Pwd status: {res_login_wrong_pwd.status_code}")
print(f"Login Wrong Pwd payload response: {res_login_wrong_pwd.get_json()}")

# 5. Login with nonexistent user
login_payload_no_user = {
    "identifier": "nonexistent@company.com",
    "password": "Password123!"
}
res_login_no_user = client.post('/api/auth/login', json=login_payload_no_user, headers={'X-CSRFToken': csrf_token})
print(f"Login No User status: {res_login_no_user.status_code}")
print(f"Login No User payload response: {res_login_no_user.get_json()}")
