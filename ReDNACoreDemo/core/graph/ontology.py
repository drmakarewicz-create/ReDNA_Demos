"""
Ontology graph operations and helpers (Phase 8)

Provides utilities for loading, querying, and navigating the trait ontology.
"""

from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import json
import logging

from .schemas import OntologyGraph, OntologyNode, OntologyEdge

logger = logging.getLogger(__name__)

# ============================================================================
# SEED ONTOLOGY LOADING
# ============================================================================


def load_seed_ontology() -> OntologyGraph:
    """
    Load seed ontology from JSON file.

    Returns minimal 4-6 trait ontology if file exists,
    otherwise creates a minimal fallback.
    """
    # Try to find seed file (check multiple locations)
    seed_candidates = [
        Path(__file__).parent.parent.parent.parent / "data" / "ontology" / "seed_ontology.json",
        Path("data/ontology/seed_ontology.json"),
        Path.cwd() / "data" / "ontology" / "seed_ontology.json",
    ]

    seed_path = next((p for p in seed_candidates if p.exists()), None)

    if not seed_path:
        logger.warning("Seed ontology file not found, creating minimal fallback")
        return _create_minimal_seed()

    try:
        with open(seed_path) as f:
            data = json.load(f)

        graph = OntologyGraph(
            version=data.get("version", "1.0"),
            nodes=[OntologyNode(**n) for n in data.get("nodes", [])],
            edges=[OntologyEdge(**e) for e in data.get("edges", [])],
        )

        logger.info(
            f"Loaded seed ontology from {seed_path}: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph

    except Exception as e:
        logger.error(f"Failed to load seed ontology from {seed_path}: {e}")
        return _create_minimal_seed()


def _create_minimal_seed() -> OntologyGraph:
    """
    Create minimal 4-trait seed ontology (fallback).

    This is a safety fallback if the JSON file is missing.
    Production should always use the JSON file.
    """
    logger.info("Creating minimal fallback ontology (4 traits)")

    nodes = [
        OntologyNode(
            node_id="ont_chronotype",
            node_type="trait",
            trait_id="PaDNA.Chronotype",
            label="Chronotype",
            category="Behavioral",
            description="Morning person vs. night owl preference",
        ),
        OntologyNode(
            node_id="ont_outdoor_freq",
            node_type="trait",
            trait_id="PaDNA.OutdoorActivity.Frequency",
            label="Outdoor Activity Frequency",
            category="Behavioral",
        ),
        OntologyNode(
            node_id="ont_exercise_time",
            node_type="trait",
            trait_id="PaDNA.Exercise.PreferredTime",
            label="Preferred Exercise Time",
            category="Behavioral",
        ),
        OntologyNode(
            node_id="ont_social_style",
            node_type="trait",
            trait_id="PaDNA.SocialStyle",
            label="Social Style",
            category="Behavioral",
        ),
    ]

    edges = [
        OntologyEdge(
            edge_id="onte_seed_001",
            from_node="ont_chronotype",
            to_node="ont_exercise_time",
            edge_type="suggests_question",
            weight=0.7,
            confidence=0.9,
            source="seed",
            rationale="Morning people often have strong exercise timing preferences",
        ),
        OntologyEdge(
            edge_id="onte_seed_002",
            from_node="ont_chronotype",
            to_node="ont_outdoor_freq",
            edge_type="correlates",
            weight=0.6,
            confidence=0.8,
            source="seed",
            rationale="Chronotype correlates with outdoor activity patterns",
        ),
    ]

    return OntologyGraph(nodes=nodes, edges=edges)


# ============================================================================
# ONTOLOGY NAVIGATION
# ============================================================================


def get_ontology_neighbors(
    ontology: OntologyGraph, trait_id: str, max_neighbors: int = 10
) -> List[Dict[str, Any]]:
    """
    Get neighboring traits in the ontology (for LLM context).

    Args:
        ontology: The ontology graph
        trait_id: Trait ID to find neighbors for (e.g., "PaDNA.Chronotype")
        max_neighbors: Maximum number of neighbors to return

    Returns:
        List of neighbor dicts with trait_id, label, edge_type, weight, rationale
        Sorted by edge weight (descending)
    """
    # Find node by trait_id
    node = next((n for n in ontology.nodes if n.trait_id == trait_id), None)
    if not node:
        logger.debug(f"Trait {trait_id} not found in ontology")
        return []

    neighbors = []

    # Find outgoing edges
    for edge in ontology.edges:
        if edge.from_node == node.node_id:
            to_node = next((n for n in ontology.nodes if n.node_id == edge.to_node), None)
            if to_node and to_node.trait_id:  # Only include trait nodes
                neighbors.append(
                    {
                        "trait_id": to_node.trait_id,
                        "label": to_node.label,
                        "edge_type": edge.edge_type,
                        "weight": edge.weight,
                        "confidence": edge.confidence,
                        "rationale": edge.rationale,
                    }
                )

    # Also check incoming edges (bidirectional relationships)
    for edge in ontology.edges:
        if edge.to_node == node.node_id and edge.edge_type in ["correlates", "suggests_question"]:
            from_node = next((n for n in ontology.nodes if n.node_id == edge.from_node), None)
            if from_node and from_node.trait_id:
                neighbors.append(
                    {
                        "trait_id": from_node.trait_id,
                        "label": from_node.label,
                        "edge_type": f"reverse_{edge.edge_type}",
                        "weight": edge.weight * 0.8,  # Slightly lower weight for reverse
                        "confidence": edge.confidence,
                        "rationale": f"(Reverse) {edge.rationale}",
                    }
                )

    # Sort by weight and return top N
    neighbors.sort(key=lambda x: x["weight"], reverse=True)
    return neighbors[:max_neighbors]


def get_trait_category_neighbors(
    ontology: OntologyGraph, category: str, exclude_trait_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all traits in a category (for exploration strategies).

    Args:
        ontology: The ontology graph
        category: Category name (e.g., "Behavioral", "Lifestyle")
        exclude_trait_id: Optionally exclude a trait (e.g., already known)

    Returns:
        List of trait dicts with trait_id, label, description
    """
    from typing import Optional

    traits = []

    for node in ontology.nodes:
        if (
            node.node_type == "trait"
            and node.category == category
            and node.trait_id != exclude_trait_id
        ):
            traits.append(
                {
                    "trait_id": node.trait_id,
                    "label": node.label,
                    "description": node.description,
                    "priority": node.metadata.get("priority", "medium"),
                }
            )

    return traits


def find_contradiction_edges(
    ontology: OntologyGraph, trait_id_a: str, trait_id_b: str
) -> Optional[OntologyEdge]:
    """
    Check if two traits have a 'contradicts' relationship in the ontology.

    Args:
        ontology: The ontology graph
        trait_id_a: First trait ID
        trait_id_b: Second trait ID

    Returns:
        OntologyEdge if contradiction exists, None otherwise
    """
    node_a = next((n for n in ontology.nodes if n.trait_id == trait_id_a), None)
    node_b = next((n for n in ontology.nodes if n.trait_id == trait_id_b), None)

    if not node_a or not node_b:
        return None

    # Check both directions
    for edge in ontology.edges:
        if edge.edge_type == "contradicts":
            if (edge.from_node == node_a.node_id and edge.to_node == node_b.node_id) or (
                edge.from_node == node_b.node_id and edge.to_node == node_a.node_id
            ):
                return edge

    return None


def get_ontology_stats(ontology: OntologyGraph) -> Dict[str, Any]:
    """Get summary statistics for the ontology (for diagnostics)."""
    trait_nodes = [n for n in ontology.nodes if n.node_type == "trait"]
    value_nodes = [n for n in ontology.nodes if n.node_type == "trait_value"]

    edge_types = {}
    for edge in ontology.edges:
        edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1

    categories = {}
    for node in trait_nodes:
        cat = node.category or "Uncategorized"
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_nodes": len(ontology.nodes),
        "trait_nodes": len(trait_nodes),
        "value_nodes": len(value_nodes),
        "total_edges": len(ontology.edges),
        "edge_types": edge_types,
        "categories": categories,
        "version": ontology.version,
    }
