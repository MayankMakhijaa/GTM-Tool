import logging
from flask import Blueprint, request, jsonify
from app.services.auth_service import signup_user, authenticate_user
from app.security.session import set_user_session, clear_user_session, login_required
from app.repositories.user_repository import get_user_by_id
from app.security.limiter import limiter
from app.services.otp_service import (
    create_and_send_otp,
    verify_user_otp,
    resend_user_otp,
    is_user_email_verified
)

logger = logging.getLogger(__name__)

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
        # Generate and send verification OTP - DO NOT set_user_session yet
        create_and_send_otp(user)
        return jsonify({
            "success": True,
            "requires_verification": True,
            "message": "Account created successfully. Please verify your business email to continue.",
            "email": user.email_id
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
    except Exception as e:
        logger.error(f"Error during signup: {str(e)}")
        user_message = str(e) if "email" in str(e).lower() else "Unable to complete signup. Please try again."
        return jsonify({
            "success": False,
            "message": user_message
        }), 500

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

    if not is_user_email_verified(user):
        return jsonify({
            "success": False,
            "error": "EMAIL_NOT_VERIFIED",
            "message": "Please verify your business email before logging in.",
            "email": user.email_id,
            "redirect": "/verify-email"
        }), 403
        
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

@auth_bp.route('/verify-otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    data = request.get_json() or {}
    email = data.get('email', '')
    otp = data.get('otp', '')

    if not email or not otp:
        return jsonify({
            "success": False,
            "message": "Email and 6-digit verification code are required."
        }), 400

    success, message, user = verify_user_otp(email, otp)
    if not success:
        return jsonify({
            "success": False,
            "message": message
        }), 400

    # Verification successful -> establish authenticated session
    set_user_session(user.user_id)
    return jsonify({
        "success": True,
        "message": message,
        "redirect": "/company",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email_id": user.email_id,
            "onboarding_step": user.onboarding_step
        }
    }), 200

@auth_bp.route('/resend-otp', methods=['POST'])
@limiter.limit("3 per 5 minutes")
def resend_otp():
    data = request.get_json() or {}
    email = data.get('email', '')

    if not email:
        return jsonify({
            "success": False,
            "message": "Email is required."
        }), 400

    success, message, retry_after = resend_user_otp(email)
    if not success:
        status_code = 429 if retry_after else 400
        resp = {"success": False, "message": message}
        if retry_after:
            resp["retry_after"] = retry_after
        return jsonify(resp), status_code

    return jsonify({
        "success": True,
        "message": message
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
