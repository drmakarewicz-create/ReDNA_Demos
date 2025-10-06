"""
Trace Consolidation

Unifies ORS span logs (Dev Explorer / UCN/RR / Core) into a single trace schema
for easier analysis and visualization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from ExplorerDev.bootstrap import ensure_repo_root
except Exception:
    import os
    import sys
    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_repo_root  # type: ignore

from ExplorerDev import tracing


REPO_ROOT = ensure_repo_root()
TRACE_ROOT = REPO_ROOT / "data" / "dev_logs"


@dataclass
class TraceSpan:
    """Unified trace span representation."""
    trace_id: str
    component: str  # devexp, ucnrr, core
    span_name: str
    phase: str  # start, end, event
    timestamp: datetime
    meta: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    event_type: Optional[str] = None


@dataclass
class UnifiedTrace:
    """Complete trace with all spans across components."""
    trace_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    spans: List[TraceSpan]
    components_involved: List[str]
    total_spans: int
    has_errors: bool
    summary: str


def parse_trace_entry(entry: Dict[str, Any], component: str) -> Optional[TraceSpan]:
    """Parse a trace log entry into a TraceSpan."""
    try:
        trace_id = entry.get("trace_id")
        if not trace_id:
            return None

        ts_str = entry.get("ts")
        if not ts_str:
            return None

        # Parse timestamp
        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

        # Determine phase and span name
        phase = entry.get("phase")
        span_name = entry.get("span")
        event_type = entry.get("event")

        if not phase and event_type:
            phase = "event"
            span_name = event_type

        if not phase or not span_name:
            return None

        return TraceSpan(
            trace_id=trace_id,
            component=component,
            span_name=span_name,
            phase=phase,
            timestamp=timestamp,
            meta=entry.get("meta", {}),
            event_type=event_type,
        )

    except Exception:
        return None


def load_trace_logs(trace_id: Optional[str] = None, limit: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load trace logs from all components.

    Args:
        trace_id: Optional trace ID to filter by
        limit: Maximum number of entries per component

    Returns:
        Dict mapping component name to list of log entries
    """
    paths = tracing.trace_log_paths()
    results: Dict[str, List[Dict[str, Any]]] = {}

    for component, path in paths.items():
        if not path.exists():
            results[component] = []
            continue

        entries: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if trace_id and entry.get("trace_id") != trace_id:
                            continue
                        entries.append(entry)
                        if len(entries) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass

        results[component] = entries

    return results


def consolidate_trace(trace_id: str) -> Optional[UnifiedTrace]:
    """
    Consolidate all logs for a specific trace ID into a unified view.

    Args:
        trace_id: The trace ID to consolidate

    Returns:
        UnifiedTrace object or None if not found
    """
    logs = load_trace_logs(trace_id=trace_id)

    # Parse all entries into spans
    all_spans: List[TraceSpan] = []
    components_seen = set()

    for component, entries in logs.items():
        for entry in entries:
            span = parse_trace_entry(entry, component)
            if span:
                all_spans.append(span)
                components_seen.add(component)

    if not all_spans:
        return None

    # Sort spans by timestamp
    all_spans.sort(key=lambda s: s.timestamp)

    # Calculate durations for matched start/end pairs
    span_pairs: Dict[Tuple[str, str], List[TraceSpan]] = {}
    for span in all_spans:
        key = (span.component, span.span_name)
        if key not in span_pairs:
            span_pairs[key] = []
        span_pairs[key].append(span)

    for key, spans in span_pairs.items():
        starts = [s for s in spans if s.phase == "start"]
        ends = [s for s in spans if s.phase == "end"]

        for start, end in zip(starts, ends):
            duration = (end.timestamp - start.timestamp).total_seconds() * 1000
            start.duration_ms = duration
            end.duration_ms = duration

    # Determine overall trace timing
    start_time = all_spans[0].timestamp
    end_time = all_spans[-1].timestamp if all_spans else None
    duration_ms = None
    if end_time:
        duration_ms = (end_time - start_time).total_seconds() * 1000

    # Check for errors
    has_errors = any(
        "error" in str(span.meta).lower() or "fail" in str(span.meta).lower()
        for span in all_spans
    )

    # Generate summary
    summary = f"{len(all_spans)} spans across {len(components_seen)} components"

    return UnifiedTrace(
        trace_id=trace_id,
        start_time=start_time,
        end_time=end_time,
        duration_ms=duration_ms,
        spans=all_spans,
        components_involved=sorted(components_seen),
        total_spans=len(all_spans),
        has_errors=has_errors,
        summary=summary,
    )


def list_recent_traces(limit: int = 50) -> List[Dict[str, Any]]:
    """
    List recent trace IDs from all logs.

    Returns:
        List of dicts with trace_id, first_seen, components
    """
    logs = load_trace_logs(limit=limit * 3)  # Over-fetch to ensure we get enough unique traces

    # Group by trace_id
    trace_index: Dict[str, Dict[str, Any]] = {}

    for component, entries in logs.items():
        for entry in entries:
            trace_id = entry.get("trace_id")
            if not trace_id:
                continue

            if trace_id not in trace_index:
                trace_index[trace_id] = {
                    "trace_id": trace_id,
                    "first_seen": entry.get("ts"),
                    "components": set(),
                }

            trace_index[trace_id]["components"].add(component)

    # Convert to list and sort by timestamp (newest first)
    traces = list(trace_index.values())
    traces.sort(key=lambda t: t.get("first_seen", ""), reverse=True)

    # Convert component sets to lists
    for trace in traces:
        trace["components"] = sorted(trace["components"])

    return traces[:limit]


def export_trace_waterfall(trace: UnifiedTrace) -> Dict[str, Any]:
    """
    Export trace in waterfall format for visualization.

    Returns:
        Dict suitable for rendering a waterfall chart
    """
    if not trace.spans:
        return {
            "trace_id": trace.trace_id,
            "duration_ms": 0,
            "entries": [],
        }

    base_time = trace.start_time
    entries = []

    for span in trace.spans:
        offset_ms = (span.timestamp - base_time).total_seconds() * 1000

        entry = {
            "component": span.component,
            "span": span.span_name,
            "phase": span.phase,
            "offset_ms": round(offset_ms, 2),
            "duration_ms": round(span.duration_ms, 2) if span.duration_ms else None,
            "meta": span.meta,
        }

        if span.event_type:
            entry["event"] = span.event_type

        entries.append(entry)

    return {
        "trace_id": trace.trace_id,
        "start_time": trace.start_time.isoformat(),
        "end_time": trace.end_time.isoformat() if trace.end_time else None,
        "duration_ms": round(trace.duration_ms, 2) if trace.duration_ms else None,
        "components": trace.components_involved,
        "total_spans": trace.total_spans,
        "has_errors": trace.has_errors,
        "entries": entries,
    }


def generate_trace_summary_csv(traces: List[UnifiedTrace]) -> str:
    """Generate a CSV summary of multiple traces."""
    lines = ["trace_id,start_time,duration_ms,total_spans,components,has_errors"]

    for trace in traces:
        lines.append(
            ",".join([
                trace.trace_id,
                trace.start_time.isoformat(),
                str(round(trace.duration_ms, 2) if trace.duration_ms else ""),
                str(trace.total_spans),
                "|".join(trace.components_involved),
                str(trace.has_errors),
            ])
        )

    return "\n".join(lines)


__all__ = [
    "TraceSpan",
    "UnifiedTrace",
    "parse_trace_entry",
    "load_trace_logs",
    "consolidate_trace",
    "list_recent_traces",
    "export_trace_waterfall",
    "generate_trace_summary_csv",
]
