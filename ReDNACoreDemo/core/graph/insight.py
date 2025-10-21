"""
Relational insight generation (Phase 8 Stage 4 - MVP Benchmark #13).

Surfaces insights when user has ≥10 traits by finding patterns across beliefs.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging

from .schemas import BeliefGraph, OntologyGraph, BeliefNode
from .storage import get_graph_storage

logger = logging.getLogger(__name__)


class InsightResponse:
    """Response structure for insight generation."""

    def __init__(
        self,
        text: str,
        cited_nodes: List[str],
        confidence: float,
        insight_type: str = "relational",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.text = text
        self.cited_nodes = cited_nodes
        self.confidence = confidence
        self.insight_type = insight_type
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "cited_nodes": self.cited_nodes,
            "confidence": self.confidence,
            "insight_type": self.insight_type,
            "metadata": self.metadata
        }


def generate_insight(user_id: str) -> Optional[InsightResponse]:
    """
    Generate relational insight from user's belief graph.

    Requirements (MVP Benchmark #13):
    - User must have ≥10 traits
    - Insight cites nodes used (provenance)
    - Returns None if insufficient data

    Stage 4 MVP: Template-based pattern matching
    Stage 4.1+: LLM-powered insight generation

    Args:
        user_id: User ID

    Returns:
        InsightResponse or None if insufficient traits
    """
    storage = get_graph_storage()
    user_graph = storage.load_user_graph(user_id)
    ontology = storage.load_ontology()

    trait_nodes = user_graph.get_trait_nodes()

    # Requirement: ≥10 traits
    if len(trait_nodes) < 10:
        logger.debug(f"User {user_id} has {len(trait_nodes)} traits, need ≥10 for insights")
        return None

    # Find relational patterns
    insight = _find_relational_patterns(user_graph, ontology, trait_nodes)

    if insight:
        logger.info(f"Generated insight for {user_id}: {insight.text[:60]}...")
        return insight
    else:
        logger.debug(f"No relational patterns found for {user_id}")
        return None


def _find_relational_patterns(
    user_graph: BeliefGraph,
    ontology: OntologyGraph,
    trait_nodes: List[BeliefNode]
) -> Optional[InsightResponse]:
    """
    Find relational patterns across traits using template matching.

    Stage 4 MVP patterns:
    1. Chronotype + Exercise → timing suggestion
    2. Diet + Exercise → optimization suggestion
    3. Sleep + Chronotype → consistency check
    4. Height + Exercise → personalization
    """

    # Build trait lookup
    traits_by_id = {n.trait_id: n for n in trait_nodes if n.trait_id}

    # Pattern 1: Morning Lark + Regular Exercise
    chronotype = traits_by_id.get("PaDNA.Chronotype")
    exercise_freq = traits_by_id.get("BehaviorDNA.Exercise.Frequency")

    if chronotype and exercise_freq:
        chrono_value = _extract_value(chronotype.value)
        if chrono_value == "Morning Lark":
            return InsightResponse(
                text=(
                    f"You're a Morning Lark with regular exercise habits. "
                    f"Research shows early risers often perform best with morning workouts. "
                    f"Consider scheduling high-intensity activities before noon for optimal results."
                ),
                cited_nodes=[chronotype.node_id, exercise_freq.node_id],
                confidence=0.75,
                insight_type="relational_optimization",
                metadata={
                    "pattern": "chronotype_exercise",
                    "trait_ids": ["PaDNA.Chronotype", "BehaviorDNA.Exercise.Frequency"]
                }
            )

    # Pattern 2: Diet + Chronotype
    diet_type = traits_by_id.get("BehaviorDNA.Diet.Type")
    if chronotype and diet_type:
        chrono_value = _extract_value(chronotype.value)
        if chrono_value == "Morning Lark":
            return InsightResponse(
                text=(
                    f"As a Morning Lark, your metabolism peaks earlier in the day. "
                    f"Given your diet preferences, consider having your largest meal at lunch "
                    f"rather than dinner to align with your natural circadian rhythm."
                ),
                cited_nodes=[chronotype.node_id, diet_type.node_id],
                confidence=0.70,
                insight_type="relational_timing",
                metadata={
                    "pattern": "chronotype_diet",
                    "trait_ids": ["PaDNA.Chronotype", "BehaviorDNA.Diet.Type"]
                }
            )

    # Pattern 3: Generic high-confidence cluster
    high_conf_traits = [
        n for n in trait_nodes
        if n.ucn and n.ucn.get("u", 1.0) < 0.3 and n.rr_score and n.rr_score > 600
    ]

    if len(high_conf_traits) >= 3:
        # Generic confidence insight
        trait_names = [
            _get_trait_display_name(n.trait_id or "") for n in high_conf_traits[:3]
        ]
        names_str = ", ".join(trait_names)

        return InsightResponse(
            text=(
                f"We have high confidence in several of your traits ({names_str}). "
                f"These form a consistent pattern that suggests stable behavioral tendencies. "
                f"This data can help personalize recommendations with greater accuracy."
            ),
            cited_nodes=[n.node_id for n in high_conf_traits[:3]],
            confidence=0.65,
            insight_type="confidence_cluster",
            metadata={
                "pattern": "high_confidence_cluster",
                "trait_count": len(high_conf_traits)
            }
        )

    # Pattern 4: Ontology-based correlation (if available)
    for edge in ontology.edges:
        if edge.edge_type in ("supports", "correlates"):
            from_node = ontology.get_node_by_id(edge.from_node)
            to_node = ontology.get_node_by_id(edge.to_node)

            if not from_node or not to_node:
                continue

            from_trait_id = from_node.trait_id
            to_trait_id = to_node.trait_id

            if from_trait_id in traits_by_id and to_trait_id in traits_by_id:
                # Both traits present - surface correlation
                from_trait = traits_by_id[from_trait_id]
                to_trait = traits_by_id[to_trait_id]

                from_name = _get_trait_display_name(from_trait_id)
                to_name = _get_trait_display_name(to_trait_id)

                return InsightResponse(
                    text=(
                        f"Your {from_name} and {to_name} show an interesting connection. "
                        f"{edge.rationale or 'These traits often correlate in research.'} "
                        f"This alignment suggests your self-reported data is consistent."
                    ),
                    cited_nodes=[from_trait.node_id, to_trait.node_id],
                    confidence=edge.confidence,
                    insight_type="ontology_correlation",
                    metadata={
                        "pattern": "ontology_correlation",
                        "edge_id": edge.edge_id,
                        "trait_ids": [from_trait_id, to_trait_id]
                    }
                )

    # No patterns found
    return None


def _extract_value(value: Any) -> str:
    """Extract string value from various value formats."""
    if isinstance(value, dict):
        if "enum" in value:
            return str(value["enum"])
        elif "int" in value:
            return str(value["int"])
        elif "float" in value:
            return str(value["float"])
        elif "range" in value:
            r = value["range"]
            return f"{r.get('min')}-{r.get('max')}"
    return str(value)


def _get_trait_display_name(trait_id: str) -> str:
    """Extract human-readable name from trait_id."""
    if not trait_id:
        return "trait"

    # Strip namespace
    parts = trait_id.split(".")
    name = parts[-1] if parts else trait_id

    # Convert CamelCase to space-separated
    import re
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

    return name.lower()


# Export public API
__all__ = ["generate_insight", "InsightResponse"]
