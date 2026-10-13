from flask import Blueprint, render_template, session, redirect, url_for, request
from app.security.session import login_required
from app.repositories.user_repository import get_user_by_id
from app.services.otp_service import is_user_email_verified

pages_bp = Blueprint("pages", __name__)

def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return get_user_by_id(user_id)
    return None

def enforce_onboarding(user, current_endpoint):
    """
    Returns a redirect if the user should not be on the current_endpoint
    given their onboarding_step.
    """
    if not user:
        return None

    if not is_user_email_verified(user):
        if current_endpoint != "pages.verify_email":
            return redirect(url_for("pages.verify_email"))
        return None
        
    step = user.onboarding_step
    if step in ("DONE", "DASHBOARD", "OPTIMIZATION"):
        # Can access any main application page once onboarding has reached OPTIMIZATION, DASHBOARD, or DONE
        return None
        
    # Mapping of state to the correct endpoint
    state_routes = {
        "LINKEDIN": "pages.connect_linkedin",
        "COMPANY": "pages.company",
        "ICP": "pages.icp",
        "OPTIMIZATION": "pages.profile_optimization"
    }
    
    target = state_routes.get(step, "pages.dashboard")
    if current_endpoint != target:
        return redirect(url_for(target))
        
    return None


@pages_bp.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("pages.dashboard"))
    return render_template("home.html")

@pages_bp.route("/verify-email")
def verify_email():
    user = get_current_user()
    if user and is_user_email_verified(user):
        return redirect(url_for("pages.dashboard"))
    return render_template("verify_email.html", user=user)

@pages_bp.route("/login")
def login():
    user = get_current_user()
    if user:
        if not is_user_email_verified(user):
            return redirect(url_for("pages.verify_email"))
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")

@pages_bp.route("/signup")
def signup():
    user = get_current_user()
    if user:
        if not is_user_email_verified(user):
            return redirect(url_for("pages.verify_email"))
        return redirect(url_for("pages.dashboard"))
    return render_template("signup.html")

@pages_bp.route("/connect-linkedin")
@login_required
def connect_linkedin():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.connect_linkedin"):
        return redir
    from app.integrations.linkedin.voyager_client import validate_user_session
    from app.models.all_models import UsersLinkedinDetails
    from app.database import db_session

    linkedin_details = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    val = validate_user_session(user.user_id) if (linkedin_details and linkedin_details.auth_data_encrypted) else {"valid": False, "category": "disconnected"}
    return render_template("connect_linkedin.html", user=user, linkedin_details=linkedin_details, validation=val)

@pages_bp.route("/onboarding/linkedin")
@login_required
def onboarding_linkedin_alias():
    return redirect(url_for("pages.connect_linkedin"))

@pages_bp.route("/company")
@login_required
def company():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.company"):
        return redir
    return render_template("companydetails.html", user=user)

@pages_bp.route("/icp")
@login_required
def icp():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.icp"):
        return redir
    return render_template("icp.html", user=user)

@pages_bp.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.dashboard"):
        return redir
    return render_template("dashboard.html", user=user)

@pages_bp.route("/profile-optimization")
@login_required
def profile_optimization():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.profile_optimization"):
        return redir
        
    from app.models.all_models import UsersLinkedinDetails, UsersICP
    from app.database import db_session
    linkedin_profile = db_session.query(UsersLinkedinDetails).filter_by(user_id=user.user_id).first()
    icp_profile = db_session.query(UsersICP).filter_by(user_id=user.user_id).first()
    
    import logging
    logging.info(f"[PROFILE OPTIMIZATION] Current user identifier = {user.user_id}")
    logging.info(f"[PROFILE OPTIMIZATION] UsersLinkedinDetails row = {linkedin_profile.id if linkedin_profile else 'None'}")
    logging.info(f"[PROFILE OPTIMIZATION] Profile name = {linkedin_profile.name if linkedin_profile else 'None'}")
    logging.info(f"[PROFILE OPTIMIZATION] Profile headline = {linkedin_profile.headline if linkedin_profile else 'None'}")
    
    return render_template("profileoptimization.html", user=user, linkedin_profile=linkedin_profile, icp_profile=icp_profile)

@pages_bp.route("/gtm")
@login_required
def gtm():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.gtm"):
        return redir
    return render_template("gtm.html", user=user)

@pages_bp.route("/emails")
@login_required
def emails():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.emails"):
        return redir
    return render_template("emails.html", user=user)

@pages_bp.route("/history")
@login_required
def history():
    user = get_current_user()
    if redir := enforce_onboarding(user, "pages.history"):
        return redir
    return render_template("history.html", user=user)

