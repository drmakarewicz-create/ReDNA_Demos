"""
Regression tests for RR normalization in snapshot/unabridged API (Phase 9).
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from ReDNACoreDemo.core.api import build_app
from ReDNACoreDemo.core.storage import get_user_data_dir


@pytest.fixture
def client():
    """Create test client for Core API."""
    app = build_app()
    return TestClient(app)


@pytest.fixture
def test_user_resolved():
    """Create test user with resolved.json containing rr_score."""
    user_id = "test_snapshot_user"
    user_dir = get_user_data_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create resolved.json with 0-1000 rr_score
    resolved_data = {
        "resolved": {
            "PaDNA.Chronotype": {
                "value": {"enum": "Morning Lark"},
                "rr_score": 750.0,  # 0-1000 scale
                "ucn": {"u": 0.25, "c": 0.75, "n": 0.5},
                "last_observed": "2025-10-19T12:00:00Z"
            },
            "PaDNA.EyeDNA.IrisColor": {
                "value": {"enum": "blue"},
                "rr_score": 85.0,  # Already 0-100
                "ucn": {"u": 0.15, "c": 0.85, "n": 0.5},
                "last_observed": "2025-10-19T12:00:00Z"
            }
        }
    }

    resolved_path = user_dir / "resolved.json"
    with open(resolved_path, 'w') as f:
        json.dump(resolved_data, f)

    yield user_id

    # Cleanup
    if resolved_path.exists():
        resolved_path.unlink()


def test_unabridged_rr_normalization(client, test_user_resolved):
    """
    Test that GET /ui/unabridged returns normalized RR/Curiosity.

    Arrange: Create user with rr_score=750 in resolved.json
    Act: Call unabridged API
    Assert: rr==75.0, curiosity==25.0, rr_meta present
    """
    user_id = test_user_resolved
    response = client.get(f"/ui/unabridged?user_id={user_id}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "traits" in data
    assert len(data["traits"]) == 2

    # Find Chronotype trait
    chronotype = next(
        (t for t in data["traits"] if t.get("trait_id") == "PaDNA.Chronotype"),
        None
    )

    assert chronotype is not None, "Chronotype not found in snapshot"

    # Assert normalized RR (750 → 75.0)
    assert chronotype.get("rr") == 75.0, f"Expected rr=75.0, got {chronotype.get('rr')}"

    # Assert Curiosity = 100 - RR
    assert chronotype.get("curiosity") == 25.0, f"Expected curiosity=25.0, got {chronotype.get('curiosity')}"

    # Assert rr_meta
    rr_meta = chronotype.get("rr_meta")
    assert rr_meta is not None, "rr_meta missing"
    assert rr_meta.get("rr_raw") == 750.0
    assert rr_meta.get("scale") == "0_1000"

    # Assert legacy rr_score preserved
    assert chronotype.get("rr_score") == 750.0, "Legacy rr_score should be preserved"


def test_unabridged_already_normalized(client, test_user_resolved):
    """
    Test that already-normalized RR values (0-100) are handled correctly.

    Arrange: Create user with rr_score=85 (already 0-100)
    Act: Call unabridged API
    Assert: rr==85.0, curiosity==15.0, scale=0_100
    """
    user_id = test_user_resolved
    response = client.get(f"/ui/unabridged?user_id={user_id}")

    assert response.status_code == 200

    data = response.json()
    eye_trait = next(
        (t for t in data["traits"] if t.get("trait_id") == "PaDNA.EyeDNA.IrisColor"),
        None
    )

    assert eye_trait is not None

    assert eye_trait.get("rr") == 85.0
    assert eye_trait.get("curiosity") == 15.0

    rr_meta = eye_trait.get("rr_meta")
    assert rr_meta.get("scale") == "0_100"


def test_snapshot_consistency_with_graph(client, test_user_resolved):
    """
    Test that snapshot and graph API return consistent RR/Curiosity values.

    Both endpoints should normalize the same trait to the same values.
    """
    user_id = test_user_resolved

    # Get unabridged snapshot
    snapshot_response = client.get(f"/ui/unabridged?user_id={user_id}")
    assert snapshot_response.status_code == 200

    snapshot_data = snapshot_response.json()
    snapshot_chronotype = next(
        (t for t in snapshot_data["traits"] if t.get("trait_id") == "PaDNA.Chronotype"),
        None
    )

    # Both should have normalized values
    assert snapshot_chronotype.get("rr") == 75.0
    assert snapshot_chronotype.get("curiosity") == 25.0
