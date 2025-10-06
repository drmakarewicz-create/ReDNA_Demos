"""Unified Observability tab for Developer Explorer.

Consolidates:
- Trace Viewer (waterfall visualization)
- Service Health (pings, uptime)
- Log Tailer (multi-source logs)
- Feedback Analytics (trait scores, planning weights)
- Testing & QA (golden path, loop test, prompt checks)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import altair as alt
except ImportError:
    alt = None

from ExplorerDev.trace_viewer import (
    render_trace_waterfall,
    render_trace_list,
    render_trace_search,
)
from ExplorerDev.ors_console import (
    render_service_console,
    render_log_tailer,
    render_trace_explorer,
)
from ExplorerDev.write_utils import WriteProtectContext
from ExplorerDev.diag_utils import (
    run_loop_test,
    run_ingest_round_trip,
    run_prompt_source_checks,
)


def render_observability_tab(context: WriteProtectContext) -> None:
    """Render unified Observability tab with all diagnostic tools."""
    st.header("🔍 Observability")
    st.caption("Traces, service health, logs, feedback analytics, and testing")

    # Sub-tabs for different observability concerns
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Trace Viewer",
        "💚 Service Health",
        "📜 Log Tailer",
        "📈 Feedback Analytics",
        "🧪 Testing & QA",
    ])

    with tab1:
        _render_trace_viewer_tab()

    with tab2:
        _render_service_health_tab(context)

    with tab3:
        _render_log_tailer_tab(context)

    with tab4:
        _render_feedback_analytics_tab(context)

    with tab5:
        _render_testing_qa_tab(context)


def _render_trace_viewer_tab() -> None:
    """Render Trace Viewer with waterfall visualization."""
    st.subheader("Trace Viewer")
    st.caption("Waterfall visualization of unified ORS traces (Dev Explorer + UCN/RR + Core)")

    # Mode selector
    mode_cols = st.columns([2, 2, 1])
    with mode_cols[0]:
        view_mode = st.radio(
            "View Mode",
            options=["Search & List", "Trace Details"],
            horizontal=True,
            key="_trace_view_mode",
        )

    if view_mode == "Search & List":
        # Trace search and list
        st.markdown("---")
        st.markdown("**Search Traces**")
        render_trace_search()

        st.markdown("---")
        st.markdown("**Recent Traces**")
        selected_trace_id = render_trace_list()

        if selected_trace_id:
            st.session_state["_trace_view_mode"] = "Trace Details"
            st.session_state["_selected_trace_id"] = selected_trace_id
            st.rerun()

    else:
        # Trace details with waterfall
        trace_id = st.session_state.get("_selected_trace_id", "")

        col1, col2 = st.columns([3, 1])
        with col1:
            trace_id_input = st.text_input(
                "Trace ID",
                value=trace_id,
                key="_trace_id_input",
            )
        with col2:
            if st.button("← Back to List"):
                st.session_state["_trace_view_mode"] = "Search & List"
                st.rerun()

        if trace_id_input:
            st.markdown("---")
            render_trace_waterfall(trace_id_input)
        else:
            st.info("Enter a trace ID to view waterfall visualization")


def _render_service_health_tab(context: WriteProtectContext) -> None:
    """Render Service Health dashboard."""
    st.subheader("Service Health")
    st.caption("Ping microservices and view health status")

    # Use existing ORS console service ping functionality
    last_ingest = st.session_state.get("_last_ingest_payload")
    render_service_console(context, last_ingest=last_ingest)

    # Additional health metrics
    st.markdown("---")
    st.subheader("Service Uptime")

    # Load service settings to get base URLs
    from ExplorerDev.diag_utils import load_service_settings
    service_state = load_service_settings()

    uptime_data = []
    services = [
        ("UCNRR", service_state.get("ucnrr_base", "")),
        ("Core", service_state.get("core_base", "")),
        ("LLM", service_state.get("llm_base", "")),
    ]

    for service_name, base_url in services:
        if not base_url:
            continue

        # Check if we have recent ping results
        ping_results = st.session_state.get("_ors_ping_results", {})
        service_key = service_name.lower()

        if service_key in ping_results:
            result = ping_results[service_key]
            status = "🟢 Online" if result.get("ok") else "🔴 Offline"
            latency = result.get("latency_ms", 0)
        else:
            status = "⚪ Unknown"
            latency = 0

        uptime_data.append({
            "Service": service_name,
            "Base URL": base_url,
            "Status": status,
            "Latency (ms)": f"{latency:.1f}" if latency > 0 else "—",
        })

    if uptime_data and pd is not None:
        df = pd.DataFrame(uptime_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif uptime_data:
        # Fallback without pandas
        for entry in uptime_data:
            st.markdown(f"**{entry['Service']}** ({entry['Base URL']}) — {entry['Status']} — {entry['Latency (ms)']} ms")
    else:
        st.info("No service endpoints configured")


def _render_log_tailer_tab(context: WriteProtectContext) -> None:
    """Render Log Tailer with multi-source support."""
    st.subheader("Log Tailer")
    st.caption("View logs from multiple sources with auto-refresh")

    # Use existing ORS console log tailer
    render_log_tailer(context)


def _render_feedback_analytics_tab(context: WriteProtectContext) -> None:
    """Render Feedback Analytics dashboard."""
    st.subheader("Feedback Analytics")
    st.caption("Trait scores, planning weights, and ToleranceForNudging from user feedback")

    # User selector
    from ExplorerDev.snapshot_utils import get_user_list_quick
    users = get_user_list_quick()

    if not users:
        st.warning("No users found in data directory")
        return

    selected_user = st.selectbox(
        "User",
        options=users,
        key="_feedback_user",
    )

    if not selected_user:
        return

    # Load feedback data
    try:
        from ReDNACoreDemo.core import feedback_analytics
        from ExplorerFinal.core import nudge_store
    except ImportError:
        st.error("Unable to import feedback_analytics or nudge_store modules")
        return

    # Tab structure for different analytics views
    analytics_tabs = st.tabs([
        "📊 Trait Scores",
        "⚖️ Planning Weights",
        "🎚️ Tolerance for Nudging",
        "📋 Feedback Summary",
    ])

    with analytics_tabs[0]:
        _render_trait_scores(selected_user, context)

    with analytics_tabs[1]:
        _render_planning_weights(selected_user, context)

    with analytics_tabs[2]:
        _render_tolerance_for_nudging(selected_user, context)

    with analytics_tabs[3]:
        _render_feedback_summary(selected_user, context)


def _render_trait_scores(user_id: str, context: WriteProtectContext) -> None:
    """Render trait score visualization."""
    st.markdown("**Trait Feedback Scores**")
    st.caption("Aggregated feedback scores per trait (-1.0 to 1.0)")

    try:
        from ReDNACoreDemo.core import feedback_analytics

        trait_analysis = feedback_analytics.load_trait_feedback_analysis(
            user_id=user_id,
            write_protect=context.write_protect,
        )

        if not trait_analysis:
            st.info("No trait feedback data available yet")
            return

        # Convert to table format
        rows = []
        for trait_path, data in trait_analysis.items():
            rows.append({
                "Trait Path": trait_path,
                "Score": f"{data.get('score', 0.0):.3f}",
                "Helpful": data.get("helpful_count", 0),
                "Not Helpful": data.get("not_helpful_count", 0),
                "Total": data.get("total_count", 0),
            })

        if pd is not None:
            df = pd.DataFrame(rows)
            df = df.sort_values("Score", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Visualization
            if alt is not None and len(rows) > 0:
                chart_df = pd.DataFrame([
                    {
                        "Trait": row["Trait Path"][:30] + "..." if len(row["Trait Path"]) > 30 else row["Trait Path"],
                        "Score": float(row["Score"]),
                    }
                    for row in rows[:15]  # Top 15
                ])

                chart = alt.Chart(chart_df).mark_bar().encode(
                    x=alt.X("Score:Q", scale=alt.Scale(domain=[-1, 1])),
                    y=alt.Y("Trait:N", sort="-x"),
                    color=alt.condition(
                        alt.datum.Score > 0,
                        alt.value("green"),
                        alt.value("red"),
                    ),
                ).properties(height=400)

                st.altair_chart(chart, use_container_width=True)
        else:
            # Fallback without pandas
            for row in rows[:20]:
                st.markdown(f"**{row['Trait Path']}**: {row['Score']} ({row['Helpful']}↑ / {row['Not Helpful']}↓)")

    except Exception as exc:
        st.error(f"Failed to load trait scores: {exc}")


def _render_planning_weights(user_id: str, context: WriteProtectContext) -> None:
    """Render planning weights table."""
    st.markdown("**Planning Weights**")
    st.caption("Multipliers (0.5-1.5) applied to motivator planning based on feedback")

    try:
        from ReDNACoreDemo.core import feedback_analytics

        weights = feedback_analytics.get_planning_weights(
            user_id=user_id,
            write_protect=context.write_protect,
        )

        if not weights:
            st.info("No planning weights available yet")
            return

        # Convert to table
        rows = []
        for trait_path, weight in weights.items():
            impact = "Boost" if weight > 1.0 else "Reduce" if weight < 1.0 else "Neutral"
            rows.append({
                "Trait Path": trait_path,
                "Weight": f"{weight:.3f}",
                "Impact": impact,
            })

        if pd is not None:
            df = pd.DataFrame(rows)
            df = df.sort_values("Weight", ascending=False)

            # Color coding
            def color_weight(val: str) -> str:
                try:
                    weight_val = float(val)
                    if weight_val > 1.0:
                        return "background-color: #d4edda"
                    elif weight_val < 1.0:
                        return "background-color: #f8d7da"
                    else:
                        return ""
                except ValueError:
                    return ""

            styled_df = df.style.applymap(color_weight, subset=["Weight"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

        else:
            # Fallback without pandas
            for row in rows[:20]:
                st.markdown(f"**{row['Trait Path']}**: {row['Weight']} ({row['Impact']})")

        # Download option
        if not context.write_protect:
            weights_json = json.dumps(weights, indent=2)
            st.download_button(
                "Download Planning Weights (JSON)",
                data=weights_json,
                file_name=f"planning_weights_{user_id}.json",
                mime="application/json",
            )

    except Exception as exc:
        st.error(f"Failed to load planning weights: {exc}")


def _render_tolerance_for_nudging(user_id: str, context: WriteProtectContext) -> None:
    """Render ToleranceForNudging emergent trait."""
    st.markdown("**Tolerance for Nudging**")
    st.caption("Emergent trait (0.0-1.0) computed from accept/dismiss/undo patterns")

    try:
        from ReDNACoreDemo.core import feedback_analytics

        tolerance_data = feedback_analytics.compute_tolerance_for_nudging(
            user_id=user_id,
            write_protect=context.write_protect,
        )

        if not tolerance_data:
            st.info("No nudge interaction data available yet")
            return

        tolerance = tolerance_data.get("tolerance", 0.5)
        accept_count = tolerance_data.get("accept_count", 0)
        dismiss_count = tolerance_data.get("dismiss_count", 0)
        undo_count = tolerance_data.get("undo_count", 0)
        total_interactions = tolerance_data.get("total_interactions", 0)

        # Metric display
        cols = st.columns(5)
        cols[0].metric("Tolerance", f"{tolerance:.2f}")
        cols[1].metric("Accepts", accept_count)
        cols[2].metric("Dismisses", dismiss_count)
        cols[3].metric("Undos", undo_count)
        cols[4].metric("Total", total_interactions)

        # Interpretation
        if tolerance >= 0.7:
            st.success("✅ High tolerance — user engages positively with nudges")
        elif tolerance >= 0.4:
            st.info("⚖️ Moderate tolerance — user is selective about nudges")
        else:
            st.warning("⚠️ Low tolerance — reduce nudge frequency or improve relevance")

        # Gauge visualization (if altair available)
        if alt is not None:
            gauge_data = pd.DataFrame([{"value": tolerance, "label": "Tolerance"}])
            gauge = alt.Chart(gauge_data).mark_arc(innerRadius=50, outerRadius=100).encode(
                theta=alt.Theta("value:Q", scale=alt.Scale(domain=[0, 1])),
                color=alt.Color(
                    "value:Q",
                    scale=alt.Scale(domain=[0, 0.4, 0.7, 1.0], range=["red", "orange", "yellow", "green"]),
                    legend=None,
                ),
            ).properties(width=200, height=200)

            st.altair_chart(gauge, use_container_width=False)

    except Exception as exc:
        st.error(f"Failed to compute ToleranceForNudging: {exc}")


def _render_feedback_summary(user_id: str, context: WriteProtectContext) -> None:
    """Render overall feedback summary."""
    st.markdown("**Feedback Summary**")
    st.caption("High-level overview of all feedback data")

    try:
        from ReDNACoreDemo.core import feedback_analytics

        summary = feedback_analytics.load_feedback_summary(
            user_id=user_id,
            write_protect=context.write_protect,
        )

        if not summary:
            st.info("No feedback data available yet")
            return

        # Display summary metrics
        total_feedback = summary.get("total_feedback_count", 0)
        helpful_pct = summary.get("helpful_percentage", 0.0)
        trait_count = summary.get("trait_count", 0)
        avg_score = summary.get("average_score", 0.0)

        cols = st.columns(4)
        cols[0].metric("Total Feedback", total_feedback)
        cols[1].metric("Helpful %", f"{helpful_pct:.1f}%")
        cols[2].metric("Traits Tracked", trait_count)
        cols[3].metric("Avg Score", f"{avg_score:.2f}")

        # Top and bottom traits
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Top 5 Traits (Most Helpful)**")
            top_traits = summary.get("top_traits", [])
            if top_traits:
                for trait in top_traits[:5]:
                    st.markdown(f"✅ **{trait.get('path', 'Unknown')}**: {trait.get('score', 0.0):.2f}")
            else:
                st.caption("No data")

        with col2:
            st.markdown("**Bottom 5 Traits (Least Helpful)**")
            bottom_traits = summary.get("bottom_traits", [])
            if bottom_traits:
                for trait in bottom_traits[:5]:
                    st.markdown(f"❌ **{trait.get('path', 'Unknown')}**: {trait.get('score', 0.0):.2f}")
            else:
                st.caption("No data")

    except Exception as exc:
        st.error(f"Failed to load feedback summary: {exc}")


def _render_testing_qa_tab(context: WriteProtectContext) -> None:
    """Render Testing & QA tools."""
    st.subheader("Testing & QA")
    st.caption("Golden path tests, loop tests, and prompt validation")

    test_tabs = st.tabs([
        "🎯 Golden Path Test",
        "🔁 Loop Test",
        "📝 Prompt Source Checks",
    ])

    with test_tabs[0]:
        _render_golden_path_test(context)

    with test_tabs[1]:
        _render_loop_test(context)

    with test_tabs[2]:
        _render_prompt_checks(context)


def _render_golden_path_test(context: WriteProtectContext) -> None:
    """Render golden path test runner."""
    st.markdown("**Golden Path Test**")
    st.caption("End-to-end regression: enqueue → accept → draft chat → undo")

    user_id = st.text_input(
        "Test User ID",
        value="test_user_golden_path",
        key="_golden_path_user",
    )

    if st.button("▶️ Run Golden Path Test", type="primary"):
        try:
            from scripts import golden_path_test

            with st.spinner("Running golden path test..."):
                success = golden_path_test.run_golden_path_test(
                    user_id=user_id,
                    write_protect=context.write_protect,
                )

            if success:
                st.success("✅ Golden path test passed!")
            else:
                st.error("❌ Golden path test failed — check logs for details")

        except Exception as exc:
            st.error(f"Test execution failed: {exc}")


def _render_loop_test(context: WriteProtectContext) -> None:
    """Render loop test (ingest → UCN → RR → motivator)."""
    st.markdown("**Loop Test**")
    st.caption("Full pipeline: ingest → UCN → RR → motivator generation")

    from ExplorerDev.diag_utils import load_service_settings

    service_state = load_service_settings()

    # User and preset inputs
    col1, col2 = st.columns(2)
    with col1:
        user_id = st.text_input(
            "User ID",
            value="demo_user",
            key="_loop_test_user",
        )
    with col2:
        from ExplorerDev.ingest_presets import list_presets
        presets = list_presets()
        selected_preset = st.selectbox(
            "Ingest Preset",
            options=presets,
            key="_loop_test_preset",
        )

    if st.button("▶️ Run Loop Test", type="primary"):
        with st.spinner("Running loop test..."):
            try:
                result = run_loop_test(
                    user_id=user_id,
                    preset_name=selected_preset,
                    service_state=service_state,
                )

                st.markdown("---")
                st.subheader("Loop Test Results")

                # Display results
                for step_name, step_result in result.items():
                    with st.expander(f"{step_name} — {'✅' if step_result.get('ok') else '❌'}"):
                        st.json(step_result)

                # Store last ingest for service console curl snippet
                if "ingest" in result and result["ingest"].get("ok"):
                    st.session_state["_last_ingest_payload"] = result["ingest"]

            except Exception as exc:
                st.error(f"Loop test failed: {exc}")


def _render_prompt_checks(context: WriteProtectContext) -> None:
    """Render prompt source validation checks."""
    st.markdown("**Prompt Source Checks**")
    st.caption("Validate that all persona prompts are defined and accessible")

    if st.button("▶️ Run Prompt Checks", type="primary"):
        with st.spinner("Validating prompts..."):
            try:
                issues = run_prompt_source_checks()

                if not issues:
                    st.success("✅ All persona prompts are valid")
                else:
                    st.warning(f"⚠️ Found {len(issues)} issue(s)")
                    for issue in issues:
                        st.markdown(f"- **{issue.get('persona_id')}**: {issue.get('message')}")

            except Exception as exc:
                st.error(f"Prompt check failed: {exc}")


__all__ = ["render_observability_tab"]
