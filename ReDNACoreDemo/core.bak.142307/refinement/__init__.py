"""
Trait Refinement — Probabilistic Trait Truthing

Ingests coach proposals, reconciles contradictions vs corroborations,
calibrates confidence → UCN, updates RR, and writes provenance-rich records.
"""

from .refinement_resolver import RefinementResolver, RefinementOutcome, create_resolver

__all__ = ["RefinementResolver", "RefinementOutcome", "create_resolver"]
