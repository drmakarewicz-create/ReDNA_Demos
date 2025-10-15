"""
CORS Headers Regression Test

Ensures that Core API responds with correct Access-Control-Allow-Origin
headers for local UI development servers.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the Core API."""
    from ReDNACoreDemo.core.api import build_app
    app = build_app()
    return TestClient(app)


def test_cors_headers_localhost_3000(client):
    """Ensure Access-Control-Allow-Origin header is present for localhost:3000."""
    origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == origin, f"Expected {origin}, got {allow_origin}"


def test_cors_headers_127_3001(client):
    """Ensure Access-Control-Allow-Origin header is present for 127.0.0.1:3001."""
    origin = "http://127.0.0.1:3001"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == origin, f"Expected {origin}, got {allow_origin}"


def test_cors_headers_preview_4173(client):
    """Ensure Access-Control-Allow-Origin header is present for preview port 4173."""
    origin = "http://127.0.0.1:4173"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == origin, f"Expected {origin}, got {allow_origin}"


def test_cors_headers_devx_vite(client):
    """Ensure Access-Control-Allow-Origin header is present for DevX Vite ports."""
    origin = "http://127.0.0.1:3100"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == origin, f"Expected {origin}, got {allow_origin}"


def test_cors_preflight_request(client):
    """Ensure CORS preflight (OPTIONS) requests are handled correctly."""
    origin = "http://localhost:3000"
    response = client.options(
        "/ui/chat/send",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )

    # OPTIONS request should return 200
    assert response.status_code == 200

    # Should have CORS headers
    assert response.headers.get("access-control-allow-origin") == origin
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_credentials_allowed(client):
    """Ensure Access-Control-Allow-Credentials is set to true."""
    origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    allow_credentials = response.headers.get("access-control-allow-credentials")
    assert allow_credentials == "true", f"Expected 'true', got {allow_credentials}"


def test_cors_headers_not_set_for_unknown_origin(client):
    """Ensure CORS headers are not set for origins not in the allowlist."""
    origin = "http://evil.com"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200

    # Should not have allow-origin header for non-allowed origin
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin is None or allow_origin != origin
