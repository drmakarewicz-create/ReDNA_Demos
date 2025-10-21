"""
Head Coach Service v1
=====================

The Head Coach (HC) is the orchestrator: butler/assistant/friend/problem-solver.

Core responsibilities:
- Ingest observations from any coach → normalize → route to Core → trigger UCNRR
- Plan next actions based on Core state + curiosity
- Explain decisions in plain language
- Maintain relationship ledger and journal

Design principles:
- Coach-agnostic: works with any coach
- Layered: HC orchestrates, Core validates/stores, UCNRR provides stats
- Curiosity-driven: curiosity = 100 - RR (RR is 0-100 percentile)
- Provenance everywhere
- User trust: loyal, transparent, helpful, boundaries-aware
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .storage import read_user_state, write_user_state, ensure_dirs_for_user
from .redna_core import build_observations, resolve_traits
from .events import publish_event

# Optional: Import UCNRR if available
try:
    from .ucn_rr_service import rescore_user
    UCNRR_AVAILABLE = True
except ImportError:
    UCNRR_AVAILABLE = False
    rescore_user = None


class HeadCoachService:
    """
    Head Coach orchestration service.

    Acts as the primary interface between coaches, Core, and the user.
    """

    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)

    def _get_hc_dir(self, user_id: str) -> Path:
        """Get HC directory for user, create if needed."""
        hc_dir = self.data_root / "users" / user_id / "hc"
        hc_dir.mkdir(parents=True, exist_ok=True)
        return hc_dir

    def _get_relationship_path(self, user_id: str) -> Path:
        """Get relationship.json path."""
        return self._get_hc_dir(user_id) / "relationship.json"

    def _get_journal_dir(self, user_id: str) -> Path:
        """Get journal directory."""
        journal_dir = self._get_hc_dir(user_id) / "journal"
        journal_dir.mkdir(exist_ok=True)
        return journal_dir

    def _get_plans_dir(self, user_id: str) -> Path:
        """Get plans directory."""
        plans_dir = self._get_hc_dir(user_id) / "plans"
        plans_dir.mkdir(exist_ok=True)
        return plans_dir

    def _get_checkpoints_dir(self, user_id: str) -> Path:
        """Get checkpoints directory."""
        checkpoints_dir = self._get_hc_dir(user_id) / "checkpoints"
        checkpoints_dir.mkdir(exist_ok=True)
        return checkpoints_dir

    def _load_relationship(self, user_id: str) -> Dict[str, Any]:
        """Load relationship ledger for user."""
        path = self._get_relationship_path(user_id)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Default relationship
        return {
            "hc_name": "Alex",
            "user_preferred_name": None,
            "tone_preference": "warm",  # warm, professional, casual
            "notification_style": "balanced",  # minimal, balanced, detailed
            "goals": [],
            "boundaries": {
                "topics_to_avoid": [],
                "preferred_coaches": []
            },
            "preferences": {
                "explain_suggestions": True,
                "proactive_nudges": True,
                "micro_rituals": True
            },
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

    def _save_relationship(self, user_id: str, relationship: Dict[str, Any]) -> None:
        """Save relationship ledger."""
        relationship["updated_at"] = datetime.utcnow().isoformat()
        path = self._get_relationship_path(user_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(relationship, f, indent=2, ensure_ascii=False)

    def _append_journal(self, user_id: str, entry: str) -> None:
        """Append entry to today's journal."""
        journal_dir = self._get_journal_dir(user_id)
        today = datetime.utcnow().strftime("%Y%m%d")
        journal_file = journal_dir / f"{today}.md"

        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        with open(journal_file, 'a', encoding='utf-8') as f:
            f.write(f"\n**{timestamp}** {entry}\n")

    def _write_checkpoint(self, user_id: str, checkpoint: Dict[str, Any]) -> None:
        """Write HC checkpoint."""
        checkpoints_dir = self._get_checkpoints_dir(user_id)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = checkpoints_dir / f"{timestamp}.json"

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    def _write_decision(self, user_id: str, decision: Dict[str, Any]) -> None:
        """Write HC decision to plans directory."""
        plans_dir = self._get_plans_dir(user_id)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        decision_file = plans_dir / f"decision_{timestamp}.json"

        with open(decision_file, 'w', encoding='utf-8') as f:
            json.dump(decision, f, indent=2, ensure_ascii=False)

    def _compute_curiosity(self, rr: float) -> float:
        """Compute curiosity score from RR (0-100 percentile)."""
        return 100.0 - rr

    def _get_curiosity_hotspots(self, user_id: str, threshold: float = 800.0) -> List[Dict[str, Any]]:
        """
        Find traits with high curiosity (low RR).

        Returns list of {trait, curiosity, ucn, rr, reason}
        """
        # Read user state from storage
        try:
            obs_dict, resolved_dict, evidence_dict = read_user_state(user_id)
        except Exception:
            return []

        hotspots = []

        for trait_path, trait_data in resolved_dict.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get('rr', 50.0)  # Default to median RR (0-100 scale)
            ucn = trait_data.get('ucn', 0.0)
            curiosity = self._compute_curiosity(rr)

            if curiosity >= threshold:
                # Determine reason
                reason = "newly observed" if ucn < 200 else "low confidence"
                if ucn > 800 and curiosity > 90:
                    reason = "high uncertainty despite high confidence"

                hotspots.append({
                    "trait": trait_path,
                    "curiosity": round(curiosity, 1),
                    "ucn": round(ucn, 1),
                    "rr": round(rr, 1),
                    "reason": reason,
                    "resolved_value": trait_data.get('resolved_value')
                })

        # Sort by curiosity descending
        hotspots.sort(key=lambda x: x['curiosity'], reverse=True)
        return hotspots

    def ingest_observations(
        self,
        user_id: str,
        observations: Dict[str, Any],
        source_coach: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Ingest observations from any coach.

        Flow:
        1. Normalize observations
        2. Submit to Core (observe_trait)
        3. Trigger UCNRR rescore
        4. Compute HC decision
        5. Emit events
        6. Return decision plan

        Args:
            user_id: User identifier
            observations: Trait observations (nested dict)
            source_coach: Name of originating coach

        Returns:
            HC decision dict with recommendations and next steps
        """
        self._append_journal(user_id, f"Ingesting observations from {source_coach}")

        # Build observations using Core's build_observations
        try:
            obs_dict, resolved_dict, evidence_dict = read_user_state(user_id)
        except Exception:
            # User might not exist yet, initialize empty
            ensure_dirs_for_user(user_id)
            obs_dict, resolved_dict, evidence_dict = {}, {}, {}

        # Flatten and add new observations
        trait_count = 0
        changed_traits = []

        def flatten_observations(container_path: str, obs_data: Dict[str, Any], target: Dict[str, Any]) -> None:
            """Recursively flatten nested observations into target dict."""
            nonlocal trait_count
            for key, value in obs_data.items():
                full_path = f"{container_path}.{key}" if container_path else key

                if isinstance(value, dict) and 'resolved_value' in value:
                    # This is a trait observation
                    target[full_path] = value
                    trait_count += 1
                    changed_traits.append(full_path)

                elif isinstance(value, dict):
                    # Recurse into nested container
                    flatten_observations(full_path, value, target)

        # Add new observations to existing
        flatten_observations("", observations, obs_dict)

        # Resolve traits using Core
        try:
            resolved_dict = resolve_traits(obs_dict, user_id)
            write_user_state(user_id, resolved_dict, evidence_dict, obs_dict)
        except Exception as e:
            self._append_journal(user_id, f"Error resolving traits: {e}")

        # Trigger UCNRR rescore if available
        if UCNRR_AVAILABLE and rescore_user:
            self._append_journal(user_id, f"Rescoring UCNRR for {trait_count} traits")
            try:
                rescore_user(user_id)
            except Exception as e:
                self._append_journal(user_id, f"UCNRR rescore error: {e}")

        # Compute curiosity hotspots
        hotspots = self._get_curiosity_hotspots(user_id)

        # Build HC decision
        decision = {
            "ts": datetime.utcnow().isoformat(),
            "source_coach": source_coach,
            "trait_count": trait_count,
            "whatChanged": changed_traits[:10],  # Top 10
            "uncertaintyDeltas": [
                {"trait": h["trait"], "delta": h["curiosity"]}
                for h in hotspots[:5]
            ],
            "recommendations": self._build_recommendations(user_id, hotspots, changed_traits),
            "curiosityTargets": [
                {"trait": h["trait"], "curiosity": h["curiosity"]}
                for h in hotspots[:5]
            ],
            "nextSteps": self._build_next_steps(user_id, hotspots, changed_traits, source_coach)
        }

        # Write decision and emit events
        self._write_decision(user_id, decision)
        publish_event("OBS_INGESTED", {
            "user_id": user_id,
            "source_coach": source_coach,
            "trait_count": trait_count
        })
        publish_event("HC_PLAN_UPDATED", {
            "user_id": user_id,
            "decision_ts": decision["ts"]
        })

        self._append_journal(user_id, f"Decision created: {len(decision['nextSteps'])} next steps")

        return decision

    def _build_recommendations(
        self,
        user_id: str,
        hotspots: List[Dict[str, Any]],
        changed_traits: List[str]
    ) -> List[str]:
        """Build human-readable recommendations."""
        recommendations = []

        if len(changed_traits) > 0:
            recommendations.append(f"Updated {len(changed_traits)} traits successfully")

        if len(hotspots) > 0:
            top_hotspot = hotspots[0]
            recommendations.append(
                f"Highest curiosity: {top_hotspot['trait']} "
                f"(curiosity {top_hotspot['curiosity']:.0f}) — {top_hotspot['reason']}"
            )

        if len(hotspots) >= 5:
            recommendations.append(
                f"{len(hotspots)} traits need attention — focus on top 3 for quickest wins"
            )

        return recommendations

    def _build_next_steps(
        self,
        user_id: str,
        hotspots: List[Dict[str, Any]],
        changed_traits: List[str],
        source_coach: str
    ) -> List[Dict[str, Any]]:
        """Build actionable next steps."""
        steps = []

        # If hotspots exist, suggest reducing uncertainty
        if len(hotspots) > 0:
            top_hotspot = hotspots[0]
            steps.append({
                "title": f"Reduce uncertainty for {top_hotspot['trait'].split('.')[-1]}",
                "action": "provide_more_evidence",
                "trait": top_hotspot['trait'],
                "etaMins": 2,
                "link": f"/coach/{source_coach}"
            })

        # Suggest reviewing top 3 hotspots
        if len(hotspots) >= 3:
            steps.append({
                "title": "Review top 3 curiosity hotspots",
                "action": "review_hotspots",
                "etaMins": 5,
                "link": "/hc/hotspots"
            })

        # If PaDNA traits changed, suggest portrait re-render
        if any('PaDNA' in t for t in changed_traits[:20]):
            steps.append({
                "title": "Re-render portrait with updated traits",
                "action": "render_portrait",
                "etaMins": 1,
                "link": "/coach/padna"
            })

        return steps

    def plan_next_actions(self, user_id: str) -> Dict[str, Any]:
        """
        Plan next actions based on current state + curiosity.

        Returns:
            {
                goals: user goals,
                prioritized_tasks: list of tasks sorted by impact,
                focus_area: recommended focus,
                quick_wins: 2-3 minute tasks
            }
        """
        relationship = self._load_relationship(user_id)
        hotspots = self._get_curiosity_hotspots(user_id)

        plan = {
            "ts": datetime.utcnow().isoformat(),
            "goals": relationship.get("goals", []),
            "prioritized_tasks": [],
            "focus_area": None,
            "quick_wins": []
        }

        # Determine focus area
        if len(hotspots) > 0:
            top = hotspots[0]
            plan["focus_area"] = {
                "trait": top["trait"],
                "curiosity": top["curiosity"],
                "reason": top["reason"],
                "suggestion": f"Reduce uncertainty for {top['trait'].split('.')[-1]}"
            }

        # Build quick wins (2-minute tasks)
        for hotspot in hotspots[:3]:
            plan["quick_wins"].append({
                "title": f"Add evidence for {hotspot['trait'].split('.')[-1]}",
                "etaMins": 2,
                "impact": "reduces curiosity",
                "trait": hotspot["trait"]
            })

        # Build prioritized tasks
        if len(hotspots) >= 5:
            plan["prioritized_tasks"].append({
                "title": "Curiosity campaign: top 5 traits",
                "etaMins": 15,
                "impact": "high",
                "playbook": "curiosity_campaign"
            })

        self._append_journal(user_id, f"Plan generated: {len(plan['quick_wins'])} quick wins")

        return plan

    def explain(self, user_id: str, topic: str) -> str:
        """
        Explain a decision or suggestion in plain language.

        Args:
            user_id: User identifier
            topic: Topic to explain (trait path, decision, etc.)

        Returns:
            Plain language explanation with provenance
        """
        # Read user state from storage
        try:
            obs_dict, resolved_dict, evidence_dict = read_user_state(user_id)
        except Exception:
            return (
                f"I don't have data for user '{user_id}' yet. "
                f"Try providing some observations first."
            )

        # If topic is a trait path, explain UCN/RR/curiosity
        if topic in resolved_dict:
            trait_data = resolved_dict[topic]
            ucn = trait_data.get('ucn', 0.0)
            rr = trait_data.get('rr', 50.0)  # Default to median RR (0-100 scale)
            curiosity = self._compute_curiosity(rr)
            value = trait_data.get('resolved_value')
            evidence_count = trait_data.get('evidence_count', 0)

            explanation = (
                f"**{topic}**\n\n"
                f"Current value: {value}\n"
                f"Confidence (UCN): {ucn:.1f}/1000\n"
                f"Refinement Rating (RR): {rr:.1f}/100\n"
                f"Curiosity: {curiosity:.1f}/100\n\n"
                f"**Why I'm suggesting this:**\n"
            )

            if curiosity > 90:
                explanation += (
                    f"This trait has very high curiosity ({curiosity:.0f}), meaning it's rare "
                    f"or uncertain. "
                )
            elif curiosity > 80:
                explanation += f"This trait has high curiosity ({curiosity:.0f}). "

            if ucn < 200:
                explanation += (
                    f"Confidence is low ({ucn:.0f}) with only {evidence_count} "
                    f"piece(s) of evidence. "
                )

            if curiosity > 800:
                explanation += (
                    "\n\n**Your quickest win:** Add one more piece of evidence to reduce uncertainty."
                )

            explanation += (
                f"\n\n*Source: ReDNA Core (UCN/RR scoring system), "
                f"{evidence_count} evidence items*"
            )

            return explanation

        # Generic explanation
        return (
            f"I don't have specific data about '{topic}' yet. "
            f"If this is a trait path, try providing more observations first."
        )

    def get_state(self, user_id: str) -> Dict[str, Any]:
        """
        Get HC state for UI rendering.

        Returns:
            {
                userId, goals, openTasks, curiosityHotspots,
                recentDecisions, checkpoints
            }
        """
        relationship = self._load_relationship(user_id)
        hotspots = self._get_curiosity_hotspots(user_id, threshold=700.0)

        # Load recent decisions
        plans_dir = self._get_plans_dir(user_id)
        decision_files = sorted(plans_dir.glob("decision_*.json"), reverse=True)[:5]
        recent_decisions = []

        for dec_file in decision_files:
            with open(dec_file, 'r', encoding='utf-8') as f:
                dec = json.load(f)
                recent_decisions.append({
                    "ts": dec.get("ts"),
                    "summary": f"Processed {dec.get('trait_count', 0)} traits from {dec.get('source_coach', 'unknown')}",
                    "why": dec.get("recommendations", [])[0] if dec.get("recommendations") else "",
                    "provenance": [dec.get("source_coach", "unknown")]
                })

        # Load checkpoints
        checkpoints_dir = self._get_checkpoints_dir(user_id)
        checkpoint_files = sorted(checkpoints_dir.glob("*.json"), reverse=True)[:10]
        checkpoints = [cp.stem for cp in checkpoint_files]

        # Build open tasks from recent decision
        open_tasks = []
        if len(decision_files) > 0:
            with open(decision_files[0], 'r', encoding='utf-8') as f:
                latest_dec = json.load(f)
                open_tasks = latest_dec.get("nextSteps", [])

        return {
            "userId": user_id,
            "hcName": relationship.get("hc_name", "Alex"),
            "goals": relationship.get("goals", []),
            "openTasks": open_tasks,
            "curiosityHotspots": hotspots[:10],
            "recentDecisions": recent_decisions,
            "checkpoints": checkpoints,
            "relationship": {
                "tone": relationship.get("tone_preference", "warm"),
                "notifications": relationship.get("notification_style", "balanced")
            }
        }


# Singleton instance
_hc_service = None

def get_hc_service(data_root: str = "data") -> HeadCoachService:
    """Get singleton HC service instance."""
    global _hc_service
    if _hc_service is None:
        _hc_service = HeadCoachService(data_root)
    return _hc_service
