from __future__ import annotations
import json
import pathlib
from typing import List, Dict, Any

_MAP_PATH = pathlib.Path(__file__).with_name("trait_id_map.json")
_IDMAP = json.loads(_MAP_PATH.read_text()) if _MAP_PATH.exists() else {}


def to_canonical(trait_id: str) -> str:
    """
    Map an extracted trait ID (e.g., 'attributes.physical.eye_color')
    to its canonical form (e.g., 'PaDNA.EyeDNA.IrisColor').

    Returns the canonical ID if mapped, otherwise returns the original ID.
    """
    return _IDMAP.get(trait_id, trait_id)


def normalize_evidence(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert a list of evidence items to use canonical trait IDs.

    This bridges the gap between evidence extraction (which uses 'attributes.*')
    and trait resolution (which uses 'BasicDNA.*', 'PaDNA.*', etc.).

    Args:
        evidence: List of evidence dicts with 'trait_id' keys

    Returns:
        List of evidence dicts with canonical trait IDs
    """
    out: List[Dict[str, Any]] = []
    for ev in evidence:
        tid = ev.get("trait_id")
        if tid:
            canonical_tid = to_canonical(tid)
            ev = {**ev, "trait_id": canonical_tid}
        out.append(ev)
    return out
