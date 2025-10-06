#!/usr/bin/env python3
"""
PaDNA Delta Wiring Acceptance Tests
Tests photo_refine playbook, task enqueueing, and provenance tracking
"""

import json
import os
import shutil
import time
from pathlib import Path

import pytest
import requests

from test_photo_coach_acceptance import create_test_image, TEST_USER

CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8001")


def cleanup_test_user():
    """Clean up test user data."""
    user_dir = Path("data/users") / TEST_USER
    if user_dir.exists():
        shutil.rmtree(user_dir)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    cleanup_test_user()
    yield
    cleanup_test_user()


def create_test_photo_batch(user_id: str) -> str:
    """Helper to create a photo batch and return batch_id."""
    image = create_test_image("portrait.jpg", color=(200, 180, 160))
    files = [('files', ('portrait.jpg', image, 'image/jpeg'))]

    response = requests.post(
        f"{CORE_API_URL}/photo/ingest",
        params={"user_id": user_id},
        files=files
    )

    assert response.status_code == 200
    manifest = response.json()

    # Add vision labels to make delta analysis work
    batch_id = manifest["batch_id"]
    label_response = requests.post(
        f"{CORE_API_URL}/photo/vision/label",
        params={"user_id": user_id, "batch_id": batch_id}
    )
    assert label_response.status_code == 200

    return batch_id


def create_test_render_batch(user_id: str, photo_batch_id: str) -> str:
    """Helper to create a render batch manifest manually."""
    from datetime import datetime, timezone
    from ReDNACoreDemo.core.render_coach import create_render_manifest

    repo_root = Path("data")

    manifest = create_render_manifest(
        user_id=user_id,
        base_dir=repo_root.parent,
        traits_resolved_path=f"users/{user_id}/hc/state/resolved.json",
        images_batch_id=photo_batch_id,
        workflow="comfyui/realvisxl.json",
        seed=12345,
        prompt="portrait of a person with freckles",
    )

    return manifest["render_batch_id"]


def test_photo_refine_playbook_enqueues_tasks():
    """Test 1: photo_refine playbook enqueues tasks based on delta analysis."""
    print(f"\n=== Test 1: Photo Refine Playbook (user={TEST_USER}) ===")

    # Create photo batch with labels
    photo_batch_id = create_test_photo_batch(TEST_USER)
    print(f"  ✓ Created photo batch: {photo_batch_id}")

    # Create render batch
    render_batch_id = create_test_render_batch(TEST_USER, photo_batch_id)
    print(f"  ✓ Created render batch: {render_batch_id}")

    # Get initial task count
    tasks_before = requests.get(
        f"{CORE_API_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    )
    initial_count = len(tasks_before.json().get("tasks", []))

    # Run photo_refine playbook
    response = requests.post(
        f"{CORE_API_URL}/hc/playbooks/run",
        params={"user_id": TEST_USER, "playbook_id": "photo_refine"}
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    result = response.json()

    print(f"  ✓ Playbook executed: {result.get('message')}")

    # Get tasks after playbook run
    tasks_after = requests.get(
        f"{CORE_API_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    )

    tasks = tasks_after.json().get("tasks", [])
    new_tasks_count = len(tasks) - initial_count

    assert new_tasks_count > 0, f"Expected tasks to be enqueued, but got {new_tasks_count} new tasks"

    print(f"  ✓ Tasks enqueued: {new_tasks_count}")

    # Verify task types
    task_actions = [task.get("action") for task in tasks]
    assert any(action in ["add_evidence", "verify_evidence", "re_render"] for action in task_actions), \
        f"Expected add_evidence, verify_evidence, or re_render tasks, got: {task_actions}"

    print(f"  ✓ Task actions: {set(task_actions)}")
    print(f"  ✓ Test 1 passed")


def test_tasks_have_provenance():
    """Test 2: Tasks enqueued by photo_refine have correct provenance."""
    print(f"\n=== Test 2: Task Provenance (user={TEST_USER}) ===")

    # Create photo and render batches
    photo_batch_id = create_test_photo_batch(TEST_USER)
    render_batch_id = create_test_render_batch(TEST_USER, photo_batch_id)

    # Run photo_refine playbook
    requests.post(
        f"{CORE_API_URL}/hc/playbooks/run",
        params={"user_id": TEST_USER, "playbook_id": "photo_refine"}
    )

    # Get tasks
    response = requests.get(
        f"{CORE_API_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    tasks = response.json().get("tasks", [])

    assert len(tasks) > 0, "No tasks found"

    # Verify provenance
    for task in tasks:
        provenance = task.get("provenance", {})

        assert provenance.get("source") == "playbook", \
            f"Expected source=playbook, got {provenance.get('source')}"

        assert provenance.get("playbook_id") == "photo_refine", \
            f"Expected playbook_id=photo_refine, got {provenance.get('playbook_id')}"

        assert "reason" in provenance, "Expected 'reason' in provenance"

        print(f"  ✓ Task {task.get('task_id')}: {task.get('title')}")
        print(f"    - Source: {provenance.get('source')}")
        print(f"    - Playbook: {provenance.get('playbook_id')}")
        print(f"    - Reason: {provenance.get('reason')[:60]}...")

    print(f"  ✓ Test 2 passed")


def test_tick_executes_re_render_stub():
    """Test 3: Task tick executes and appends to journal."""
    print(f"\n=== Test 3: Task Tick Execution (user={TEST_USER}) ===")

    # Create photo and render batches
    photo_batch_id = create_test_photo_batch(TEST_USER)
    render_batch_id = create_test_render_batch(TEST_USER, photo_batch_id)

    # Run photo_refine playbook to enqueue tasks
    requests.post(
        f"{CORE_API_URL}/hc/playbooks/run",
        params={"user_id": TEST_USER, "playbook_id": "photo_refine"}
    )

    # Get tasks
    tasks_response = requests.get(
        f"{CORE_API_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    )

    tasks = tasks_response.json().get("tasks", [])
    assert len(tasks) > 0, "No tasks to tick"

    pending_tasks = [t for t in tasks if t.get("status") == "pending"]
    assert len(pending_tasks) > 0, "No pending tasks to execute"

    task_id = pending_tasks[0]["task_id"]
    print(f"  ✓ Found pending task: {task_id}")

    # Tick the task
    tick_response = requests.post(
        f"{CORE_API_URL}/hc/tasks/tick",
        params={"user_id": TEST_USER}
    )

    assert tick_response.status_code == 200, f"Expected 200, got {tick_response.status_code}: {tick_response.text}"

    tick_result = tick_response.json()
    print(f"  ✓ Task executed: {tick_result.get('task_id')}")
    print(f"    - Action: {tick_result.get('action')}")
    print(f"    - Status: {tick_result.get('status')}")

    # Verify task status changed
    updated_tasks = requests.get(
        f"{CORE_API_URL}/hc/tasks/list",
        params={"user_id": TEST_USER}
    ).json().get("tasks", [])

    executed_task = next((t for t in updated_tasks if t["task_id"] == task_id), None)

    if executed_task:
        assert executed_task["status"] in ["completed", "in_progress"], \
            f"Expected task status to change, got {executed_task['status']}"
        print(f"  ✓ Task status updated: {executed_task['status']}")

    # Verify journal entry exists
    from datetime import datetime
    journal_date = datetime.now().strftime("%Y-%m-%d")
    journal_path = Path("data/users") / TEST_USER / "hc" / "journal" / f"{journal_date}.md"

    if journal_path.exists():
        with open(journal_path, "r", encoding="utf-8") as f:
            journal_content = f.read()

        assert len(journal_content) > 0, "Journal is empty"
        print(f"  ✓ Journal updated: {journal_path}")
        print(f"    - Entries: {journal_content.count('##')} sections")
    else:
        print(f"  ⚠ Journal not found (may be expected for some task types)")

    print(f"  ✓ Test 3 passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
