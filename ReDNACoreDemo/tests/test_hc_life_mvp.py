"""
Tests for Head Coach Life OS MVP.

Validates:
- Quick capture creates todos
- Summary returns aggregated data
- PATCH updates todos and goals
- Audit events are logged
- L2 daily nudge enqueues when today_three is empty
"""

import json
import pytest
from pathlib import Path
from dataclasses import asdict

from ReDNACoreDemo.core import hc_life
from ReDNACoreDemo.core.storage import USERS_DIR, CORE_DATA_ROOT


@pytest.fixture
def test_user():
    """Create a test user ID."""
    return "TEST_LIFE_USER"


@pytest.fixture
def clean_life_data(test_user):
    """Clean up life data before and after tests."""
    life_dir = USERS_DIR / test_user / "hc_life"
    if life_dir.exists():
        import shutil
        shutil.rmtree(life_dir)
    yield
    if life_dir.exists():
        import shutil
        shutil.rmtree(life_dir)


def test_capture_adds_todo(test_user, clean_life_data):
    """Test that quick capture creates a new todo."""
    # Create a todo
    todo = hc_life.Todo(
        id="",
        text="Call mentor",
        when="today",
        tags=["career"]
    )

    created = hc_life.create_todo(test_user, todo)

    # Verify it was created
    assert created.id.startswith("td_")
    assert created.text == "Call mentor"
    assert created.when == "today"
    assert "career" in created.tags
    assert created.created_at
    assert created.updated_at

    # Verify it appears in summary
    summary = hc_life.get_life_summary(test_user)
    assert len(summary["today_three"]) == 1
    assert summary["today_three"][0]["text"] == "Call mentor"


def test_summary_returns_aggregated_data(test_user, clean_life_data):
    """Test that summary returns all sections."""
    # Set north star
    north_star = hc_life.NorthStar(
        identity="Software engineer",
        purpose="Build great products",
        happiness_notes="Work-life balance"
    )
    hc_life.save_north_star(test_user, north_star)

    # Add a goal
    goal = hc_life.Goal(
        id="",
        text="Get promoted",
        owner="me",
        why="Career growth",
        first_step="Talk to manager",
        confidence=0.7
    )
    hc_life.create_goal(test_user, goal)

    # Add a todo
    todo = hc_life.Todo(
        id="",
        text="Finish review",
        when="today",
        priority=0.8
    )
    hc_life.create_todo(test_user, todo)

    # Add a link
    link = hc_life.Link(
        id="",
        title="Great article",
        url="https://example.com",
        source="newsletter"
    )
    hc_life.create_link(test_user, link)

    # Get summary
    summary = hc_life.get_life_summary(test_user)

    # Verify all sections
    assert summary["north_star"]["identity"] == "Software engineer"
    assert len(summary["today_three"]) == 1
    assert summary["today_three"][0]["text"] == "Finish review"
    assert len(summary["goals"]) == 1
    assert summary["goals"][0]["text"] == "Get promoted"
    assert len(summary["links"]) == 1
    assert summary["links"][0]["title"] == "Great article"


def test_patch_marks_todo_done(test_user, clean_life_data):
    """Test that PATCH updates todo status."""
    # Create a todo
    todo = hc_life.Todo(
        id="",
        text="Review PR",
        when="today"
    )
    created = hc_life.create_todo(test_user, todo)

    # Update status to done
    success = hc_life.update_todo(test_user, created.id, {"status": "done"})
    assert success

    # Verify it was updated
    updated = hc_life.get_todo(test_user, created.id)
    assert updated is not None
    assert updated.status == "done"


def test_patch_updates_goal(test_user, clean_life_data):
    """Test that PATCH updates goal fields."""
    # Create a goal
    goal = hc_life.Goal(
        id="",
        text="Learn TypeScript",
        owner="me",
        why="Skill development",
        first_step="Read documentation",
        confidence=0.5
    )
    created = hc_life.create_goal(test_user, goal)

    # Update confidence and first step
    success = hc_life.update_goal(test_user, created.id, {
        "confidence": 0.8,
        "first_step": "Build a small project"
    })
    assert success

    # Verify updates
    updated = hc_life.get_goal(test_user, created.id)
    assert updated is not None
    assert updated.confidence == 0.8
    assert updated.first_step == "Build a small project"


def test_audit_events_logged(test_user, clean_life_data):
    """Test that create/update operations log audit events."""
    from ReDNACoreDemo.core.agent_capabilities import audit_event

    # Create a todo (this should trigger audit in API layer, but we test the function directly)
    audit_event("life_capture", {
        "user_id": test_user,
        "todo_id": "test_123",
        "text": "Test task",
        "when": "today"
    })

    # Verify audit log exists
    audit_log = CORE_DATA_ROOT / "telemetry" / "agents" / "agent_activity.jsonl"
    assert audit_log.exists()

    # Read last line
    with open(audit_log, "r") as f:
        lines = f.readlines()
        last_line = lines[-1]
        entry = json.loads(last_line)

        assert entry["event"] == "life_capture"
        assert entry["user_id"] == test_user
        assert entry["todo_id"] == "test_123"


def test_l2_daily_nudge_enqueues_when_empty(test_user, clean_life_data):
    """Test that L2 daily nudge enqueues when today_three is empty."""
    from ReDNACoreDemo import agents
    from ReDNACoreDemo.core.agent_providers import life_os_daily_provider

    # Create a goal to derive suggestions from
    goal = hc_life.Goal(
        id="",
        text="Ship new feature",
        owner="me",
        why="Product launch",
        first_step="Write technical spec",
        confidence=0.9
    )
    hc_life.create_goal(test_user, goal)

    # Create mock policy and state (L2 = autonomous)
    policy = agents.AgentPolicy(
        user_id=test_user,
        agent_id=f"agent_{test_user}",
        autonomy="auto",
        quotas={"jobs_per_day": 50},
        features={},
        permissions={}
    )

    state = agents.AgentState(
        user_id=test_user,
        agent_id=f"agent_{test_user}",
        status="active",
        job_counts={}
    )

    # Call provider
    jobs = life_os_daily_provider(test_user, policy, state)

    # Should generate 1 job with suggestions
    assert len(jobs) == 1
    job = jobs[0]
    assert job["kind"] == "life_daily_three"
    assert job["job_id"] == f"life-daily-{test_user}"
    assert len(job["payload"]["suggestions"]) == 1
    assert job["payload"]["suggestions"][0]["text"] == "Write technical spec"


def test_daily_nudge_respects_cooldown(test_user, clean_life_data):
    """Test that daily nudge doesn't spam within 20 hours."""
    from ReDNACoreDemo import agents
    from ReDNACoreDemo.core.agent_providers import life_os_daily_provider

    # Create a goal
    goal = hc_life.Goal(
        id="",
        text="Test goal",
        owner="me",
        why="Testing",
        first_step="Test step",
        confidence=0.8
    )
    hc_life.create_goal(test_user, goal)

    # Create state with recent proposal
    policy = agents.AgentPolicy(
        user_id=test_user,
        agent_id=f"agent_{test_user}",
        autonomy="auto",
        quotas={"jobs_per_day": 50},
        features={},
        permissions={}
    )

    # Set job count to indicate we already proposed
    # Already has job count
    # recent_time = now.isoformat().replace("+00:00", "Z")

    state = agents.AgentState(
        user_id=test_user,
        agent_id=f"agent_{test_user}",
        status="active",
        job_counts={"life_daily_three": 1}
    )

    # Call provider - should return empty since we already proposed
    jobs = life_os_daily_provider(test_user, policy, state)
    assert len(jobs) == 0


def test_inbox_filters_backlog_todos(test_user, clean_life_data):
    """Test that inbox shows backlog todos."""
    # Create backlog todos
    for i in range(3):
        todo = hc_life.Todo(
            id="",
            text=f"Backlog task {i+1}",
            when="backlog"
        )
        hc_life.create_todo(test_user, todo)

    # Create today todos (should not appear in inbox)
    todo_today = hc_life.Todo(
        id="",
        text="Today task",
        when="today"
    )
    hc_life.create_todo(test_user, todo_today)

    # Get summary
    summary = hc_life.get_life_summary(test_user)

    # Verify inbox only has backlog
    assert len(summary["inbox"]) == 3
    assert all("Backlog" in item["text"] for item in summary["inbox"])

    # Verify today_three has today task
    assert len(summary["today_three"]) == 1
    assert summary["today_three"][0]["text"] == "Today task"


def test_goals_sorted_by_recency(test_user, clean_life_data):
    """Test that goals are sorted by updated_at."""
    import time

    # Create goal 1
    goal1 = hc_life.Goal(
        id="",
        text="Old goal",
        owner="me",
        why="Testing",
        first_step="Step 1",
        confidence=0.5
    )
    created1 = hc_life.create_goal(test_user, goal1)

    time.sleep(0.1)

    # Create goal 2
    goal2 = hc_life.Goal(
        id="",
        text="New goal",
        owner="me",
        why="Testing",
        first_step="Step 2",
        confidence=0.7
    )
    created2 = hc_life.create_goal(test_user, goal2)

    # Get summary
    summary = hc_life.get_life_summary(test_user)

    # Verify new goal appears first
    assert len(summary["goals"]) == 2
    assert summary["goals"][0]["text"] == "New goal"
    assert summary["goals"][1]["text"] == "Old goal"
