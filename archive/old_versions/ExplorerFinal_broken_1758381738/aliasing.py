# ExplorerFinal/aliasing.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os

try:
    import yaml
except Exception:
    yaml = None

# Import the whole module defensively so we can probe for whichever
# function names your local bridge exposes.
import bridge as _bridge  # type: ignore

ROOT = Path(__file__).resolve().parent
ALIASES_FILE = os.getenv("ALIASES_FILE", str(ROOT / "aliases.yaml"))

def _load_yaml(path: str | Path) -> Dict[str, Any]:
    if yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data
    except Exception:
        return {}

def load_alias_map() -> Dict[str, List[str]]:
    data = _load_yaml(ALIASES_FILE)
    if isinstance(data, dict) and "aliases" in data and isinstance(data["aliases"], dict):
        out: Dict[str, List[str]] = {}
        for k, v in data["aliases"].items():
            if isinstance(v, list):
                out[k] = [str(x) for x in v]
            elif isinstance(v, str):
                out[k] = [v]
        return out
    return {}

def _bridge_get_current_value(user_id: str, path: str) -> Dict[str, Any]:
    """
    Try several possible function names to read the current value from Core.
    Returns {} on failure.
    """
    for fn_name in (
        "get_current_value",
        "fetch_current_value",
        "read_current_value",
        "core_get_current_value",
    ):
        fn = getattr(_bridge, fn_name, None)
        if callable(fn):
            try:
                return fn(user_id, path) or {}
            except Exception:
                pass
    return {}

def _bridge_write_event(user_id: str, path: str, new_value: Any,
                        evidence: Dict[str, Any], provenance: str,
                        ai_enabled: bool) -> Dict[str, Any]:
    """
    Try several possible function names to write a change event to Core.
    """
    for fn_name in (
        "write_event",
        "save_event",
        "save_change",
        "post_change",
    ):
        fn = getattr(_bridge, fn_name, None)
        if callable(fn):
            try:
                return fn(user_id, path, new_value, evidence, provenance, ai_enabled) or {}
            except Exception:
                pass
    return {}

def resolve_with_aliases(user_id: str, canonical_path: str) -> Tuple[Optional[Any], Dict[str, Any], Optional[str]]:
    """
    Try canonical path; if empty, try each alias until one yields a value.
    Returns (value, full_result_dict, source_path_used_or_None)
    """
    # Canonical first
    res = _bridge_get_current_value(user_id, canonical_path) or {}
    val = res.get("value", None)
    if val not in (None, ""):
        return val, res, None

    # Then aliases
    alias_map = load_alias_map()
    for a in alias_map.get(canonical_path, []):
        r = _bridge_get_current_value(user_id, a) or {}
        av = r.get("value", None)
        if av not in (None, ""):
            return av, r, a

    return None, res, None

def promote_alias_value(user_id: str,
                        canonical_path: str,
                        source_path: str,
                        value: Any,
                        evidence: Dict[str, Any],
                        ai_enabled: bool) -> Dict[str, Any]:
    """
    Write a new change event at the canonical path using the value found at source_path.
    """
    provenance = f"explorer-final::promoted-from-alias::{source_path}"
    return _bridge_write_event(
        user_id=user_id,
        path=canonical_path,
        new_value=value,
        evidence=evidence,
        provenance=provenance,
        ai_enabled=ai_enabled,
    ) or {}