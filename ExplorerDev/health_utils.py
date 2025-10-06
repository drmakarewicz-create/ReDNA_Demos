"""Helper utilities for Dev Explorer health checks."""

from __future__ import annotations

import requests


def check_health(base_url: str | None, timeout: float = 0.75) -> bool:
    """Return True if `/health` responds with HTTP 200; otherwise False (no raise)."""

    if not base_url:
        return False

    base = base_url.strip()
    if not base:
        return False

    url = base.rstrip("/") + "/health"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return False
    return response.status_code == 200
