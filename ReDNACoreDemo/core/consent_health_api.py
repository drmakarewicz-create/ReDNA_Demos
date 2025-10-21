"""
Consent Health API
==================

Exposes a health check endpoint for the Consent service to report:
- Whether a production-grade JWT secret is configured
- Whether JWT sign/verify roundtrip works
- Detailed error diagnostics for failures
- Current TTL configuration

This allows DevX and other monitoring tools to accurately report Consent service status.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter
import jwt

logger = logging.getLogger(__name__)

router = APIRouter()

# Known development default secrets (insecure)
DEV_SECRETS = [
    "dev-insecure-secret-change-in-production",
    "INSECURE_DEV_SECRET_CHANGE_IN_PROD",
]


def parse_secret(raw_secret: str) -> Tuple[bytes, str]:
    """
    Parse JWT secret from environment with flexible encoding support.

    Supports:
    - Raw string (UTF-8 encoded)
    - Hex-encoded string (even length, decoded to bytes)
    - Base64-encoded string (if CONSENT_JWT_SECRET_B64=true)

    Args:
        raw_secret: Secret string from environment

    Returns:
        Tuple of (secret_bytes, encoding_used)

    Raises:
        ValueError: If secret cannot be parsed
    """
    if not raw_secret:
        raise ValueError("Secret is empty")

    # Check if base64 flag is set
    is_base64 = os.getenv("CONSENT_JWT_SECRET_B64", "false").lower() in ("true", "1", "yes")

    if is_base64:
        try:
            secret_bytes = base64.b64decode(raw_secret)
            return secret_bytes, "base64"
        except binascii.Error as e:
            raise ValueError(f"Failed to decode base64 secret: {e}")

    # Try hex decoding if string is all hex and even length
    if len(raw_secret) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in raw_secret):
        try:
            secret_bytes = bytes.fromhex(raw_secret)
            return secret_bytes, "hex"
        except ValueError:
            pass  # Not valid hex, fall through to raw string

    # Default: treat as raw string
    secret_bytes = raw_secret.encode("utf-8")
    return secret_bytes, "raw"


def get_consent_config() -> Dict[str, Any]:
    """
    Get current Consent JWT configuration from environment.

    Returns:
        Dict with 'secret', 'secret_bytes', 'secret_encoding', 'has_secret',
        'ttl_minutes', 'algorithm', 'leeway_seconds', 'warning'
    """
    secret_raw = os.getenv("CONSENT_JWT_SECRET", DEV_SECRETS[0])
    ttl_str = os.getenv("CONSENT_JWT_TTL_MINUTES", "")
    algorithm = os.getenv("CONSENT_JWT_ALG", os.getenv("CONSENT_JWT_ALGORITHM", "HS256")).upper()
    leeway_str = os.getenv("CONSENT_JWT_LEEWAY_SECONDS", "30")
    audience = os.getenv("CONSENT_JWT_AUD")
    issuer = os.getenv("CONSENT_JWT_ISS")

    # Parse secret with flexible encoding
    try:
        secret_bytes, secret_encoding = parse_secret(secret_raw)
    except ValueError as e:
        secret_bytes = None
        secret_encoding = f"parse_error: {e}"

    # Parse TTL
    ttl_minutes = None
    if ttl_str:
        try:
            ttl_minutes = int(ttl_str)
        except ValueError:
            pass

    # Parse leeway
    leeway_seconds = 30  # default
    try:
        leeway_seconds = int(leeway_str)
    except ValueError:
        pass

    # Check if using dev secret
    has_secret = secret_raw and secret_raw not in DEV_SECRETS
    warning = None
    if not has_secret:
        warning = "dev secret in use"

    return {
        "secret": secret_raw,
        "secret_bytes": secret_bytes,
        "secret_encoding": secret_encoding,
        "has_secret": has_secret,
        "ttl_minutes": ttl_minutes,
        "algorithm": algorithm,
        "leeway_seconds": leeway_seconds,
        "audience": audience,
        "issuer": issuer,
        "warning": warning,
    }


def test_roundtrip() -> Tuple[bool, Optional[str]]:
    """
    Perform an in-memory JWT sign/verify roundtrip test with detailed diagnostics.

    Uses the current CONSENT_JWT_SECRET to sign a throwaway payload,
    then immediately verifies it. No external calls, no PII.

    Returns:
        Tuple of (success: bool, error_reason: Optional[str])
        - (True, None) if roundtrip succeeds
        - (False, "error message") if roundtrip fails
    """
    try:
        config = get_consent_config()

        # Check if secret parsing failed
        if config["secret_bytes"] is None:
            error_msg = f"Secret parsing failed: {config['secret_encoding']}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        # Determine key based on algorithm
        algorithm = config["algorithm"]
        if algorithm.startswith("HS"):  # Symmetric (HS256, HS384, HS512)
            signing_key = config["secret_bytes"]
            verify_key = config["secret_bytes"]
        elif algorithm.startswith("RS") or algorithm.startswith("ES"):  # Asymmetric
            # For health check, we expect symmetric keys for simplicity
            # Production RS256/ES256 would need private/public key pair
            error_msg = f"Asymmetric algorithm {algorithm} not supported in health check roundtrip"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        else:
            error_msg = f"Unknown algorithm: {algorithm}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        # Create throwaway payload with current timestamp
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=5)  # 5 minute expiry for test token

        test_payload = {
            "check": "consent_health",
            "ts": now.isoformat(),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }

        # Add optional claims if configured
        if config["issuer"]:
            test_payload["iss"] = config["issuer"]
        if config["audience"]:
            test_payload["aud"] = config["audience"]

        # Sign token
        try:
            token = jwt.encode(test_payload, signing_key, algorithm=algorithm)
        except Exception as e:
            error_msg = f"JWT sign failed: {type(e).__name__}: {str(e)}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        if not token:
            error_msg = "JWT encode returned empty token"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        # Verify token
        try:
            # Build verification options
            verify_options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
            }

            # Only verify aud/iss if they were set
            if config["audience"]:
                verify_options["verify_aud"] = True
            else:
                verify_options["verify_aud"] = False

            if config["issuer"]:
                verify_options["verify_iss"] = True
            else:
                verify_options["verify_iss"] = False

            # Decode with leeway
            verified = jwt.decode(
                token,
                verify_key,
                algorithms=[algorithm],
                leeway=config["leeway_seconds"],
                audience=config["audience"],
                issuer=config["issuer"],
                options=verify_options,
            )
        except jwt.ExpiredSignatureError as e:
            error_msg = f"JWT verify failed: ExpiredSignatureError (leeway={config['leeway_seconds']}s)"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except jwt.InvalidSignatureError as e:
            error_msg = f"JWT verify failed: InvalidSignatureError (key or algorithm mismatch)"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except jwt.InvalidAudienceError as e:
            error_msg = f"JWT verify failed: InvalidAudienceError (expected: {config['audience']})"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except jwt.InvalidIssuerError as e:
            error_msg = f"JWT verify failed: InvalidIssuerError (expected: {config['issuer']})"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except jwt.DecodeError as e:
            error_msg = f"JWT verify failed: DecodeError: {str(e)}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except jwt.InvalidTokenError as e:
            error_msg = f"JWT verify failed: {type(e).__name__}: {str(e)}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"JWT verify failed: Unexpected {type(e).__name__}: {str(e)}"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        if not verified:
            error_msg = "JWT decode returned empty payload"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        # Check payload matches
        if verified.get("check") != "consent_health":
            error_msg = "Roundtrip payload mismatch: 'check' field does not match"
            logger.warning(f"[Consent Health] {error_msg}")
            return False, error_msg

        # Success!
        logger.debug(
            f"[Consent Health] Roundtrip OK: alg={algorithm}, "
            f"encoding={config['secret_encoding']}, leeway={config['leeway_seconds']}s"
        )
        return True, None

    except Exception as e:
        error_msg = f"Unexpected roundtrip exception: {type(e).__name__}: {str(e)}"
        logger.error(f"[Consent Health] {error_msg}", exc_info=True)
        return False, error_msg


@router.get("/core/consent/health")
def consent_health() -> Dict[str, Any]:
    """
    GET /core/consent/health

    Returns comprehensive health status for Consent JWT service with detailed diagnostics.

    Response:
        200 OK with JSON:
        {
            "status": "healthy" | "degraded" | "error",
            "has_secret": bool,
            "ttl_minutes": int | null,
            "roundtrip_ok": bool,
            "warning": str | null,
            "error_reason": str | null,  # Present if roundtrip_ok=false
            "config": {
                "algorithm": str,
                "secret_encoding": str,
                "leeway_seconds": int,
                "has_audience": bool,
                "has_issuer": bool
            }
        }

    Status meanings:
        - "healthy": Production secret configured, roundtrip passes
        - "degraded": Using dev secret, but roundtrip passes
        - "error": Roundtrip failed (JWT sign/verify broken)

    Always returns 200 OK, even on error status (diagnostics always available).
    """
    config = get_consent_config()
    roundtrip_ok, error_reason = test_roundtrip()

    # Determine overall status
    if not roundtrip_ok:
        status = "error"
    elif not config["has_secret"]:
        status = "degraded"
    else:
        status = "healthy"

    response = {
        "status": status,
        "has_secret": config["has_secret"],
        "ttl_minutes": config["ttl_minutes"],
        "roundtrip_ok": roundtrip_ok,
        "warning": config["warning"],
        "error_reason": error_reason,  # None if roundtrip_ok, error message otherwise
        "config": {
            "algorithm": config["algorithm"],
            "secret_encoding": config["secret_encoding"],
            "leeway_seconds": config["leeway_seconds"],
            "has_audience": bool(config["audience"]),
            "has_issuer": bool(config["issuer"]),
        },
    }

    # Log once at appropriate level
    if not roundtrip_ok:
        logger.warning(
            f"[Consent Health] status=error, error_reason={error_reason}"
        )
    else:
        logger.debug(
            f"[Consent Health] status={status}, has_secret={config['has_secret']}, "
            f"alg={config['algorithm']}, encoding={config['secret_encoding']}"
        )

    return response


def log_consent_startup_config() -> None:
    """
    Log Consent configuration at startup for visibility.

    Call this from api.py during application startup.
    Performs a self-check and warns if roundtrip fails.
    """
    config = get_consent_config()
    logger.info(
        f"[Consent] has_secret={config['has_secret']}, "
        f"ttl_minutes={config['ttl_minutes']}, "
        f"algorithm={config['algorithm']}, "
        f"leeway={config['leeway_seconds']}s"
    )
    if config["warning"]:
        logger.warning(f"[Consent] ⚠️  {config['warning']}")
    if config["secret_bytes"] is None:
        logger.error(f"[Consent] ❌ Secret parsing failed: {config['secret_encoding']}")

    # Perform startup self-check
    roundtrip_ok, error_reason = test_roundtrip()
    if not roundtrip_ok:
        logger.warning(f"[Consent] ⚠️  Startup self-check failed: {error_reason}")
