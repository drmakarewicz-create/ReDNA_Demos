"""
Head Coach Life OS - Projects & Priority Matrix (Phase 2)

Enables organizing todos & goals into projects and quadrants for
better strategic planning and prioritization.
"""

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .hc_life import _life_dir


@dataclass
class Project:
    """A project groups related goals/todos with priority and status."""
    id: str
    title: str
    goal_id: Optional[str] = None
    quadrant: str = "important_not_urgent"  # 'important_urgent' | 'important_not_urgent' | 'not_important_urgent' | 'neither'
    status: str = "active"  # 'active' | 'paused' | 'completed'
    next_step: Optional[str] = None
    risk: Optional[str] = None
    confidence: float = 0.5
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_projects_file(user_id: str) -> Path:
    """Get the projects.jsonl file path for a user."""
    life_dir = _life_dir(user_id)
    return life_dir / "projects.jsonl"


def list_projects(user_id: str, status: Optional[str] = None) -> List[Project]:
    """
    List all projects for a user.

    Args:
        user_id: User identifier
        status: Optional filter by status ('active', 'paused', 'completed')

    Returns:
        List of Project objects
    """
    projects_file = _get_projects_file(user_id)

    if not projects_file.exists():
        return []

    projects = []
    with open(projects_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                project = Project(**data)
                if status is None or project.status == status:
                    projects.append(project)

    # Sort by updated_at desc, then created_at desc
    projects.sort(
        key=lambda p: (p.updated_at or p.created_at or ""),
        reverse=True
    )

    return projects


def get_project(user_id: str, project_id: str) -> Optional[Project]:
    """Get a specific project by ID."""
    projects = list_projects(user_id)
    for project in projects:
        if project.id == project_id:
            return project
    return None


def create_project(
    user_id: str,
    title: str,
    goal_id: Optional[str] = None,
    quadrant: str = "important_not_urgent",
    next_step: Optional[str] = None,
    risk: Optional[str] = None,
    confidence: float = 0.5
) -> Project:
    """
    Create a new project.

    Args:
        user_id: User identifier
        title: Project title
        goal_id: Optional linked goal ID
        quadrant: Priority quadrant
        next_step: Next action to take
        risk: Risk assessment
        confidence: Confidence level (0.0 to 1.0)

    Returns:
        Created Project object
    """
    projects_file = _get_projects_file(user_id)
    projects_file.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().isoformat() + "Z"
    project = Project(
        id=str(uuid.uuid4()),
        title=title,
        goal_id=goal_id,
        quadrant=quadrant,
        status="active",
        next_step=next_step,
        risk=risk,
        confidence=confidence,
        created_at=now,
        updated_at=now
    )

    with open(projects_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(project.to_dict()) + "\n")

    _record_audit_event(user_id, "project_created", project.id, {
        "title": title,
        "quadrant": quadrant
    })

    return project


def update_project(
    user_id: str,
    project_id: str,
    **updates
) -> Optional[Project]:
    """
    Update an existing project.

    Args:
        user_id: User identifier
        project_id: Project ID to update
        **updates: Fields to update

    Returns:
        Updated Project object or None if not found
    """
    projects = list_projects(user_id)
    updated_project = None

    for project in projects:
        if project.id == project_id:
            # Apply updates
            for key, value in updates.items():
                if hasattr(project, key):
                    setattr(project, key, value)

            project.updated_at = datetime.utcnow().isoformat() + "Z"
            updated_project = project
            break

    if updated_project is None:
        return None

    # Rewrite file
    projects_file = _get_projects_file(user_id)
    with open(projects_file, "w", encoding="utf-8") as f:
        for project in projects:
            f.write(json.dumps(project.to_dict()) + "\n")

    _record_audit_event(user_id, "project_updated", project_id, updates)

    return updated_project


def delete_project(user_id: str, project_id: str) -> bool:
    """
    Delete a project.

    Args:
        user_id: User identifier
        project_id: Project ID to delete

    Returns:
        True if deleted, False if not found
    """
    projects = list_projects(user_id)
    original_count = len(projects)

    projects = [p for p in projects if p.id != project_id]

    if len(projects) == original_count:
        return False

    # Rewrite file
    projects_file = _get_projects_file(user_id)
    with open(projects_file, "w", encoding="utf-8") as f:
        for project in projects:
            f.write(json.dumps(project.to_dict()) + "\n")

    _record_audit_event(user_id, "project_deleted", project_id, {})

    return True


def get_priority_matrix(user_id: str) -> Dict[str, List[str]]:
    """
    Get the priority matrix mapping quadrants to todo IDs.

    Returns:
        Dict with keys: 'important_urgent', 'important_not_urgent',
        'not_important_urgent', 'neither'
        Each value is a list of todo IDs in that quadrant.
    """
    from .hc_life import list_todos

    matrix = {
        "important_urgent": [],
        "important_not_urgent": [],
        "not_important_urgent": [],
        "neither": []
    }

    # Get all open (active) todos
    todos = list_todos(user_id, status="open")

    for todo in todos:
        # Check if todo has a quadrant metadata field
        quadrant = None
        if hasattr(todo, 'metadata') and todo.metadata:
            quadrant = todo.metadata.get('quadrant')

        # Default quadrant assignment based on priority and due date
        if quadrant is None:
            priority = getattr(todo, 'priority', 0.5)

            # Check if there's a due date - use scheduled_for or check when="today"
            is_urgent = todo.when == "today"

            # Can also check scheduled_for if present
            scheduled_for = getattr(todo, 'scheduled_for', None)
            if scheduled_for and not is_urgent:
                from datetime import datetime, timedelta
                try:
                    due = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
                    now = datetime.utcnow()
                    is_urgent = (due - now) < timedelta(days=7)
                except:
                    pass

            # Determine importance from priority (>0.7 is important)
            is_important = priority >= 0.7

            if is_important and is_urgent:
                quadrant = "important_urgent"
            elif is_important and not is_urgent:
                quadrant = "important_not_urgent"
            elif not is_important and is_urgent:
                quadrant = "not_important_urgent"
            else:
                quadrant = "neither"

        if quadrant in matrix:
            matrix[quadrant].append(todo.id)

    return matrix


def update_todo_quadrant(user_id: str, todo_id: str, quadrant: str) -> bool:
    """
    Update a todo's quadrant assignment.

    Args:
        user_id: User identifier
        todo_id: Todo ID
        quadrant: New quadrant assignment

    Returns:
        True if updated, False if todo not found
    """
    from .hc_life import get_todo, update_todo

    todo = get_todo(user_id, todo_id)
    if not todo:
        return False

    # Update metadata with quadrant
    metadata = todo.metadata or {}
    metadata['quadrant'] = quadrant

    update_todo(user_id, todo_id, {'metadata': metadata})

    _record_audit_event(user_id, "todo_quadrant_updated", todo_id, {
        "quadrant": quadrant
    })

    return True


def get_top_projects(user_id: str, limit: int = 3) -> List[Project]:
    """
    Get top active projects, prioritized by quadrant.

    Important & Urgent projects are shown first, then Important & Not Urgent.

    Args:
        user_id: User identifier
        limit: Maximum number of projects to return

    Returns:
        List of top Project objects
    """
    projects = list_projects(user_id, status="active")

    # Sort by quadrant priority
    quadrant_priority = {
        "important_urgent": 0,
        "important_not_urgent": 1,
        "not_important_urgent": 2,
        "neither": 3
    }

    projects.sort(
        key=lambda p: (
            quadrant_priority.get(p.quadrant, 99),
            -(p.confidence or 0.5)
        )
    )

    return projects[:limit]


def get_important_urgent_task(user_id: str) -> Optional[str]:
    """
    Get one task from the Important & Urgent quadrant.

    Used by the Life OS agent provider when "Today's 3" is empty.

    Returns:
        Todo ID or None
    """
    matrix = get_priority_matrix(user_id)
    urgent_tasks = matrix.get("important_urgent", [])

    if urgent_tasks:
        return urgent_tasks[0]

    return None


def _record_audit_event(user_id: str, event_type: str, project_id: str, metadata: Dict[str, Any]):
    """Record an audit event for project operations."""
    try:
        audit_dir = Path("data/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "event_type": event_type,
            "project_id": project_id,
            "metadata": metadata
        }

        audit_file = audit_dir / f"life_projects_{datetime.utcnow().strftime('%Y%m')}.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        # Don't fail operations due to audit errors
        pass


def calculate_project_progress(user_id: str, project_id: str) -> float:
    """
    Calculate project progress based on linked goals/todos.

    Args:
        user_id: User identifier
        project_id: Project ID

    Returns:
        Progress percentage (0.0 to 1.0)
    """
    from .hc_life import list_todos, list_goals

    project = get_project(user_id, project_id)
    if not project:
        return 0.0

    # If linked to a goal, use goal progress
    if project.goal_id:
        goals = list_goals(user_id)
        for goal in goals:
            if goal.id == project.goal_id:
                return goal.confidence or 0.0

    # Otherwise, count todos with project_id in metadata
    all_todos = list_todos(user_id)
    project_todos = [
        t for t in all_todos
        if t.metadata and t.metadata.get('project_id') == project_id
    ]

    if not project_todos:
        return project.confidence

    completed = len([t for t in project_todos if t.status == "done"])
    return completed / len(project_todos) if project_todos else 0.0
