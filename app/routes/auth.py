from flask import Blueprint, request, jsonify
from app.services.auth_service import signup_user, authenticate_user
from app.security.session import set_user_session, clear_user_session, login_required
from app.repositories.user_repository import get_user_by_id
from app.security.limiter import limiter
from app.integrations.linkedin.voyager_client import validate_linkedin_connection, extract_cookies_from_browser, encrypt_credential, create_voyager_client_from_browser
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, ConnectionStatus
import os
import json
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    try:
        user = signup_user(name, email, phone, password)
        # Auth the user right after signup
        set_user_session(user.user_id)
        
        # LinkedIn linking has been moved to /linkedin/reconnect or /linkedin/connect
        # which properly uses the user-specific browser profile.
            
        return jsonify({
            "success": True,
            "message": "User created successfully",
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "email_id": user.email_id,
                "phone_no": user.phone_no,
                "onboarding_step": user.onboarding_step,
                "optimization_status": user.optimization_status,
                "is_active": user.is_active
            }
        }), 201
    except ValueError as e:
        error_msg = str(e)
        field = "general"
        if "email" in error_msg.lower(): field = "email"
        elif "phone" in error_msg.lower(): field = "phone"
        elif "password" in error_msg.lower(): field = "password"
        elif "name" in error_msg.lower(): field = "name"
        
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": error_msg,
            "fields": {
                field: error_msg
            }
        }), 400

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json() or {}
    identifier = data.get('identifier')
    password = data.get('password')
    
    user = authenticate_user(identifier, password)
    if not user:
        return jsonify({
            "success": False,
            "error": "INVALID_CREDENTIALS",
            "message": "Invalid credentials"
        }), 401
        
    set_user_session(user.user_id)
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email_id": user.email_id,
            "phone_no": user.phone_no,
            "onboarding_step": user.onboarding_step,
            "optimization_status": user.optimization_status,
            "is_active": user.is_active
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    clear_user_session()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    from flask import session
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            "authenticated": False
        }), 200
        
    user = get_user_by_id(user_id)
    
    if not user or not user.is_active:
        return jsonify({
            "authenticated": False
        }), 200
        
    return jsonify({
        "authenticated": True,
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email_id": user.email_id,
            "phone_no": user.phone_no,
            "onboarding_step": user.onboarding_step,
            "optimization_status": user.optimization_status,
            "is_active": user.is_active
        }
    }), 200

@auth_bp.route('/linkedin/status', methods=['GET'])
@login_required
def get_linkedin_status():
    """
    Validates if the current user has a valid Voyager-authenticated LinkedIn session.
    Never launches Chromium for status checks.
    """
    user_id = request.user_id
    from app.integrations.linkedin.voyager_client import validate_user_session
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails
    res = validate_user_session(user_id)
    record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    return jsonify({
        "success": True,
        "connected": res["valid"],
        "status": res["category"],
        "message": res["message"],
        "profile": {
            "name": record.name if record else None,
            "headline": record.headline if record else None,
            "profile_url": record.profile_url if record else None
        } if (record and res["valid"]) else None
    }), 200

@auth_bp.route('/linkedin/reconnect', methods=['POST'])
@login_required
def reconnect_linkedin():
    """
    Reconnects the existing user's LinkedIn session via interactive Playwright login,
    captures cookies, encrypts and updates UsersLinkedinDetails in PostgreSQL.
    """
    user_id = request.user_id
    from legacy.profile_extractor import launch_interactive_linkedin_login
    from app.integrations.linkedin.voyager_client import validate_user_session

    result = launch_interactive_linkedin_login(user_id)
    if not result.get("success"):
        return jsonify({
            "success": False,
            "message": result.get("message", "Failed to connect LinkedIn session."),
            "error": result.get("error", "RECONNECT_FAILED")
        }), 400

    validation = validate_user_session(user_id)
    return jsonify({
        "success": True,
        "connected": validation.get("valid", False),
        "status": validation.get("category", "unknown"),
        "message": "LinkedIn session reconnected successfully."
    }), 200


