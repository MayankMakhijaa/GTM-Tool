from flask import Blueprint, request, jsonify
from app.services.auth_service import signup_user, authenticate_user
from app.security.session import set_user_session, clear_user_session, login_required
from app.repositories.user_repository import get_user_by_id
from app.security.limiter import limiter

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
