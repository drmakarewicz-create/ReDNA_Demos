"""
Coach Delegation System v1
==========================

Enables Head Coach to orchestrate specialized coaches to satisfy curiosity
through their natural domains.

TERMINOLOGY:
- **Coach Modes**: Functional specializations (Head Coach, Photo Coach, RC)
  - Same AI system operating in different modes for domain expertise
- **CReDNA** (Future): Per-user coach personality customization
  - Tone, playbooks, heuristics, knowledge shards, safety contracts
  - Example: "BSTest's Photo Coach" with distinct personality/voice/look
- **Personas** (Future): User-created ReDNA snapshots for marketplace
  - Static/dynamic profiles users can share/sell (requires 5%+ RR)

Features:
- Coach registry management
- Delegation decision logic
- Delegation tracking and status
- Return protocol handling

CReDNA COMPATIBILITY:
- Delegation records are user-scoped (supports per-user coach customization)
- DelegationResult can be extended with credna_profile field
- Coach registry already supports per-coach metadata (easy to add CReDNA keys)
- Future: Delegation can trigger CReDNA personality loading for specialized modes
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class DelegationResult:
    """Result of a delegation attempt."""
    success: bool
    coach: str
    delegation_id: str
    message: str  # Message to show user
    curiosity_targets: List[str]  # What coach should explore
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class DelegationStatus:
    """Status of an active or completed delegation."""
    delegation_id: str
    coach: str
    status: str  # pending, active, completed, failed
    traits_collected: List[str]
    curiosity_satisfied: float  # 0.0-1.0, how much curiosity was reduced
    timestamp: str
    notes: str = ""


class CoachRegistry:
    """Manages coach capabilities and delegation rules."""

    def __init__(self, registry_path: Optional[Path] = None):
        """
        Initialize coach registry.

        Args:
            registry_path: Path to coach_registry.yaml (default: core/coach_registry.yaml)
        """
        if registry_path is None:
            registry_path = Path(__file__).parent / "coach_registry.yaml"

        self.registry_path = registry_path
        self.config = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load coach registry from YAML file."""
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load coach registry: {e}")
            return self._get_default_registry()

    def _get_default_registry(self) -> Dict[str, Any]:
        """Return minimal default registry if file load fails."""
        return {
            "coaches": {
                "head_coach": {
                    "display_name": "Head Coach",
                    "id": "head_coach",
                    "description": "General conversation coach",
                    "primary_namespaces": ["CogDNA", "GenDNA"],
                    "capabilities": ["*"],
                    "delegation_context": "direct conversation",
                    "natural_domains": ["general conversation"],
                    "suitable_for_types": ["trait", "container", "missing"],
                    "is_default": True
                }
            },
            "delegation_rules": {
                "min_curiosity_for_delegation": 60.0,
                "min_tolerance_for_proactive_delegation": 0.5,
                "aggressive_delegation_tolerance": 0.8,
                "max_concurrent_delegations": 2,
                "min_items_per_delegation": 1
            },
            "availability": {
                "head_coach": True
            }
        }

    def get_coach_for_namespace(self, namespace: str) -> Optional[str]:
        """
        Get primary coach for a DNA namespace.

        Args:
            namespace: DNA namespace (e.g., "PaDNA", "ReDNA")

        Returns:
            Coach ID or None if no match
        """
        coaches = self.config.get("coaches", {})

        for coach_id, coach_data in coaches.items():
            primary_namespaces = coach_data.get("primary_namespaces", [])
            if namespace in primary_namespaces:
                return coach_id

        # Check for default coach
        for coach_id, coach_data in coaches.items():
            if coach_data.get("is_default", False):
                return coach_id

        return None

    def get_coach_for_path(self, path: str) -> Optional[str]:
        """
        Get best coach for a specific DNA path.

        Args:
            path: Full DNA path (e.g., "PaDNA.HairDNA.Color")

        Returns:
            Coach ID or None
        """
        # Try exact capability match first
        coaches = self.config.get("coaches", {})

        for coach_id, coach_data in coaches.items():
            capabilities = coach_data.get("capabilities", [])

            # Check for wildcard match (e.g., "ReDNA.*")
            for capability in capabilities:
                if capability == "*" or path.startswith(capability.replace(".*", "")):
                    return coach_id

            # Check for exact match
            if path in capabilities:
                return coach_id

        # Fallback to namespace-based match
        namespace = path.split(".")[0]
        return self.get_coach_for_namespace(namespace)

    def can_delegate_to(self, coach_id: str, user_id: str) -> bool:
        """
        Check if a coach is available for delegation.

        Args:
            coach_id: Coach identifier
            user_id: User identifier

        Returns:
            True if coach is available
        """
        # Check availability in config
        availability = self.config.get("availability", {})
        if not availability.get(coach_id, False):
            return False

        # TODO: Add user-specific checks:
        # - User has access to coach (RR thresholds, subscriptions)
        # - Coach is not currently busy with user
        # - Max concurrent delegations not exceeded

        return True

    def get_delegation_rules(self) -> Dict[str, Any]:
        """Get delegation rules from registry."""
        return self.config.get("delegation_rules", {})


class DelegationManager:
    """Manages delegation lifecycle and tracking."""

    def __init__(self, data_dir: Path):
        """
        Initialize delegation manager.

        Args:
            data_dir: Root data directory
        """
        self.data_dir = data_dir
        self.registry = CoachRegistry()

    def should_delegate(
        self,
        curiosity_items: List[Dict[str, Any]],
        user_tolerance: float,
        conversation_context: Optional[str] = None
    ) -> bool:
        """
        Decide if delegation is appropriate based on user tolerance.

        Args:
            curiosity_items: List of high-curiosity items
            user_tolerance: User's tolerance for nudging (0.0-1.0)
            conversation_context: Current conversation context (optional)

        Returns:
            True if delegation should proceed
        """
        rules = self.registry.get_delegation_rules()
        min_tolerance = rules.get("min_tolerance_for_proactive_delegation", 0.5)
        aggressive_tolerance = rules.get("aggressive_delegation_tolerance", 0.8)
        min_curiosity = rules.get("min_curiosity_for_delegation", 60.0)

        # Check if any items meet curiosity threshold
        high_curiosity_items = [
            item for item in curiosity_items
            if item.get("curiosity", 0) >= min_curiosity
        ]

        if not high_curiosity_items:
            return False

        # Tolerance-based decision
        if user_tolerance >= aggressive_tolerance:
            # User wants aggressive data collection
            return True

        if user_tolerance >= min_tolerance:
            # Check if delegation is contextually appropriate
            # TODO: Implement contextual appropriateness check
            # For now, allow if tolerance is balanced
            return True

        # Low tolerance - only delegate if user explicitly requests
        return False

    def delegate_to_coach(
        self,
        coach_id: str,
        user_id: str,
        curiosity_targets: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> DelegationResult:
        """
        Delegate curiosity exploration to specialized coach.

        Args:
            coach_id: Coach identifier
            user_id: User identifier
            curiosity_targets: List of high-curiosity paths to explore
            context: Additional context (delegation_reason, priority, etc.)

        Returns:
            DelegationResult with success status and details
        """
        context = context or {}

        # Check if coach is available
        if not self.registry.can_delegate_to(coach_id, user_id):
            return DelegationResult(
                success=False,
                coach=coach_id,
                delegation_id="",
                message=f"{coach_id} is not available right now",
                curiosity_targets=curiosity_targets,
                error="coach_unavailable"
            )

        # Create delegation record
        delegation_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        delegation_record = {
            "delegation_id": delegation_id,
            "coach": coach_id,
            "user_id": user_id,
            "curiosity_targets": curiosity_targets,
            "context": context,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp
        }

        # Save delegation record
        delegation_dir = self.data_dir / "users" / user_id / "delegations"
        delegation_dir.mkdir(parents=True, exist_ok=True)

        delegation_file = delegation_dir / f"{delegation_id}.json"
        with open(delegation_file, "w", encoding="utf-8") as f:
            json.dump(delegation_record, f, indent=2)

        # Get coach display name
        coaches = self.registry.config.get("coaches", {})
        coach_data = coaches.get(coach_id, {})
        coach_display_name = coach_data.get("display_name", coach_id)

        message = f"I think {coach_display_name} could help explore these areas. Want to chat with them?"

        return DelegationResult(
            success=True,
            coach=coach_id,
            delegation_id=delegation_id,
            message=message,
            curiosity_targets=curiosity_targets,
            context=context
        )

    def check_delegation_status(self, delegation_id: str, user_id: str) -> Optional[DelegationStatus]:
        """
        Check status of a delegation.

        Args:
            delegation_id: Delegation identifier
            user_id: User identifier

        Returns:
            DelegationStatus or None if not found
        """
        delegation_file = self.data_dir / "users" / user_id / "delegations" / f"{delegation_id}.json"

        if not delegation_file.exists():
            logger.warning(f"Delegation {delegation_id} not found for user {user_id}")
            return None

        try:
            with open(delegation_file, "r", encoding="utf-8") as f:
                record = json.load(f)

            return DelegationStatus(
                delegation_id=record["delegation_id"],
                coach=record["coach"],
                status=record["status"],
                traits_collected=record.get("traits_collected", []),
                curiosity_satisfied=record.get("curiosity_satisfied", 0.0),
                timestamp=record["updated_at"],
                notes=record.get("notes", "")
            )

        except Exception as e:
            logger.error(f"Error loading delegation status: {e}")
            return None

    def complete_delegation(
        self,
        delegation_id: str,
        user_id: str,
        traits_collected: List[str],
        curiosity_before: Dict[str, float],
        curiosity_after: Dict[str, float],
        notes: str = ""
    ) -> bool:
        """
        Mark delegation as completed and calculate curiosity satisfaction.

        Args:
            delegation_id: Delegation identifier
            user_id: User identifier
            traits_collected: List of trait paths collected
            curiosity_before: Curiosity scores before delegation
            curiosity_after: Curiosity scores after delegation
            notes: Optional notes about the delegation

        Returns:
            True if successful
        """
        delegation_file = self.data_dir / "users" / user_id / "delegations" / f"{delegation_id}.json"

        if not delegation_file.exists():
            logger.error(f"Delegation {delegation_id} not found")
            return False

        try:
            with open(delegation_file, "r", encoding="utf-8") as f:
                record = json.load(f)

            # Calculate curiosity satisfaction
            total_reduction = 0.0
            total_before = 0.0

            for path in traits_collected:
                before = curiosity_before.get(path, 0)
                after = curiosity_after.get(path, 0)
                total_before += before
                total_reduction += max(0, before - after)

            curiosity_satisfied = total_reduction / total_before if total_before > 0 else 0.0

            # Update record
            record["status"] = "completed"
            record["traits_collected"] = traits_collected
            record["curiosity_before"] = curiosity_before
            record["curiosity_after"] = curiosity_after
            record["curiosity_satisfied"] = curiosity_satisfied
            record["notes"] = notes
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
            record["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Save updated record
            with open(delegation_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)

            logger.info(
                f"Delegation {delegation_id} completed: "
                f"{len(traits_collected)} traits, "
                f"{curiosity_satisfied:.1%} curiosity satisfied"
            )

            return True

        except Exception as e:
            logger.error(f"Error completing delegation: {e}")
            return False

    def get_active_delegations(self, user_id: str) -> List[DelegationStatus]:
        """
        Get all active delegations for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active DelegationStatus objects
        """
        delegation_dir = self.data_dir / "users" / user_id / "delegations"

        if not delegation_dir.exists():
            return []

        active_delegations = []

        for delegation_file in delegation_dir.glob("*.json"):
            try:
                with open(delegation_file, "r", encoding="utf-8") as f:
                    record = json.load(f)

                if record["status"] in ["pending", "active"]:
                    active_delegations.append(
                        DelegationStatus(
                            delegation_id=record["delegation_id"],
                            coach=record["coach"],
                            status=record["status"],
                            traits_collected=record.get("traits_collected", []),
                            curiosity_satisfied=record.get("curiosity_satisfied", 0.0),
                            timestamp=record["updated_at"],
                            notes=record.get("notes", "")
                        )
                    )

            except Exception as e:
                logger.warning(f"Error reading delegation file {delegation_file}: {e}")
                continue

        return active_delegations

    def group_curiosity_by_coach(
        self,
        curiosity_items: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group curiosity items by responsible coach.

        Args:
            curiosity_items: List of curiosity items with paths

        Returns:
            Dict mapping coach_id to list of items
        """
        by_coach = {}

        for item in curiosity_items:
            path = item.get("path", item.get("trait", ""))
            coach_id = self.registry.get_coach_for_path(path)

            if coach_id:
                by_coach.setdefault(coach_id, []).append(item)

        return by_coach
