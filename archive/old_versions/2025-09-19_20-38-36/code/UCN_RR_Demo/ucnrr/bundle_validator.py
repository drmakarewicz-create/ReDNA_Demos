# ucnrr/bundle_validator.py
from __future__ import annotations
from typing import Dict, Any, Tuple, List

def validate_explorer_bundle(bundle: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not isinstance(bundle, dict):
        return False, ["Bundle is not an object."]
    if bundle.get("schema_version") != "explorer.bundle/1.0":
        errs.append("schema_version must be 'explorer.bundle/1.0'.")
    for req in ["source", "identity", "paths_present", "results"]:
        if req not in bundle:
            errs.append(f"Missing '{req}'.")
    res = bundle.get("results") or {}
    for req in ["ucn", "curiosity", "rr", "meta"]:
        if req not in res:
            errs.append(f"results missing '{req}'.")
    ident = bundle.get("identity") or {}
    if not ident.get("user_id"):
        errs.append("identity.user_id is required.")
    if not ident.get("snapshot_id"):
        errs.append("identity.snapshot_id is required.")
    ok = len(errs) == 0
    return ok, errs