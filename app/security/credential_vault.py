import os
import json
import base64
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

CURRENT_KEY_VERSION = 1

def _get_encryption_key(version: int = CURRENT_KEY_VERSION) -> bytes:
    """
    Retrieves the 256-bit AES encryption key for the specified version.
    Keys are loaded from environment variables (e.g. SMTP_ENCRYPTION_KEY or SMTP_ENCRYPTION_KEY_V1).
    Falls back to a derived stable key in development/test if not explicitly configured.
    """
    env_var_name = f"SMTP_ENCRYPTION_KEY_V{version}" if version > 1 else "SMTP_ENCRYPTION_KEY"
    key_str = os.environ.get(env_var_name)
    if not key_str and version == 1:
        # Check fallback generic key
        key_str = os.environ.get("LINKEDIN_SESSION_ENCRYPTION_KEY")
    
    if not key_str:
        load_dotenv()
        key_str = os.environ.get(env_var_name) or (os.environ.get("LINKEDIN_SESSION_ENCRYPTION_KEY") if version == 1 else None)

    if not key_str:
        # Development fallback (safe 32-byte key) - never store or expose
        key_str = "fameweb_smtp_dev_secret_key_32b_!" # 32 bytes

    # Convert to 32 bytes: if base64 encoded, decode; otherwise pad/truncate
    try:
        decoded = base64.b64decode(key_str)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass

    key_bytes = key_str.encode('utf-8')
    if len(key_bytes) == 32:
        return key_bytes
    elif len(key_bytes) > 32:
        return key_bytes[:32]
    else:
        return key_bytes.ljust(32, b'0')


def encrypt_smtp_credentials(credentials: Dict[str, Any], key_version: int = CURRENT_KEY_VERSION) -> Tuple[str, int]:
    """
    Encrypts a dictionary of credentials (e.g. password, tokens) using AES-256-GCM.
    Returns: (base64_encoded_ciphertext, key_version)
    The ciphertext payload contains the 12-byte nonce prepended to the GCM ciphertext and tag.
    """
    key = _get_encryption_key(key_version)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext_bytes = json.dumps(credentials).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    
    # Prepend nonce to ciphertext
    payload = nonce + ciphertext
    encoded = base64.b64encode(payload).decode('utf-8')
    return encoded, key_version


def decrypt_smtp_credentials(encrypted_payload: str, key_version: int = CURRENT_KEY_VERSION) -> Dict[str, Any]:
    """
    Decrypts an AES-256-GCM encrypted payload using the specified key version.
    Returns the parsed credentials dictionary.
    """
    if not encrypted_payload:
        return {}
    key = _get_encryption_key(key_version)
    aesgcm = AESGCM(key)
    raw_payload = base64.b64decode(encrypted_payload.encode('utf-8'))
    
    if len(raw_payload) < 12:
        raise ValueError("Invalid encrypted payload: too short.")
    
    nonce = raw_payload[:12]
    ciphertext = raw_payload[12:]
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext_bytes.decode('utf-8'))
