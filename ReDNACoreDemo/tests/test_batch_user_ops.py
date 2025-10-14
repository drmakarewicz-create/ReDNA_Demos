import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class StubConsentClient:
    """Test double for the consent service."""

    def __init__(self):
        self.revoked = []
        self.offline_users = set()
        self.capabilities = {}

    def list_capabilities(self, user_id: str):
        if user_id in self.offline_users:
            return (None, "Consent service offline.")
        caps = [
            {"id": f"{user_id}-cap-1"},
            {"id": f"{user_id}-cap-2"},
        ]
        self.capabilities[user_id] = caps
        return (caps, None)

    def revoke_capability(self, capability: dict):
        self.revoked.append(capability.get("id"))
        return None


@pytest.fixture
def batch_ops_testbed(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    users_root = data_root / "users"

    # Seed user directories with simple structures
    for user_id in ("U1", "U2"):
        base = users_root / user_id
        (base / "evidence").mkdir(parents=True)
        (base / "derived").mkdir(parents=True)
        (base / "containers").mkdir(parents=True)
        (base / "evidence" / "event.json").write_text("{}", encoding="utf-8")
        (base / "derived" / "feature.json").write_text("{}", encoding="utf-8")
        (base / "containers" / "bundle.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("DEVX_DATA_ROOT", str(data_root))
    monkeypatch.setenv("CONSENT_SERVICE_URL", "http://consent.stub")

    from ReDNACoreDemo.core.vault import vault_client

    monkeypatch.setattr(vault_client, "VAULT_ROOT", users_root)

    module = importlib.import_module("ReDNACoreDemo.devx.backend.batch_ops_api")
    module = importlib.reload(module)

    stub = StubConsentClient()

    def _get_stub_client():
        return stub

    module.get_consent_client = _get_stub_client  # type: ignore[assignment]

    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)

    return {
        "client": client,
        "module": module,
        "data_root": data_root,
        "stub": stub,
    }


def test_list_users_and_summary(batch_ops_testbed):
    client = batch_ops_testbed["client"]

    response = client.get("/users/list")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {user["user_id"] for user in payload["users"]} == {"U1", "U2"}

    summary = client.get("/users/summary", params={"user_id": "U1"})
    assert summary.status_code == 200
    details = summary.json()
    assert details["counts"]["evidence"] == 1
    assert details["counts"]["derived"] == 1
    assert details["counts"]["containers"] == 1


def test_dry_run_returns_plan(batch_ops_testbed):
    client = batch_ops_testbed["client"]

    response = client.post("/users/batch/dry-run", json={"user_ids": ["U1", "U2"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["users"] == 2
    assert "U1" in payload["users"]
    assert payload["users"]["U1"]["bytes_to_quarantine"] > 0


def test_delete_undo_and_purge_flow(batch_ops_testbed):
    client = batch_ops_testbed["client"]
    module = batch_ops_testbed["module"]
    data_root = batch_ops_testbed["data_root"]
    stub: StubConsentClient = batch_ops_testbed["stub"]

    # Simulate consent service offline for U2
    stub.offline_users.add("U2")

    # Submit deletion (quarantine)
    delete_payload = {
        "user_ids": ["U1", "U2"],
        "reason": "Cleanup test",
        "grace_days": 7,
        "confirm": "DELETE 2 USERS",
    }
    delete_resp = client.post("/users/batch/delete", json=delete_payload)
    assert delete_resp.status_code == 200
    delete_body = delete_resp.json()
    job_id = delete_body["job_id"]
    assert set(delete_body["accepted"]) == {"U1", "U2"}
    assert delete_body["errors"] == []

    users_root = data_root / "users"
    assert not (users_root / "U1").exists()
    assert not (users_root / "U2").exists()

    # Quarantine directory should now exist
    quarantine_dirs = sorted((data_root / "quarantine").glob("*"))
    assert quarantine_dirs, "Expected quarantine directory to be created."
    batch_dir = quarantine_dirs[-1]
    assert (batch_dir / "U1").exists()
    assert (batch_dir / "U2").exists()

    # Ticket files created
    ticket_u1 = sorted((data_root / "purge_requests" / "U1").glob("ticket_*.json"))[-1]
    ticket_u2 = sorted((data_root / "purge_requests" / "U2").glob("ticket_*.json"))[-1]
    ticket_payload_u1 = json.loads(ticket_u1.read_text(encoding="utf-8"))
    ticket_payload_u2 = json.loads(ticket_u2.read_text(encoding="utf-8"))
    assert ticket_payload_u1["status"] == "quarantine"
    assert ticket_payload_u2["status"] == "quarantine"
    assert ticket_payload_u2["capabilities_revoked"] is None
    assert any("offline" in msg.lower() for msg in ticket_payload_u2["warnings"])

    # Job status surfaces per-user entries
    status_resp = client.get("/users/batch/status", params={"job_id": job_id})
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["users"]["U1"]["status"] == "quarantine"
    assert status_payload["users"]["U2"]["status"] == "quarantine"

    # Undo for U1 (still within grace period)
    undo_payload = {
        "job_id": job_id,
        "user_ids": ["U1"],
        "confirm": "UNDO 1 USERS",
    }
    undo_resp = client.post("/users/batch/undo", json=undo_payload)
    assert undo_resp.status_code == 200
    undo_data = undo_resp.json()
    assert undo_data["restored"] == ["U1"]
    assert (users_root / "U1").exists()
    updated_ticket_u1 = json.loads(ticket_u1.read_text(encoding="utf-8"))
    assert updated_ticket_u1["status"] == "restored"

    # Attempt purge before grace period should fail
    purge_payload = {
        "user_ids": ["U2"],
        "confirm": "PURGE 1 USERS",
    }
    purge_resp = client.post("/users/batch/purge", json=purge_payload)
    assert purge_resp.status_code == 200
    purge_data = purge_resp.json()
    assert purge_data["purged"] == []
    assert purge_data["errors"], "Expected purge to be blocked during grace period."

    # Force grace expiration by adjusting ticket
    expired_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    ticket_payload_u2["review_until"] = expired_time
    ticket_u2.write_text(json.dumps(ticket_payload_u2), encoding="utf-8")

    purge_resp = client.post("/users/batch/purge", json=purge_payload)
    assert purge_resp.status_code == 200
    purge_data = purge_resp.json()
    assert purge_data["purged"] == ["U2"]
    assert not (batch_dir / "U2").exists()

    refreshed_ticket_u2 = json.loads(ticket_u2.read_text(encoding="utf-8"))
    assert refreshed_ticket_u2["status"] == "purged"

    # Status call now reflects restored/purged states
    final_status = client.get("/users/batch/status", params={"job_id": job_id}).json()
    assert final_status["users"]["U1"]["status"] == "restored"
    assert final_status["users"]["U2"]["status"] == "purged"


def test_run_holistic_creates_job_manifest(batch_ops_testbed):
    client = batch_ops_testbed["client"]
    data_root = batch_ops_testbed["data_root"]

    response = client.post("/users/batch/run-holistic", json={"user_ids": ["U1", "U2"], "reason": "smoke"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["count"] == 2
    job_id = payload["job_id"]

    holistic_dir = data_root / "devx_jobs" / "holistic"
    job_path = holistic_dir / f"{job_id}.json"
    assert job_path.exists()

    job_manifest = json.loads(job_path.read_text(encoding="utf-8"))
    assert job_manifest["action"] == "run_holistic"
    assert job_manifest["status"] == "queued"
    assert job_manifest["user_ids"] == ["U1", "U2"]
    assert job_manifest["reason"] == "smoke"


def test_revoke_caps_records_warnings(batch_ops_testbed):
    client = batch_ops_testbed["client"]
    data_root = batch_ops_testbed["data_root"]
    stub: StubConsentClient = batch_ops_testbed["stub"]

    stub.offline_users.update({"U1", "U2"})

    response = client.post(
        "/users/batch/revoke-caps",
        json={"user_ids": ["U1", "U2"], "reason": "maintenance"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_revoked"] == 0
    assert payload["status"] == "completed"
    assert len(payload["results"]) == 2
    for result in payload["results"]:
        assert result["warnings"]
        assert result["revoked"] == 0

    job_path = data_root / "devx_jobs" / "revoke_caps" / f"{payload['job_id']}.json"
    assert job_path.exists()
    job_manifest = json.loads(job_path.read_text(encoding="utf-8"))
    assert job_manifest["total_revoked"] == 0


def test_export_json_batch_creates_files(batch_ops_testbed, monkeypatch):
    data_root = batch_ops_testbed["data_root"]
    exports_root = data_root / "exports"

    from ReDNACoreDemo.devx.backend import privacy_dashboard_api

    privacy_module = importlib.reload(privacy_dashboard_api)
    monkeypatch.setattr(privacy_module, "EXPORTS_ROOT", exports_root)
    exports_root.mkdir(parents=True, exist_ok=True)

    resolved_path = data_root / "users" / "U1" / "resolved.json"
    resolved_path.write_text(
        json.dumps(
            {
                "metadata": {"owner": "TEST"},
                "containers": [
                    {"path": "SkillDNA.sample", "rr": 0.6, "extra": "hidden"},
                    {"path": "BehDNA.other", "rr": 0.4},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert resolved_path.exists()

    from ReDNACoreDemo.core.vault import vault_client

    monkeypatch.setattr(vault_client, "VAULT_ROOT", data_root / "users")

    vc = vault_client.VaultClient("U1")
    assert vc.vault_path == resolved_path.parent
    loaded_resolved = vc.read_resolved()
    assert loaded_resolved.get("containers"), "expected seeded resolved data"

    app = FastAPI()
    app.include_router(privacy_module.router)
    client = TestClient(app)

    response = client.post("/privacy/export-json-batch", json={"user_ids": ["U1"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["status"] == "ready"
    download_path = exports_root / "U1"
    export_file = next(download_path.glob("export_*.json"))
    export_data = json.loads(export_file.read_text(encoding="utf-8"))
    assert export_data["user_id"] == "U1"
    assert "metadata" in export_data
    assert export_data["containers"] == [
        {"path": "SkillDNA.sample", "rr": 0.6},
        {"path": "BehDNA.other", "rr": 0.4},
    ]
