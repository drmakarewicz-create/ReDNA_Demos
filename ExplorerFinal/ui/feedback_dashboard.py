"""Feedback analytics dashboard for the Explorer UI."""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:  # optional dependencies for richer visualisation
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None

try:
    import altair as alt  # type: ignore
except Exception:  # pragma: no cover
    alt = None

from ExplorerFinal.core import nudge_store
from ExplorerFinal.ui.components import write_protect_enabled

_DEV_TRUE = {"1", "true", "yes", "on"}

try:
    from ExplorerDev.schema_utils import get_flag_bool
except Exception:  # pragma: no cover - fallback if ExplorerDev missing
    def get_flag_bool(name: str, default: bool = False):
        env_val = os.getenv(name)
        if env_val is not None:
            token = env_val.strip().lower()
            if token in _DEV_TRUE:
                return True, "env"
            if token in {"0", "false", "no", "off"}:
                return False, "env"
        return default, "default"


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def render_feedback_dashboard(*, default_user: str, active_user: Optional[str] = None) -> None:
    flag_value, flag_source = get_flag_bool("FEEDBACK_ENABLED", True)
    if not flag_value:
        st.info("Feedback capture is disabled. Enable FEEDBACK_ENABLED in Control Panel Plus to view analytics.")
        return

    st.markdown("### Feedback Dashboard")
    st.caption(f"FEEDBACK_ENABLED (source: {flag_source})")
    write_protect_state, write_protect_source = write_protect_enabled()
    st.caption(
        f"WRITE_PROTECT: {'on' if write_protect_state else 'off'} (source: {write_protect_source})"
    )

    today = datetime.utcnow().date()
    default_start = today - timedelta(days=21)
    date_range = st.date_input(
        "Date range",
        value=(default_start, today),
        max_value=today,
        key="feedback_date_range",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start, today
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    filters_col1, filters_col2, filters_col3 = st.columns(3)
    with filters_col1:
        persona_filter = st.text_input("Filter persona", key="feedback_persona_filter").strip()
    with filters_col2:
        user_filter = st.text_input("Filter user", value=active_user or default_user, key="feedback_user_filter").strip()
    with filters_col3:
        show_notes_only = st.checkbox("Notes only", value=False, key="feedback_notes_only")

    feedback_entries = nudge_store.load_feedback_entries(
        limit=None,
        user_id=user_filter or None,
        newest_first=False,
        write_protect=write_protect_state,
    )
    filtered_entries: List[Dict[str, Any]] = []
    for entry in feedback_entries:
        ts = _parse_ts(entry.get("ts"))
        if ts is None or ts < start_dt or ts > end_dt:
            continue
        persona_id = str(entry.get("persona_id") or "")
        if persona_filter and persona_filter not in persona_id:
            continue
        if show_notes_only and not entry.get("note"):
            continue
        entry["_ts_obj"] = ts
        filtered_entries.append(entry)

    st.caption(f"Entries displayed: {len(filtered_entries)}")

    # Metrics -----------------------------------------------------------------
    helpful = sum(1 for row in filtered_entries if row.get("rating") == "helpful")
    not_helpful = sum(1 for row in filtered_entries if row.get("rating") == "not_helpful")
    total_feedback = helpful + not_helpful

    actions = nudge_store.load_nudge_actions_log(limit=None, newest_first=False)
    accepted_actions = [row for row in actions if row.get("action") == "accept"]

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Feedback events", f"{total_feedback}")
    with metric_cols[1]:
        helpful_rate = (helpful / total_feedback * 100.0) if total_feedback else 0.0
        st.metric("Helpful %", f"{helpful_rate:.1f}%")
    with metric_cols[2]:
        st.metric("Accepted nudges", f"{len(accepted_actions)}")

    # Feedback over time ------------------------------------------------------
    timeline_counter: Dict[datetime, Tuple[int, int]] = defaultdict(lambda: [0, 0])
    for entry in filtered_entries:
        ts = entry.get("_ts_obj")
        if not isinstance(ts, datetime):
            continue
        day = datetime(ts.year, ts.month, ts.day)
        rating = entry.get("rating")
        if rating == "helpful":
            timeline_counter[day][0] += 1
        elif rating == "not_helpful":
            timeline_counter[day][1] += 1

    timeline_rows: List[Dict[str, Any]] = []
    for day, (help_count, not_count) in sorted(timeline_counter.items()):
        total = help_count + not_count
        pct = (help_count / total * 100.0) if total else 0.0
        timeline_rows.append(
            {
                "date": day,
                "helpful": help_count,
                "not_helpful": not_count,
                "helpful_pct": pct,
            }
        )

    timeline_cols = st.columns(2)
    with timeline_cols[0]:
        st.markdown("#### Helpful percentage over time")
        if timeline_rows and alt is not None:
            chart = (
                alt.Chart(timeline_rows)
                .mark_line(point=True)
                .encode(x="date:T", y="helpful_pct:Q", tooltip=["date:T", "helpful_pct:Q"])
            )
            st.altair_chart(chart, use_container_width=True)
        elif timeline_rows:
            st.table(timeline_rows)
        else:
            st.info("No feedback entries in range.")

    with timeline_cols[1]:
        st.markdown("#### Daily counts")
        if timeline_rows and alt is not None:
            counts = []
            for row in timeline_rows:
                counts.append({"date": row["date"], "label": "Helpful", "count": row["helpful"]})
                counts.append({"date": row["date"], "label": "Not helpful", "count": row["not_helpful"]})
            chart = (
                alt.Chart(counts)
                .mark_bar()
                .encode(x="date:T", y="count:Q", color="label:N", tooltip=["date:T", "label:N", "count:Q"])
            )
            st.altair_chart(chart, use_container_width=True)
        elif timeline_rows:
            st.table([{**row, "date": row["date"].date()} for row in timeline_rows])
        else:
            st.info("No feedback entries in range.")

    # Persona matrix ----------------------------------------------------------
    persona_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"helpful": 0, "not_helpful": 0})
    for entry in filtered_entries:
        persona_id = str(entry.get("persona_id") or "unknown")
        rating = entry.get("rating")
        if rating in ("helpful", "not_helpful"):
            persona_totals[persona_id][rating] += 1

    matrix_rows: List[Dict[str, Any]] = []
    for persona_id, data in persona_totals.items():
        total = data["helpful"] + data["not_helpful"]
        helpful_pct = (data["helpful"] / total * 100.0) if total else 0.0
        matrix_rows.append({"persona_id": persona_id, "helpful_pct": helpful_pct, "count": total})

    st.markdown("#### Persona helpfulness")
    if matrix_rows and alt is not None:
        chart = (
            alt.Chart(matrix_rows)
            .mark_bar()
            .encode(
                x=alt.X("persona_id:N", title="Persona"),
                y=alt.Y("helpful_pct:Q", title="Helpful %"),
                color="helpful_pct:Q",
                tooltip=["persona_id:N", "helpful_pct:Q", "count:Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    elif matrix_rows:
        st.table(matrix_rows)
    else:
        st.info("No persona feedback captured.")

    # Note analysis -----------------------------------------------------------
    note_terms: Counter[str] = Counter()
    for entry in filtered_entries:
        note_text = str(entry.get("note") or "").strip()
        if not note_text:
            continue
        for token in note_text.replace("\n", " ").split():
            cleaned = token.strip(".,!?:;\"'() ").lower()
            if len(cleaned) >= 3:
                note_terms[cleaned] += 1

    st.markdown("#### Top note terms")
    if note_terms:
        top_terms = note_terms.most_common(15)
        if pd is not None:
            st.dataframe(pd.DataFrame(top_terms, columns=["term", "count"]))
        else:
            st.table({"term": term, "count": count} for term, count in top_terms)
    else:
        st.info("No feedback notes available.")

    # Funnel view -------------------------------------------------------------
    total_nudges = len(actions)
    feedback_count = len(filtered_entries)
    funnel_cols = st.columns(4)
    funnel_cols[0].metric("Nudges logged", f"{total_nudges}")
    funnel_cols[1].metric("Accepted", f"{len(accepted_actions)}")
    funnel_cols[2].metric("Feedback", f"{feedback_count}")
    funnel_cols[3].metric("Helpful", f"{helpful}")

    if not filtered_entries:
        st.info("Adjust filters or generate more feedback to populate the dashboard.")


__all__ = ["render_feedback_dashboard"]
