"""Analytics data collection backend for ReDNA system metrics.

Collects and aggregates metrics for:
- Coach usage patterns
- Curiosity coverage
- Ops schedule compliance
- System health
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os


@dataclass
class CoachSessionMetric:
    """Metrics for a single coach session."""
    user_id: str
    coach_id: str
    session_start: str
    session_end: Optional[str]
    message_count: int
    duration_seconds: Optional[float]
    engagement_score: float  # 0.0-1.0 based on message depth


@dataclass
class CuriosityCoverageMetric:
    """Coverage metrics for trait families."""
    trait_family: str
    total_traits: int
    traits_with_data: int
    coverage_percentage: float
    avg_curiosity: float
    avg_ucn: float
    last_updated: str


@dataclass
class OpsComplianceMetric:
    """Ops schedule compliance metrics."""
    operation_type: str
    scheduled_time: str
    actual_time: Optional[str]
    status: str  # "completed", "missed", "failed", "pending"
    duration_seconds: Optional[float]
    user_id: Optional[str]


@dataclass
class SystemHealthMetric:
    """System health snapshot."""
    timestamp: str
    service_name: str
    status: str  # "online", "offline", "degraded"
    latency_ms: Optional[float]
    error_count: int
    request_count: int


def get_write_protect() -> bool:
    """Get write-protect status from environment."""
    return os.getenv("WRITE_PROTECT", "true").lower() in {"true", "1", "yes", "on"}


def get_metrics_path(metric_type: str) -> Path:
    """Get path for metrics storage."""
    write_protect = get_write_protect()
    base = Path("data/dev_analytics") if write_protect else Path("data/analytics")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{metric_type}_metrics.jsonl"


# ============================================================================
# Coach Analytics Collection
# ============================================================================

def log_coach_session(
    user_id: str,
    coach_id: str,
    message_count: int,
    duration_seconds: float,
    engagement_score: float = 0.5,
) -> None:
    """Log a completed coach session."""
    metric = CoachSessionMetric(
        user_id=user_id,
        coach_id=coach_id,
        session_start=datetime.now(timezone.utc).isoformat(),
        session_end=datetime.now(timezone.utc).isoformat(),
        message_count=message_count,
        duration_seconds=duration_seconds,
        engagement_score=engagement_score,
    )

    path = get_metrics_path("coach_sessions")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(metric)) + "\n")


def load_coach_session_metrics(
    days_back: int = 30,
    user_id: Optional[str] = None,
) -> List[CoachSessionMetric]:
    """Load coach session metrics."""
    path = get_metrics_path("coach_sessions")
    if not path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    metrics = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                session_start = datetime.fromisoformat(data["session_start"].replace("Z", "+00:00"))

                if session_start < cutoff:
                    continue

                if user_id and data["user_id"] != user_id:
                    continue

                metrics.append(CoachSessionMetric(**data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return metrics


def compute_coach_switch_frequency(days_back: int = 30) -> Dict[str, int]:
    """Compute how often each coach is used."""
    sessions = load_coach_session_metrics(days_back=days_back)

    frequency = defaultdict(int)
    for session in sessions:
        frequency[session.coach_id] += 1

    return dict(frequency)


def compute_coach_engagement_scores(days_back: int = 30) -> Dict[str, float]:
    """Compute average engagement score per coach."""
    sessions = load_coach_session_metrics(days_back=days_back)

    totals = defaultdict(float)
    counts = defaultdict(int)

    for session in sessions:
        totals[session.coach_id] += session.engagement_score
        counts[session.coach_id] += 1

    return {
        coach_id: totals[coach_id] / counts[coach_id]
        for coach_id in counts
        if counts[coach_id] > 0
    }


def compute_coach_session_durations(days_back: int = 30) -> Dict[str, float]:
    """Compute average session duration per coach (seconds)."""
    sessions = load_coach_session_metrics(days_back=days_back)

    totals = defaultdict(float)
    counts = defaultdict(int)

    for session in sessions:
        if session.duration_seconds is not None:
            totals[session.coach_id] += session.duration_seconds
            counts[session.coach_id] += 1

    return {
        coach_id: totals[coach_id] / counts[coach_id]
        for coach_id in counts
        if counts[coach_id] > 0
    }


# ============================================================================
# Curiosity Coverage Analytics
# ============================================================================

def compute_curiosity_coverage(user_id: str) -> List[CuriosityCoverageMetric]:
    """Compute curiosity coverage by trait family for a user."""
    try:
        from ReDNACoreDemo.core import storage
    except ImportError:
        return []

    # Load user state
    try:
        resolved, _, _ = storage.read_user_state(user_id)
    except Exception:
        return []

    # Group by trait family
    families = defaultdict(lambda: {"total": 0, "with_data": 0, "curiosity": [], "ucn": []})

    for trait_id, trait_data in resolved.items():
        # Parse family from trait_id (e.g., "PhotoPreferences.lighting_style")
        if "." in trait_id:
            family = trait_id.split(".")[0]
        else:
            family = "Unknown"

        families[family]["total"] += 1

        ucn = trait_data.get("ucn")
        if ucn is not None and ucn > 0:
            families[family]["with_data"] += 1
            families[family]["ucn"].append(ucn)

        # Get curiosity if available
        curiosity = trait_data.get("curiosity")
        if curiosity is not None:
            families[family]["curiosity"].append(curiosity)

    # Convert to metrics
    metrics = []
    for family, data in families.items():
        coverage_pct = (data["with_data"] / data["total"] * 100) if data["total"] > 0 else 0.0
        avg_curiosity = sum(data["curiosity"]) / len(data["curiosity"]) if data["curiosity"] else 0.0
        avg_ucn = sum(data["ucn"]) / len(data["ucn"]) if data["ucn"] else 0.0

        metrics.append(CuriosityCoverageMetric(
            trait_family=family,
            total_traits=data["total"],
            traits_with_data=data["with_data"],
            coverage_percentage=coverage_pct,
            avg_curiosity=avg_curiosity,
            avg_ucn=avg_ucn,
            last_updated=datetime.now(timezone.utc).isoformat(),
        ))

    return sorted(metrics, key=lambda m: m.coverage_percentage, reverse=True)


def identify_coverage_gaps(user_id: str, threshold: float = 0.3) -> List[str]:
    """Identify traits with low UCN (below threshold)."""
    try:
        from ReDNACoreDemo.core import storage
    except ImportError:
        return []

    try:
        resolved, _, _ = storage.read_user_state(user_id)
    except Exception:
        return []

    gaps = []
    for trait_id, trait_data in resolved.items():
        ucn = trait_data.get("ucn", 0.0)
        if ucn < threshold:
            gaps.append(trait_id)

    return sorted(gaps)


# ============================================================================
# Ops Compliance Analytics
# ============================================================================

def log_ops_execution(
    operation_type: str,
    scheduled_time: str,
    actual_time: str,
    status: str,
    duration_seconds: Optional[float] = None,
    user_id: Optional[str] = None,
) -> None:
    """Log an ops execution."""
    metric = OpsComplianceMetric(
        operation_type=operation_type,
        scheduled_time=scheduled_time,
        actual_time=actual_time,
        status=status,
        duration_seconds=duration_seconds,
        user_id=user_id,
    )

    path = get_metrics_path("ops_compliance")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(metric)) + "\n")


def load_ops_compliance_metrics(days_back: int = 30) -> List[OpsComplianceMetric]:
    """Load ops compliance metrics."""
    path = get_metrics_path("ops_compliance")
    if not path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    metrics = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                scheduled = datetime.fromisoformat(data["scheduled_time"].replace("Z", "+00:00"))

                if scheduled < cutoff:
                    continue

                metrics.append(OpsComplianceMetric(**data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return metrics


def compute_ops_success_rate(days_back: int = 30) -> Dict[str, float]:
    """Compute success rate by operation type."""
    metrics = load_ops_compliance_metrics(days_back=days_back)

    totals = defaultdict(int)
    successes = defaultdict(int)

    for metric in metrics:
        totals[metric.operation_type] += 1
        if metric.status == "completed":
            successes[metric.operation_type] += 1

    return {
        op_type: (successes[op_type] / totals[op_type] * 100) if totals[op_type] > 0 else 0.0
        for op_type in totals
    }


def compute_schedule_adherence(days_back: int = 30, tolerance_minutes: int = 5) -> Dict[str, Any]:
    """Compute schedule adherence (on-time vs. late vs. missed)."""
    metrics = load_ops_compliance_metrics(days_back=days_back)

    on_time = 0
    late = 0
    missed = 0

    for metric in metrics:
        if metric.status == "missed":
            missed += 1
        elif metric.actual_time:
            scheduled = datetime.fromisoformat(metric.scheduled_time.replace("Z", "+00:00"))
            actual = datetime.fromisoformat(metric.actual_time.replace("Z", "+00:00"))
            delay_minutes = (actual - scheduled).total_seconds() / 60

            if delay_minutes <= tolerance_minutes:
                on_time += 1
            else:
                late += 1

    total = on_time + late + missed

    return {
        "on_time": on_time,
        "late": late,
        "missed": missed,
        "on_time_percentage": (on_time / total * 100) if total > 0 else 0.0,
        "total_operations": total,
    }


# ============================================================================
# System Health Analytics
# ============================================================================

def log_system_health(
    service_name: str,
    status: str,
    latency_ms: Optional[float] = None,
    error_count: int = 0,
    request_count: int = 0,
) -> None:
    """Log system health snapshot."""
    metric = SystemHealthMetric(
        timestamp=datetime.now(timezone.utc).isoformat(),
        service_name=service_name,
        status=status,
        latency_ms=latency_ms,
        error_count=error_count,
        request_count=request_count,
    )

    path = get_metrics_path("system_health")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(metric)) + "\n")


def load_system_health_metrics(
    hours_back: int = 24,
    service_name: Optional[str] = None,
) -> List[SystemHealthMetric]:
    """Load system health metrics."""
    path = get_metrics_path("system_health")
    if not path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    metrics = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

                if timestamp < cutoff:
                    continue

                if service_name and data["service_name"] != service_name:
                    continue

                metrics.append(SystemHealthMetric(**data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return metrics


def compute_service_uptime(hours_back: int = 24) -> Dict[str, float]:
    """Compute uptime percentage per service."""
    metrics = load_system_health_metrics(hours_back=hours_back)

    totals = defaultdict(int)
    online = defaultdict(int)

    for metric in metrics:
        totals[metric.service_name] += 1
        if metric.status == "online":
            online[metric.service_name] += 1

    return {
        service: (online[service] / totals[service] * 100) if totals[service] > 0 else 0.0
        for service in totals
    }


def compute_latency_percentiles(
    service_name: str,
    hours_back: int = 24,
) -> Dict[str, float]:
    """Compute latency percentiles (p50, p95, p99)."""
    metrics = load_system_health_metrics(hours_back=hours_back, service_name=service_name)

    latencies = [m.latency_ms for m in metrics if m.latency_ms is not None]

    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    latencies.sort()
    n = len(latencies)

    return {
        "p50": latencies[int(n * 0.50)] if n > 0 else 0.0,
        "p95": latencies[int(n * 0.95)] if n > 0 else 0.0,
        "p99": latencies[int(n * 0.99)] if n > 0 else 0.0,
    }


def compute_error_rate(hours_back: int = 24) -> Dict[str, float]:
    """Compute error rate per service (errors / total requests)."""
    metrics = load_system_health_metrics(hours_back=hours_back)

    errors = defaultdict(int)
    requests = defaultdict(int)

    for metric in metrics:
        errors[metric.service_name] += metric.error_count
        requests[metric.service_name] += metric.request_count

    return {
        service: (errors[service] / requests[service] * 100) if requests[service] > 0 else 0.0
        for service in requests
    }


def get_storage_size() -> Dict[str, float]:
    """Get storage size for data directories (MB)."""
    paths = {
        "users": Path("data/users"),
        "dev_users": Path("data/dev_users"),
        "audit_logs": Path("data/audit_logs"),
        "dev_logs": Path("data/dev_logs"),
    }

    sizes = {}
    for name, path in paths.items():
        if not path.exists():
            sizes[name] = 0.0
            continue

        total_size = sum(
            f.stat().st_size
            for f in path.rglob("*")
            if f.is_file()
        )
        sizes[name] = total_size / (1024 * 1024)  # Convert to MB

    return sizes


__all__ = [
    "CoachSessionMetric",
    "CuriosityCoverageMetric",
    "OpsComplianceMetric",
    "SystemHealthMetric",
    "log_coach_session",
    "load_coach_session_metrics",
    "compute_coach_switch_frequency",
    "compute_coach_engagement_scores",
    "compute_coach_session_durations",
    "compute_curiosity_coverage",
    "identify_coverage_gaps",
    "log_ops_execution",
    "load_ops_compliance_metrics",
    "compute_ops_success_rate",
    "compute_schedule_adherence",
    "log_system_health",
    "load_system_health_metrics",
    "compute_service_uptime",
    "compute_latency_percentiles",
    "compute_error_rate",
    "get_storage_size",
]
