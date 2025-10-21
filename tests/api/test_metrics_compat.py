"""
Test metrics import compatibility (Phase 9).

Verifies that legacy metrics imports work without crashing.
"""

import pytest


def test_metrics_import_compatibility():
    """
    Test that legacy metrics imports don't crash (Phase 9 compatibility shims).

    AC: Can import METRICS, MetricNames, record_request without ImportError
    """
    try:
        from ReDNACoreDemo.core.metrics import record_request, METRICS, MetricNames
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")

    # Call record_request (should not raise)
    record_request(latency_ms=100.0, is_error=False, status_code=200)

    # Access MetricNames (should not raise)
    assert hasattr(MetricNames, "RR")

    # Access METRICS (should not raise)
    assert METRICS is not None


def test_curiosity_canonical_relationship():
    """
    Test that Curiosity = 100 - RR for normalization logic.

    This is the authoritative rule that must hold everywhere.
    """
    from ReDNACoreDemo.core.graph.schemas import BeliefNode
    from ReDNACoreDemo.core.graph.normalize_egress import normalize_belief_node

    test_cases = [
        (800.0, 80.0, 20.0),   # 0-1000 scale
        (500.0, 50.0, 50.0),
        (250.0, 25.0, 75.0),
        (90.0, 90.0, 10.0),    # 0-100 scale
        (0.0, 0.0, 100.0),     # Edge case
        (1000.0, 100.0, 0.0),  # Max
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

        assert normalized.rr == expected_rr, f"Failed for {rr_raw}: rr={normalized.rr}"
        assert normalized.curiosity == expected_curiosity, f"Failed for {rr_raw}: curiosity={normalized.curiosity}"
        assert abs(normalized.rr + normalized.curiosity - 100.0) < 0.01, "Curiosity != 100 - RR"
