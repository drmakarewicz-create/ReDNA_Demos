"""
Phase 8 Stage 3 Integration Test

Tests end-to-end flow: Evidence → Trait Resolution → Belief Graph Update
"""

import pytest
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from ReDNACoreDemo.core.resolver.impl import resolve_roundtrip
from ReDNACoreDemo.core.graph.storage import get_graph_storage
from ReDNACoreDemo.core.graph.belief import on_trait_promotion, get_or_create_user_trait_node


@pytest.fixture(autouse=True)
def cleanup_test_users():
    """Clean up test user data before each test."""
    data_root = project_root / "data" / "users"
    test_users = ["test_stage3_user1", "test_stage3_user2", "test_stage3_user3"]

    for user_id in test_users:
        user_dir = data_root / user_id
        if user_dir.exists():
            shutil.rmtree(user_dir)

    yield  # Run test

    # Optional: cleanup after test too
    for user_id in test_users:
        user_dir = data_root / user_id
        if user_dir.exists():
            shutil.rmtree(user_dir)


def test_on_trait_promotion_creates_nodes_and_edge():
    """Test that on_trait_promotion creates observation, trait, and evidence edge."""
    user_id = "test_stage3_user1"

    # Call on_trait_promotion
    result = on_trait_promotion(
        user_id=user_id,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=720.0,
        ucn={"u": 0.3, "c": 0.6, "n": 0.7},
        observation_text="I wake up at 6am naturally every morning",
        observation_source="chat"
    )

    # Check result
    assert result["status"] == "ok"
    assert result["is_new_trait"] == True
    assert "observation_node_id" in result
    assert "trait_node_id" in result
    assert "edge_id" in result

    # Load graph from storage
    storage = get_graph_storage()
    graph = storage.load_user_graph(user_id)

    # Verify graph structure
    assert len(graph.nodes) == 2  # 1 observation + 1 trait
    assert len(graph.edges) == 1  # 1 evidence edge

    # Find nodes
    obs_node = None
    trait_node = None
    for node in graph.nodes:
        if node.node_type == "observation":
            obs_node = node
        elif node.node_type == "trait_belief":
            trait_node = node

    assert obs_node is not None
    assert trait_node is not None

    # Verify observation node
    assert obs_node.observation_text == "I wake up at 6am naturally every morning"
    assert obs_node.observation_source == "chat"

    # Verify trait node
    assert trait_node.trait_id == "PaDNA.Chronotype"
    assert trait_node.value == "Morning Lark"
    assert trait_node.rr_score == 720.0
    assert trait_node.ucn["u"] == 0.3
    assert trait_node.ucn["c"] == 0.6

    # Verify edge
    edge = graph.edges[0]
    assert edge.edge_type == "evidence_for"
    assert edge.from_node == obs_node.node_id
    assert edge.to_node == trait_node.node_id
    assert edge.weight == 0.72  # 720 / 1000
    assert edge.confidence == 0.6  # ucn.c
    assert edge.source == "promotion"

    print(f"✅ Test passed: Created {len(graph.nodes)} nodes and {len(graph.edges)} edge")


def test_second_promotion_reuses_trait_node():
    """Test that second promotion for same trait reuses the trait node."""
    user_id = "test_stage3_user2"

    # First promotion
    result1 = on_trait_promotion(
        user_id=user_id,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=700.0,
        ucn={"u": 0.4, "c": 0.5, "n": 0.6},
        observation_text="I prefer mornings",
        observation_source="chat"
    )

    assert result1["is_new_trait"] == True
    trait_node_id_1 = result1["trait_node_id"]

    # Second promotion (same trait, same value)
    result2 = on_trait_promotion(
        user_id=user_id,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",  # Same value
        rr_score=850.0,  # Higher RR
        ucn={"u": 0.2, "c": 0.7, "n": 0.8},
        observation_text="I love morning workouts",
        observation_source="chat"
    )

    assert result2["is_new_trait"] == False  # Should reuse
    assert result2["trait_node_id"] == trait_node_id_1  # Same node ID

    # Load graph
    storage = get_graph_storage()
    graph = storage.load_user_graph(user_id)

    # Verify: 2 observations, 1 trait (reused), 2 edges
    assert len([n for n in graph.nodes if n.node_type == "observation"]) == 2
    assert len([n for n in graph.nodes if n.node_type == "trait_belief"]) == 1
    assert len(graph.edges) == 2

    # Verify trait node was updated with new RR score
    trait_node = next(n for n in graph.nodes if n.node_type == "trait_belief")
    assert trait_node.rr_score == 850.0  # Updated
    assert trait_node.ucn["u"] == 0.2  # Updated

    print(f"✅ Test passed: Node reused, graph has {len(graph.nodes)} nodes, {len(graph.edges)} edges")


def test_resolve_roundtrip_triggers_graph_update():
    """Test that resolve_roundtrip automatically updates belief graph."""
    user_id = "test_stage3_user3"

    # Create evidence
    evidence = [
        {
            "trait_id": "PaDNA.Chronotype",
            "value": "Morning Lark",
            "text": "I naturally wake up at 5:30am",
            "source": "chat",
            "ts": datetime.now(timezone.utc).isoformat(),
            "ucn_prior": 0.3,
            "_reliability": 0.85
        }
    ]

    # Call resolve_roundtrip (should trigger graph update via hook)
    result = resolve_roundtrip(
        user_id=user_id,
        evidence=evidence,
        source="chat"
    )

    assert result["rr_ok"] == True or result["rr_ok"] == False  # Either is valid
    assert "resolved" in result

    # Check that belief graph was updated
    storage = get_graph_storage()
    graph = storage.load_user_graph(user_id)

    # Should have at least 1 observation and 1 trait
    assert len(graph.nodes) >= 2
    assert len(graph.edges) >= 1

    # Find trait node
    trait_node = next((n for n in graph.nodes if n.node_type == "trait_belief"), None)
    assert trait_node is not None
    assert trait_node.trait_id == "PaDNA.Chronotype"

    print(f"✅ Test passed: resolve_roundtrip triggered graph update ({len(graph.nodes)} nodes)")


def test_get_or_create_user_trait_node():
    """Test get_or_create_user_trait_node helper function."""
    from ReDNACoreDemo.core.graph.schemas import BeliefGraph

    # Empty graph
    graph = BeliefGraph(user_id="test_helper", version="1.0", nodes=[], edges=[])

    # Create new node
    node1, is_new1 = get_or_create_user_trait_node(
        graph=graph,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=700.0,
        ucn={"u": 0.3, "c": 0.5, "n": 0.6}
    )

    assert is_new1 == True
    assert node1.trait_id == "PaDNA.Chronotype"
    assert node1.value == "Morning Lark"
    assert node1.rr_score == 700.0

    # Add to graph
    graph.nodes.append(node1)

    # Reuse existing node (same trait, same value)
    node2, is_new2 = get_or_create_user_trait_node(
        graph=graph,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",  # Same value
        rr_score=850.0,  # Higher score
        ucn={"u": 0.2, "c": 0.6, "n": 0.7}
    )

    assert is_new2 == False  # Reused
    assert node2.node_id == node1.node_id  # Same node
    assert node2.rr_score == 850.0  # Updated

    # Different value (contradiction)
    node3, is_new3 = get_or_create_user_trait_node(
        graph=graph,
        trait_id="PaDNA.Chronotype",
        value="Night Owl",  # Different value
        rr_score=750.0,
        ucn={"u": 0.4, "c": 0.5, "n": 0.6}
    )

    assert is_new3 == True  # New node (contradiction)
    assert node3.node_id != node1.node_id  # Different node
    assert node3.value == "Night Owl"

    print("✅ Test passed: get_or_create_user_trait_node works correctly")


if __name__ == "__main__":
    print("Running Phase 8 Stage 3 Integration Tests...")
    print()

    try:
        test_get_or_create_user_trait_node()
        print()
        test_on_trait_promotion_creates_nodes_and_edge()
        print()
        test_second_promotion_reuses_trait_node()
        print()
        test_resolve_roundtrip_triggers_graph_update()
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
