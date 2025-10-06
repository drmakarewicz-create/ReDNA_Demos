from __future__ import annotations

from typing import Any, Dict

import pytest

from ExplorerFinal.ui import coach_api


class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.ok = status == 200
        self.reason = "OK" if self.ok else "error"
        self.headers = {"content-type": "application/json"}

    def json(self) -> Any:
        return self._payload


@pytest.fixture(autouse=True)
def _reset_persona(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(coach_api, "get_persona", lambda _pid: {"title": "Head Coach", "tools": ["ingest_text", "get_resolved"], "style": {}})
    monkeypatch.setattr(coach_api, "persona_compose_system_prompt", lambda *args, **kwargs: "system")
    monkeypatch.setattr(coach_api, "persona_apply_style", lambda style, text: text)


def test_run_holistic_review_summarizes_counts(monkeypatch: pytest.MonkeyPatch):
    report = {
        "ok": True,
        "ucn_rr_updates": [{"path": "Trait.A"}, {"path": "Trait.B"}],
        "implied_additions": [{"path": "Trait.C"}],
        "contradictions": [],
    }

    def fake_post(url: str, json: Dict[str, Any], timeout: int):  # type: ignore[override]
        assert url.endswith("/holistic/tester")
        return _FakeResponse(report)

    def fake_get(url: str, timeout: int):  # type: ignore[override]
        assert url.endswith("/resolved/tester")
        return _FakeResponse({"resolved": {}})

    monkeypatch.setattr(coach_api.requests, "post", fake_post)
    monkeypatch.setattr(coach_api.requests, "get", fake_get)

    result = coach_api.run_holistic_review("tester")
    assert result["ok"] is True
    assert result["summary"] == {
        "ran": True,
        "async": False,
        "ucn_rr_updates": 2,
        "implied_additions": 1,
        "contradictions": 0,
    }
    assert "Holistic review updated" in result.get("badge", "")


def test_coach_ingest_text_includes_holistic_badge(monkeypatch: pytest.MonkeyPatch):
    holistic_report = {
        "ucn_rr_updates": [{"path": "Trait.A"}],
        "implied_additions": [],
        "contradictions": [],
    }

    def fake_post(url: str, json: Dict[str, Any], timeout: int):  # type: ignore[override]
        if url.endswith("/ingest_text"):
            return _FakeResponse({"core_response": {"holistic": holistic_report}, "changed_keys": ["Trait.A"]})
        raise AssertionError("Unexpected POST url")

    def fake_get(url: str, timeout: int):  # type: ignore[override]
        if url.endswith("/resolved/tester"):
            return _FakeResponse({"resolved": {}})
        return _FakeResponse({"resolved": {}})

    monkeypatch.setattr(coach_api.requests, "post", fake_post)
    monkeypatch.setattr(coach_api.requests, "get", fake_get)

    reply = coach_api.coach_ingest_text("tester", "Hello", dev_mode=False)
    assert reply["holistic"]["ran"] is True
    assert reply["holistic"]["ucn_rr_updates"] == 1
