import importlib
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SOURCE = PROJECT_ROOT / "core" / "ontology" / "trait_semantics" / "schema" / "trait_semantics.schema.json"


@pytest.fixture
def semantics_testbed(tmp_path, monkeypatch):
    """Prepare an isolated semantics store and API client."""
    store = tmp_path / "trait_semantics"
    schema_dir = store / "schema"
    schema_dir.mkdir(parents=True)

    schema_dir.joinpath("trait_semantics.schema.json").write_text(
        SCHEMA_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    store.joinpath("registry.yaml").write_text("{}\n", encoding="utf-8")
    store.joinpath("CHANGELOG.md").write_text("# test changelog\n", encoding="utf-8")

    monkeypatch.setenv("REDNA_SEMANTICS_ROOT", str(store))

    module = importlib.import_module("ReDNACoreDemo.devx.backend.semantics_api")
    module = importlib.reload(module)

    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)

    return {
        "client": client,
        "store": store,
    }


def test_get_semantics_returns_null_when_missing(semantics_testbed):
    client = semantics_testbed["client"]
    response = client.get("/get", params={"path": "BehDNA.NonExistentTrait"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "BehDNA.NonExistentTrait"
    assert payload["semantics"] is None


def test_propose_invalid_draft_returns_errors(semantics_testbed):
    client = semantics_testbed["client"]
    payload = {
        "path": "BehDNA.InvalidTrait",
        "draft": {
            "version": "1.0.0"
        }
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["errors"], "Expected validation errors for missing definition"


def test_propose_and_apply_low_risk_change(semantics_testbed):
    client = semantics_testbed["client"]
    store = semantics_testbed["store"]
    registry_path = store / "registry.yaml"

    existing_entry = {
        "definition": "Existing definition text.",
        "scope_notes": "Original scope notes.",
        "examples": [
            {"label": "baseline", "description": "Existing example"}
        ],
        "counterexamples": [],
        "version": "1.0.0"
    }
    registry_path.write_text(
        yaml.safe_dump({"BehDNA.DocTrait": existing_entry}, sort_keys=True),
        encoding="utf-8",
    )

    draft = {
        "definition": "Updated definition text with clarification.",
        "scope_notes": "Original scope notes.",
        "examples": existing_entry["examples"] + [{"label": "new", "description": "New supporting example"}],
        "counterexamples": [],
        "version": "1.0.0"
    }
    propose_resp = client.post(
        "/propose",
        json={
            "path": "BehDNA.DocTrait",
            "draft": draft,
            "notes": "Clarified definition and added example."
        },
    )
    assert propose_resp.status_code == 200
    proposal = propose_resp.json()
    assert proposal["accepted"] is True
    cr_id = proposal["cr_id"]

    validate_resp = client.get("/validate", params={"cr_id": cr_id})
    assert validate_resp.status_code == 200
    validation = validate_resp.json()
    assert validation["valid"] is True
    assert validation["errors"] == []

    apply_resp = client.post("/apply", json={"cr_id": cr_id})
    assert apply_resp.status_code == 200
    applied = apply_resp.json()
    assert applied["applied"] is True
    assert applied["path"] == "BehDNA.DocTrait"

    updated_registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert updated_registry["BehDNA.DocTrait"]["definition"] == draft["definition"]
    assert len(updated_registry["BehDNA.DocTrait"]["examples"]) == 2

    changelog_text = (store / "CHANGELOG.md").read_text(encoding="utf-8")
    assert cr_id in changelog_text
    assert "Applied: yes" in changelog_text


def test_apply_requires_approval_for_high_risk_changes(semantics_testbed):
    client = semantics_testbed["client"]
    store = semantics_testbed["store"]
    registry_path = store / "registry.yaml"

    baseline = {
        "definition": "Definition v1",
        "scope_notes": "Scope notes v1",
        "examples": [],
        "counterexamples": [],
        "version": "1.0.0"
    }
    registry_path.write_text(
        yaml.safe_dump({"BehDNA.HighRisk": baseline}, sort_keys=True),
        encoding="utf-8",
    )

    draft = {
        **baseline,
        "version": "2.0.0",  # version bump should trigger approval requirement
    }
    propose_resp = client.post(
        "/propose",
        json={
            "path": "BehDNA.HighRisk",
            "draft": draft,
            "notes": "Major update."
        },
    )
    assert propose_resp.status_code == 200
    proposal = propose_resp.json()
    assert proposal["accepted"] is True
    cr_id = proposal["cr_id"]

    apply_resp = client.post("/apply", json={"cr_id": cr_id})
    assert apply_resp.status_code == 200
    outcome = apply_resp.json()
    assert outcome["applied"] is False
    assert outcome["requires_approval"] is True

    registry_snapshot = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert registry_snapshot["BehDNA.HighRisk"]["version"] == "1.0.0"


def test_diagnostics_reports_store_status(semantics_testbed):
    client = semantics_testbed["client"]
    response = client.get("/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["registry_exists"] is True
    assert payload["entry_count"] == 0


def test_schema_endpoint_returns_json_schema(semantics_testbed):
    client = semantics_testbed["client"]
    response = client.get("/schema")
    assert response.status_code == 200
    schema = response.json()
    assert schema.get("title") == "TraitSemantics"
    assert "properties" in schema
