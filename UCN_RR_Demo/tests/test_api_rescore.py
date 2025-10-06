# UCN_RR_Demo/tests/test_api_rescore.py
"""
Unit tests for /api/rescore endpoint.
Tests curiosity calculation formula and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from ucnrr_app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_rescore_happy_path_multiple_traits(client):
    """Test rescore with multiple traits returns RR and curiosity."""
    payload = {
        "user_id": "test_user_001",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 850.0},
            {"id": "PaDNA.HairDNA.Color", "value": "Red", "rr": 650.0},
            {"id": "PsyDNA.PersonalityTraits.Openness", "value": 0.8, "rr": 750.0},
        ],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["ok"] is True
    assert data["user_id"] == "test_user_001"
    assert "rr_by_trait" in data
    assert "curiosity_by_trait" in data
    assert "global_curiosity" in data

    # Check that all traits are present
    assert "PaDNA.EyeDNA.IrisColor" in data["rr_by_trait"]
    assert "PaDNA.HairDNA.Color" in data["rr_by_trait"]
    assert "PsyDNA.PersonalityTraits.Openness" in data["rr_by_trait"]

    # Check RR values are returned correctly
    assert data["rr_by_trait"]["PaDNA.EyeDNA.IrisColor"] == 850.0
    assert data["rr_by_trait"]["PaDNA.HairDNA.Color"] == 650.0
    assert data["rr_by_trait"]["PsyDNA.PersonalityTraits.Openness"] == 750.0

    # Check curiosity values are calculated (0-1 range)
    for trait_id, curiosity in data["curiosity_by_trait"].items():
        assert 0.0 <= curiosity <= 1.0

    # Global curiosity should be average
    assert 0.0 <= data["global_curiosity"] <= 1.0


def test_rescore_empty_traits_list(client):
    """Test rescore with empty traits list returns 400."""
    payload = {
        "user_id": "test_user_002",
        "traits": [],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 400
    assert "No traits provided" in response.json()["detail"]


def test_rescore_malformed_payload_no_user_id(client):
    """Test rescore without user_id returns 422 (validation error)."""
    payload = {
        "traits": [{"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 850.0}],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 422


def test_rescore_unknown_trait_uses_fallback(client):
    """Test rescore with unknown trait path uses fallback weight."""
    payload = {
        "user_id": "test_user_003",
        "traits": [
            {"id": "UnknownDNA.SomeTrait.Value", "value": "Test", "rr": 500.0},
        ],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["ok"] is True
    assert "UnknownDNA.SomeTrait.Value" in data["curiosity_by_trait"]
    # Curiosity should be calculated using fallback weight
    assert 0.0 <= data["curiosity_by_trait"]["UnknownDNA.SomeTrait.Value"] <= 1.0


def test_rescore_with_recency_boost(client):
    """Test curiosity calculation increases with days_since_update."""
    base_payload = {
        "user_id": "test_user_004",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 700.0, "days_since_update": 0},
        ],
    }

    response_base = client.post("/api/rescore", json=base_payload)
    data_base = response_base.json()
    curiosity_base = data_base["curiosity_by_trait"]["PaDNA.EyeDNA.IrisColor"]

    # Same trait with older update should have higher curiosity
    aged_payload = {
        "user_id": "test_user_004",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 700.0, "days_since_update": 30},
        ],
    }

    response_aged = client.post("/api/rescore", json=aged_payload)
    data_aged = response_aged.json()
    curiosity_aged = data_aged["curiosity_by_trait"]["PaDNA.EyeDNA.IrisColor"]

    # Older trait should have higher curiosity (recency boost)
    assert curiosity_aged > curiosity_base


def test_rescore_with_tolerance_factor(client):
    """Test curiosity calculation varies with user tolerance."""
    low_tolerance_payload = {
        "user_id": "test_user_005",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 700.0, "tolerance": 0.2},
        ],
    }

    response_low = client.post("/api/rescore", json=low_tolerance_payload)
    data_low = response_low.json()
    curiosity_low = data_low["curiosity_by_trait"]["PaDNA.EyeDNA.IrisColor"]

    high_tolerance_payload = {
        "user_id": "test_user_005",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 700.0, "tolerance": 0.8},
        ],
    }

    response_high = client.post("/api/rescore", json=high_tolerance_payload)
    data_high = response_high.json()
    curiosity_high = data_high["curiosity_by_trait"]["PaDNA.EyeDNA.IrisColor"]

    # Lower tolerance should result in higher curiosity
    assert curiosity_low > curiosity_high


def test_rescore_text_extraction(client):
    """Test rescore can extract traits from text."""
    payload = {
        "user_id": "test_user_006",
        "text": "PaDNA.EyeDNA.IrisColor=Blue\nPaDNA.HairDNA.Color=Brown",
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["ok"] is True
    assert "PaDNA.EyeDNA.IrisColor" in data["rr_by_trait"]
    assert "PaDNA.HairDNA.Color" in data["rr_by_trait"]


def test_rescore_trait_with_invalid_rr(client):
    """Test rescore handles invalid RR values gracefully."""
    payload = {
        "user_id": "test_user_007",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": "invalid"},
        ],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Should use default RR of 500.0
    assert data["rr_by_trait"]["PaDNA.EyeDNA.IrisColor"] == 500.0


def test_rescore_rr_clamping(client):
    """Test RR values are clamped to 0-1000 range."""
    payload = {
        "user_id": "test_user_008",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 1500.0},  # Too high
            {"id": "PaDNA.HairDNA.Color", "value": "Red", "rr": -100.0},  # Too low
        ],
    }

    response = client.post("/api/rescore", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Values should be clamped
    assert data["rr_by_trait"]["PaDNA.EyeDNA.IrisColor"] == 1000.0
    assert data["rr_by_trait"]["PaDNA.HairDNA.Color"] == 0.0


def test_rescore_global_curiosity_average(client):
    """Test global_curiosity is correctly averaged across traits."""
    payload = {
        "user_id": "test_user_009",
        "traits": [
            {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 800.0},
            {"id": "PaDNA.HairDNA.Color", "value": "Red", "rr": 600.0},
        ],
    }

    response = client.post("/api/rescore", json=payload)
    data = response.json()

    # Calculate expected average
    curiosities = list(data["curiosity_by_trait"].values())
    expected_avg = sum(curiosities) / len(curiosities)

    # Should be close (allowing for rounding)
    assert abs(data["global_curiosity"] - expected_avg) < 0.001
