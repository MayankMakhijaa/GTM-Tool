from functools import wraps
from flask import session, jsonify, request, current_app
from app.repositories.user_repository import get_user_by_id
from app.services.otp_service import is_user_email_verified

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                "success": False,
                "error": "UNAUTHORIZED",
                "message": "Authentication required."
            }), 401
            
        user = get_user_by_id(user_id)
        if not user or not user.is_active:
            # Clear invalid session
            session.clear()
            return jsonify({
                "success": False,
                "error": "UNAUTHORIZED",
                "message": "User inactive or not found."
            }), 401

        if not is_user_email_verified(user):
            if request.path.startswith('/api/'):
                if request.endpoint not in ('auth.verify_otp', 'auth.resend_otp', 'auth.logout'):
                    return jsonify({
                        "success": False,
                        "error": "EMAIL_NOT_VERIFIED",
                        "message": "Email verification required.",
                        "redirect": "/verify-email"
                    }), 403
            else:
                from flask import redirect, url_for
                if request.endpoint != "pages.verify_email":
                    return redirect(url_for("pages.verify_email"))
            
        request.user_id = user_id
        request.user = user
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Authentication required."
                }), 401
            from flask import redirect, url_for
            return redirect(url_for('pages.login'))

        user = get_user_by_id(user_id)
        if not user or not user.is_active:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "User inactive or not found."
                }), 401
            from flask import redirect, url_for
            return redirect(url_for('pages.login'))

        if not is_user_email_verified(user):
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "EMAIL_NOT_VERIFIED",
                    "message": "Email verification required.",
                    "redirect": "/verify-email"
                }), 403
            from flask import redirect, url_for
            return redirect(url_for('pages.verify_email'))

        from app.models.all_models import UserRole
        if user.role not in (UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value):
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "FORBIDDEN",
                    "message": "Administrator privileges required."
                }), 403
            from flask import redirect, url_for
            return redirect(url_for('pages.dashboard'))

        request.user_id = user_id
        request.user = user
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Authentication required."
                }), 401
            from flask import redirect, url_for
            return redirect(url_for('pages.login'))

        user = get_user_by_id(user_id)
        if not user or not user.is_active:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "User inactive or not found."
                }), 401
            from flask import redirect, url_for
            return redirect(url_for('pages.login'))

        if not is_user_email_verified(user):
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "EMAIL_NOT_VERIFIED",
                    "message": "Email verification required.",
                    "redirect": "/verify-email"
                }), 403
            from flask import redirect, url_for
            return redirect(url_for('pages.verify_email'))

        from app.models.all_models import UserRole
        if user.role != UserRole.SUPER_ADMIN.value:
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False,
                    "error": "FORBIDDEN",
                    "message": "Super Administrator privileges required."
                }), 403
            from flask import redirect, url_for
            return redirect(url_for('pages.dashboard'))

        request.user_id = user_id
        request.user = user
        return f(*args, **kwargs)
    return decorated_function

def set_user_session(user_id: int):
    """Sets the authenticated user in the session. Preserves CSRF token to prevent token invalidation."""
    csrf_token = session.get('csrf_token')
    session.clear()
    session['user_id'] = user_id
    if csrf_token:
        session['csrf_token'] = csrf_token

def clear_user_session():
    """Clears user session attributes while preserving CSRF token."""
    csrf_token = session.get('csrf_token')
    session.clear()
    if csrf_token:
        session['csrf_token'] = csrf_token
