"""
Unified Metrics Tracking for ReDNA

Provides simple counter-based metrics for monitoring system health and performance.
Metrics are stored in memory and exposed via HTTP endpoints.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple


class MetricsCollector:
    """
    Thread-safe metrics collector with counters and gauges.

    Supports:
    - Counters: Monotonically increasing values (requests, errors, etc.)
    - Gauges: Point-in-time values (queue depth, active connections, etc.)
    - Timers: Duration tracking for operations
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, list] = defaultdict(list)
        self._start_time = time.time()
        self._lock = threading.Lock()

    def increment(self, metric: str, value: int = 1) -> None:
        """
        Increment a counter metric.

        Args:
            metric: Metric name (e.g., "ingests.total", "errors.4xx")
            value: Amount to increment by (default: 1)
        """
        with self._lock:
            self._counters[metric] += value

    def decrement(self, metric: str, value: int = 1) -> None:
        """Decrement a counter metric."""
        with self._lock:
            self._counters[metric] -= value

    def set_gauge(self, metric: str, value: float) -> None:
        """
        Set a gauge metric to a specific value.

        Args:
            metric: Metric name (e.g., "queue.depth", "active.connections")
            value: Current value
        """
        with self._lock:
            self._gauges[metric] = value

    def record_time(self, metric: str, duration_ms: float) -> None:
        """
        Record a timing measurement.

        Args:
            metric: Metric name (e.g., "ingest.duration_ms", "resolve.duration_ms")
            duration_ms: Duration in milliseconds
        """
        with self._lock:
            self._timers[metric].append(duration_ms)
            # Keep only last 1000 measurements to avoid unbounded growth
            if len(self._timers[metric]) > 1000:
                self._timers[metric] = self._timers[metric][-1000:]

    def observe(self, metric: str, value: float) -> None:
        """
        Record an observation (alias for record_time for semantic clarity).

        Args:
            metric: Metric name
            value: Observed value (typically milliseconds for timing)
        """
        self.record_time(metric, value)

    def get_counter(self, metric: str) -> int:
        """Get current value of a counter."""
        with self._lock:
            return self._counters.get(metric, 0)

    def get_gauge(self, metric: str) -> Optional[float]:
        """Get current value of a gauge."""
        with self._lock:
            return self._gauges.get(metric)

    def get_timer_stats(self, metric: str) -> Dict[str, float]:
        """
        Get statistics for a timer metric.

        Returns:
            Dict with count, mean, min, max, p50, p95, p99
        """
        with self._lock:
            measurements = self._timers.get(metric, [])
            if not measurements:
                return {"count": 0}

            sorted_measurements = sorted(measurements)
            count = len(sorted_measurements)

            return {
                "count": count,
                "mean": sum(sorted_measurements) / count,
                "min": sorted_measurements[0],
                "max": sorted_measurements[-1],
                "p50": sorted_measurements[int(count * 0.5)],
                "p95": sorted_measurements[int(count * 0.95)],
                "p99": sorted_measurements[int(count * 0.99)],
            }

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics as a dictionary.

        Returns:
            Dict with counters, gauges, timers, and metadata
        """
        with self._lock:
            uptime_seconds = int(time.time() - self._start_time)

            # Build timer stats
            timer_stats = {}
            for metric, measurements in self._timers.items():
                timer_stats[metric] = self.get_timer_stats(metric)

            payload = {
                "service": self.service_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": uptime_seconds,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timers": timer_stats,
            }
            rolling_snapshot = ROLLING_REQUESTS.snapshot()
            payload["counters"]["errors_5xx_window_5m"] = rolling_snapshot["errors_5xx_window_5m"]
            payload["counters"]["requests_window_5m"] = rolling_snapshot["requests_window_5m"]
            payload["gauges"]["latency_p95_ms_window_5m"] = rolling_snapshot["latency_p95_ms_window_5m"]
            payload["rolling_window"] = rolling_snapshot
            return payload

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()


# Rolling request metrics
class RollingWindowTracker:
    """Track request counts, error counts, and latency percentiles over a rolling window."""

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._durations: Deque[Tuple[float, float]] = deque()
        self._errors: Deque[float] = deque()
        self._lock = threading.Lock()

    def record(self, duration_ms: float, status_code: int) -> None:
        now = time.time()
        with self._lock:
            self._durations.append((now, float(duration_ms)))
            if status_code >= 500:
                self._errors.append(now)
            self._trim(now)

    def _trim(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._durations and self._durations[0][0] < cutoff:
            self._durations.popleft()
        while self._errors and self._errors[0] < cutoff:
            self._errors.popleft()

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            self._trim(now)
            requests = len(self._durations)
            errors = len(self._errors)
            latencies = [entry[1] for entry in self._durations]

            p95_ms: Optional[float] = None
            if latencies:
                sorted_latencies = sorted(latencies)
                index = max(
                    0,
                    min(len(sorted_latencies) - 1, int(0.95 * (len(sorted_latencies) - 1))),
                )
                p95_ms = float(sorted_latencies[index])

            first_event = self._durations[0][0] if self._durations else None
            span_seconds = (now - first_event) if first_event else 0.0

            return {
                "window_seconds": self.window_seconds,
                "requests_window_5m": requests,
                "errors_5xx_window_5m": errors,
                "latency_p95_ms_window_5m": p95_ms,
                "span_seconds": span_seconds,
                "warming": requests == 0 or span_seconds < min(self.window_seconds, 60),
            }


# Global metrics collector instances
_collectors: Dict[str, MetricsCollector] = {}
_collectors_lock = threading.Lock()


def get_metrics_collector(service_name: str = "core") -> MetricsCollector:
    """
    Get or create a metrics collector for a service.

    Args:
        service_name: Name of the service

    Returns:
        MetricsCollector instance
    """
    with _collectors_lock:
        if service_name not in _collectors:
            _collectors[service_name] = MetricsCollector(service_name)
        return _collectors[service_name]


# Default collector for convenience
METRICS = get_metrics_collector("core")
ROLLING_REQUESTS = RollingWindowTracker()


# Context manager for timing operations
class Timer:
    """
    Context manager for timing operations.

    Usage:
        with Timer(METRICS, "ingest.duration_ms"):
            # ... do work ...
            pass
    """

    def __init__(self, collector: MetricsCollector, metric: str):
        self.collector = collector
        self.metric = metric
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.collector.record_time(self.metric, duration_ms)


# Standard metric names (for consistency)
class MetricNames:
    """Standard metric names used across ReDNA services."""

    # Ingestion metrics
    INGESTS_TOTAL = "ingests.total"
    INGESTS_SUCCESS = "ingests.success"
    INGESTS_ERRORS = "ingests.errors"
    INGESTS_EVIDENCE_COUNT = "ingests.evidence.count"
    INGESTS_INFERRED_COUNT = "ingests.inferred.count"
    INGEST_REQUESTS = "ingest.requests"
    INGEST_ERRORS = "ingest.errors"

    # Hop timing metrics (pipeline performance)
    HOP_MS_PREPROCESS = "hop_ms.preprocess"
    HOP_MS_UCNRR = "hop_ms.ucnrr"
    HOP_MS_RESOLVE = "hop_ms.resolve"
    HOP_MS_TOTAL = "hop_ms.total"

    # HTTP error metrics
    ERRORS_4XX = "errors.4xx"
    ERRORS_5XX = "errors.5xx"
    ERRORS_400_VALIDATION = "errors.400.validation"
    ERRORS_503_UCNRR_REQUIRED = "errors.503.ucnrr_required"

    # RR/UCNRR metrics
    RR_CALLS = "rr.calls"
    RR_SUCCESS = "rr.success"
    RR_FALLBACK = "rr.fallback"
    RR_ERRORS = "rr.errors"

    # Resolution metrics
    RESOLVE_CALLS = "resolve.calls"
    RESOLVE_TRAITS = "resolve.traits.count"
    RESOLVE_DURATION_MS = "resolve.duration_ms"

    # Chat metrics
    CHAT_MESSAGES = "chat.messages"
    CHAT_TURNS = "chat.turns"
    CHAT_DURATION_MS = "chat.duration_ms"

    # Policy metrics
    POLICY_SUPERSESSIONS = "policy.supersessions"
    POLICY_CONTRADICTIONS = "policy.contradictions"
    POLICY_TIER_HOT = "policy.tier.hot"
    POLICY_TIER_WARM = "policy.tier.warm"
    POLICY_TIER_COLD = "policy.tier.cold"
    POLICY_TIER_DROP = "policy.tier.drop"

    # Prompt metrics
    PROMPT_RELOADS = "prompt.reloads"
    PROMPT_LOAD_ERRORS = "prompt.load_errors"

    # HTTP server metrics
    HTTP_REQUESTS_TOTAL = "http.requests.total"
    HTTP_REQUESTS_ERRORS = "http.requests.errors"
    HTTP_LATENCY_MS = "http.latency_ms"


def record_request(*, latency_ms: float, is_error: bool, status_code: Optional[int] = None) -> None:
    """Record an HTTP request for rolling and cumulative metrics."""
    METRICS.increment(MetricNames.HTTP_REQUESTS_TOTAL)
    if is_error:
        METRICS.increment(MetricNames.HTTP_REQUESTS_ERRORS)
    METRICS.record_time(MetricNames.HTTP_LATENCY_MS, latency_ms)

    status_for_window = status_code if status_code is not None else (500 if is_error else 200)
    ROLLING_REQUESTS.record(latency_ms, int(status_for_window))
