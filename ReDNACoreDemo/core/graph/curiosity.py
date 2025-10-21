"""
Graph-aware curiosity question selection (Phase 8 Stage 4, Phase 10.1 LLM Enhancement).

Chooses next question based on:
- Belief gaps (high uncertainty traits)
- Ontology neighbors (traits that correlate/support)
- User graph coverage
- LLM-generated natural language questions (Phase 10.1)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .schemas import BeliefGraph, OntologyGraph, NextQuestionResponse, BeliefNode
from .storage import get_graph_storage
from ..llm.provider import LLMClient

logger = logging.getLogger(__name__)

# Configuration flags
WHYCARD_USE_LLM = os.getenv("WHYCARD_USE_LLM", "false").lower() in ("true", "1", "yes")
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "llama3:8b"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "200"))


def generate_llm_question(
    user_id: str,
    target_trait_id: str,
    graph_context: List[Dict[str, Any]],
    timeout: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    Generate a natural-language curiosity question using LLM (Phase 10.1).

    Args:
        user_id: User identifier
        target_trait_id: Trait ID to ask about
        graph_context: List of connected nodes with their RR/Curiosity scores
        timeout: LLM request timeout in seconds (default: 30)

    Returns:
        Dict with question_text, rationale, source:"LLM", or None on failure
    """
    try:
        client = LLMClient()

        # Check if Ollama is accessible
        if not client.health():
            logger.warning("[LLM Question] Ollama not accessible, falling back to deterministic")
            return None

        # Build trait context summary
        trait_name = _get_trait_display_name(target_trait_id)

        context_summary = []
        for node in graph_context[:5]:  # Limit to top 5 nodes
            node_trait = node.get("trait_id", "")
            node_name = _get_trait_display_name(node_trait)
            node_rr = node.get("rr", 50)
            node_curiosity = node.get("curiosity", 50)

            context_summary.append(
                f"- {node_name}: confidence {node_rr}%, curiosity {node_curiosity}%"
            )

        context_text = "\n".join(context_summary) if context_summary else "No existing traits"

        # Build system prompt
        system_prompt = (
            "You are the Head Coach AI, a conversational assistant helping users explore their traits. "
            "Using the following user traits and confidence levels, write ONE clarifying question that helps "
            f"refine understanding of {trait_name}. "
            "Avoid yes/no questions; aim for conversational curiosity that encourages the user to share details."
        )

        user_prompt = (
            f"Target trait: {trait_name}\n\n"
            f"Known traits:\n{context_text}\n\n"
            f"Write a single question (no preamble, just the question) to help understand the user's {trait_name}."
        )

        # Call LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = client.chat(
            messages=messages,
            model=LLM_MODEL,
            temperature=0.7,
            options={
                "num_predict": LLM_MAX_TOKENS,
            }
        )

        # Extract question text
        question_text = response.get("message", {}).get("content", "").strip()

        if not question_text:
            logger.warning("[LLM Question] Empty response from LLM")
            return None

        # Clean up question (remove quotes, trim)
        question_text = question_text.strip('"\'')

        # Build rationale
        rationale = (
            f"LLM-generated question for {trait_name} based on "
            f"{len(graph_context)} connected traits"
        )

        return {
            "question_text": question_text,
            "rationale": rationale,
            "source": "LLM",
            "target_trait_id": target_trait_id,
            "model": LLM_MODEL,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"[LLM Question] Failed to generate question: {e}", exc_info=True)
        return None


def choose_next_question(
    user_id: str,
    strategy: str = "auto",
    max_candidates: int = 5
) -> NextQuestionResponse:
    """
    Choose next curiosity question using graph traversal + LLM (Phase 10.1).

    Stage 4 MVP: Uses deterministic heuristics (gaps + ontology).
    Phase 10.1: Can use LLM to generate natural language questions when WHYCARD_USE_LLM=true.

    Args:
        user_id: User ID
        strategy: "breadth" (explore new), "depth" (refine existing), "auto"
        max_candidates: Max number of candidates to consider

    Returns:
        NextQuestionResponse with question, rationale, and metadata
    """
    storage = get_graph_storage()
    user_graph = storage.load_user_graph(user_id)
    ontology = storage.load_ontology()

    # Find candidates based on strategy
    candidates = _find_question_candidates(
        user_graph, ontology, strategy, max_candidates
    )

    if not candidates:
        # Fallback: generic open question
        return NextQuestionResponse(
            question_text="What's something interesting about yourself that I don't know yet?",
            target_trait_id="unknown",
            rationale="No specific gaps detected in belief graph",
            graph_path=[],
            confidence=0.3
        )

    # Select best candidate (Stage 4: highest priority, Phase 10.1: LLM generation)
    best = candidates[0]
    trait_id, question, rationale, priority, path = best

    # Phase 10.1: Try LLM generation if enabled
    if WHYCARD_USE_LLM:
        # Check cache first
        cached_question = _check_question_cache(user_id, trait_id)
        if cached_question:
            logger.info(f"[LLM Question] Using cached question for {trait_id}")
            return NextQuestionResponse(
                question_text=cached_question["question_text"],
                target_trait_id=trait_id,
                rationale=f"{cached_question.get('rationale', 'Cached LLM question')} (cached)",
                graph_path=path,
                confidence=priority
            )

        # Build graph context from user's belief graph
        graph_context = []
        for node in user_graph.get_trait_nodes()[:10]:  # Top 10 traits
            if node.trait_id:
                graph_context.append({
                    "trait_id": node.trait_id,
                    "rr": node.rr if hasattr(node, "rr") and node.rr is not None else 50,
                    "curiosity": node.curiosity if hasattr(node, "curiosity") and node.curiosity is not None else 50,
                })

        # Try LLM generation
        llm_result = generate_llm_question(user_id, trait_id, graph_context)

        if llm_result:
            logger.info(f"[LLM Question] Generated: {llm_result['question_text'][:50]}...")

            # Cache the question
            _cache_question(user_id, trait_id, llm_result)

            return NextQuestionResponse(
                question_text=llm_result["question_text"],
                target_trait_id=trait_id,
                rationale=llm_result["rationale"],
                graph_path=path,
                confidence=priority
            )
        else:
            logger.warning(f"[LLM Question] LLM generation failed, using deterministic fallback")

    # Fallback to deterministic question
    return NextQuestionResponse(
        question_text=question,
        target_trait_id=trait_id,
        rationale=rationale,
        graph_path=path,
        confidence=priority
    )


def _find_question_candidates(
    user_graph: BeliefGraph,
    ontology: OntologyGraph,
    strategy: str,
    max_candidates: int
) -> List[Tuple[str, str, str, float, List[str]]]:
    """
    Find candidate questions based on belief gaps and ontology neighbors.

    Returns:
        List of (trait_id, question_text, rationale, priority, graph_path) tuples
        sorted by priority (descending)
    """
    candidates = []

    # Strategy 1: High-uncertainty traits (depth)
    if strategy in ("depth", "auto"):
        trait_nodes = user_graph.get_trait_nodes()
        for node in trait_nodes:
            if node.ucn and node.ucn.get("u", 0) > 0.6:
                # High uncertainty - ask follow-up
                trait_name = _get_trait_display_name(node.trait_id or "")
                priority = node.ucn.get("u", 0) * node.ucn.get("c", 0.5)  # u * c

                question = f"Can you tell me more about your {trait_name}?"
                rationale = f"High uncertainty ({node.ucn.get('u', 0):.2f}) on existing trait"

                candidates.append((
                    node.trait_id or "",
                    question,
                    rationale,
                    priority,
                    [node.node_id]
                ))

    # Strategy 2: Ontology neighbors (breadth)
    if strategy in ("breadth", "auto"):
        # Get traits user already has
        user_trait_ids = set(
            n.trait_id for n in user_graph.get_trait_nodes() if n.trait_id
        )

        # Find ontology neighbors via suggests_question edges
        for edge in ontology.edges:
            if edge.edge_type == "suggests_question":
                from_trait = edge.from_node
                to_trait = edge.to_node

                # Check if user has from_trait but not to_trait
                from_node = ontology.get_node_by_id(from_trait)
                to_node = ontology.get_node_by_id(to_trait)

                if not from_node or not to_node:
                    continue

                from_trait_id = from_node.trait_id
                to_trait_id = to_node.trait_id

                if from_trait_id in user_trait_ids and to_trait_id not in user_trait_ids:
                    # User has from_trait, missing to_trait - good candidate
                    to_name = _get_trait_display_name(to_trait_id or "")
                    priority = edge.weight * 0.7  # Ontology suggestions slightly lower than gaps

                    question = f"What about your {to_name}?"
                    rationale = (
                        f"Exploring {to_trait_id} based on known {from_trait_id} "
                        f"(ontology suggests relationship)"
                    )

                    candidates.append((
                        to_trait_id or "",
                        question,
                        rationale,
                        priority,
                        [from_trait, edge.edge_id, to_trait]
                    ))

    # Strategy 3: Coverage gaps (auto fallback)
    if strategy == "auto" and len(candidates) < 2:
        # Find common traits user doesn't have yet
        common_traits = _get_common_traits(ontology)
        user_trait_ids = set(
            n.trait_id for n in user_graph.get_trait_nodes() if n.trait_id
        )

        for trait_id in common_traits:
            if trait_id not in user_trait_ids:
                trait_name = _get_trait_display_name(trait_id)
                question = f"What can you tell me about your {trait_name}?"
                rationale = f"Exploring common trait gap: {trait_id}"
                priority = 0.4  # Lower priority than uncertainty/ontology

                candidates.append((
                    trait_id,
                    question,
                    rationale,
                    priority,
                    []
                ))

                if len(candidates) >= max_candidates:
                    break

    # Sort by priority (descending) and limit
    candidates.sort(key=lambda x: x[3], reverse=True)
    return candidates[:max_candidates]


def _get_trait_display_name(trait_id: str) -> str:
    """Extract human-readable name from trait_id."""
    if not trait_id:
        return "preferences"

    # Strip namespace (e.g., "PaDNA.Chronotype" → "Chronotype")
    parts = trait_id.split(".")
    name = parts[-1] if parts else trait_id

    # Convert CamelCase to space-separated
    import re
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

    return name.lower()


def _get_common_traits(ontology: OntologyGraph) -> List[str]:
    """
    Get list of common traits to ask about.

    Stage 4: Hard-coded common traits.
    Stage 4.1+: Could use ontology metadata or population frequency.
    """
    common = []

    # Extract trait_ids from ontology nodes
    for node in ontology.nodes:
        if node.node_type == "trait" and node.trait_id:
            # Heuristic: traits in "Behavioral" or "Physical" categories are common
            if node.category in ("Behavioral", "Physical", "Preferences"):
                common.append(node.trait_id)

    # Fallback: well-known trait IDs
    if not common:
        common = [
            "PaDNA.Chronotype",
            "PaDNA.EyeDNA.IrisColor",
            "PaDNA.Height",
            "BehaviorDNA.Exercise.Frequency",
            "BehaviorDNA.Diet.Type",
        ]

    return common[:10]  # Limit to top 10


def _get_question_cache_path(user_id: str) -> Path:
    """Get path to user's question cache file."""
    from ..storage import ensure_dirs_for_user

    user_dirs = ensure_dirs_for_user(user_id)
    cache_dir = Path(user_dirs["udir"]) / "question_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "llm_questions.jsonl"


def _check_question_cache(user_id: str, trait_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a question for this trait is already cached.

    Returns cached question if trait hasn't changed, None otherwise.
    """
    try:
        cache_path = _get_question_cache_path(user_id)
        if not cache_path.exists():
            return None

        # Load cache
        cache_lines = cache_path.read_text(encoding="utf-8").strip().split("\n")

        # Find latest entry for this trait
        for line in reversed(cache_lines):
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                if entry.get("target_trait_id") == trait_id:
                    # Found cached question for this trait
                    return entry
            except json.JSONDecodeError:
                continue

        return None

    except Exception as e:
        logger.warning(f"[LLM Question] Failed to check cache: {e}")
        return None


def _cache_question(user_id: str, trait_id: str, llm_result: Dict[str, Any]) -> None:
    """
    Cache an LLM-generated question for this trait.

    Appends to JSONL cache file.
    """
    try:
        cache_path = _get_question_cache_path(user_id)

        # Prepare cache entry
        cache_entry = {
            "target_trait_id": trait_id,
            "question_text": llm_result["question_text"],
            "rationale": llm_result["rationale"],
            "source": llm_result["source"],
            "model": llm_result.get("model", LLM_MODEL),
            "timestamp": llm_result.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }

        # Append to cache
        with cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cache_entry) + "\n")

        logger.debug(f"[LLM Question] Cached question for {trait_id}")

    except Exception as e:
        logger.warning(f"[LLM Question] Failed to cache question: {e}")


# Export public API
__all__ = ["choose_next_question", "generate_llm_question"]
