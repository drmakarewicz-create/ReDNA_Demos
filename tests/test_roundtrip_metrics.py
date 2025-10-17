"""
Test roundtrip metrics collection.

Verifies that hop timing is captured correctly during evidence ingestion.
"""
import pytest
import time
from unittest.mock import patch, MagicMock
from ReDNACoreDemo.core.ingest.pipeline import ingest_evidence_roundtrip, HopTimer
from ReDNACoreDemo.core.metrics import METRICS, MetricNames


def test_hop_timer():
    """Test HopTimer helper class."""
    ht = HopTimer()

    # Mark t0
    ht.mark("t0")
    time.sleep(0.01)  # 10ms

    # Mark t1
    ht.mark("t1")
    time.sleep(0.02)  # 20ms

    # Mark t2
    ht.mark("t2")

    # Check delta t0→t1 (should be ~10ms)
    dt_01 = ht.dt("t0", "t1")
    assert 8 < dt_01 < 15, f"Expected ~10ms, got {dt_01}ms"

    # Check delta t1→t2 (should be ~20ms)
    dt_12 = ht.dt("t1", "t2")
    assert 18 < dt_12 < 25, f"Expected ~20ms, got {dt_12}ms"

    # Check total t0→t2 (should be ~30ms)
    dt_02 = ht.dt("t0", "t2")
    assert 28 < dt_02 < 40, f"Expected ~30ms, got {dt_02}ms"

    # Check missing marks return 0
    assert ht.dt("t0", "nonexistent") == 0
    assert ht.dt("nonexistent", "t1") == 0


@patch("ReDNACoreDemo.core.ingest.pipeline._resolve_direct")
@patch("ReDNACoreDemo.core.ingest.pipeline._store_evidence")
@patch("ReDNACoreDemo.core.ingest.pipeline._build_snapshot")
@patch("ReDNACoreDemo.core.ingest.pipeline.validate_batch")
@patch("ReDNACoreDemo.core.ingest.pipeline.id_normalize")
def test_ingest_roundtrip_metrics(
    mock_id_normalize,
    mock_validate_batch,
    mock_build_snapshot,
    mock_store_evidence,
    mock_resolve_direct
):
    """Test that ingest_evidence_roundtrip emits hop metrics."""
    # Reset metrics
    METRICS.reset()

    # Setup mocks
    mock_id_normalize.return_value = [
        {"trait_id": "Test.Trait", "value": {"text": "test"}}
    ]
    mock_validate_batch.return_value = [
        {"trait_id": "Test.Trait", "value": {"text": "test"}, "source": "test", "ts": "2025-01-01T00:00:00Z"}
    ]
    mock_store_evidence.return_value = {"records": [], "persisted": []}
    mock_resolve_direct.return_value = 1
    mock_build_snapshot.return_value = {"traits": {}}

    # Add a delay to simulate UCNRR processing
    def slow_resolve(*args, **kwargs):
        time.sleep(0.05)  # 50ms
        return 1

    mock_resolve_direct.side_effect = slow_resolve

    # Call ingest with test evidence
    result = ingest_evidence_roundtrip(
        user_id="test_metrics_user",
        source="test",
        evidence=[
            {"trait_id": "Test.Trait", "value": {"text": "test"}}
        ]
    )

    # Verify result
    assert result["ok"] is True
    assert "req_id" in result

    # Verify hop metrics were recorded
    assert METRICS.get_counter(MetricNames.INGEST_REQUESTS) == 1

    # Check hop timing metrics
    preprocess_stats = METRICS.get_timer_stats(MetricNames.HOP_MS_PREPROCESS)
    assert preprocess_stats["count"] == 1
    assert preprocess_stats["mean"] > 0

    ucnrr_stats = METRICS.get_timer_stats(MetricNames.HOP_MS_UCNRR)
    assert ucnrr_stats["count"] == 1
    # Should be ~50ms due to our mock delay
    assert 45 < ucnrr_stats["mean"] < 100

    resolve_stats = METRICS.get_timer_stats(MetricNames.HOP_MS_RESOLVE)
    assert resolve_stats["count"] == 1
    assert resolve_stats["mean"] >= 0

    total_stats = METRICS.get_timer_stats(MetricNames.HOP_MS_TOTAL)
    assert total_stats["count"] == 1
    assert total_stats["mean"] > ucnrr_stats["mean"]


@patch("ReDNACoreDemo.core.ingest.pipeline._resolve_direct")
@patch("ReDNACoreDemo.core.ingest.pipeline._store_evidence")
@patch("ReDNACoreDemo.core.ingest.pipeline._build_snapshot")
@patch("ReDNACoreDemo.core.ingest.pipeline.validate_batch")
@patch("ReDNACoreDemo.core.ingest.pipeline.id_normalize")
def test_ingest_error_metrics(
    mock_id_normalize,
    mock_validate_batch,
    mock_build_snapshot,
    mock_store_evidence,
    mock_resolve_direct
):
    """Test that ingest errors are counted."""
    # Reset metrics
    METRICS.reset()

    # Setup mocks to raise an error
    mock_id_normalize.side_effect = ValueError("Test error")

    # Call ingest and expect error
    with pytest.raises(ValueError):
        ingest_evidence_roundtrip(
            user_id="test_error_user",
            source="test",
            evidence=[
                {"trait_id": "Test.Trait", "value": {"text": "test"}}
            ]
        )

    # Verify error was counted
    assert METRICS.get_counter(MetricNames.INGEST_ERRORS) == 1


def test_metrics_collector_observe():
    """Test that observe() method works for recording metrics."""
    # Reset metrics
    METRICS.reset()

    # Record some observations
    METRICS.observe(MetricNames.HOP_MS_PREPROCESS, 10.5)
    METRICS.observe(MetricNames.HOP_MS_PREPROCESS, 20.3)
    METRICS.observe(MetricNames.HOP_MS_PREPROCESS, 15.7)

    # Get stats
    stats = METRICS.get_timer_stats(MetricNames.HOP_MS_PREPROCESS)

    assert stats["count"] == 3
    assert stats["min"] == 10.5
    assert stats["max"] == 20.3
    assert 14 < stats["mean"] < 16  # Average should be ~15.5
    assert stats["p50"] == 15.7
