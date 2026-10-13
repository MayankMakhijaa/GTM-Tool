import pytest
from app.models.all_models import UserTable
from app.database import db_session

@pytest.fixture
def client(flask_app):
    return flask_app.test_client()

@pytest.fixture
def sample_user():
    user = db_session.query(UserTable).filter_by(email_id="ui_test_user@fameweb.ai").first()
    if not user:
        user = UserTable(
            name="Alex Rivera",
            email_id="ui_test_user@fameweb.ai",
            phone_no="+1555987654",
            password_hash="pbkdf2:sha256:1000$test$test",
            onboarding_step="OPTIMIZATION",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
    return {"user_id": user.user_id, "name": user.name}

def test_login_and_signup_pages_render(client):
    """Test that login and signup pages render cleanly with correct navigation links."""
    res_login = client.get("/login")
    assert res_login.status_code == 200
    html_login = res_login.get_data(as_text=True)
    assert 'href="/signup"' in html_login
    assert 'id="togglePassword"' in html_login

    res_signup = client.get("/signup")
    assert res_signup.status_code == 200
    html_signup = res_signup.get_data(as_text=True)
    assert 'href="/login"' in html_signup

def test_navigation_access_for_authenticated_users(client, sample_user):
    """Test that authenticated users in OPTIMIZATION or DASHBOARD step can access dashboard and other pages."""
    user_id = sample_user["user_id"]
    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    user.onboarding_step = "OPTIMIZATION"
    db_session.commit()

    # Verify access to pages without unwanted redirects
    for route in ["/dashboard", "/profile-optimization", "/gtm", "/emails", "/history", "/company", "/icp"]:
        res = client.get(route)
        assert res.status_code == 200, f"Expected 200 for {route}, got {res.status_code}"

def test_dynamic_user_details_in_templates(client, sample_user):
    """Test that authenticated user's name is dynamically rendered instead of hardcoded Sarah Jenkins."""
    user_id = sample_user["user_id"]
    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Sarah Jenkins" not in html
    assert "Alex" in html

    res_emails = client.get("/emails")
    assert res_emails.status_code == 200
    html_emails = res_emails.get_data(as_text=True)
    assert 'window.currentUserName = "Alex Rivera";' in html_emails or "Alex Rivera" in html_emails
