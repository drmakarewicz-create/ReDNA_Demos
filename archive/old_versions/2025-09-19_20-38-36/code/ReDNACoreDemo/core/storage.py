# ReDNACoreDemo/core/storage.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]  # ReDNACoreDemo/
DATA_DIR = ROOT / "data"
USERS_DIR = DATA_DIR / "users"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
CONFIG_DIR = DATA_DIR / "config"

# File names in each user folder we keep stable:
RESOLVED_FILENAME = "resolved.json"       # final merged view (what Explorer shows)
EVIDENCE_FILENAME = "evidence.json"       # all raw “facts” with provenance
OBS_FILENAME = "observations.json"        # intermediate normalized observations

def ensure_dirs_for_user(user_id: str) -> Dict[str, Path]:
    udir = USERS_DIR / user_id
    udir.mkdir(parents=True, exist_ok=True)
    (CHECKPOINTS_DIR / user_id / "events").mkdir(parents=True, exist_ok=True)
    return {
        "udir": udir,
        "resolved": udir / RESOLVED_FILENAME,
        "evidence": udir / EVIDENCE_FILENAME,
        "observations": udir / OBS_FILENAME,
        "events": CHECKPOINTS_DIR / user_id / "events",
    }

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False))

def event_checkpoint(user_id: str, name: str, payload: Dict[str, Any]) -> Path:
    # Save an event under checkpoints to help with regressions
    epath = ensure_dirs_for_user(user_id)["events"] / f"{name}.json"
    save_json(epath, payload)
    return epath

def read_user_state(user_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    paths = ensure_dirs_for_user(user_id)
    resolved = load_json(paths["resolved"], default={})
    evidence = load_json(paths["evidence"], default={"items": []})
    observations = load_json(paths["observations"], default={"items": []})
    return resolved, evidence, observations

def write_user_state(
    user_id: str,
    resolved: Dict[str, Any],
    evidence: Dict[str, Any],
    observations: Dict[str, Any],
) -> None:
    paths = ensure_dirs_for_user(user_id)
    save_json(paths["resolved"], resolved)
    save_json(paths["evidence"], evidence)
    save_json(paths["observations"], observations)