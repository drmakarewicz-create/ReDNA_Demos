from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from fastapi.testclient import TestClient

from ReDNACoreDemo.core import hc_human_intel


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _create_sample_telemetry(data_root: Path, user_id: str = "USER1") -> Tuple[Path, Path]:
    """Create synthetic empathy + curiosity telemetry for tests."""

    now = datetime(2025, 10, 12, 12, 0, tzinfo=timezone.utc)

    empathy_rows = [
        {
            "ts": (now - timedelta(days=2)).isoformat(),
            "emotional_state": "trust",
            "intensity": 0.42,
            "confidence": 0.68,
            "primary_needs": ["validation"],
            "recommended_actions": ["Acknowledge the effort"],
            "bonding_metrics": {
                "turns_observed": 8,
                "positive_turns": 4,
                "trust_score": 0.52,
                "rapport_score": 0.49,
            },
        },
        {
            "ts": now.isoformat(),
            "emotional_state": "joy",
            "intensity": 0.71,
            "confidence": 0.79,
            "primary_needs": ["celebration"],
            "recommended_actions": ["Celebrate the win"],
            "bonding_metrics": {
                "turns_observed": 9,
                "positive_turns": 5,
                "trust_score": 0.63,
                "rapport_score": 0.58,
            },
        },
    ]

    empathy_path = data_root / "telemetry" / "empathy" / f"{user_id}.jsonl"
    _write_jsonl(empathy_path, empathy_rows)

    debt_payload: Dict[str, Dict[str, float]] = {
        "CareerDNA.focus_depth": {
            "score": 0.72,
            "last_seen": (now - timedelta(days=12)).isoformat(),
        },
        "HealthDNA.sleep_quality": {
            "score": 0.55,
            "last_seen": (now - timedelta(days=3)).isoformat(),
        },
        "SocialDNA.connection_map": {
            "score": 0.61,
            "last_seen": (now - timedelta(days=9)).isoformat(),
        },
        "GrowthDNA.learning_flux": {
            "score": 0.33,
            "last_seen": now.isoformat(),
        },
    }

    debt_dir = data_root / "curiosity" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    (debt_dir / f"{user_id}.json").write_text(
        json.dumps(
            {
                "updated_at": now.isoformat(),
                "items": debt_payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    agenda_dir = data_root / "curiosity" / "agendas"
    agenda_dir.mkdir(parents=True, exist_ok=True)
    (agenda_dir / f"{user_id}.json").write_text(
        json.dumps(
            {
                "generated_at": (now - timedelta(days=1)).isoformat(),
                "items": [
                    {"target": "CareerDNA.focus_depth", "debt_score": 0.41},
                    {"target": "HealthDNA.sleep_quality", "debt_score": 0.38},
                    {"target": "SocialDNA.connection_map", "debt_score": 0.36},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return empathy_path, debt_dir


def test_build_human_intel_snapshot(tmp_path: Path) -> None:
    data_root = tmp_path
    _create_sample_telemetry(data_root)

    snapshot = hc_human_intel.build_human_intel_snapshot(
        "USER1",
        window_days=7,
        data_root=data_root,
    )

    assert snapshot["user_id"] == "USER1"
    assert snapshot["empathy"]["samples"] == 2
    assert snapshot["empathy"]["trend"]["direction"] == "up"
    assert snapshot["curiosity"]["trend"]["direction"] == "up"
    assert len(snapshot["curiosity"]["top_gaps"]) == 3
    assert snapshot["curiosity"]["trend"]["stale_targets"] >= 1
    daily = snapshot["curiosity"]["snapshot"]
    assert isinstance(daily.get("prompt"), (str, type(None)))
    assert isinstance(daily.get("daily_questions"), list)


def test_human_intel_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from ReDNACoreDemo.core import api

    calls: Dict[str, Tuple[str, int]] = {}

    def fake_snapshot(user_id: str, *, window_days: int, data_root: Path | None = None) -> Dict[str, Any]:  # type: ignore[name-defined]
        calls["args"] = (user_id, window_days)
        return {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": window_days,
            "empathy": {"samples": 0, "trend": {"direction": "steady"}},
            "curiosity": {"top_gaps": [], "trend": {"direction": "steady"}, "snapshot": {"daily_questions": []}},
        }

    monkeypatch.setattr(api.hc_human_intel, "build_human_intel_snapshot", fake_snapshot)

    client = TestClient(api.app)
    response = client.get("/ui/hc/life/USER9/human_intel?days=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["snapshot"]["user_id"] == "USER9"
    assert payload["snapshot"]["window_days"] == 5
    assert "duration_ms" in payload
    assert calls["args"] == ("USER9", 5)
