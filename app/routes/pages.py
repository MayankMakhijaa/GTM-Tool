from flask import Blueprint, render_template, session, redirect, url_for, request
from app.security.session import login_required
from app.repositories.user_repository import get_user_by_id

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
        
    step = user.onboarding_step
    if step == "DONE":
        # Can access anything
        return None
        
    # Mapping of state to the correct endpoint
    state_routes = {
        "LINKEDIN": "pages.company",
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

@pages_bp.route("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")

@pages_bp.route("/signup")
def signup():
    if session.get("user_id"):
        return redirect(url_for("pages.dashboard"))
    return render_template("signup.html")

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

