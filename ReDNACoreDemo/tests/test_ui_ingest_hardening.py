# ReDNACoreDemo/tests/test_ui_ingest_hardening.py
"""
Tests for /ui/ingest/text and /ui/ingest/json endpoint hardening.
Verifies provenance logging, error resilience, and UCN/RR integration.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import requests


@pytest.fixture
def client():
    """FastAPI test client for Core API."""
    from ReDNACoreDemo.core.api import build_app
    app = build_app()
    return TestClient(app)


@pytest.fixture
def test_user():
    """Test user ID."""
    return "test-ingest-001"


def test_ingest_text_happy_path(client, test_user):
    """Test /ui/ingest/text with valid payload and successful UCN/RR response."""
    # Mock UCN/RR response
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "ok": True,
            "user_id": test_user,
            "rr_by_trait": {"PaDNA.EyeDNA.IrisColor": 850.0},
            "curiosity_by_trait": {"PaDNA.EyeDNA.IrisColor": 0.15},
            "global_curiosity": 0.15,
        }
        mock_post.return_value = mock_response

        payload = {
            "user_id": test_user,
            "text": "I have blue eyes",
            "source": "test",
        }

        response = client.post("/ui/ingest/text", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["user_id"] == test_user
        assert data["status"] == "accepted"
        assert "event_written" in data
        assert data["rescore"]["ok"] is True


def test_ingest_text_ucnrr_connection_error(client, test_user):
    """Test /ui/ingest/text handles UCN/RR connection error gracefully."""
    # Mock UCN/RR connection failure
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        payload = {
            "user_id": test_user,
            "text": "I have blue eyes",
        }

        response = client.post("/ui/ingest/text", json=payload)
        assert response.status_code == 200  # Should still succeed (provenance logged)

        data = response.json()
        assert data["ok"] is False  # Failed because UCN/RR unreachable
        assert data["status"] == "failed"
        assert "event_written" in data
        assert "Connection error" in data["rescore"]["error"]


def test_ingest_text_ucnrr_timeout(client, test_user):
    """Test /ui/ingest/text handles UCN/RR timeout gracefully."""
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        payload = {
            "user_id": test_user,
            "text": "I have brown hair",
        }

        response = client.post("/ui/ingest/text", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "Timeout" in data["rescore"]["error"]


def test_ingest_text_missing_user_id(client):
    """Test /ui/ingest/text rejects missing user_id."""
    payload = {
        "text": "I have blue eyes",
    }

    response = client.post("/ui/ingest/text", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "user_id" in data["message"]


def test_ingest_text_missing_text(client, test_user):
    """Test /ui/ingest/text rejects missing text."""
    payload = {
        "user_id": test_user,
    }

    response = client.post("/ui/ingest/text", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "text" in data["message"]


def test_ingest_json_happy_path(client, test_user):
    """Test /ui/ingest/json with valid payload and successful UCN/RR response."""
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "ok": True,
            "user_id": test_user,
            "rr_by_trait": {"PaDNA.EyeDNA.IrisColor": 900.0},
            "curiosity_by_trait": {"PaDNA.EyeDNA.IrisColor": 0.1},
            "global_curiosity": 0.1,
        }
        mock_post.return_value = mock_response

        payload = {
            "user_id": test_user,
            "traits": [
                {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 850.0},
            ],
            "source": "test",
        }

        response = client.post("/ui/ingest/json", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["user_id"] == test_user
        assert data["status"] == "accepted"
        assert data["traits_count"] == 1
        assert "event_written" in data


def test_ingest_json_ucnrr_http_error(client, test_user):
    """Test /ui/ingest/json handles UCN/RR HTTP error gracefully."""
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        payload = {
            "user_id": test_user,
            "traits": [
                {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 850.0},
            ],
        }

        response = client.post("/ui/ingest/json", json=payload)
        assert response.status_code == 200  # Provenance logged

        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "HTTP 500" in data["rescore"]["error"]


def test_ingest_json_missing_traits(client, test_user):
    """Test /ui/ingest/json rejects missing traits."""
    payload = {
        "user_id": test_user,
    }

    response = client.post("/ui/ingest/json", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "traits" in data["message"]


def test_ingest_json_malformed_payload(client):
    """Test /ui/ingest/json rejects non-dict payload."""
    response = client.post("/ui/ingest/json", json="not a dict")
    # FastAPI returns 422 for type validation errors, 400 for our manual checks
    assert response.status_code in (400, 422)

    data = response.json()
    # Accept either our error message or FastAPI validation error
    assert ("JSON object" in str(data.get("message", ""))) or ("detail" in data)


def test_ingest_text_provenance_always_logged(client, test_user):
    """Test provenance is logged even when UCN/RR fails."""
    with patch("ReDNACoreDemo.core.api.requests.post") as mock_post:
        mock_post.side_effect = Exception("Unexpected error")

        payload = {
            "user_id": test_user,
            "text": "I have green eyes",
        }

        response = client.post("/ui/ingest/text", json=payload)
        assert response.status_code == 200

        data = response.json()
        # Provenance should be logged even though UCN/RR failed
        assert "event_written" in data
        assert data["status"] == "failed"
        assert "Unexpected error" in data["rescore"]["error"]
