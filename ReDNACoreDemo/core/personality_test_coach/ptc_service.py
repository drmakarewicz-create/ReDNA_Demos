"""
Personality Test Coach (PTC) Service
Adaptive personality assessment through contextual questions and behavioral observations.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..storage import read_user_state, write_user_state


class PersonalityTestCoach:
    """
    Adaptive personality assessment coach that refines PersonalityDNA, MotivationDNA,
    and BeliefValueDNA through micro-assessments and contextual observations.
    """

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.personality_items = self._load_personality_items()

    def _load_personality_items(self) -> List[Dict[str, Any]]:
        """Load personality assessment questions from data file."""
        items_path = self.data_dir / "personality_items.json"
        if not items_path.exists():
            return []

        with open(items_path, "r") as f:
            data = json.load(f)
            return data.get("items", [])

    def get_adaptive_questions(
        self,
        count: int = 5,
        min_curiosity: float = 70.0
    ) -> List[Dict[str, Any]]:
        """
        Get adaptive personality questions based on current RR/curiosity state.

        Args:
            count: Number of questions to return
            min_curiosity: Minimum curiosity threshold for prioritization

        Returns:
            List of question objects with metadata
        """
        resolved, _, _ = read_user_state(self.user_id)

        # Find traits with low RR (high curiosity) in PsyDNA namespaces
        target_namespaces = [
            "PsyDNA.PersonalityDNA",
            "PsyDNA.MotivationDNA",
            "PsyDNA.BeliefValueDNA"
        ]

        low_rr_traits = []
        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            # Check if trait is in target namespaces
            if not any(trait_path.startswith(ns) for ns in target_namespaces):
                continue

            curiosity = trait_data.get("curiosity", 0.0)
            rr = trait_data.get("rr", 100.0)

            if curiosity >= min_curiosity or rr < (100 - min_curiosity):
                low_rr_traits.append({
                    "path": trait_path,
                    "curiosity": curiosity,
                    "rr": rr
                })

        # Sort by curiosity (highest first)
        low_rr_traits.sort(key=lambda x: x["curiosity"], reverse=True)

        # Match questions to low-RR traits
        selected_questions = []
        for trait in low_rr_traits[:count]:
            matching_questions = [
                q for q in self.personality_items
                if trait["path"].startswith(q.get("trait_target", ""))
            ]

            if matching_questions:
                question = random.choice(matching_questions)
                selected_questions.append({
                    **question,
                    "target_trait": trait["path"],
                    "current_curiosity": trait["curiosity"],
                    "current_rr": trait["rr"]
                })

        # Fill remaining slots with general questions if needed
        while len(selected_questions) < count and len(self.personality_items) > 0:
            unused_questions = [
                q for q in self.personality_items
                if q not in selected_questions
            ]
            if not unused_questions:
                break
            selected_questions.append(random.choice(unused_questions))

        return selected_questions[:count]

    def process_answer(
        self,
        question_id: str,
        answer: Any,
        trait_target: str,
        evidence_weight: float = 0.7
    ) -> Dict[str, Any]:
        """
        Process a personality question answer and update trait UCN/RR.

        Args:
            question_id: ID of the question answered
            answer: User's response
            trait_target: Target trait path to update
            evidence_weight: Weight for this evidence (0-1)

        Returns:
            Update summary with old/new values
        """
        resolved, evidence, obs = read_user_state(self.user_id)

        # Get or create trait entry
        trait_entry = resolved.get(trait_target, {})
        if not isinstance(trait_entry, dict):
            trait_entry = {}

        old_ucn = trait_entry.get("ucn", 500.0)
        old_rr = trait_entry.get("rr", 50.0)

        # Update UCN based on answer confidence
        # For now, use simple evidence weight adjustment
        # In production, this would map answer → UCN based on item calibration
        new_ucn = old_ucn * (1 - evidence_weight) + (800.0 * evidence_weight)

        # Update trait
        trait_entry["ucn"] = new_ucn
        trait_entry["resolved_value"] = answer
        trait_entry.setdefault("reasons", []).append(
            f"PTC assessment: {question_id}"
        )
        trait_entry.setdefault("provenance", {})
        trait_entry["provenance"]["source"] = "personality_test_coach"
        trait_entry["provenance"]["step"] = "ptc-assessment"
        trait_entry["updated_ts"] = datetime.now(timezone.utc).isoformat()

        resolved[trait_target] = trait_entry

        # Save updated state
        write_user_state(self.user_id, resolved, evidence, obs)

        # Trigger RR recalculation via holistic review
        from ..holistic import run_holistic
        report, updated_resolved, _, _ = run_holistic(
            self.user_id,
            loader=lambda uid: read_user_state(uid),
            use_llm=False
        )

        # Get new RR value
        new_resolved, _, _ = read_user_state(self.user_id)
        new_trait = new_resolved.get(trait_target, {})
        new_rr = new_trait.get("rr", old_rr)

        return {
            "trait": trait_target,
            "question_id": question_id,
            "old_ucn": old_ucn,
            "new_ucn": new_ucn,
            "old_rr": old_rr,
            "new_rr": new_rr,
            "curiosity_delta": (100 - new_rr) - (100 - old_rr)
        }

    def get_personality_summary(self, top_n: int = 5) -> Dict[str, Any]:
        """
        Get summary of top personality facets and current state.

        Args:
            top_n: Number of top facets to return

        Returns:
            Summary with top traits, curiosity map, and recommendations
        """
        resolved, _, _ = read_user_state(self.user_id)

        psy_traits = []
        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if trait_path.startswith("PsyDNA.PersonalityDNA"):
                psy_traits.append({
                    "path": trait_path,
                    "value": trait_data.get("resolved_value") or trait_data.get("value"),
                    "rr": trait_data.get("rr", 50.0),
                    "curiosity": trait_data.get("curiosity", 50.0),
                    "ucn": trait_data.get("ucn", 500.0)
                })

        # Sort by RR (most resolved first) for "top facets"
        psy_traits.sort(key=lambda x: x["rr"], reverse=True)
        top_facets = psy_traits[:top_n]

        # Sort by curiosity (most curious first) for "needs attention"
        psy_traits.sort(key=lambda x: x["curiosity"], reverse=True)
        high_curiosity = [t for t in psy_traits if t["curiosity"] >= 60.0][:top_n]

        return {
            "top_facets": top_facets,
            "high_curiosity_facets": high_curiosity,
            "total_personality_traits": len(psy_traits),
            "avg_rr": sum(t["rr"] for t in psy_traits) / len(psy_traits) if psy_traits else 0.0,
            "avg_curiosity": sum(t["curiosity"] for t in psy_traits) / len(psy_traits) if psy_traits else 0.0
        }


__all__ = ["PersonalityTestCoach"]
