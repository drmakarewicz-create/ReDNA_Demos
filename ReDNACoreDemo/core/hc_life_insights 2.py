"""
Head Coach Life OS - Insights & Analytics (Phase 3)

Lightweight analytics layer that summarizes behavior and progress over time.
Computes metrics from Life OS data (goals, todos, projects) and audit logs.
"""

import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from .hc_life import (
    list_todos, list_goals, _life_dir,
    Todo, Goal
)
from .hc_life_projects import list_projects, Project


@dataclass
class InsightMetrics:
    """Computed metrics for a time window."""
    # Goal progression
    goals_total: int
    goals_active: int
    goals_completed: int
    goal_completion_rate: float
    goal_velocity: float  # avg progress delta per week
    goals_at_risk: List[Dict[str, Any]]  # goals with no activity

    # Todo completion
    todos_completed: int
    todos_created: int
    todos_completion_rate: float
    todays_three_success_rate: float
    avg_completion_hour: Optional[float]

    # Quadrant distribution
    quadrant_share: Dict[str, float]  # IU/IN/NU/NN percentages

    # Streaks
    current_streak: int
    longest_streak: int
    streak_days: List[str]  # ISO dates with completions

    # Focus clusters
    top_tags: List[Tuple[str, int]]  # (tag, count)
    focus_categories: Dict[str, int]

    # Nudge effectiveness
    nudge_acceptance_rate: float
    nudge_completion_rate: float

    # At-risk signals
    projects_at_risk: List[Dict[str, Any]]
    idle_days_threshold: int

    # Metadata
    window_days: int
    computed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendDataPoint:
    """Single data point in trends time-series."""
    week_start: str  # ISO date (Monday)
    week_label: str  # "Week of Jan 15"
    todos_completed: int
    goals_progressed: int
    avg_confidence: float
    quadrant_share: Dict[str, float]
    top_tag: Optional[str]


def _parse_iso_date(iso_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    if not iso_str:
        return datetime.now(timezone.utc)

    # Handle various ISO formats
    iso_str = iso_str.strip()
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'

    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        # Fallback for older formats
        return datetime.strptime(iso_str[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)


def _get_audit_events(user_id: str, days: int) -> List[Dict[str, Any]]:
    """Load audit events for user within time window."""
    from .storage import CORE_DATA_ROOT

    audit_file = CORE_DATA_ROOT / "telemetry" / "agents" / "agent_activity.jsonl"
    if not audit_file.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []

    with open(audit_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get('user_id') != user_id:
                    continue

                # Parse timestamp
                ts_str = event.get('timestamp', '')
                if not ts_str:
                    continue

                ts = _parse_iso_date(ts_str)
                if ts >= cutoff:
                    events.append(event)
            except (json.JSONDecodeError, ValueError):
                continue

    return events


def _compute_goal_metrics(
    user_id: str,
    days: int,
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute goal-related metrics."""
    goals = list_goals(user_id, status='active')
    all_goals = list_goals(user_id)  # includes completed

    # Count goals by status
    goals_active = len(goals)
    goals_completed = sum(1 for g in all_goals if g.status == 'completed')
    goals_total = len(all_goals)

    # Completion rate
    completion_rate = goals_completed / goals_total if goals_total > 0 else 0.0

    # Find goals with no recent activity (at-risk)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    goals_at_risk = []

    for goal in goals:
        # Check if goal has recent updates
        updated_at = _parse_iso_date(goal.updated_at) if hasattr(goal, 'updated_at') and goal.updated_at else None
        created_at = _parse_iso_date(goal.created_at) if goal.created_at else datetime.now(timezone.utc)

        last_activity = updated_at or created_at
        idle_days = (datetime.now(timezone.utc) - last_activity).days

        if idle_days > 7:  # No activity in 7+ days
            goals_at_risk.append({
                'id': goal.id,
                'text': goal.text,
                'idle_days': idle_days,
                'confidence': goal.confidence
            })

    # Compute velocity (simplified: avg confidence delta)
    # In production, track confidence changes over time
    goal_velocity = 0.0
    if goals_active > 0:
        avg_confidence = sum(g.confidence for g in goals) / goals_active
        goal_velocity = avg_confidence * 0.1  # Simplified velocity estimate

    return {
        'goals_total': goals_total,
        'goals_active': goals_active,
        'goals_completed': goals_completed,
        'goal_completion_rate': completion_rate,
        'goal_velocity': goal_velocity,
        'goals_at_risk': goals_at_risk
    }


def _compute_todo_metrics(
    user_id: str,
    days: int,
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute todo-related metrics."""
    todos_all = list_todos(user_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Count todos in window
    todos_completed = 0
    todos_created = 0
    completion_hours = []

    for todo in todos_all:
        created_at = _parse_iso_date(todo.created_at) if todo.created_at else None
        updated_at = _parse_iso_date(todo.updated_at) if hasattr(todo, 'updated_at') and todo.updated_at else None

        if created_at and created_at >= cutoff:
            todos_created += 1

        if todo.status == 'done' and updated_at and updated_at >= cutoff:
            todos_completed += 1
            completion_hours.append(updated_at.hour)

    # Completion rate
    completion_rate = todos_completed / todos_created if todos_created > 0 else 0.0

    # Average completion hour
    avg_completion_hour = sum(completion_hours) / len(completion_hours) if completion_hours else None

    # Today's 3 success rate (from audit events)
    todays_three_proposed = sum(1 for e in events if e.get('event') == 'life_daily_three_proposed')
    todays_three_completed = sum(1 for e in events if e.get('event') == 'life_daily_three_completed')
    todays_three_success_rate = todays_three_completed / todays_three_proposed if todays_three_proposed > 0 else 0.0

    return {
        'todos_completed': todos_completed,
        'todos_created': todos_created,
        'todos_completion_rate': completion_rate,
        'todays_three_success_rate': todays_three_success_rate,
        'avg_completion_hour': avg_completion_hour
    }


def _compute_quadrant_share(
    user_id: str,
    days: int
) -> Dict[str, float]:
    """Compute time share across matrix quadrants."""
    todos_all = list_todos(user_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    quadrant_counts = defaultdict(int)
    total = 0

    for todo in todos_all:
        if todo.status != 'done':
            continue

        updated_at = _parse_iso_date(todo.updated_at) if hasattr(todo, 'updated_at') and todo.updated_at else None
        if not updated_at or updated_at < cutoff:
            continue

        # Get quadrant from metadata
        quadrant = None
        if hasattr(todo, 'metadata') and todo.metadata:
            quadrant = todo.metadata.get('quadrant')

        # Default assignment based on priority and when
        if not quadrant:
            is_urgent = todo.when == 'today'
            is_important = todo.priority >= 0.6

            if is_urgent and is_important:
                quadrant = 'important_urgent'
            elif not is_urgent and is_important:
                quadrant = 'important_not_urgent'
            elif is_urgent and not is_important:
                quadrant = 'not_important_urgent'
            else:
                quadrant = 'neither'

        quadrant_counts[quadrant] += 1
        total += 1

    # Convert to percentages
    quadrant_share = {}
    for q in ['important_urgent', 'important_not_urgent', 'not_important_urgent', 'neither']:
        quadrant_share[q] = (quadrant_counts[q] / total * 100) if total > 0 else 0.0

    return quadrant_share


def _compute_streaks(
    user_id: str,
    days: int
) -> Tuple[int, int, List[str]]:
    """Compute current and longest streaks."""
    todos_all = list_todos(user_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get completion dates
    completion_dates = set()
    for todo in todos_all:
        if todo.status != 'done':
            continue

        updated_at = _parse_iso_date(todo.updated_at) if hasattr(todo, 'updated_at') and todo.updated_at else None
        if updated_at and updated_at >= cutoff:
            completion_dates.add(updated_at.date().isoformat())

    if not completion_dates:
        return 0, 0, []

    # Sort dates
    sorted_dates = sorted([datetime.fromisoformat(d).date() for d in completion_dates])

    # Compute current streak (backward from today)
    current_streak = 0
    today = datetime.now(timezone.utc).date()
    check_date = today

    while check_date in sorted_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Compute longest streak
    longest_streak = 0
    streak = 0
    prev_date = None

    for date in sorted_dates:
        if prev_date is None or (date - prev_date).days == 1:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 1
        prev_date = date

    return current_streak, longest_streak, [d.isoformat() for d in sorted_dates]


def _compute_focus_clusters(
    user_id: str,
    days: int
) -> Tuple[List[Tuple[str, int]], Dict[str, int]]:
    """Compute focus clusters from tags."""
    todos_all = list_todos(user_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    tag_counts = Counter()

    for todo in todos_all:
        created_at = _parse_iso_date(todo.created_at) if todo.created_at else None
        if not created_at or created_at < cutoff:
            continue

        for tag in todo.tags:
            tag_counts[tag] += 1

    # Get top tags
    top_tags = tag_counts.most_common(5)

    # Categorize tags (simplified)
    categories = defaultdict(int)
    category_keywords = {
        'career': ['work', 'job', 'career', 'project', 'task'],
        'health': ['health', 'exercise', 'fitness', 'wellness', 'gym'],
        'creative': ['creative', 'art', 'music', 'writing', 'design'],
        'learning': ['learning', 'study', 'course', 'book', 'education'],
        'personal': ['personal', 'family', 'friend', 'relationship']
    }

    for tag, count in tag_counts.items():
        tag_lower = tag.lower()
        categorized = False
        for category, keywords in category_keywords.items():
            if any(kw in tag_lower for kw in keywords):
                categories[category] += count
                categorized = True
                break
        if not categorized:
            categories['other'] += count

    return top_tags, dict(categories)


def _compute_nudge_effectiveness(events: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute nudge acceptance and completion rates."""
    nudge_proposed = sum(1 for e in events if e.get('event') in ['life_daily_three_proposed', 'agent_nudge_sent'])
    nudge_accepted = sum(1 for e in events if e.get('event') in ['life_daily_three_accepted', 'agent_nudge_accepted'])
    nudge_completed = sum(1 for e in events if e.get('event') == 'life_daily_three_completed')

    acceptance_rate = nudge_accepted / nudge_proposed if nudge_proposed > 0 else 0.0
    completion_rate = nudge_completed / nudge_accepted if nudge_accepted > 0 else 0.0

    return {
        'nudge_acceptance_rate': acceptance_rate,
        'nudge_completion_rate': completion_rate
    }


def _compute_projects_at_risk(user_id: str, days: int) -> List[Dict[str, Any]]:
    """Find projects with missing next_step or long idle time."""
    projects = list_projects(user_id, status='active')
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    at_risk = []
    for project in projects:
        # Check for missing next_step
        if not project.next_step or not project.next_step.strip():
            at_risk.append({
                'id': project.id,
                'title': project.title,
                'reason': 'missing_next_step',
                'days_idle': None
            })
            continue

        # Check for long idle time
        updated_at = _parse_iso_date(project.updated_at) if project.updated_at else None
        created_at = _parse_iso_date(project.created_at) if project.created_at else datetime.now(timezone.utc)

        last_activity = updated_at or created_at
        idle_days = (datetime.now(timezone.utc) - last_activity).days

        if idle_days > 14:  # No activity in 14+ days
            at_risk.append({
                'id': project.id,
                'title': project.title,
                'reason': 'long_idle',
                'days_idle': idle_days
            })

    return at_risk


def compute_insights(user_id: str, days: int = 14) -> Dict[str, Any]:
    """
    Compute insight metrics for a user over a rolling window.

    Args:
        user_id: User identifier
        days: Rolling window size in days (default: 14)

    Returns:
        Dict with computed metrics
    """
    # Load audit events
    events = _get_audit_events(user_id, days)

    # Compute goal metrics
    goal_metrics = _compute_goal_metrics(user_id, days, events)

    # Compute todo metrics
    todo_metrics = _compute_todo_metrics(user_id, days, events)

    # Compute quadrant share
    quadrant_share = _compute_quadrant_share(user_id, days)

    # Compute streaks
    current_streak, longest_streak, streak_days = _compute_streaks(user_id, days)

    # Compute focus clusters
    top_tags, focus_categories = _compute_focus_clusters(user_id, days)

    # Compute nudge effectiveness
    nudge_metrics = _compute_nudge_effectiveness(events)

    # Find at-risk projects
    projects_at_risk = _compute_projects_at_risk(user_id, days)

    # Build metrics object
    metrics = InsightMetrics(
        # Goals
        goals_total=goal_metrics['goals_total'],
        goals_active=goal_metrics['goals_active'],
        goals_completed=goal_metrics['goals_completed'],
        goal_completion_rate=goal_metrics['goal_completion_rate'],
        goal_velocity=goal_metrics['goal_velocity'],
        goals_at_risk=goal_metrics['goals_at_risk'],

        # Todos
        todos_completed=todo_metrics['todos_completed'],
        todos_created=todo_metrics['todos_created'],
        todos_completion_rate=todo_metrics['todos_completion_rate'],
        todays_three_success_rate=todo_metrics['todays_three_success_rate'],
        avg_completion_hour=todo_metrics['avg_completion_hour'],

        # Quadrants
        quadrant_share=quadrant_share,

        # Streaks
        current_streak=current_streak,
        longest_streak=longest_streak,
        streak_days=streak_days,

        # Focus
        top_tags=top_tags,
        focus_categories=focus_categories,

        # Nudges
        nudge_acceptance_rate=nudge_metrics['nudge_acceptance_rate'],
        nudge_completion_rate=nudge_metrics['nudge_completion_rate'],

        # At-risk
        projects_at_risk=projects_at_risk,
        idle_days_threshold=7,

        # Metadata
        window_days=days,
        computed_at=datetime.now(timezone.utc).isoformat() + 'Z'
    )

    return metrics.to_dict()


def compute_trends(user_id: str, weeks: int = 8) -> Dict[str, Any]:
    """
    Compute time-series trends over multiple weeks.

    Args:
        user_id: User identifier
        weeks: Number of weeks to analyze (default: 8)

    Returns:
        Dict with weekly trend data
    """
    todos_all = list_todos(user_id)
    goals_all = list_goals(user_id)

    # Compute start date (Monday of N weeks ago)
    today = datetime.now(timezone.utc).date()
    days_since_monday = today.weekday()
    start_date = today - timedelta(days=days_since_monday) - timedelta(weeks=weeks - 1)

    # Build weekly bins
    weekly_data = []

    for week_offset in range(weeks):
        week_start = start_date + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)

        # Count todos completed in this week
        todos_completed = sum(
            1 for todo in todos_all
            if todo.status == 'done'
            and hasattr(todo, 'updated_at') and todo.updated_at
            and week_start <= _parse_iso_date(todo.updated_at).date() < week_end
        )

        # Count goals progressed (updated in this week)
        goals_progressed = sum(
            1 for goal in goals_all
            if hasattr(goal, 'updated_at') and goal.updated_at
            and week_start <= _parse_iso_date(goal.updated_at).date() < week_end
        )

        # Compute avg confidence
        active_goals = [g for g in goals_all if g.status == 'active']
        avg_confidence = sum(g.confidence for g in active_goals) / len(active_goals) if active_goals else 0.0

        # Compute quadrant share for this week
        quadrant_counts = defaultdict(int)
        total = 0

        for todo in todos_all:
            if todo.status != 'done':
                continue
            if not hasattr(todo, 'updated_at') or not todo.updated_at:
                continue

            updated_at = _parse_iso_date(todo.updated_at).date()
            if not (week_start <= updated_at < week_end):
                continue

            # Get quadrant
            quadrant = None
            if hasattr(todo, 'metadata') and todo.metadata:
                quadrant = todo.metadata.get('quadrant')

            if not quadrant:
                is_urgent = todo.when == 'today'
                is_important = todo.priority >= 0.6

                if is_urgent and is_important:
                    quadrant = 'important_urgent'
                elif not is_urgent and is_important:
                    quadrant = 'important_not_urgent'
                elif is_urgent and not is_important:
                    quadrant = 'not_important_urgent'
                else:
                    quadrant = 'neither'

            quadrant_counts[quadrant] += 1
            total += 1

        quadrant_share = {}
        for q in ['important_urgent', 'important_not_urgent', 'not_important_urgent', 'neither']:
            quadrant_share[q] = (quadrant_counts[q] / total * 100) if total > 0 else 0.0

        # Get top tag for this week
        tag_counts = Counter()
        for todo in todos_all:
            if not hasattr(todo, 'created_at') or not todo.created_at:
                continue
            created_at = _parse_iso_date(todo.created_at).date()
            if week_start <= created_at < week_end:
                for tag in todo.tags:
                    tag_counts[tag] += 1

        top_tag = tag_counts.most_common(1)[0][0] if tag_counts else None

        # Build data point
        week_label = f"Week of {week_start.strftime('%b %d')}"
        data_point = TrendDataPoint(
            week_start=week_start.isoformat(),
            week_label=week_label,
            todos_completed=todos_completed,
            goals_progressed=goals_progressed,
            avg_confidence=avg_confidence,
            quadrant_share=quadrant_share,
            top_tag=top_tag
        )

        weekly_data.append(asdict(data_point))

    return {
        'weeks': weeks,
        'start_date': start_date.isoformat(),
        'end_date': (start_date + timedelta(weeks=weeks)).isoformat(),
        'data': weekly_data,
        'computed_at': datetime.now(timezone.utc).isoformat() + 'Z'
    }
