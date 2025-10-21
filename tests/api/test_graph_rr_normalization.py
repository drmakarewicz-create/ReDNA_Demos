"""
Regression tests for RR normalization in graph API (Phase 9).
"""

import pytest
from fastapi.testclient import TestClient
from ReDNACoreDemo.core.api import build_app
from ReDNACoreDemo.core.graph.schemas import BeliefGraph, BeliefNode
from ReDNACoreDemo.core.graph.storage import get_graph_storage


@pytest.fixture
def client():
    """Create test client for Core API."""
    app = build_app()
    return TestClient(app)


@pytest.fixture
def test_user_graph():
    """Create a test belief graph with rr_score=800 for Chronotype."""
    storage = get_graph_storage()
    user_id = "test_rr_user"

    # Create a belief graph with a Chronotype trait
    graph = BeliefGraph(
        user_id=user_id,
        nodes=[
            BeliefNode(
                node_type="trait_belief",
                trait_id="PaDNA.Chronotype",
                value="Morning Lark",
                rr_score=800.0,  # 0-1000 scale (should normalize to 80.0)
                ucn={"u": 0.2, "c": 0.8, "n": 0.5}
            ),
            BeliefNode(
                node_type="trait_belief",
                trait_id="PaDNA.EyeDNA.IrisColor",
                value="blue",
                rr_score=63.0,  # Already 0-100 scale
                ucn={"u": 0.3, "c": 0.7, "n": 0.5}
            ),
        ],
        edges=[]
    )

    # Save to storage
    storage.save_user_graph(user_id, graph)

    yield user_id

    # Cleanup (optional - depends on your test isolation strategy)
    # storage.delete_user_graph(user_id)


def test_graph_api_rr_normalization(client, test_user_graph):
    """
    Test that GET /core/graph/user/{id} returns normalized RR/Curiosity.

    Arrange: Create graph with rr_score=800 for PaDNA.Chronotype
    Act: Call graph API
    Assert: rr==80.0, curiosity==20.0, rr_meta present
    """
    user_id = test_user_graph
    response = client.get(f"/core/graph/user/{user_id}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "nodes" in data
    assert len(data["nodes"]) == 2

    # Find Chronotype node
    chronotype_node = next(
        (n for n in data["nodes"] if n.get("trait_id") == "PaDNA.Chronotype"),
        None
    )

    assert chronotype_node is not None, "Chronotype node not found in response"

    # Assert normalized RR (800 → 80.0)
    assert chronotype_node.get("rr") == 80.0, f"Expected rr=80.0, got {chronotype_node.get('rr')}"

    # Assert Curiosity = 100 - RR
    assert chronotype_node.get("curiosity") == 20.0, f"Expected curiosity=20.0, got {chronotype_node.get('curiosity')}"

    # Assert rr_meta structure
    rr_meta = chronotype_node.get("rr_meta")
    assert rr_meta is not None, "rr_meta missing"
    assert rr_meta.get("rr_raw") == 800.0, f"Expected rr_raw=800.0, got {rr_meta.get('rr_raw')}"
    assert rr_meta.get("scale") == "0_1000", f"Expected scale=0_1000, got {rr_meta.get('scale')}"
    assert rr_meta.get("source") == "adapter", f"Expected source=adapter, got {rr_meta.get('source')}"


def test_graph_api_already_normalized_rr(client, test_user_graph):
    """
    Test that RR values already in 0-100 range are handled correctly.

    Arrange: Create graph with rr_score=63 for EyeColor (already 0-100)
    Act: Call graph API
    Assert: rr==63.0, curiosity==37.0, scale=0_100
    """
    user_id = test_user_graph
    response = client.get(f"/core/graph/user/{user_id}")

    assert response.status_code == 200

    data = response.json()
    eye_node = next(
        (n for n in data["nodes"] if n.get("trait_id") == "PaDNA.EyeDNA.IrisColor"),
        None
    )

    assert eye_node is not None

    assert eye_node.get("rr") == 63.0
    assert eye_node.get("curiosity") == 37.0

    rr_meta = eye_node.get("rr_meta")
    assert rr_meta.get("scale") == "0_100"  # Should detect 0-100 scale
