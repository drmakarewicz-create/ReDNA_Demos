#!/usr/bin/env python3
"""
Test script for bidirectional HC <-> Trait system.

This demonstrates:
1. User states preferences in conversation
2. HC extracts and stores preferences as traits
3. User asks for recommendations
4. HC retrieves traits and provides personalized response
"""

import json
import time
import requests
from pathlib import Path

CORE_API_BASE = "http://127.0.0.1:8015"
TEST_USER_ID = "trait_test_user"


def send_message(text: str, user_id: str = TEST_USER_ID) -> dict:
    """Send a message to Head Coach."""
    url = f"{CORE_API_BASE}/ui/chat/send"
    payload = {
        "user_id": user_id,
        "text": text,
        "persona": "head coach",
        "client_ts": int(time.time() * 1000)
    }

    print(f"\n{'='*80}")
    print(f"USER: {text}")
    print(f"{'='*80}")

    response = requests.post(url, json=payload, timeout=60)
    data = response.json()

    hc_response = data.get("text", "")
    print(f"HEAD COACH: {hc_response}")

    return data


def check_evidence(user_id: str = TEST_USER_ID) -> dict:
    """Check stored evidence for user."""
    evidence_path = Path(f"data/users/{user_id}/evidence.json")

    if not evidence_path.exists():
        print(f"\n⚠️  No evidence file found at {evidence_path}")
        return {}

    with open(evidence_path) as f:
        evidence = json.load(f)

    items = evidence.get("items", [])
    print(f"\n{'='*80}")
    print(f"STORED EVIDENCE ({len(items)} items):")
    print(f"{'='*80}")

    for idx, item in enumerate(items[-10:], 1):  # Show last 10
        trait_id = item.get("trait_id", "unknown")
        value = item.get("value", 0)
        confidence = item.get("confidence", 0)
        provenance = item.get("provenance", {})
        method = provenance.get("method", "unknown")
        signal = provenance.get("signal", "")

        print(f"{idx}. {trait_id} = {value} (confidence: {confidence}, method: {method})")
        if signal:
            print(f"   Signal: {signal}")

    return evidence


def check_resolved(user_id: str = TEST_USER_ID) -> dict:
    """Check resolved traits for user."""
    resolved_path = Path(f"data/users/{user_id}/resolved.json")

    if not resolved_path.exists():
        print(f"\n⚠️  No resolved file found at {resolved_path}")
        return {}

    with open(resolved_path) as f:
        data = json.load(f)

    resolved = data.get("resolved", {}) if isinstance(data, dict) and "resolved" in data else data

    print(f"\n{'='*80}")
    print(f"RESOLVED TRAITS ({len(resolved)} total):")
    print(f"{'='*80}")

    # Show preference traits
    pref_traits = {k: v for k, v in resolved.items() if "preferences" in k}
    if pref_traits:
        print("\nPreferences:")
        for trait_id, trait_data in list(pref_traits.items())[:10]:
            if isinstance(trait_data, dict):
                value = trait_data.get("value", "unknown")
                print(f"  - {trait_id}: {value}")

    return resolved


def main():
    """Run bidirectional trait test."""
    print("\n" + "="*80)
    print("BIDIRECTIONAL HC ↔ TRAIT SYSTEM TEST")
    print("="*80)

    # Test Phase 1: State preferences
    print("\n📥 PHASE 1: INGEST - User states preferences")
    print("-" * 80)

    send_message("I love comedies and sci-fi shows, but I really hate horror films")
    time.sleep(2)

    send_message("I'm also tall with brown hair")
    time.sleep(2)

    # Check what got stored
    print("\n🔍 Checking stored data after preference statements...")
    check_evidence()
    check_resolved()

    # Test Phase 2: Ask for recommendations
    print("\n\n📤 PHASE 2: RETRIEVE - User asks for recommendations")
    print("-" * 80)

    send_message("What TV show should I watch tonight?")
    time.sleep(2)

    # Check conversation again
    send_message("Any movie recommendations?")
    time.sleep(2)

    print("\n\n✅ TEST COMPLETE")
    print("="*80)
    print("\nExpected behavior:")
    print("1. Turn 1-2: HC extracts preferences (comedy=high, sci-fi=high, horror=low)")
    print("2. Evidence stored with 'llm_extraction' method")
    print("3. Turn 3-4: HC retrieves preferences and recommends comedies/sci-fi")
    print("4. HC should NOT recommend horror films")
    print("\nCheck the HC responses above to verify personalization!")


if __name__ == "__main__":
    try:
        # Check Core is running
        response = requests.get(f"{CORE_API_BASE}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Core API is not healthy")
            exit(1)

        print("✅ Core API is running")
        main()

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Core API. Is it running on port 8015?")
        exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit(0)
