import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def health_testbed(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("DEVX_DATA_ROOT", str(data_root))

    from ReDNACoreDemo.devx.backend import health_api

    module = importlib.reload(health_api)

    async def stub_probe(url: str):  # pragma: no cover - simple stub
        return {"status": "green", "ok": True, "ms": 5.0, "detail": "stub"}

    module._probe = stub_probe  # type: ignore[attr-defined]

    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)

    return {
        "client": client,
        "module": module,
        "data_root": data_root,
    }


def test_health_status_writes_history(health_testbed):
    client = health_testbed["client"]
    module = health_testbed["module"]
    data_root = health_testbed["data_root"]

    for _ in range(2):
        response = client.get("/health/status")
        assert response.status_code == 200

    history_file = module.HISTORY_FILE
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2

    history_resp = client.get("/health/history", params={"limit": 2})
    assert history_resp.status_code == 200
    payload = history_resp.json()
    assert len(payload["entries"]) == 2
    assert all("ts" in entry for entry in payload["entries"])
