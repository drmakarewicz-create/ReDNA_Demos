"""
Feedback Analytics Module

Provides analytics and insights on nudge feedback to inform Head Coach planning.
Integrates with nudge_store feedback data to surface helpful/not_helpful patterns.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add ExplorerFinal to path for nudge_store import
REPO_ROOT = Path(__file__).resolve().parents[2]
EXPLORER_FINAL = REPO_ROOT / "ExplorerFinal"
if EXPLORER_FINAL.exists() and str(EXPLORER_FINAL) not in sys.path:
    sys.path.insert(0, str(EXPLORER_FINAL))

try:
    from ExplorerFinal.core import nudge_store
except ImportError:
    nudge_store = None  # type: ignore


def is_feedback_available() -> bool:
    """Check if feedback system is available."""
    return nudge_store is not None


def load_feedback_summary(
    user_id: Optional[str] = None,
    persona_id: Optional[str] = None,
    days: int = 30,
    write_protect: bool = True,
) -> Dict[str, Any]:
    """
    Load feedback summary for analysis.

    Args:
        user_id: Filter by specific user (None for all users)
        persona_id: Filter by specific persona (None for all personas)
        days: Number of days to look back
        write_protect: Whether to run in write-protected mode

    Returns:
        Summary dict with feedback statistics
    """
    if not nudge_store:
        return {
            "ok": False,
            "error": "Feedback system not available",
        }

    try:
        # Load all feedback entries
        entries = nudge_store.load_feedback_entries(
            user_id=user_id,
            persona_id=persona_id,
            mode=None,
            newest_first=True,
            limit=None,
            write_protect=write_protect,
        )

        # Filter by time window if needed
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered_entries = []
        for entry in entries:
            ts = entry.get("ts")
            if not ts:
                continue
            try:
                entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if entry_time >= cutoff:
                    filtered_entries.append(entry)
            except (ValueError, AttributeError):
                continue

        # Compute statistics
        total = len(filtered_entries)
        helpful = sum(1 for e in filtered_entries if e.get("rating") == "helpful")
        not_helpful = sum(1 for e in filtered_entries if e.get("rating") == "not_helpful")

        # Per-persona breakdown
        persona_stats: Dict[str, Dict[str, int]] = {}
        for entry in filtered_entries:
            pid = entry.get("persona_id", "unknown")
            if pid not in persona_stats:
                persona_stats[pid] = {"helpful": 0, "not_helpful": 0, "total": 0}

            persona_stats[pid]["total"] += 1
            if entry.get("rating") == "helpful":
                persona_stats[pid]["helpful"] += 1
            elif entry.get("rating") == "not_helpful":
                persona_stats[pid]["not_helpful"] += 1

        # Calculate scores
        for pid, stats in persona_stats.items():
            if stats["total"] > 0:
                stats["score"] = (stats["helpful"] - stats["not_helpful"]) / stats["total"]
                stats["helpfulness_rate"] = stats["helpful"] / stats["total"]
            else:
                stats["score"] = 0.0
                stats["helpfulness_rate"] = 0.0

        return {
            "ok": True,
            "summary": {
                "total_feedback": total,
                "helpful": helpful,
                "not_helpful": not_helpful,
                "helpfulness_rate": helpful / total if total > 0 else 0.0,
                "overall_score": (helpful - not_helpful) / total if total > 0 else 0.0,
            },
            "by_persona": persona_stats,
            "days_analyzed": days,
            "user_filter": user_id,
            "persona_filter": persona_id,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def load_trait_feedback_analysis(
    user_id: Optional[str] = None,
    min_feedback_count: int = 2,
    write_protect: bool = True,
) -> Dict[str, Any]:
    """
    Analyze feedback by trait path to identify which traits generate helpful responses.

    Args:
        user_id: Filter by specific user
        min_feedback_count: Minimum feedback entries to include a trait
        write_protect: Whether to run in write-protected mode

    Returns:
        Analysis dict with per-trait feedback scores
    """
    if not nudge_store:
        return {
            "ok": False,
            "error": "Feedback system not available",
        }

    try:
        aggregates = nudge_store.load_feedback_aggregates(
            user_id=user_id,
            write_protect=write_protect,
        )

        # Filter and sort traits
        traits: List[Dict[str, Any]] = []
        for path, data in aggregates.items():
            total = data.get("helpful", 0) + data.get("not_helpful", 0)
            if total < min_feedback_count:
                continue

            traits.append({
                "trait_path": path,
                "container": data.get("container"),
                "trait_id": data.get("trait_id"),
                "helpful": data.get("helpful", 0),
                "not_helpful": data.get("not_helpful", 0),
                "total": total,
                "score": data.get("score", 0.0),
                "helpfulness_rate": data["helpful"] / total if total > 0 else 0.0,
                "last_feedback": data.get("last_ts"),
            })

        # Sort by score (descending)
        traits.sort(key=lambda x: x["score"], reverse=True)

        # Categorize traits
        high_performers = [t for t in traits if t["score"] > 0.3]
        low_performers = [t for t in traits if t["score"] < -0.3]
        neutral = [t for t in traits if -0.3 <= t["score"] <= 0.3]

        return {
            "ok": True,
            "traits": traits,
            "high_performers": high_performers,
            "low_performers": low_performers,
            "neutral": neutral,
            "total_traits_analyzed": len(traits),
            "min_feedback_threshold": min_feedback_count,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def get_planning_weights(
    user_id: str,
    write_protect: bool = True,
) -> Dict[str, float]:
    """
    Generate planning weights based on feedback scores.

    Traits with consistently helpful feedback get higher weights.
    Traits with not_helpful feedback get lower weights (down-weighted).

    Args:
        user_id: User ID to analyze
        write_protect: Whether to run in write-protected mode

    Returns:
        Dict mapping trait_path -> weight multiplier (0.5 to 1.5)
    """
    if not nudge_store:
        return {}

    try:
        aggregates = nudge_store.load_feedback_aggregates(
            user_id=user_id,
            write_protect=write_protect,
        )

        weights: Dict[str, float] = {}
        for path, data in aggregates.items():
            score = data.get("score", 0.0)
            total = data.get("helpful", 0) + data.get("not_helpful", 0)

            # Need at least 2 feedback entries to influence weights
            if total < 2:
                continue

            # Map score (-1.0 to 1.0) to weight multiplier (0.5 to 1.5)
            # score = 1.0 → weight = 1.5 (boost helpful traits)
            # score = 0.0 → weight = 1.0 (neutral)
            # score = -1.0 → weight = 0.5 (down-weight unhelpful traits)
            weight = 1.0 + (score * 0.5)
            weight = max(0.5, min(weight, 1.5))

            weights[path] = round(weight, 3)

        return weights

    except Exception as e:
        return {}


def compute_tolerance_for_nudging(
    user_id: str,
    days: int = 30,
    write_protect: bool = True,
) -> Optional[float]:
    """
    Compute a user's ToleranceForNudging as an emergent ReDNA trait.

    Based on:
    - Overall helpfulness rate
    - Frequency of feedback (engagement)
    - Ratio of dismissals to acceptances

    Returns:
        Float between 0.0 (low tolerance) and 1.0 (high tolerance), or None if insufficient data
    """
    if not nudge_store:
        return None

    try:
        # Load feedback
        summary = load_feedback_summary(
            user_id=user_id,
            days=days,
            write_protect=write_protect,
        )

        if not summary.get("ok"):
            return None

        total_feedback = summary["summary"]["total_feedback"]
        if total_feedback == 0:
            return None

        helpfulness_rate = summary["summary"]["helpfulness_rate"]

        # Load nudge actions
        try:
            actions = nudge_store.load_nudge_actions_log(limit=200, newest_first=True)
            user_actions = [a for a in actions if a.get("user_id") == user_id]

            accepts = sum(1 for a in user_actions if a.get("action") == "accept")
            dismisses = sum(1 for a in user_actions if a.get("action") == "dismiss")

            if accepts + dismisses == 0:
                acceptance_rate = 0.5
            else:
                acceptance_rate = accepts / (accepts + dismisses)

        except Exception:
            acceptance_rate = 0.5

        # Combine signals
        # 60% weight on helpfulness, 40% weight on acceptance rate
        tolerance = (0.6 * helpfulness_rate) + (0.4 * acceptance_rate)

        # Boost if high engagement (lots of feedback)
        if total_feedback > 20:
            tolerance = min(1.0, tolerance * 1.1)

        return round(tolerance, 3)

    except Exception:
        return None


def feedback_enabled() -> bool:
    """Check if feedback analytics are enabled."""
    return is_feedback_available()


__all__ = [
    "is_feedback_available",
    "load_feedback_summary",
    "load_trait_feedback_analysis",
    "get_planning_weights",
    "compute_tolerance_for_nudging",
    "feedback_enabled",
]
