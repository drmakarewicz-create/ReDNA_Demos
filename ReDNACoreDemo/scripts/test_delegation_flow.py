#!/usr/bin/env python3
"""
Quick-start script to test the complete delegation flow.

This script demonstrates the full delegation lifecycle:
1. Analyze curiosity → recommend coach
2. Create delegation
3. Switch to specialized coach mode
4. Simulate trait collection
5. Complete delegation with auto-return
6. Verify results

Usage:
    python scripts/test_delegation_flow.py
"""

import json
import sys
import time
from pathlib import Path

import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

API_BASE = "http://localhost:8000"
TEST_USER_ID = "delegation_test_user_123"

# ANSI colors for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, description):
    """Print a step header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}STEP {step_num}: {description}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(message):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_info(message):
    """Print info message."""
    print(f"{Colors.BLUE}→ {message}{Colors.END}")

def print_error(message):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_json(data, title=None):
    """Pretty print JSON data."""
    if title:
        print(f"{Colors.YELLOW}{title}:{Colors.END}")
    print(json.dumps(data, indent=2))

def check_api_health():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     DELEGATION SYSTEM - END-TO-END FLOW TEST              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(Colors.END)

    # Check API is running
    print_info("Checking API health...")
    if not check_api_health():
        print_error(f"API is not running at {API_BASE}")
        print_info("Start the API with: cd ReDNACoreDemo && ../.venv/bin/python -m uvicorn core.api:app --reload")
        sys.exit(1)
    print_success("API is running")

    # ================================================================
    # STEP 1: Analyze Curiosity
    # ================================================================
    print_step(1, "Analyze Curiosity for Delegation Recommendation")

    curiosity_data = {
        "PaDNA.HairDNA.Color": 92.0,
        "PaDNA.HairDNA.Texture": 85.0,
        "PaDNA.EyeDNA.Color": 88.0,
        "PaDNA.SkinDNA.Tone": 78.0,
        "ReDNA.AttachmentStyle.Type": 65.0,
    }

    print_info(f"Analyzing curiosity for user: {TEST_USER_ID}")
    print_json(curiosity_data, "Curiosity Data")

    analyze_response = requests.post(
        f"{API_BASE}/delegation/analyze",
        json={
            "user_id": TEST_USER_ID,
            "curiosity_data": curiosity_data,
            "tolerance": 0.7
        }
    )

    analyze_data = analyze_response.json()

    if analyze_data.get("should_delegate"):
        print_success(f"Delegation recommended: {analyze_data['recommended_coach']}")
        print_info(f"Priority items: {len(analyze_data['priority_items'])}")
        for item in analyze_data['priority_items']:
            print(f"  • {item['path']}: {item['curiosity']:.1f}% curiosity")
    else:
        print_info("No delegation recommended (curiosity not high enough)")
        return

    recommended_coach = analyze_data['recommended_coach']
    curiosity_targets = [item['path'] for item in analyze_data['priority_items']]

    time.sleep(1)

    # ================================================================
    # STEP 2: Create Delegation
    # ================================================================
    print_step(2, "Create Delegation Record")

    print_info(f"Creating delegation to {recommended_coach}...")
    print_info(f"Curiosity targets: {curiosity_targets}")

    create_response = requests.post(
        f"{API_BASE}/delegation/create",
        json={
            "user_id": TEST_USER_ID,
            "coach_id": recommended_coach,
            "curiosity_targets": curiosity_targets,
            "context": {
                "delegation_reason": "user_accepted_recommendation",
                "test_run": True,
            }
        }
    )

    create_data = create_response.json()

    if create_data.get("ok"):
        delegation_id = create_data["delegation"]["delegation_id"]
        print_success(f"Delegation created: {delegation_id}")
        print_json(create_data["delegation"], "Delegation Record")
    else:
        print_error(f"Failed to create delegation: {create_data.get('message')}")
        return

    time.sleep(1)

    # ================================================================
    # STEP 3: Switch to Specialized Coach Mode
    # ================================================================
    print_step(3, "Switch to Specialized Coach Mode")

    # First check current mode
    current_mode_response = requests.get(f"{API_BASE}/users/{TEST_USER_ID}/coach-mode")
    current_mode_data = current_mode_response.json()
    print_info(f"Current mode: {current_mode_data['active_mode']}")

    # Convert coach_id to mode name
    mode_map = {
        "photo_coach": "photo",
        "relationship_coach": "relationship",
        "head_coach": "head_coach"
    }
    target_mode = mode_map.get(recommended_coach, recommended_coach)

    print_info(f"Switching to {target_mode} mode with delegation context...")

    switch_response = requests.post(
        f"{API_BASE}/users/{TEST_USER_ID}/coach-mode",
        json={
            "target_mode": target_mode,
            "delegation_id": delegation_id,
            "context": {
                "curiosity_targets": curiosity_targets
            }
        }
    )

    switch_data = switch_response.json()

    if switch_data.get("ok"):
        print_success(f"Switched from {switch_data['previous_mode']} → {switch_data['new_mode']}")
        print_info(f"Mode info: {switch_data['mode_info']['display_name']} {switch_data['mode_info']['emoji']}")
    else:
        print_error(f"Failed to switch mode: {switch_data.get('message')}")
        return

    time.sleep(1)

    # ================================================================
    # STEP 4: Simulate Specialized Coach Collecting Traits
    # ================================================================
    print_step(4, "Simulate Trait Collection (Photo Coach)")

    print_info("Simulating specialized coach conversation...")
    print_info("In real scenario, coach would analyze photo and collect traits")

    # Simulate collected traits with before/after curiosity
    traits_collected = curiosity_targets[:3]  # Collect first 3 traits
    curiosity_before = {path: curiosity_data[path] for path in traits_collected}
    curiosity_after = {
        traits_collected[0]: 12.0,  # Highly satisfied
        traits_collected[1]: 15.0,  # Highly satisfied
        traits_collected[2]: 20.0,  # Moderately satisfied
    }

    print_success(f"Collected {len(traits_collected)} traits:")
    for trait in traits_collected:
        before = curiosity_before[trait]
        after = curiosity_after[trait]
        reduction = ((before - after) / before) * 100
        print(f"  • {trait}: {before:.1f} → {after:.1f} ({reduction:.0f}% satisfied)")

    time.sleep(1)

    # ================================================================
    # STEP 5: Complete Delegation with Auto-Return
    # ================================================================
    print_step(5, "Complete Delegation & Return to Head Coach")

    notes = f"Analyzed {len(traits_collected)} visual traits from photo. High-quality data collected."

    print_info("Marking delegation as complete with auto-return...")

    complete_response = requests.post(
        f"{API_BASE}/delegation/{TEST_USER_ID}/complete/{delegation_id}",
        json={
            "traits_collected": traits_collected,
            "curiosity_before": curiosity_before,
            "curiosity_after": curiosity_after,
            "notes": notes,
            "auto_return": True
        }
    )

    complete_data = complete_response.json()

    if complete_data.get("ok"):
        summary = complete_data["delegation_summary"]
        satisfaction = summary["curiosity_satisfied"] * 100

        print_success("Delegation completed successfully!")
        print_info(f"Traits collected: {summary['traits_collected_count']}")
        print_info(f"Curiosity satisfied: {satisfaction:.1f}%")

        if satisfaction >= 80:
            print(f"{Colors.GREEN}★ Excellent result! 🎉{Colors.END}")
        elif satisfaction >= 60:
            print(f"{Colors.BLUE}★ Good result!{Colors.END}")

        # Check mode switch
        if complete_data.get("mode_switch"):
            mode_switch = complete_data["mode_switch"]
            print_success(f"Returned to {mode_switch['new_mode']} mode")
        else:
            print_info("Stayed in specialized coach mode (auto_return was false)")
    else:
        print_error(f"Failed to complete delegation: {complete_data.get('message')}")
        return

    time.sleep(1)

    # ================================================================
    # STEP 6: Verify Final State
    # ================================================================
    print_step(6, "Verify Final State")

    # Check current mode
    final_mode_response = requests.get(f"{API_BASE}/users/{TEST_USER_ID}/coach-mode")
    final_mode_data = final_mode_response.json()
    print_info(f"Current mode: {final_mode_data['active_mode']}")

    # Check delegation status
    status_response = requests.get(f"{API_BASE}/delegation/{TEST_USER_ID}/status/{delegation_id}")
    status_data = status_response.json()

    if status_data.get("ok"):
        status = status_data["status"]
        print_success(f"Delegation status: {status['status']}")
        print_info(f"Curiosity satisfied: {status['curiosity_satisfied'] * 100:.1f}%")
        print_info(f"Traits collected: {len(status['traits_collected'])}")

    # Check mode history
    history_response = requests.get(f"{API_BASE}/users/{TEST_USER_ID}/coach-mode/history?limit=5")
    history_data = history_response.json()

    if history_data.get("ok"):
        print_info(f"Recent mode transitions: {len(history_data['history'])}")
        for i, transition in enumerate(history_data['history'][-2:]):
            print(f"  {i+1}. {transition['from_mode']} → {transition['to_mode']}")

    # Check mode stats
    stats_response = requests.get(f"{API_BASE}/users/{TEST_USER_ID}/coach-mode/stats")
    stats_data = stats_response.json()

    if stats_data.get("ok"):
        stats = stats_data["stats"]
        print_info(f"Total mode transitions: {stats['total_transitions']}")
        print_info(f"Most used mode: {stats['most_used_mode']}")

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    TEST COMPLETE ✓                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(Colors.END)

    print(f"\n{Colors.GREEN}All steps completed successfully!{Colors.END}\n")

    print(f"{Colors.BOLD}Summary:{Colors.END}")
    print(f"  • User ID: {TEST_USER_ID}")
    print(f"  • Delegation ID: {delegation_id}")
    print(f"  • Coach: {recommended_coach} ({target_mode} mode)")
    print(f"  • Traits collected: {len(traits_collected)}")
    print(f"  • Satisfaction: {satisfaction:.1f}%")
    print(f"  • Final mode: {final_mode_data['active_mode']}")

    print(f"\n{Colors.YELLOW}Next steps:{Colors.END}")
    print("  1. Check the delegation record in data/users/")
    print("  2. View mode history and stats via API")
    print("  3. Integrate UI components into your app")
    print("  4. Test with real LLM conversations")

    print(f"\n{Colors.CYAN}Useful commands:{Colors.END}")
    print(f"  • View delegation: curl {API_BASE}/delegation/{TEST_USER_ID}/status/{delegation_id}")
    print(f"  • View mode: curl {API_BASE}/users/{TEST_USER_ID}/coach-mode")
    print(f"  • View history: curl {API_BASE}/users/{TEST_USER_ID}/coach-mode/history")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
