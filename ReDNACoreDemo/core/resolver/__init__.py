"""
Resolver subsystem for trait resolution with UCN scoring.

This module provides the canonical resolution pipeline that all
ingestion paths (chat, onboarding, goals) flow through.
"""
from core.resolver.impl import resolve_roundtrip, resolve_traits
from core.resolver.contracts import Evidence, ResolvedTrait, Resolved

__all__ = [
    "resolve_roundtrip",
    "resolve_traits",
    "Evidence",
    "ResolvedTrait",
    "Resolved"
]
