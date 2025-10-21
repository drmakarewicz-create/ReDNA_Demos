"""
Graph storage abstraction for Cross-Trait Reasoning Graphs (Phase 8)

Provides file-backed storage (JSONL) with protocol for future graph DB swap.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Protocol
import json
from datetime import datetime
import logging

from .schemas import (
    OntologyGraph,
    OntologyNode,
    OntologyEdge,
    BeliefGraph,
    BeliefNode,
    BeliefEdge,
    WhyCard,
)

logger = logging.getLogger(__name__)

# ============================================================================
# STORAGE PROTOCOL (for future graph DB swap)
# ============================================================================


class GraphStorage(Protocol):
    """Abstract interface for graph storage."""

    def load_ontology(self) -> OntologyGraph:
        """Load the system ontology graph."""
        ...

    def save_ontology(self, graph: OntologyGraph) -> None:
        """Persist ontology graph."""
        ...

    def load_user_graph(self, user_id: str) -> BeliefGraph:
        """Load user's belief graph."""
        ...

    def save_user_graph(self, graph: BeliefGraph) -> None:
        """Persist user's belief graph."""
        ...

    def append_user_graph_update(
        self,
        user_id: str,
        nodes: Optional[List[BeliefNode]] = None,
        edges: Optional[List[BeliefEdge]] = None,
    ) -> None:
        """Append updates to user graph (JSONL pattern)."""
        ...

    def save_why_card(self, why_card: WhyCard) -> None:
        """Save Why-Card to user's why_cards.jsonl."""
        ...

    def load_why_cards(self, user_id: str, trait_id: Optional[str] = None) -> List[WhyCard]:
        """Load Why-Cards for user (optionally filtered by trait_id)."""
        ...

    def get_why_card_by_id(self, user_id: str, why_card_id: str) -> Optional[WhyCard]:
        """Get specific Why-Card by ID."""
        ...


# ============================================================================
# FILE-BACKED IMPLEMENTATION (MVP)
# ============================================================================


class FileGraphStorage:
    """File-backed graph storage (JSONL for append-only updates)."""

    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)
        self.ontology_dir = self.data_root / "ontology"
        self.users_dir = self.data_root / "users"
        self.ontology_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized FileGraphStorage at {self.data_root}")

    # Ontology methods

    def load_ontology(self) -> OntologyGraph:
        """Load ontology from seed + JSONL updates."""
        seed_path = self.ontology_dir / "seed_ontology.json"
        updates_path = self.ontology_dir / "ontology_v1.jsonl"

        # Start with seed
        if not seed_path.exists():
            logger.warning("Seed ontology not found, returning empty graph")
            return OntologyGraph()

        try:
            with open(seed_path) as f:
                data = json.load(f)

            graph = OntologyGraph(
                version=data.get("version", "1.0"),
                nodes=[OntologyNode(**n) for n in data.get("nodes", [])],
                edges=[OntologyEdge(**e) for e in data.get("edges", [])],
            )

            logger.info(
                f"Loaded seed ontology: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
            )

            # Apply updates if any
            if updates_path.exists():
                with open(updates_path) as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            update = json.loads(line)
                            if update["type"] == "add_node":
                                graph.nodes.append(OntologyNode(**update["node"]))
                            elif update["type"] == "add_edge":
                                graph.edges.append(OntologyEdge(**update["edge"]))
                        except Exception as e:
                            logger.error(
                                f"Failed to apply ontology update line {line_num}: {e}"
                            )

                logger.info(
                    f"Applied updates from {updates_path}: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
                )

            return graph

        except Exception as e:
            logger.error(f"Failed to load ontology: {e}")
            return OntologyGraph()

    def save_ontology(self, graph: OntologyGraph) -> None:
        """Save full ontology (overwrites seed)."""
        seed_path = self.ontology_dir / "seed_ontology.json"
        try:
            with open(seed_path, "w") as f:
                json.dump(
                    {
                        "version": graph.version,
                        "created_at": graph.last_updated.isoformat(),
                        "nodes": [n.model_dump(mode="json") for n in graph.nodes],
                        "edges": [e.model_dump(mode="json") for e in graph.edges],
                    },
                    f,
                    indent=2,
                )
            logger.info(
                f"Saved ontology: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
            )
        except Exception as e:
            logger.error(f"Failed to save ontology: {e}")
            raise

    def append_ontology_update(
        self,
        node: Optional[OntologyNode] = None,
        edge: Optional[OntologyEdge] = None,
    ) -> None:
        """Append update to JSONL (for versioning)."""
        updates_path = self.ontology_dir / "ontology_v1.jsonl"
        try:
            with open(updates_path, "a") as f:
                if node:
                    f.write(
                        json.dumps(
                            {"type": "add_node", "node": node.model_dump(mode="json")}
                        )
                        + "\n"
                    )
                    logger.debug(f"Appended ontology node: {node.node_id}")
                if edge:
                    f.write(
                        json.dumps(
                            {"type": "add_edge", "edge": edge.model_dump(mode="json")}
                        )
                        + "\n"
                    )
                    logger.debug(f"Appended ontology edge: {edge.edge_id}")
        except Exception as e:
            logger.error(f"Failed to append ontology update: {e}")
            raise

    # User graph methods

    def load_user_graph(self, user_id: str) -> BeliefGraph:
        """Load user's belief graph from JSONL."""
        user_dir = self.users_dir / user_id
        graph_path = user_dir / "belief_graph.jsonl"

        if not graph_path.exists():
            logger.debug(f"No belief graph for user {user_id}, returning empty")
            return BeliefGraph(user_id=user_id)

        nodes = []
        edges = []
        node_map = {}  # node_id -> index in nodes list

        try:
            with open(graph_path) as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        update = json.loads(line)
                        if update["type"] == "add_node":
                            node = BeliefNode(**update["node"])
                            # Check if node_id already exists (later occurrence updates earlier)
                            if node.node_id in node_map:
                                idx = node_map[node.node_id]
                                nodes[idx] = node  # Replace existing node
                            else:
                                nodes.append(node)
                                node_map[node.node_id] = len(nodes) - 1
                        elif update["type"] == "add_edge":
                            edges.append(BeliefEdge(**update["edge"]))
                        elif update["type"] == "update_node":
                            # Find and update existing node
                            node_id = update["node"]["node_id"]
                            if node_id in node_map:
                                idx = node_map[node_id]
                                nodes[idx] = BeliefNode(**update["node"])
                            else:
                                logger.warning(
                                    f"Update for unknown node {node_id} at line {line_num}"
                                )
                    except Exception as e:
                        logger.error(
                            f"Failed to parse belief graph line {line_num} for user {user_id}: {e}"
                        )

            logger.info(
                f"Loaded belief graph for {user_id}: {len(nodes)} nodes, {len(edges)} edges"
            )
            return BeliefGraph(user_id=user_id, nodes=nodes, edges=edges)

        except Exception as e:
            logger.error(f"Failed to load belief graph for {user_id}: {e}")
            return BeliefGraph(user_id=user_id)

    def save_user_graph(self, graph: BeliefGraph) -> None:
        """Overwrite user graph (for migrations)."""
        user_dir = self.users_dir / graph.user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        graph_path = user_dir / "belief_graph.jsonl"

        try:
            # Write full graph as series of adds
            with open(graph_path, "w") as f:
                for node in graph.nodes:
                    f.write(
                        json.dumps(
                            {"type": "add_node", "node": node.model_dump(mode="json")}
                        )
                        + "\n"
                    )
                for edge in graph.edges:
                    f.write(
                        json.dumps(
                            {"type": "add_edge", "edge": edge.model_dump(mode="json")}
                        )
                        + "\n"
                    )
            logger.info(
                f"Saved belief graph for {graph.user_id}: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
            )
        except Exception as e:
            logger.error(f"Failed to save belief graph for {graph.user_id}: {e}")
            raise

    def append_user_graph_update(
        self,
        user_id: str,
        nodes: Optional[List[BeliefNode]] = None,
        edges: Optional[List[BeliefEdge]] = None,
    ) -> None:
        """Append updates to user's graph (efficient)."""
        user_dir = self.users_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        graph_path = user_dir / "belief_graph.jsonl"

        # Load existing graph to detect updates vs adds
        existing_node_ids = set()
        if graph_path.exists():
            try:
                with open(graph_path) as f:
                    for line in f:
                        try:
                            update = json.loads(line)
                            if update["type"] in ("add_node", "update_node"):
                                existing_node_ids.add(update["node"]["node_id"])
                        except Exception:
                            pass
            except Exception:
                pass

        try:
            with open(graph_path, "a") as f:
                for node in nodes or []:
                    # Use update_node if node already exists, add_node otherwise
                    operation_type = "update_node" if node.node_id in existing_node_ids else "add_node"
                    f.write(
                        json.dumps(
                            {"type": operation_type, "node": node.model_dump(mode="json")}
                        )
                        + "\n"
                    )
                    # Track newly added nodes
                    existing_node_ids.add(node.node_id)

                for edge in edges or []:
                    f.write(
                        json.dumps(
                            {"type": "add_edge", "edge": edge.model_dump(mode="json")}
                        )
                        + "\n"
                    )
            logger.debug(
                f"Appended to belief graph for {user_id}: {len(nodes or [])} nodes, {len(edges or [])} edges"
            )
        except Exception as e:
            logger.error(f"Failed to append to belief graph for {user_id}: {e}")
            raise

    # Why-Card methods

    def save_why_card(self, why_card: WhyCard) -> None:
        """Save Why-Card to user's why_cards.jsonl (append-only)."""
        user_dir = self.users_dir / why_card.user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        why_cards_path = user_dir / "why_cards.jsonl"

        try:
            with open(why_cards_path, "a") as f:
                f.write(json.dumps(why_card.model_dump(mode="json")) + "\n")
            logger.debug(f"Saved Why-Card {why_card.id} for {why_card.user_id}/{why_card.trait_id}")
        except Exception as e:
            logger.error(f"Failed to save Why-Card {why_card.id}: {e}")
            raise

    def load_why_cards(self, user_id: str, trait_id: Optional[str] = None) -> List[WhyCard]:
        """Load Why-Cards for user (optionally filtered by trait_id)."""
        user_dir = self.users_dir / user_id
        why_cards_path = user_dir / "why_cards.jsonl"

        if not why_cards_path.exists():
            logger.debug(f"No Why-Cards found for user {user_id}")
            return []

        cards = []
        try:
            with open(why_cards_path) as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        card_data = json.loads(line)
                        card = WhyCard(**card_data)
                        if trait_id is None or card.trait_id == trait_id:
                            cards.append(card)
                    except Exception as e:
                        logger.error(
                            f"Failed to parse Why-Card line {line_num} for user {user_id}: {e}"
                        )

            logger.info(f"Loaded {len(cards)} Why-Cards for {user_id}" + (f" (trait={trait_id})" if trait_id else ""))
            return cards

        except Exception as e:
            logger.error(f"Failed to load Why-Cards for {user_id}: {e}")
            return []

    def get_why_card_by_id(self, user_id: str, why_card_id: str) -> Optional[WhyCard]:
        """Get specific Why-Card by ID."""
        all_cards = self.load_why_cards(user_id)
        return next((card for card in all_cards if card.id == why_card_id), None)


# ============================================================================
# FACTORY
# ============================================================================


def get_graph_storage() -> GraphStorage:
    """Get graph storage instance (env-configurable for future DB swap)."""
    import os
    from pathlib import Path

    storage_type = os.getenv("GRAPH_STORAGE", "file")
    data_root = Path(os.getenv("CORE_DATA_ROOT", "data"))

    if storage_type == "file":
        return FileGraphStorage(data_root)
    else:
        raise ValueError(f"Unknown graph storage type: {storage_type}")
