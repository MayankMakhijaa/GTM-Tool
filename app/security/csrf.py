from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def init_csrf(app):
    """Initialize CSRF protection for the Flask application."""
    csrf.init_app(app)
