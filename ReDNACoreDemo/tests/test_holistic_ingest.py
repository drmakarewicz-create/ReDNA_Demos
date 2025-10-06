from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def core_test_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module_name = "ReDNACoreDemo.app"

    monkeypatch.setenv("CORE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CORE_HOLISTIC_ON_INGEST", "1")
    monkeypatch.setenv("CORE_HOLISTIC_MAX_MS", "750")

    # Ensure a clean import for every test run
    for name in list(sys.modules.keys()):
        if name.startswith("ReDNACoreDemo"):
            del sys.modules[name]

    app_module = importlib.import_module(module_name)
    client = TestClient(app_module.app)

    yield client, tmp_path

    # Remove modules loaded with the test configuration so later tests re-import defaults
    for name in list(sys.modules.keys()):
        if name.startswith("ReDNACoreDemo"):
            del sys.modules[name]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_ingest_runs_holistic_and_backfills(core_test_client):
    client, tmp_path = core_test_client

    payload = {
        "user_id": "tester",
        "observations": {
            "PaDNA.HairDNA.Color": {"value": "Blonde"},
        },
    }

    resp = client.post("/ingest_from_ucnrr", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    holistic = body.get("holistic") or {}
    assert holistic.get("ran") is True
    assert holistic.get("ucn_rr_updates", 0) >= 1

    user_dir = tmp_path / "users" / "tester"
    resolved_doc = _read_json(user_dir / "resolved.json")
    entry = resolved_doc["resolved"]["PaDNA.HairDNA.Color"]
    assert entry["ucn"] >= 50.0
    assert entry["rr"] >= 5.0
    assert entry.get("curiosity") <= 95.0
    assert entry.get("provenance", {}).get("step") == "core-holistic"

    last_holistic = _read_json(user_dir / "last_holistic.json")
    assert "PaDNA.HairDNA.Color" in last_holistic.get("paths", {}).get("all", [])


def test_import_padna_triggers_inference(core_test_client):
    client, tmp_path = core_test_client

    payload = {
        "user_id": "bundle-user",
        "observations": {
            "PaDNA.HairDNA.Color": {"value": "Blonde"},
            "PaDNA.SkinDNA.Undertone": {"value": "Warm"},
        },
        "default_provenance": {"source": "padna_json"},
    }

    resp = client.post("/import/padna_json", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    holistic = body.get("holistic") or {}
    assert holistic.get("ran") is True
    assert holistic.get("implied_additions", 0) >= 1

    user_dir = tmp_path / "users" / "bundle-user"
    resolved_doc = _read_json(user_dir / "resolved.json")
    implied_entry = resolved_doc["resolved"].get("PaDNA.EyeDNA.Brows")
    assert implied_entry is not None, "Expected inference to add brow trait"
    assert implied_entry.get("value") == "Light brown"
    assert implied_entry.get("provenance", {}).get("step") == "core-holistic"

    last_holistic = _read_json(user_dir / "last_holistic.json")
    implied_reasons = last_holistic.get("implied_reasons", {})
    assert implied_reasons.get("PaDNA.EyeDNA.Brows")

