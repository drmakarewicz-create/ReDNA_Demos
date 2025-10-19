"""
ReDNA Head Coach Narrator Engine
Provides transparent, human-readable reasoning traces for HC decisions.

Benchmark: 4.A2 - Narrator Mode
Version: 1.0.0
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# Trace storage location
TRACE_FILE = Path("prompts/insights/narrator_traces.jsonl")


@dataclass
class NarratorTrace:
    """Single reasoning trace entry."""
    ts: str
    user_id: str
    context_version: int
    decision: str
    reasoning: List[str]
    confidence: float
    impact: str  # "low" | "medium" | "high"
    duration_ms: int
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class NarratorEngine:
    """
    Head Coach Narrator Engine.

    Generates and stores transparent reasoning traces for all major
    HC decisions: coach switches, tone shifts, curiosity triggers,
    Codex proposals, etc.
    """

    def __init__(self, trace_file: Optional[Path] = None):
        self.trace_file = trace_file or TRACE_FILE
        self._ensure_trace_file()

    def _ensure_trace_file(self):
        """Ensure trace file and directory exist."""
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.trace_file.exists():
            self.trace_file.touch()

    def _get_timestamp(self) -> str:
        """Get ISO8601 timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def record_trace(
        self,
        user_id: str,
        decision: str,
        reasoning: List[str],
        confidence: float,
        impact: str = "medium",
        context_version: Optional[int] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> NarratorTrace:
        """
        Record a reasoning trace.

        Args:
            user_id: User identifier
            decision: Short decision description
            reasoning: List of reasoning points
            confidence: Confidence score (0.0 - 1.0)
            impact: "low" | "medium" | "high"
            context_version: HC context version number
            session_id: Session identifier
            metadata: Additional metadata
            duration_ms: Decision duration in milliseconds

        Returns:
            Created NarratorTrace
        """
        start_time = time.perf_counter()

        # Get context version if not provided
        if context_version is None:
            context_version = self._get_current_context_version(user_id)

        # Calculate duration if not provided
        if duration_ms is None:
            duration_ms = 0

        trace = NarratorTrace(
            ts=self._get_timestamp(),
            user_id=user_id,
            context_version=context_version,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            impact=impact,
            duration_ms=duration_ms,
            session_id=session_id,
            metadata=metadata or {}
        )

        # Append to trace file
        try:
            with open(self.trace_file, "a") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")

            logger.info(
                f"Narrator trace recorded: {decision} "
                f"(confidence={confidence:.2f}, impact={impact})"
            )
        except Exception as e:
            logger.error(f"Failed to record narrator trace: {e}")

        return trace

    def record_coach_switch(
        self,
        user_id: str,
        from_coach: str,
        to_coach: str,
        reasoning_factors: List[str],
        confidence: float,
        context_version: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> NarratorTrace:
        """Record a coach switching decision."""
        decision = f"Switch from {from_coach} to {to_coach}"
        return self.record_trace(
            user_id=user_id,
            decision=decision,
            reasoning=reasoning_factors,
            confidence=confidence,
            impact="high",
            context_version=context_version,
            session_id=session_id,
            metadata={
                "type": "coach_switch",
                "from_coach": from_coach,
                "to_coach": to_coach
            }
        )

    def record_tone_shift(
        self,
        user_id: str,
        tone_change: str,
        reasoning: List[str],
        confidence: float,
        context_version: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> NarratorTrace:
        """Record a tone shift decision."""
        decision = f"Tone shift: {tone_change}"
        return self.record_trace(
            user_id=user_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            impact="medium",
            context_version=context_version,
            session_id=session_id,
            metadata={"type": "tone_shift", "tone_change": tone_change}
        )

    def record_curiosity_trigger(
        self,
        user_id: str,
        trait_container: str,
        priority: float,
        reasoning: List[str],
        confidence: float,
        context_version: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> NarratorTrace:
        """Record a curiosity trigger decision."""
        decision = f"Trigger curiosity for {trait_container}"
        return self.record_trace(
            user_id=user_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            impact="medium",
            context_version=context_version,
            session_id=session_id,
            metadata={
                "type": "curiosity_trigger",
                "trait_container": trait_container,
                "priority": priority
            }
        )

    def record_codex_action(
        self,
        user_id: str,
        action: str,
        reasoning: List[str],
        confidence: float,
        impact: str = "high",
        context_version: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> NarratorTrace:
        """Record a Codex action decision."""
        decision = f"Codex action: {action}"
        return self.record_trace(
            user_id=user_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            impact=impact,
            context_version=context_version,
            session_id=session_id,
            metadata={"type": "codex_action", "action": action}
        )

    def record_delegation_decision(
        self,
        user_id: str,
        target_coach: str,
        reasoning: List[str],
        confidence: float,
        context_version: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> NarratorTrace:
        """Record a delegation decision."""
        decision = f"Delegate to {target_coach}"
        return self.record_trace(
            user_id=user_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            impact="high",
            context_version=context_version,
            session_id=session_id,
            metadata={"type": "delegation", "target_coach": target_coach}
        )

    def get_traces(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        decision_type: Optional[str] = None,
        session_id: Optional[str] = None,
        min_confidence: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve narrator traces with filtering.

        Args:
            user_id: Filter by user ID
            limit: Maximum number of traces to return
            decision_type: Filter by decision type (coach_switch, tone_shift, etc.)
            session_id: Filter by session ID
            min_confidence: Minimum confidence threshold

        Returns:
            List of trace dictionaries (newest first)
        """
        traces = []

        if not self.trace_file.exists():
            return traces

        try:
            with open(self.trace_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        trace = json.loads(line)

                        # Apply filters
                        if user_id and trace.get("user_id") != user_id:
                            continue

                        if session_id and trace.get("session_id") != session_id:
                            continue

                        if decision_type:
                            metadata = trace.get("metadata", {})
                            if metadata.get("type") != decision_type:
                                continue

                        if min_confidence is not None:
                            if trace.get("confidence", 0) < min_confidence:
                                continue

                        traces.append(trace)
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping invalid trace line: {line[:50]}...")
                        continue

        except Exception as e:
            logger.error(f"Failed to read narrator traces: {e}")
            return []

        # Sort by timestamp (newest first) and limit
        traces.sort(key=lambda t: t.get("ts", ""), reverse=True)
        return traces[:limit]

    def build_narrative(
        self,
        user_id: str,
        limit: int = 20,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a structured narrative from traces.

        Args:
            user_id: User identifier
            limit: Maximum traces to include
            session_id: Optional session filter

        Returns:
            Dictionary with grouped traces and metadata
        """
        traces = self.get_traces(
            user_id=user_id,
            limit=limit,
            session_id=session_id
        )

        # Group by session
        sessions: Dict[str, List[Dict[str, Any]]] = {}
        for trace in traces:
            sid = trace.get("session_id", "unknown")
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(trace)

        # Calculate statistics
        total_traces = len(traces)
        avg_confidence = sum(t.get("confidence", 0) for t in traces) / max(total_traces, 1)

        decision_types = {}
        for trace in traces:
            dtype = trace.get("metadata", {}).get("type", "unknown")
            decision_types[dtype] = decision_types.get(dtype, 0) + 1

        return {
            "user_id": user_id,
            "total_traces": total_traces,
            "sessions": sessions,
            "session_count": len(sessions),
            "avg_confidence": round(avg_confidence, 3),
            "decision_types": decision_types,
            "latest_trace": traces[0] if traces else None
        }

    def export_narrative(
        self,
        user_id: str,
        format: str = "json",
        limit: int = 100,
        session_id: Optional[str] = None
    ) -> str:
        """
        Export narrative in specified format.

        Args:
            user_id: User identifier
            format: "json" or "markdown"
            limit: Maximum traces to export
            session_id: Optional session filter

        Returns:
            Formatted export string
        """
        narrative = self.build_narrative(user_id, limit, session_id)

        if format == "json":
            return json.dumps(narrative, indent=2)

        elif format == "markdown":
            lines = [
                f"# Narrator Timeline - {user_id}",
                "",
                f"**Total Traces:** {narrative['total_traces']}",
                f"**Sessions:** {narrative['session_count']}",
                f"**Avg Confidence:** {narrative['avg_confidence']:.1%}",
                "",
                "## Decision Types",
                ""
            ]

            for dtype, count in narrative["decision_types"].items():
                lines.append(f"- {dtype}: {count}")

            lines.extend(["", "## Timeline", ""])

            for session_id, traces in narrative["sessions"].items():
                lines.append(f"### Session: {session_id}")
                lines.append("")

                for trace in traces:
                    conf_pct = trace.get("confidence", 0) * 100
                    lines.extend([
                        f"**{trace['ts']}** (v{trace.get('context_version', '?')})",
                        f"- **Decision:** {trace['decision']}",
                        f"- **Confidence:** {conf_pct:.0f}%",
                        f"- **Impact:** {trace.get('impact', 'unknown')}",
                        "- **Reasoning:**"
                    ])

                    for reason in trace.get("reasoning", []):
                        lines.append(f"  - {reason}")

                    lines.append("")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _get_current_context_version(self, user_id: str) -> int:
        """Get current HC context version for user."""
        # Try to read from HC runtime state
        try:
            state_file = Path(f"data/users/{user_id}/hc_runtime_state.json")
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                    return state.get("context_version", 0)
        except Exception:
            pass

        return 0


# Global narrator instance
_narrator = None


def get_narrator() -> NarratorEngine:
    """Get global narrator engine instance."""
    global _narrator
    if _narrator is None:
        _narrator = NarratorEngine()
    return _narrator


def build_weekly_life_summary(user_id: str) -> str:
    """
    Build a human-readable weekly Life OS summary.

    This function generates a narrative summary of the user's weekly
    progress based on Life OS insights. It's designed to be called
    by the agent daemon on Mondays (or configurable schedule).

    Args:
        user_id: User identifier

    Returns:
        Human-readable summary string

    Example output:
        "You completed 8 tasks this week, maintained a 3-day streak,
        and focused on health. One career goal looks idle—want to plan
        a next step?"
    """
    from .hc_life_insights import compute_insights

    try:
        # Get 7-day insights
        insights = compute_insights(user_id, days=7)

        # Build narrative components
        parts = []

        # Task completion
        if insights['todos_completed'] > 0:
            parts.append(f"You completed {insights['todos_completed']} tasks this week")

        # Streak
        if insights['current_streak'] > 0:
            parts.append(f"maintained a {insights['current_streak']}-day streak")

        # Focus area
        if insights['top_tags'] and len(insights['top_tags']) > 0:
            top_tag = insights['top_tags'][0][0]
            parts.append(f"focused on {top_tag}")

        # At-risk signals
        at_risk_parts = []
        if insights['goals_at_risk']:
            goal_text = "goal" if len(insights['goals_at_risk']) == 1 else "goals"
            at_risk_parts.append(f"{len(insights['goals_at_risk'])} {goal_text} look idle")

        if insights['projects_at_risk']:
            project_text = "project" if len(insights['projects_at_risk']) == 1 else "projects"
            at_risk_parts.append(f"{len(insights['projects_at_risk'])} {project_text} need attention")

        # Build final message
        if not parts:
            return "No activity this week. Want to set some goals for the week ahead?"

        summary = ", ".join(parts) + "."

        # Add at-risk prompt
        if at_risk_parts:
            summary += f" {' and '.join(at_risk_parts)}—want to plan next steps?"

        # Log as narrator trace
        narrator = get_narrator()
        narrator.record_trace(
            user_id=user_id,
            decision="life_os_weekly_summary",
            reasoning=[
                f"Generated weekly summary from 7-day insights",
                f"Tasks completed: {insights['todos_completed']}",
                f"Current streak: {insights['current_streak']}",
                f"At-risk items: {len(insights['goals_at_risk']) + len(insights['projects_at_risk'])}"
            ],
            confidence=0.9,
            impact="medium",
            metadata={
                "todos_completed": insights['todos_completed'],
                "current_streak": insights['current_streak'],
                "goals_at_risk": len(insights['goals_at_risk']),
                "projects_at_risk": len(insights['projects_at_risk'])
            }
        )

        return summary

    except Exception as exc:
        logger.exception(f"Failed to build weekly summary for {user_id}")
        return "I couldn't generate your weekly summary. Let's chat about your week instead?"
