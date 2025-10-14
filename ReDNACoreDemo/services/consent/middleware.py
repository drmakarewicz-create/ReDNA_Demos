"""
Consent Middleware - Phase 5.C

Enforces namespace-level consent checks for all sensitive API endpoints.

Architecture:
- Wraps sensitive endpoints with consent validation
- Checks capability tokens for required scopes
- Audits all consent checks to agent_activity.jsonl
- Provides clear error messages for consent violations

Usage:
    from ReDNACoreDemo.services.consent.middleware import require_consent

    @app.get("/api/sensitive/data")
    @require_consent(scopes=["read:PsyDNA"], namespace="psy_insights")
    async def get_sensitive_data(request: Request):
        # Handler logic here
        pass
"""

import logging
from typing import List, Optional, Callable, Any
from functools import wraps
from fastapi import Request, HTTPException
from datetime import datetime
import json
from pathlib import Path

from .jwt_utils import verify_capability, is_expired
from .storage import ConsentStorage
from .models import LedgerEventType

logger = logging.getLogger(__name__)

# Initialize storage
_storage = ConsentStorage()


class ConsentViolation(HTTPException):
    """Raised when a consent check fails."""

    def __init__(self, reason: str, required_scopes: List[str]):
        super().__init__(
            status_code=403,
            detail={
                "error": "consent_violation",
                "reason": reason,
                "required_scopes": required_scopes,
                "help": "Request a capability token from the Consent Service with the required scopes.",
            },
        )


def _extract_token_from_request(request: Request) -> Optional[str]:
    """
    Extract capability token from request.

    Checks (in order):
    1. Authorization header: Bearer <token>
    2. Query parameter: ?token=<token>
    3. Cookie: capability_token=<token>
    """
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Strip "Bearer "

    # Check query parameter
    token = request.query_params.get("token")
    if token:
        return token

    # Check cookie
    token = request.cookies.get("capability_token")
    if token:
        return token

    return None


def _audit_consent_check(
    user_id: str,
    namespace: str,
    required_scopes: List[str],
    granted: bool,
    reason: Optional[str] = None,
    cap_id: Optional[str] = None,
) -> None:
    """
    Audit a consent check to agent_activity.jsonl.

    Logs:
    - Timestamp
    - User ID
    - Namespace
    - Required scopes
    - Whether consent was granted
    - Reason (if denied)
    - Capability ID (if granted)
    """
    audit_dir = Path("data/users") / user_id / "agent"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "agent_activity.jsonl"

    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "consent_checked",
        "user_id": user_id,
        "namespace": namespace,
        "required_scopes": required_scopes,
        "granted": granted,
        "reason": reason,
        "cap_id": cap_id,
    }

    try:
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.error(f"Failed to audit consent check: {e}")


def _check_scope_coverage(
    token_scopes: List[str], required_scopes: List[str]
) -> bool:
    """
    Check if token scopes cover the required scopes.

    Supports wildcards:
    - read:* covers read:SkillDNA, read:PsyDNA, etc.
    - write:* covers write:Goals, write:Evidence, etc.
    """
    # Convert to sets for easier comparison
    token_set = set(token_scopes)
    required_set = set(required_scopes)

    # Check for exact matches first
    if required_set.issubset(token_set):
        return True

    # Check for wildcard matches
    for required in required_set:
        matched = False

        # Check exact match
        if required in token_set:
            matched = True
            continue

        # Check wildcard matches
        if ":" in required:
            prefix, _ = required.split(":", 1)
            wildcard = f"{prefix}:*"
            if wildcard in token_set:
                matched = True
                continue

        # Check universal wildcard
        if "*" in token_set or "read:*" in token_set or "write:*" in token_set:
            matched = True
            continue

        if not matched:
            return False

    return True


def require_consent(
    scopes: List[str],
    namespace: str,
    allow_superuser: bool = False,
) -> Callable:
    """
    Decorator to enforce consent checks on API endpoints.

    Args:
        scopes: Required capability scopes (e.g., ["read:PsyDNA"])
        namespace: Namespace being accessed (e.g., "psy_insights")
        allow_superuser: If True, allow requests with SUPERUSER env var

    Raises:
        ConsentViolation: If consent check fails

    Example:
        @app.get("/api/psydna/{user_id}")
        @require_consent(scopes=["read:PsyDNA"], namespace="psy_insights")
        async def get_psydna(request: Request, user_id: str):
            return {"data": "..."}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request is None:
                request = kwargs.get("request")

            if request is None:
                logger.error("require_consent: No Request object found in arguments")
                raise HTTPException(
                    status_code=500, detail="Internal error: No request context"
                )

            # Extract user_id from path params or query params
            user_id = kwargs.get("user_id") or request.path_params.get(
                "user_id"
            ) or request.query_params.get("user_id")

            if not user_id:
                logger.warning(
                    f"require_consent: No user_id found for namespace {namespace}"
                )
                raise HTTPException(
                    status_code=400, detail="user_id required for consent check"
                )

            # Check for superuser bypass (development only)
            if allow_superuser:
                import os

                if os.getenv("SUPERUSER") == "1":
                    logger.info(
                        f"SUPERUSER bypass for {namespace} (user: {user_id})"
                    )
                    _audit_consent_check(
                        user_id, namespace, scopes, True, "superuser_bypass"
                    )
                    return await func(*args, **kwargs)

            # Extract capability token
            token = _extract_token_from_request(request)
            if not token:
                _audit_consent_check(
                    user_id, namespace, scopes, False, "no_token_provided"
                )
                raise ConsentViolation("No capability token provided", scopes)

            # Verify token signature and expiration
            try:
                payload = verify_capability(token)
            except Exception as e:
                _audit_consent_check(
                    user_id, namespace, scopes, False, f"invalid_token: {str(e)}"
                )
                raise ConsentViolation(f"Invalid token: {str(e)}", scopes)

            # Check expiration
            if is_expired(payload):
                _audit_consent_check(
                    user_id, namespace, scopes, False, "token_expired"
                )
                raise ConsentViolation("Token expired", scopes)

            # Check user_id match
            if payload.get("user_id") != user_id:
                _audit_consent_check(
                    user_id,
                    namespace,
                    scopes,
                    False,
                    f"user_mismatch: token for {payload.get('user_id')}",
                )
                raise ConsentViolation(
                    "Token user_id does not match requested user_id", scopes
                )

            # Check scope coverage
            token_scopes = payload.get("scopes", [])
            if not _check_scope_coverage(token_scopes, scopes):
                _audit_consent_check(
                    user_id,
                    namespace,
                    scopes,
                    False,
                    f"insufficient_scopes: token has {token_scopes}",
                )
                raise ConsentViolation(
                    f"Token scopes {token_scopes} do not cover required scopes {scopes}",
                    scopes,
                )

            # Check revocation status
            cap_id = payload.get("cap_id")
            if cap_id:
                # Query storage to check if revoked
                # For now, we'll skip this check if storage is unavailable
                try:
                    # This would query the ledger for revocation events
                    # Implementation depends on storage.get_capability_status()
                    pass
                except Exception as e:
                    logger.warning(
                        f"Could not check revocation status for {cap_id}: {e}"
                    )

            # All checks passed - audit and proceed
            _audit_consent_check(
                user_id, namespace, scopes, True, None, cap_id
            )

            # Add consent context to request state for downstream use
            if not hasattr(request, "state"):
                request.state = type("State", (), {})()
            request.state.consent_verified = True
            request.state.consent_cap_id = cap_id
            request.state.consent_scopes = token_scopes

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_consent_sync(
    user_id: str,
    required_scopes: List[str],
    token: str,
    namespace: str = "unknown",
) -> bool:
    """
    Synchronous consent check (for non-FastAPI contexts).

    Args:
        user_id: User ID to check consent for
        required_scopes: Required scopes
        token: JWT capability token
        namespace: Namespace being accessed (for audit)

    Returns:
        True if consent granted, False otherwise

    This function audits the check but returns boolean instead of raising.
    """
    try:
        # Verify token
        payload = verify_capability(token)

        # Check expiration
        if is_expired(payload):
            _audit_consent_check(
                user_id, namespace, required_scopes, False, "token_expired"
            )
            return False

        # Check user match
        if payload.get("user_id") != user_id:
            _audit_consent_check(
                user_id, namespace, required_scopes, False, "user_mismatch"
            )
            return False

        # Check scopes
        token_scopes = payload.get("scopes", [])
        if not _check_scope_coverage(token_scopes, required_scopes):
            _audit_consent_check(
                user_id,
                namespace,
                required_scopes,
                False,
                "insufficient_scopes",
            )
            return False

        # Success
        _audit_consent_check(
            user_id, namespace, required_scopes, True, None, payload.get("cap_id")
        )
        return True

    except Exception as e:
        _audit_consent_check(
            user_id, namespace, required_scopes, False, f"error: {str(e)}"
        )
        return False


__all__ = [
    "require_consent",
    "check_consent_sync",
    "ConsentViolation",
]
