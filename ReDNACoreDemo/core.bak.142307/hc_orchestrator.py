"""
HC Orchestrator — Jarvis Functionality Phase 1

Enables autonomous Head Coach orchestration by:
1. Consulting Curiosity Engine v2 for "what to pursue next"
2. Consulting Self-Improvement analytics for live tone/creativity guidance
3. Proposing contextual nudges with permission-aware actions
4. Adaptive tone & empathy through real-time analysis (Connection Phase 1)

Part of Benchmark #6/#8 integration for autonomous learning and exploration.
"""

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ingestion_pipeline import get_ingestion_pipeline
from .head_coach.empathy_monitor import EmpathyMonitor
from .head_coach.tool_manager import ToolManager

try:
    from ReDNACoreDemo.core.curiosity.curiosity_engine_v3 import (
        CuriosityEngineV3,
        ReprioritizationEvent,
        ReprioritizationTrigger,
    )
except Exception:  # pragma: no cover - optional import
    CuriosityEngineV3 = None  # type: ignore
    ReprioritizationEvent = None  # type: ignore
    ReprioritizationTrigger = None  # type: ignore

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent / "hc_orchestrator_config.json"


class Nudge:
    """Structured nudge object for HC suggestions."""

    def __init__(
        self,
        kind: str,
        title: str,
        coach_id: str,
        prompt: str,
        priority: float,
        reason: str,
        requires_consent: bool = False,
        target: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
    ):
        self.kind = kind
        self.title = title
        self.coach_id = coach_id
        self.prompt = prompt
        self.priority = priority
        self.reason = reason
        self.requires_consent = requires_consent
        self.target = target
        self.evidence_refs = evidence_refs or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "kind": self.kind,
            "title": self.title,
            "coach_id": self.coach_id,
            "prompt": self.prompt,
            "priority": self.priority,
            "reason": self.reason,
            "requires_consent": self.requires_consent,
            "target": self.target,
            "evidence_refs": self.evidence_refs,
        }


class HCOrchestrator:
    """
    Head Coach Orchestrator for autonomous learning and exploration.

    Responsibilities:
    - Pull behavior context, learning summary, and curiosity agenda
    - Generate contextual nudges for exploration
    - Apply permission gates for sensitive namespaces
    - Influence behavior hints based on learning analytics
    """

    def __init__(self, config_path: Optional[Path] = None, data_root: Optional[Path] = None):
        """
        Initialize orchestrator.

        Args:
            config_path: Path to orchestrator config JSON
            data_root: Root directory for data files
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.data_root = data_root or Path(__file__).parent.parent / "data"

        # Load configuration
        self.config = self._load_config()

        # Cached learning report (refreshed on demand)
        self._learning_cache: Optional[Dict[str, Any]] = None
        self._learning_cache_time: Optional[datetime] = None

        # Activation snapshot cache (per user/context version)
        self._activation_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # Tone adapter for Connection Phase 1 (lazy init)
        self._tone_adapter: Optional[Any] = None
        try:
            self._ingestion_pipeline = get_ingestion_pipeline()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to initialize ingestion pipeline: %s", exc)
            self._ingestion_pipeline = None

        self._empathy_monitors: Dict[str, EmpathyMonitor] = {}

        if CuriosityEngineV3 is not None:
            try:
                self._curiosity_engine_v3 = CuriosityEngineV3()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to initialize Curiosity Engine v3: %s", exc)
                self._curiosity_engine_v3 = None
        else:
            self._curiosity_engine_v3 = None
        self._tool_manager: Optional[ToolManager] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load orchestrator configuration."""
        if not self.config_path.exists():
            logger.warning(f"Orchestrator config not found at {self.config_path}, using defaults")
            return {
                "min_nudge_priority": 0.65,
                "idle_seconds": 90,
                "learning_influence": {"tone_weight": 0.3, "creativity_weight": 0.2},
                "respect_consent": True,
                "max_nudges_per_turn": 1,
                "sensitive_namespaces": ["PaDNA", "Photo"],
            }

        with open(self.config_path, "r") as f:
            return json.load(f)

    def _get_learning_report(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get cached learning report or load from disk.

        Args:
            force_refresh: Force reload from disk

        Returns:
            Learning report dict or None if not found
        """
        # Use cache if fresh (< 5 minutes)
        if not force_refresh and self._learning_cache is not None:
            if self._learning_cache_time is not None:
                age = (datetime.now(timezone.utc) - self._learning_cache_time).total_seconds()
                if age < 300:  # 5 minutes
                    return self._learning_cache

        # Load from disk
        report_path = self.data_root / "learning" / "analysis_report.json"
        if not report_path.exists():
            logger.info("Learning report not found, skipping learning influence")
            return None

        try:
            with open(report_path, "r") as f:
                report = json.load(f)

            self._learning_cache = report
            self._learning_cache_time = datetime.now(timezone.utc)
            return report
        except Exception as e:
            logger.error(f"Failed to load learning report: {e}")
            return None

    def _get_tone_adapter(self):
        """Lazy-load tone adapter."""
        if self._tone_adapter is None:
            try:
                from ReDNACoreDemo.core.connection.tone_adapter import create_tone_adapter
                self._tone_adapter = create_tone_adapter()
            except Exception as e:
                logger.warning(f"Failed to load tone adapter: {e}")
                self._tone_adapter = None
        return self._tone_adapter

    def on_turn_start(
        self,
        user_id: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        behavior_context: Optional[Dict[str, Any]] = None,
        recent_history: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Called at the start of each HC turn to enrich behavior context.

        Args:
            user_id: User identifier
            text: User's message text
            meta: Optional metadata
            behavior_context: Existing behavior context from situational awareness
            recent_history: Last 2-3 messages for tone analysis

        Returns:
            Updated behavior context with learning influences and connection adjustments
        """
        context = behavior_context or {}
        meta = meta or {}
        recent_history = recent_history or []

        self._ingest_turn_start(
            user_id=user_id,
            text=text,
            meta=meta,
            recent_history=recent_history,
        )
        self._apply_empathy_analysis(
            user_id=user_id,
            text=text,
            meta=meta,
            recent_history=recent_history,
            context=context,
        )

        # Pull learning summary
        learning_report = self._get_learning_report()

        if learning_report is not None:
            # Apply learning influence to tone/creativity hints
            context = self._apply_learning_influence(context, learning_report)

            # Add learning summary for narrator trace
            if meta.get("developer_mode", False):
                context["learning_summary"] = self._extract_learning_summary(learning_report)

        # Apply Connection Phase 1: Adaptive tone & empathy
        tone_adapter = self._get_tone_adapter()
        if tone_adapter:
            try:
                # Analyze turn
                analysis = tone_adapter.analyze_turn(
                    user_text=text,
                    recent_history=recent_history,
                    user_id=user_id
                )

                # Compute adjustments
                adjustments = tone_adapter.compute_adjustments(
                    tone_score=analysis["tone_score"],
                    formality_score=analysis["formality_score"],
                    empathy_cue=analysis["empathy_cue"],
                    behavior_context=context,
                    user_id=user_id
                )

                # Merge hints into context
                if "hints" in adjustments:
                    for key, value in adjustments["hints"].items():
                        context[key] = value

                # Store connection data for telemetry
                context["_connection_data"] = {
                    "tone_target": adjustments["hints"].get("tone_target"),
                    "formality_bias": adjustments["hints"].get("formality_bias"),
                    "empathy_bias": adjustments["hints"].get("empathy_bias"),
                    "confidence": adjustments.get("confidence"),
                    "signals": analysis.get("signals", {})
                }

                # Developer trace
                if meta.get("developer_mode", False) or self._should_trace_connection():
                    logger.info(
                        f"[HC-Connection] tone_target={adjustments['hints'].get('tone_target')} "
                        f"formality={adjustments['hints'].get('formality_bias'):.2f} "
                        f"empathy_bias={adjustments['hints'].get('empathy_bias'):.2f} "
                        f"(ema α={tone_adapter.config.get('ema_alpha', 0.5)})"
                    )

            except Exception as e:
                logger.error(f"Tone adapter failed: {e}")

        return context

    def _apply_empathy_analysis(
        self,
        *,
        user_id: str,
        text: str,
        meta: Dict[str, Any],
        recent_history: List[str],
        context: Dict[str, Any],
    ) -> None:
        monitor = self._get_empathy_monitor(user_id)
        snapshot = monitor.observe_turn(
            message_text=text,
            recent_history=recent_history,
            metadata=meta,
        )
        context["_empathy_state"] = snapshot.to_dict()

        hints = context.setdefault("hints", {})
        if snapshot.primary_needs:
            hints["bonding_need"] = snapshot.primary_needs[0]
        if snapshot.recommended_actions:
            hints["bonding_action"] = snapshot.recommended_actions[0]
        hints["empathy_state"] = snapshot.emotional_state.value
        hints["trust_score"] = snapshot.bonding_metrics.get("trust_score")

        self._log_telemetry_event(
            user_id,
            "empathy_snapshot",
            {
                "emotional_state": snapshot.emotional_state.value,
                "intensity": snapshot.intensity,
                "confidence": snapshot.confidence,
                "primary_need": snapshot.primary_needs[0] if snapshot.primary_needs else None,
                "recommendation": snapshot.recommended_actions[0] if snapshot.recommended_actions else None,
                "trust_score": snapshot.bonding_metrics.get("trust_score"),
                "rapport_score": snapshot.bonding_metrics.get("rapport_score"),
            },
        )

    def _ingest_turn_start(
        self,
        *,
        user_id: str,
        text: str,
        meta: Dict[str, Any],
        recent_history: List[str],
    ) -> None:
        """Record the user's turn for ingestion telemetry."""
        if not self._ingestion_pipeline or not text:
            return

        ingestion_meta = {
            "tone_hint": meta.get("tone"),
            "developer_mode": meta.get("developer_mode", False),
            "recent_history_count": len(recent_history),
            "sensitivity_level": meta.get("sensitivity_level", "standard"),
        }

        cleaned_meta = {k: v for k, v in ingestion_meta.items() if v is not None}

        try:
            self._ingestion_pipeline.capture_chat(
                user_id=user_id,
                text=text,
                meta=cleaned_meta,
                source="head_coach_turn",
                actor="hc_orchestrator",
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("HC ingestion capture failed for %s: %s", user_id, exc)

    def _get_empathy_monitor(self, user_id: str) -> EmpathyMonitor:
        monitor = self._empathy_monitors.get(user_id)
        if monitor is None:
            monitor = EmpathyMonitor(user_id=user_id, data_root=self.data_root)
            self._empathy_monitors[user_id] = monitor
        return monitor

    def get_tool_manager(self) -> ToolManager:
        if self._tool_manager is None:
            self._tool_manager = ToolManager()
        return self._tool_manager

    def _should_trace_connection(self) -> bool:
        """Check if connection traces should be logged."""
        try:
            tone_adapter = self._get_tone_adapter()
            if tone_adapter:
                return tone_adapter.config.get("developer_trace", False)
        except:
            pass
        return False

    def _apply_learning_influence(
        self,
        context: Dict[str, Any],
        learning_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply learning analytics to behavior context (tone, creativity hints).

        Args:
            context: Current behavior context
            learning_report: Latest learning analysis

        Returns:
            Updated behavior context
        """
        influence_config = self.config["learning_influence"]
        tone_weight = influence_config.get("tone_weight", 0.3)
        creativity_weight = influence_config.get("creativity_weight", 0.2)

        # Extract coach-level metrics
        coaches = learning_report.get("coaches", {})

        # Aggregate tone signals (positive_rate as proxy for empathy/warmth)
        tone_scores = [
            coach.get("positive_rate", 0.5)
            for coach in coaches.values()
            if coach.get("positive_rate") is not None
        ]

        if tone_scores:
            avg_tone = sum(tone_scores) / len(tone_scores)

            # Adjust tone hint based on performance
            if avg_tone > 0.7:
                context["tone_hint"] = "empathetic"
            elif avg_tone < 0.4:
                context["tone_hint"] = "concise"
            else:
                context["tone_hint"] = "balanced"

            # Store raw score for narrator trace
            context["tone_bias"] = round(avg_tone, 2)

        # Aggregate creativity signals (inverse of avg_latency_ms as proxy)
        latency_scores = [
            coach.get("avg_latency_ms", 2000)
            for coach in coaches.values()
            if coach.get("avg_latency_ms") is not None
        ]

        if latency_scores:
            avg_latency = sum(latency_scores) / len(latency_scores)

            # Lower latency → more creative/exploratory
            # Map 500-3000ms to 0.2-0.8 creativity bias
            creativity_bias = max(0.2, min(0.8, 1.0 - (avg_latency - 500) / 2500))
            context["creativity_bias"] = round(creativity_bias, 2)

        return context

    def _extract_learning_summary(self, learning_report: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics for narrator trace."""
        coaches = learning_report.get("coaches", {})

        total_turns = sum(c.get("total_turns", 0) for c in coaches.values())
        avg_positive = sum(c.get("positive_rate", 0) for c in coaches.values()) / max(len(coaches), 1)

        return {
            "total_turns_analyzed": total_turns,
            "avg_positive_rate": round(avg_positive, 2),
            "coaches_analyzed": len(coaches),
        }

    def maybe_nudge(
        self,
        user_id: str,
        text: str,
        idle_flag: bool = False,
        developer_mode: bool = False,
    ) -> Optional[Nudge]:
        """
        Generate a curiosity-driven nudge if appropriate.

        Args:
            user_id: User identifier
            text: User's message text
            idle_flag: Whether user is idle (detected by timeout)
            developer_mode: Include narrator trace

        Returns:
            Nudge object or None if no nudge appropriate
        """
        min_priority = self.config["min_nudge_priority"]

        # Get curiosity agenda
        try:
            from ReDNACoreDemo.core.curiosity.curiosity_engine_v2 import generate_agenda

            agenda = generate_agenda(
                user_id=user_id,
                limit=8,
                min_priority=min_priority,
                fallback=True,  # Always generate fallback
            )

            items = agenda.get("items", [])

            if not items:
                logger.info(f"No curiosity items for {user_id}, skipping nudge")
                return None

            # Select top item above threshold
            top_item = items[0]
            priority = top_item.get("priority", 0.0)

            if priority < min_priority:
                logger.info(f"Top item priority {priority} < min {min_priority}, suppressed")
                return None

            # Build nudge
            nudge = Nudge(
                kind="curiosity_nudge",
                title="Close a high-value gap",
                coach_id=top_item.get("suggested_coach", "head_coach"),
                prompt=top_item.get("suggested_prompt", "Tell me more."),
                priority=priority,
                reason=top_item.get("reason", "High impact + low coverage"),
                target=top_item.get("target"),
                evidence_refs=top_item.get("evidence_refs", []),
            )

            # Apply permission gate
            nudge = self.apply_permission_gate(nudge, user_id)

            # Emit telemetry
            self._emit_nudge_telemetry(user_id, nudge, "shown")

            if developer_mode:
                logger.info(
                    f"[HC-Orchestrator] top_target={nudge.target} p={nudge.priority:.2f} "
                    f"coach={nudge.coach_id} consent={nudge.requires_consent}"
                )

            return nudge

        except Exception as e:
            logger.error(f"Failed to generate nudge: {e}")
            return None

    def apply_permission_gate(self, nudge: Nudge, user_id: str) -> Nudge:
        """
        Apply permission checks for sensitive namespaces.

        Args:
            nudge: Candidate nudge
            user_id: User identifier

        Returns:
            Nudge with requires_consent flag set if needed
        """
        if not self.config["respect_consent"]:
            return nudge

        sensitive_namespaces = self.config.get("sensitive_namespaces", ["PaDNA", "Photo"])

        # Check if target touches sensitive namespace
        target = nudge.target or ""

        for ns in sensitive_namespaces:
            if target.startswith(ns):
                nudge.requires_consent = True
                logger.info(f"Nudge target {target} requires consent (namespace: {ns})")
                break

        return nudge

    def _emit_nudge_telemetry(
        self,
        user_id: str,
        nudge: Nudge,
        event: str,
        reason: Optional[str] = None,
    ):
        """
        Emit telemetry event for nudge.

        Args:
            user_id: User identifier
            nudge: Nudge object
            event: Event type (shown, suppressed, accepted, rejected)
            reason: Optional reason for suppression
        """
        telemetry_path = self.data_root / "learning" / "nudge_telemetry.jsonl"
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "event": f"nudge_{event}",
            "nudge": nudge.to_dict(),
        }

        if reason:
            entry["reason"] = reason

        try:
            with open(telemetry_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to emit nudge telemetry: {e}")

    def enqueue_conflict_to_curiosity(
        self,
        user_id: str,
        trait: str,
        conflict_data: Dict[str, Any]
    ) -> None:
        """
        Enqueue a refinement conflict to the curiosity engine for investigation.

        Args:
            user_id: User identifier
            trait: Trait with conflict
            conflict_data: Conflict details (proposals, confidence, etc.)
        """
        try:
            from ReDNACoreDemo.core.curiosity.curiosity_engine_v2 import enqueue_custom_item

            # Build curiosity item for this conflict
            item = {
                "target": trait,
                "kind": "conflict_investigation",
                "priority": 0.85,  # High priority for conflicts
                "reason": f"Conflicting trait proposals detected (requires investigation)",
                "suggested_coach": "head_coach",
                "suggested_prompt": f"Let's investigate the conflicting signals for {trait}. Can you clarify?",
                "metadata": {
                    "conflict_id": conflict_data.get("conflict_id"),
                    "proposals": conflict_data.get("proposals", []),
                    "opened_at": conflict_data.get("opened_at")
                }
            }

            # Enqueue to curiosity engine
            enqueue_custom_item(user_id=user_id, item=item)

            logger.info(f"Enqueued conflict for {trait} to curiosity engine for user {user_id}")

        except Exception as e:
                logger.warning(f"Failed to enqueue conflict to curiosity: {e}")

    def maybe_propose_ui_improvements(
        self,
        user_id: str,
        trigger_context: Optional[Dict[str, Any]] = None,
        max_proposals: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate UI improvement proposals via Jarvis-Codex.

        Args:
            user_id: User ID for context
            trigger_context: Optional context (e.g., learning analysis results, explicit command)
            max_proposals: Maximum proposals to generate

        Returns:
            List of generated proposals

        Triggers:
        - After /learning/analyze shows recurring confusion
        - On explicit command (e.g., "optimize labels")
        - On threshold cadence (e.g., daily check)
        """

        try:
            from .jarvis_codex.proposal_generator import create_proposal_generator
            from .jarvis_codex.codex_agent import create_codex_agent
            import anthropic
            import os

            # Create proposal generator
            project_root = Path.cwd()

            # Initialize LLM client if API key available
            llm_client = None
            if os.getenv("ANTHROPIC_API_KEY"):
                llm_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            generator = create_proposal_generator(
                project_root=project_root,
                llm_client=llm_client
            )

            proposals = []

            # Determine generation strategy based on trigger
            if trigger_context and "analysis_results" in trigger_context:
                # Analysis-driven proposals (from Self-Improvement)
                analysis_results = trigger_context["analysis_results"]
                proposals = generator.trigger_analysis_based_proposals(
                    analysis_results,
                    max_proposals=max_proposals
                )

            elif trigger_context and "explicit_command" in trigger_context:
                # Explicit command (e.g., "optimize UI labels in DevX")
                command = trigger_context["explicit_command"]

                # Determine directory from command
                if "devx" in command.lower():
                    directory = Path("devx/frontend/src")
                elif "web" in command.lower():
                    directory = Path("web/src")
                else:
                    # Scan both
                    devx_proposals = generator.scan_directory_for_proposals(
                        Path("devx/frontend/src"),
                        intent_context="optimize labels per HC request",
                        max_proposals=max(2, max_proposals // 2),
                        use_llm=bool(llm_client)
                    )
                    web_proposals = generator.scan_directory_for_proposals(
                        Path("web/src"),
                        intent_context="optimize labels per HC request",
                        max_proposals=max(2, max_proposals // 2),
                        use_llm=bool(llm_client)
                    )
                    proposals = devx_proposals + web_proposals
                    proposals = proposals[:max_proposals]

                if not proposals and "directory" in locals():
                    proposals = generator.scan_directory_for_proposals(
                        directory,
                        intent_context="optimize labels per HC request",
                        max_proposals=max_proposals,
                        use_llm=bool(llm_client)
                    )

            else:
                # Threshold cadence — light scan of recent files
                proposals = generator.scan_directory_for_proposals(
                    Path("devx/frontend/src/routes"),
                    intent_context="routine UI clarity check",
                    max_proposals=max_proposals,
                    use_llm=bool(llm_client)
                )

            # Submit proposals to Jarvis-Codex
            codex_agent = create_codex_agent()
            submitted = []

            for proposal in proposals:
                try:
                    # Validate and create proposal
                    result = codex_agent.propose_change(
                        scope=proposal["scope"],
                        file_path=proposal["file"],
                        intent=proposal["intent"],
                        suggested_change=proposal["suggested_change"],
                        confidence=proposal["confidence"],
                        source=proposal["source"]
                    )

                    if result[0]:  # Success
                        submitted.append(result[1])  # Proposal data

                        # Log telemetry
                        self._log_telemetry_event(
                            user_id=user_id,
                            event_type="codex_proposed",
                            data={
                                "proposal_id": result[1].get("proposal_id"),
                                "file": proposal["file"],
                                "intent": proposal["intent"],
                                "confidence": proposal["confidence"]
                            }
                        )

                except Exception as e:
                    logger.warning(f"Failed to submit proposal for {proposal['file']}: {e}")

            logger.info(f"HC proposed {len(submitted)} UI improvements for user {user_id}")
            return submitted

        except Exception as e:
            logger.exception(f"Failed to generate UI proposals: {e}")
            return []

    def build_activation_snapshot(
        self,
        user_id: str,
        context_version: Optional[int] = None,
        behavior_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build per-turn activation snapshot for Coach Brain visualization.

        Args:
            user_id: User identifier
            context_version: Optional context version hint from caller
            behavior_context: Optional pre-loaded behavior context (avoids disk read)

        Returns:
            Snapshot dict with nodes, edges, and derived metadata.
        """
        from ReDNACoreDemo.core.head_coach.session_manager import get_session_manager
        from ReDNACoreDemo.core.coach_mode_manager import MODE_DISPLAY_NAMES

        session_manager = get_session_manager()
        session = session_manager.get_session(user_id)

        actual_version = session.context_version
        if actual_version == 0:
            # Fallback to most recent cached snapshot if available
            for cache_key in reversed(self._activation_cache):
                if cache_key.startswith(f"{user_id}:"):
                    cached_snapshot = self._activation_cache[cache_key]
                    return cached_snapshot

            # No session built yet – return placeholder snapshot
            return {
                "ts": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "context_version": 0,
                "active_coach_id": "head_coach",
                "nodes": [
                    {"id": "head_coach", "label": "Head Coach", "active": True, "weight": 1.0},
                    {"id": "curiosity_engine", "label": "Curiosity Engine", "active": False, "weight": 0.0},
                    {"id": "learning", "label": "Self-Improvement", "active": False, "weight": 0.0},
                    {"id": "permission", "label": "Permission Guard", "active": False, "weight": 0.0},
                ],
                "edges": [],
                "meta": {
                    "note": "No context built yet for this user."
                }
            }

        cache_key = f"{user_id}:{actual_version}"
        cached = self._activation_cache.get(cache_key)
        if cached:
            return cached

        # Use session behavior context unless explicitly provided
        behavior_context = behavior_context or session.behavior_context or {}
        connection_data = behavior_context.get("_connection_data", {})

        active_coach_id = session.active_coach_id or "head_coach"
        coach_label = MODE_DISPLAY_NAMES.get(
            active_coach_id,
            active_coach_id.replace("_", " ").title()
        )

        # Augmentation weight from connection confidence (fallback to heuristic)
        augment_confidence = connection_data.get("confidence")
        if augment_confidence is None:
            hints = behavior_context.get("hints", {})
            augment_confidence = hints.get("confidence") or hints.get("confidence_bias")
        if augment_confidence is None:
            augment_confidence = 0.8 if active_coach_id != "head_coach" else 0.0
        augment_weight = float(max(0.0, min(1.0, augment_confidence)))

        # Curiosity signals
        curiosity_item, curiosity_priority, requires_consent = self._peek_curiosity_top(user_id)
        curiosity_weight = float(max(0.0, min(1.0, curiosity_priority)))

        # Learning influence
        learning_weight = self._compute_learning_weight()

        # Permission guard weight
        permission_weight = 1.0 if requires_consent else (0.45 if self.config.get("respect_consent", True) else 0.0)

        nodes: List[Dict[str, Any]] = [
            {
                "id": "head_coach",
                "label": "Head Coach",
                "active": True,
                "weight": 1.0,
            }
        ]

        if active_coach_id != "head_coach":
            nodes.append({
                "id": active_coach_id,
                "label": coach_label,
                "active": True,
                "weight": round(augment_weight, 2),
            })
        else:
            nodes.append({
                "id": "head_coach_role",
                "label": "Head Coach (Solo)",
                "active": True,
                "weight": round(augment_weight, 2),
            })

        nodes.append({
            "id": "curiosity_engine",
            "label": "Curiosity Engine",
            "active": curiosity_weight >= 0.25,
            "weight": round(curiosity_weight, 2),
        })

        nodes.append({
            "id": "learning",
            "label": "Self-Improvement",
            "active": learning_weight >= 0.2,
            "weight": round(learning_weight, 2),
        })

        nodes.append({
            "id": "permission",
            "label": "Permission Guard",
            "active": requires_consent,
            "weight": round(permission_weight, 2),
        })

        edges: List[Dict[str, Any]] = []
        augment_target_id = active_coach_id if active_coach_id != "head_coach" else "head_coach_role"
        if augment_weight > 0:
            edges.append({
                "from": "head_coach",
                "to": augment_target_id,
                "strength": round(augment_weight, 2),
            })

        if curiosity_weight > 0:
            edges.append({
                "from": "curiosity_engine",
                "to": "head_coach",
                "strength": round(curiosity_weight, 2),
            })

        if learning_weight > 0:
            edges.append({
                "from": "learning",
                "to": "head_coach",
                "strength": round(learning_weight, 2),
            })

        if permission_weight > 0:
            edges.append({
                "from": "permission",
                "to": "head_coach",
                "strength": round(permission_weight, 2),
            })

        snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "context_version": actual_version,
            "active_coach_id": active_coach_id,
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "augment_confidence": round(augment_weight, 2),
                "curiosity_priority": round(curiosity_weight, 2),
                "curiosity_target": curiosity_item.get("target") if curiosity_item else None,
                "learning_positive_rate": round(learning_weight, 2),
                "requires_consent": requires_consent,
                "requested_context_version": context_version,
            }
        }

        # Cache snapshot (bounded LRU of 32 entries)
        self._activation_cache[cache_key] = snapshot
        while len(self._activation_cache) > 32:
            self._activation_cache.popitem(last=False)

        return snapshot

    def _peek_curiosity_top(
        self,
        user_id: str,
    ) -> Tuple[Optional[Dict[str, Any]], float, bool]:
        """Peek top curiosity agenda item without emitting telemetry."""
        agenda: Optional[Dict[str, Any]] = None

        if getattr(self, "_curiosity_engine_v3", None) is not None:
            try:
                agenda = self._curiosity_engine_v3.generate_agenda(
                    user_id=user_id,
                    limit=1,
                    min_priority=0.0,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Curiosity Engine v3 peek failed for %s: %s", user_id, exc)
                agenda = None

        if agenda is None or not agenda.get("items"):
            try:
                from ReDNACoreDemo.core.curiosity.curiosity_engine_v2 import generate_agenda as generate_agenda_v2

                agenda = generate_agenda_v2(
                    user_id=user_id,
                    limit=1,
                    min_priority=0.0,
                    fallback=False,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug(f"Curiosity peek failed for {user_id}: {exc}")
                return None, 0.0, False

        items = agenda.get("items", []) if isinstance(agenda, dict) else []
        if not items:
            return None, 0.0, False

        top = items[0]
        priority = float(top.get("priority") or 0.0)

        nudge = Nudge(
            kind=top.get("kind", "curiosity"),
            title=top.get("title", "Curiosity Target"),
            coach_id=top.get("suggested_coach", "head_coach"),
            prompt=top.get("suggested_prompt", ""),
            priority=priority,
            reason=top.get("reason", "High impact target"),
            target=top.get("target"),
            evidence_refs=top.get("evidence_refs", []),
        )
        nudge = self.apply_permission_gate(nudge, user_id)

        return top, max(0.0, min(1.0, priority)), bool(nudge.requires_consent)

    def get_daily_curiosity_prompt(
        self,
        user_id: str,
        *,
        limit: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """Return daily curiosity brief for Head Coach dashboards."""
        engine = getattr(self, "_curiosity_engine_v3", None)
        if engine is None:
            return None
        try:
            return engine.generate_daily_prompt(user_id=user_id, limit=limit)
        except Exception as exc:  # pragma: no cover
            logger.debug("Daily curiosity prompt failed for %s: %s", user_id, exc)
            return None

    def _compute_learning_weight(self) -> float:
        """Derive learning influence weight from cached report."""
        report = self._get_learning_report()
        if not report:
            return 0.0

        coaches = report.get("coaches", {})
        if not coaches:
            return 0.0

        positives: List[float] = []
        for coach in coaches.values():
            rate = coach.get("positive_rate")
            if rate is not None:
                try:
                    positives.append(float(rate))
                except (TypeError, ValueError):
                    continue

        if not positives:
            return 0.0

        avg_positive = sum(positives) / len(positives)
        return max(0.0, min(1.0, round(avg_positive, 2)))

    def _log_telemetry_event(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """Log telemetry event to insights directory."""
        try:
            insights_dir = Path(__file__).parent.parent / "prompts" / "insights"
            insights_dir.mkdir(parents=True, exist_ok=True)

            telemetry_file = insights_dir / "hc_orchestrator_telemetry.jsonl"

            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "event_type": event_type,
                **data
            }

            with open(telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

        except Exception as e:
            logger.warning(f"Failed to log telemetry event: {e}")


# Convenience function
def create_orchestrator(
    config_path: Optional[Path] = None,
    data_root: Optional[Path] = None,
) -> HCOrchestrator:
    """Create HC orchestrator instance."""
    return HCOrchestrator(config_path=config_path, data_root=data_root)
