from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from werkzeug.security import check_password_hash as werkzeug_check_password_hash

# We use default settings which are secure and recommended for Argon2id.
# They can be tuned later if needed for performance vs security.
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return ph.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a password against stored Argon2id or legacy Werkzeug hash."""
    if not password or not stored_hash:
        return False
    try:
        return ph.verify(stored_hash, password)
    except Exception:
        pass
    try:
        return werkzeug_check_password_hash(stored_hash, password)
    except Exception:
        return False
