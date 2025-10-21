"""
Refinement Resolver — Trait Refinement Depth Phase 1

Reconciles coach proposals for traits using:
- Corroboration gain (consistent proposals boost confidence)
- Contradiction penalty (conflicting proposals down-weight both)
- Recency decay (older evidence weighted less)
- Beta-like confidence calibration (UCN updates)
- RR (Refinement Rating) as 1 - uncertainty

Outputs provenance-rich, reversible records to Core.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from collections import defaultdict
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent / "refinement_config.json"


@dataclass
class RefinementOutcome:
    """Structured outcome from refinement resolution."""

    trait: str
    prior: Dict[str, Any]  # {value, ucn, rr}
    proposal_summary: Dict[str, Any]  # {consistent, conflicting, effective_conf}
    action: str  # "accept" | "hold" | "conflict"
    resolved: Dict[str, Any]  # {value, ucn, rr}
    conflicts: List[Dict[str, Any]]  # [{value, weight, sources}]
    provenance: Dict[str, Any]  # {events: [...]}
    ts: str  # ISO-8601

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


class RefinementResolver:
    """
    Trait refinement resolver for probabilistic trait truthing.

    Reconciles coach proposals with corroboration/contradiction logic,
    calibrates UCN via Beta-like updates, and maintains provenance.
    """

    def __init__(self, config_path: Optional[Path] = None, data_root: Optional[Path] = None):
        """
        Initialize resolver.

        Args:
            config_path: Path to refinement config JSON
            data_root: Root directory for user data
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.data_root = data_root or Path(__file__).parent.parent.parent / "data"

        # Load configuration
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load refinement configuration."""
        if not self.config_path.exists():
            logger.warning(f"Refinement config not found at {self.config_path}, using defaults")
            return {
                "accept_threshold": 0.7,
                "investigate_threshold": 0.55,
                "decay_lambda": 0.015,  # per day
                "corroboration_gain": 0.15,
                "contradiction_penalty": 0.2,
                "max_gain_per_turn": 0.2,
                "source_weights": {"default": 1.0}
            }

        with open(self.config_path, "r") as f:
            return json.load(f)

    def resolve_proposals(
        self,
        user_id: str,
        proposals: List[Dict[str, Any]]
    ) -> List[RefinementOutcome]:
        """
        Resolve a batch of trait proposals for a user.

        Args:
            user_id: User identifier
            proposals: List of proposal dicts
                {
                    "trait": "SkillDNA.programming.python_fluency",
                    "value": "intermediate",
                    "confidence": 0.78,
                    "evidenceRefs": ["telemetry:...", "msg:..."],
                    "source": "career_coach",
                    "ts": "ISO-8601"
                }

        Returns:
            List of RefinementOutcome objects
        """
        # Group proposals by trait
        by_trait = defaultdict(list)
        for proposal in proposals:
            by_trait[proposal["trait"]].append(proposal)

        # Resolve each trait
        outcomes = []
        for trait, trait_proposals in by_trait.items():
            outcome = self._resolve_trait(user_id, trait, trait_proposals)
            outcomes.append(outcome)

            # Persist outcome
            self._persist_outcome(user_id, outcome)

            # Log telemetry
            self._log_refinement_telemetry(user_id, outcome)

        # Update resolved snapshot
        self._update_resolved_snapshot(user_id, outcomes)

        # Update conflicts
        self._update_conflicts(user_id, outcomes)

        return outcomes

    def _resolve_trait(
        self,
        user_id: str,
        trait: str,
        proposals: List[Dict[str, Any]]
    ) -> RefinementOutcome:
        """
        Resolve proposals for a single trait.

        Args:
            user_id: User identifier
            trait: Trait path
            proposals: Proposals for this trait

        Returns:
            RefinementOutcome
        """
        # Load prior state
        prior_state = self._load_prior_state(user_id, trait)

        # Apply recency decay to proposals
        weighted_proposals = self._apply_recency_decay(proposals)

        # Group by value
        by_value = defaultdict(list)
        for prop in weighted_proposals:
            by_value[prop["value"]].append(prop)

        # Find dominant value and conflicts
        dominant_value, dominant_weight, conflicts = self._analyze_proposals(by_value)

        # Compute effective confidence
        consistent_count = len(by_value.get(dominant_value, []))
        conflicting_count = sum(len(props) for val, props in by_value.items() if val != dominant_value)

        effective_conf = self._compute_effective_confidence(
            dominant_weight,
            consistent_count,
            conflicting_count
        )

        # Apply max gain cap
        max_gain = self.config["max_gain_per_turn"]
        prior_ucn = prior_state.get("ucn", 0.5)

        if effective_conf > prior_ucn + max_gain:
            effective_conf = prior_ucn + max_gain

        # Update UCN via Beta-like calibration
        new_ucn = self._calibrate_ucn(
            prior_ucn,
            consistent_count,
            conflicting_count,
            effective_conf
        )

        # Compute RR (Refinement Rating) as 1 - uncertainty
        new_rr = self._compute_rr(new_ucn, conflicting_count)

        # Determine action
        action = self._determine_action(new_ucn, conflicts)

        # Build outcome
        outcome = RefinementOutcome(
            trait=trait,
            prior={
                "value": prior_state.get("value"),
                "ucn": prior_ucn,
                "rr": prior_state.get("rr", 0.5)
            },
            proposal_summary={
                "consistent": consistent_count,
                "conflicting": conflicting_count,
                "effective_conf": round(effective_conf, 3)
            },
            action=action,
            resolved={
                "value": dominant_value,
                "ucn": round(new_ucn, 3),
                "rr": round(new_rr, 3)
            },
            conflicts=[
                {
                    "value": val,
                    "weight": round(sum(p["weighted_confidence"] for p in props), 3),
                    "sources": list(set(p["source"] for p in props))
                }
                for val, props in by_value.items()
                if val != dominant_value
            ],
            provenance={
                "events": [
                    {
                        "value": p["value"],
                        "confidence": p["confidence"],
                        "source": p["source"],
                        "ts": p["ts"],
                        "evidenceRefs": p.get("evidenceRefs", [])
                    }
                    for p in proposals
                ]
            },
            ts=datetime.now(timezone.utc).isoformat()
        )

        return outcome

    def _load_prior_state(self, user_id: str, trait: str) -> Dict[str, Any]:
        """Load prior state for trait from resolved.json."""
        user_dir = self.data_root / "users" / user_id
        resolved_path = user_dir / "resolved.json"

        if not resolved_path.exists():
            return {"value": None, "ucn": 0.5, "rr": 0.5}

        try:
            with open(resolved_path, "r") as f:
                resolved = json.load(f)

            return resolved.get(trait, {"value": None, "ucn": 0.5, "rr": 0.5})
        except Exception as e:
            logger.error(f"Failed to load prior state: {e}")
            return {"value": None, "ucn": 0.5, "rr": 0.5}

    def _apply_recency_decay(self, proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply exponential decay to older proposals."""
        decay_lambda = self.config["decay_lambda"]
        now = datetime.now(timezone.utc)

        weighted = []
        for prop in proposals:
            try:
                ts = datetime.fromisoformat(prop["ts"].replace("Z", "+00:00"))
                age_days = (now - ts).total_seconds() / 86400
                decay_factor = math.exp(-decay_lambda * age_days)
            except:
                decay_factor = 1.0  # No decay if timestamp invalid

            weighted_prop = dict(prop)
            weighted_prop["weighted_confidence"] = prop["confidence"] * decay_factor
            weighted.append(weighted_prop)

        return weighted

    def _analyze_proposals(
        self,
        by_value: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Analyze proposals grouped by value.

        Returns:
            (dominant_value, dominant_weight, conflicts)
        """
        # Compute total weight per value
        value_weights = {
            val: sum(p["weighted_confidence"] for p in props)
            for val, props in by_value.items()
        }

        # Find dominant
        dominant_value = max(value_weights, key=value_weights.get)
        dominant_weight = value_weights[dominant_value]

        # Identify conflicts (values with significant weight)
        conflict_threshold = dominant_weight * 0.3  # 30% of dominant
        conflicts = [
            {"value": val, "weight": weight}
            for val, weight in value_weights.items()
            if val != dominant_value and weight >= conflict_threshold
        ]

        return dominant_value, dominant_weight, conflicts

    def _compute_effective_confidence(
        self,
        dominant_weight: float,
        consistent_count: int,
        conflicting_count: int
    ) -> float:
        """
        Compute effective confidence with corroboration gain and contradiction penalty.

        Args:
            dominant_weight: Sum of weighted confidences for dominant value
            consistent_count: Number of consistent proposals
            conflicting_count: Number of conflicting proposals

        Returns:
            Effective confidence (0..1)
        """
        corroboration_gain = self.config["corroboration_gain"]
        contradiction_penalty = self.config["contradiction_penalty"]

        # Base confidence is dominant weight
        eff_conf = dominant_weight

        # Apply corroboration gain (diminishing returns)
        if consistent_count > 1:
            # Gain = base_gain * (1 - 1/count)
            # E.g., 2 proposals: gain * 0.5, 3 proposals: gain * 0.67
            corr_factor = (1 - 1/consistent_count) * corroboration_gain
            eff_conf += corr_factor

        # Apply contradiction penalty
        if conflicting_count > 0:
            # Penalty scales with conflict count
            contr_factor = min(conflicting_count * contradiction_penalty, 0.3)
            eff_conf -= contr_factor

        # Clamp to [0, 1]
        return max(0.0, min(1.0, eff_conf))

    def _calibrate_ucn(
        self,
        prior_ucn: float,
        consistent_count: int,
        conflicting_count: int,
        effective_conf: float
    ) -> float:
        """
        Calibrate UCN using Beta-like update.

        Conceptually: posterior = (α + corroboration, β + contradiction)
        UCN = α / (α + β)

        Args:
            prior_ucn: Prior uncertainty (0..1, higher = more certain)
            consistent_count: Evidence supporting dominant value
            conflicting_count: Evidence contradicting dominant value
            effective_conf: Effective confidence after gains/penalties

        Returns:
            Updated UCN
        """
        # Convert prior UCN to pseudo-counts
        # Higher UCN → higher alpha (more certain)
        prior_alpha = prior_ucn * 10
        prior_beta = (1 - prior_ucn) * 10

        # Add evidence
        posterior_alpha = prior_alpha + consistent_count * effective_conf
        posterior_beta = prior_beta + conflicting_count * 0.5  # Conflicts add to beta

        # Compute posterior UCN
        new_ucn = posterior_alpha / (posterior_alpha + posterior_beta)

        return new_ucn

    def _compute_rr(self, ucn: float, conflicting_count: int) -> float:
        """
        Compute RR (Refinement Rating) as 1 - uncertainty.

        RR represents overall refinement quality, accounting for:
        - UCN (confidence in value)
        - Presence of conflicts (reduces RR)

        Args:
            ucn: Uncertainty/confidence score
            conflicting_count: Number of conflicting proposals

        Returns:
            RR score (0..1) - Phase 9: This is legacy code, should use rr_to_percentile()
        """
        # LEGACY: Direct UCN→RR assignment (Phase 9 TODO: Use rr_to_percentile adapter)
        # For now, keep as-is since this returns 0-1 normalized score for internal use
        rr = ucn

        # Reduce for conflicts
        if conflicting_count > 0:
            conflict_penalty = min(conflicting_count * 0.1, 0.3)
            rr -= conflict_penalty

        return max(0.0, min(1.0, rr))

    def _determine_action(self, ucn: float, conflicts: List[Dict[str, Any]]) -> str:
        """
        Determine action based on UCN and conflicts.

        Returns:
            "accept" | "hold" | "conflict"
        """
        accept_threshold = self.config["accept_threshold"]
        investigate_threshold = self.config["investigate_threshold"]

        # Hard conflict if significant contradictions
        if len(conflicts) > 0 and any(c["weight"] >= 0.4 for c in conflicts):
            return "conflict"

        # Accept if UCN above threshold
        if ucn >= accept_threshold:
            return "accept"

        # Hold/investigate if between thresholds
        if ucn >= investigate_threshold:
            return "hold"

        # Otherwise, need more investigation
        return "hold"

    def _persist_outcome(self, user_id: str, outcome: RefinementOutcome):
        """Persist outcome to trait-specific refinement log."""
        user_dir = self.data_root / "users" / user_id
        refinement_dir = user_dir / "refinement"
        refinement_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize trait for filename
        trait_file = outcome.trait.replace(".", "_").replace("/", "_") + ".jsonl"
        log_path = refinement_dir / trait_file

        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(outcome.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist outcome: {e}")

    def _update_resolved_snapshot(self, user_id: str, outcomes: List[RefinementOutcome]):
        """Update resolved.json with new values/UCN/RR atomically."""
        user_dir = self.data_root / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = user_dir / "resolved.json"

        # Load existing
        if resolved_path.exists():
            try:
                with open(resolved_path, "r") as f:
                    resolved = json.load(f)
            except:
                resolved = {}
        else:
            resolved = {}

        # Update with outcomes
        for outcome in outcomes:
            resolved[outcome.trait] = outcome.resolved

        # Atomic write
        temp_path = resolved_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(resolved, f, indent=2)
            temp_path.replace(resolved_path)
        except Exception as e:
            logger.error(f"Failed to update resolved snapshot: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def _update_conflicts(self, user_id: str, outcomes: List[RefinementOutcome]):
        """Update conflicts.json with open conflicts."""
        user_dir = self.data_root / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        conflicts_path = user_dir / "conflicts.json"

        # Load existing
        if conflicts_path.exists():
            try:
                with open(conflicts_path, "r") as f:
                    conflicts_db = json.load(f)
            except:
                conflicts_db = {}
        else:
            conflicts_db = {}

        # Update conflicts
        for outcome in outcomes:
            if outcome.action == "conflict" or outcome.conflicts:
                conflicts_db[outcome.trait] = {
                    "conflicts": outcome.conflicts,
                    "last_seen": outcome.ts,
                    "count": len(outcome.conflicts),
                    "resolved_value": outcome.resolved["value"]
                }
            else:
                # Remove if resolved
                conflicts_db.pop(outcome.trait, None)

        # Write
        try:
            with open(conflicts_path, "w") as f:
                json.dump(conflicts_db, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update conflicts: {e}")

    def get_conflicts(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get open conflicts for user."""
        user_dir = self.data_root / "users" / user_id
        conflicts_path = user_dir / "conflicts.json"

        if not conflicts_path.exists():
            return []

        try:
            with open(conflicts_path, "r") as f:
                conflicts_db = json.load(f)

            # Convert to list and limit
            conflicts_list = [
                {"trait": trait, **data}
                for trait, data in conflicts_db.items()
            ]

            # Sort by last_seen (most recent first)
            conflicts_list.sort(key=lambda x: x["last_seen"], reverse=True)

            return conflicts_list[:limit]
        except Exception as e:
            logger.error(f"Failed to load conflicts: {e}")
            return []

    def get_trait_state(self, user_id: str, trait: str) -> Optional[Dict[str, Any]]:
        """Get current resolved state for a trait."""
        prior_state = self._load_prior_state(user_id, trait)

        # Load recent outcomes
        user_dir = self.data_root / "users" / user_id
        refinement_dir = user_dir / "refinement"

        trait_file = trait.replace(".", "_").replace("/", "_") + ".jsonl"
        log_path = refinement_dir / trait_file

        last_outcomes = []
        if log_path.exists():
            try:
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    # Get last 5 outcomes
                    for line in lines[-5:]:
                        last_outcomes.append(json.loads(line))
            except:
                pass

        return {
            "trait": trait,
            "current": prior_state,
            "recent_outcomes": last_outcomes
        }

    def _log_refinement_telemetry(self, user_id: str, outcome: RefinementOutcome):
        """
        Log refinement telemetry to insights directory.

        Creates three types of events:
        - refinement_outcome: For all resolutions
        - refinement_conflict_opened: When new conflict detected
        - refinement_investigate: When held for investigation
        """
        try:
            insights_dir = self.data_root.parent / "prompts" / "insights"
            insights_dir.mkdir(parents=True, exist_ok=True)

            telemetry_file = insights_dir / "refinement_events.jsonl"

            # Base event data
            base_event = {
                "ts": outcome.ts,
                "user_id": user_id,
                "trait": outcome.trait
            }

            events_to_log = []

            # Always log refinement_outcome
            outcome_event = {
                **base_event,
                "kind": "refinement_outcome",
                "action": outcome.action,
                "prior_ucn": outcome.prior.get("ucn"),
                "resolved_ucn": outcome.resolved.get("ucn"),
                "prior_rr": outcome.prior.get("rr"),
                "resolved_rr": outcome.resolved.get("rr"),
                "consistent_count": outcome.proposal_summary.get("consistent"),
                "conflicting_count": outcome.proposal_summary.get("conflicting"),
                "effective_conf": outcome.proposal_summary.get("effective_conf")
            }
            events_to_log.append(outcome_event)

            # Log conflict_opened if action == "conflict"
            if outcome.action == "conflict" and outcome.conflicts:
                conflict_event = {
                    **base_event,
                    "kind": "refinement_conflict_opened",
                    "conflict_count": len(outcome.conflicts),
                    "dominant_value": outcome.resolved.get("value"),
                    "conflicting_values": [c["value"] for c in outcome.conflicts]
                }
                events_to_log.append(conflict_event)

            # Log investigate if action == "hold"
            if outcome.action == "hold":
                investigate_event = {
                    **base_event,
                    "kind": "refinement_investigate",
                    "reason": "UCN below accept threshold, requires more evidence",
                    "current_ucn": outcome.resolved.get("ucn"),
                    "proposal_count": outcome.proposal_summary.get("consistent") + outcome.proposal_summary.get("conflicting")
                }
                events_to_log.append(investigate_event)

            # Write all events
            with open(telemetry_file, "a", encoding="utf-8") as f:
                for event in events_to_log:
                    f.write(json.dumps(event) + "\n")

        except Exception as e:
            logger.error(f"Failed to log refinement telemetry: {e}")


# Convenience functions
def create_resolver(
    config_path: Optional[Path] = None,
    data_root: Optional[Path] = None
) -> RefinementResolver:
    """Create refinement resolver instance."""
    return RefinementResolver(config_path=config_path, data_root=data_root)


def create_refinement_resolver(
    config_path: Optional[Path] = None,
    data_root: Optional[Path] = None
) -> RefinementResolver:
    """Alias for create_resolver() for consistency with other modules."""
    return create_resolver(config_path=config_path, data_root=data_root)
