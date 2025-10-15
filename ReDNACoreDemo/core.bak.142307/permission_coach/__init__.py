"""Permission Coach module - Consent and capability mediation."""

from .client import ensure_capability, revoke_capability, PermissionDeniedError, PermissionPendingError
from .permcoach_service import PermissionCoach, audit_user_capabilities

__all__ = [
    "ensure_capability",
    "revoke_capability",
    "PermissionDeniedError",
    "PermissionPendingError",
    "PermissionCoach",
    "audit_user_capabilities",
]
