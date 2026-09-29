from functools import wraps
from flask import session, jsonify, request, current_app
from app.repositories.user_repository import get_user_by_id

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
            
        return f(*args, **kwargs)
    return decorated_function

def set_user_session(user_id: int):
    """Sets the authenticated user in the session. Regenerates session to prevent fixation."""
    # Flask regenerates the session ID automatically when contents change or session is cleared.
    session.clear()
    session['user_id'] = user_id

def clear_user_session():
    """Clears the session completely."""
    session.clear()
