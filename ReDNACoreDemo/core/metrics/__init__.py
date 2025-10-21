"""Core metrics and normalization utilities."""

from .rr_adapter import rr_to_percentile, Scale

# Phase 9: Import legacy metrics for backward compatibility
# The old metrics.py module is still used by pipeline and other modules
try:
    from ..metrics import METRICS, MetricNames, record_request
except ImportError:
    # Fallback if metrics.py doesn't exist
    class MetricNames:
        """Stub metric names for backward compatibility."""
        RR = "RR"
        INGEST_REQUESTS = "ingest.requests"
        INGEST_ERRORS = "ingest.errors"
        HOP_MS_PREPROCESS = "hop_ms.preprocess"
        HOP_MS_UCNRR = "hop_ms.ucnrr"
        HOP_MS_RESOLVE = "hop_ms.resolve"
        HOP_MS_TOTAL = "hop_ms.total"
        POLICY_TIER_HOT = "policy.tier.hot"
        POLICY_TIER_WARM = "policy.tier.warm"
        POLICY_TIER_COLD = "policy.tier.cold"
        POLICY_TIER_DROP = "policy.tier.drop"

    class NoOpMetrics:
        """No-op metrics collector for when real metrics unavailable."""
        def observe(self, metric: str, value: float) -> None:
            pass
        def increment(self, metric: str, value: int = 1) -> None:
            pass
        def record_time(self, metric: str, duration_ms: float) -> None:
            pass

    METRICS = NoOpMetrics()

    def record_request(*, latency_ms: float, is_error: bool, status_code: int = None) -> None:
        """Backward compatibility shim for record_request.

        No-op implementation when metrics.py is not available.
        """
        pass

__all__ = ["rr_to_percentile", "Scale", "METRICS", "MetricNames", "record_request"]
