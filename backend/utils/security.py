"""
Cryptographic security utilities for AMAP.

Provides:
- Secure password hashing and verification (PBKDF2-HMAC-SHA256, 600,000 iterations).
- Cryptographic JWT access token generation and signature verification (HS256).
- Constant-time string and signature comparison to prevent timing attacks.
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.config import get_settings


# PBKDF2 parameters aligned with NIST / OWASP guidelines
HASH_ALGORITHM = "sha256"
ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256 with a unique random salt.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not plain_password:
        raise ValueError("Password cannot be empty.")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        plain_password.encode("utf-8"),
        salt,
        ITERATIONS,
    )

    salt_hex = salt.hex()
    hash_hex = derived.hex()

    return f"pbkdf2_sha256${ITERATIONS}${salt_hex}${hash_hex}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False

        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])

        candidate_hash = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )

        return secrets.compare_digest(candidate_hash, expected_hash)
    except Exception:
        return False


def _b64_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    """Base64url decode with automatic padding calculation."""
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(
    payload: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed HS256 JWT access token containing the provided payload claims.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire_time = now + expires_delta
    else:
        expire_time = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = payload.copy()
    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire_time.timestamp()),
    })

    header = {
        "typ": "JWT",
        "alg": "HS256",
    }

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(to_encode, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    signature_b64 = _b64_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a signed HS256 JWT access token.
    Raises ValueError if token format is invalid, signature mismatch, or expired.
    """
    settings = get_settings()

    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format.")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature in constant time
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()

        actual_sig = _b64_decode(signature_b64)
        if not secrets.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid token signature.")

        # Decode payload JSON
        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Verify expiration
        exp = payload.get("exp")
        if exp is not None:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts > exp:
                raise ValueError("Token has expired.")

        return payload
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"Token decoding failed: {exc}") from exc
