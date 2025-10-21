"""
Cross-Trait Reasoning Graph Module (Phase 8)

This module implements the graph-based reasoning layer for ReDNA:
- Ontology Graph: System-wide trait relationships
- Belief Graph: Per-user trait beliefs with provenance
- LLM-powered edge inference and curiosity orchestration

AI-Native Principle: All graph updates use LLM reasoning, not deterministic rules.
"""

from .schemas import (
    OntologyNode,
    OntologyEdge,
    OntologyGraph,
    BeliefNode,
    BeliefEdge,
    BeliefGraph,
    GraphUpdate,
    NextQuestionRequest,
    NextQuestionResponse,
)
from .storage import get_graph_storage, GraphStorage
from .ontology import load_seed_ontology, get_ontology_neighbors

__all__ = [
    # Schemas
    "OntologyNode",
    "OntologyEdge",
    "OntologyGraph",
    "BeliefNode",
    "BeliefEdge",
    "BeliefGraph",
    "GraphUpdate",
    "NextQuestionRequest",
    "NextQuestionResponse",
    # Storage
    "get_graph_storage",
    "GraphStorage",
    # Ontology
    "load_seed_ontology",
    "get_ontology_neighbors",
]
