import requests
import pytest


pytestmark = pytest.mark.e2e

UCNRR_BASE = "http://127.0.0.1:8011"


def _require_service():
    try:
        health = requests.get(f"{UCNRR_BASE}/health", timeout=2)
    except requests.RequestException as exc:  # pragma: no cover - environment driven
        pytest.skip(f"UCNRR health check failed: {exc}")
    if not health.ok:
        pytest.skip(f"UCNRR health returned {health.status_code}")


def test_ucnrr_selftest_online():
    _require_service()

    response = requests.get(f"{UCNRR_BASE}/ucnrr/selftest", timeout=3)
    assert response.ok

    payload = response.json()
    assert payload.get("ok") is True
