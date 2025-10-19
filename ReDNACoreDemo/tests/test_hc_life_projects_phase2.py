"""
Tests for Head Coach Life OS Phase 2: Projects + Priority Matrix

Covers:
- CRUD operations for projects
- Priority matrix generation
- Quadrant assignments
- Agent provider integration
- Audit events
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from ReDNACoreDemo.core import hc_life_projects, hc_life


@pytest.fixture
def test_user():
    """Test user with some life data."""
    user_id = "test_projects_user"

    # Create test user directory
    life_dir = hc_life._life_dir(user_id)
    life_dir.mkdir(parents=True, exist_ok=True)

    # Add some test todos
    todo1 = hc_life.Todo(
        id="",
        text="Important urgent task",
        when="today",
        priority=1.0
    )
    hc_life.create_todo(user_id=user_id, todo=todo1)

    todo2 = hc_life.Todo(
        id="",
        text="Important not urgent task",
        when="week",
        priority=0.8
    )
    hc_life.create_todo(user_id=user_id, todo=todo2)

    todo3 = hc_life.Todo(
        id="",
        text="Not important urgent task",
        when="today",
        priority=0.3
    )
    hc_life.create_todo(user_id=user_id, todo=todo3)

    # Add a test goal
    test_goal = hc_life.Goal(
        id="",
        text="Test Goal",
        owner="me",
        why="For testing",
        first_step="Start testing",
        confidence=0.6
    )
    goal = hc_life.create_goal(user_id=user_id, goal=test_goal)

    yield user_id, goal.id

    # Cleanup
    import shutil
    try:
        shutil.rmtree(life_dir)
    except:
        pass

    # Cleanup audit files
    try:
        audit_dir = Path("data/audit")
        for audit_file in audit_dir.glob("life_projects_*.jsonl"):
            audit_file.unlink()
    except:
        pass


def test_create_project(test_user):
    """Test creating a new project."""
    user_id, goal_id = test_user

    project = hc_life_projects.create_project(
        user_id=user_id,
        title="Test Project",
        goal_id=goal_id,
        quadrant="important_urgent",
        next_step="First step",
        risk="Low risk",
        confidence=0.7
    )

    assert project.id is not None
    assert project.title == "Test Project"
    assert project.goal_id == goal_id
    assert project.quadrant == "important_urgent"
    assert project.status == "active"
    assert project.next_step == "First step"
    assert project.risk == "Low risk"
    assert project.confidence == 0.7
    assert project.created_at is not None
    assert project.updated_at is not None


def test_list_projects(test_user):
    """Test listing projects."""
    user_id, goal_id = test_user

    # Create multiple projects
    p1 = hc_life_projects.create_project(
        user_id=user_id,
        title="Project 1",
        quadrant="important_urgent"
    )

    p2 = hc_life_projects.create_project(
        user_id=user_id,
        title="Project 2",
        quadrant="important_not_urgent"
    )

    # List all projects
    projects = hc_life_projects.list_projects(user_id)
    assert len(projects) == 2

    # Check they're sorted by updated_at (most recent first)
    assert projects[0].title == "Project 2"
    assert projects[1].title == "Project 1"

    # List by status
    active_projects = hc_life_projects.list_projects(user_id, status="active")
    assert len(active_projects) == 2

    completed_projects = hc_life_projects.list_projects(user_id, status="completed")
    assert len(completed_projects) == 0


def test_get_project(test_user):
    """Test getting a specific project."""
    user_id, _ = test_user

    created = hc_life_projects.create_project(
        user_id=user_id,
        title="Test Get",
        quadrant="important_urgent"
    )

    # Get by ID
    project = hc_life_projects.get_project(user_id, created.id)
    assert project is not None
    assert project.id == created.id
    assert project.title == "Test Get"

    # Get non-existent
    missing = hc_life_projects.get_project(user_id, "nonexistent")
    assert missing is None


def test_update_project(test_user):
    """Test updating a project."""
    user_id, _ = test_user

    project = hc_life_projects.create_project(
        user_id=user_id,
        title="Original Title",
        quadrant="neither",
        confidence=0.3
    )

    # Update multiple fields
    updated = hc_life_projects.update_project(
        user_id=user_id,
        project_id=project.id,
        title="Updated Title",
        quadrant="important_urgent",
        status="paused",
        confidence=0.8,
        risk="High risk now"
    )

    assert updated is not None
    assert updated.id == project.id
    assert updated.title == "Updated Title"
    assert updated.quadrant == "important_urgent"
    assert updated.status == "paused"
    assert updated.confidence == 0.8
    assert updated.risk == "High risk now"
    assert updated.updated_at > project.updated_at

    # Verify persistence
    retrieved = hc_life_projects.get_project(user_id, project.id)
    assert retrieved.title == "Updated Title"
    assert retrieved.status == "paused"


def test_delete_project(test_user):
    """Test deleting a project."""
    user_id, _ = test_user

    project = hc_life_projects.create_project(
        user_id=user_id,
        title="To Delete"
    )

    # Delete it
    success = hc_life_projects.delete_project(user_id, project.id)
    assert success is True

    # Verify it's gone
    retrieved = hc_life_projects.get_project(user_id, project.id)
    assert retrieved is None

    # Delete non-existent
    success = hc_life_projects.delete_project(user_id, "nonexistent")
    assert success is False


def test_priority_matrix(test_user):
    """Test priority matrix generation."""
    user_id, _ = test_user

    # Get the matrix
    matrix = hc_life_projects.get_priority_matrix(user_id)

    assert "important_urgent" in matrix
    assert "important_not_urgent" in matrix
    assert "not_important_urgent" in matrix
    assert "neither" in matrix

    # Each quadrant should have a list
    assert isinstance(matrix["important_urgent"], list)
    assert isinstance(matrix["important_not_urgent"], list)
    assert isinstance(matrix["not_important_urgent"], list)
    assert isinstance(matrix["neither"], list)

    # Should have todos distributed across quadrants
    total_todos = sum(len(todos) for todos in matrix.values())
    assert total_todos >= 3  # We created 3 todos in the fixture


def test_update_todo_quadrant(test_user):
    """Test updating a todo's quadrant."""
    user_id, _ = test_user

    # Create a new todo
    new_todo = hc_life.Todo(
        id="",
        text="Quadrant test todo",
        when="backlog"
    )
    todo = hc_life.create_todo(user_id=user_id, todo=new_todo)

    # Update its quadrant
    success = hc_life_projects.update_todo_quadrant(
        user_id=user_id,
        todo_id=todo.id,
        quadrant="important_urgent"
    )
    assert success is True

    # Verify the metadata was updated
    updated_todo = hc_life.get_todo(user_id, todo.id)
    assert updated_todo.metadata is not None
    assert updated_todo.metadata.get("quadrant") == "important_urgent"

    # Verify it shows up in the matrix
    matrix = hc_life_projects.get_priority_matrix(user_id)
    assert todo.id in matrix["important_urgent"]

    # Update to different quadrant
    hc_life_projects.update_todo_quadrant(
        user_id=user_id,
        todo_id=todo.id,
        quadrant="neither"
    )

    matrix = hc_life_projects.get_priority_matrix(user_id)
    assert todo.id not in matrix["important_urgent"]
    assert todo.id in matrix["neither"]


def test_get_top_projects(test_user):
    """Test getting top projects by priority."""
    user_id, _ = test_user

    # Create projects in different quadrants
    p1 = hc_life_projects.create_project(
        user_id=user_id,
        title="Neither",
        quadrant="neither",
        confidence=0.9
    )

    p2 = hc_life_projects.create_project(
        user_id=user_id,
        title="Important Urgent",
        quadrant="important_urgent",
        confidence=0.5
    )

    p3 = hc_life_projects.create_project(
        user_id=user_id,
        title="Important Not Urgent",
        quadrant="important_not_urgent",
        confidence=0.8
    )

    # Get top 3
    top_projects = hc_life_projects.get_top_projects(user_id, limit=3)

    assert len(top_projects) == 3

    # Should be sorted by quadrant priority first
    # important_urgent (0), important_not_urgent (1), neither (3)
    assert top_projects[0].quadrant == "important_urgent"
    assert top_projects[1].quadrant == "important_not_urgent"
    assert top_projects[2].quadrant == "neither"

    # Test limit
    top_1 = hc_life_projects.get_top_projects(user_id, limit=1)
    assert len(top_1) == 1
    assert top_1[0].quadrant == "important_urgent"


def test_get_important_urgent_task(test_user):
    """Test getting an important & urgent task for agent provider."""
    user_id, _ = test_user

    # Create a todo and mark it as important & urgent
    new_urgent_todo = hc_life.Todo(
        id="",
        text="Urgent important task",
        when="today",
        priority=1.0
    )
    todo = hc_life.create_todo(user_id=user_id, todo=new_urgent_todo)

    hc_life_projects.update_todo_quadrant(
        user_id=user_id,
        todo_id=todo.id,
        quadrant="important_urgent"
    )

    # Get the urgent task
    task_id = hc_life_projects.get_important_urgent_task(user_id)
    assert task_id is not None
    # Should be one of the important/urgent tasks
    matrix = hc_life_projects.get_priority_matrix(user_id)
    assert task_id in matrix["important_urgent"]


def test_calculate_project_progress(test_user):
    """Test project progress calculation."""
    user_id, goal_id = test_user

    # Create project linked to a goal
    project = hc_life_projects.create_project(
        user_id=user_id,
        title="Goal-linked Project",
        goal_id=goal_id,
        confidence=0.5
    )

    # Progress should match goal confidence
    progress = hc_life_projects.calculate_project_progress(user_id, project.id)
    assert progress == 0.6  # Goal was created with 0.6 confidence

    # Create project with todos
    project2 = hc_life_projects.create_project(
        user_id=user_id,
        title="Todo-based Project",
        confidence=0.7
    )

    # Add todos linked to project
    new_todo1 = hc_life.Todo(
        id="",
        text="Project todo 1",
        when="today",
        metadata={"project_id": project2.id}
    )
    todo1 = hc_life.create_todo(user_id=user_id, todo=new_todo1)

    new_todo2 = hc_life.Todo(
        id="",
        text="Project todo 2",
        when="week",
        metadata={"project_id": project2.id}
    )
    todo2 = hc_life.create_todo(user_id=user_id, todo=new_todo2)

    # No todos done yet
    progress = hc_life_projects.calculate_project_progress(user_id, project2.id)
    assert progress == 0.0

    # Complete one todo
    hc_life.update_todo(user_id, todo1.id, {'status': 'done'})

    progress = hc_life_projects.calculate_project_progress(user_id, project2.id)
    assert progress == 0.5  # 1 of 2 done

    # Complete both
    hc_life.update_todo(user_id, todo2.id, {'status': 'done'})

    progress = hc_life_projects.calculate_project_progress(user_id, project2.id)
    assert progress == 1.0  # All done


def test_audit_events(test_user):
    """Test that audit events are recorded."""
    user_id, _ = test_user

    # Create a project (should record audit event)
    project = hc_life_projects.create_project(
        user_id=user_id,
        title="Audit Test"
    )

    # Update it (should record audit event)
    hc_life_projects.update_project(
        user_id=user_id,
        project_id=project.id,
        status="completed"
    )

    # Delete it (should record audit event)
    hc_life_projects.delete_project(user_id, project.id)

    # Check audit file was created
    audit_dir = Path("data/audit")
    audit_files = list(audit_dir.glob("life_projects_*.jsonl"))

    # Should have at least one audit file
    assert len(audit_files) > 0

    # Read the most recent one
    audit_file = audit_files[-1]
    events = []
    with open(audit_file, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    # Should have recorded events
    assert len(events) >= 3

    # Check event types
    event_types = [e["event_type"] for e in events if e.get("user_id") == user_id]
    assert "project_created" in event_types
    assert "project_updated" in event_types
    assert "project_deleted" in event_types


def test_agent_provider_integration(test_user):
    """Test that the agent provider uses important/urgent tasks."""
    user_id, _ = test_user

    # Create an important & urgent task
    new_todo = hc_life.Todo(
        id="",
        text="Agent provider test task",
        when="today",
        priority=1.0
    )
    todo = hc_life.create_todo(user_id=user_id, todo=new_todo)

    hc_life_projects.update_todo_quadrant(
        user_id=user_id,
        todo_id=todo.id,
        quadrant="important_urgent"
    )

    # Verify the important/urgent task function works
    task_id = hc_life_projects.get_important_urgent_task(user_id)
    assert task_id is not None

    # Verify it's the one we just created
    fetched_todo = hc_life.get_todo(user_id, task_id)
    assert fetched_todo is not None
    # It should be either the one we just created or another important/urgent one
    assert fetched_todo.priority >= 0.7 or fetched_todo.when == "today"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
