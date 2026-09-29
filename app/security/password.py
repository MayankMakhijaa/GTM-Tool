from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# We use default settings which are secure and recommended for Argon2id.
# They can be tuned later if needed for performance vs security.
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return ph.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a password against a stored Argon2id hash."""
    try:
        return ph.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False
