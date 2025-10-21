"""
FastAPI router for Cross-Trait Reasoning Graphs (Phase 8 Stage 2)

Provides REST API for ontology and belief graph operations.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .schemas import (
    OntologyGraph,
    BeliefGraph,
    GraphUpdate,
    NextQuestionRequest,
    NextQuestionResponse,
    BeliefNode,
    BeliefEdge,
)
from .storage import get_graph_storage
from .ontology import (
    load_seed_ontology,
    get_ontology_neighbors,
    get_ontology_stats,
)
from .curiosity import choose_next_question
from .insight import generate_insight
from .aliases import get_all_aliases, get_canonical_trait_id
from .normalize_egress import normalize_belief_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])

# ============================================================================
# VERSION COMPARISON HELPER (Phase 10)
# ============================================================================


def _version_greater(v1: str, v2: str) -> bool:
    """
    Compare semantic versions (e.g., "2.0" > "1.0").

    Args:
        v1: Version string (e.g., "2.0", "1.5.3")
        v2: Version string to compare against

    Returns:
        True if v1 > v2, False otherwise
    """
    try:
        # Parse versions as tuples of ints (e.g., "2.0" -> (2, 0))
        v1_parts = tuple(int(x) for x in v1.split("."))
        v2_parts = tuple(int(x) for x in v2.split("."))
        return v1_parts > v2_parts
    except (ValueError, AttributeError):
        # If parsing fails, fall back to string comparison
        return v1 > v2


# ============================================================================
# ONTOLOGY ENDPOINTS
# ============================================================================


@router.post("/ontology/load")
async def load_ontology_endpoint(force: bool = Query(default=False)) -> Dict[str, Any]:
    """
    Load seed ontology (idempotent, safe to call on startup).

    This endpoint loads the seed ontology from disk and saves it to storage
    if it doesn't already exist. Calling multiple times is safe.

    Args:
        force: If True, REPLACE existing ontology with seed (not merge). Default False.

    Returns:
        dict: Status with node/edge counts and version

    Phase 10: Supports force=true to reload Phase 10 hierarchy, and auto-upgrade when seed.version > stored.version
    """
    try:
        storage = get_graph_storage()

        if force:
            # Force load: replace existing ontology with seed
            logger.info("[Phase 10] Force loading ontology from seed (replace mode)")
            graph = load_seed_ontology()
            storage.save_ontology(graph)
            action = "force_loaded"
        else:
            # Normal load: only load if empty or version upgrade needed
            graph = storage.load_ontology()
            seed_graph = load_seed_ontology()

            if not graph.nodes:
                # Empty: load from seed
                logger.info("Ontology empty, loading from seed")
                graph = seed_graph
                storage.save_ontology(graph)
                action = "loaded_from_seed"
            elif _version_greater(seed_graph.version, graph.version):
                # Version upgrade: replace with seed
                logger.info(
                    f"[Phase 10] Seed version {seed_graph.version} > stored version {graph.version}, upgrading"
                )
                graph = seed_graph
                storage.save_ontology(graph)
                action = "upgraded"
            else:
                # Already loaded, no action needed
                logger.debug(f"Ontology already loaded (version {graph.version}), no action needed")
                action = "already_loaded"

        stats = get_ontology_stats(graph)

        return {
            "status": "ok",
            "message": "Ontology loaded successfully",
            "action": action,
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "version": graph.version,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Failed to load ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load ontology: {str(e)}")


@router.get("/ontology", response_model=OntologyGraph)
async def get_ontology() -> OntologyGraph:
    """
    Get full ontology graph.

    Returns:
        OntologyGraph: Complete ontology with all nodes and edges
    """
    try:
        storage = get_graph_storage()
        graph = storage.load_ontology()

        if not graph.nodes:
            logger.warning("Ontology is empty, may need to call POST /ontology/load")

        return graph

    except Exception as e:
        logger.error(f"Failed to get ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ontology: {str(e)}")


@router.get("/ontology/stats")
async def get_ontology_statistics() -> Dict[str, Any]:
    """
    Get ontology statistics (diagnostics).

    Returns:
        dict: Statistics including node counts, edge types, categories
    """
    try:
        storage = get_graph_storage()
        ontology = storage.load_ontology()
        stats = get_ontology_stats(ontology)
        return {"status": "ok", "stats": stats}

    except Exception as e:
        logger.error(f"Failed to get ontology stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get ontology stats: {str(e)}"
        )


@router.get("/ontology/neighbors/{trait_id}")
async def get_ontology_trait_neighbors(
    trait_id: str, max_neighbors: int = Query(default=10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get neighboring traits in ontology (for LLM context).

    Args:
        trait_id: Trait ID to find neighbors for (e.g., "PaDNA.Chronotype")
        max_neighbors: Maximum number of neighbors to return

    Returns:
        dict: List of neighbor traits with relationship info
    """
    try:
        storage = get_graph_storage()
        ontology = storage.load_ontology()
        neighbors = get_ontology_neighbors(ontology, trait_id, max_neighbors)

        return {
            "status": "ok",
            "trait_id": trait_id,
            "neighbor_count": len(neighbors),
            "neighbors": neighbors,
        }

    except Exception as e:
        logger.error(f"Failed to get neighbors for {trait_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get neighbors: {str(e)}"
        )


# ============================================================================
# USER BELIEF GRAPH ENDPOINTS
# ============================================================================


@router.get("/user/{user_id}", response_model=BeliefGraph)
async def get_user_belief_graph(user_id: str) -> BeliefGraph:
    """
    Get user's complete belief graph with normalized RR/Curiosity values.

    Args:
        user_id: User identifier

    Returns:
        BeliefGraph: User's belief graph with RR (0-100), Curiosity (100-RR), and rr_meta
    """
    try:
        storage = get_graph_storage()
        graph = storage.load_user_graph(user_id)

        # Normalize RR/Curiosity for API egress (Phase 9)
        graph = normalize_belief_graph(graph, user_id)

        logger.info(
            f"Retrieved belief graph for {user_id}: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph

    except Exception as e:
        logger.error(f"Failed to get belief graph for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get belief graph: {str(e)}"
        )


@router.get("/user/{user_id}/stats")
async def get_user_graph_stats(user_id: str) -> Dict[str, Any]:
    """
    Get user's belief graph statistics.

    Args:
        user_id: User identifier

    Returns:
        dict: Statistics about user's graph (node counts, edge types, etc.)
    """
    try:
        storage = get_graph_storage()
        graph = storage.load_user_graph(user_id)

        trait_nodes = [n for n in graph.nodes if n.node_type == "trait_belief"]
        obs_nodes = [n for n in graph.nodes if n.node_type == "observation"]

        edge_types = {}
        for edge in graph.edges:
            edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1

        # Average RR score for traits
        rr_scores = [n.rr_score for n in trait_nodes if n.rr_score is not None]
        avg_rr = sum(rr_scores) / len(rr_scores) if rr_scores else 0

        return {
            "status": "ok",
            "user_id": user_id,
            "total_nodes": len(graph.nodes),
            "trait_nodes": len(trait_nodes),
            "observation_nodes": len(obs_nodes),
            "total_edges": len(graph.edges),
            "edge_types": edge_types,
            "avg_rr_score": round(avg_rr, 2),
            "version": graph.version,
            "last_updated": graph.last_updated.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get stats for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/user/{user_id}/update")
async def update_user_belief_graph(user_id: str, update: GraphUpdate) -> Dict[str, Any]:
    """
    Update user's belief graph (add nodes/edges from promotions).

    Args:
        user_id: User identifier
        update: GraphUpdate with operation, node/edge data, and Why-Card

    Returns:
        dict: Status with updated counts and Why-Card text
    """
    try:
        storage = get_graph_storage()

        # Validate user_id matches
        if update.user_id != user_id:
            raise HTTPException(
                status_code=400,
                detail=f"User ID mismatch: URL={user_id}, body={update.user_id}",
            )

        # Load current graph (for validation)
        graph = storage.load_user_graph(user_id)

        # Prepare nodes and edges to append
        nodes_to_add: List[BeliefNode] = []
        edges_to_add: List[BeliefEdge] = []

        if update.operation == "add_node" and update.node:
            nodes_to_add.append(update.node)
            logger.info(
                f"Adding node {update.node.node_id} to user {user_id} ({update.node.node_type})"
            )

        elif update.operation == "add_edge" and update.edge:
            edges_to_add.append(update.edge)
            logger.info(
                f"Adding edge {update.edge.edge_id} to user {user_id} ({update.edge.edge_type})"
            )

        elif update.operation == "update_node" and update.node:
            # For update, we write a new version (append-only)
            nodes_to_add.append(update.node)
            logger.info(f"Updating node {update.node.node_id} for user {user_id}")

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation or missing data: {update.operation}",
            )

        # Also add any nodes/edges from metadata (e.g., observation + evidence edge)
        if update.metadata:
            if "observation_node" in update.metadata:
                obs_node = BeliefNode(**update.metadata["observation_node"])
                nodes_to_add.append(obs_node)
                logger.debug(f"Added observation node from metadata: {obs_node.node_id}")

            if "evidence_edge" in update.metadata:
                evidence_edge = BeliefEdge(**update.metadata["evidence_edge"])
                edges_to_add.append(evidence_edge)
                logger.debug(f"Added evidence edge from metadata: {evidence_edge.edge_id}")

            if "inferred_edges" in update.metadata:
                for edge_data in update.metadata["inferred_edges"]:
                    inferred_edge = BeliefEdge(**edge_data)
                    edges_to_add.append(inferred_edge)
                    logger.debug(f"Added inferred edge from metadata: {inferred_edge.edge_id}")

        # Append to storage (atomic operation)
        storage.append_user_graph_update(user_id, nodes=nodes_to_add, edges=edges_to_add)

        # Reload to get updated counts
        updated_graph = storage.load_user_graph(user_id)

        return {
            "status": "ok",
            "message": "Graph updated successfully",
            "user_id": user_id,
            "nodes": len(updated_graph.nodes),
            "edges": len(updated_graph.edges),
            "nodes_added": len(nodes_to_add),
            "edges_added": len(edges_to_add),
            "why_card_text": update.why_card_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update graph for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update graph: {str(e)}")


@router.get("/user/{user_id}/provenance/{trait_id}")
async def get_trait_provenance(user_id: str, trait_id: str) -> Dict[str, Any]:
    """
    Get provenance chain for a trait (observations → inferences).

    Traces back from a trait belief to the observations that support it.

    Args:
        user_id: User identifier
        trait_id: Trait ID to trace (e.g., "PaDNA.Chronotype")

    Returns:
        dict: Trait node and evidence chain (observations, edges) with normalized RR/Curiosity
    """
    try:
        from .normalize_egress import normalize_belief_node

        storage = get_graph_storage()
        graph = storage.load_user_graph(user_id)

        # Find trait node
        trait_node = next(
            (n for n in graph.nodes if n.trait_id == trait_id and n.node_type == "trait_belief"),
            None,
        )

        if not trait_node:
            raise HTTPException(
                status_code=404, detail=f"Trait {trait_id} not found in belief graph for {user_id}"
            )

        # Phase 9: Normalize trait node before returning
        trait_node = normalize_belief_node(trait_node, user_id)

        # Traverse backwards to find evidence
        evidence_chain = []
        visited = set()

        def traverse(node_id: str, depth: int = 0):
            if node_id in visited or depth > 10:
                return
            visited.add(node_id)

            # Find incoming evidence edges
            for edge in graph.edges:
                if edge.to_node == node_id and edge.edge_type == "evidence_for":
                    from_node = next(
                        (n for n in graph.nodes if n.node_id == edge.from_node), None
                    )
                    if from_node:
                        evidence_chain.append(
                            {
                                "node": from_node.model_dump(mode="json"),
                                "edge": edge.model_dump(mode="json"),
                                "depth": depth,
                            }
                        )
                        # Recursively traverse (in case observations build on each other)
                        traverse(edge.from_node, depth + 1)

        traverse(trait_node.node_id)

        return {
            "status": "ok",
            "user_id": user_id,
            "trait_id": trait_id,
            "trait_node": trait_node.model_dump(mode="json"),
            "evidence_count": len(evidence_chain),
            "evidence_chain": evidence_chain,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provenance for {trait_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get provenance: {str(e)}"
        )


# ============================================================================
# CURIOSITY ORCHESTRATOR (Graph-Aware) - STUB FOR STAGE 4
# ============================================================================


@router.post("/user/{user_id}/next_question")
async def get_next_question_graph_aware(
    user_id: str, request: NextQuestionRequest
) -> NextQuestionResponse:
    """
    Get next curiosity question via graph traversal + LLM selection.

    **STAGE 2 STUB**: Returns a simple fallback response.
    **STAGE 4**: Will implement full LLM-powered graph traversal.

    Args:
        user_id: User identifier
        request: NextQuestionRequest with strategy and max_candidates

    Returns:
        NextQuestionResponse: Selected question with graph rationale
    """
    try:
        storage = get_graph_storage()
        user_graph = storage.load_user_graph(user_id)
        ontology = storage.load_ontology()

        # STUB: Simple fallback logic (deterministic)
        # TODO Stage 4: Replace with LLM-powered selection

        logger.warning(
            f"next_question endpoint is STUB in Stage 2 (user={user_id}, strategy={request.strategy})"
        )

        # Find traits with suggests_ask edges
        suggestion_edges = [e for e in user_graph.edges if e.edge_type == "suggests_ask"]

        if suggestion_edges:
            # Return first suggestion
            edge = suggestion_edges[0]
            return NextQuestionResponse(
                question_text=f"Can you tell me more about {edge.to_node}?",
                target_trait_id=edge.to_node,
                rationale="[STUB Stage 2] Found suggests_ask edge in graph",
                graph_path=[edge.from_node, edge.edge_id, edge.to_node],
                confidence=0.5,
            )
        else:
            # No suggestions, return generic question
            return NextQuestionResponse(
                question_text="What's something interesting about yourself?",
                target_trait_id="unknown",
                rationale="[STUB Stage 2] No graph suggestions available",
                graph_path=[],
                confidence=0.3,
            )

    except Exception as e:
        logger.error(f"Failed to get next question for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get next question: {str(e)}"
        )


@router.get("/user/{user_id}/next_question")
async def get_next_question_get(
    user_id: str, strategy: str = "auto", max_candidates: int = 5
) -> NextQuestionResponse:
    """
    Convenience GET shim for graph-aware curiosity question selection (Stage 4).

    Uses graph traversal + ontology neighbors to find best next question.
    """
    try:
        # Stage 4: Use graph-aware selection
        result = choose_next_question(user_id, strategy, max_candidates)
        logger.info(
            f"Generated next question for {user_id}: {result.question_text[:50]}... "
            f"(target={result.target_trait_id}, conf={result.confidence:.2f})"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to get next question for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get next question: {str(e)}"
        )


# ============================================================================
# WHY-CARDS & INSIGHTS (Stage 4)
# ============================================================================


@router.get("/user/{user_id}/why_cards")
async def get_user_why_cards(
    user_id: str, trait_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get Why-Cards for user (Stage 4 - MVP Benchmark #4).

    Optionally filter by trait_id. Trait filtering is alias-aware:
    - PaDNA.Chronotype will also return BehaviorDNA.Sleep.Chronotype cards
    - BehaviorDNA.Sleep.Chronotype will also return PaDNA.Chronotype cards

    Args:
        user_id: User identifier
        trait_id: Optional trait ID filter (alias-aware)

    Returns:
        dict: List of Why-Cards with 3-part template (what, why, next)
    """
    try:
        storage = get_graph_storage()

        # Expand trait_id to include all aliases
        if trait_id:
            all_trait_ids = get_all_aliases(trait_id)
            logger.debug(f"Expanding trait_id={trait_id} to aliases: {all_trait_ids}")
        else:
            all_trait_ids = []

        # Fetch cards for all aliases and merge
        all_cards = []
        seen_card_ids = set()

        if trait_id:
            for tid in all_trait_ids:
                cards = storage.load_why_cards(user_id, tid)
                for card in cards:
                    if card.id not in seen_card_ids:
                        all_cards.append(card)
                        seen_card_ids.add(card.id)
        else:
            # No filter, just get all
            all_cards = storage.load_why_cards(user_id, None)

        # Sort by created_at descending (most recent first)
        all_cards.sort(key=lambda c: c.created_at, reverse=True)

        return {
            "status": "ok",
            "user_id": user_id,
            "trait_id": trait_id,
            "count": len(all_cards),
            "why_cards": [card.model_dump(mode="json") for card in all_cards]
        }

    except Exception as e:
        logger.error(f"Failed to get Why-Cards for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get Why-Cards: {str(e)}"
        )


@router.get("/user/{user_id}/why_cards/{why_card_id}")
async def get_why_card_by_id(user_id: str, why_card_id: str) -> Dict[str, Any]:
    """
    Get specific Why-Card by ID (AC2: renders ≤2s with RR, UCN, evidence).

    Args:
        user_id: User identifier
        why_card_id: Why-Card ID

    Returns:
        dict: Why-Card with full details
    """
    try:
        storage = get_graph_storage()
        card = storage.get_why_card_by_id(user_id, why_card_id)

        if not card:
            raise HTTPException(
                status_code=404,
                detail=f"Why-Card {why_card_id} not found for user {user_id}"
            )

        return {
            "status": "ok",
            "why_card": card.model_dump(mode="json")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Why-Card {why_card_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get Why-Card: {str(e)}"
        )


@router.get("/user/{user_id}/insight")
async def get_user_insight(user_id: str) -> Dict[str, Any]:
    """
    Generate relational insight for user (Stage 4 - MVP Benchmark #13).

    Requires ≥10 traits. Returns insight with cited nodes.

    Args:
        user_id: User identifier

    Returns:
        dict: Insight text, cited nodes, confidence (or null if <10 traits)
    """
    try:
        insight = generate_insight(user_id)

        if not insight:
            return {
                "status": "insufficient_data",
                "user_id": user_id,
                "message": "Need ≥10 traits to generate insights",
                "insight": None
            }

        return {
            "status": "ok",
            "user_id": user_id,
            "insight": insight.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to generate insight for {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate insight: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/health")
async def graph_health_check() -> Dict[str, Any]:
    """
    Health check for graph module.

    Returns:
        dict: Status, ontology loaded status, version
    """
    try:
        storage = get_graph_storage()
        ontology = storage.load_ontology()

        return {
            "status": "healthy",
            "module": "graph",
            "ontology_loaded": len(ontology.nodes) > 0,
            "ontology_nodes": len(ontology.nodes),
            "ontology_edges": len(ontology.edges),
            "ontology_version": ontology.version,
        }
    except Exception as e:
        logger.error(f"Graph health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "module": "graph",
            "error": str(e),
        }
