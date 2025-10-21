"""
Belief Graph Update Rules (Phase 8 Stage 3)

Handles automatic belief graph updates when traits are promoted in the main pipeline.

Core Invariant:
    Every trait promotion MUST produce:
    - 1 observation node (raw evidence)
    - 1 trait belief node (promoted trait, may be reused)
    - 1 evidence_for edge (observation → trait)

Design Philosophy:
    - Deterministic graph updates (no LLM calls in Stage 3)
    - Node reuse for same trait/value (versioned via last_updated)
    - Provenance tracking (every belief traces to observations)
    - Curiosity triggers on high uncertainty

---
Phase 9: AI-First Parent-Child UCN Propagation
---

When creating or updating parent DNA nodes (e.g., PaDNA.HairDNA), the AI should:

1. Consider child UCNs as strong priors:
   - Read current UCNs of all child traits (e.g., PaDNA.HairDNA.Color, PaDNA.HairDNA.Texture).
   - Use them to inform parent UCN, NOT via formula, but via reasoning.

2. Prefer discretion over averaging:
   - If children have high UCN (>750), parent should likely be high too.
   - If children are mixed, reason about what that means for the parent category.
   - If parent has direct evidence (separate from children), weigh it appropriately.

3. Create Why-Cards for divergences:
   - If parent UCN differs from child consensus by >200 points (0-1000 scale):
     Generate Why-Card explaining the reasoning.

4. Soft checks (not hard constraints):
   - No formula-based clamping.
   - Let AI decide parent UCN based on child UCNs + parent evidence + recency + contradictions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
import logging

from .schemas import BeliefGraph, BeliefNode, BeliefEdge
from .storage import get_graph_storage
from .whycard_gen import generate_why_card

logger = logging.getLogger(__name__)


def get_or_create_user_trait_node(
    graph: BeliefGraph,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float]
) -> Tuple[BeliefNode, bool]:
    """
    Get existing trait belief node or create new one.

    Rules:
    - If node exists with same trait_id AND same value:
        - Update rr_score, ucn, last_updated
        - Return (existing_node, False)
    - If node exists with same trait_id BUT different value:
        - Create new node (value changed - contradiction)
        - Return (new_node, True)
    - If node doesn't exist:
        - Create new node
        - Return (new_node, True)

    Args:
        graph: User's belief graph
        trait_id: Trait ID (e.g., "PaDNA.Chronotype")
        value: Trait value (e.g., "Morning Lark")
        rr_score: RR score from UCNRR
        ucn: UCN scores {"u": ..., "c": ..., "n": ...}

    Returns:
        (node, is_new) where is_new=True if node was created
    """
    # 1. Find existing trait belief node with same trait_id
    existing = None
    for node in graph.nodes:
        if node.node_type == "trait_belief" and node.trait_id == trait_id:
            existing = node
            break

    # 2. Check if value matches
    if existing:
        if existing.value == value:
            # CASE A: Same trait, same value → UPDATE
            logger.info(f"Reusing trait node {existing.node_id} for {trait_id}={value}")
            existing.rr_score = rr_score
            existing.ucn = ucn
            existing.last_updated = datetime.now(timezone.utc)
            return (existing, False)
        else:
            # CASE B: Same trait, different value → CONTRADICTION
            logger.warning(
                f"Contradiction detected: {trait_id} changed from {existing.value} to {value}"
            )

            # Stage 4: Log contradiction event (AC5)
            _log_contradiction_event(
                trait_id=trait_id,
                old_node_id=existing.node_id,
                old_value=existing.value,
                new_value=value,
                old_rr=existing.rr_score or 0,
                new_rr=rr_score,
                old_ucn=existing.ucn or {},
                new_ucn=ucn
            )

            new_node = BeliefNode(
                node_type="trait_belief",
                trait_id=trait_id,
                value=value,
                rr_score=rr_score,
                ucn=ucn
            )
            # Note: Contradiction edge creation deferred to Stage 4.1
            return (new_node, True)
    else:
        # CASE C: New trait → CREATE
        logger.info(f"Creating new trait node for {trait_id}={value}")
        new_node = BeliefNode(
            node_type="trait_belief",
            trait_id=trait_id,
            value=value,
            rr_score=rr_score,
            ucn=ucn
        )
        return (new_node, True)


def validate_evidence_edge(edge: BeliefEdge, from_node: BeliefNode, to_node: BeliefNode) -> None:
    """
    Validate evidence_for edge meets schema requirements.

    Rules:
    - No self-loops
    - Must go from observation → trait_belief
    - Required fields must be present

    Raises:
        ValueError: If validation fails
    """
    # No self-loops
    if edge.from_node == edge.to_node:
        raise ValueError(
            f"evidence_for edges cannot be self-loops (node_id={edge.from_node})"
        )

    # Must go from observation → trait_belief
    if from_node.node_type != "observation":
        raise ValueError(
            f"evidence_for edges must originate from observation nodes, "
            f"got {from_node.node_type}"
        )

    if to_node.node_type != "trait_belief":
        raise ValueError(
            f"evidence_for edges must point to trait_belief nodes, "
            f"got {to_node.node_type}"
        )

    # Required fields (already enforced by Pydantic, but double-check)
    if edge.weight is None or edge.confidence is None:
        raise ValueError(
            f"evidence_for edges must have weight and confidence fields"
        )


def on_trait_promotion(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_ts: Optional[datetime] = None,
    why_card_text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update user's belief graph after trait promotion.

    This is the main hook called from the existing promotion pipeline.

    Args:
        user_id: User ID
        trait_id: Trait ID (e.g., "PaDNA.Chronotype")
        value: Trait value (e.g., "Morning Lark", 175, {"min": 5, "max": 7})
        rr_score: RR score from UCNRR (0-1000)
        ucn: UCN scores {"u": float, "c": float, "n": float}
        observation_text: Original raw text (e.g., "I wake up at 6am every day")
        observation_source: Source ("chat", "photo_analysis", "inference", "onboarding")
        observation_ts: When observation was captured (defaults to now)
        why_card_text: Optional Why-Card explanation
        metadata: Optional metadata for observation node

    Returns:
        {
            "status": "ok",
            "observation_node_id": str,
            "trait_node_id": str,
            "edge_id": str,
            "is_new_trait": bool,
            "contradiction_detected": bool,
            "curiosity_triggered": bool
        }

    Raises:
        ValueError: If validation fails
    """
    try:
        storage = get_graph_storage()
        graph = storage.load_user_graph(user_id)

        # 1. Create observation node
        obs_node = BeliefNode(
            node_type="observation",
            observation_text=observation_text,
            observation_source=observation_source,
            observation_ts=observation_ts or datetime.now(timezone.utc),
            metadata=metadata or {}
        )

        logger.info(
            f"Created observation node {obs_node.node_id} for {user_id}: "
            f"{observation_text[:50]}..."
        )

        # 2. Get or create trait belief node
        trait_node, is_new = get_or_create_user_trait_node(
            graph, trait_id, value, rr_score, ucn
        )

        # 3. Generate Why-Card (Stage 4)
        why_card = generate_why_card(
            user_id=user_id,
            trait_id=trait_id,
            value=value,
            rr_score=rr_score,
            ucn=ucn,
            observation_text=observation_text,
            observation_source=observation_source,
            observation_node_id=obs_node.node_id,
            metadata=metadata
        )

        # Save Why-Card to storage
        storage.save_why_card(why_card)

        logger.info(
            f"Generated Why-Card {why_card.id} for {user_id}/{trait_id}: "
            f"RR={rr_score:.0f}, UCN={{u:{ucn.get('u', 0):.2f}}}"
        )

        # 4. Create evidence edge with Why-Card reference
        edge = BeliefEdge(
            edge_type="evidence_for",
            from_node=obs_node.node_id,
            to_node=trait_node.node_id,
            weight=rr_score / 1000.0,  # Normalize to [0, 1]
            confidence=ucn.get("c", 0.5),
            source="promotion",
            why_card_id=why_card.id,  # Link to Why-Card
            metadata={
                "promotion_ts": datetime.now(timezone.utc).isoformat(),
                "why_card_text": why_card_text  # Legacy field for backward compat
            }
        )

        # 5. Validate edge
        validate_evidence_edge(edge, obs_node, trait_node)

        logger.info(
            f"Created evidence edge {edge.edge_id}: "
            f"{obs_node.node_id} → {trait_node.node_id} "
            f"(weight={edge.weight:.3f}, conf={edge.confidence:.3f}, why_card={why_card.id})"
        )

        # 6. Append to storage
        # Always write both observation and trait nodes (trait may be updated)
        nodes_to_add = [obs_node, trait_node]

        storage.append_user_graph_update(
            user_id=user_id,
            nodes=nodes_to_add,
            edges=[edge]
        )

        logger.info(
            f"Graph updated for {user_id}: +{len(nodes_to_add)} nodes, +1 edge"
        )

        # 7. Check for high uncertainty → trigger curiosity
        curiosity_triggered = False
        if ucn.get("u", 0) > 0.7:
            on_high_uncertainty(user_id, trait_id, ucn)
            curiosity_triggered = True

        return {
            "status": "ok",
            "observation_node_id": obs_node.node_id,
            "trait_node_id": trait_node.node_id,
            "edge_id": edge.edge_id,
            "why_card_id": why_card.id,
            "is_new_trait": is_new,
            "contradiction_detected": False,  # Stage 3: always False, Stage 4: detect
            "curiosity_triggered": curiosity_triggered
        }

    except Exception as e:
        logger.error(
            f"Failed to update graph for {user_id}/{trait_id}: {e}",
            exc_info=True
        )
        # Don't fail the promotion if graph update fails
        return {
            "status": "degraded",
            "error": str(e),
            "warning": "Graph update failed but promotion succeeded"
        }


def on_high_uncertainty(
    user_id: str,
    trait_id: str,
    ucn: Dict[str, float]
) -> None:
    """
    Trigger curiosity queue update for high-uncertainty traits.

    Stage 3: Simple threshold-based enqueue
    Stage 4: LLM-powered question selection using graph context

    Args:
        user_id: User ID
        trait_id: Trait ID with high uncertainty
        ucn: UCN scores {"u": float, "c": float, "n": float}
    """
    uncertainty = ucn.get("u", 0)
    curiosity = ucn.get("c", 0)

    # Only trigger if uncertainty is high AND curiosity is non-zero
    if uncertainty > 0.7 and curiosity > 0.3:
        try:
            # Import here to avoid circular dependencies
            from ..curiosity import store as curiosity_store
            from ..curiosity.models import CuriosityItem

            # Create simple curiosity item (Stage 4 will use graph context)
            item = CuriosityItem(
                user_id=user_id,
                trait_id=trait_id,
                question_text=f"[Graph Uncertainty] Tell me more about {trait_id}",
                priority=curiosity,
                metadata={
                    "ucn": ucn,
                    "source": "graph_uncertainty",
                    "stage": 3
                }
            )

            # Enqueue (integrates with existing curiosity queue)
            curiosity_store.enqueue_item(user_id, item)

            logger.info(
                f"Enqueued curiosity item for {user_id}/{trait_id} "
                f"(u={uncertainty:.2f}, c={curiosity:.2f})"
            )

        except ImportError:
            logger.warning(
                f"Curiosity store not available, skipping enqueue for {user_id}/{trait_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to enqueue curiosity item for {user_id}/{trait_id}: {e}",
                exc_info=True
            )


def _log_contradiction_event(
    trait_id: str,
    old_node_id: str,
    old_value: Any,
    new_value: Any,
    old_rr: float,
    new_rr: float,
    old_ucn: Dict[str, float],
    new_ucn: Dict[str, float]
) -> None:
    """
    Log contradiction event to file (AC5: badge + log).

    Stage 4: Logs event to contradiction_events.jsonl
    Stage 4.1: Create contradicts edge + trigger LLM explanation

    Args:
        trait_id: Trait ID with contradiction
        old_node_id: Previous node ID
        old_value: Previous value
        new_value: New (conflicting) value
        old_rr: Previous RR score
        new_rr: New RR score
        old_ucn: Previous UCN
        new_ucn: New UCN
    """
    import json
    from pathlib import Path
    import os

    # Write to system-wide contradiction log
    data_root = Path(os.getenv("CORE_DATA_ROOT", "data"))
    log_path = data_root / "contradiction_events.jsonl"

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "trait_id": trait_id,
        "old_node_id": old_node_id,
        "new_node_id": "pending",  # Will be set after node creation
        "old_value": old_value,
        "new_value": new_value,
        "old_rr": old_rr,
        "new_rr": new_rr,
        "old_ucn": old_ucn,
        "new_ucn": new_ucn,
        "severity": "moderate" if abs(new_rr - old_rr) > 200 else "low"
    }

    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

        logger.warning(
            f"[CONTRADICTION] {trait_id}: {old_value} → {new_value} "
            f"(RR: {old_rr:.0f} → {new_rr:.0f})"
        )
    except Exception as e:
        logger.error(f"Failed to log contradiction event: {e}")


def on_contradiction_detected(
    user_id: str,
    old_node_id: str,
    new_node_id: str,
    trait_id: str
) -> None:
    """
    Handle trait value contradictions (same trait, different values).

    Stage 4: Logs contradiction event (called from get_or_create_user_trait_node)
    Stage 4.1: Create "contradicts" edge and trigger LLM explanation

    Args:
        user_id: User ID
        old_node_id: Previous trait belief node ID
        new_node_id: New trait belief node ID
        trait_id: Trait ID that has contradictory values
    """
    logger.warning(
        f"Contradiction detected for {user_id}/{trait_id}: "
        f"{old_node_id} → {new_node_id}"
    )

    # Stage 4: Event logged in _log_contradiction_event()
    # Stage 4.1: Create "contradicts" edge and trigger LLM explanation


# Export public API
__all__ = [
    "on_trait_promotion",
    "on_high_uncertainty",
    "on_contradiction_detected",
    "get_or_create_user_trait_node",
    "validate_evidence_edge",
]
