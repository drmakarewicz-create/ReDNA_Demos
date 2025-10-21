"""
Egress normalization for RR/Curiosity values in API responses.

Ensures all API responses return RR as 0-100 percentiles and Curiosity = 100 - RR.

Phase 9: Enhanced with guarded normalization (defense-in-depth):
- Adapts rr > 100 (legacy 0-1000 scale)
- Fills missing rr from rr_score
- Fills missing rr from reference population (if UCN present)
- Corrects curiosity mismatches (ensures curiosity = 100 - rr)
- Logs all adaptations for audit trail
"""

from typing import Any, Dict, List, Optional
import logging
import os

from .schemas import BeliefGraph, BeliefNode
from ..metrics.rr_adapter import rr_to_percentile

logger = logging.getLogger(__name__)

# Feature flags
RR_ADAPTER_ENABLED = os.getenv("RR_ADAPTER_ENABLED", "true").lower() == "true"
REFERENCE_POP_ENABLED = os.getenv("REFERENCE_POP_ENABLED", "true").lower() == "true"
REFERENCE_POP_SOURCE = os.getenv("REFERENCE_POP_SOURCE", "synthetic")
RR_PREFER_REFERENCE_OVER_SCORE = os.getenv("RR_PREFER_REFERENCE_OVER_SCORE", "true").lower() == "true"

# Log feature flags once at module load
logger.info(
    f"[RR-Adapter] enabled={RR_ADAPTER_ENABLED}, "
    f"reference_enabled={REFERENCE_POP_ENABLED}, "
    f"source={REFERENCE_POP_SOURCE}, "
    f"prefer_reference={RR_PREFER_REFERENCE_OVER_SCORE}"
)


def normalize_belief_node(node: BeliefNode, user_id: str) -> BeliefNode:
    """
    Normalize RR/Curiosity in a belief node for API egress (Phase 9 guarded normalization).

    Guards:
    1. If rr > 100 → assume 0-1000 scale, divide by 10, recompute curiosity
    2. If rr=null and rr_score present → derive using adapter
    3. If curiosity present but rr missing → compute rr = 100 - curiosity
    4. If curiosity ≠ 100 - rr → correct and log mismatch
    5. If neither RR nor rr_score but UCN present → derive from reference pop

    Args:
        node: Belief node (may have rr_score in 0-1000 range, or rr/curiosity fields)
        user_id: User identifier for reference lookup

    Returns:
        Normalized node with rr (0-100), curiosity (0-100), and rr_meta
    """
    if node.node_type != "trait_belief":
        return node

    node_dict = node.model_dump()
    trait_id = node.trait_id or "unknown"

    # Extract current values (may be None or set)
    rr = node_dict.get("rr")
    rr_score = node_dict.get("rr_score")
    curiosity = node_dict.get("curiosity")
    ucn = node_dict.get("ucn")  # {u, c, n} dict or scalar

    # Guard 1: If rr > 100, assume legacy 0-1000 scale
    if rr is not None and rr > 100:
        logger.warning(f"[RR-Norm] {trait_id}: rr={rr:.2f} > 100, adapting from 0-1000 scale")
        rr = rr / 10.0
        curiosity = 100.0 - rr

    # Guard 2: If rr=null but rr_score present, derive using adapter
    elif rr is None and rr_score is not None:
        scale = "0_1000" if rr_score > 100 else "0_100"
        normalized = rr_to_percentile(
            rr_raw=rr_score,
            rr_scale=scale,
            trait_id=trait_id,
            user_id=user_id
        )
        rr = normalized["rr"]
        curiosity = normalized["curiosity"]
        node_dict["rr_meta"] = normalized["rr_meta"]
        logger.info(f"[RR-Norm] {trait_id}: filled rr from rr_score={rr_score:.2f} → rr={rr:.2f}")

    # Guard 3: If curiosity present but rr missing, compute rr = 100 - curiosity
    elif rr is None and curiosity is not None:
        rr = 100.0 - curiosity
        logger.info(f"[RR-Norm] {trait_id}: filled rr from curiosity={curiosity:.2f} → rr={rr:.2f}")

    # Guard 5: If neither RR nor rr_score but UCN present, derive from reference pop
    elif rr is None and rr_score is None and ucn is not None:
        if REFERENCE_POP_ENABLED:
            normalized = rr_to_percentile(
                rr_raw=None,
                rr_scale="reference_percentile",
                trait_id=trait_id,
                user_id=user_id,
                use_reference=True
            )
            rr = normalized["rr"]
            curiosity = normalized["curiosity"]
            node_dict["rr_meta"] = normalized["rr_meta"]
            logger.info(f"[RR-Norm] {trait_id}: derived rr from reference pop (UCN present) → rr={rr:.2f}")
        else:
            # Fallback: no RR available
            rr = 50.0
            curiosity = 50.0
            logger.warning(f"[RR-Norm] {trait_id}: no RR/rr_score, using fallback rr=50.0")

    # Guard 4: Ensure curiosity = 100 - rr (correct any mismatch)
    if rr is not None and curiosity is not None:
        expected_curiosity = 100.0 - rr
        if abs(curiosity - expected_curiosity) > 0.01:
            logger.warning(
                f"[RR-Norm] {trait_id}: curiosity mismatch: "
                f"curiosity={curiosity:.2f}, expected={expected_curiosity:.2f} (from rr={rr:.2f}), correcting"
            )
            curiosity = expected_curiosity

    # If we still don't have rr, use fallback
    if rr is None:
        rr = 50.0
        curiosity = 50.0
        logger.warning(f"[RR-Norm] {trait_id}: final fallback rr=50.0")

    # Update node dict with normalized values
    node_dict["rr"] = rr
    node_dict["curiosity"] = curiosity

    # Ensure rr_meta exists (for provenance)
    if "rr_meta" not in node_dict:
        node_dict["rr_meta"] = {
            "rr_raw": rr_score,
            "scale": "0_1000" if (rr_score and rr_score > 100) else "0_100",
            "source": "adapter",
            "trait_id": trait_id,
            "user_id": user_id
        }

    return BeliefNode(**node_dict)


def normalize_belief_graph(graph: BeliefGraph, user_id: str) -> BeliefGraph:
    """
    Normalize all belief nodes in a graph for API egress.

    Args:
        graph: Belief graph
        user_id: User identifier

    Returns:
        Graph with normalized RR/Curiosity values
    """
    # Normalize all nodes
    normalized_nodes = [
        normalize_belief_node(node, user_id) for node in graph.nodes
    ]

    # Create new graph with normalized nodes
    graph_dict = graph.model_dump()
    graph_dict["nodes"] = normalized_nodes  # Keep as BeliefNode objects

    logger.info(f"Egress normalization applied: {len(normalized_nodes)} nodes processed for user {user_id}")

    return BeliefGraph(**graph_dict)


def normalize_trait_dict(trait: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Normalize RR/Curiosity in a trait dictionary (e.g., from resolved.json) - Phase 10.2 with preference.

    Priority (when RR_PREFER_REFERENCE_OVER_SCORE=true):
    0. If UCN present and REFERENCE_POP_ENABLED → use reference (archive rr_score in metadata)

    Fallback Guards:
    1. If rr > 100 → assume 0-1000 scale, divide by 10, recompute curiosity
    2. If rr=null and rr_score present → derive using adapter
    3. If curiosity present but rr missing → compute rr = 100 - curiosity
    4. If curiosity ≠ 100 - rr → correct and log mismatch

    Args:
        trait: Trait dictionary with possible rr_score field
        user_id: User identifier

    Returns:
        Normalized trait dict with rr (0-100), curiosity (0-100), rr_meta
    """
    trait_id = trait.get("trait_id", "unknown")
    rr = trait.get("rr")
    rr_score = trait.get("rr_score")
    curiosity = trait.get("curiosity")
    ucn = trait.get("ucn")

    # Track legacy rr_score for lineage
    legacy_rr_score = rr_score
    method = None

    # Priority 0: Prefer reference over rr_score when UCN available
    if RR_PREFER_REFERENCE_OVER_SCORE and REFERENCE_POP_ENABLED and ucn is not None:
        # Normalize UCN to [0,1] range if needed (legacy data may use 0-100 or 0-1000 scales)
        ucn_raw = ucn if isinstance(ucn, (int, float)) else None
        ucn_norm = None

        if ucn_raw is not None:
            if ucn_raw > 100.0:
                # Assume 0-1000 scale (e.g., ucn=740 → 0.74)
                ucn_norm = ucn_raw / 1000.0
                logger.debug(f"[RR] egress normalized UCN {ucn_raw:.2f} → {ucn_norm:.4f} (0-1000 scale) for {trait_id}")
            elif ucn_raw > 1.0:
                # Assume 0-100 percent scale (e.g., ucn=80 → 0.80, ucn=5 → 0.05)
                ucn_norm = ucn_raw / 100.0
                logger.debug(f"[RR] egress normalized UCN {ucn_raw:.2f} → {ucn_norm:.4f} (0-100 scale) for {trait_id}")
            else:
                # Already normalized [0,1]
                ucn_norm = ucn_raw

        # Use reference population regardless of rr/rr_score presence
        normalized = rr_to_percentile(
            rr_raw=ucn_norm,
            rr_scale="reference_percentile",
            trait_id=trait_id,
            user_id=user_id,
            use_reference=True
        )
        rr = normalized["rr"]
        curiosity = normalized["curiosity"]
        trait["rr_meta"] = normalized["rr_meta"]

        # Add legacy_rr_score and method to rr_meta
        trait["rr_meta"]["legacy_rr_score"] = legacy_rr_score
        trait["rr_meta"]["method"] = "reference"

        logger.info(
            f"[RR-Norm] {trait_id}: using reference (prefer over rr_score={legacy_rr_score}) → rr={rr:.2f}"
        )
        method = "reference"

    # Guard 1: If rr > 100, assume legacy 0-1000 scale
    elif rr is not None and rr > 100:
        logger.warning(f"[RR-Norm] {trait_id}: rr={rr:.2f} > 100, adapting from 0-1000 scale")
        rr = rr / 10.0
        curiosity = 100.0 - rr
        method = "legacy_score"

    # Guard 2: If rr=null but rr_score present, derive using adapter
    elif rr is None and rr_score is not None:
        scale = "0_1000" if rr_score > 100 else "0_100"
        normalized = rr_to_percentile(
            rr_raw=rr_score,
            rr_scale=scale,
            trait_id=trait_id,
            user_id=user_id
        )
        rr = normalized["rr"]
        curiosity = normalized["curiosity"]
        trait["rr_meta"] = normalized["rr_meta"]
        trait["rr_meta"]["legacy_rr_score"] = legacy_rr_score
        trait["rr_meta"]["method"] = "legacy_score"
        logger.info(f"[RR-Norm] {trait_id}: filled rr from rr_score={rr_score:.2f} → rr={rr:.2f}")
        method = "legacy_score"

    # Guard 3: If curiosity present but rr missing, compute rr = 100 - curiosity
    elif rr is None and curiosity is not None:
        rr = 100.0 - curiosity
        logger.info(f"[RR-Norm] {trait_id}: filled rr from curiosity={curiosity:.2f} → rr={rr:.2f}")
        method = "curiosity_inverse"

    # Guard 4: If neither RR nor rr_score but UCN present, derive from reference pop (fallback when prefer=false)
    elif rr is None and rr_score is None and ucn is not None:
        if REFERENCE_POP_ENABLED:
            # Normalize UCN to [0,1] range if needed
            ucn_raw = ucn if isinstance(ucn, (int, float)) else None
            ucn_norm = None

            if ucn_raw is not None:
                if ucn_raw > 100.0:
                    # Assume 0-1000 scale
                    ucn_norm = ucn_raw / 1000.0
                    logger.debug(f"[RR] egress normalized UCN {ucn_raw:.2f} → {ucn_norm:.4f} (0-1000 scale) for {trait_id}")
                elif ucn_raw > 1.0:
                    # Assume 0-100 percent scale
                    ucn_norm = ucn_raw / 100.0
                    logger.debug(f"[RR] egress normalized UCN {ucn_raw:.2f} → {ucn_norm:.4f} (0-100 scale) for {trait_id}")
                else:
                    # Already normalized [0,1]
                    ucn_norm = ucn_raw

            normalized = rr_to_percentile(
                rr_raw=ucn_norm,
                rr_scale="reference_percentile",
                trait_id=trait_id,
                user_id=user_id,
                use_reference=True
            )
            rr = normalized["rr"]
            curiosity = normalized["curiosity"]
            trait["rr_meta"] = normalized["rr_meta"]
            trait["rr_meta"]["legacy_rr_score"] = None
            trait["rr_meta"]["method"] = "reference"
            logger.info(f"[RR-Norm] {trait_id}: derived rr from reference pop (UCN present) → rr={rr:.2f}")
            method = "reference"
        else:
            # Fallback: no RR available
            rr = 50.0
            curiosity = 50.0
            logger.warning(f"[RR-Norm] {trait_id}: no RR/rr_score, using fallback rr=50.0")
            method = "fallback"

    # Guard 5: Ensure curiosity = 100 - rr (correct any mismatch)
    if rr is not None and curiosity is not None:
        expected_curiosity = 100.0 - rr
        if abs(curiosity - expected_curiosity) > 0.01:
            logger.warning(
                f"[RR-Norm] {trait_id}: curiosity mismatch: "
                f"curiosity={curiosity:.2f}, expected={expected_curiosity:.2f} (from rr={rr:.2f}), correcting"
            )
            curiosity = expected_curiosity

    # If we still don't have rr, return unchanged or with fallback
    if rr is None:
        if "rr_score" in trait or "rr" in trait or "curiosity" in trait:
            rr = 50.0
            curiosity = 50.0
            logger.warning(f"[RR-Norm] {trait_id}: final fallback rr=50.0")
            method = "fallback"
        else:
            # No RR-related fields, return unchanged
            return trait

    # Update trait dict with normalized values
    trait["rr"] = rr
    trait["curiosity"] = curiosity

    # Ensure rr_meta exists
    if "rr_meta" not in trait:
        trait["rr_meta"] = {
            "rr_raw": rr_score,
            "scale": "0_1000" if (rr_score and rr_score > 100) else "0_100",
            "source": "adapter",
            "trait_id": trait_id,
            "user_id": user_id,
            "legacy_rr_score": legacy_rr_score,
            "method": method or "fallback"
        }
    elif "method" not in trait["rr_meta"]:
        # Add method if not already set
        trait["rr_meta"]["method"] = method or "unknown"

    return trait
