from flask_wtf.csrf import CSRFProtect, CSRFError
from flask import jsonify, request

csrf = CSRFProtect()

def init_csrf(app):
    """Initialize CSRF protection for the Flask application."""
    csrf.init_app(app)
    
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "CSRF_ERROR", "message": e.description}), 400
        return e.description, 400
