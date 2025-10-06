#!/usr/bin/env python3
"""
Test script for trait container discovery system.

Demonstrates:
1. User states various preferences (TV, food, lifestyle)
2. System auto-discovers new trait containers
3. Containers are registered and tracked
4. API endpoint shows discovered containers
"""

import json
import time
import requests

CORE_API_BASE = "http://127.0.0.1:8015"
TEST_USER_ID = "container_discovery_test"


def send_message(text: str) -> dict:
    """Send a message to Head Coach."""
    url = f"{CORE_API_BASE}/ui/chat/send"
    payload = {
        "user_id": TEST_USER_ID,
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


def get_discovered_containers() -> dict:
    """Get all discovered trait containers."""
    url = f"{CORE_API_BASE}/api/trait-containers"

    response = requests.get(url, timeout=10)
    data = response.json()

    return data


def print_containers(category_filter: str = None):
    """Print discovered containers."""
    url = f"{CORE_API_BASE}/api/trait-containers"
    if category_filter:
        url += f"?category={category_filter}"

    response = requests.get(url, timeout=10)
    data = response.json()

    containers = data.get("containers", {})
    stats = data.get("stats", {})

    print(f"\n{'='*80}")
    print(f"DISCOVERED TRAIT CONTAINERS")
    if category_filter:
        print(f"Category Filter: {category_filter}")
    print(f"{'='*80}")

    print(f"\n📊 STATS:")
    print(f"  Total Containers: {stats.get('total_containers', 0)}")
    print(f"  Sensitive Containers: {stats.get('sensitive_containers', 0)}")
    print(f"\n  By Category:")
    for cat, count in stats.get('by_category', {}).items():
        print(f"    - {cat}: {count}")
    print(f"\n  By Source:")
    for source, count in stats.get('by_source', {}).items():
        print(f"    - {source}: {count}")

    print(f"\n📦 CONTAINERS:")
    for path, meta in containers.items():
        category = meta.get("category", "Unknown")
        subcategory = meta.get("subcategory", "")
        description = meta.get("description", "")
        source = meta.get("source", "unknown")
        count = meta.get("observation_count", 0)
        sensitive = meta.get("sensitive", False)
        examples = meta.get("example_traits", [])

        sensitive_flag = " 🔒" if sensitive else ""
        print(f"\n  {path}{sensitive_flag}")
        print(f"    Category: {category} / {subcategory}")
        print(f"    Description: {description}")
        print(f"    Source: {source}")
        print(f"    Observations: {count}")
        if examples:
            print(f"    Examples: {', '.join(examples[:3])}")


def main():
    """Run container discovery test."""
    print("\n" + "="*80)
    print("TRAIT CONTAINER DISCOVERY TEST")
    print("="*80)

    # Phase 1: State diverse preferences to trigger container discovery
    print("\n🔍 PHASE 1: Stating diverse preferences to discover containers")
    print("-" * 80)

    # Entertainment preferences
    send_message("I love sci-fi movies and mystery novels")
    time.sleep(2)

    # Food preferences
    send_message("I prefer Italian cuisine and spicy food")
    time.sleep(2)

    # Lifestyle preferences
    send_message("I'm a morning person who exercises daily")
    time.sleep(2)

    # Music preferences
    send_message("I listen to jazz and classical music")
    time.sleep(2)

    # Physical attributes
    send_message("I have green eyes and curly hair")
    time.sleep(2)

    # Phase 2: Check discovered containers
    print("\n\n📦 PHASE 2: Checking discovered containers")
    print("-" * 80)

    print_containers()

    # Phase 3: Check specific categories
    print("\n\n🎯 PHASE 3: Filtering by specific categories")
    print("-" * 80)

    print("\n--- PREFERENCES ONLY ---")
    print_containers("Preferences")

    print("\n\n--- PHYSICAL ATTRIBUTES ONLY ---")
    print_containers("Physical Attributes")

    print("\n\n✅ TEST COMPLETE")
    print("="*80)
    print("\nExpected Results:")
    print("1. Multiple containers discovered under 'Preferences' category:")
    print("   - preferences.entertainment (movies, books)")
    print("   - preferences.food (cuisine types)")
    print("   - preferences.lifestyle (routines, habits)")
    print("   - preferences.music (genres)")
    print("2. Containers discovered under 'Physical Attributes':")
    print("   - attributes.physical (eye color, hair)")
    print("3. All containers tracked with observation counts")
    print("4. Containers persist across restarts in discovered_trait_containers.json")


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
