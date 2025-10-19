"""Learning jobs for the conflict resolver."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict

from .calibration import CalibrationManager
from .storage import _user_log_path


LEARNING_CACHE = Path(__file__).resolve().parents[3] / "data" / "system" / "conflict_learning_snapshot.json"
LEARNING_CACHE.parent.mkdir(parents=True, exist_ok=True)


def run_nightly_learning(user_ids: list[str]) -> Dict[str, Dict[str, float]]:
    calibration = CalibrationManager()
    for user_id in user_ids:
        log_path = _user_log_path(user_id)
        if not log_path.exists():
            continue
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                path = record.get("path") or "generic"
                outcome = record.get("outcome") or {}
                if outcome.get("resolver") == "auto_merge":
                    calibration.record_outcome(user_id, path, "confirmed")
                elif record.get("status") == "denied":
                    calibration.record_outcome(user_id, path, "contradicted")
    snapshot = _build_snapshot(calibration)
    LEARNING_CACHE.write_text(json.dumps(snapshot, indent=2))
    return snapshot


def get_learning_snapshot() -> Dict[str, Dict]:
    calibration = CalibrationManager()
    if LEARNING_CACHE.exists():
        try:
            data = json.loads(LEARNING_CACHE.read_text())
            if data.get("generated_at"):
                return data
        except json.JSONDecodeError:
            pass
    snapshot = _build_snapshot(calibration)
    LEARNING_CACHE.write_text(json.dumps(snapshot, indent=2))
    return snapshot


def _build_snapshot(calibration: CalibrationManager) -> Dict[str, Dict[str, float]]:
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "weights": calibration.snapshot(),
    }
