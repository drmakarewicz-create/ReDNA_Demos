"""
Integration tests for Why-Card promotion pipeline.

Requires live Core + UCNRR services.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional

import pytest
import requests

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8004")


def _fetch_envvars() -> Dict[str, Optional[str]]:
    try:
        resp = requests.get(f"{CORE_BASE}/core/api/debug/envvars", timeout=5)
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except requests.RequestException:
        pass
    return {}


@pytest.fixture
def live_core():
    try:
        health = requests.get(f"{CORE_BASE}/health", timeout=3)
        health.raise_for_status()
    except requests.RequestException:
        pytest.skip(f"Core service not reachable at {CORE_BASE}")
    return CORE_BASE


def _restore_chrono(enable_value: Optional[str], rr_min_value: Optional[str]) -> None:
    try:
        if enable_value is not None:
            requests.post(
                f"{CORE_BASE}/core/api/debug/set_toggle",
                json={"key": "PROMOTE_ENABLE_CHRONO", "value": enable_value},
                timeout=5,
            )
        else:
            requests.post(
                f"{CORE_BASE}/core/api/debug/set_toggle",
                json={"trait": "CHRONO", "enable": False},
                timeout=5,
            )
        if rr_min_value is not None:
            requests.post(
                f"{CORE_BASE}/core/api/debug/set_toggle",
                json={"key": "RR_PROMOTE_MIN_CHRONO", "value": rr_min_value},
                timeout=5,
            )
    except requests.RequestException:
        pass


def test_chronotype_whycards(live_core):
    before_env = _fetch_envvars()
    prior_enable = before_env.get("PROMOTE_ENABLE_CHRONO")
    prior_rr_min = before_env.get("RR_PROMOTE_MIN_CHRONO")

    toggle_payload = {"trait": "CHRONO", "enable": True, "rr_min": 780}
    try:
        toggle_resp = requests.post(
            f"{live_core}/core/api/debug/set_toggle",
            json=toggle_payload,
            timeout=5,
        )
        assert toggle_resp.status_code == 200

        data = toggle_resp.json()
        assert "updated" in data and data["updated"], "Toggle update did not report changes"

        user_id = f"whycard_{int(time.time())}"
        phrase = "I am a morning person, up before sunrise."

        ingest_resp = requests.post(
            f"{live_core}/core/api/ingest_text",
            json={"user_id": user_id, "text": phrase, "source": "whycard_test"},
            timeout=10,
        )
        assert ingest_resp.status_code == 200
        ingest_data = ingest_resp.json()
        rescore = ingest_data.get("rescore", {})
        assert "BehaviorDNA.Sleep.Chronotype" in (rescore.get("rr_by_trait") or {}), \
            "Chronotype promotion not present in rescore payload"

        # Allow file write to settle
        time.sleep(0.5)

        why_resp = requests.get(
            f"{live_core}/core/api/traits/BehaviorDNA.Sleep.Chronotype/why",
            params={"user_id": user_id},
            timeout=5,
        )
        assert why_resp.status_code == 200
        why_data = why_resp.json()
        assert why_data.get("user_id") == user_id
        assert "morning" in (why_data.get("why") or "").lower()
    finally:
        _restore_chrono(prior_enable, prior_rr_min)
