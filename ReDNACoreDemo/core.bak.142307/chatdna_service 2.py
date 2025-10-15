"""
ChatDNA Coach Service
Conversational style analysis and language pattern simulation.
"""

from __future__ import annotations

from typing import Any, Dict, List
from .storage import read_user_state


class ChatDNACoach:
    """
    ChatDNA coach that analyzes LanguageStyleDNA, InteractionStyleDNA,
    and provides conversational style insights.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_language_traits(
        self,
        min_curiosity: float = 50.0
    ) -> Dict[str, Any]:
        """
        Get language and interaction style traits with curiosity/RR data.

        Args:
            min_curiosity: Minimum curiosity threshold for filtering

        Returns:
            Language traits with metadata
        """
        resolved, _, _ = read_user_state(self.user_id)

        language_traits = []
        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            # Collect LanguageStyleDNA and InteractionStyleDNA traits
            if (trait_path.startswith("LanguageStyleDNA") or
                trait_path.startswith("SocDNA.InteractionStyleDNA")):

                curiosity = trait_data.get("curiosity", 50.0)
                if curiosity >= min_curiosity:
                    language_traits.append({
                        "trait_name": trait_path.split(".")[-1],
                        "rr": trait_data.get("rr", 50.0),
                        "curiosity": curiosity,
                        "sample_count": trait_data.get("sample_count", 0)
                    })

        # Sort by curiosity (descending)
        language_traits.sort(key=lambda x: x["curiosity"], reverse=True)

        return {
            "traits": language_traits,
            "total_count": len(language_traits)
        }

    def get_chatdna_snapshot(self) -> Dict[str, Any]:
        """
        Generate ChatDNA snapshot for dashboard panel.

        Returns:
            Snapshot data with RR metrics and top traits
        """
        resolved, _, _ = read_user_state(self.user_id)

        # Calculate aggregate RRs
        language_rrs = []
        interaction_rrs = []
        all_traits = []

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get("rr", 50.0)
            curiosity = trait_data.get("curiosity", 50.0)

            if trait_path.startswith("LanguageStyleDNA"):
                language_rrs.append(rr)
                all_traits.append({
                    "name": trait_path.split(".")[-1],
                    "rr": rr,
                    "curiosity": curiosity
                })
            elif trait_path.startswith("SocDNA.InteractionStyleDNA"):
                interaction_rrs.append(rr)
                all_traits.append({
                    "name": trait_path.split(".")[-1],
                    "rr": rr,
                    "curiosity": curiosity
                })

        # Calculate averages
        languagestyle_rr = (
            int(sum(language_rrs) / len(language_rrs))
            if language_rrs else 50
        )
        interaction_rr = (
            int(sum(interaction_rrs) / len(interaction_rrs))
            if interaction_rrs else 50
        )

        # Get top traits by RR
        all_traits.sort(key=lambda x: x["rr"], reverse=True)
        top_traits = [t["name"] for t in all_traits[:5]]

        # Count writing samples (could be enhanced with actual sample tracking)
        writing_samples = len([t for t in all_traits if t["rr"] > 50])

        return {
            "snapshot": {
                "languagestyle_rr": languagestyle_rr,
                "interaction_rr": interaction_rr,
                "top_traits": top_traits,
                "writing_samples": writing_samples,
                "active_mode": "casual"  # Default mode, could be enhanced
            }
        }

    def render_chat_response(self, user_input: str) -> str:
        """
        Generate a response in the user's conversational style.

        Args:
            user_input: User's message or prompt

        Returns:
            Generated response matching user's style
        """
        # Placeholder for now - would integrate with LLM for style simulation
        return f"ChatDNA response (style-matched): {user_input}"
