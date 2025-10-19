"""
JWT utilities for capability token signing and verification.

Uses HS256 by default (symmetric). Can be upgraded to RS256 (asymmetric) for production.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import jwt

logger = logging.getLogger(__name__)

# JWT secret key (in production, load from secure env var or key management service)
JWT_SECRET = os.getenv("CONSENT_JWT_SECRET", "INSECURE_DEV_SECRET_CHANGE_IN_PROD")
JWT_ALGORITHM = os.getenv("CONSENT_JWT_ALGORITHM", "HS256").upper()


def _load_key_from_env(var_name: str) -> Optional[str]:
    """
    Load an RSA key from environment variable or referenced file.
    """
    value = os.getenv(var_name)
    if not value:
        return None

    candidate_path = Path(value)
    if candidate_path.exists():
        try:
            return candidate_path.read_text()
        except Exception as exc:
            logger.error(f"Failed to read key file for {var_name}: {exc}")
            return None

    # Support escaped newlines
    return value.replace("\\n", "\n")


RS256_ENABLED = False
JWT_SIGNING_KEY = JWT_SECRET
JWT_VERIFY_KEY = JWT_SECRET
JWT_LEEWAY_SECONDS = int(os.getenv("CONSENT_JWT_LEEWAY_SECONDS", "0"))

if JWT_ALGORITHM == "RS256":
    private_key = _load_key_from_env("CONSENT_JWT_PRIVATE_KEY")
    public_key = _load_key_from_env("CONSENT_JWT_PUBLIC_KEY")

    if private_key and public_key:
        RS256_ENABLED = True
        JWT_SIGNING_KEY = private_key
        JWT_VERIFY_KEY = public_key
        logger.info("Consent Service JWT configured for RS256 signing.")
    else:
        logger.error("RS256 requested but CONSENT_JWT_PRIVATE_KEY and CONSENT_JWT_PUBLIC_KEY were not provided. Falling back to HS256.")
        JWT_ALGORITHM = "HS256"
        JWT_SIGNING_KEY = JWT_SECRET
        JWT_VERIFY_KEY = JWT_SECRET
else:
    JWT_ALGORITHM = "HS256"

# Warning if using insecure dev secret
if JWT_SECRET == "INSECURE_DEV_SECRET_CHANGE_IN_PROD":
    logger.warning("⚠️  Using insecure dev JWT secret. Set CONSENT_JWT_SECRET env var for production!")


def sign_capability(payload: Dict[str, Any]) -> str:
    """
    Sign a capability token payload as JWT.

    Args:
        payload: Capability token data (must include exp, iss, etc.)

    Returns:
        Signed JWT string
    """
    try:
        token = jwt.encode(payload, JWT_SIGNING_KEY, algorithm=JWT_ALGORITHM)
        logger.debug(f"Signed capability JWT: cap_id={payload.get('cap_id')}, exp={payload.get('exp')}")
        return token
    except Exception as e:
        logger.error(f"Failed to sign JWT: {e}")
        raise


def verify_capability(token: str) -> Dict[str, Any]:
    """
    Verify and decode a capability JWT.

    Args:
        token: JWT string

    Returns:
        Decoded payload dict

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
    """
    try:
        key = JWT_VERIFY_KEY if JWT_ALGORITHM == "RS256" else JWT_VERIFY_KEY
        payload = jwt.decode(token, key, algorithms=[JWT_ALGORITHM], leeway=JWT_LEEWAY_SECONDS)
        logger.debug(f"Verified capability JWT: cap_id={payload.get('cap_id')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT verification failed: token expired")
        raise
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise


def parse_ttl_to_seconds(ttl: str) -> int:
    """
    Parse ISO-8601 duration string to seconds.

    Supports:
    - PT24H (24 hours)
    - PT1H (1 hour)
    - PT30M (30 minutes)
    - P7D (7 days)

    Args:
        ttl: ISO-8601 duration string

    Returns:
        Duration in seconds

    Raises:
        ValueError: If TTL format is invalid
    """
    ttl = ttl.upper().strip()

    try:
        # Handle PT (time) durations
        if ttl.startswith("PT"):
            duration_str = ttl[2:]  # Remove "PT"

            total_seconds = 0

            # Parse hours
            if "H" in duration_str:
                hours_str, duration_str = duration_str.split("H")
                total_seconds += int(hours_str) * 3600

            # Parse minutes
            if "M" in duration_str:
                minutes_str, duration_str = duration_str.split("M")
                total_seconds += int(minutes_str) * 60

            # Parse seconds
            if "S" in duration_str:
                seconds_str, _ = duration_str.split("S")
                total_seconds += int(seconds_str)

            return total_seconds

        # Handle P (date) durations
        elif ttl.startswith("P"):
            duration_str = ttl[1:]  # Remove "P"

            total_seconds = 0

            # Parse days
            if "D" in duration_str:
                days_str, duration_str = duration_str.split("D")
                total_seconds += int(days_str) * 86400

            # Parse weeks
            if "W" in duration_str:
                weeks_str, _ = duration_str.split("W")
                total_seconds += int(weeks_str) * 604800

            return total_seconds

        else:
            raise ValueError(f"Invalid TTL format: {ttl}")

    except Exception as e:
        logger.error(f"Failed to parse TTL '{ttl}': {e}")
        raise ValueError(f"Invalid TTL format: {ttl}")


def compute_expiration(ttl: str) -> int:
    """
    Compute Unix timestamp for expiration based on TTL.

    Args:
        ttl: ISO-8601 duration string

    Returns:
        Unix timestamp (seconds since epoch)
    """
    ttl_seconds = parse_ttl_to_seconds(ttl)
    exp_timestamp = int(datetime.utcnow().timestamp()) + ttl_seconds
    logger.debug(f"Computed expiration: ttl={ttl}, exp={exp_timestamp}")
    return exp_timestamp


def is_expired(exp: int) -> bool:
    """
    Check if a Unix timestamp has passed.

    Args:
        exp: Unix timestamp

    Returns:
        True if expired, False otherwise
    """
    now = int(datetime.utcnow().timestamp())
    expired = now >= exp
    if expired:
        logger.debug(f"Token expired: exp={exp}, now={now}")
    return expired
