# ucnrr/core_adapter.py
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Tuple

def _normalize_path(ev: Dict[str, Any], bucket: str) -> List[str]:
    if "dna_path" in ev and isinstance(ev["dna_path"], list) and ev["dna_path"]:
        return [str(x) for x in ev["dna_path"]]
    dna = str(ev.get("dna", bucket))
    return [p.strip() for p in dna.split(".") if p.strip()] or [dna]

def iter_core_evidence(snapshot: Dict[str, Any]) -> Iterable[Tuple[List[str], Dict[str, Any]]]:
    """
    Yield (dna_path, evidence_dict) from a Core snapshot.
    Prefers 'dna_path' (schema ≥3.1). Falls back to splitting evidence['dna'] on '.'.
    """
    data = snapshot.get("data") or {}
    for bucket, rows in data.items():
        for ev in rows or []:
            path = _normalize_path(ev, bucket)
            yield (path, ev)