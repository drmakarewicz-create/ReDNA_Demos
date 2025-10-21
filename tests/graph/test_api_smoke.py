from __future__ import annotations

from ReDNACoreDemo.core.graph.belief import on_trait_promotion
from ReDNACoreDemo.core.graph.schemas import (
    BeliefGraph,
    BeliefNode,
    BeliefEdge,
    OntologyGraph,
    OntologyNode,
)
from ReDNACoreDemo.core.graph.storage import FileGraphStorage


def test_promotion_creates_observation_and_evidence(tmp_path, monkeypatch):
    """Test that on_trait_promotion creates observation node and evidence edge."""
    # Patch storage to use tmp_path
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    # Call on_trait_promotion with current API signature
    result = on_trait_promotion(
        user_id="smoke_user",
        trait_id="BehaviorDNA.Sleep.Chronotype",
        value="Morning",
        rr_score=820.0,
        ucn={"u": 0.2, "c": 0.7, "n": 0.1},
        observation_text="I wake up at 5AM feeling most alert before noon.",
        observation_source="unit_test",
    )

    # Verify result structure
    assert result["status"] == "ok"
    assert "observation_node_id" in result
    assert "trait_node_id" in result
    assert "edge_id" in result

    # Load graph and verify structure
    storage = FileGraphStorage(tmp_path)
    graph = storage.load_user_graph("smoke_user")

    obs_nodes = [n for n in graph.nodes if n.node_type == "observation"]
    trait_nodes = [
        n
        for n in graph.nodes
        if n.node_type == "trait_belief" and n.trait_id == "BehaviorDNA.Sleep.Chronotype"
    ]
    evidence_edges = [e for e in graph.edges if e.edge_type == "evidence_for"]

    assert len(obs_nodes) == 1, "Should have exactly 1 observation node"
    assert len(trait_nodes) == 1, "Should have exactly 1 trait belief node"
    assert len(evidence_edges) == 1, "Should have exactly 1 evidence edge"

    edge = evidence_edges[0]
    assert edge.from_node == obs_nodes[0].node_id
    assert edge.to_node == trait_nodes[0].node_id
    assert edge.source == "promotion"


def test_graph_loads_from_existing_jsonl(tmp_path):
    """
    Test that a user graph persisted to belief_graph.jsonl can be loaded after restart.

    This verifies the fix for: "GET /core/graph/user/{user_id} should never return 404
    if belief_graph.jsonl exists."
    """
    storage = FileGraphStorage(tmp_path)

    # Create a user with some graph data
    user_id = "persistent_user"
    obs_node = BeliefNode(
        node_type="observation",
        observation_text="I prefer mornings",
        observation_source="test",
    )
    trait_node = BeliefNode(
        node_type="trait_belief",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=700.0,
        ucn={"u": 0.3, "c": 0.6, "n": 0.5},
    )
    evidence_edge = BeliefEdge(
        edge_type="evidence_for",
        from_node=obs_node.node_id,
        to_node=trait_node.node_id,
        weight=0.7,
        confidence=0.6,
        source="promotion",  # Must be one of: promotion, contradiction_detected, llm_inference, holistic
    )

    # Persist to JSONL
    storage.append_user_graph_update(
        user_id, nodes=[obs_node, trait_node], edges=[evidence_edge]
    )

    # Verify file exists
    graph_path = tmp_path / "users" / user_id / "belief_graph.jsonl"
    assert graph_path.exists(), "belief_graph.jsonl should exist after append"

    # Simulate restart: create NEW storage instance (no in-memory cache)
    fresh_storage = FileGraphStorage(tmp_path)

    # Load graph (should replay JSONL, not return empty/404)
    loaded_graph = fresh_storage.load_user_graph(user_id)

    # Verify all data is restored
    assert len(loaded_graph.nodes) == 2, "Should load 2 nodes from JSONL"
    assert len(loaded_graph.edges) == 1, "Should load 1 edge from JSONL"

    # Verify node types
    obs_nodes = [n for n in loaded_graph.nodes if n.node_type == "observation"]
    trait_nodes = [n for n in loaded_graph.nodes if n.node_type == "trait_belief"]
    assert len(obs_nodes) == 1, "Should have 1 observation node"
    assert len(trait_nodes) == 1, "Should have 1 trait node"

    # Verify trait content
    trait = trait_nodes[0]
    assert trait.trait_id == "PaDNA.Chronotype"
    assert trait.value == "Morning Lark"
    assert trait.rr_score == 700.0

    # Verify edge connectivity
    edge = loaded_graph.edges[0]
    assert edge.from_node == obs_nodes[0].node_id
    assert edge.to_node == trait_nodes[0].node_id
