"""Self-report calibration utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple


CALIBRATION_PATH = Path(__file__).resolve().parents[3] / "data" / "system" / "self_report_calibration.json"
CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)

MIN_WEIGHT = 0.20
MAX_WEIGHT = 0.70


def _load_calibration() -> Dict[str, Dict[str, Dict[str, float]]]:
    if CALIBRATION_PATH.exists():
        try:
            return json.loads(CALIBRATION_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"users": {}}


def _save_calibration(payload: Dict[str, Dict]) -> None:
    CALIBRATION_PATH.write_text(json.dumps(payload, indent=2))


@dataclass
class CalibrationStats:
    trust: float = 0.5
    samples: int = 0

    def update(self, outcome: str) -> None:
        if outcome == "confirmed":
            self.trust = min(1.0, self.trust + 0.05)
        elif outcome == "contradicted":
            self.trust = max(0.0, self.trust - 0.05)
        elif outcome == "pending":
            self.trust = max(0.0, min(1.0, self.trust))
        self.samples += 1

    def weight(self) -> float:
        return MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * self.trust


class CalibrationManager:
    """Manage per-user, per-domain self-report calibration weights."""

    def __init__(self) -> None:
        self._state = _load_calibration()

    def _key(self, user_id: str, domain: str) -> Tuple[Dict, str]:
        users = self._state.setdefault("users", {})
        user_entry = users.setdefault(user_id, {})
        return user_entry, domain

    def get_weight(self, user_id: str, domain: str) -> float:
        user_entry, key = self._key(user_id, domain)
        stats = user_entry.get(key)
        if not stats:
            return 0.40
        trust = float(stats.get("trust", 0.5))
        return MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * trust

    def record_outcome(self, user_id: str, domain: str, outcome: str) -> None:
        user_entry, key = self._key(user_id, domain)
        stats_dict = user_entry.setdefault(key, {"trust": 0.5, "samples": 0})
        stats = CalibrationStats(trust=float(stats_dict.get("trust", 0.5)), samples=int(stats_dict.get("samples", 0)))
        stats.update(outcome)
        stats_dict["trust"] = stats.trust
        stats_dict["samples"] = stats.samples
        _save_calibration(self._state)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {
            user_id: {domain: float(meta.get("trust", 0.5)) for domain, meta in domains.items()}
            for user_id, domains in self._state.get("users", {}).items()
        }

