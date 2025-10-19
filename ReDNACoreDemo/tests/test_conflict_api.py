import importlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    # Redirect calibration and storage to temporary paths
    calibration_module = importlib.import_module('ReDNACoreDemo.core.conflict.calibration')
    importlib.reload(calibration_module)
    monkeypatch.setattr(calibration_module, 'CALIBRATION_PATH', tmp_path / 'calibration.json', raising=False)

    storage_module = importlib.import_module('ReDNACoreDemo.core.conflict.storage')
    importlib.reload(storage_module)

    def temp_user_log(user_id: str):
        base = tmp_path / user_id
        base.mkdir(parents=True, exist_ok=True)
        return base / 'conflict_log.jsonl'

    monkeypatch.setattr(storage_module, '_user_log_path', temp_user_log, raising=False)

    api_module = importlib.import_module('ReDNACoreDemo.core.api')
    importlib.reload(api_module)
    app = api_module.build_app()
    return TestClient(app)


def test_conflict_simulation_flow(api_client):
    payload = {
        "conflict": {
            "user_id": "TEST",
            "kind": "trait",
            "severity": "low",
            "path": "SkillDNA.sample_trait",
        },
        "evidence": [
            {
                "evidence_id": "u1",
                "source_type": "user_assertion",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": "user report",
                "provenance": {"support": 1.0},
                "assertion_text": "user report",
            },
            {
                "evidence_id": "c1",
                "source_type": "core",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": 0.8,
                "provenance": {"support": -1.0},
            },
        ],
    }

    response = api_client.post('/conflicts/simulate', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] in {'auto_resolved', 'resolved'}
    conflict_id = data['conflict_id']

    list_response = api_client.get('/conflicts/list')
    assert list_response.status_code == 200
    conflicts = list_response.json().get('conflicts', [])
    assert any(entry['conflict_id'] == conflict_id for entry in conflicts)

    stats_response = api_client.get('/conflicts/stats')
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats['total'] >= 1
    assert 'auto_resolved' in stats['by_status']
