"""
Audit Log Viewer for Dev Explorer

Displays change history for Head Coach Ops, RR Baselines, CReDNA imports,
and provides rollback capability.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

from ExplorerDev.write_utils import WriteProtectContext


REPO_ROOT = ensure_repo_root()
LOGS_ROOT = REPO_ROOT / "data" / "dev_logs"


class AuditLogType:
    """Audit log types."""
    RR_BASELINES = "rr_baselines"
    CREDNA_IMPORT = "credna_import"
    HEAD_COACH_OPS = "head_coach_ops"
    NUDGE_ACTIONS = "nudge_actions"


def get_audit_log_path(log_type: str) -> Path:
    """Get path for an audit log type."""
    paths = {
        AuditLogType.RR_BASELINES: LOGS_ROOT / "rr_baselines_changes.log",
        AuditLogType.CREDNA_IMPORT: LOGS_ROOT / "credna_import_history.jsonl",
        AuditLogType.HEAD_COACH_OPS: LOGS_ROOT / "head_coach_ops_changes.jsonl",
        AuditLogType.NUDGE_ACTIONS: LOGS_ROOT / "nudge_actions.jsonl",
    }
    return paths.get(log_type, LOGS_ROOT / f"{log_type}.jsonl")


def load_audit_log(log_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load audit log entries.

    Args:
        log_type: Type of audit log
        limit: Maximum number of entries to return (newest first)

    Returns:
        List of log entries
    """
    path = get_audit_log_path(log_type)

    if not path.exists():
        return []

    entries: List[Dict[str, Any]] = []

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

    except FileNotFoundError:
        return []

    # Return newest first
    entries.reverse()
    return entries[:limit]


def format_timestamp(ts_str: Optional[str]) -> str:
    """Format timestamp for display."""
    if not ts_str:
        return "Unknown"

    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return ts_str


def render_rr_baselines_audit(limit: int = 50) -> None:
    """Render RR baselines change history."""
    if st is None:
        return

    st.subheader("RR Baselines Change History")

    entries = load_audit_log(AuditLogType.RR_BASELINES, limit=limit)

    if not entries:
        st.info("No RR baseline changes recorded")
        return

    st.caption(f"Showing {len(entries)} most recent changes")

    for idx, entry in enumerate(entries):
        timestamp = entry.get("timestamp", "")
        before = entry.get("before", {})
        after = entry.get("after", {})

        with st.expander(f"Change {idx + 1} - {format_timestamp(timestamp)}", expanded=(idx == 0)):
            col1, col2 = st.columns(2)

            with col1:
                st.caption("**Before**")
                before_note = before.get("note", "")
                if before_note:
                    st.text(f"Note: {before_note}")

                before_defaults = before.get("defaults", {})
                if before_defaults:
                    st.json(before_defaults)

            with col2:
                st.caption("**After**")
                after_note = after.get("note", "")
                if after_note:
                    st.text(f"Note: {after_note}")

                after_defaults = after.get("defaults", {})
                if after_defaults:
                    st.json(after_defaults)

            # Show container/trait changes
            before_containers = before.get("containers", {})
            after_containers = after.get("containers", {})

            all_containers = set(before_containers.keys()) | set(after_containers.keys())
            if all_containers:
                st.caption("**Container Changes**")
                for container in sorted(all_containers):
                    before_val = before_containers.get(container)
                    after_val = after_containers.get(container)

                    if before_val != after_val:
                        st.text(f"• {container}")
                        if before_val and after_val:
                            st.text(f"  Before: {before_val}")
                            st.text(f"  After: {after_val}")


def render_credna_import_audit(limit: int = 50) -> None:
    """Render CReDNA import history."""
    if st is None:
        return

    st.subheader("CReDNA Import History")

    entries = load_audit_log(AuditLogType.CREDNA_IMPORT, limit=limit)

    if not entries:
        st.info("No CReDNA imports recorded")
        return

    st.caption(f"Showing {len(entries)} most recent imports")

    for idx, entry in enumerate(entries):
        timestamp = entry.get("timestamp", "")
        coach_id = entry.get("coach_id", "unknown")
        status = entry.get("status", "unknown")
        source = entry.get("source", "unknown")

        with st.expander(
            f"Import {idx + 1} - {coach_id} - {format_timestamp(timestamp)}",
            expanded=(idx == 0),
        ):
            col1, col2 = st.columns([1, 2])

            with col1:
                st.text(f"Coach: {coach_id}")
                st.text(f"Status: {status}")
                st.text(f"Source: {source}")

            with col2:
                if "changes" in entry:
                    st.caption("**Changes**")
                    changes = entry["changes"]
                    st.json(changes)

                if "error" in entry:
                    st.error(f"Error: {entry['error']}")


def render_nudge_actions_audit(limit: int = 100) -> None:
    """Render nudge action history."""
    if st is None:
        return

    st.subheader("Nudge Actions History")

    entries = load_audit_log(AuditLogType.NUDGE_ACTIONS, limit=limit)

    if not entries:
        st.info("No nudge actions recorded")
        return

    st.caption(f"Showing {len(entries)} most recent actions")

    # Group by user
    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        user_id = entry.get("user_id", "unknown")
        if user_id not in by_user:
            by_user[user_id] = []
        by_user[user_id].append(entry)

    # Show user selector
    selected_user = st.selectbox(
        "Filter by user",
        options=["All"] + sorted(by_user.keys()),
        key="audit_nudge_user_filter",
    )

    # Filter entries
    if selected_user != "All":
        entries = by_user.get(selected_user, [])

    # Display table
    if entries:
        rows = []
        for entry in entries[:50]:  # Limit to 50 for table performance
            rows.append({
                "Time": format_timestamp(entry.get("ts", "")),
                "User": entry.get("user_id", ""),
                "Action": entry.get("action", ""),
                "Nudge ID": entry.get("nudge_id", "")[:16],
                "Actor": entry.get("actor", ""),
            })

        st.dataframe(rows, use_container_width=True)


def render_rollback_interface() -> None:
    """Render rollback interface for audit logs."""
    if st is None:
        return

    st.subheader("Rollback Operations")

    st.warning("⚠️ Rollback operations are destructive and cannot be undone without backups.")

    log_type = st.selectbox(
        "Select log type",
        options=[
            AuditLogType.RR_BASELINES,
            AuditLogType.CREDNA_IMPORT,
        ],
        key="rollback_log_type",
    )

    entries = load_audit_log(log_type, limit=20)

    if not entries:
        st.info(f"No {log_type} changes available for rollback")
        return

    # Show entries with rollback button
    st.caption("Select a change to rollback to:")

    for idx, entry in enumerate(entries):
        timestamp = entry.get("timestamp", "")
        before = entry.get("before", {})

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.text(f"{idx + 1}. {format_timestamp(timestamp)}")
                if "note" in before:
                    st.caption(f"Note: {before['note']}")

            with col2:
                if st.button(f"Rollback to #{idx + 1}", key=f"rollback_{log_type}_{idx}"):
                    st.error("Rollback not yet implemented - requires write_protect=false and confirmation")
                    # TODO: Implement actual rollback logic
                    # This would require:
                    # 1. Load 'before' state
                    # 2. Apply to current config
                    # 3. Save with new audit entry
                    # 4. Verify integrity


def render_audit_viewer_tab() -> None:
    """Render complete audit viewer tab."""
    if st is None:
        return

    st.title("🔍 Audit Log Viewer")

    st.markdown("""
    View change history for system configurations and operations.
    All changes are logged with timestamps and before/after states.
    """)

    tab1, tab2, tab3, tab4 = st.tabs([
        "RR Baselines",
        "CReDNA Imports",
        "Nudge Actions",
        "Rollback",
    ])

    with tab1:
        render_rr_baselines_audit()

    with tab2:
        render_credna_import_audit()

    with tab3:
        render_nudge_actions_audit()

    with tab4:
        render_rollback_interface()


__all__ = [
    "AuditLogType",
    "load_audit_log",
    "render_audit_viewer_tab",
    "render_rr_baselines_audit",
    "render_credna_import_audit",
    "render_nudge_actions_audit",
    "render_rollback_interface",
]
