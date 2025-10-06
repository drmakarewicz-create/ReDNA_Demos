# UCN_RR_Demo/validator.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

def validate_explorer_delta(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not isinstance(payload, dict):
        return False, ["Delta must be an object"]
    if payload.get("schema_version") not in ("explorer.delta/1.0", "explorer.delta/1"):
        errs.append("schema_version must be 'explorer.delta/1.0'")
    sug = payload.get("suggested_evidence")
    if not isinstance(sug, list):
        errs.append("suggested_evidence must be a list")
        return False, errs
    for i, row in enumerate(sug):
        if not isinstance(row, dict):
            errs.append(f"suggested_evidence[{i}] must be an object")
            continue
        if "dna_path" not in row:
            errs.append(f"suggested_evidence[{i}] missing dna_path")
        # value optional (string notes are also allowed in stub), confidence/weight optional
    return (len(errs) == 0), errs