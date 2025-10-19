"""
Head Coach Life OS - Agent Learning Hooks (Phase 3b)

Adaptive feedback loop that uses Life OS insights to automatically adjust:
- Nudging frequency and timing
- Tone bias (empathetic vs direct)
- Creativity/exploration bias
- Focus area weighting

Learning state persists per user and updates on weekly cycles or manual triggers.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from .hc_life_insights import compute_insights
from .storage import CORE_DATA_ROOT


@dataclass
class LearningState:
    """Adaptive learning state for Head Coach behavior."""
    # Nudging adjustments
    nudge_frequency_multiplier: float  # 0.5 = half as often, 2.0 = twice as often
    nudge_timing_preference: str  # 'morning', 'afternoon', 'evening', 'adaptive'

    # Tone adjustments
    tone_bias: float  # -1.0 (direct) to +1.0 (empathetic)
    formality_bias: float  # -1.0 (casual) to +1.0 (formal)

    # Exploration adjustments
    creativity_bias: float  # 0.0 (conservative) to 1.0 (experimental)

    # Focus area weights (by category or tag)
    focus_weights: Dict[str, float]  # category -> weight multiplier

    # Performance tracking
    last_update: str
    update_count: int
    baseline_metrics: Dict[str, float]  # Initial performance snapshot

    # Metadata
    version: str = "1.0"
    computed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize_metric(value: float, min_val: float, max_val: float) -> float:
    """Normalize metric to 0–1 range."""
    if max_val == min_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def _compute_nudge_adjustments(insights: Dict[str, Any], current_state: Optional[LearningState]) -> Dict[str, Any]:
    """
    Compute nudge frequency and timing adjustments based on performance.

    Logic:
    - High completion rate (>70%) → reduce nudge frequency
    - Low completion rate (<40%) → increase nudge frequency
    - Avg completion hour → suggest timing preference
    """
    completion_rate = insights.get('todos_completion_rate', 0.0)
    nudge_acceptance = insights.get('nudge_acceptance_rate', 0.0)
    avg_completion_hour = insights.get('avg_completion_hour')

    # Base multiplier on completion and acceptance rates
    if completion_rate > 0.7 and nudge_acceptance > 0.6:
        # User is doing well, reduce nudges
        frequency_multiplier = 0.7
    elif completion_rate < 0.4 or nudge_acceptance < 0.3:
        # User needs more support
        frequency_multiplier = 1.3
    else:
        # Middle ground
        frequency_multiplier = 1.0

    # Smooth transition from previous state
    if current_state:
        prev_multiplier = current_state.nudge_frequency_multiplier
        frequency_multiplier = prev_multiplier * 0.6 + frequency_multiplier * 0.4

    # Determine timing preference from completion patterns
    timing_preference = 'adaptive'
    if avg_completion_hour is not None:
        if avg_completion_hour < 12:
            timing_preference = 'morning'
        elif avg_completion_hour < 17:
            timing_preference = 'afternoon'
        else:
            timing_preference = 'evening'

    return {
        'nudge_frequency_multiplier': round(frequency_multiplier, 2),
        'nudge_timing_preference': timing_preference
    }


def _compute_tone_adjustments(insights: Dict[str, Any], current_state: Optional[LearningState]) -> Dict[str, Any]:
    """
    Compute tone bias based on user behavior patterns.

    Logic:
    - Active streaks + high completion → more direct/brief
    - Struggling (low streaks, at-risk projects) → more empathetic
    - Quadrant balance (more important_not_urgent) → encourage strategic thinking
    """
    current_streak = insights.get('current_streak', 0)
    completion_rate = insights.get('todos_completion_rate', 0.0)
    projects_at_risk = len(insights.get('projects_at_risk', []))
    goals_at_risk = len(insights.get('goals_at_risk', []))

    # Compute tone bias
    if current_streak >= 7 and completion_rate > 0.7:
        # User is crushing it → be more direct and brief
        tone_bias = -0.3
    elif current_streak < 3 or completion_rate < 0.4:
        # User is struggling → be more empathetic
        tone_bias = 0.5
    else:
        # Balanced
        tone_bias = 0.1

    # Factor in at-risk items (more empathy if things are falling through)
    if projects_at_risk > 2 or goals_at_risk > 3:
        tone_bias += 0.2

    # Smooth transition
    if current_state:
        prev_bias = current_state.tone_bias
        tone_bias = prev_bias * 0.5 + tone_bias * 0.5

    # Formality stays relatively neutral
    formality_bias = 0.0

    return {
        'tone_bias': round(max(-1.0, min(1.0, tone_bias)), 2),
        'formality_bias': round(formality_bias, 2)
    }


def _compute_creativity_adjustments(insights: Dict[str, Any], current_state: Optional[LearningState]) -> Dict[str, Any]:
    """
    Compute creativity/exploration bias.

    Logic:
    - High quadrant imbalance (too much urgent) → encourage exploration
    - Repeating same tags/categories → encourage diversity
    - Strong performance on diverse tasks → maintain exploration
    """
    quadrant_share = insights.get('quadrant_share', {})
    focus_categories = insights.get('focus_categories', {})

    # Check quadrant balance
    urgent_share = quadrant_share.get('important_urgent', 0.0) + quadrant_share.get('not_important_urgent', 0.0)

    # Check focus diversity (normalized entropy)
    total_focus = sum(focus_categories.values())
    if total_focus > 0:
        category_probs = [count / total_focus for count in focus_categories.values()]
        # Simple diversity metric: how evenly distributed?
        max_diversity = len(focus_categories)
        actual_diversity = len([p for p in category_probs if p > 0.1])  # Categories with >10% share
        diversity_score = actual_diversity / max_diversity if max_diversity > 0 else 0.5
    else:
        diversity_score = 0.5

    # Compute creativity bias
    if urgent_share > 60.0:
        # Too much urgency → encourage strategic exploration
        creativity_bias = 0.7
    elif diversity_score < 0.3:
        # Low diversity → encourage trying new areas
        creativity_bias = 0.6
    elif diversity_score > 0.6:
        # High diversity → user is exploring well
        creativity_bias = 0.5
    else:
        # Middle ground
        creativity_bias = 0.4

    # Smooth transition
    if current_state:
        prev_bias = current_state.creativity_bias
        creativity_bias = prev_bias * 0.5 + creativity_bias * 0.5

    return {
        'creativity_bias': round(creativity_bias, 2)
    }


def _compute_focus_weights(insights: Dict[str, Any], current_state: Optional[LearningState]) -> Dict[str, float]:
    """
    Compute focus area weights based on activity and at-risk signals.

    Logic:
    - Active categories get baseline weight (1.0)
    - At-risk goal categories get boosted weight (1.5)
    - Inactive categories get reduced weight (0.7)
    """
    focus_categories = insights.get('focus_categories', {})
    goals_at_risk = insights.get('goals_at_risk', [])

    # Normalize category counts
    total_focus = sum(focus_categories.values())
    weights = {}

    for category, count in focus_categories.items():
        if total_focus > 0:
            activity_ratio = count / total_focus
            if activity_ratio > 0.3:
                # High activity
                weights[category] = 1.1
            elif activity_ratio < 0.1:
                # Low activity
                weights[category] = 0.8
            else:
                weights[category] = 1.0
        else:
            weights[category] = 1.0

    # Boost categories with at-risk goals
    # (This is simplified; in production, parse goal categories from metadata)
    if goals_at_risk:
        for goal in goals_at_risk:
            # Heuristic: boost 'career' if work goals at risk, etc.
            # For now, apply a general boost to career/personal
            if 'career' in weights:
                weights['career'] = min(1.5, weights['career'] + 0.2)
            if 'personal' in weights:
                weights['personal'] = min(1.5, weights['personal'] + 0.1)

    # Smooth transition from previous state
    if current_state and current_state.focus_weights:
        for category, weight in weights.items():
            if category in current_state.focus_weights:
                prev_weight = current_state.focus_weights[category]
                weights[category] = round(prev_weight * 0.6 + weight * 0.4, 2)

    return weights


def compute_learning_deltas(user_id: str, days: int = 14) -> Dict[str, Any]:
    """
    Compute learning deltas by analyzing Life OS insights.

    Args:
        user_id: User identifier
        days: Rolling window for insight computation (default: 14)

    Returns:
        Dict with computed deltas (not yet applied to state)
    """
    # Load current state
    current_state = load_state(user_id)

    # Compute fresh insights
    insights = compute_insights(user_id, days=days)

    # Compute adjustments across dimensions
    nudge_adj = _compute_nudge_adjustments(insights, current_state)
    tone_adj = _compute_tone_adjustments(insights, current_state)
    creativity_adj = _compute_creativity_adjustments(insights, current_state)
    focus_weights = _compute_focus_weights(insights, current_state)

    # Build deltas object
    deltas = {
        'nudge_frequency_multiplier': nudge_adj['nudge_frequency_multiplier'],
        'nudge_timing_preference': nudge_adj['nudge_timing_preference'],
        'tone_bias': tone_adj['tone_bias'],
        'formality_bias': tone_adj['formality_bias'],
        'creativity_bias': creativity_adj['creativity_bias'],
        'focus_weights': focus_weights,
        'insights_snapshot': {
            'completion_rate': insights.get('todos_completion_rate'),
            'current_streak': insights.get('current_streak'),
            'nudge_acceptance': insights.get('nudge_acceptance_rate'),
            'projects_at_risk_count': len(insights.get('projects_at_risk', [])),
            'goals_at_risk_count': len(insights.get('goals_at_risk', []))
        },
        'computed_at': datetime.now(timezone.utc).isoformat() + 'Z'
    }

    return deltas


def apply_learning_deltas(user_id: str, deltas: Optional[Dict[str, Any]] = None) -> LearningState:
    """
    Apply learning deltas to user state and persist.

    Args:
        user_id: User identifier
        deltas: Pre-computed deltas (if None, will compute fresh)

    Returns:
        Updated LearningState
    """
    # Load or initialize state
    current_state = load_state(user_id)

    # Compute deltas if not provided
    if deltas is None:
        deltas = compute_learning_deltas(user_id)

    # Initialize baseline metrics on first run
    baseline_metrics = {}
    if current_state and current_state.baseline_metrics:
        baseline_metrics = current_state.baseline_metrics
    elif 'insights_snapshot' in deltas:
        baseline_metrics = deltas['insights_snapshot']

    # Build new state
    new_state = LearningState(
        nudge_frequency_multiplier=deltas['nudge_frequency_multiplier'],
        nudge_timing_preference=deltas['nudge_timing_preference'],
        tone_bias=deltas['tone_bias'],
        formality_bias=deltas['formality_bias'],
        creativity_bias=deltas['creativity_bias'],
        focus_weights=deltas['focus_weights'],
        last_update=deltas['computed_at'],
        update_count=(current_state.update_count + 1) if current_state else 1,
        baseline_metrics=baseline_metrics,
        computed_at=deltas['computed_at']
    )

    # Persist state
    save_state(user_id, new_state)

    # Log audit event
    _log_learning_applied(user_id, deltas, new_state)

    return new_state


def load_state(user_id: str) -> Optional[LearningState]:
    """Load learning state for user."""
    state_file = _learning_dir(user_id) / "state.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return LearningState(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def save_state(user_id: str, state: LearningState) -> None:
    """Save learning state for user."""
    learning_dir = _learning_dir(user_id)
    learning_dir.mkdir(parents=True, exist_ok=True)

    state_file = learning_dir / "state.json"

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)


def _learning_dir(user_id: str) -> Path:
    """Get learning directory for user."""
    return CORE_DATA_ROOT / "users" / user_id / "hc_learning"


def _log_learning_applied(user_id: str, deltas: Dict[str, Any], state: LearningState) -> None:
    """Log learning application to audit trail."""
    audit_dir = CORE_DATA_ROOT / "telemetry" / "agents"
    audit_dir.mkdir(parents=True, exist_ok=True)

    audit_file = audit_dir / "agent_activity.jsonl"

    event = {
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'user_id': user_id,
        'event': 'learning_applied',
        'agent': 'head_coach',
        'data': {
            'update_count': state.update_count,
            'nudge_frequency_multiplier': state.nudge_frequency_multiplier,
            'tone_bias': state.tone_bias,
            'creativity_bias': state.creativity_bias,
            'focus_weight_count': len(state.focus_weights),
            'insights_snapshot': deltas.get('insights_snapshot', {})
        }
    }

    with open(audit_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')


def get_behavior_context(user_id: str) -> Dict[str, Any]:
    """
    Get behavior context for LLM prompt injection.

    This is used by coach_mode_manager to bias behavior based on learning.

    Returns:
        Dict with learning-based behavior hints
    """
    state = load_state(user_id)

    if not state:
        return {}

    # Build human-readable context
    tone_hint = ""
    if state.tone_bias > 0.3:
        tone_hint = "empathetic and supportive"
    elif state.tone_bias < -0.2:
        tone_hint = "direct and concise"
    else:
        tone_hint = "balanced"

    timing_hint = state.nudge_timing_preference
    if timing_hint == 'adaptive':
        timing_hint = "at opportune moments"

    creativity_hint = ""
    if state.creativity_bias > 0.6:
        creativity_hint = "Encourage exploration and trying new approaches."
    elif state.creativity_bias < 0.4:
        creativity_hint = "Focus on proven strategies and consistency."
    else:
        creativity_hint = "Balance proven methods with occasional exploration."

    focus_hint = ""
    if state.focus_weights:
        top_areas = sorted(state.focus_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        focus_hint = f"Priority areas: {', '.join([f'{area} ({weight:.1f}x)' for area, weight in top_areas])}"

    return {
        'learning_enabled': True,
        'update_count': state.update_count,
        'last_update': state.last_update,
        'tone': tone_hint,
        'timing': timing_hint,
        'creativity': creativity_hint,
        'focus': focus_hint,
        'nudge_frequency_multiplier': state.nudge_frequency_multiplier,
        'raw_state': state.to_dict()
    }
