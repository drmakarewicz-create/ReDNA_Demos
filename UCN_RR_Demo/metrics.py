"""
Metrics tracking for UCNRR service.

Simple in-memory metrics for monitoring UCNRR health and performance.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class UCNRRMetrics:
    """Lightweight metrics collector for UCNRR."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Counters
        self.counters = {
            "rr_requests_total": 0,
            "rr_requests_2xx": 0,
            "rr_requests_4xx": 0,
            "rr_requests_5xx": 0,
            "rr_selftest_ok": 0,
            "rr_selftest_fail": 0,
        }

        # Latency samples (last 50)
        self.latency_samples: Dict[str, deque] = {
            "rr_score": deque(maxlen=50),
            "rr_selftest": deque(maxlen=50),
        }

        # Last selftest result
        self.last_selftest: Optional[Dict[str, Any]] = None

    def increment(self, key: str, n: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            if key in self.counters:
                self.counters[key] += n

    def observe_latency(self, key: str, ms: float) -> None:
        """Record a latency observation."""
        with self._lock:
            if key in self.latency_samples:
                self.latency_samples[key].append(ms)

    def update_selftest(self, result: Dict[str, Any]) -> None:
        """Update last selftest result."""
        with self._lock:
            self.last_selftest = result

    def _percentile(self, samples: List[float], p: float) -> float:
        """Calculate percentile from samples."""
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        idx = int(len(sorted_samples) * p)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def get_snapshot(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            uptime_seconds = int(time.time() - self._start_time)

            # Calculate percentiles for each latency category
            p50_ms = {}
            p95_ms = {}
            for key, samples in self.latency_samples.items():
                sample_list = list(samples)
                if sample_list:
                    p50_ms[key] = round(self._percentile(sample_list, 0.50), 1)
                    p95_ms[key] = round(self._percentile(sample_list, 0.95), 1)

            snapshot = {
                "service": "ucnrr",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": uptime_seconds,
                "counters": dict(self.counters),
                "p50_ms": p50_ms,
                "p95_ms": p95_ms,
            }

            # Add selftest info if available
            if self.last_selftest:
                snapshot["selftest"] = {
                    "ok": self.last_selftest.get("ok", False),
                    "last_ms": self.last_selftest.get("elapsed_ms", 0),
                    "ucn": self.last_selftest.get("ucn", 0),
                }

            return snapshot


# Global metrics instance
METRICS = UCNRRMetrics()
