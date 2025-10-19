"""
Canonical contracts for the resolver subsystem.

This module defines the exact schemas for:
- Evidence: normalized input to the resolver
- ResolvedTrait: output from resolution
- Resolved: complete snapshot of resolved traits

These contracts lock the interface between pipeline stages.
"""
from __future__ import annotations
from typing import TypedDict, Literal, Dict, Any, List, Optional


# Value types for trait values
class ValueEnum(TypedDict, total=False):
    enum: str


class ValueNumber(TypedDict, total=False):
    number: float


class ValueText(TypedDict, total=False):
    text: str


# Union type for values
Value = ValueEnum | ValueNumber | ValueText


class Evidence(TypedDict, total=False):
    """
    Canonical evidence input to the resolver.

    Fields:
        trait_id: Canonical trait ID (e.g., "PaDNA.EyeDNA.IrisColor")
        value: One of {enum|number|text}
        source: Origin ("chat", "onboarding", "goal", etc.)
        ts: ISO8601 timestamp with Z suffix
        provenance: Optional provenance string (e.g., "inference:rule_id")
        ucn_prior: Optional seed confidence (0..1)
    """
    trait_id: str
    value: Dict[str, Any]  # One of {enum|number|text}
    source: str
    ts: str
    provenance: str
    ucn_prior: float


class ResolvedTrait(TypedDict, total=False):
    """
    A single resolved trait with confidence and metadata.

    Fields:
        value: Chosen value
        ucn: Uncertainty Confidence Number (0..1)
        sources: List of evidence source tags
        status: Resolution status
        last_updated: ISO8601 timestamp
    """
    value: Dict[str, Any]
    ucn: float
    sources: List[str]
    status: Literal["resolved", "unknown", "conflict", "inferred"]
    last_updated: str


# Complete resolved snapshot
Resolved = Dict[str, ResolvedTrait]
