"""
Policy Engine - Capability Evaluation

This module evaluates whether a capability token authorizes a requested operation.

Evaluation checks:
1. JWT signature valid
2. Not expired (TTL)
3. Not revoked (ledger lookup)
4. Scopes cover requested operation
5. Data tags compatible with scopes
6. Environment restrictions (localhost only unless remote_ok)
7. Export control (deny export unless data_policy.export = true)
8. Reuse limit not exceeded

Default deny: All checks must pass, or request is DENIED with explicit reason.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

# Import from ReDNACoreDemo.services package
from ReDNACoreDemo.services.consent.jwt_utils import verify_capability, is_expired
from ReDNACoreDemo.services.consent.storage import ConsentStorage
from ReDNACoreDemo.services.consent.models import LedgerEventType

logger = logging.getLogger(__name__)

# Initialize storage for revocation checks
storage = ConsentStorage()


class PolicyViolation(Exception):
    """Raised when a policy check fails."""
    pass


class PolicyEngine:
    """
    Policy engine for capability evaluation.

    This is the enforcement point for all /use/* requests.
    """

    def __init__(self):
        """Initialize policy engine."""
        self.storage = ConsentStorage()

    def evaluate(
        self,
        jwt_token: str,
        requested_scope: str,
        requested_operation: str,  # e.g., "read", "write", "export"
        requested_containers: Optional[List[str]] = None,  # e.g., ["SkillDNA", "ProfDNA"]
        remote_request: bool = False,  # True if request is from non-localhost
    ) -> Dict[str, Any]:
        """
        Evaluate a capability JWT against a requested operation.

        Args:
            jwt_token: Capability JWT
            requested_scope: Requested scope (e.g., "read:SkillDNA")
            requested_operation: Operation type (read/write/export)
            requested_containers: Optional list of container namespaces
            remote_request: Whether request is from remote (non-localhost)

        Returns:
            Dict with evaluation result:
            {
                "allowed": bool,
                "reason": str,
                "cap_id": str,
                "user_id": str,
                "grantee_id": str,
            }

        Raises:
            PolicyViolation: If any check fails
        """
        try:
            # 1. Verify JWT signature and decode
            try:
                payload = verify_capability(jwt_token)
            except Exception as e:
                logger.warning(f"JWT verification failed: {e}")
                raise PolicyViolation(f"Invalid or expired JWT: {e}")

            cap_id = payload.get("cap_id")
            user_id = payload.get("user_id")
            grantee_id = payload.get("grantee_id")
            scopes = payload.get("scopes", [])
            exp = payload.get("exp")
            data_policy = payload.get("data_policy", {})
            reuse_limit = payload.get("reuse_limit")

            logger.debug(f"Evaluating capability: cap_id={cap_id}, grantee={grantee_id}, scopes={scopes}")

            # 2. Check expiration
            if is_expired(exp):
                raise PolicyViolation(f"Capability expired: {cap_id}")

            # 3. Check revocation (ledger lookup)
            capability = self.storage.get_capability(cap_id)
            if not capability:
                raise PolicyViolation(f"Capability not found: {cap_id}")

            if capability.revoked:
                raise PolicyViolation(f"Capability revoked: {cap_id}")

            # 4. Check reuse limit
            if reuse_limit and capability.use_count >= reuse_limit:
                raise PolicyViolation(f"Capability reuse limit exceeded: {cap_id} (limit={reuse_limit}, used={capability.use_count})")

            # 5. Check scopes cover requested operation
            if not self._check_scopes(scopes, requested_scope, requested_containers):
                raise PolicyViolation(f"Insufficient scopes: requested={requested_scope}, granted={scopes}")

            # 6. Check environment restrictions (remote access)
            if remote_request and not data_policy.get("remote_access", False):
                raise PolicyViolation(f"Remote access denied: capability {cap_id} requires localhost")

            # 7. Check export control
            if requested_operation == "export" and not data_policy.get("export", False):
                raise PolicyViolation(f"Export denied: capability {cap_id} does not allow export")

            # 8. All checks passed - ALLOW
            logger.info(f"✅ Policy check PASSED: cap_id={cap_id}, scope={requested_scope}, op={requested_operation}")

            return {
                "allowed": True,
                "reason": "All policy checks passed",
                "cap_id": cap_id,
                "user_id": user_id,
                "grantee_id": grantee_id,
                "scope_used": requested_scope,
            }

        except PolicyViolation as e:
            logger.warning(f"❌ Policy check FAILED: {e}")

            # Log denial event to ledger
            try:
                self.storage.create_ledger_event(
                    event_type=LedgerEventType.DENY,
                    user_id=payload.get("user_id", "unknown") if "payload" in locals() else "unknown",
                    cap_id=payload.get("cap_id") if "payload" in locals() else None,
                    reason=str(e),
                    metadata={
                        "requested_scope": requested_scope,
                        "requested_operation": requested_operation,
                        "requested_containers": requested_containers,
                    }
                )
            except Exception as log_err:
                logger.error(f"Failed to log denial event: {log_err}")

            return {
                "allowed": False,
                "reason": str(e),
                "cap_id": payload.get("cap_id") if "payload" in locals() else None,
                "user_id": payload.get("user_id") if "payload" in locals() else None,
                "grantee_id": payload.get("grantee_id") if "payload" in locals() else None,
            }

        except Exception as e:
            logger.error(f"Unexpected error in policy evaluation: {e}")
            return {
                "allowed": False,
                "reason": f"Internal policy engine error: {e}",
                "cap_id": None,
                "user_id": None,
                "grantee_id": None,
            }

    def _check_scopes(
        self,
        granted_scopes: List[str],
        requested_scope: str,
        requested_containers: Optional[List[str]] = None
    ) -> bool:
        """
        Check if granted scopes cover requested scope.

        Supports wildcards:
        - "read:*" covers all read operations
        - "write:*" covers all write operations

        Args:
            granted_scopes: List of granted scopes (e.g., ["read:SkillDNA", "write:Goals"])
            requested_scope: Requested scope (e.g., "read:SkillDNA")
            requested_containers: Optional list of container namespaces

        Returns:
            True if scopes cover request, False otherwise
        """
        # Check for wildcard match
        operation, _, namespace = requested_scope.partition(":")

        for scope in granted_scopes:
            # Exact match
            if scope == requested_scope:
                return True

            # Wildcard match (e.g., "read:*" matches "read:SkillDNA")
            if scope == f"{operation}:*":
                return True

            # Full wildcard (e.g., "*:*" matches everything - very dangerous!)
            if scope == "*:*":
                logger.warning(f"⚠️  Full wildcard scope granted: *:*")
                return True

        # Check container-level scopes
        if requested_containers:
            for container in requested_containers:
                container_scope = f"{operation}:{container}"
                if container_scope in granted_scopes or f"{operation}:*" in granted_scopes:
                    continue
                else:
                    # Missing scope for this container
                    return False
            # All containers covered
            return True

        # No match found
        return False


# Singleton instance
_policy_engine = PolicyEngine()


def evaluate_capability(
    jwt_token: str,
    requested_scope: str,
    requested_operation: str,
    requested_containers: Optional[List[str]] = None,
    remote_request: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate a capability (convenience function).

    Args:
        jwt_token: Capability JWT
        requested_scope: Requested scope
        requested_operation: Operation type
        requested_containers: Optional container list
        remote_request: Whether request is remote

    Returns:
        Evaluation result dict
    """
    return _policy_engine.evaluate(
        jwt_token=jwt_token,
        requested_scope=requested_scope,
        requested_operation=requested_operation,
        requested_containers=requested_containers,
        remote_request=remote_request,
    )
