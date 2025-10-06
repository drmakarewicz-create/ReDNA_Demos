# ReDNACoreDemo/core/schemas.py
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, TypedDict

class EvidenceItem(TypedDict, total=False):
    trait: str                 # "PaDNA.EyeDNA.IrisColor"
    value: Any                 # "Blue"
    ucn: float                 # 0..100 confidence (as %)
    source: str                # "ingest:explorer_text_local@120"
    reasons: List[str]         # human-readable reasons
    flags: List[str]           # e.g., ["conflict", "low_evidence"]
    when: Optional[str]        # ISO time
    kind: Literal["self_report", "photo", "model_infer", "legacy", "other"]

class ObservationItem(TypedDict, total=False):
    trait: str
    value: Any
    ucn: float
    provenance: EvidenceItem   # link back to one piece of evidence

class BundleIn(TypedDict, total=False):
    user_id: str
    items: List[EvidenceItem]  # UCN/RR -> Core payload

class ResolveOut(TypedDict, total=False):
    resolved: Dict[str, Any]   # flattened trait map
    priorities: Dict[str, float]  # curiosity/system-need score 0..1