"""Governance & Audit tab for Developer Explorer.

Provides:
- Audit Log Viewer (RR Baselines, CReDNA, Nudge Actions, User State)
- Dormancy Management (lifecycle states, heir transfer)
- Sensitivity Gating (consent, UCN thresholds)
- Provenance Explorer (diff viewer, replay)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from ExplorerDev.write_utils import WriteProtectContext
from ExplorerDev.audit_viewer import (
    AuditLogType,
    load_audit_log,
    render_rr_baselines_audit,
    render_credna_import_audit,
    render_nudge_actions_audit,
    render_rollback_interface,
)


def render_governance_tab(context: WriteProtectContext) -> None:
    """Render unified Governance & Audit tab."""
    st.header("🔐 Governance & Audit")
    st.caption("Audit logs, dormancy protocols, sensitivity gating, and provenance tracking")

    # Sub-tabs for different governance concerns
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Audit Logs",
        "⏳ Dormancy Management",
        "🔒 Sensitivity Gating",
        "🔍 Provenance Explorer",
    ])

    with tab1:
        _render_audit_logs_tab(context)

    with tab2:
        _render_dormancy_tab(context)

    with tab3:
        _render_sensitivity_tab(context)

    with tab4:
        _render_provenance_tab(context)


def _render_audit_logs_tab(context: WriteProtectContext) -> None:
    """Render audit log viewer with rollback capability."""
    st.subheader("Audit Logs")
    st.caption("Change history with before/after comparison and rollback capability")

    # Log type selector
    log_type_options = {
        "RR Baselines": AuditLogType.RR_BASELINES,
        "CReDNA Imports": AuditLogType.CREDNA_IMPORT,
        "Nudge Actions": AuditLogType.NUDGE_ACTIONS,
        "Head Coach Ops": AuditLogType.HEAD_COACH_OPS,
    }

    selected_log_type = st.selectbox(
        "Audit Log Type",
        options=list(log_type_options.keys()),
        key="_audit_log_type",
    )

    log_type = log_type_options[selected_log_type]

    # Limit selector
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{selected_log_type} Change History**")
    with col2:
        limit = st.number_input(
            "Max entries",
            min_value=10,
            max_value=500,
            value=50,
            step=10,
            key="_audit_limit",
        )

    st.markdown("---")

    # Render appropriate audit viewer
    if log_type == AuditLogType.RR_BASELINES:
        render_rr_baselines_audit(limit=limit)
    elif log_type == AuditLogType.CREDNA_IMPORT:
        render_credna_import_audit(limit=limit)
    elif log_type == AuditLogType.NUDGE_ACTIONS:
        render_nudge_actions_audit(limit=limit)
    elif log_type == AuditLogType.HEAD_COACH_OPS:
        _render_head_coach_ops_audit(limit=limit)

    # Rollback interface
    if not context.write_protect:
        st.markdown("---")
        st.subheader("Rollback Operations")
        st.warning("⚠️ Rollback operations are destructive. Proceed with caution.")
        render_rollback_interface()


def _render_head_coach_ops_audit(limit: int = 50) -> None:
    """Render Head Coach Ops audit log."""
    st.markdown("**Head Coach Operations Audit**")
    st.caption("Scheduler operations, batch actions, and configuration changes")

    entries = load_audit_log(AuditLogType.HEAD_COACH_OPS, limit=limit)

    if not entries:
        st.info("No Head Coach Ops audit entries found")
        return

    for idx, entry in enumerate(entries):
        timestamp = entry.get("timestamp", "")
        operation = entry.get("operation", "unknown")
        user_id = entry.get("user_id", "N/A")
        details = entry.get("details", {})

        with st.expander(f"Op {idx + 1} — {operation} — {timestamp}"):
            st.markdown(f"**User:** {user_id}")
            st.markdown(f"**Operation:** {operation}")
            st.markdown(f"**Timestamp:** {timestamp}")

            if details:
                st.markdown("**Details:**")
                st.json(details)


def _render_dormancy_tab(context: WriteProtectContext) -> None:
    """Render Dormancy Management interface."""
    st.subheader("Dormancy Management")
    st.caption("User lifecycle states and heir transfer protocols")

    # Import dormancy module
    try:
        from ReDNACoreDemo.core import dormancy
    except ImportError:
        st.error("Unable to import dormancy module — ensure it exists in ReDNACoreDemo/core/")
        return

    # Dormancy tabs
    dormancy_tabs = st.tabs([
        "📊 Lifecycle States",
        "👥 Heir Transfer",
        "⚙️ Dormancy Config",
    ])

    with dormancy_tabs[0]:
        _render_lifecycle_states(context)

    with dormancy_tabs[1]:
        _render_heir_transfer(context)

    with dormancy_tabs[2]:
        _render_dormancy_config(context)


def _render_lifecycle_states(context: WriteProtectContext) -> None:
    """Render user lifecycle state viewer."""
    st.markdown("**User Lifecycle States**")
    st.caption("View and update user activity states")

    try:
        from ReDNACoreDemo.core import dormancy
        from ExplorerDev.snapshot_utils import get_user_list_quick

        users = get_user_list_quick()

        if not users:
            st.info("No users found")
            return

        # Load lifecycle records
        lifecycle_records = dormancy.load_lifecycle_records(write_protect=context.write_protect)

        # Build table
        rows = []
        for user_id in users[:50]:  # Limit to 50 for performance
            record = lifecycle_records.get(user_id)

            if record:
                state = record.get("state", "active")
                last_activity = record.get("last_activity_date", "Unknown")
                heir_id = record.get("heir_user_id", "—")
            else:
                state = "active"
                last_activity = "Unknown"
                heir_id = "—"

            rows.append({
                "User ID": user_id,
                "State": state,
                "Last Activity": last_activity,
                "Heir": heir_id,
            })

        if pd is not None:
            df = pd.DataFrame(rows)

            # Color code states
            def color_state(val: str) -> str:
                if val == "active":
                    return "background-color: #d4edda"
                elif val == "deceased":
                    return "background-color: #f8d7da"
                elif "dormant" in val:
                    return "background-color: #fff3cd"
                return ""

            styled_df = df.style.applymap(color_state, subset=["State"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            # Fallback without pandas
            for row in rows:
                st.markdown(f"**{row['User ID']}**: {row['State']} (Last: {row['Last Activity']}, Heir: {row['Heir']})")

        # State update interface
        if not context.write_protect:
            st.markdown("---")
            st.markdown("**Update Lifecycle State**")

            col1, col2, col3 = st.columns(3)
            with col1:
                update_user = st.selectbox(
                    "User ID",
                    options=users,
                    key="_lifecycle_update_user",
                )
            with col2:
                new_state = st.selectbox(
                    "New State",
                    options=[s.value for s in dormancy.LifecycleState],
                    key="_lifecycle_new_state",
                )
            with col3:
                if st.button("Update State"):
                    try:
                        dormancy.update_lifecycle_state(
                            user_id=update_user,
                            new_state=dormancy.LifecycleState(new_state),
                            write_protect=context.write_protect,
                        )
                        st.success(f"Updated {update_user} to {new_state}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to update state: {exc}")

    except Exception as exc:
        st.error(f"Failed to load lifecycle states: {exc}")


def _render_heir_transfer(context: WriteProtectContext) -> None:
    """Render heir transfer interface."""
    st.markdown("**Heir Transfer**")
    st.caption("Execute inheritance of ReDNA traits from deceased users")

    try:
        from ReDNACoreDemo.core import dormancy
        from ExplorerDev.snapshot_utils import get_user_list_quick

        users = get_user_list_quick()

        if not users:
            st.info("No users found")
            return

        # Transfer interface
        col1, col2 = st.columns(2)
        with col1:
            deceased_user = st.selectbox(
                "Deceased User",
                options=users,
                key="_heir_deceased",
            )
        with col2:
            heir_user = st.selectbox(
                "Heir User",
                options=[u for u in users if u != deceased_user],
                key="_heir_user",
            )

        # Trait selection
        st.markdown("**Traits to Transfer**")
        trait_input = st.text_area(
            "Trait IDs (one per line)",
            placeholder="PhotoPreferences.lighting_style\nPersonalityProfile.openness",
            key="_heir_traits",
        )

        traits_to_transfer = [
            line.strip()
            for line in trait_input.split("\n")
            if line.strip()
        ]

        if traits_to_transfer:
            st.caption(f"Transferring {len(traits_to_transfer)} trait(s)")
            for trait in traits_to_transfer:
                st.markdown(f"- {trait}")

        # Reason
        transfer_reason = st.text_input(
            "Transfer Reason",
            placeholder="Will-based inheritance",
            key="_heir_reason",
        )

        # Execute transfer
        if not context.write_protect:
            if st.button("Execute Heir Transfer", type="primary", disabled=not traits_to_transfer):
                try:
                    transfer = dormancy.HeirTransfer(
                        deceased_user_id=deceased_user,
                        heir_user_id=heir_user,
                        transferred_traits=traits_to_transfer,
                        transfer_reason=transfer_reason or "Manual transfer via Dev Explorer",
                        transfer_date=datetime.now(timezone.utc).isoformat(),
                    )

                    result = dormancy.execute_heir_transfer(transfer)

                    st.success("✅ Heir transfer completed")
                    st.json(result)

                except Exception as exc:
                    st.error(f"Failed to execute heir transfer: {exc}")
        else:
            st.info("Write-protect ON — transfer operations disabled")

        # Transfer history
        st.markdown("---")
        st.markdown("**Transfer History**")

        transfer_history = dormancy.load_transfer_history(write_protect=context.write_protect)

        if transfer_history:
            for idx, transfer_record in enumerate(transfer_history[:20]):
                with st.expander(f"Transfer {idx + 1} — {transfer_record.get('deceased_user_id')} → {transfer_record.get('heir_user_id')}"):
                    st.json(transfer_record)
        else:
            st.caption("No transfer history found")

    except Exception as exc:
        st.error(f"Failed to load heir transfer interface: {exc}")


def _render_dormancy_config(context: WriteProtectContext) -> None:
    """Render dormancy configuration."""
    st.markdown("**Dormancy Configuration**")
    st.caption("Configure lifecycle thresholds and policies")

    try:
        from ReDNACoreDemo.core import dormancy

        # Load config
        config = dormancy.load_dormancy_config(write_protect=context.write_protect)

        st.markdown("**Current Configuration:**")
        st.json(config)

        # Edit interface
        if not context.write_protect:
            st.markdown("---")
            st.markdown("**Edit Configuration**")

            new_config = st.text_area(
                "Dormancy Config (JSON)",
                value=json.dumps(config, indent=2),
                height=300,
                key="_dormancy_config_edit",
            )

            if st.button("Save Configuration"):
                try:
                    parsed_config = json.loads(new_config)
                    dormancy.save_dormancy_config(parsed_config, write_protect=context.write_protect)
                    st.success("✅ Configuration saved")
                    st.rerun()
                except json.JSONDecodeError as exc:
                    st.error(f"Invalid JSON: {exc}")
                except Exception as exc:
                    st.error(f"Failed to save configuration: {exc}")

    except Exception as exc:
        st.error(f"Failed to load dormancy configuration: {exc}")


def _render_sensitivity_tab(context: WriteProtectContext) -> None:
    """Render Sensitivity Gating interface."""
    st.subheader("Sensitivity Gating")
    st.caption("Manage consent records and UCN threshold unlocking for sensitive traits")

    # Import sensitivity module
    try:
        from ReDNACoreDemo.core import sensitivity_gating
    except ImportError:
        st.error("Unable to import sensitivity_gating module — ensure it exists in ReDNACoreDemo/core/")
        return

    # Sensitivity tabs
    sensitivity_tabs = st.tabs([
        "🔐 Consent Records",
        "⚙️ Sensitivity Config",
        "🎚️ UCN Thresholds",
    ])

    with sensitivity_tabs[0]:
        _render_consent_records(context)

    with sensitivity_tabs[1]:
        _render_sensitivity_config(context)

    with sensitivity_tabs[2]:
        _render_ucn_thresholds(context)


def _render_consent_records(context: WriteProtectContext) -> None:
    """Render consent record viewer and editor."""
    st.markdown("**Consent Records**")
    st.caption("User consent status for sensitive traits")

    try:
        from ReDNACoreDemo.core import sensitivity_gating
        from ExplorerDev.snapshot_utils import get_user_list_quick

        users = get_user_list_quick()

        if not users:
            st.info("No users found")
            return

        selected_user = st.selectbox(
            "User ID",
            options=users,
            key="_consent_user",
        )

        consent_records = sensitivity_gating.load_consent_records(
            user_id=selected_user,
            write_protect=context.write_protect,
        )

        if not consent_records:
            st.info(f"No consent records found for {selected_user}")
        else:
            # Display as table
            rows = []
            for trait_id, consent in consent_records.items():
                rows.append({
                    "Trait ID": trait_id,
                    "Status": consent.status.value,
                    "Granted At": consent.granted_at or "—",
                    "Revoked At": consent.revoked_at or "—",
                })

            if pd is not None:
                df = pd.DataFrame(rows)

                def color_status(val: str) -> str:
                    if val == "granted":
                        return "background-color: #d4edda"
                    elif val == "revoked":
                        return "background-color: #f8d7da"
                    elif val == "pending":
                        return "background-color: #fff3cd"
                    return ""

                styled_df = df.style.applymap(color_status, subset=["Status"])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                for row in rows:
                    st.markdown(f"**{row['Trait ID']}**: {row['Status']} (Granted: {row['Granted At']}, Revoked: {row['Revoked At']})")

        # Grant/revoke interface
        if not context.write_protect:
            st.markdown("---")
            st.markdown("**Grant or Revoke Consent**")

            col1, col2, col3 = st.columns(3)
            with col1:
                trait_id_input = st.text_input(
                    "Trait ID",
                    placeholder="PhotoPreferences.location_data",
                    key="_consent_trait",
                )
            with col2:
                if st.button("✅ Grant Consent"):
                    if trait_id_input:
                        try:
                            sensitivity_gating.grant_consent(
                                user_id=selected_user,
                                trait_id=trait_id_input,
                                write_protect=context.write_protect,
                            )
                            st.success(f"Granted consent for {trait_id_input}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to grant consent: {exc}")
            with col3:
                if st.button("❌ Revoke Consent"):
                    if trait_id_input:
                        try:
                            sensitivity_gating.revoke_consent(
                                user_id=selected_user,
                                trait_id=trait_id_input,
                                write_protect=context.write_protect,
                            )
                            st.success(f"Revoked consent for {trait_id_input}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to revoke consent: {exc}")

    except Exception as exc:
        st.error(f"Failed to load consent records: {exc}")


def _render_sensitivity_config(context: WriteProtectContext) -> None:
    """Render sensitivity configuration editor."""
    st.markdown("**Sensitivity Configuration**")
    st.caption("Configure sensitivity levels and consent requirements for trait families")

    try:
        from ReDNACoreDemo.core import sensitivity_gating

        config = sensitivity_gating.load_sensitivity_registry(write_protect=context.write_protect)

        st.markdown("**Current Sensitivity Registry:**")
        st.json(config)

        # Edit interface
        if not context.write_protect:
            st.markdown("---")
            st.markdown("**Edit Sensitivity Registry**")

            new_config = st.text_area(
                "Sensitivity Registry (JSON)",
                value=json.dumps(config, indent=2),
                height=400,
                key="_sensitivity_config_edit",
            )

            if st.button("Save Sensitivity Registry"):
                try:
                    parsed_config = json.loads(new_config)
                    sensitivity_gating.save_sensitivity_registry(parsed_config, write_protect=context.write_protect)
                    st.success("✅ Sensitivity registry saved")
                    st.rerun()
                except json.JSONDecodeError as exc:
                    st.error(f"Invalid JSON: {exc}")
                except Exception as exc:
                    st.error(f"Failed to save registry: {exc}")

    except Exception as exc:
        st.error(f"Failed to load sensitivity configuration: {exc}")


def _render_ucn_thresholds(context: WriteProtectContext) -> None:
    """Render UCN threshold configuration."""
    st.markdown("**UCN Threshold Unlocking**")
    st.caption("Configure UCN thresholds for sensitive trait visibility")

    try:
        from ReDNACoreDemo.core import sensitivity_gating

        st.markdown("**How UCN Thresholds Work:**")
        st.info(
            "Sensitive traits can be gated behind UCN (User Certainty Number) thresholds. "
            "When a user's UCN for a trait exceeds the threshold, the trait becomes visible "
            "even without explicit consent (if `consent_required` is False)."
        )

        # Example threshold table
        example_thresholds = [
            {"Trait Family": "PhotoPreferences", "UCN Threshold": 0.6, "Consent Required": "No"},
            {"Trait Family": "HealthData", "UCN Threshold": 0.8, "Consent Required": "Yes"},
            {"Trait Family": "FinancialInfo", "UCN Threshold": 0.9, "Consent Required": "Yes"},
        ]

        if pd is not None:
            df = pd.DataFrame(example_thresholds)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            for row in example_thresholds:
                st.markdown(f"**{row['Trait Family']}**: UCN ≥ {row['UCN Threshold']}, Consent: {row['Consent Required']}")

        st.markdown("---")
        st.markdown("**Trait Visibility Check**")

        from ExplorerDev.snapshot_utils import get_user_list_quick
        users = get_user_list_quick()

        col1, col2, col3 = st.columns(3)
        with col1:
            check_user = st.selectbox("User ID", options=users, key="_ucn_check_user")
        with col2:
            check_trait = st.text_input("Trait ID", placeholder="PhotoPreferences.location_data", key="_ucn_check_trait")
        with col3:
            check_ucn = st.number_input("Current UCN", min_value=0.0, max_value=1.0, value=0.5, step=0.05, key="_ucn_check_value")

        if st.button("Check Visibility"):
            if check_user and check_trait:
                try:
                    is_visible = sensitivity_gating.is_trait_visible(
                        user_id=check_user,
                        trait_id=check_trait,
                        current_ucn=check_ucn,
                    )

                    if is_visible:
                        st.success(f"✅ Trait **{check_trait}** is VISIBLE to {check_user} (UCN: {check_ucn})")
                    else:
                        st.warning(f"⚠️ Trait **{check_trait}** is HIDDEN from {check_user} (UCN: {check_ucn})")

                except Exception as exc:
                    st.error(f"Visibility check failed: {exc}")

    except Exception as exc:
        st.error(f"Failed to load UCN threshold interface: {exc}")


def _render_provenance_tab(context: WriteProtectContext) -> None:
    """Render Provenance Explorer."""
    st.subheader("Provenance Explorer")
    st.caption("Diff viewer and replay capability for state changes")

    # Import provenance lab
    from ExplorerDev.provenance_lab import render_provenance_lab

    # Get repo root
    from ExplorerDev.bootstrap import ensure_repo_root
    repo_root = ensure_repo_root()

    # Render existing provenance lab
    render_provenance_lab(repo_root)


__all__ = ["render_governance_tab"]
