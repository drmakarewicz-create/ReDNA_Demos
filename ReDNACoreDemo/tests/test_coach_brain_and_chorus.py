from __future__ import annotations

import hashlib
from typing import Any, Dict
import json

from fastapi.testclient import TestClient
import pytest

from ReDNACoreDemo.core.api import build_app


class DummySession:
    def __init__(self, active_coach_id: str = "career_coach", context_version: int = 42):
        self.active_coach_id = active_coach_id
        self.context_version = context_version
        self.cancel_token = "token"
        self.merged_hash = "abc123"
        self.behavior_context: Dict[str, Any] = {
            "hints": {"tone_target": "empathetic", "confidence": 0.82},
            "_connection_data": {"confidence": 0.82},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_coach_id": self.active_coach_id,
            "context_version": self.context_version,
            "cancel_token": self.cancel_token,
            "merged_hash": self.merged_hash,
            "behavior_context": self.behavior_context,
        }


class DummySessionManager:
    def __init__(self):
        self._session = DummySession()
        self._coach_text = ("# Head Coach Mandate\n", "# Career Coach Mandate\n")

    def get_session(self, user_id: str) -> DummySession:
        return self._session

    def _load_coach_mandate(self, coach_id: str):
        return self._coach_text

    def _merge_prompt(self, coach_mandate, behavior_context: Dict[str, Any]) -> str:
        hc, aug = coach_mandate
        hints = behavior_context.get("hints", {})
        hint_lines = "\n".join(f"{k}: {v}" for k, v in hints.items())
        return f"{hc}\n=== AUGMENT ===\n{aug}\n=== RUNTIME ===\n{hint_lines}\n"


class DummyOrchestrator:
    def build_activation_snapshot(self, user_id: str, context_version: int | None = None, **_: Any) -> Dict[str, Any]:
        return {
            "ts": "2025-10-10T19:24:05.451Z",
            "user_id": user_id,
            "context_version": context_version or 42,
            "active_coach_id": "career_coach",
            "nodes": [
                {"id": "head_coach", "label": "Head Coach", "active": True, "weight": 1.0},
                {"id": "career_coach", "label": "Career Coach", "active": True, "weight": 0.78},
                {"id": "curiosity_engine", "label": "Curiosity", "active": True, "weight": 0.62},
                {"id": "learning", "label": "Self-Improvement", "active": False, "weight": 0.4},
            ],
            "edges": [
                {"from": "head_coach", "to": "career_coach", "strength": 0.78},
                {"from": "curiosity_engine", "to": "head_coach", "strength": 0.62},
            ],
            "meta": {
                "augment_confidence": 0.78,
                "curiosity_priority": 0.62,
                "requires_consent": False,
            },
        }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    dummy_manager = DummySessionManager()
    dummy_orchestrator = DummyOrchestrator()

    from ReDNACoreDemo.core import api as api_module
    from ReDNACoreDemo.core.head_coach import session_manager as session_module

    monkeypatch.setattr(session_module, "get_session_manager", lambda: dummy_manager, raising=False)
    monkeypatch.setattr(api_module, "_get_orchestrator", lambda: dummy_orchestrator, raising=False)

    return TestClient(build_app())


def test_coach_brain_snapshot(client: TestClient) -> None:
    response = client.get("/coach/brain", params={"user_id": "TEST"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    snapshot = payload["snapshot"]
    assert snapshot["active_coach_id"] == "career_coach"
    assert snapshot["context_version"] == 42
    assert any(node["id"] == "head_coach" for node in snapshot["nodes"])
    assert any(edge["from"] == "curiosity_engine" for edge in snapshot["edges"])


def test_coach_chorus_sections(client: TestClient) -> None:
    response = client.get("/coach/chorus", params={"user_id": "TEST"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["active_coach_id"] == "career_coach"

    head = payload["head_coach"]["text"]
    augment = payload["augment"]["text"]
    merged = payload["merged"]["text"]
    runtime_hash = payload["runtime"]["hash"]
    runtime_json = payload["runtime"]["json"]

    assert "# Head Coach Mandate" in head
    assert "# Career Coach Mandate" in augment
    assert "=== AUGMENT ===" in merged

    canonical = hashlib.sha256(
        json.dumps(runtime_json, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    assert runtime_hash == canonical
