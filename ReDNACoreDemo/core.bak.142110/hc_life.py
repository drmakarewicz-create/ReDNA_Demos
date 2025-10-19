"""
Head Coach Life OS - data model and storage for personal productivity.

Implements the "Life OS" right pane: goals, todos, quick capture, links, and inspiration.
Storage: data/users/<id>/hc_life/{north_star.json, goals.jsonl, todos.jsonl, links.jsonl, inspiration.jsonl}
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4

from .storage import USERS_DIR, load_json, save_json
from .bundles import iso_now

logger = logging.getLogger(__name__)

# =========================================================================
# TYPE DEFINITIONS
# =========================================================================

TodoWhen = Literal["today", "week", "backlog", "scheduled"]
TodoStatus = Literal["open", "done", "snoozed"]
GoalStatus = Literal["active", "completed", "archived"]

@dataclass
class NorthStar:
    """User's core identity, purpose, and happiness notes."""
    identity: str = ""
    purpose: str = ""
    happiness_notes: str = ""

@dataclass
class Goal:
    """Quarter/long-term goal with tracking metadata."""
    id: str
    text: str
    owner: str
    why: str
    first_step: str
    confidence: float  # 0.0 - 1.0
    target_date: Optional[str] = None
    status: GoalStatus = "active"
    created_at: str = ""
    updated_at: str = ""

@dataclass
class Todo:
    """Task or reminder with scheduling and priority."""
    id: str
    text: str
    when: TodoWhen = "backlog"
    priority: float = 0.5  # 0.0 - 1.0
    status: TodoStatus = "open"
    goal_id: Optional[str] = None
    project_id: Optional[str] = None
    tags: List[str] = None
    metadata: Optional[Dict[str, Any]] = None  # For quadrant, custom fields, etc.
    created_at: str = ""
    updated_at: str = ""
    scheduled_for: Optional[str] = None  # ISO timestamp for "scheduled" when

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class Link:
    """Saved link or recommendation."""
    id: str
    title: str
    url: str
    source: str = ""
    est_time_minutes: Optional[int] = None
    is_recommended: bool = False
    created_at: str = ""

@dataclass
class Inspiration:
    """Quote or advice with context."""
    id: str
    text: str
    source: str
    why_matters: str = ""
    created_at: str = ""

# =========================================================================
# STORAGE LAYER
# =========================================================================

def _life_dir(user_id: str) -> Path:
    """Ensure hc_life directory exists for user."""
    path = USERS_DIR / user_id / "hc_life"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _north_star_path(user_id: str) -> Path:
    return _life_dir(user_id) / "north_star.json"

def _goals_path(user_id: str) -> Path:
    return _life_dir(user_id) / "goals.jsonl"

def _todos_path(user_id: str) -> Path:
    return _life_dir(user_id) / "todos.jsonl"

def _links_path(user_id: str) -> Path:
    return _life_dir(user_id) / "links.jsonl"

def _inspiration_path(user_id: str) -> Path:
    return _life_dir(user_id) / "inspiration.jsonl"

# =========================================================================
# NORTH STAR
# =========================================================================

def load_north_star(user_id: str) -> NorthStar:
    """Load user's north star (identity, purpose, happiness)."""
    path = _north_star_path(user_id)
    data = load_json(path, default={})
    return NorthStar(
        identity=data.get("identity", ""),
        purpose=data.get("purpose", ""),
        happiness_notes=data.get("happiness_notes", "")
    )

def save_north_star(user_id: str, north_star: NorthStar) -> None:
    """Save user's north star."""
    path = _north_star_path(user_id)
    save_json(path, asdict(north_star))

# =========================================================================
# JSONL UTILITIES
# =========================================================================

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read all records from a JSONL file."""
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping invalid JSON line in {path}")
    return records

def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append a record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def _write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Overwrite a JSONL file with all records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

def _update_record(path: Path, record_id: str, updates: Dict[str, Any]) -> bool:
    """Update a single record in JSONL file by ID. Returns True if found."""
    records = _read_jsonl(path)
    found = False
    for rec in records:
        if rec.get("id") == record_id:
            rec.update(updates)
            rec["updated_at"] = iso_now()
            found = True
            break
    if found:
        _write_jsonl(path, records)
    return found

# =========================================================================
# GOALS
# =========================================================================

def list_goals(user_id: str, status: Optional[GoalStatus] = None) -> List[Goal]:
    """Load all goals, optionally filtered by status."""
    path = _goals_path(user_id)
    records = _read_jsonl(path)
    goals = []
    for rec in records:
        if status is None or rec.get("status") == status:
            goals.append(Goal(**rec))
    return goals

def get_goal(user_id: str, goal_id: str) -> Optional[Goal]:
    """Get a specific goal by ID."""
    path = _goals_path(user_id)
    records = _read_jsonl(path)
    for rec in records:
        if rec.get("id") == goal_id:
            return Goal(**rec)
    return None

def create_goal(user_id: str, goal: Goal) -> Goal:
    """Create a new goal."""
    if not goal.id:
        goal.id = f"g_{uuid4().hex[:8]}"
    now = iso_now()
    goal.created_at = now
    goal.updated_at = now
    path = _goals_path(user_id)
    _append_jsonl(path, asdict(goal))
    return goal

def update_goal(user_id: str, goal_id: str, updates: Dict[str, Any]) -> bool:
    """Update a goal. Returns True if successful."""
    return _update_record(_goals_path(user_id), goal_id, updates)

# =========================================================================
# TODOS
# =========================================================================

def list_todos(
    user_id: str,
    scope: Optional[TodoWhen] = None,
    status: Optional[TodoStatus] = None
) -> List[Todo]:
    """Load todos, optionally filtered by scope (when) and/or status."""
    path = _todos_path(user_id)
    records = _read_jsonl(path)
    todos = []
    for rec in records:
        if (scope is None or rec.get("when") == scope) and \
           (status is None or rec.get("status") == status):
            todos.append(Todo(**rec))
    return todos

def get_todo(user_id: str, todo_id: str) -> Optional[Todo]:
    """Get a specific todo by ID."""
    path = _todos_path(user_id)
    records = _read_jsonl(path)
    for rec in records:
        if rec.get("id") == todo_id:
            return Todo(**rec)
    return None

def create_todo(user_id: str, todo: Todo) -> Todo:
    """Create a new todo."""
    if not todo.id:
        todo.id = f"td_{uuid4().hex[:8]}"
    now = iso_now()
    todo.created_at = now
    todo.updated_at = now
    path = _todos_path(user_id)
    _append_jsonl(path, asdict(todo))
    return todo

def update_todo(user_id: str, todo_id: str, updates: Dict[str, Any]) -> bool:
    """Update a todo. Returns True if successful."""
    return _update_record(_todos_path(user_id), todo_id, updates)

# =========================================================================
# LINKS
# =========================================================================

def list_links(user_id: str, limit: Optional[int] = None) -> List[Link]:
    """Load links, optionally limited to most recent N."""
    path = _links_path(user_id)
    records = _read_jsonl(path)
    links = [Link(**rec) for rec in records]
    # Most recent first
    links.sort(key=lambda x: x.created_at, reverse=True)
    if limit:
        links = links[:limit]
    return links

def create_link(user_id: str, link: Link) -> Link:
    """Create a new link."""
    if not link.id:
        link.id = f"lnk_{uuid4().hex[:8]}"
    link.created_at = iso_now()
    path = _links_path(user_id)
    _append_jsonl(path, asdict(link))
    return link

# =========================================================================
# INSPIRATION
# =========================================================================

def list_inspiration(user_id: str, limit: Optional[int] = None) -> List[Inspiration]:
    """Load inspiration entries, optionally limited to most recent N."""
    path = _inspiration_path(user_id)
    records = _read_jsonl(path)
    inspirations = [Inspiration(**rec) for rec in records]
    # Most recent first
    inspirations.sort(key=lambda x: x.created_at, reverse=True)
    if limit:
        inspirations = inspirations[:limit]
    return inspirations

def create_inspiration(user_id: str, inspiration: Inspiration) -> Inspiration:
    """Create a new inspiration entry."""
    if not inspiration.id:
        inspiration.id = f"insp_{uuid4().hex[:8]}"
    inspiration.created_at = iso_now()
    path = _inspiration_path(user_id)
    _append_jsonl(path, asdict(inspiration))
    return inspiration

# =========================================================================
# SUMMARY VIEW
# =========================================================================

def get_life_summary(user_id: str) -> Dict[str, Any]:
    """
    Get aggregated Life OS summary for right pane display.

    Returns:
        - north_star: identity, purpose, happiness_notes
        - today_three: top 3 todos for today by priority
        - inbox: latest 5 open todos without specific 'when' or marked backlog
        - goals: top 5 active goals by recency
        - links: latest 3 links
        - quote: 1 random inspiration
    """
    # North star
    north_star = load_north_star(user_id)

    # Today's 3: open todos with when="today", sorted by priority desc
    today_todos = list_todos(user_id, scope="today", status="open")
    today_todos.sort(key=lambda t: t.priority, reverse=True)
    today_three = [asdict(t) for t in today_todos[:3]]

    # Inbox: latest 5 backlog todos
    inbox_todos = list_todos(user_id, scope="backlog", status="open")
    inbox_todos.sort(key=lambda t: t.created_at, reverse=True)
    inbox = [asdict(t) for t in inbox_todos[:5]]

    # Goals: top 5 active goals by updated_at
    active_goals = list_goals(user_id, status="active")
    active_goals.sort(key=lambda g: g.updated_at, reverse=True)
    goals = [asdict(g) for g in active_goals[:5]]

    # Links: latest 3
    recent_links = list_links(user_id, limit=3)
    links = [asdict(link) for link in recent_links]

    # Quote: pick the most recent inspiration
    inspirations = list_inspiration(user_id, limit=1)
    quote = asdict(inspirations[0]) if inspirations else None

    return {
        "north_star": asdict(north_star),
        "today_three": today_three,
        "inbox": inbox,
        "goals": goals,
        "links": links,
        "quote": quote
    }
