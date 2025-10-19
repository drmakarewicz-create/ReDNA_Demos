# ReDNACoreDemo/core/traits/__init__.py
"""
Trait ID canonicalization and inference system.
Northstar Phase 2: Evidence → Canonical → Resolve → Infer → Re-Resolve
"""

from .trait_id_mapper import to_canonical, normalize_evidence
from .inference_engine import run_inference

__all__ = ["to_canonical", "normalize_evidence", "run_inference"]
