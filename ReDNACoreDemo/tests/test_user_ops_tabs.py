from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ReDNACoreDemo.devx.backend import batch_ops_api


@pytest.fixture
def devx_client(tmp_path, monkeypatch) -> Tuple[TestClient, Dict[str, Path]]:
    data_root = tmp_path / "data"
    users_root = data_root / "users"
    quarantine_root = data_root / "quarantine"
    purge_root = data_root / "purge_requests"
    jobs_root = data_root / "devx_jobs"
    holistic_jobs_root = jobs_root / "holistic"
    revoke_jobs_root = jobs_root / "revoke_caps"
    holistic_results_root = data_root / "holistic"
    holistic_history_root = holistic_results_root / "history"
    permissions_root = data_root / "permissions"
    capability_store_root = data_root / "capability_tokens"
    audit_log = jobs_root / "user_ops_audit.jsonl"

    for path in (
        users_root,
        quarantine_root,
        purge_root,
        jobs_root,
        holistic_jobs_root,
        revoke_jobs_root,
        holistic_results_root,
        holistic_history_root,
        permissions_root,
        capability_store_root,
        audit_log.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)
    audit_log.write_text("", encoding="utf-8")

    monkeypatch.setattr(batch_ops_api, "DATA_ROOT", data_root)
    monkeypatch.setattr(batch_ops_api, "USERS_ROOT", users_root)
    monkeypatch.setattr(batch_ops_api, "QUARANTINE_ROOT", quarantine_root)
    monkeypatch.setattr(batch_ops_api, "PURGE_REQUESTS_ROOT", purge_root)
    monkeypatch.setattr(batch_ops_api, "DEVX_JOBS_ROOT", jobs_root)
    monkeypatch.setattr(batch_ops_api, "HOLISTIC_JOBS_ROOT", holistic_jobs_root)
    monkeypatch.setattr(batch_ops_api, "REVOKE_CAPS_JOBS_ROOT", revoke_jobs_root)
    monkeypatch.setattr(batch_ops_api, "HOLISTIC_RESULTS_ROOT", holistic_results_root)
    monkeypatch.setattr(batch_ops_api, "HOLISTIC_HISTORY_ROOT", holistic_history_root)
    monkeypatch.setattr(batch_ops_api, "PERMISSIONS_ROOT", permissions_root)
    monkeypatch.setattr(batch_ops_api, "CAPABILITY_STORE_ROOT", capability_store_root)
    monkeypatch.setattr(batch_ops_api, "AUDIT_LOG", audit_log)

    class StubConsentClient:
        def list_capabilities(self, user_id: str):
            return ([], None)

        def revoke_capability(self, payload: Dict[str, str]):
            return None

    monkeypatch.setattr(batch_ops_api, "get_consent_client", lambda: StubConsentClient())

    app = FastAPI()
    app.include_router(batch_ops_api.router, prefix="/devx/api")

    env = {
        "data_root": data_root,
        "users_root": users_root,
        "quarantine_root": quarantine_root,
        "purge_root": purge_root,
        "holistic_results_root": holistic_results_root,
        "holistic_history_root": holistic_history_root,
        "permissions_root": permissions_root,
        "capability_store_root": capability_store_root,
        "audit_log": audit_log,
    }

    return TestClient(app), env


def create_user_fixture(root: Path, user_id: str, include_resolved: bool = True) -> Path:
    user_dir = root / user_id
    (user_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (user_dir / "derived").mkdir(parents=True, exist_ok=True)
    (user_dir / "containers").mkdir(parents=True, exist_ok=True)
    (user_dir / "evidence" / "sample.txt").write_text("evidence", encoding="utf-8")
    if include_resolved:
        resolved = {
            "containers": [
                {"path": "SkillDNA.software_engineering", "rr": 0.42},
                {"path": "Career.management", "rr": 0.65},
            ]
        }
        (user_dir / "resolved.json").write_text(json.dumps(resolved), encoding="utf-8")
    return user_dir


def test_holistic_run_and_latest(devx_client):
    client, env = devx_client
    create_user_fixture(env["users_root"], "USER1")

    resp = client.post("/devx/api/users/USER1/holistic/run", json={"reason": "test-case"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    process = client.post(
        "/devx/api/users/batch/run-holistic/process",
        json={"job_id": job_id},
    )
    assert process.status_code == 200

    latest = client.get("/devx/api/users/USER1/holistic/latest")
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["user_id"] == "USER1"
    assert payload["latest"]["counts"]["evidence"] >= 1
    assert payload["latest"]["rr"]["overall_rr"] > 0
    assert payload["history"], "History should include at least one entry"


def test_user_rename_moves_assets_and_logs(devx_client):
    client, env = devx_client
    create_user_fixture(env["users_root"], "USER2")
    (env["holistic_results_root"] / "USER2.json").write_text(json.dumps({"user_id": "USER2"}), encoding="utf-8")
    (env["holistic_history_root"] / "USER2_20201012T010101Z.json").write_text("{}", encoding="utf-8")

    resp = client.post(
        "/devx/api/users/USER2/rename",
        json={"new_user_id": "USER2B", "confirm": "RENAME USER2 TO USER2B"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "renamed"
    assert not (env["users_root"] / "USER2").exists()
    assert (env["users_root"] / "USER2B").exists()
    assert not (env["holistic_results_root"] / "USER2.json").exists()
    assert (env["holistic_results_root"] / "USER2B.json").exists()

    audit = client.get("/devx/api/users/USER2B/audit")
    events = [entry["event"] for entry in audit.json()["entries"]]
    assert "user_rename" in events


def test_user_retire_and_purge_flow(devx_client):
    client, env = devx_client
    create_user_fixture(env["users_root"], "USER3")

    retire = client.request(
        "DELETE",
        "/devx/api/users/USER3",
        json={"mode": "retire", "confirm": "DELETE USER3", "reason": "cleanup", "grace_days": 2},
    )
    assert retire.status_code == 200
    payload = retire.json()
    quarantine_path = Path(payload["quarantine_path"])
    assert quarantine_path.exists()

    ticket_path = Path(payload["ticket_path"])
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket["review_until"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    batch_ops_api.safe_json_dump(ticket_path, ticket)

    purge = client.request(
        "DELETE",
        "/devx/api/users/USER3",
        json={"mode": "purge", "confirm": "PURGE USER3"},
    )
    assert purge.status_code == 200
    assert not quarantine_path.exists()

    audit = client.get("/devx/api/users/USER3/audit")
    events = [entry["event"] for entry in audit.json()["entries"]]
    assert "user_retire" in events
    assert "user_purge" in events


def test_permissions_and_capabilities_flow(devx_client):
    client, env = devx_client
    user_id = "USER4"

    grant = client.post(
        f"/devx/api/users/{user_id}/permissions/grant",
        json={"namespace": "SkillDNA", "scope": "read"},
    )
    assert grant.status_code == 200

    issue = client.post(
        f"/devx/api/users/{user_id}/capability/issue",
        json={"scope": "core.agent.run", "ttl_minutes": 15},
    )
    assert issue.status_code == 200
    capability_id = issue.json()["capability_id"]

    revoke_cap = client.post(
        f"/devx/api/users/{user_id}/capability/revoke",
        json={"capability_id": capability_id},
    )
    assert revoke_cap.status_code == 200

    revoke_perm = client.post(
        f"/devx/api/users/{user_id}/permissions/revoke",
        json={"namespace": "SkillDNA", "scope": "read"},
    )
    assert revoke_perm.status_code == 200

    perms_file = env["permissions_root"] / f"{user_id}.json"
    assert perms_file.exists()
    permissions = json.loads(perms_file.read_text(encoding="utf-8"))
    assert permissions["namespaces"] == {}

    capabilities = json.loads((env["capability_store_root"] / f"{user_id}.json").read_text(encoding="utf-8"))
    assert len(capabilities) == 1
    assert capabilities[0]["status"] == "revoked"


def test_batch_endpoints_smoke(devx_client):
    client, env = devx_client
    create_user_fixture(env["users_root"], "USER5")
    create_user_fixture(env["users_root"], "USER6")

    dry = client.post(
        "/devx/api/users/batch/dry-run",
        json={"user_ids": ["USER5", "USER6"]},
    )
    assert dry.status_code == 200

    resp = client.post(
        "/devx/api/users/batch/run-holistic",
        json={"user_ids": ["USER5", "USER6"]},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    process = client.post(
        "/devx/api/users/batch/run-holistic/process",
        json={"job_id": job_id},
    )
    assert process.status_code == 200
    assert len(process.json()["results"]) == 2
