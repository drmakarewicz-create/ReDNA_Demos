from __future__ import annotations
from typing import Dict, Any, Tuple, List

REQUIRED_TOP = ["schema_version","source","identity","results"]

def validate_bundle(b: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    for k in REQUIRED_TOP:
        if k not in b:
            errs.append(f"Missing top-level key: {k}")

    if "identity" in b:
        if "user_id" not in b["identity"]: errs.append("identity.user_id required")
        if "snapshot_id" not in b["identity"]: errs.append("identity.snapshot_id required")

    res = b.get("results", {})
    ucn = res.get("ucn", {})
    per = ucn.get("per_dna", {})
    desc = res.get("descriptors", {})

    if not isinstance(per, dict): errs.append("results.ucn.per_dna must be an object")
    if not isinstance(desc, dict): errs.append("results.descriptors must be an object")

    return (len(errs) == 0, errs)