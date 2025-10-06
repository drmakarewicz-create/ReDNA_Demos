from __future__ import annotations

from fastapi.testclient import TestClient

from ReDNACoreDemo.core.api import build_app


def _client() -> TestClient:
    return TestClient(build_app())


def test_health() -> None:
    client = _client()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "healthy"
    assert body.get("service") == "core"


def test_create_and_list_users() -> None:
    client = _client()
    create = client.post("/ui/user/create", json={"user_id": "test_user_smoke"})
    assert create.status_code in (200, 409)
    listing = client.get("/ui/users")
    assert listing.status_code == 200
    payload = listing.json()
    assert "users" in payload


def test_media_upload_rejection_surface() -> None:
    client = _client()
    files = {"file": ("bad.txt", b"xxx", "text/plain")}
    data = {"user_id": "TEST"}
    response = client.post("/ui/media/upload", files=files, data=data)
    assert response.status_code in (200, 400, 413, 415)
