from __future__ import annotations

import json

import pytest

from ExplorerFinal.ui import coach_orchestrator as orchestrator
from PhotoRefinementCoach.src import importer


def _make_response(body: dict, *, ok: bool = True, status_code: int = 200, content_type: str = "application/json"):
    class _Response:
        def __init__(self) -> None:
            self.ok = ok
            self.status_code = status_code
            self._body = body
            self.headers = {"content-type": content_type}

        def json(self) -> dict:
            return self._body

        @property
        def text(self) -> str:
            return json.dumps(self._body)

    return _Response()


def test_build_core_payload_merges_provenance():
    payload = {
        "default_provenance": {"images": ["img-a.jpg"]},
        "observations": {
            "PaDNA.HairDNA.Color": {"resolved_value": "Honey", "ucn": 840}
        },
        "warnings": ["note"],
    }

    result = orchestrator._build_core_payload_from_import(
        payload,
        "tester",
        compute_rr=False,
        use_inbound_rr=False,
    )

    assert result["user_id"] == "tester"
    assert result["options"]["compute_rr_curiosity"] is False
    trait = result["observations"]["PaDNA.HairDNA.Color"]
    provenance = trait.get("provenance", {})
    assert provenance.get("actor") == "photo-import"
    assert provenance.get("source") == "explorer"
    assert provenance.get("via") == "json"
    assert "ts" in provenance
    assert sorted(provenance.get("images", [])) == ["img-a.jpg"]
    assert result["metadata"]["warnings"] == ["note"]


def test_build_core_payload_preserves_inbound_rr():
    payload = {
        "default_provenance": {},
        "observations": {
            "PaDNA.EyeDNA.Color": {"resolved_value": "Hazel", "rr": 0.42}
        },
    }

    result = orchestrator._build_core_payload_from_import(
        payload,
        "tester",
        compute_rr=True,
        use_inbound_rr=True,
    )

    trait = result["observations"]["PaDNA.EyeDNA.Color"]
    assert trait["rr"] == 0.42
    assert "options" not in result  # compute_rr=True by default


def test_flatten_schema_reports_missing_observations_message():
    flattened, warnings, _ = importer.flatten_schema({})
    assert not flattened
    assert any(w.startswith(importer.MISSING_OBSERVATIONS_MESSAGE) for w in warnings)


def test_flatten_schema_reports_non_object_indexes():
    payload = {"observations": ["bad", 42, {"path": "PaDNA.HairDNA.Color", "value": "Brown"}]}
    flattened, warnings, _ = importer.flatten_schema(payload)
    assert "PaDNA.HairDNA.Color" in flattened
    joined = " ".join(warnings)
    assert "Each `observations` entry must be an object" in joined
    assert "0" in joined and "1" in joined


def test_load_and_validate_returns_clear_error_for_missing_observations():
    payload = {"user_id": "demo"}
    normalized, report, errors = importer.load_and_validate(json.dumps(payload).encode("utf-8"))
    assert report["observations"]["ok"] is False
    assert any(err.startswith(importer.MISSING_OBSERVATIONS_MESSAGE) for err in errors)


def test_ensure_user_ready_handles_responses(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_post(url: str, *args, **kwargs):  # type: ignore[override]
        calls.append(url)
        if url.endswith("/users/init"):
            return _make_response({"init": "ok"})
        if url.endswith("/ensure"):
            return _make_response({"ensure": "fail"}, ok=False, status_code=500)
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(orchestrator.requests, "post", fake_post)

    summary = orchestrator._ensure_user_ready_in_services("tester")

    assert summary["ucnrr"]["ok"] is True
    assert summary["ucnrr"]["status_code"] == 200
    assert summary["core"]["ok"] is False
    assert summary["core"]["status_code"] == 500
    assert any(url.endswith("/users/init") for url in calls)
    assert any(url.endswith("/ensure") for url in calls)
