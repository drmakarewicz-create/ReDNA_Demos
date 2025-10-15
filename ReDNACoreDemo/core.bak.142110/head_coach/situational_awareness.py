"""
Head Coach Situational Awareness Engine
========================================

4-layer user state model with TTL caching for Jarvis-class context awareness.

Layers:
1. user_core_state - Always fresh (no cache)
2. goal_task_layer - 5-minute TTL
3. context_layer - 1-hour TTL
4. memory_layer - 24-hour TTL

Features:
- Pluggable emotional tone extractor
- Privacy-aware (no raw message text)
- Workshop-compatible summary
- Policy/provenance tracking
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

# TTL Constants (in seconds)
TTL_CORE = 0  # Always fresh
TTL_GOAL_TASK = 5 * 60  # 5 minutes
TTL_CONTEXT = 60 * 60  # 1 hour
TTL_MEMORY = 24 * 60 * 60  # 24 hours


class AwarenessEngine:
    """
    Situational awareness engine for Head Coach v2.

    Builds 4-layer user state snapshot with TTL caching.
    """

    def __init__(self, tone_extractor: Optional[Callable] = None):
        """
        Initialize awareness engine.

        Args:
            tone_extractor: Optional custom emotional tone extractor
                           Signature: (messages: List[Dict]) -> (tone: str, confidence: float)
        """
        self.tone_extractor = tone_extractor or self._default_tone_extractor

    def get_snapshot(
        self,
        user_id: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get situational awareness snapshot for user.

        Args:
            user_id: User identifier
            force_refresh: Force cache refresh for all layers

        Returns:
            Complete awareness snapshot matching hc_awareness.schema.json
        """
        start_time = time.time()

        # Load cached snapshot if valid
        if not force_refresh:
            cached = self._load_cache(user_id)
            if cached:
                # Check which layers need refresh
                cache_times = cached.get("cache_timestamps", {})
                now = datetime.now(timezone.utc)

                needs_refresh = {
                    "core": True,  # Always refresh
                    "goal_task": self._is_expired(cache_times.get("goal_task"), TTL_GOAL_TASK, now),
                    "context": self._is_expired(cache_times.get("context"), TTL_CONTEXT, now),
                    "memory": self._is_expired(cache_times.get("memory"), TTL_MEMORY, now)
                }

                # If only core needs refresh, update just that layer
                if not (needs_refresh["goal_task"] or needs_refresh["context"] or needs_refresh["memory"]):
                    snapshot = cached["snapshot"]
                    snapshot["user_core_state"] = self._build_core_state(user_id)
                    snapshot["ttl_hints"]["core"] = "live"

                    # Update summary
                    snapshot["summary"] = self._build_summary(snapshot)

                    # Update policy
                    build_ms = (time.time() - start_time) * 1000
                    snapshot["policy"]["build_ms"] = round(build_ms, 2)

                    return snapshot

        # Build fresh snapshot
        snapshot = {
            "user_core_state": self._build_core_state(user_id),
            "goal_task_layer": self._build_goal_task_layer(user_id),
            "context_layer": self._build_context_layer(user_id),
            "memory_layer": self._build_memory_layer(user_id),
            "ttl_hints": {
                "core": "live",
                "goal_task": "live",
                "context": "live",
                "memory": "live"
            },
            "policy": {
                "awareness_version": "v1",
                "schema": "hc_awareness.schema.json@v1",
                "build_ms": 0.0,  # Updated below
                "redacted_fields": ["raw_messages"]
            },
            "summary": {}  # Updated below
        }

        # Build summary from snapshot
        snapshot["summary"] = self._build_summary(snapshot)

        # Calculate build time
        build_ms = (time.time() - start_time) * 1000
        snapshot["policy"]["build_ms"] = round(build_ms, 2)

        # Save to cache
        self._save_cache(user_id, snapshot)

        return snapshot

    def _build_core_state(self, user_id: str) -> Dict[str, Any]:
        """Build user_core_state layer (always fresh)."""
        from ..storage import read_user_state

        try:
            resolved, _, _ = read_user_state(user_id)
        except Exception as e:
            logger.warning(f"Could not load user state for {user_id}: {e}")
            resolved = {}

        # Get curiosity hotspots from curiosity engine
        curiosity_hotspots = self._get_curiosity_hotspots(user_id)

        # Load recent conversation messages for emotional tone
        messages = self._load_recent_messages(user_id, limit=5)
        emotional_tone, emotion_confidence = self.tone_extractor(messages)

        # Determine current mode (placeholder - could be from active coach)
        current_mode = "exploration"  # Future: read from session state

        # Get active coach (placeholder)
        active_coach = "head_coach"  # Future: read from coach_mode.json

        # Get last message time
        last_message_time = datetime.now(timezone.utc).isoformat()
        if messages:
            last_message_time = messages[-1].get("ts", last_message_time)

        return {
            "user_id": user_id,
            "active_coach": active_coach,
            "last_message_time": last_message_time,
            "current_mode": current_mode,
            "emotional_tone": emotional_tone,
            "emotion_confidence": emotion_confidence,
            "curiosity_hotspots": curiosity_hotspots
        }

    def _build_goal_task_layer(self, user_id: str) -> Dict[str, Any]:
        """Build goal_task_layer (5-minute TTL)."""
        # Future: Load from task/goal files
        # For now, return empty structures

        return {
            "active_goals": [],
            "pending_tasks": [],
            "plan_states": [],
            "recent_intent_distribution": {}
        }

    def _build_context_layer(self, user_id: str) -> Dict[str, Any]:
        """Build context_layer (1-hour TTL)."""
        now = datetime.now(timezone.utc)

        return {
            "local_time": now.isoformat(),
            "day_of_week": now.strftime("%A"),
            "timezone": "UTC",  # Future: user-specific timezone
            "availability_flag": "active",  # Future: infer from activity
            "recent_external_interactions": []
        }

    def _build_memory_layer(self, user_id: str) -> Dict[str, Any]:
        """Build memory_layer (24-hour TTL)."""
        from ..storage import read_user_state

        try:
            resolved, _, _ = read_user_state(user_id)
        except Exception as e:
            logger.warning(f"Could not load user state for {user_id}: {e}")
            return self._empty_memory_layer()

        # Aggregate RR scores by domain
        domain_rrs = self._aggregate_rr_by_domain(resolved)

        # Classify high/low RR domains
        high_rr_domains = [d for d, rr in domain_rrs.items() if rr >= 70]
        low_rr_domains = [d for d, rr in domain_rrs.items() if rr < 50]

        # Calculate overall RR
        all_rrs = [trait.get("rr", 0) for trait in resolved.values() if isinstance(trait, dict) and "rr" in trait]
        overall_rr = sum(all_rrs) / len(all_rrs) if all_rrs else 0.0

        return {
            "traits_summary": {
                "high_rr_domains": high_rr_domains,
                "low_rr_domains": low_rr_domains,
                "overall_rr": round(overall_rr, 1)
            },
            "hc_history_summary": {
                "successful_patterns": [],
                "failed_patterns": [],
                "total_interactions": 0  # Future: count from conversation log
            },
            "meta_feedback_stats": {
                "avg_satisfaction": 0.0,
                "total_feedback_count": 0
            }
        }

    def _build_summary(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Build summary block for Workshop UI."""
        goal_task = snapshot.get("goal_task_layer", {})
        core = snapshot.get("user_core_state", {})

        # Human-readable emotional state
        tone = core.get("emotional_tone", "neutral")
        confidence = core.get("emotion_confidence", 0.0)
        emotional_state_map = {
            "positive": "Positive and engaged",
            "neutral": "Neutral and focused",
            "negative": "Concerned or uncertain",
            "frustrated": "Frustrated - needs support",
            "curious": "Curious and exploring"
        }
        emotional_state = emotional_state_map.get(tone, "Unknown")
        if confidence < 0.5:
            emotional_state += " (low confidence)"

        return {
            "active_goal_count": len(goal_task.get("active_goals", [])),
            "pending_tasks": len(goal_task.get("pending_tasks", [])),
            "top_curiosity": core.get("curiosity_hotspots", [])[:5],
            "emotional_state": emotional_state
        }

    def _get_curiosity_hotspots(self, user_id: str, top_n: int = 5) -> List[str]:
        """Get top N curiosity hotspots from curiosity engine."""
        try:
            from ..curiosity.curiosity_engine import CuriosityEngine

            engine = CuriosityEngine(data_dir=Path("data"))
            agenda = engine.generate_curiosity_agenda(
                user_id=user_id,
                top_n=top_n,
                min_curiosity=50.0
            )

            return [item.path for item in agenda]
        except Exception as e:
            logger.warning(f"Curiosity engine failed for {user_id}: {e}")
            return []

    def _load_recent_messages(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Load recent conversation messages (for emotional tone extraction)."""
        try:
            from ..hc_llm_agent import load_conversation_history

            messages = load_conversation_history(user_id, limit=limit)
            return messages
        except Exception as e:
            logger.warning(f"Could not load conversation history for {user_id}: {e}")
            return []

    def _default_tone_extractor(self, messages: List[Dict[str, Any]]) -> tuple[str, float]:
        """
        Default emotional tone extractor (keyword-based).

        Pluggable - can be replaced with ML classifier.

        Returns:
            (tone, confidence) where tone in [positive, neutral, negative, frustrated, curious]
        """
        if not messages:
            return ("neutral", 0.5)

        # Combine recent messages
        text = " ".join([msg.get("content", "") for msg in messages]).lower()

        # Keyword matching (simple heuristic)
        positive_keywords = ["great", "thanks", "awesome", "perfect", "yes", "good", "appreciate"]
        negative_keywords = ["wrong", "bad", "no", "not", "don't", "can't", "won't"]
        frustrated_keywords = ["frustrated", "annoying", "stupid", "why", "again", "still"]
        curious_keywords = ["how", "why", "what", "tell me", "curious", "wonder", "interested"]

        scores = {
            "positive": sum(1 for kw in positive_keywords if kw in text),
            "negative": sum(1 for kw in negative_keywords if kw in text),
            "frustrated": sum(1 for kw in frustrated_keywords if kw in text),
            "curious": sum(1 for kw in curious_keywords if kw in text)
        }

        # Determine dominant tone
        max_score = max(scores.values())
        if max_score == 0:
            return ("neutral", 0.6)

        dominant_tone = max(scores, key=scores.get)

        # Calculate confidence (higher score → higher confidence)
        total_keywords = sum(scores.values())
        confidence = min(0.9, 0.5 + (max_score / (total_keywords + 1)) * 0.4)

        return (dominant_tone, round(confidence, 2))

    def _aggregate_rr_by_domain(self, resolved: Dict[str, Any]) -> Dict[str, float]:
        """Aggregate RR scores by top-level domain."""
        domain_rrs = {}

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get("rr", 0)

            # Extract top-level domain (e.g., "SkillDNA" from "SkillDNA.PresentationDNA")
            domain = trait_path.split(".")[0] if "." in trait_path else trait_path

            if domain not in domain_rrs:
                domain_rrs[domain] = []

            domain_rrs[domain].append(rr)

        # Calculate average per domain
        return {
            domain: sum(rrs) / len(rrs) if rrs else 0.0
            for domain, rrs in domain_rrs.items()
        }

    def _empty_memory_layer(self) -> Dict[str, Any]:
        """Empty memory layer fallback."""
        return {
            "traits_summary": {
                "high_rr_domains": [],
                "low_rr_domains": [],
                "overall_rr": 0.0
            },
            "hc_history_summary": {
                "successful_patterns": [],
                "failed_patterns": [],
                "total_interactions": 0
            },
            "meta_feedback_stats": {
                "avg_satisfaction": 0.0,
                "total_feedback_count": 0
            }
        }

    def _load_cache(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load cached awareness snapshot."""
        cache_file = Path(f"data/users/{user_id}/head_coach/awareness.json")

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)

            return cached
        except Exception as e:
            logger.warning(f"Could not load awareness cache for {user_id}: {e}")
            return None

    def _save_cache(self, user_id: str, snapshot: Dict[str, Any]) -> None:
        """Save awareness snapshot to cache."""
        cache_file = Path(f"data/users/{user_id}/head_coach/awareness.json")
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Build cache with timestamps
        now = datetime.now(timezone.utc).isoformat()
        cache_data = {
            "snapshot": snapshot,
            "cache_timestamps": {
                "user_core_state": now,
                "goal_task": now,
                "context": now,
                "memory": now
            }
        }

        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save awareness cache for {user_id}: {e}")

    def _is_expired(
        self,
        timestamp_str: Optional[str],
        ttl_seconds: int,
        now: datetime
    ) -> bool:
        """Check if cached layer is expired."""
        if not timestamp_str:
            return True

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            age_seconds = (now - timestamp).total_seconds()
            return age_seconds > ttl_seconds
        except Exception:
            return True
