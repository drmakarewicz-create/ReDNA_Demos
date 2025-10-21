"""
Unit tests for RR normalization at API layer (Phase 9).

These tests verify the normalization logic without requiring full API startup.
"""

import pytest
from ReDNACoreDemo.core.graph.schemas import BeliefGraph, BeliefNode
from ReDNACoreDemo.core.graph.normalize_egress import (
    normalize_belief_node,
    normalize_belief_graph,
    normalize_trait_dict,
)


def test_normalize_belief_node_0_1000_scale():
    """Test normalization of BeliefNode with 0-1000 rr_score."""
    node = BeliefNode(
        node_type="trait_belief",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=800.0,
        ucn={"u": 0.2, "c": 0.8, "n": 0.5}
    )

    normalized = normalize_belief_node(node, "test_user")

    assert normalized.rr == 80.0, f"Expected rr=80.0, got {normalized.rr}"
    assert normalized.curiosity == 20.0, f"Expected curiosity=20.0, got {normalized.curiosity}"
    assert normalized.rr_meta is not None
    assert normalized.rr_meta["rr_raw"] == 800.0
    assert normalized.rr_meta["scale"] == "0_1000"


def test_normalize_belief_node_0_100_scale():
    """Test normalization of BeliefNode already in 0-100 range."""
    node = BeliefNode(
        node_type="trait_belief",
        trait_id="PaDNA.EyeColor",
        value="blue",
        rr_score=63.0,  # Already 0-100
        ucn={"u": 0.3, "c": 0.7, "n": 0.5}
    )

    normalized = normalize_belief_node(node, "test_user")

    assert normalized.rr == 63.0
    assert normalized.curiosity == 37.0
    assert normalized.rr_meta["scale"] == "0_100"


def test_normalize_belief_graph():
    """Test normalization of entire BeliefGraph."""
    graph = BeliefGraph(
        user_id="test_user",
        nodes=[
            BeliefNode(
                node_type="trait_belief",
                trait_id="PaDNA.Chronotype",
                value="Morning Lark",
                rr_score=750.0,  # 0-1000
                ucn={"u": 0.25, "c": 0.75, "n": 0.5}
            ),
            BeliefNode(
                node_type="observation",
                observation_text="I wake up at 6am",
                observation_source="chat"
            ),
            BeliefNode(
                node_type="trait_belief",
                trait_id="PaDNA.EyeColor",
                value="blue",
                rr_score=85.0,  # 0-100
                ucn={"u": 0.15, "c": 0.85, "n": 0.5}
            ),
        ],
        edges=[]
    )

    normalized = normalize_belief_graph(graph, "test_user")

    # Check Chronotype (0-1000 → 0-100)
    chronotype = next(n for n in normalized.nodes if n.trait_id == "PaDNA.Chronotype")
    assert chronotype.rr == 75.0
    assert chronotype.curiosity == 25.0

    # Check EyeColor (already 0-100)
    eye = next(n for n in normalized.nodes if n.trait_id == "PaDNA.EyeColor")
    assert eye.rr == 85.0
    assert eye.curiosity == 15.0

    # Check observation node unchanged
    obs = next(n for n in normalized.nodes if n.node_type == "observation")
    assert obs.rr is None
    assert obs.curiosity is None


def test_normalize_trait_dict():
    """Test normalization of trait dictionary (for snapshot API)."""
    trait = {
        "trait_id": "PaDNA.Chronotype",
        "value": "Morning Lark",
        "rr_score": 800.0,  # 0-1000
        "ucn": {"u": 0.2, "c": 0.8, "n": 0.5}
    }

    normalized = normalize_trait_dict(trait, "test_user")

    assert normalized["rr"] == 80.0
    assert normalized["curiosity"] == 20.0
    assert normalized["rr_meta"]["rr_raw"] == 800.0
    assert normalized["rr_meta"]["scale"] == "0_1000"
    # Ensure backward compat
    assert normalized["rr_score"] == 800.0


def test_normalize_trait_dict_no_rr():
    """Test that traits without rr_score are not modified."""
    trait = {
        "trait_id": "PaDNA.Height",
        "value": 175,
        "ucn": {"u": 0.5, "c": 0.5, "n": 0.5}
    }

    normalized = normalize_trait_dict(trait, "test_user")

    # Should return unchanged
    assert "rr" not in normalized
    assert "curiosity" not in normalized
    assert "rr_meta" not in normalized


def test_curiosity_always_100_minus_rr():
    """Test canonical relationship: Curiosity = 100 - RR for various values."""
    test_cases = [
        # (rr_raw, expected_rr, expected_curiosity)
        (900.0, 90.0, 10.0),    # 0-1000 scale (>100 triggers 0-1000 detection)
        (500.0, 50.0, 50.0),    # 0-1000 scale
        (200.0, 20.0, 80.0),    # 0-1000 scale
        (75.0, 75.0, 25.0),     # 0-100 scale (ambiguous, assumes 0-100)
        (0.0, 0.0, 100.0),      # Edge case: 0 on any scale
        (1000.0, 100.0, 0.0),   # 0-1000 scale (max)
        (100.0, 100.0, 0.0),    # Edge case: 100 (ambiguous - treated as 0-100)
    ]

    for rr_raw, expected_rr, expected_curiosity in test_cases:
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="test",
            value="test",
            rr_score=rr_raw,
            ucn={}
        )

        normalized = normalize_belief_node(node, "test_user")

        assert normalized.rr == expected_rr, f"Failed for rr_raw={rr_raw}, got rr={normalized.rr}"
        assert normalized.curiosity == expected_curiosity, f"Failed for rr_raw={rr_raw}, got curiosity={normalized.curiosity}"
        assert normalized.rr + normalized.curiosity == 100.0
