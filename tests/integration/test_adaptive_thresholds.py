"""
Integration checks for adaptive promotion thresholds.

Requires live Core service.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional

import pytest
import requests

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8004")
REDNA_HOME = Path(os.environ.get("REDNA_HOME", str(Path.home() / ".redna"))).expanduser()
POLICY_DIR = REDNA_HOME / "policy"
POLICY_HISTORY_PATH = POLICY_DIR / "promotion_history.jsonl"
POLICY_LEARNED_PATH = POLICY_DIR / "learned_thresholds.json"


@pytest.fixture(scope="module")
def live_core():
    try:
        resp = requests.get(f"{CORE_BASE}/health", timeout=3)
        resp.raise_for_status()
    except requests.RequestException:
        pytest.skip(f"Core service not reachable at {CORE_BASE}")
    return CORE_BASE


def _load_history_lines(path: Path) -> list[Dict[str, object]]:
    out: list[Dict[str, object]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _write_history(entries: list[Dict[str, object]]) -> None:
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    with POLICY_HISTORY_PATH.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _round_trip_get_policies() -> Dict[str, Dict[str, object]]:
    resp = requests.get(f"{CORE_BASE}/core/api/policies", timeout=5)
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("policies", {})


def test_adaptive_thresholds_learning_cycle(live_core):
    # Backup existing files
    original_history = POLICY_HISTORY_PATH.read_text(encoding="utf-8") if POLICY_HISTORY_PATH.exists() else None
    original_learned = POLICY_LEARNED_PATH.read_text(encoding="utf-8") if POLICY_LEARNED_PATH.exists() else None

    try:
        if POLICY_LEARNED_PATH.exists():
            POLICY_LEARNED_PATH.unlink()

        ts = datetime.now(timezone.utc)
        seed_entries = []
        for idx in range(12):
            rr_value = 720 + idx  # 720..731
            curiosity = 0.10 + (idx * 0.01)
            entry = {
                "ts": (ts.replace(microsecond=0) + idx * timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
                "user_id": f"seed_{idx}",
                "trait_id": "BehaviorDNA.Sleep.Chronotype",
                "rr": rr_value,
                "base_rr": 780.0,
                "decision": "promote",
                "curiosity": curiosity,
                "value": "morning",
                "why": "seeded history",
                "source": "test_seed",
            }
            seed_entries.append(entry)

        _write_history(seed_entries)

        resp = requests.post(f"{CORE_BASE}/core/api/learn_thresholds", timeout=10)
        resp.raise_for_status()
        learn_payload = resp.json()
        updated = learn_payload.get("updated", {})
        chrono_update = updated.get("BehaviorDNA.Sleep.Chronotype")
        assert chrono_update, "Chronotype not updated by learner"
        new_threshold = float(chrono_update.get("new") or 0.0)
        assert new_threshold < 780.0, f"Expected learned threshold below base, got {new_threshold}"

        policies = _round_trip_get_policies()
        chrono_policy = policies.get("BehaviorDNA.Sleep.Chronotype")
        assert chrono_policy is not None
        assert float(chrono_policy.get("learned_rr") or 0.0) == pytest.approx(new_threshold)

        # Ensure policy learner data survives subsequent ingest call
        toggle_resp = requests.post(
            f"{CORE_BASE}/core/api/debug/set_toggle",
            json={"trait": "CHRONO", "enable": True, "rr_min": 780},
            timeout=5,
        )
        toggle_resp.raise_for_status()

        user_id = f"dbg_threshold_{int(time.time())}"
        ingest_resp = requests.post(
            f"{CORE_BASE}/core/api/ingest_text",
            json={"user_id": user_id, "text": "I am a morning person, up before sunrise.", "source": "adaptive_test"},
            timeout=15,
        )
        ingest_resp.raise_for_status()
        ingest_payload = ingest_resp.json()
        assert ingest_payload.get("success") is True or ingest_payload.get("ok") is True

        history_after = _load_history_lines(POLICY_HISTORY_PATH)
        assert history_after, "Promotion history should not be empty after ingest"
        last_record = history_after[-1]
        assert last_record.get("trait_id") == "BehaviorDNA.Sleep.Chronotype"
        assert last_record.get("decision") in {"promote", "skip"}
        if last_record.get("decision") == "promote":
            eff = float(last_record.get("effective_rr") or 0.0)
            assert eff == pytest.approx(new_threshold)
    finally:
        if original_history is None:
            if POLICY_HISTORY_PATH.exists():
                POLICY_HISTORY_PATH.unlink()
        else:
            POLICY_HISTORY_PATH.write_text(original_history, encoding="utf-8")

        if original_learned is None:
            if POLICY_LEARNED_PATH.exists():
                POLICY_LEARNED_PATH.unlink()
        else:
            POLICY_LEARNED_PATH.write_text(original_learned, encoding="utf-8")
