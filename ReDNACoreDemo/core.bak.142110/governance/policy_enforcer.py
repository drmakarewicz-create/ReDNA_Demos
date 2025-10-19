"""
Policy Enforcement Layer - Phase 6

Validates capability scopes against policy rules.

Policy rules:
- No auto-writes to PsyDNA without explicit consent
- Export requires explicit export:allowed scope
- Aggregate-only data cannot be exported raw
- Remote access blocked for sensitive namespaces by default

Integration with consent middleware for enforcement.
"""

from typing import List, Dict, Any, Optional
from .privacy_overlay import check_privacy_level, PrivacyLevel


class PolicyViolation(Exception):
    """Raised when a policy rule is violated."""

    pass


class PolicyEnforcer:
    """Policy enforcement engine."""

    def __init__(self):
        """Initialize policy enforcer."""
        self.rules_enabled = True

    def check_write_policy(
        self, namespace: str, scopes: List[str], data_policy: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if write operation is allowed by policy.

        Args:
            namespace: DNA namespace being written to
            scopes: Capability scopes
            data_policy: Data policy from capability

        Returns:
            True if allowed

        Raises:
            PolicyViolation: If policy violated
        """
        privacy_level = check_privacy_level(namespace)

        # Highly sensitive namespaces require explicit write scope
        if privacy_level == PrivacyLevel.HIGHLY_SENSITIVE:
            required_scope = f"write:{namespace}"
            if required_scope not in scopes and "write:*" not in scopes:
                raise PolicyViolation(
                    f"Writing to {namespace} requires explicit {required_scope} scope"
                )

        return True

    def check_export_policy(
        self, scopes: List[str], data_policy: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if export operation is allowed.

        Args:
            scopes: Capability scopes
            data_policy: Data policy from capability

        Returns:
            True if allowed

        Raises:
            PolicyViolation: If export not allowed
        """
        # Check for explicit export permission
        if "export" not in scopes and "export:allowed" not in scopes:
            if data_policy and not data_policy.get("export", False):
                raise PolicyViolation("Export not allowed by data policy")

        # Check aggregate-only constraint
        if data_policy and data_policy.get("aggregate_only", False):
            raise PolicyViolation(
                "Cannot export raw data - aggregate_only policy enforced"
            )

        return True

    def check_remote_access_policy(
        self, namespace: str, scopes: List[str], remote: bool = False
    ) -> bool:
        """
        Check if remote access is allowed.

        Args:
            namespace: DNA namespace
            scopes: Capability scopes
            remote: Whether request is from remote host

        Returns:
            True if allowed

        Raises:
            PolicyViolation: If remote access not allowed
        """
        if not remote:
            return True

        privacy_level = check_privacy_level(namespace)

        # Sensitive and highly sensitive require explicit remote_ok scope
        if privacy_level in (PrivacyLevel.SENSITIVE, PrivacyLevel.HIGHLY_SENSITIVE):
            if "remote_ok" not in scopes:
                raise PolicyViolation(
                    f"Remote access to {namespace} requires remote_ok scope"
                )

        return True

    def validate_capability(
        self,
        scopes: List[str],
        operation: str,
        namespace: Optional[str] = None,
        data_policy: Optional[Dict[str, Any]] = None,
        remote: bool = False,
    ) -> bool:
        """
        Validate capability against all policy rules.

        Args:
            scopes: Capability scopes
            operation: Operation type (read, write, export)
            namespace: DNA namespace (if applicable)
            data_policy: Data policy from capability
            remote: Whether request is from remote host

        Returns:
            True if all policies pass

        Raises:
            PolicyViolation: If any policy violated
        """
        if not self.rules_enabled:
            return True

        if operation == "write" and namespace:
            self.check_write_policy(namespace, scopes, data_policy)

        if operation == "export":
            self.check_export_policy(scopes, data_policy)

        if namespace and remote:
            self.check_remote_access_policy(namespace, scopes, remote)

        return True


__all__ = ["PolicyEnforcer", "PolicyViolation"]
