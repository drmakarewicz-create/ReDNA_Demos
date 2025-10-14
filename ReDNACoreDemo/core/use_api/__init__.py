"""
Use API module - Capability-gated external access.

IMPORTANT BOUNDARY:
- Refinement plane (core/vault): Internal vault operations, NO capability required
- Use plane (core/use_api): External read/write/export, capability REQUIRED
"""

from .middleware import CapabilityMiddleware, require_capability, extract_capability_info

__all__ = ["CapabilityMiddleware", "require_capability", "extract_capability_info"]
