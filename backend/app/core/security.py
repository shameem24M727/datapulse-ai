import secrets
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import bcrypt
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.config import settings

def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with configured salt rounds."""
    # Ensure password is not overly long for bcrypt
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")

get_password_hash = hash_password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Enforces minimum security requirements:
    - At least 8 characters
    - At least one alphabet character
    - At least one numeric digit
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters in length."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    return True, ""

def create_access_token(
    data: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
    **kwargs,
) -> str:
    """Creates a signed JWT access token with an expiration timestamp."""
    to_encode = dict(data or {})
    to_encode.update(kwargs)

    # Normalize subject and organization aliases
    if "subject" in to_encode and "sub" not in to_encode:
        to_encode["sub"] = to_encode.pop("subject")
    if "organization_id" in to_encode and "org_id" not in to_encode:
        to_encode["org_id"] = to_encode.pop("organization_id")

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": secrets.token_hex(8),
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises ExpiredSignatureError if expired, or JWTError if signature is invalid.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

def create_refresh_token() -> str:
    """Generates a high-entropy cryptographically secure refresh token string."""
    return secrets.token_urlsafe(32)

def hash_token(raw_token: str) -> str:
    """Hashes a raw token string using SHA-256 for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
