import json
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient

import ReDNACoreDemo.core.api as api_module


def _build_persona_index() -> Dict[str, List[Dict[str, float]]]:
    return {
        "career": [
            {
                "container_id": "career_1",
                "path": "CareerDNA.progression.generated.1",
                "weight": 0.95,
                "trait_relevance": 0.82,
                "curiosity_boost": 0.4,
            },
            {
                "container_id": "career_2",
                "path": "CareerDNA.progression.generated.2",
                "weight": 0.7,
                "trait_relevance": 0.74,
                "curiosity_boost": 0.35,
            },
        ],
        "relationship": [
            {
                "container_id": "rel_1",
                "path": "RelationshipDNA.trust.generated.1",
                "weight": 0.88,
                "trait_relevance": 0.77,
                "curiosity_boost": 0.5,
            }
        ],
    }


@pytest.fixture()
def persona_api(tmp_path: Path, monkeypatch) -> TestClient:
    """Provide a TestClient with a temporary persona index."""
    index_data = _build_persona_index()
    index_path = tmp_path / "persona_context_index.json"
    index_path.write_text(json.dumps(index_data), encoding="utf-8")
    monkeypatch.setattr(api_module, "PERSONA_CONTEXT_INDEX_PATH", index_path)
    app = api_module.build_app()
    return TestClient(app)


def test_persona_context_success_response(persona_api: TestClient) -> None:
    response = persona_api.get("/ui/persona/context/career/demo-user")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["persona"] == "career"
    assert payload["user_id"] == "demo-user"
    assert payload["total_containers"] == 2
    assert payload["returned_containers"] == 2


def test_persona_context_limit_parameter(persona_api: TestClient) -> None:
    response = persona_api.get("/ui/persona/context/career/demo-user?limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_containers"] == 1
    assert len(payload["containers"]) == 1


def test_persona_context_sorting_by_weight(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/career/demo-user").json()
    weights = [entry["weight"] for entry in payload["containers"]]
    assert weights == sorted(weights, reverse=True)


def test_persona_context_missing_persona_returns_empty(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/unknown/demo").json()
    assert payload["ok"] is True
    assert payload["total_containers"] == 0
    assert payload["containers"] == []


def test_persona_context_duration_under_threshold(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/career/demo").json()
    assert payload["duration_ms"] < 20


def test_persona_context_includes_trait_metadata(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/career/demo").json()
    entry = payload["containers"][0]
    assert "trait_relevance" in entry
    assert "curiosity_boost" in entry


def test_persona_context_error_when_index_missing(tmp_path: Path, monkeypatch) -> None:
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(api_module, "PERSONA_CONTEXT_INDEX_PATH", missing_path)
    app = api_module.build_app()
    client = TestClient(app)
    payload = client.get("/ui/persona/context/career/demo").json()
    assert payload["ok"] is False
    assert "error" in payload


def test_persona_context_invalid_json_returns_500(tmp_path: Path, monkeypatch) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{ not json }", encoding="utf-8")
    monkeypatch.setattr(api_module, "PERSONA_CONTEXT_INDEX_PATH", invalid_path)
    app = api_module.build_app()
    client = TestClient(app)
    response = client.get("/ui/persona/context/career/demo")
    assert response.status_code == 500
    assert "Failed to get persona context" in response.json()["detail"]


def test_persona_context_default_limit_returns_all(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/relationship/demo").json()
    assert payload["returned_containers"] == 1
    assert payload["total_containers"] == 1


def test_persona_context_respects_limit_upper_bound(persona_api: TestClient) -> None:
    payload = persona_api.get("/ui/persona/context/career/demo?limit=10").json()
    assert payload["returned_containers"] == 2
    assert len(payload["containers"]) == 2
