"""
BeliefDNA Coach Service
Philosophy & values simulator - generates belief-based reasoning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .storage import read_user_state


class BeliefDNACoach:
    """
    BeliefDNA coach that analyzes BeliefValueDNA, MotivationDNA, CogDNA,
    and PsyDNA to generate philosophical and moral reasoning.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_belief_snapshot(self) -> Dict[str, Any]:
        """
        Generate BeliefDNA snapshot for dashboard panel.

        Returns:
            Snapshot with RR metrics, top curiosity traits, and moral foundations
        """
        resolved, _, _ = read_user_state(self.user_id)

        # Calculate aggregate RRs
        belief_rrs = []
        cog_rrs = []
        motivation_rrs = []
        all_traits = []

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get("rr", 50.0)
            curiosity = trait_data.get("curiosity", 50.0)

            if trait_path.startswith("BeliefValueDNA"):
                belief_rrs.append(rr)
                all_traits.append({
                    "path": trait_path,
                    "name": trait_path.split(".")[-1],
                    "rr": rr,
                    "curiosity": curiosity
                })
            elif trait_path.startswith("CogDNA"):
                cog_rrs.append(rr)
                all_traits.append({
                    "path": trait_path,
                    "name": trait_path.split(".")[-1],
                    "rr": rr,
                    "curiosity": curiosity
                })
            elif trait_path.startswith("MotivationDNA"):
                motivation_rrs.append(rr)

        # Calculate averages
        belief_rr = int(sum(belief_rrs) / len(belief_rrs)) if belief_rrs else 50
        cog_rr = int(sum(cog_rrs) / len(cog_rrs)) if cog_rrs else 50
        motivation_rr = int(sum(motivation_rrs) / len(motivation_rrs)) if motivation_rrs else 50

        # Get top curiosity traits
        all_traits.sort(key=lambda x: x["curiosity"], reverse=True)
        top_curiosity = [t["path"] for t in all_traits[:3] if t["curiosity"] > 60]

        # Determine dominant moral foundations (stub - would analyze actual data)
        dominant_moral_foundations = ["Care/Fairness", "Liberty/Oppression"]

        return {
            "snapshot": {
                "belief_rr": belief_rr,
                "cog_rr": cog_rr,
                "motivation_rr": motivation_rr,
                "top_curiosity": top_curiosity,
                "dominant_moral_foundations": dominant_moral_foundations,
                "active_intent": "moral"
            }
        }

    def get_question_templates(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get predefined question templates for different categories.

        Returns:
            Dictionary with template cards
        """
        return {
            "templates": {
                "cards": [
                    {"id": "existential_1", "prompt": "Is there such a thing as fate?"},
                    {"id": "existential_2", "prompt": "Do humans have free will?"},
                    {"id": "moral_1", "prompt": "Is lying ever morally acceptable?"},
                    {"id": "moral_2", "prompt": "Should we prioritize individual rights or collective good?"},
                    {"id": "political_1", "prompt": "Should the government regulate speech?"},
                    {"id": "political_2", "prompt": "What is the ideal balance between freedom and security?"},
                    {"id": "social_1", "prompt": "Are humans inherently cooperative or competitive?"},
                    {"id": "social_2", "prompt": "Is inequality inevitable in society?"},
                    {"id": "psychological_1", "prompt": "What makes a person truly happy?"},
                    {"id": "psychological_2", "prompt": "Can people fundamentally change?"}
                ]
            }
        }

    def generate_belief_response(
        self,
        prompt: str,
        intent: str = "moral"
    ) -> Dict[str, Any]:
        """
        Generate a belief-based answer to a philosophical question.

        Args:
            prompt: The question to answer
            intent: Category (moral, social, existential, political, psychological)

        Returns:
            Response with output, reasoning map, similarity, and evidence
        """
        resolved, _, _ = read_user_state(self.user_id)

        # Collect relevant traits for reasoning
        belief_traits = []
        cog_traits = []
        personality_traits = []

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get("rr", 50.0)
            if trait_path.startswith("BeliefValueDNA"):
                belief_traits.append({"path": trait_path, "rr": rr})
            elif trait_path.startswith("CogDNA.CognitiveStyleDNA"):
                cog_traits.append({"path": trait_path, "rr": rr})
            elif trait_path.startswith("PsyDNA.PersonalityDNA"):
                personality_traits.append({"path": trait_path, "rr": rr})

        # Build reasoning map with actual trait data
        reason_map = []

        # Add top belief traits
        for trait in sorted(belief_traits, key=lambda x: x["rr"], reverse=True)[:2]:
            weight = min(trait["rr"] / 100.0, 1.0)
            reason_map.append({
                "trait": trait["path"],
                "rr": int(trait["rr"]),
                "weight": round(weight, 2),
                "influence": f"Strong influence from your belief system (RR: {int(trait['rr'])})"
            })

        # Add top cognitive traits
        for trait in sorted(cog_traits, key=lambda x: x["rr"], reverse=True)[:2]:
            weight = min(trait["rr"] / 100.0, 1.0)
            reason_map.append({
                "trait": trait["path"],
                "rr": int(trait["rr"]),
                "weight": round(weight, 2),
                "influence": f"Shaped by your cognitive style (RR: {int(trait['rr'])})"
            })

        # Add personality influence
        if personality_traits:
            trait = max(personality_traits, key=lambda x: x["rr"])
            weight = min(trait["rr"] / 100.0, 1.0)
            reason_map.append({
                "trait": trait["path"],
                "rr": int(trait["rr"]),
                "weight": round(weight, 2),
                "influence": f"Reflects your personality tendencies (RR: {int(trait['rr'])})"
            })

        # If no traits found, use demo data for UI demonstration
        if not reason_map:
            reason_map = [
                {
                    "trait": "BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA",
                    "rr": 65,
                    "weight": 0.65,
                    "influence": "Emphasizes compassion and fairness in moral reasoning"
                },
                {
                    "trait": "CogDNA.CognitiveStyleDNA.NeedForClosureDNA",
                    "rr": 55,
                    "weight": 0.55,
                    "influence": "Moderate preference for definitive answers vs. ambiguity"
                },
                {
                    "trait": "PsyDNA.PersonalityDNA.OpennessDNA",
                    "rr": 72,
                    "weight": 0.72,
                    "influence": "High openness leads to considering multiple perspectives"
                }
            ]

        # Generate stub response based on intent
        responses = {
            "moral": "You'd likely approach this from a care/fairness perspective, weighing individual harm against collective benefit.",
            "social": "You'd probably see humans as fundamentally cooperative but shaped by their environment and circumstances.",
            "existential": "You'd likely take a nuanced view, acknowledging both deterministic forces and human agency.",
            "political": "You'd tend to balance individual liberty with practical considerations for collective wellbeing.",
            "psychological": "You'd likely emphasize intrinsic fulfillment over external achievement, with empathy playing a key role."
        }

        output = responses.get(intent, "You'd likely approach this question thoughtfully, drawing on both logic and empathy.")

        # Calculate stub similarity scores
        similarity = {
            "conceptual": 0.77,
            "linguistic": 0.71,
            "overall": 0.74
        }

        # Identify relevant containers with full metadata
        all_relevant = sorted(
            belief_traits + cog_traits + personality_traits,
            key=lambda x: x["rr"],
            reverse=True
        )[:5]

        relevant_containers = [
            {
                "path": t["path"],
                "similarity": min(t["rr"] / 100.0, 0.95),  # Convert RR to similarity score
                "rr": int(t["rr"])
            }
            for t in all_relevant
        ]

        # If no containers found, use demo data
        if not relevant_containers:
            relevant_containers = [
                {
                    "path": "BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA",
                    "similarity": 0.85,
                    "rr": 65
                },
                {
                    "path": "CogDNA.CognitiveStyleDNA.NeedForClosureDNA",
                    "similarity": 0.72,
                    "rr": 55
                },
                {
                    "path": "PsyDNA.PersonalityDNA.OpennessDNA",
                    "similarity": 0.88,
                    "rr": 72
                },
                {
                    "path": "EmDNA.EmpathyCompassionDNA",
                    "similarity": 0.68,
                    "rr": 58
                }
            ]

        # Calculate RR summary
        belief_rrs = [t["rr"] for t in belief_traits]
        cog_rrs = [t["rr"] for t in cog_traits]
        motivation_rrs = []  # Would collect from MotivationDNA

        rr_summary = {
            "BeliefValueDNA": int(sum(belief_rrs) / len(belief_rrs)) if belief_rrs else 50,
            "CogDNA": int(sum(cog_rrs) / len(cog_rrs)) if cog_rrs else 50,
            "MotivationDNA": int(sum(motivation_rrs) / len(motivation_rrs)) if motivation_rrs else 50
        }

        return {
            "output": output,
            "reason_map": reason_map,
            "similarity": similarity,
            "relevant_containers": relevant_containers,
            "rr_summary": rr_summary
        }

    def record_feedback(
        self,
        prompt: str,
        output: str,
        user_rating: int,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Record user feedback and calculate RR adjustments.

        Args:
            prompt: The original question
            output: The generated response
            user_rating: Rating from 1-5
            notes: Optional user notes

        Returns:
            Feedback result with RR deltas
        """
        # Map ratings to deltas: 1→-8, 2→-4, 3→0, 4→+4, 5→+8
        delta_map = {1: -8, 2: -4, 3: 0, 4: 4, 5: 8}
        rr_delta = delta_map.get(user_rating, 0)

        # Stub - would identify affected containers from reasoning
        affected_containers = [
            "BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA",
            "CogDNA.CognitiveStyleDNA.NeedForClosureDNA"
        ]

        return {
            "success": True,
            "rr_delta": rr_delta,
            "affected_containers": affected_containers,
            "message": f"Feedback recorded. RR adjustments: {rr_delta:+d}"
        }

    def get_panel_data(self) -> Dict[str, Any]:
        """
        Get complete panel data for BeliefDNA Coach UI.

        Returns:
            Unified panel payload with all widget data
        """
        snapshot_data = self.get_belief_snapshot()
        templates_data = self.get_question_templates()

        # Build complete panel response
        panel_data = {
            **snapshot_data,
            **templates_data,
            "console_state": {
                "last_prompt": "",
                "last_output": ""
            },
            "reason_map": {
                "rows": []
            },
            "contradictions": {
                "cards": []
            },
            "evidence_links": {
                "items": []
            }
        }

        return panel_data
