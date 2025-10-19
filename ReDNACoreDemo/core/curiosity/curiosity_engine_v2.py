"""
Curiosity Engine v2
===================

Adaptive curiosity engine that prioritizes which containers/traits to explore next
based on Self-Improvement analytics, data coverage, and coach performance.

Scoring Formula:
- Gap Score (50%): Inverse of data coverage/certainty (high gap = high priority)
- Impact Score (30%): Coach success rate from telemetry analysis
- Recency Score (10%): Prefer targets not touched recently
- Cost Score (10%): Down-weight if prior attempts failed

Author: ReDNA Core Team
Version: 2.0
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG_PATH = Path(__file__).parent / "curiosity_config.json"
DEFAULT_ANALYSIS_REPORT_PATH = Path("data/learning/analysis_report.json")
DEFAULT_ONTOLOGY_PATH = Path("ReDNACoreDemo/core/ontology/dna_registry.json")


class CuriosityEngine:
    """
    Generates prioritized curiosity agendas for users based on gap analysis,
    coach performance, and exploration strategy.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        analysis_report_path: Optional[Path] = None,
        ontology_path: Optional[Path] = None,
        data_root: Optional[Path] = None,
    ):
        """
        Initialize the Curiosity Engine.

        Args:
            config_path: Path to curiosity_config.json
            analysis_report_path: Path to learning analysis report
            ontology_path: Path to DNA registry/ontology
            data_root: Root data directory for user files
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.analysis_report_path = analysis_report_path or DEFAULT_ANALYSIS_REPORT_PATH
        self.ontology_path = ontology_path or DEFAULT_ONTOLOGY_PATH
        self.data_root = data_root or Path("data")

        # Load configuration
        self.config = self._load_config()
        self.weights = self.config["weights"]
        self.max_items = self.config["max_items"]
        self.min_priority = self.config["min_priority"]
        self.namespace_to_coach = self.config["namespace_to_coach"]
        self.recency_window_hours = self.config.get("recency_window_hours", 72)
        self.cost_failure_multiplier = self.config.get("cost_failure_multiplier", 0.7)
        self.suggested_prompts = self.config.get("suggested_prompts", {})

        # Load analysis report
        self.analysis_report = self._load_analysis_report()

        # Load ontology metadata
        self.ontology = self._load_ontology()

    def _load_config(self) -> Dict[str, Any]:
        """Load curiosity configuration."""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config not found at {self.config_path}, using defaults")
            return {
                "weights": {"gap": 0.5, "impact": 0.3, "recency": 0.1, "cost": 0.1},
                "max_items": 12,
                "min_priority": 0.55,
                "namespace_to_coach": {},
                "recency_window_hours": 72,
                "cost_failure_multiplier": 0.7,
                "suggested_prompts": {},
            }

    def _load_analysis_report(self) -> Dict[str, Any]:
        """Load learning analysis report."""
        try:
            with open(self.analysis_report_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Analysis report not found at {self.analysis_report_path}")
            return {"coaches": {}}

    def _load_ontology(self) -> Dict[str, Any]:
        """Load ontology/DNA registry."""
        try:
            with open(self.ontology_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Ontology not found at {self.ontology_path}")
            return {"containers": []}

    def generate_agenda(
        self,
        user_id: str,
        limit: Optional[int] = None,
        min_priority: Optional[float] = None,
        debug: bool = False,
        fallback: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a prioritized curiosity agenda for a user.

        Args:
            user_id: User ID
            limit: Maximum number of items (defaults to config max_items)
            min_priority: Override config min_priority (optional)
            debug: Include diagnostic information in response
            fallback: Generate fallback agenda if empty (default: True)

        Returns:
            Agenda dict with ranked items and optional debug info
        """
        limit = limit or self.max_items
        min_priority_threshold = min_priority if min_priority is not None else self.min_priority
        user_dir = self.data_root / "users" / user_id

        # Initialize debug info
        debug_info = {
            "analysis_report_found": self.analysis_report_path.exists() if hasattr(self.analysis_report_path, 'exists') else False,
            "ontology_found": self.ontology_path.exists() if hasattr(self.ontology_path, 'exists') else False,
            "min_priority": min_priority_threshold,
            "weights_summary": self.weights,
            "total_candidates_scored": 0,
            "below_threshold_count": 0,
            "namespaces_found": [],
        }

        # Load user data for gap analysis
        user_data = self._load_user_data(user_dir)

        # Load recent interaction history for recency scoring
        recent_interactions = self._load_recent_interactions(user_dir)

        # Load failure history for cost scoring
        failure_history = self._load_failure_history(user_dir)

        # Get all potential targets from ontology
        targets = self._extract_targets_from_ontology()
        debug_info["total_candidates_scored"] = len(targets)

        # Extract unique namespaces
        namespaces = set(t.get("namespace") for t in targets if t.get("namespace"))
        debug_info["namespaces_found"] = list(namespaces)

        # Score each target
        scored_items = []
        below_threshold_items = []

        for target in targets:
            scores = self._score_target(
                target=target,
                user_data=user_data,
                recent_interactions=recent_interactions,
                failure_history=failure_history,
            )

            if scores["priority"] >= min_priority_threshold:
                scored_items.append(scores)
            else:
                below_threshold_items.append(scores)

        debug_info["below_threshold_count"] = len(below_threshold_items)

        # Sort by priority descending
        scored_items.sort(key=lambda x: x["priority"], reverse=True)

        # Take top N
        top_items = scored_items[:limit]

        # Determine reason if empty
        reason = None
        if len(top_items) == 0:
            if not debug_info["analysis_report_found"]:
                reason = "missing analysis report"
            elif not debug_info["ontology_found"]:
                reason = "missing ontology"
            elif debug_info["total_candidates_scored"] == 0:
                reason = "no valid containers found"
            elif debug_info["below_threshold_count"] == debug_info["total_candidates_scored"]:
                reason = "all below threshold"
            else:
                reason = "unknown - check logs"

            logger.warning(f"Empty curiosity agenda for {user_id}: {reason}")
            debug_info["reason"] = reason

            # Generate fallback agenda if enabled
            if fallback:
                top_items = self._generate_fallback_agenda(limit=min(5, limit))
                debug_info["reason"] = "low telemetry signal; fallback agenda generated"
                logger.info(f"Generated fallback agenda for {user_id}: {len(top_items)} items")
        elif not debug_info["analysis_report_found"]:
            # Add diagnostic note even when items exist
            debug_info["note"] = "analysis report missing but items generated from ontology"

        # Build agenda
        agenda = {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": top_items,
            "total_candidates": len(targets),
            "above_threshold": len(scored_items),
        }

        # Add debug info if requested
        if debug or len(top_items) == 0:
            agenda["debug"] = debug_info

        # Persist agenda
        self._save_agenda(user_dir, agenda)

        return agenda

    def _load_user_data(self, user_dir: Path) -> Dict[str, Any]:
        """Load user data for gap analysis (user.json, resolved.json, etc.)."""
        user_data = {}

        # Load user.json
        user_file = user_dir / "user.json"
        if user_file.exists():
            try:
                with open(user_file, "r") as f:
                    user_data["user"] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {user_file}: {e}")

        # Load resolved.json (RR/UCN data)
        resolved_file = user_dir / "resolved.json"
        if resolved_file.exists():
            try:
                with open(resolved_file, "r") as f:
                    user_data["resolved"] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {resolved_file}: {e}")

        return user_data

    def _load_recent_interactions(self, user_dir: Path) -> Dict[str, datetime]:
        """Load recent interactions from events directory."""
        interactions = {}
        events_dir = user_dir / "events"

        if not events_dir.exists():
            return interactions

        # Scan event files for timestamps
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_window_hours)

        try:
            for event_file in events_dir.glob("*.json"):
                with open(event_file, "r") as f:
                    event = json.load(f)
                    if "timestamp" in event and "target" in event:
                        ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                        if ts > cutoff:
                            interactions[event["target"]] = ts
        except Exception as e:
            logger.warning(f"Failed to load interactions from {events_dir}: {e}")

        return interactions

    def _load_failure_history(self, user_dir: Path) -> Dict[str, int]:
        """Load failure counts per target from curiosity feedback."""
        failures = {}
        feedback_file = Path("prompts/insights/curiosity_feedback.jsonl")

        if not feedback_file.exists():
            return failures

        try:
            with open(feedback_file, "r") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("result") in ("blocked", "irrelevant"):
                        target = entry.get("target")
                        if target:
                            failures[target] = failures.get(target, 0) + 1
        except Exception as e:
            logger.warning(f"Failed to load failure history: {e}")

        return failures

    def _extract_targets_from_ontology(self) -> List[Dict[str, Any]]:
        """Extract potential targets from ontology."""
        targets = []

        # Extract containers
        containers = self.ontology.get("containers", [])
        for container in containers:
            path = container.get("path", "")
            namespace = container.get("namespace", "")
            name = container.get("name", "")

            if path and namespace:
                targets.append({
                    "target": path,
                    "namespace": namespace,
                    "name": name,
                    "type": "container",
                })

        return targets

    def _score_target(
        self,
        target: Dict[str, Any],
        user_data: Dict[str, Any],
        recent_interactions: Dict[str, datetime],
        failure_history: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Score a target using the weighted formula.

        Returns:
            Dict with target, priority, reason, suggested_coach, suggested_prompt, evidence_refs
        """
        target_path = target["target"]
        namespace = target["namespace"]

        # Gap score (0..1, higher = bigger gap)
        gap_score = self._calculate_gap_score(target_path, user_data)

        # Impact score (0..1, based on coach performance)
        coach_id = self.namespace_to_coach.get(namespace, "head_coach")
        impact_score = self._calculate_impact_score(coach_id)

        # Recency score (0..1, higher = not recently touched)
        recency_score = self._calculate_recency_score(target_path, recent_interactions)

        # Cost score (0..1, lower if many failures)
        cost_score = self._calculate_cost_score(target_path, failure_history)

        # Weighted priority
        priority = (
            self.weights["gap"] * gap_score
            + self.weights["impact"] * impact_score
            + self.weights["recency"] * recency_score
            + self.weights["cost"] * cost_score
        )

        # Build reason
        reason = self._build_reason(gap_score, impact_score, recency_score, cost_score, coach_id)

        # Get suggested prompt
        suggested_prompt = self.suggested_prompts.get(namespace, "Tell me more about this area.")

        # Build evidence refs
        evidence_refs = []
        if coach_id in self.analysis_report.get("coaches", {}):
            evidence_refs.append(f"analysis_report:coach={coach_id}")

        return {
            "target": target_path,
            "priority": round(priority, 3),
            "reason": reason,
            "suggested_coach": coach_id,
            "suggested_prompt": suggested_prompt,
            "evidence_refs": evidence_refs,
        }

    def _calculate_gap_score(self, target_path: str, user_data: Dict[str, Any]) -> float:
        """
        Calculate gap score (0..1, higher = bigger gap).

        Uses resolved.json RR/UCN data if available, otherwise assumes high gap.
        """
        resolved = user_data.get("resolved", {})

        # Check if target exists in resolved data
        # For now, simple heuristic: if not in resolved, gap = 0.9
        # If in resolved but low certainty, gap based on UCN
        if target_path not in resolved:
            return 0.9  # High gap, no data

        entry = resolved[target_path]
        ucnrr = entry.get("ucnrr", 100)  # Default to high uncertainty

        # Convert UCN (0..100) to gap score (0..1)
        gap_score = ucnrr / 100.0
        return min(1.0, max(0.0, gap_score))

    def _calculate_impact_score(self, coach_id: str) -> float:
        """
        Calculate impact score based on coach performance (0..1).

        Uses sentiment trend from analysis report.
        """
        coaches = self.analysis_report.get("coaches", {})
        if coach_id not in coaches:
            return 0.5  # Neutral if no data

        coach_metrics = coaches[coach_id]
        sentiment = coach_metrics.get("sentiment_trend", {})
        positive_rate = sentiment.get("positive", 0.0)

        # Convert positive rate (0..1) to impact score
        # Add baseline: even 0% positive gets 0.3 impact
        return min(1.0, 0.3 + positive_rate * 0.7)

    def _calculate_recency_score(
        self,
        target_path: str,
        recent_interactions: Dict[str, datetime],
    ) -> float:
        """
        Calculate recency score (0..1, higher = not recently touched).
        """
        if target_path not in recent_interactions:
            return 1.0  # Never touched = high recency score

        # Get hours since last interaction
        last_interaction = recent_interactions[target_path]
        hours_ago = (datetime.now(timezone.utc) - last_interaction).total_seconds() / 3600

        # Decay: after recency_window_hours, score = 0
        score = hours_ago / self.recency_window_hours
        return min(1.0, max(0.0, score))

    def _calculate_cost_score(
        self,
        target_path: str,
        failure_history: Dict[str, int],
    ) -> float:
        """
        Calculate cost score (0..1, lower if many failures).
        """
        failures = failure_history.get(target_path, 0)

        # Apply exponential decay
        score = self.cost_failure_multiplier ** failures
        return max(0.0, score)

    def _build_reason(
        self,
        gap_score: float,
        impact_score: float,
        recency_score: float,
        cost_score: float,
        coach_id: str,
    ) -> str:
        """Build human-readable reason for priority."""
        parts = []

        if gap_score > 0.7:
            parts.append("High data gap")
        elif gap_score > 0.4:
            parts.append("Moderate data gap")

        if impact_score > 0.7:
            parts.append(f"{coach_id} performing well")
        elif impact_score < 0.4:
            parts.append(f"{coach_id} needs tuning")

        if recency_score > 0.8:
            parts.append("not recently explored")
        elif recency_score < 0.2:
            parts.append("recently visited")

        if cost_score < 0.6:
            parts.append("multiple prior failures")

        if not parts:
            parts.append("standard exploration priority")

        return "; ".join(parts)

    def _generate_fallback_agenda(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Generate a fallback agenda with placeholder items when no valid targets found.

        Args:
            limit: Maximum number of fallback items

        Returns:
            List of fallback agenda items
        """
        fallback_items = []

        # Use namespace→coach mapping from config to generate sensible defaults
        fallback_namespaces = [
            ("SkillDNA", "career_coach", "Tell me about your recent work experience and skills."),
            ("BeliefValueDNA", "beliefdna_coach", "What values and beliefs guide your important decisions?"),
            ("LanguageStyleDNA", "chatdna_coach", "How would you describe your communication style?"),
            ("PsyDNA", "personality_test_coach", "Let's explore your personality traits."),
            ("ReDNA", "relationship_coach", "Tell me about your important relationships."),
        ]

        for namespace, coach, prompt in fallback_namespaces[:limit]:
            fallback_items.append({
                "target": f"{namespace}.general_exploration",
                "priority": 0.5,
                "reason": "fallback_agenda_due_to_low_signal",
                "suggested_coach": coach,
                "suggested_prompt": prompt,
                "evidence_refs": ["fallback:no_telemetry"],
            })

        return fallback_items

    def _save_agenda(self, user_dir: Path, agenda: Dict[str, Any]) -> None:
        """Save agenda to user's curiosity directory."""
        curiosity_dir = user_dir / "curiosity"
        curiosity_dir.mkdir(parents=True, exist_ok=True)

        agenda_file = curiosity_dir / "agenda.json"
        with open(agenda_file, "w") as f:
            json.dump(agenda, f, indent=2)

        logger.info(f"Saved curiosity agenda to {agenda_file}")


def generate_agenda(
    user_id: str,
    limit: Optional[int] = None,
    min_priority: Optional[float] = None,
    debug: bool = False,
    fallback: bool = True,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate a curiosity agenda.

    Args:
        user_id: User ID
        limit: Maximum number of items
        min_priority: Override config min_priority
        debug: Include diagnostic information
        fallback: Generate fallback agenda if empty
        config_path: Optional custom config path

    Returns:
        Agenda dict
    """
    engine = CuriosityEngine(config_path=config_path)
    return engine.generate_agenda(
        user_id=user_id,
        limit=limit,
        min_priority=min_priority,
        debug=debug,
        fallback=fallback,
    )
