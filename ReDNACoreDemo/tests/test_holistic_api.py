import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def holistic_testbed(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    users_root = data_root / "users"
    users_root.mkdir(parents=True)

    # Seed vault contents
    base = users_root / "U1"
    (base / "evidence").mkdir(parents=True)
    (base / "derived").mkdir(parents=True)
    (base / "containers").mkdir(parents=True)
    (base / "evidence" / "e1.json").write_text("{}", encoding="utf-8")
    (base / "derived" / "d1.json").write_text("{}", encoding="utf-8")
    containers = [
        {"path": "SkillDNA.communication", "rr": 72.0},
        {"path": "ProfDNA.collaboration", "rr": 61.0},
        {"path": "PsyDNA.openness", "rr": 49.0},
    ]
    resolved_payload = {
        "metadata": {"owner": "U1"},
        "containers": containers,
    }
    (base / "resolved.json").write_text(json.dumps(resolved_payload), encoding="utf-8")

    monkeypatch.setenv("DEVX_DATA_ROOT", str(data_root))

    from ReDNACoreDemo.devx.backend import batch_ops_api, holistic_api

    batch_module = importlib.reload(batch_ops_api)
    holistic_module = importlib.reload(holistic_api)

    job_id = "holistic_testjob"
    manifest = {
        "job_id": job_id,
        "user_ids": ["U1"],
        "queued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "queued",
        "action": "run_holistic",
        "reason": "unit-test",
    }
    batch_module.safe_json_dump(batch_module.HOLISTIC_JOBS_ROOT / f"{job_id}.json", manifest)

    batch_app = FastAPI()
    batch_app.include_router(batch_module.router)
    batch_client = TestClient(batch_app)

    holistic_app = FastAPI()
    holistic_app.include_router(holistic_module.router)
    holistic_client = TestClient(holistic_app)

    return {
        "data_root": data_root,
        "batch_client": batch_client,
        "holistic_client": holistic_client,
        "job_id": job_id,
    }


def test_run_holistic_process_generates_results(holistic_testbed):
    client = holistic_testbed["batch_client"]
    job_id = holistic_testbed["job_id"]
    data_root = holistic_testbed["data_root"]

    response = client.post("/users/batch/run-holistic/process", json={"job_id": job_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["results"][0]["status"] == "ok"

    result_path = data_root / "holistic" / "U1.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["counts"]["containers"] == 3
    assert result["counts"]["evidence"] == 1
    assert result["counts"]["derived"] == 1
    assert result["rr"]["overall_rr"] > 0
    assert result["top_low_rr_paths"], "expected low RR paths"

    history_dir = data_root / "holistic" / "history"
    history_files = list(history_dir.glob("U1_*.json"))
    assert history_files, "history entry expected"


def test_holistic_get_and_history(holistic_testbed):
    # Ensure results exist
    test_run_holistic_process_generates_results(holistic_testbed)

    client = holistic_testbed["holistic_client"]

    result_resp = client.get("/get", params={"user_id": "U1"})
    assert result_resp.status_code == 200
    result = result_resp.json()
    assert result["user_id"] == "U1"
    assert "counts" in result

    history_resp = client.get("/history", params={"user_id": "U1", "limit": 5})
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["entries"], "history entries expected"
