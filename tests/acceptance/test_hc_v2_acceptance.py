#!/usr/bin/env python3
"""
Head Coach v2 Sprint 1a Acceptance Tests
=========================================

Tests for HC v2 Phase A features:
1. Task Runner (queue, tick, state transitions)
2. Reminders (schedule, tick, task enqueueing)
3. UCNRR Client (mock mode)
4. Feature flags integration
"""

import json
import requests
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "http://localhost:8001"
TEST_USER = "hc_v2_demo"


def cleanup_test_user():
    """Remove test user data."""
    user_dir = Path("data/users") / TEST_USER
    if user_dir.exists():
        import shutil
        shutil.rmtree(user_dir)
    print(f"✓ Cleaned up test user: {TEST_USER}")


def test_1_feature_flags():
    """Test 1: Feature flags endpoint"""
    print("\n" + "="*70)
    print("TEST 1: Feature Flags")
    print("="*70)

    response = requests.get(f"{BASE_URL}/hc/flags")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    flags = response.json()

    print("✓ Flags endpoint successful")
    print(f"  - enable_task_runner: {flags.get('enable_task_runner', False)}")
    print(f"  - enable_reminders: {flags.get('enable_reminders', False)}")
    print(f"  - enable_ucnrr: {flags.get('enable_ucnrr', False)}")

    assert "enable_task_runner" in flags, "Missing enable_task_runner flag"
    assert "enable_reminders" in flags, "Missing enable_reminders flag"
    assert "enable_ucnrr" in flags, "Missing enable_ucnrr flag"

    print("✓ All expected flags present")

    return flags


def test_2_task_runner():
    """Test 2: Task Runner (queue → tick → state transitions)"""
    print("\n" + "="*70)
    print("TEST 2: Task Runner (Queue → Tick → State Transitions)")
    print("="*70)

    # Enqueue a task
    print("\n[Step 1] Enqueue task...")
    response = requests.post(
        f"{BASE_URL}/hc/tasks/queue",
        params={"user_id": TEST_USER},
        json={
            "title": "Reduce uncertainty for Freckles",
            "action": "add_evidence",
            "args": {"trait": "PaDNA.SkinDNA.Freckles.Density"},
            "eta_mins": 2,
            "provenance": {"source": "test", "reason": "acceptance test"}
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    task = response.json()

    print(f"✓ Task enqueued: {task['id']}")
    print(f"  - Title: {task['title']}")
    print(f"  - State: {task['state']}")
    print(f"  - Action: {task['action']}")

    assert task["state"] == "queued", f"Expected 'queued', got {task['state']}"

    task_id = task["id"]

    # List tasks
    print("\n[Step 2] List tasks...")
    response = requests.get(
        f"{BASE_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    data = response.json()
    tasks = data.get("tasks", [])

    print(f"✓ Listed {len(tasks)} task(s)")
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}"

    # Tick (execute task)
    print("\n[Step 3] Tick (execute task)...")
    response = requests.post(
        f"{BASE_URL}/hc/tasks/tick",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    result = response.json()

    print(f"✓ Tick executed")
    print(f"  - Executed: {result.get('executed', False)}")
    if result.get("executed"):
        print(f"  - Task ID: {result['task']['id']}")
        print(f"  - Final state: {result['task']['state']}")

    assert result["executed"] == True, "Task should have been executed"
    assert result["task"]["id"] == task_id, "Wrong task executed"

    # Verify state transition
    print("\n[Step 4] Verify state transition...")
    response = requests.get(
        f"{BASE_URL}/hc/tasks/list",
        params={"user_id": TEST_USER, "state": "done"}
    )

    assert response.status_code == 200
    data = response.json()
    done_tasks = data.get("tasks", [])

    print(f"✓ Found {len(done_tasks)} done task(s)")
    assert len(done_tasks) == 1, f"Expected 1 done task, got {len(done_tasks)}"
    assert done_tasks[0]["id"] == task_id, "Task ID mismatch"

    print("\n✅ Task Runner test passed")

    return task_id


def test_3_reminders():
    """Test 3: Reminders (schedule → tick → task enqueueing)"""
    print("\n" + "="*70)
    print("TEST 3: Reminders (Schedule → Tick → Task Enqueueing)")
    print("="*70)

    # Schedule a reminder (due 1 second ago to ensure it's immediate)
    print("\n[Step 1] Schedule reminder...")
    due_time = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()

    response = requests.post(
        f"{BASE_URL}/hc/reminders/schedule",
        params={"user_id": TEST_USER},
        json={
            "title": "Morning snapshot reminder",
            "when_iso": due_time,
            "action": "morning_snapshot",
            "args": {}
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    reminder = response.json()

    print(f"✓ Reminder scheduled: {reminder['id']}")
    print(f"  - Title: {reminder['title']}")
    print(f"  - Due: {reminder['when_iso']}")
    print(f"  - Action: {reminder['action']}")

    reminder_id = reminder["id"]

    # List reminders
    print("\n[Step 2] List reminders...")
    response = requests.get(
        f"{BASE_URL}/hc/reminders/list",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    data = response.json()
    reminders = data.get("reminders", [])

    print(f"✓ Listed {len(reminders)} reminder(s)")
    assert len(reminders) >= 1, f"Expected at least 1 reminder"

    # Tick reminders (should enqueue task)
    print("\n[Step 3] Tick reminders...")
    response = requests.post(
        f"{BASE_URL}/hc/reminders/tick",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    result = response.json()

    print(f"✓ Reminders tick executed")
    print(f"  - Executed: {result.get('executed', False)}")
    print(f"  - Count: {result.get('count', 0)}")
    print(f"  - Enqueued task IDs: {result.get('enqueued_task_ids', [])}")

    assert result["executed"] == True, "Should have processed reminders"
    assert result["count"] >= 1, "Should have enqueued at least 1 task"

    enqueued_task_id = result["enqueued_task_ids"][0] if result["enqueued_task_ids"] else None
    assert enqueued_task_id, "Should have enqueued a task"

    # Verify task was enqueued
    print("\n[Step 4] Verify task was enqueued...")
    response = requests.get(
        f"{BASE_URL}/hc/tasks/list",
        params={"user_id": TEST_USER, "state": "queued"}
    )

    assert response.status_code == 200
    data = response.json()
    queued_tasks = data.get("tasks", [])

    print(f"✓ Found {len(queued_tasks)} queued task(s)")

    # Find the enqueued task
    enqueued_task = next((t for t in queued_tasks if t["id"] == enqueued_task_id), None)
    assert enqueued_task, f"Enqueued task {enqueued_task_id} not found"

    print(f"✓ Task enqueued from reminder")
    print(f"  - Task ID: {enqueued_task['id']}")
    print(f"  - Title: {enqueued_task['title']}")
    print(f"  - Provenance: {enqueued_task.get('provenance', {})}")

    # Verify provenance links back to reminder
    provenance = enqueued_task.get("provenance", {})
    assert provenance.get("source") == "reminder", "Provenance should indicate 'reminder'"
    assert provenance.get("reminder_id") == reminder_id, "Provenance should link to reminder ID"

    print("\n✅ Reminders test passed")

    return reminder_id, enqueued_task_id


def test_4_hc_state_v2():
    """Test 4: HC State endpoint includes v2 features"""
    print("\n" + "="*70)
    print("TEST 4: HC State v2 (Flags, Tasks, Reminders)")
    print("="*70)

    response = requests.get(
        f"{BASE_URL}/hc/state",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    state = response.json()

    print("✓ HC State endpoint successful")

    # Check v2 features
    assert "flags" in state, "Missing 'flags' in state"
    assert "tasks" in state, "Missing 'tasks' in state"
    assert "reminders" in state, "Missing 'reminders' in state"

    print("\n✓ v2 features present in state:")
    print(f"  - Flags: {list(state['flags'].keys())}")
    print(f"  - Tasks queued: {len(state['tasks'].get('queued', []))}")
    print(f"  - Tasks done: {len(state['tasks'].get('done', []))}")
    print(f"  - Reminders pending: {len(state['reminders'])}")

    # Verify tasks structure
    tasks = state["tasks"]
    assert "queued" in tasks, "Missing 'queued' in tasks"
    assert "running" in tasks, "Missing 'running' in tasks"
    assert "done" in tasks, "Missing 'done' in tasks"
    assert "failed" in tasks, "Missing 'failed' in tasks"

    print("\n✓ Tasks structure correct")

    print("\n✅ HC State v2 test passed")

    return state


def run_all_tests():
    """Run all acceptance tests."""
    print("\n" + "#"*70)
    print("# HEAD COACH v2 SPRINT 1a ACCEPTANCE TESTS")
    print("#"*70)

    # Cleanup before tests
    cleanup_test_user()

    try:
        # Run tests
        flags = test_1_feature_flags()
        task_id = test_2_task_runner()
        reminder_id, enqueued_task_id = test_3_reminders()
        state = test_4_hc_state_v2()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)
        print("\nHC v2 Sprint 1a core features are working:")
        print("  ✓ Feature flags")
        print("  ✓ Task runner (queue → tick → done)")
        print("  ✓ Reminders (schedule → tick → enqueue task)")
        print("  ✓ HC state v2 integration")

        print("\nNext steps for Sprint 1b:")
        print("  - UI components (hc-tasks.tsx, panel updates)")
        print("  - Conversation memory (/hc/say)")
        print("  - Playbook runner integration")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
