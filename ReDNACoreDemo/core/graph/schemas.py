"""
Pydantic schemas for Cross-Trait Reasoning Graphs (Phase 8)

All graph structures are immutable and versioned for provenance tracking.

Phase 10: ReDNA Hierarchy Redefinition
---------------------------------------
ReDNA (root) = Replicated Digital Neural Approximation - The complete digital organism
├── RelDNA (tier-1) = Relational DNA - Social connections and relationships
├── PaDNA (tier-1) = Physical Attributes DNA - Observable physical traits
├── BehDNA (tier-1) = Behavioral DNA - Behavior patterns and habits
├── CogDNA (tier-1) = Cognitive DNA - Thinking patterns
└── EmoDNA (tier-1) = Emotional DNA - Emotional patterns

Legacy Aliases (read-time compatibility):
- "RelationalDNA" → "RelDNA"
- "BehaviorDNA" → "BehDNA"
"""

from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import uuid4

# ============================================================================
# ONTOLOGY GRAPH (System-wide trait relationships)
# ============================================================================


class OntologyNode(BaseModel):
    """
    Trait or trait-value in the ontology.

    Phase 10: node_type can also be "dna_category" for hierarchy nodes (ReDNA, RelDNA, etc.)
    """

    node_id: str = Field(default_factory=lambda: f"ont_{uuid4().hex[:12]}")
    node_type: Literal["trait", "trait_value", "category", "dna_category"]
    trait_id: Optional[str] = None  # e.g., "PaDNA.Chronotype"
    value: Optional[str] = None  # e.g., "Morning Lark"
    category: Optional[str] = None  # e.g., "Behavioral"
    label: str  # Human-readable
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "ont_chronotype",
                "node_type": "trait",
                "trait_id": "PaDNA.Chronotype",
                "label": "Chronotype",
                "category": "Behavioral",
                "description": "Morning vs. evening preference",
            }
        }


class OntologyEdge(BaseModel):
    """Relationship between traits in the ontology."""

    edge_id: str = Field(default_factory=lambda: f"onte_{uuid4().hex[:12]}")
    from_node: str  # node_id
    to_node: str  # node_id
    edge_type: Literal[
        "supports",  # A supports belief in B
        "contradicts",  # A contradicts B
        "correlates",  # A correlates with B (population data)
        "suggests_question",  # A suggests asking about B
        "is_subcategory_of",  # Hierarchy (legacy)
        "is_parent_of",  # Hierarchy (Phase 10: DNA category hierarchy)
    ]
    weight: float = Field(ge=0.0, le=1.0, default=0.5)  # Strength of relationship
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)  # LLM confidence
    source: Literal["seed", "llm_inferred", "population_learned", "manual"]
    rationale: Optional[str] = None  # Why this edge exists (LLM-generated)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "onte_seed_001",
                "from_node": "ont_chronotype",
                "to_node": "ont_exercise_time",
                "edge_type": "suggests_question",
                "weight": 0.7,
                "confidence": 0.9,
                "source": "seed",
                "rationale": "Morning people often have strong exercise timing preferences",
            }
        }


class OntologyGraph(BaseModel):
    """Complete ontology graph."""

    version: str = "1.0"
    nodes: List[OntologyNode] = Field(default_factory=list)
    edges: List[OntologyEdge] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def get_node_by_id(self, node_id: str) -> Optional[OntologyNode]:
        """Find node by ID."""
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def get_node_by_trait(self, trait_id: str) -> Optional[OntologyNode]:
        """Find node by trait_id."""
        return next((n for n in self.nodes if n.trait_id == trait_id), None)

    def get_outgoing_edges(self, node_id: str) -> List[OntologyEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.from_node == node_id]

    def get_incoming_edges(self, node_id: str) -> List[OntologyEdge]:
        """Get all edges pointing to a node."""
        return [e for e in self.edges if e.to_node == node_id]


# ============================================================================
# USER BELIEF GRAPH (Per-user trait beliefs + observations)
# ============================================================================


class BeliefNode(BaseModel):
    """Node in user's belief graph (trait belief or observation)."""

    node_id: str = Field(default_factory=lambda: f"bn_{uuid4().hex[:12]}")
    node_type: Literal["trait_belief", "observation", "question"]

    # For trait_belief nodes
    trait_id: Optional[str] = None
    value: Optional[Any] = None  # Resolved value
    rr_score: Optional[float] = None  # Legacy 0-1000 (kept for backward compat)
    ucn: Optional[Dict[str, float]] = None  # {u, c, n}

    # Phase 9: Normalized RR/Curiosity (0-100 percentiles)
    rr: Optional[float] = None  # Normalized 0-100 percentile
    curiosity: Optional[float] = None  # 100 - rr (0-100)
    rr_meta: Optional[Dict[str, Any]] = None  # Metadata: {rr_raw, scale, source}

    # For observation nodes
    observation_text: Optional[str] = None
    observation_source: Optional[str] = None  # "chat", "photo", "import"
    observation_ts: Optional[datetime] = None

    # Common fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "bn_abc123def456",
                "node_type": "trait_belief",
                "trait_id": "PaDNA.Chronotype",
                "value": "Morning Lark",
                "rr_score": 750,
                "ucn": {"u": 0.2, "c": 0.7, "n": 0.1},
            }
        }


class BeliefEdge(BaseModel):
    """Edge in user's belief graph (provenance, relationships)."""

    edge_id: str = Field(default_factory=lambda: f"be_{uuid4().hex[:12]}")
    from_node: str  # node_id
    to_node: str  # node_id
    edge_type: Literal[
        "evidence_for",  # Observation → Trait belief
        "supports",  # Trait A supports Trait B (user-specific)
        "contradicts",  # Trait A contradicts Trait B
        "suggests_ask",  # Uncertainty in A → Ask about B
        "inferred_from",  # Trait B inferred from Trait A
    ]
    weight: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source: Literal["promotion", "contradiction_detected", "llm_inference", "holistic"]
    why_card_id: Optional[str] = None  # Link to explainability
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BeliefGraph(BaseModel):
    """Complete user belief graph."""

    user_id: str
    version: str = "1.0"
    nodes: List[BeliefNode] = Field(default_factory=list)
    edges: List[BeliefEdge] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def get_node_by_id(self, node_id: str) -> Optional[BeliefNode]:
        """Find node by ID."""
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def get_trait_nodes(self) -> List[BeliefNode]:
        """Get all trait belief nodes."""
        return [n for n in self.nodes if n.node_type == "trait_belief"]

    def get_observation_nodes(self) -> List[BeliefNode]:
        """Get all observation nodes."""
        return [n for n in self.nodes if n.node_type == "observation"]

    def get_outgoing_edges(self, node_id: str) -> List[BeliefEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.from_node == node_id]

    def get_incoming_edges(self, node_id: str) -> List[BeliefEdge]:
        """Get all edges pointing to a node."""
        return [e for e in self.edges if e.to_node == node_id]


# ============================================================================
# GRAPH OPERATIONS
# ============================================================================


class GraphUpdate(BaseModel):
    """Request to update a user's belief graph."""

    user_id: str
    operation: Literal[
        "add_node", "add_edge", "update_node", "update_edge", "remove_edge"
    ]
    node: Optional[BeliefNode] = None
    edge: Optional[BeliefEdge] = None
    why_card_text: Optional[str] = None  # Natural language explanation
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NextQuestionRequest(BaseModel):
    """Request for next curiosity question via graph traversal."""

    user_id: str
    strategy: Literal["breadth", "depth", "coherence", "auto"] = "auto"
    max_candidates: int = Field(default=5, ge=1, le=20)


class NextQuestionResponse(BaseModel):
    """LLM-selected next question with graph rationale."""

    question_text: str
    target_trait_id: str
    rationale: str  # 1-sentence LLM explanation
    graph_path: List[str] = Field(default_factory=list)  # node_ids showing reasoning path
    ucn_scores: Optional[Dict[str, float]] = None  # Projected UCN after answer
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# LLM REASONING STRUCTURES
# ============================================================================


class WhyCard(BaseModel):
    """
    Explainability card for trait promotions (Phase 8 Stage 4).

    3-part template matching MVP Benchmark #4:
    - what: What was observed/evidence used
    - why: Why it was promoted (RR/UCN/policy rationale)
    - next: What would increase confidence
    """

    id: str = Field(default_factory=lambda: f"wc_{uuid4().hex[:12]}")
    user_id: str
    trait_id: str

    # 3-part template
    what: str  # Top evidence snippet(s)
    why: str   # Promotion rationale tied to RR/UCN/policy
    next: str  # What would increase confidence

    # Metrics
    rr: Optional[float] = None
    ucn: Optional[Dict[str, float]] = None  # {u, c, n}

    # Provenance
    evidence_node_ids: List[str] = Field(default_factory=list)  # Links to observation nodes
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "wc_abc123def456",
                "user_id": "demo_user",
                "trait_id": "PaDNA.Chronotype",
                "what": "You mentioned waking up at 6am naturally every morning",
                "why": "This is a strong signal for Morning Lark chronotype (RR: 720, UCN: 0.3/1.0)",
                "next": "Confirming your evening energy levels would increase confidence to 0.95+",
                "rr": 720.0,
                "ucn": {"u": 0.3, "c": 0.6, "n": 0.7}
            }
        }


class EdgeInferenceRequest(BaseModel):
    """Request to LLM: infer edges from a promoted trait."""

    trait_id: str
    value: Any
    user_context: Dict[str, Any]  # Existing traits for context
    ontology_neighbors: List[str]  # Nearby trait_ids from ontology
    max_edges: int = Field(default=3, ge=1, le=10)


class EdgeInferenceResponse(BaseModel):
    """LLM response: proposed edges with rationale."""

    edges: List[OntologyEdge] = Field(default_factory=list)
    rationale: str  # Overall reasoning


class WhyCardGraphRequest(BaseModel):
    """Request to LLM: generate Why-Card connecting multiple traits."""

    user_id: str
    updated_trait_id: str
    graph_slice: Dict[str, Any]  # Relevant subgraph (nodes + edges)
    trigger: Literal["promotion", "contradiction", "inference"]


class WhyCardGraphResponse(BaseModel):
    """LLM-generated Why-Card with graph context."""

    why_card_text: str  # Natural language explanation
    evidence_nodes: List[str] = Field(default_factory=list)  # node_ids used as evidence
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    uncertainty: float = Field(ge=0.0, le=1.0, default=0.5)
