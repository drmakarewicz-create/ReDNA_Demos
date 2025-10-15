"""
Use API Middleware - Capability Verification

This middleware enforces capability checks on all /use/* endpoints.

IMPORTANT BOUNDARY:
- /refine/* routes: NO capability required (vault-internal operations)
- /use/* routes: Capability REQUIRED (external read/write/export)

Default deny: All /use/* requests denied without valid capability.
"""

import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Callable, Optional
import re

from ..policy.policy_engine import evaluate_capability, PolicyViolation

logger = logging.getLogger(__name__)


class CapabilityMiddleware:
    """
    Middleware for capability verification on /use/* routes.

    Extracts JWT from Authorization header, evaluates capability,
    and denies request if capability is invalid or insufficient.
    """

    def __init__(self, app):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
        """
        self.app = app

    async def __call__(self, scope, receive, send):
        """
        ASGI middleware handler.

        Args:
            scope: ASGI scope
            receive: ASGI receive channel
            send: ASGI send channel
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Check if this is a /use/* route (requires capability)
        if path.startswith("/core/use/") or path.startswith("/use/"):
            logger.debug(f"Capability check required for: {path}")

            try:
                # Extract JWT from Authorization header
                auth_header = request.headers.get("Authorization")
                if not auth_header:
                    logger.warning(f"Missing Authorization header for {path}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing Authorization header. All /use/* endpoints require a valid capability token."
                    )

                # Parse "Bearer <jwt>"
                parts = auth_header.split()
                if len(parts) != 2 or parts[0].lower() != "bearer":
                    logger.warning(f"Malformed Authorization header for {path}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Malformed Authorization header. Expected: 'Bearer <jwt>'"
                    )

                jwt_token = parts[1]

                # Infer requested scope from path
                # Pattern: /core/use/{namespace}/{operation}
                # Example: /core/use/SkillDNA/read → scope: "read:SkillDNA"
                scope_match = re.match(r"/(?:core/)?use/([^/]+)/([^/]+)", path)
                if not scope_match:
                    logger.warning(f"Cannot infer scope from path: {path}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot infer scope from path: {path}"
                    )

                namespace = scope_match.group(1)
                operation = scope_match.group(2)
                requested_scope = f"{operation}:{namespace}"

                # Detect remote request (non-localhost)
                client_host = request.client.host if request.client else "unknown"
                remote_request = client_host not in ["127.0.0.1", "localhost", "::1"]

                logger.debug(f"Evaluating capability: scope={requested_scope}, remote={remote_request}, client={client_host}")

                # Evaluate capability
                result = evaluate_capability(
                    jwt_token=jwt_token,
                    requested_scope=requested_scope,
                    requested_operation=operation,
                    remote_request=remote_request,
                )

                if not result.get("allowed"):
                    # DENY
                    reason = result.get("reason", "Unknown policy violation")
                    logger.warning(f"❌ Capability check DENIED: {path} - {reason}")

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Capability check failed: {reason}"
                    )

                # ALLOW - attach capability info to request state for downstream use
                request.state.capability = result
                logger.info(f"✅ Capability check PASSED: {path} (cap_id={result.get('cap_id')})")

            except HTTPException:
                # Re-raise HTTP exceptions
                raise
            except Exception as e:
                logger.error(f"Unexpected error in capability middleware: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Internal error during capability check: {e}"
                )

        # Proceed to next middleware/endpoint
        await self.app(scope, receive, send)


def require_capability(
    scope: str,
    operation: str = "read",
    allow_export: bool = False
):
    """
    Decorator for explicit capability requirements.

    Use this to annotate coach endpoints that need specific capabilities.

    Args:
        scope: Required scope (e.g., "SkillDNA", "ProfDNA")
        operation: Operation type (read/write/export)
        allow_export: Whether export is allowed

    Returns:
        Decorator function

    Example:
        @require_capability(scope="SkillDNA", operation="read")
        async def get_skill_data(request: Request):
            # Capability already verified by middleware
            cap_info = request.state.capability
            user_id = cap_info["user_id"]
            ...
    """
    def decorator(func: Callable):
        async def wrapper(request: Request, *args, **kwargs):
            # Check if capability was verified by middleware
            if not hasattr(request.state, "capability"):
                logger.error(f"Capability middleware did not run for {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Capability middleware not configured"
                )

            cap_info = request.state.capability

            # Verify scope matches
            scope_used = cap_info.get("scope_used", "")
            expected_scope = f"{operation}:{scope}"

            if scope_used != expected_scope and not scope_used.endswith(":*"):
                logger.warning(f"Scope mismatch: expected={expected_scope}, used={scope_used}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient scope: {scope_used} does not cover {expected_scope}"
                )

            # Check export permission if needed
            if allow_export and operation == "export":
                # Export capability already checked by policy engine
                pass

            # Proceed to endpoint
            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


def extract_capability_info(request: Request) -> Optional[dict]:
    """
    Extract capability info from request state.

    Args:
        request: FastAPI Request object

    Returns:
        Capability info dict, or None if not present

    Example:
        cap_info = extract_capability_info(request)
        if cap_info:
            user_id = cap_info["user_id"]
            grantee_id = cap_info["grantee_id"]
    """
    return getattr(request.state, "capability", None)
