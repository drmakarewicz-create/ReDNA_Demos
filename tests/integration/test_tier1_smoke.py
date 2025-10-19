"""
Tier-1 Integration Smoke Tests

Quick sanity checks that each Tier-1 trait (Hair, Age, Relationship, Height)
can be extracted and appears in snapshot.traits with a non-null value.

These tests require:
- Core service running
- UCNRR online (local Ollama)
- Tier-1 trait toggles enabled in .env
"""

import os
import pytest
import requests
import time
from typing import Dict, Any, Optional


# Core API base
CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8004")

# Test data for each Tier-1 trait
TIER1_TEST_CASES = [
    {
        "trait": "Hair Color",
        "text": "I have brown hair",
        "expected_trait_id": "PaDNA.HairDNA.Color",
        "env_toggle": "PROMOTE_ENABLE_HAIR",
    },
    {
        "trait": "Age",
        "text": "I am 28 years old",
        "expected_trait_id": "GenDNA.AgeDNA.AgeYears",
        "env_toggle": "PROMOTE_ENABLE_AGE",
    },
    {
        "trait": "Relationship Status",
        "text": "I am in a long-term relationship",
        "expected_trait_id": "ReDNA.RelationshipStatus",
        "env_toggle": "PROMOTE_ENABLE_REL",
    },
    {
        "trait": "Height",
        "text": "I am 5 feet 10 inches tall",
        "expected_trait_id": "PaDNA.PhysDNA.Height",
        "env_toggle": "PROMOTE_ENABLE_HEIGHT",
    },
]


def check_trait_enabled(trait_name: str, env_toggle: str) -> bool:
    """Check if trait promotion is enabled in environment."""
    value = os.getenv(env_toggle, "false").lower()
    return value in ("true", "1", "yes", "on")


def ingest_text(user_id: str, text: str, timeout: int = 30) -> bool:
    """
    Send text to Core ingest API.

    Returns True if successful, False otherwise.
    """
    try:
        resp = requests.post(
            f"{CORE_BASE}/core/api/ingest_text",
            json={
                "user_id": user_id,
                "text": text,
                "source": "tier1_smoke_test",
            },
            timeout=timeout
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"Ingest failed: {e}")
        return False


def get_snapshot(user_id: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Fetch user snapshot from Core.

    Returns snapshot dict or None if not found.
    """
    try:
        resp = requests.get(
            f"{CORE_BASE}/users/{user_id}/snapshot",
            timeout=timeout
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException as e:
        print(f"Snapshot fetch failed: {e}")
        return None


@pytest.mark.parametrize("test_case", TIER1_TEST_CASES, ids=lambda tc: tc["trait"])
def test_tier1_trait_extraction(test_case: Dict[str, Any]):
    """
    Test that a Tier-1 trait can be extracted and appears in snapshot.

    This test:
    1. Checks if the trait's promotion toggle is enabled
    2. Sends a test phrase to Core ingest
    3. Waits briefly for processing
    4. Fetches the snapshot and verifies the trait is present

    If the trait toggle is disabled, the test is skipped.
    """
    trait = test_case["trait"]
    text = test_case["text"]
    expected_trait_id = test_case["expected_trait_id"]
    env_toggle = test_case["env_toggle"]

    # Check if trait is enabled
    if not check_trait_enabled(trait, env_toggle):
        pytest.skip(f"{trait} promotion not enabled ({env_toggle}=false)")

    # Generate unique user ID
    user_id = f"tier1_smoke_{trait.lower().replace(' ', '_')}_{int(time.time())}"

    # Ingest text
    print(f"\nTesting {trait}: '{text}'")
    assert ingest_text(user_id, text), f"Failed to ingest text for {trait}"

    # Wait for processing (UCNRR + resolver)
    time.sleep(2)

    # Fetch snapshot
    snapshot = get_snapshot(user_id)
    assert snapshot is not None, f"Snapshot not found for user {user_id}"

    # Check if trait is in snapshot
    traits = snapshot.get("traits", {})
    assert expected_trait_id in traits, \
        f"{trait} ({expected_trait_id}) not found in snapshot.traits. Available: {list(traits.keys())}"

    # Verify value is not null
    trait_data = traits[expected_trait_id]
    value = trait_data.get("value")
    assert value is not None, f"{trait} value is null"

    print(f"✓ {trait} extracted successfully: {value}")


def test_core_health():
    """Verify Core service is healthy before running smoke tests."""
    try:
        resp = requests.get(f"{CORE_BASE}/health", timeout=5)
        assert resp.status_code == 200, "Core health check failed"

        data = resp.json()
        assert data.get("status") == "healthy", "Core status not healthy"

        rr_mode = data.get("rr_mode", "").lower()
        assert rr_mode in ("online", "degraded"), \
            f"UCNRR not available (rr_mode={rr_mode})"

        print(f"✓ Core healthy (rr_mode={rr_mode})")

    except requests.RequestException as e:
        pytest.fail(f"Could not connect to Core at {CORE_BASE}: {e}")


if __name__ == "__main__":
    # Allow running directly for quick testing
    import sys

    print("Tier-1 Smoke Tests")
    print("=" * 60)

    # Check Core health
    print("\nChecking Core health...")
    test_core_health()

    # Run each test case
    for test_case in TIER1_TEST_CASES:
        try:
            test_tier1_trait_extraction(test_case)
        except pytest.skip.Exception as e:
            print(f"⊘ Skipped: {e}")
        except AssertionError as e:
            print(f"✗ Failed: {e}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print("All smoke tests passed!")
