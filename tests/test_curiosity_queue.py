from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest
from fastapi.testclient import TestClient

import ReDNACoreDemo.core.api as core_api
from ReDNACoreDemo.core.curiosity import store as curiosity_store


@pytest.fixture
def curiosity_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Configure curiosity storage to use a temporary directory and return a TestClient.
    """
    data_root = tmp_path / "data"
    users_root = data_root / "users"
    users_root.mkdir(parents=True, exist_ok=True)

    def _ensure_dirs_for_user(user_id: str):
        user_dir = users_root / user_id
        events_dir = user_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        return {
            "udir": user_dir,
            "events": events_dir,
        }

    monkeypatch.setattr(core_api, "ensure_dirs_for_user", _ensure_dirs_for_user)
    monkeypatch.setattr(core_api, "ENABLE_CURIOSITY_LOOP", True)
    monkeypatch.setattr(core_api, "CURIOSITY_MAX_OPEN_PER_USER", 50)
    monkeypatch.setattr(core_api, "CURIOSITY_MAX_OPEN_PER_TRAIT", 10)
    monkeypatch.setattr(core_api, "CURIOSITY_COOLDOWN_SEC", 0)

    monkeypatch.setattr(curiosity_store, "ensure_dirs_for_user", _ensure_dirs_for_user)
    curiosity_store._ITEM_INDEX.clear()
    curiosity_store._ITEM_CACHE.clear()

    app = core_api.build_app()
    client = TestClient(app)
    return client, users_root


def _enqueue_payload(user_id: str) -> Dict[str, object]:
    return {
        "user_id": user_id,
        "trait_id": "BehaviorDNA.Sleep.Chronotype",
        "reason_code": "low_confidence",
        "inputs": {
            "rr": 720.0,
            "base_rr": 780.0,
            "learned_rr": 750.0,
            "p": 0.55,
            "curiosity": 0.5,
            "impact_weight": 0.75,
        },
        "context": {"cooldown_sec": 0},
        "suggested_question": "Quick check—are you mainly a morning person?",
        "expected_information_gain": 0.7,
    }


def test_curiosity_enqueue_and_flow(curiosity_setup):
    client, users_root = curiosity_setup
    user_id = "curiosity_user"
    payload = _enqueue_payload(user_id)

    resp = client.post("/core/api/curiosity/enqueue", json=payload)
    assert resp.status_code == 200, resp.text
    item = resp.json()
    assert item["status"] == "queued"
    assert item["expected_information_gain"] > 0
    item_id = item["id"]

    # Fetch queue
    resp = client.get(f"/core/api/curiosity?user_id={user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["id"] == item_id

    # Ack item
    resp = client.post(f"/core/api/curiosity/{item_id}/ack", json={})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify status persisted
    curiosity_file = users_root / user_id / "curiosity.jsonl"
    stored_item = json.loads(curiosity_file.read_text(encoding="utf-8").strip().splitlines()[0])
    assert stored_item["status"] == "asked"
    assert stored_item["asked_at"]

    # Answer item
    resp = client.post(
        f"/core/api/curiosity/{item_id}/answer",
        json={"answer_text": "Yes, I'm definitely a morning person."},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    lines = curiosity_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["status"] == "answered"

    # Curiosity answer should have triggered ingest and created an event file
    events_dir = (users_root / user_id / "events")
    assert any(events_dir.iterdir()), "expected curiosity answer to write an ingest event"


def test_curiosity_deduplication(curiosity_setup):
    client, _ = curiosity_setup
    user_id = "dedupe_user"
    payload = _enqueue_payload(user_id)
    payload["context"] = {"cooldown_sec": 604800}

    resp = client.post("/core/api/curiosity/enqueue", json=payload)
    assert resp.status_code == 200

    resp = client.post("/core/api/curiosity/enqueue", json=payload)
    assert resp.status_code == 409


def test_curiosity_per_user_cap(curiosity_setup, monkeypatch: pytest.MonkeyPatch):
    client, _ = curiosity_setup
    monkeypatch.setattr(core_api, "CURIOSITY_MAX_OPEN_PER_USER", 2)
    curiosity_store._ITEM_INDEX.clear()
    curiosity_store._ITEM_CACHE.clear()

    user_id = "cap_user"
    for idx in range(2):
        payload = _enqueue_payload(user_id)
        payload["inputs"]["rr"] = 700.0 + idx * 5
        resp = client.post("/core/api/curiosity/enqueue", json=payload)
        assert resp.status_code == 200

    payload = _enqueue_payload(user_id)
    payload["inputs"]["rr"] = 715.0
    resp = client.post("/core/api/curiosity/enqueue", json=payload)
    assert resp.status_code == 409
