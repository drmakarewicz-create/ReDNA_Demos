"""
Trace Waterfall Viewer

Streamlit UI component for visualizing trace waterfalls from consolidated ORS logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

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

from ExplorerDev import trace_consolidation


# Component color mapping
COMPONENT_COLORS = {
    "devexp": "#3498db",    # Blue
    "ucnrr": "#e74c3c",     # Red
    "core": "#2ecc71",      # Green
}


def render_waterfall_entry(
    entry: Dict[str, Any],
    total_duration_ms: float,
    bar_width_px: int = 600,
) -> None:
    """
    Render a single waterfall entry.

    Args:
        entry: Waterfall entry dict
        total_duration_ms: Total trace duration for scaling
        bar_width_px: Width of the waterfall bar in pixels
    """
    if st is None:
        return

    component = entry.get("component", "unknown")
    span = entry.get("span", "unknown")
    phase = entry.get("phase", "")
    offset_ms = entry.get("offset_ms", 0)
    duration_ms = entry.get("duration_ms")

    # Skip non-start entries (they don't have duration)
    if phase != "start" or duration_ms is None:
        return

    # Calculate bar position and width
    if total_duration_ms > 0:
        start_pct = (offset_ms / total_duration_ms) * 100
        width_pct = (duration_ms / total_duration_ms) * 100
    else:
        start_pct = 0
        width_pct = 0

    color = COMPONENT_COLORS.get(component, "#95a5a6")

    # Create HTML for waterfall bar
    bar_html = f"""
    <div style="
        margin: 4px 0;
        padding: 2px 0;
        position: relative;
        height: 24px;
    ">
        <div style="
            font-size: 11px;
            color: #666;
            position: absolute;
            left: 0;
            top: 4px;
            width: 120px;
        ">
            <strong>{component}</strong> · {span}
        </div>
        <div style="
            margin-left: 130px;
            position: relative;
            background: #f0f0f0;
            height: 20px;
            border-radius: 3px;
        ">
            <div style="
                position: absolute;
                left: {start_pct:.2f}%;
                width: {width_pct:.2f}%;
                background: {color};
                height: 100%;
                border-radius: 3px;
                box-sizing: border-box;
                border: 1px solid rgba(0,0,0,0.1);
            ">
                <span style="
                    font-size: 10px;
                    color: white;
                    padding: 0 4px;
                    line-height: 20px;
                    white-space: nowrap;
                ">
                    {duration_ms:.1f}ms
                </span>
            </div>
        </div>
    </div>
    """

    st.markdown(bar_html, unsafe_allow_html=True)


def render_trace_waterfall(trace_id: str) -> None:
    """Render waterfall visualization for a specific trace."""
    if st is None:
        return

    # Consolidate trace
    unified_trace = trace_consolidation.consolidate_trace(trace_id)

    if unified_trace is None:
        st.error(f"Trace {trace_id} not found")
        return

    # Export waterfall format
    waterfall = trace_consolidation.export_trace_waterfall(unified_trace)

    # Header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Duration", f"{waterfall['duration_ms']:.1f} ms")
    with col2:
        st.metric("Total Spans", waterfall["total_spans"])
    with col3:
        components_str = ", ".join(waterfall["components"])
        st.metric("Components", components_str)

    if waterfall.get("has_errors"):
        st.warning("⚠️ This trace contains errors")

    st.divider()

    # Waterfall visualization
    st.subheader("Request Flow")

    total_duration = waterfall.get("duration_ms", 0)
    entries = waterfall.get("entries", [])

    if total_duration > 0:
        for entry in entries:
            render_waterfall_entry(entry, total_duration)
    else:
        st.info("No timing data available for this trace")

    # Detailed span list
    with st.expander("Detailed Span List", expanded=False):
        rows = []
        for entry in entries:
            rows.append({
                "Component": entry.get("component", ""),
                "Span": entry.get("span", ""),
                "Phase": entry.get("phase", ""),
                "Offset (ms)": f"{entry.get('offset_ms', 0):.2f}",
                "Duration (ms)": f"{entry.get('duration_ms', 0):.2f}" if entry.get("duration_ms") else "—",
            })

        st.dataframe(rows, use_container_width=True)

    # Metadata
    with st.expander("Trace Metadata", expanded=False):
        st.json({
            "trace_id": waterfall["trace_id"],
            "start_time": waterfall["start_time"],
            "end_time": waterfall["end_time"],
            "components": waterfall["components"],
        })


def render_trace_list() -> Optional[str]:
    """
    Render list of recent traces and return selected trace_id.

    Returns:
        Selected trace_id or None
    """
    if st is None:
        return None

    st.subheader("Recent Traces")

    # Load recent traces
    limit = st.slider("Number of traces", min_value=10, max_value=100, value=25, key="trace_list_limit")

    traces = trace_consolidation.list_recent_traces(limit=limit)

    if not traces:
        st.info("No traces found")
        return None

    # Create selection table
    rows = []
    for trace in traces:
        rows.append({
            "Trace ID": trace["trace_id"],
            "First Seen": trace.get("first_seen", ""),
            "Components": ", ".join(trace.get("components", [])),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Trace selector
    trace_ids = [t["trace_id"] for t in traces]
    selected_trace = st.selectbox(
        "Select trace to view",
        options=trace_ids,
        key="trace_viewer_selection",
    )

    return selected_trace


def render_trace_viewer_tab() -> None:
    """Render complete trace viewer tab."""
    if st is None:
        return

    st.title("📊 Trace Waterfall Viewer")

    st.markdown("""
    Visualize end-to-end request flows across Dev Explorer, UCN/RR, and Core components.
    Each trace shows timing, component interaction, and potential bottlenecks.
    """)

    # Component legend
    with st.expander("Component Legend", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div style="background: {COMPONENT_COLORS['devexp']}; color: white; padding: 8px; border-radius: 4px; text-align: center;">
                Dev Explorer
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background: {COMPONENT_COLORS['ucnrr']}; color: white; padding: 8px; border-radius: 4px; text-align: center;">
                UCN/RR Engine
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background: {COMPONENT_COLORS['core']}; color: white; padding: 8px; border-radius: 4px; text-align: center;">
                Core Service
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Trace selection
    selected_trace = render_trace_list()

    if selected_trace:
        st.divider()
        render_trace_waterfall(selected_trace)


def render_trace_search() -> None:
    """Render trace search interface."""
    if st is None:
        return

    st.subheader("Search Traces")

    trace_id_input = st.text_input(
        "Enter Trace ID",
        placeholder="rt_20251004T123456_abcd",
        key="trace_search_input",
    )

    if trace_id_input and st.button("Search", key="trace_search_button"):
        render_trace_waterfall(trace_id_input)


__all__ = [
    "render_trace_waterfall",
    "render_trace_list",
    "render_trace_viewer_tab",
    "render_trace_search",
]
