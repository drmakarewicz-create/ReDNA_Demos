"""Analytics Dashboards tab for Developer Explorer.

Provides comprehensive analytics across:
- Coach usage patterns
- Curiosity coverage
- Ops schedule compliance
- System health metrics
"""

from __future__ import annotations

import json
from collections import defaultdict
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

from ExplorerDev.write_utils import WriteProtectContext


def render_analytics_tab(context: WriteProtectContext) -> None:
    """Render unified Analytics tab with all dashboards."""
    st.header("📊 Analytics Dashboards")
    st.caption("Comprehensive metrics for coaches, curiosity, ops, and system health")

    # Sub-tabs for different analytics dashboards
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Coach Analytics",
        "🧠 Curiosity Coverage",
        "⏱️ Ops Compliance",
        "💚 System Health",
    ])

    with tab1:
        _render_coach_analytics(context)

    with tab2:
        _render_curiosity_coverage(context)

    with tab3:
        _render_ops_compliance(context)

    with tab4:
        _render_system_health(context)


# ============================================================================
# Coach Analytics Dashboard
# ============================================================================

def _render_coach_analytics(context: WriteProtectContext) -> None:
    """Render Coach Analytics dashboard."""
    st.subheader("Coach Usage Analytics")
    st.caption("Switch frequency, session duration, and engagement metrics")

    try:
        from ReDNACoreDemo.core import analytics_collector
    except ImportError:
        st.error("Unable to import analytics_collector module")
        return

    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Analysis Period**")
    with col2:
        days_back = st.selectbox(
            "Period",
            options=[7, 14, 30, 60, 90],
            format_func=lambda d: f"Last {d} days",
            key="_coach_analytics_days",
        )

    st.markdown("---")

    # Compute metrics
    try:
        switch_frequency = analytics_collector.compute_coach_switch_frequency(days_back=days_back)
        engagement_scores = analytics_collector.compute_coach_engagement_scores(days_back=days_back)
        session_durations = analytics_collector.compute_coach_session_durations(days_back=days_back)
    except Exception as exc:
        st.error(f"Failed to compute coach metrics: {exc}")
        return

    if not switch_frequency:
        st.info(f"No coach session data found for the last {days_back} days. Sessions will be logged as users interact with coaches.")
        return

    # Metrics summary
    total_sessions = sum(switch_frequency.values())
    most_used_coach = max(switch_frequency, key=switch_frequency.get) if switch_frequency else "N/A"
    least_used_coach = min(switch_frequency, key=switch_frequency.get) if switch_frequency else "N/A"

    metric_cols = st.columns(3)
    metric_cols[0].metric("Total Sessions", total_sessions)
    metric_cols[1].metric("Most Used Coach", most_used_coach)
    metric_cols[2].metric("Least Used Coach", least_used_coach)

    st.markdown("---")

    # Coach Switch Frequency
    st.markdown("**Coach Switch Frequency**")
    st.caption("How often each coach is used")

    if pd is not None and alt is not None:
        freq_df = pd.DataFrame([
            {"Coach": coach, "Sessions": count}
            for coach, count in sorted(switch_frequency.items(), key=lambda x: x[1], reverse=True)
        ])

        chart = alt.Chart(freq_df).mark_bar().encode(
            x=alt.X("Sessions:Q"),
            y=alt.Y("Coach:N", sort="-x"),
            color=alt.Color("Sessions:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["Coach", "Sessions"]
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)
    elif pd is not None:
        freq_df = pd.DataFrame([
            {"Coach": coach, "Sessions": count}
            for coach, count in sorted(switch_frequency.items(), key=lambda x: x[1], reverse=True)
        ])
        st.dataframe(freq_df, use_container_width=True, hide_index=True)
    else:
        for coach, count in sorted(switch_frequency.items(), key=lambda x: x[1], reverse=True):
            st.markdown(f"**{coach}**: {count} sessions")

    st.markdown("---")

    # Engagement Scores
    st.markdown("**Engagement Scores**")
    st.caption("Average engagement per coach (0.0-1.0 scale)")

    if engagement_scores:
        if pd is not None and alt is not None:
            engage_df = pd.DataFrame([
                {"Coach": coach, "Engagement": score}
                for coach, score in sorted(engagement_scores.items(), key=lambda x: x[1], reverse=True)
            ])

            chart = alt.Chart(engage_df).mark_bar().encode(
                x=alt.X("Engagement:Q", scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("Coach:N", sort="-x"),
                color=alt.condition(
                    alt.datum.Engagement > 0.7,
                    alt.value("green"),
                    alt.condition(
                        alt.datum.Engagement > 0.4,
                        alt.value("orange"),
                        alt.value("red")
                    )
                ),
                tooltip=["Coach", "Engagement"]
            ).properties(height=300)

            st.altair_chart(chart, use_container_width=True)
        else:
            for coach, score in sorted(engagement_scores.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"**{coach}**: {score:.2f}")
    else:
        st.info("No engagement data available")

    st.markdown("---")

    # Session Durations
    st.markdown("**Average Session Duration**")
    st.caption("Average time spent per coach (minutes)")

    if session_durations:
        if pd is not None:
            duration_df = pd.DataFrame([
                {"Coach": coach, "Duration (min)": f"{duration / 60:.1f}"}
                for coach, duration in sorted(session_durations.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(duration_df, use_container_width=True, hide_index=True)
        else:
            for coach, duration in sorted(session_durations.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"**{coach}**: {duration / 60:.1f} min")
    else:
        st.info("No session duration data available")

    # Export option
    if not context.write_protect:
        st.markdown("---")
        export_data = {
            "switch_frequency": switch_frequency,
            "engagement_scores": engagement_scores,
            "session_durations": {k: v / 60 for k, v in session_durations.items()},  # Convert to minutes
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days_back,
        }

        st.download_button(
            "📥 Export Coach Analytics (JSON)",
            data=json.dumps(export_data, indent=2),
            file_name=f"coach_analytics_{days_back}d.json",
            mime="application/json",
        )


# ============================================================================
# Curiosity Coverage Dashboard
# ============================================================================

def _render_curiosity_coverage(context: WriteProtectContext) -> None:
    """Render Curiosity Coverage dashboard."""
    st.subheader("Curiosity Coverage Analytics")
    st.caption("Coverage percentage, gaps, and curiosity heatmap")

    try:
        from ReDNACoreDemo.core import analytics_collector
        from ExplorerDev.snapshot_utils import get_user_list_quick
    except ImportError:
        st.error("Unable to import required modules")
        return

    # User selector
    users = get_user_list_quick()
    if not users:
        st.warning("No users found")
        return

    selected_user = st.selectbox(
        "User",
        options=users,
        key="_curiosity_coverage_user",
    )

    st.markdown("---")

    # Compute coverage
    try:
        coverage_metrics = analytics_collector.compute_curiosity_coverage(selected_user)
        gaps = analytics_collector.identify_coverage_gaps(selected_user, threshold=0.3)
    except Exception as exc:
        st.error(f"Failed to compute curiosity coverage: {exc}")
        return

    if not coverage_metrics:
        st.info(f"No trait data found for user {selected_user}")
        return

    # Summary metrics
    total_traits = sum(m.total_traits for m in coverage_metrics)
    total_with_data = sum(m.traits_with_data for m in coverage_metrics)
    overall_coverage = (total_with_data / total_traits * 100) if total_traits > 0 else 0.0

    metric_cols = st.columns(4)
    metric_cols[0].metric("Total Traits", total_traits)
    metric_cols[1].metric("Traits with Data", total_with_data)
    metric_cols[2].metric("Overall Coverage", f"{overall_coverage:.1f}%")
    metric_cols[3].metric("Coverage Gaps", len(gaps))

    st.markdown("---")

    # Coverage by Family
    st.markdown("**Coverage by Trait Family**")

    if pd is not None:
        coverage_df = pd.DataFrame([
            {
                "Family": m.trait_family,
                "Total": m.total_traits,
                "With Data": m.traits_with_data,
                "Coverage %": f"{m.coverage_percentage:.1f}%",
                "Avg UCN": f"{m.avg_ucn:.2f}",
                "Avg Curiosity": f"{m.avg_curiosity:.2f}",
            }
            for m in coverage_metrics
        ])

        # Color code coverage
        def color_coverage(val: str) -> str:
            try:
                pct = float(val.rstrip('%'))
                if pct >= 80:
                    return "background-color: #d4edda"
                elif pct >= 50:
                    return "background-color: #fff3cd"
                else:
                    return "background-color: #f8d7da"
            except ValueError:
                return ""

        styled_df = coverage_df.style.applymap(color_coverage, subset=["Coverage %"])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Visualization
        if alt is not None:
            viz_df = pd.DataFrame([
                {"Family": m.trait_family, "Coverage %": m.coverage_percentage}
                for m in coverage_metrics
            ])

            chart = alt.Chart(viz_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("Coverage %:Q"),
                color=alt.Color("Family:N", legend=alt.Legend(title="Trait Family")),
                tooltip=["Family", "Coverage %"]
            ).properties(height=400)

            st.altair_chart(chart, use_container_width=True)
    else:
        for m in coverage_metrics:
            st.markdown(f"**{m.trait_family}**: {m.coverage_percentage:.1f}% ({m.traits_with_data}/{m.total_traits})")

    st.markdown("---")

    # Coverage Gaps
    st.markdown("**Coverage Gaps (UCN < 0.3)**")
    st.caption(f"Traits with low certainty for {selected_user}")

    if gaps:
        if pd is not None:
            gaps_df = pd.DataFrame([{"Trait ID": gap} for gap in gaps[:50]])
            st.dataframe(gaps_df, use_container_width=True, hide_index=True)

            if len(gaps) > 50:
                st.info(f"Showing first 50 of {len(gaps)} gaps")
        else:
            for gap in gaps[:20]:
                st.markdown(f"- {gap}")
            if len(gaps) > 20:
                st.info(f"...and {len(gaps) - 20} more")
    else:
        st.success("✅ No coverage gaps — all traits have UCN ≥ 0.3")

    # Export
    if not context.write_protect:
        st.markdown("---")
        export_data = {
            "user_id": selected_user,
            "coverage_metrics": [
                {
                    "family": m.trait_family,
                    "total_traits": m.total_traits,
                    "traits_with_data": m.traits_with_data,
                    "coverage_percentage": m.coverage_percentage,
                    "avg_curiosity": m.avg_curiosity,
                    "avg_ucn": m.avg_ucn,
                }
                for m in coverage_metrics
            ],
            "coverage_gaps": gaps,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        st.download_button(
            "📥 Export Coverage Analysis (JSON)",
            data=json.dumps(export_data, indent=2),
            file_name=f"curiosity_coverage_{selected_user}.json",
            mime="application/json",
        )


# ============================================================================
# Ops Compliance Dashboard
# ============================================================================

def _render_ops_compliance(context: WriteProtectContext) -> None:
    """Render Ops Compliance dashboard."""
    st.subheader("Ops Schedule Compliance")
    st.caption("Schedule adherence, success rates, and missed operations")

    try:
        from ReDNACoreDemo.core import analytics_collector
    except ImportError:
        st.error("Unable to import analytics_collector module")
        return

    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Analysis Period**")
    with col2:
        days_back = st.selectbox(
            "Period",
            options=[7, 14, 30, 60],
            format_func=lambda d: f"Last {d} days",
            key="_ops_compliance_days",
        )

    st.markdown("---")

    # Compute metrics
    try:
        success_rates = analytics_collector.compute_ops_success_rate(days_back=days_back)
        adherence = analytics_collector.compute_schedule_adherence(days_back=days_back)
        ops_metrics = analytics_collector.load_ops_compliance_metrics(days_back=days_back)
    except Exception as exc:
        st.error(f"Failed to compute ops compliance: {exc}")
        return

    if not ops_metrics:
        st.info(f"No ops execution data found for the last {days_back} days. Operations will be logged as they execute.")
        return

    # Summary metrics
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total Operations", adherence.get("total_operations", 0))
    metric_cols[1].metric("On-Time %", f"{adherence.get('on_time_percentage', 0):.1f}%")
    metric_cols[2].metric("Late", adherence.get("late", 0))
    metric_cols[3].metric("Missed", adherence.get("missed", 0))

    st.markdown("---")

    # Success Rates by Operation Type
    st.markdown("**Success Rates by Operation Type**")
    st.caption("Percentage of successful completions")

    if success_rates:
        if pd is not None and alt is not None:
            success_df = pd.DataFrame([
                {"Operation": op_type, "Success Rate %": rate}
                for op_type, rate in sorted(success_rates.items(), key=lambda x: x[1], reverse=True)
            ])

            chart = alt.Chart(success_df).mark_bar().encode(
                x=alt.X("Success Rate %:Q", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Operation:N", sort="-x"),
                color=alt.condition(
                    alt.datum["Success Rate %"] > 90,
                    alt.value("green"),
                    alt.condition(
                        alt.datum["Success Rate %"] > 70,
                        alt.value("orange"),
                        alt.value("red")
                    )
                ),
                tooltip=["Operation", "Success Rate %"]
            ).properties(height=300)

            st.altair_chart(chart, use_container_width=True)
        elif pd is not None:
            success_df = pd.DataFrame([
                {"Operation": op_type, "Success Rate": f"{rate:.1f}%"}
                for op_type, rate in sorted(success_rates.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(success_df, use_container_width=True, hide_index=True)
        else:
            for op_type, rate in sorted(success_rates.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"**{op_type}**: {rate:.1f}%")
    else:
        st.info("No success rate data available")

    st.markdown("---")

    # Schedule Adherence Breakdown
    st.markdown("**Schedule Adherence Breakdown**")

    adherence_cols = st.columns(3)
    adherence_cols[0].metric("On-Time", adherence.get("on_time", 0), delta=None, help="Within 5 minutes of scheduled time")
    adherence_cols[1].metric("Late", adherence.get("late", 0), delta=None, help="More than 5 minutes late")
    adherence_cols[2].metric("Missed", adherence.get("missed", 0), delta=None, help="Did not execute")

    # Recent operations
    st.markdown("---")
    st.markdown("**Recent Operations**")

    if pd is not None:
        recent_df = pd.DataFrame([
            {
                "Operation": m.operation_type,
                "Scheduled": m.scheduled_time[:19],
                "Actual": m.actual_time[:19] if m.actual_time else "—",
                "Status": m.status,
                "User": m.user_id or "—",
            }
            for m in ops_metrics[:20]
        ])
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        for m in ops_metrics[:10]:
            st.markdown(f"**{m.operation_type}** — {m.status} — Scheduled: {m.scheduled_time[:19]}")

    # Export
    if not context.write_protect:
        st.markdown("---")
        export_data = {
            "success_rates": success_rates,
            "adherence": adherence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days_back,
        }

        st.download_button(
            "📥 Export Ops Compliance (JSON)",
            data=json.dumps(export_data, indent=2),
            file_name=f"ops_compliance_{days_back}d.json",
            mime="application/json",
        )


# ============================================================================
# System Health Dashboard
# ============================================================================

def _render_system_health(context: WriteProtectContext) -> None:
    """Render System Health dashboard."""
    st.subheader("System Health Metrics")
    st.caption("Uptime, latency, error rates, and storage")

    try:
        from ReDNACoreDemo.core import analytics_collector
    except ImportError:
        st.error("Unable to import analytics_collector module")
        return

    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Analysis Period**")
    with col2:
        hours_back = st.selectbox(
            "Period",
            options=[1, 6, 12, 24, 48, 72],
            format_func=lambda h: f"Last {h} hours",
            key="_system_health_hours",
        )

    st.markdown("---")

    # Compute metrics
    try:
        uptime = analytics_collector.compute_service_uptime(hours_back=hours_back)
        error_rates = analytics_collector.compute_error_rate(hours_back=hours_back)
        storage_sizes = analytics_collector.get_storage_size()
    except Exception as exc:
        st.error(f"Failed to compute system health: {exc}")
        return

    # Service Uptime
    st.markdown("**Service Uptime**")
    st.caption("Percentage of time each service was online")

    if uptime:
        metric_cols = st.columns(len(uptime))
        for idx, (service, uptime_pct) in enumerate(sorted(uptime.items())):
            color = "normal" if uptime_pct >= 99 else "inverse"
            metric_cols[idx].metric(service, f"{uptime_pct:.1f}%", delta=None)

        if pd is not None and alt is not None:
            uptime_df = pd.DataFrame([
                {"Service": service, "Uptime %": pct}
                for service, pct in uptime.items()
            ])

            chart = alt.Chart(uptime_df).mark_bar().encode(
                x=alt.X("Uptime %:Q", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Service:N"),
                color=alt.condition(
                    alt.datum["Uptime %"] >= 99,
                    alt.value("green"),
                    alt.value("orange")
                ),
                tooltip=["Service", "Uptime %"]
            ).properties(height=200)

            st.altair_chart(chart, use_container_width=True)
    else:
        st.info(f"No uptime data found for the last {hours_back} hours. Health metrics will be logged as services are pinged.")

    st.markdown("---")

    # Latency Percentiles
    st.markdown("**Latency Percentiles (ms)**")
    st.caption("p50, p95, p99 latency for each service")

    services = ["UCNRR", "Core", "LLM"]
    if pd is not None:
        latency_rows = []
        for service in services:
            try:
                percentiles = analytics_collector.compute_latency_percentiles(service, hours_back=hours_back)
                latency_rows.append({
                    "Service": service,
                    "p50": f"{percentiles['p50']:.1f}",
                    "p95": f"{percentiles['p95']:.1f}",
                    "p99": f"{percentiles['p99']:.1f}",
                })
            except Exception:
                latency_rows.append({
                    "Service": service,
                    "p50": "—",
                    "p95": "—",
                    "p99": "—",
                })

        latency_df = pd.DataFrame(latency_rows)
        st.dataframe(latency_df, use_container_width=True, hide_index=True)
    else:
        st.info("Install pandas for latency percentile visualization")

    st.markdown("---")

    # Error Rates
    st.markdown("**Error Rates**")
    st.caption("Percentage of requests that resulted in errors")

    if error_rates:
        if pd is not None:
            error_df = pd.DataFrame([
                {"Service": service, "Error Rate %": f"{rate:.2f}%"}
                for service, rate in sorted(error_rates.items())
            ])
            st.dataframe(error_df, use_container_width=True, hide_index=True)
        else:
            for service, rate in sorted(error_rates.items()):
                st.markdown(f"**{service}**: {rate:.2f}%")
    else:
        st.info("No error rate data available")

    st.markdown("---")

    # Storage Size
    st.markdown("**Storage Usage**")
    st.caption("Disk space used by data directories (MB)")

    if storage_sizes:
        if pd is not None:
            storage_df = pd.DataFrame([
                {"Directory": name, "Size (MB)": f"{size:.2f}"}
                for name, size in sorted(storage_sizes.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(storage_df, use_container_width=True, hide_index=True)
        else:
            for name, size in sorted(storage_sizes.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"**{name}**: {size:.2f} MB")

    # Export
    if not context.write_protect:
        st.markdown("---")
        export_data = {
            "uptime": uptime,
            "error_rates": error_rates,
            "storage_sizes": storage_sizes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_hours": hours_back,
        }

        st.download_button(
            "📥 Export System Health (JSON)",
            data=json.dumps(export_data, indent=2),
            file_name=f"system_health_{hours_back}h.json",
            mime="application/json",
        )


__all__ = ["render_analytics_tab"]
