# ExplorerFinal/persist.py
"""
Persistence helpers for ExplorerFinal.
- Writes change_event, UCN/RR result, and Core plan to:
    Core:   ReDNACoreDemo/data/checkpoints/<user>/events/<ts>.json
    UCN_RR: UCN_RR_Demo/data/users/<user>/Inbox/<ts>_change.json
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent  # project root
CORE_DIR = ROOT / "ReDNACoreDemo" / "data" / "checkpoints"
UCNRR_DIR = ROOT / "UCN_RR_Demo" / "data" / "users"


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    tmp.replace(path)


def persist_everything(user_id: str,
                       change_event: Dict[str, Any],
                       ucnrr_result: Dict[str, Any],
                       core_plan: Dict[str, Any]) -> Dict[str, str]:
    """
    Save to:
      Core:   .../checkpoints/<user>/events/<ts>.json
      UCN_RR: .../users/<user>/Inbox/<ts>_change.json
    Returns dict of written file paths (strings).
    """
    ts = change_event.get("ts") or int(time.time())
    ts_s = str(ts)

    core_event_dir = CORE_DIR / user_id / "events"
    core_path = core_event_dir / f"{ts_s}.json"
    core_payload = {
        "user": user_id,
        "change_event": change_event,
        "ucnrr_result": ucnrr_result,
        "core_plan": core_plan,
        "written_at": int(time.time())
    }
    _atomic_write(core_path, core_payload)

    inbox_dir = UCNRR_DIR / user_id / "Inbox"
    ucnrr_path = inbox_dir / f"{ts_s}_change.json"
    ucnrr_payload = {
        "user": user_id,
        "change_event": change_event,
        "ucnrr_result": ucnrr_result,
        "written_at": int(time.time())
    }
    _atomic_write(ucnrr_path, ucnrr_payload)

    return {"core": str(core_path), "ucnrr": str(ucnrr_path)}