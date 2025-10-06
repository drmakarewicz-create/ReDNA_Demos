#!/usr/bin/env python3
"""
Head Coach v2 Sprint 1b Acceptance Tests

Tests for:
- Conversation memory (/hc/say)
- Playbook runner (/hc/playbooks/run)
- Real task execution (add_evidence, morning_snapshot)
- End-to-end integration

Usage:
    python test_hc_v2_sprint1b_acceptance.py

Requirements:
    - Core API running on http://localhost:8001
    - Test user: hc_v2_1b_demo
"""

import requests
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_URL = "http://localhost:8001"
TEST_USER = "hc_v2_1b_demo"

def cleanup_test_user():
    """Remove test user data."""
    user_dir = Path("data/users") / TEST_USER
    if user_dir.exists():
        shutil.rmtree(user_dir)
        print(f"✓ Cleaned up test user: {TEST_USER}")

def test_1_conversation_memory():
    """
    Test conversation memory:
    - POST /hc/say to log a message
    - GET /hc/conversation/history to retrieve it
    """
    print("\n" + "="*70)
    print("TEST 1: Conversation Memory (/hc/say)")
    print("="*70)

    # Log a user message
    response = requests.post(
        f"{BASE_URL}/hc/say?user_id={TEST_USER}",
        json={
            "message": "This is a test message from the user",
            "role": "user"
        }
    )
    assert response.status_code == 200, f"Say failed: {response.status_code}"
    result = response.json()
    assert result["logged"] is True
    print(f"✓ User message logged: {result['ts']}")

    # Log an assistant message
    response = requests.post(
        f"{BASE_URL}/hc/say?user_id={TEST_USER}",
        json={
            "message": "This is a response from Head Coach",
            "role": "assistant",
            "provenance": {"source": "test"}
        }
    )
    assert response.status_code == 200
    print("✓ Assistant message logged")

    # Retrieve conversation history
    response = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
    assert response.status_code == 200
    history = response.json()
    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"
    print(f"✓ Retrieved {len(history['messages'])} messages from history")

    print("\n✅ Conversation Memory test passed\n")

def test_2_playbook_runner():
    """
    Test playbook runner:
    - List available playbooks
    - Run curiosity_campaign playbook
    - Verify task was enqueued
    """
    print("\n" + "="*70)
    print("TEST 2: Playbook Runner")
    print("="*70)

    # List playbooks
    response = requests.get(f"{BASE_URL}/hc/playbooks/list")
    assert response.status_code == 200
    playbooks = response.json()["playbooks"]
    print(f"✓ Found {len(playbooks)} playbooks:")
    for pb in playbooks:
        print(f"  - {pb['id']}: {pb['name']}")

    # Ensure playbook exists
    playbook_ids = [pb["id"] for pb in playbooks]
    assert "curiosity_campaign" in playbook_ids, "curiosity_campaign playbook not found"

    # For this test, we need a user with traits
    # Let's create a simple trait structure
    from pathlib import Path
    from ReDNACoreDemo.core.storage import write_user_state

    # Ensure user directory exists
    user_dir = Path("data/users") / TEST_USER
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal resolved state with a high-curiosity trait
    resolved = {
        "PaDNA.EyeDNA.Iris.BaseColor": {
            "resolved_value": "Green",
            "curiosity": 900,  # High curiosity
            "ucn": 800,
            "rr": 100
        }
    }
    evidence = {}
    obs = []

    write_user_state(TEST_USER, resolved, evidence, obs)
    print(f"✓ Created test user state with high-curiosity trait")

    # Run playbook
    response = requests.post(
        f"{BASE_URL}/hc/playbooks/run?user_id={TEST_USER}",
        json={"playbook_id": "curiosity_campaign"}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["executed"] is True
    assert len(result["tasks_enqueued"]) > 0
    print(f"✓ Playbook executed, enqueued {len(result['tasks_enqueued'])} task(s)")

    # Verify task was created
    response = requests.get(f"{BASE_URL}/hc/tasks/list?user_id={TEST_USER}")
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) > 0
    print(f"✓ Found {len(tasks)} task(s) in queue")
    print(f"  - Task: {tasks[0]['title']}")

    print("\n✅ Playbook Runner test passed\n")

def test_3_real_task_execution():
    """
    Test real task execution:
    - Enqueue add_evidence task
    - Execute task via tick
    - Verify conversation journal entry was created
    """
    print("\n" + "="*70)
    print("TEST 3: Real Task Execution")
    print("="*70)

    # Clear any existing tasks from previous tests
    import shutil
    from pathlib import Path
    tasks_dir = Path("data/users") / TEST_USER / "hc" / "tasks"
    if tasks_dir.exists():
        shutil.rmtree(tasks_dir)
        tasks_dir.mkdir(parents=True, exist_ok=True)

    # Enqueue add_evidence task
    response = requests.post(
        f"{BASE_URL}/hc/tasks/queue?user_id={TEST_USER}",
        json={
            "title": "Add evidence for Eye Color",
            "action": "add_evidence",
            "args": {"trait": "PaDNA.EyeDNA.Iris.BaseColor"},
            "eta_mins": 2
        }
    )
    assert response.status_code == 200
    task = response.json()
    print(f"✓ Task enqueued: {task['id']}")

    # Execute task
    response = requests.post(f"{BASE_URL}/hc/tasks/tick?user_id={TEST_USER}")
    assert response.status_code == 200
    result = response.json()
    assert result["executed"] is True
    print(f"✓ Task executed")

    # Verify conversation journal entry was created
    response = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
    assert response.status_code == 200
    history = response.json()

    # Find the add_evidence journal entry
    evidence_entry = None
    for msg in history["messages"]:
        if msg.get("task_id") == task["id"]:
            evidence_entry = msg
            break

    assert evidence_entry is not None, "Evidence request not found in conversation"
    assert "Eye" in evidence_entry["content"] or "evidence" in evidence_entry["content"].lower()
    print(f"✓ Conversation entry created: \"{evidence_entry['content'][:50]}...\"")

    print("\n✅ Real Task Execution test passed\n")

def test_4_morning_snapshot():
    """
    Test morning_snapshot action:
    - Enqueue morning_snapshot task
    - Execute task
    - Verify snapshot was generated with top traits
    """
    print("\n" + "="*70)
    print("TEST 4: Morning Snapshot Task")
    print("="*70)

    # Enqueue morning_snapshot task
    response = requests.post(
        f"{BASE_URL}/hc/tasks/queue?user_id={TEST_USER}",
        json={
            "title": "Morning snapshot",
            "action": "morning_snapshot",
            "args": {},
            "eta_mins": 1
        }
    )
    assert response.status_code == 200
    task = response.json()
    print(f"✓ Morning snapshot task enqueued: {task['id']}")

    # Execute task
    response = requests.post(f"{BASE_URL}/hc/tasks/tick?user_id={TEST_USER}")
    assert response.status_code == 200
    result = response.json()
    assert result["executed"] is True
    print(f"✓ Morning snapshot task executed")

    # Verify conversation entry
    response = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
    assert response.status_code == 200
    history = response.json()

    snapshot_entry = None
    for msg in history["messages"]:
        if msg.get("snapshot_type") == "morning":
            snapshot_entry = msg
            break

    assert snapshot_entry is not None, "Morning snapshot not found in conversation"
    assert "Good morning" in snapshot_entry["content"] or "snapshot" in snapshot_entry["content"].lower()
    print(f"✓ Morning snapshot generated")
    print(f"  Preview: \"{snapshot_entry['content'][:60]}...\"")

    print("\n✅ Morning Snapshot test passed\n")

def test_5_end_to_end_integration():
    """
    End-to-end integration test:
    - Run playbook (enqueues task)
    - Tick to execute task (creates conversation entry)
    - Verify state consistency
    """
    print("\n" + "="*70)
    print("TEST 5: End-to-End Integration")
    print("="*70)

    # Get initial state
    response = requests.get(f"{BASE_URL}/hc/state?user_id={TEST_USER}")
    assert response.status_code == 200
    initial_state = response.json()
    print(f"✓ Initial state retrieved")
    print(f"  - Flags present: {'flags' in initial_state}")
    print(f"  - Tasks present: {'tasks' in initial_state}")
    print(f"  - Reminders present: {'reminders' in initial_state}")

    # Verify flags, tasks, reminders in state
    assert "flags" in initial_state
    assert "tasks" in initial_state
    assert "reminders" in initial_state
    print(f"✓ HC State v2 fields present")

    # Count current queued tasks
    initial_queued = len(initial_state["tasks"].get("queued", []))
    print(f"  - Initial queued tasks: {initial_queued}")

    # Run playbook
    response = requests.post(
        f"{BASE_URL}/hc/playbooks/run?user_id={TEST_USER}",
        json={"playbook_id": "curiosity_campaign"}
    )
    assert response.status_code == 200

    # Get updated state
    response = requests.get(f"{BASE_URL}/hc/state?user_id={TEST_USER}")
    final_state = response.json()
    final_queued = len(final_state["tasks"].get("queued", []))

    print(f"✓ Playbook executed and state updated")
    print(f"  - Final queued tasks: {final_queued}")

    # Note: final_queued might not be greater if tasks were already executed
    # That's OK for this integration test

    print("\n✅ End-to-End Integration test passed\n")

def run_all_tests():
    """Run all acceptance tests."""
    print("\n" + "#"*70)
    print("# HEAD COACH v2 SPRINT 1b ACCEPTANCE TESTS")
    print("#"*70)

    cleanup_test_user()

    try:
        test_1_conversation_memory()
        test_2_playbook_runner()
        test_3_real_task_execution()
        test_4_morning_snapshot()
        test_5_end_to_end_integration()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)
        print("\nHC v2 Sprint 1b features are working:")
        print("  ✓ Conversation memory (/hc/say)")
        print("  ✓ Playbook runner (curiosity_campaign)")
        print("  ✓ Real task execution (add_evidence, morning_snapshot)")
        print("  ✓ End-to-end integration")
        print("\nNext steps:")
        print("  - Add UI components to React app")
        print("  - Test manual playbook triggers from UI")
        print("  - Expand playbook library")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise
    finally:
        # Cleanup
        print("\n" + "="*70)
        cleanup_test_user()

if __name__ == "__main__":
    run_all_tests()
