from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from ReDNACoreDemo.core.api import build_app
from ReDNACoreDemo.core.storage import USERS_DIR, CHECKPOINTS_DIR


def test_ingest_text_alias(tmp_path):
    app = build_app()
    client = TestClient(app)

    user_id = "pytest_compat"
    payload = {"user_id": user_id, "text": "alias smoke"}

    response = client.post("/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # Legacy endpoint returns \"ok\" flag
    assert "ok" in data

    # Cleanup generated user data
    for root in (USERS_DIR, CHECKPOINTS_DIR):
        target = Path(root) / user_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
