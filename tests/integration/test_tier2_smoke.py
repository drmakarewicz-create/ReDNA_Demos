"""
Tier-2 Integration Smoke Tests

Ensures env-gated Tier-2 traits can be promoted when toggles are enabled.

Requirements:
- Core service running locally
- UCNRR stack available (Phase 4 warmup)
- Individual Tier-2 toggles enabled before running each case
"""

import os
import pytest
import requests
import time
from typing import Dict, Any, Optional

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8004")

TIER2_TEST_CASES = [
    {
        "trait": "Chronotype",
        "text": "I'm a morning person, up before sunrise every weekday.",
        "expected_trait_id": "BehaviorDNA.Sleep.Chronotype",
        "expected_value": "morning",
        "env_toggle": "PROMOTE_ENABLE_CHRONO",
    },
    {
        "trait": "Diet",
        "text": "I don't eat meat at all—strictly vegetarian.",
        "expected_trait_id": "BehaviorDNA.Health.Diet",
        "expected_value": "vegetarian",
        "env_toggle": "PROMOTE_ENABLE_DIET",
    },
    {
        "trait": "Work Location",
        "text": "I work from home full time in a remote role.",
        "expected_trait_id": "BehaviorDNA.Work.Location",
        "expected_value": "remote",
        "env_toggle": "PROMOTE_ENABLE_WORKLOC",
    },
    {
        "trait": "Social Group Size",
        "text": "Quiet weekends at home, I prefer small group dinners.",
        "expected_trait_id": "PreferenceDNA.Social.GroupSize",
        "expected_value": "small",
        "env_toggle": "PROMOTE_ENABLE_GROUPSIZE",
    },
    {
        "trait": "Exercise Type",
        "text": "I run every morning before work; running is my therapy.",
        "expected_trait_id": "BehaviorDNA.Exercise.Type",
        "expected_value": "running",
        "env_toggle": "PROMOTE_ENABLE_EXERCISE_TYPE",
    },
]


def check_trait_enabled(env_toggle: str) -> bool:
    return os.getenv(env_toggle, "false").lower() in ("true", "1", "yes", "on")


def ingest_text(user_id: str, text: str, timeout: int = 30) -> bool:
    try:
        resp = requests.post(
            f"{CORE_BASE}/core/api/ingest_text",
            json={
                "user_id": user_id,
                "text": text,
                "source": "tier2_smoke_test",
            },
            timeout=timeout,
        )
        return resp.status_code == 200
    except requests.RequestException as exc:
        print(f"Ingest failed: {exc}")
        return False


def get_snapshot(user_id: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(f"{CORE_BASE}/users/{user_id}/snapshot", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException as exc:
        print(f"Snapshot fetch failed: {exc}")
        return None


@pytest.mark.parametrize("test_case", TIER2_TEST_CASES, ids=lambda tc: tc["trait"])
def test_tier2_promotions(test_case: Dict[str, Any]) -> None:
    env_toggle = test_case["env_toggle"]
    if not check_trait_enabled(env_toggle):
        pytest.skip(f"{test_case['trait']} promotion disabled ({env_toggle}=false)")

    user_id = f"tier2_smoke_{test_case['trait'].lower().replace(' ', '_')}_{int(time.time())}"

    assert ingest_text(user_id, test_case["text"]), f"Failed ingest for {test_case['trait']}"

    time.sleep(2)

    snapshot = get_snapshot(user_id)
    assert snapshot is not None, f"Snapshot missing for user {user_id}"

    traits = snapshot.get("traits", {})
    expected_trait_id = test_case["expected_trait_id"]
    assert expected_trait_id in traits, f"{expected_trait_id} not found. Traits: {list(traits.keys())}"

    value = traits[expected_trait_id].get("value")
    assert value == test_case["expected_value"], f"Unexpected value for {expected_trait_id}: {value}"


def test_core_health() -> None:
    try:
        resp = requests.get(f"{CORE_BASE}/health", timeout=5)
        assert resp.status_code == 200, "Core health check failed"

        data = resp.json()
        assert data.get("status") == "healthy", "Core status not healthy"

        rr_mode = data.get("rr_mode", "").lower()
        assert rr_mode in ("online", "degraded"), f"UCNRR not ready (rr_mode={rr_mode})"
    except requests.RequestException as exc:
        pytest.fail(f"Could not reach Core at {CORE_BASE}: {exc}")


if __name__ == "__main__":
    import sys

    print("Tier-2 Smoke Tests")
    print("=" * 60)

    print("\nChecking Core health...")
    test_core_health()

    for case in TIER2_TEST_CASES:
        try:
            test_tier2_promotions(case)
        except pytest.skip.Exception as skip_exc:
            print(f"⊘ Skipped: {skip_exc}")
        except AssertionError as err:
            print(f"✗ Failed: {err}")
            sys.exit(1)

    print("\nAll Tier-2 smoke tests passed.")
