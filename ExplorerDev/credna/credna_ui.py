"""Streamlit UI for the CReDNA (Coach ReDNA) Studio."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

import streamlit as st

from ExplorerDev import schema_utils
from ExplorerDev.credna import credna_import, credna_ops, credna_reports, credna_store
from ExplorerDev.credna.ctg import compute_coverage, to_graph
from ExplorerDev.write_utils import WriteProtectContext

SESSION_COACH_KEY = "_credna_selected_coach"
SESSION_TAB_KEY = "_credna_active_tab"
SESSION_IMPORT_PREVIEW_KEY = "_credna_import_preview"
SESSION_IMPORT_SELECTION_KEY = "_credna_import_selection"
SESSION_LIVE_USER_KEY = "_credna_live_user"
SESSION_LAST_SNAPSHOT = "_credna_last_snapshot"


def render_credna_studio(context: WriteProtectContext) -> None:
    registry = credna_store.load_registry(context)
    coaches = credna_ops.list_coaches(registry)

    if not coaches:
        st.info("No CReDNA coaches registered yet. Import traits from persona contracts to get started.")
        return

    selected_coach = _select_coach(coaches)
    coach = credna_ops.get_coach(registry, selected_coach)
    if coach is None:
        st.error(f"Coach `{selected_coach}` not found in registry.")
        return

    graph = to_graph(coach)
    coverage = compute_coverage(coach)

    left_col, main_col, actions_col = st.columns([1.1, 2.4, 1.2])

    with left_col:
        _render_coach_summary(coaches, registry, selected_coach)

    with main_col:
        _render_main_tabs(coach, selected_coach, graph, coverage, registry, context)

    with actions_col:
        _render_actions_panel(registry, coach, selected_coach, context)


def _select_coach(coaches: List[str]) -> str:
    if st.session_state.get(SESSION_COACH_KEY) not in coaches:
        st.session_state[SESSION_COACH_KEY] = coaches[0]
    selected = st.radio(
        "Coaches",
        options=coaches,
        index=coaches.index(st.session_state[SESSION_COACH_KEY]),
        key=SESSION_COACH_KEY,
    )
    return selected


def _render_coach_summary(coaches: List[str], registry: Mapping[str, Any], selected: str) -> None:
    st.subheader("Coach Registry")
    for coach_id in coaches:
        coach = credna_ops.get_coach(registry, coach_id) or {}
        stats = compute_coverage(coach)
        mapped = stats.get("mapped_to_core", 0)
        total = stats.get("total_traits", 0)
        with st.container():
            color = "#20c997" if mapped and total else "#6c757d"
            st.markdown(
                f"<div style='padding:0.35rem;border-radius:0.5rem;"
                f"border:1px solid rgba(0,0,0,0.08);background:{'rgba(32,201,151,0.08)' if coach_id == selected else '#fff'}'>"
                f"<strong>{coach_id}</strong><br><span style='font-size:0.8rem;color:{color};'>"
                f"{mapped}/{total} mapped</span></div>",
                unsafe_allow_html=True,
            )


def _render_main_tabs(
    coach: Mapping[str, Any],
    coach_id: str,
    graph: Mapping[str, Any],
    coverage: Mapping[str, Any],
    registry: Mapping[str, Any],
    context: WriteProtectContext,
) -> None:
    tabs = st.tabs(["Trait Graph", "Coverage", "Live Snapshot"])
    _render_trait_graph_tab(tabs[0], graph)
    reports_enabled, _ = schema_utils.get_flag_bool("CREDNA_REPORTS_ENABLED", True)
    if reports_enabled:
        _render_coverage_tab(tabs[1], coach, coach_id)
    else:
        with tabs[1]:
            st.info("Enable `CREDNA_REPORTS_ENABLED` in CP+ to view coverage reports.")
    _render_live_snapshot_tab(tabs[2], coach, coach_id, registry, context)


def _render_trait_graph_tab(tab, graph: Mapping[str, Any]) -> None:
    with tab:
        st.markdown("### Trait Graph")
        dot = _graph_to_dot(graph)
        st.graphviz_chart(dot)
        with st.expander("Nodes"):
            st.json(graph.get("nodes", []))
        with st.expander("Edges"):
            st.json(graph.get("edges", []))


def _render_coverage_tab(tab, coach: Mapping[str, Any], coach_id: str) -> None:
    with tab:
        st.markdown("### Template Coverage")
        report = credna_reports.generate_template_report({"coaches": {coach_id: coach}}, coach_id)
        if not report.get("ok"):
            st.info(report.get("error", "Coverage report unavailable."))
            return
        rows = report.get("rows", [])
        if not rows:
            st.info("No traits available for reporting yet.")
            return
        st.dataframe(rows, hide_index=True)

        csv_bytes = credna_reports.export_report_csv(report)
        json_bytes = credna_reports.export_report_json(report)
        download_cols = st.columns(2)
        with download_cols[0]:
            st.download_button(
                "Export CSV",
                data=csv_bytes,
                file_name=f"credna_{coach_id}_coverage.csv",
                mime="text/csv",
            )
        with download_cols[1]:
            st.download_button(
                "Export JSON",
                data=json_bytes,
                file_name=f"credna_{coach_id}_coverage.json",
                mime="application/json",
            )


def _render_live_snapshot_tab(
    tab,
    coach: Mapping[str, Any],
    coach_id: str,
    registry: Mapping[str, Any],
    context: WriteProtectContext,
) -> None:
    with tab:
        st.markdown("### Live Coach Snapshot")
        default_user, _ = schema_utils.get_flag_str("DEV_LOOPTEST_USER_ID", "devexp_test")
        if SESSION_LIVE_USER_KEY not in st.session_state:
            st.session_state[SESSION_LIVE_USER_KEY] = default_user

        user_id = st.text_input(
            "User id",
            value=st.session_state[SESSION_LIVE_USER_KEY],
            key="_credna_live_user_input",
        ).strip()
        st.session_state[SESSION_LIVE_USER_KEY] = user_id or default_user

        run_cols = st.columns([0.25, 0.75])
        with run_cols[0]:
            run_requested = st.button("Run snapshot", type="primary")
        with run_cols[1]:
            st.caption("Combines coach defaults with Core curiosity and resolved UCNs.")

        if run_requested and user_id:
            snapshot = credna_ops.build_coach_snapshot(
                registry,
                coach_id,
                user_id=user_id,
                core_base=schema_utils.core_base_url(),
            )
            st.session_state[SESSION_LAST_SNAPSHOT] = snapshot
        snapshot_state = st.session_state.get(SESSION_LAST_SNAPSHOT)
        if not snapshot_state:
            return
        if not snapshot_state.get("ok"):
            st.warning(snapshot_state.get("error", "Snapshot unavailable."))
            return

        data = snapshot_state.get("snapshot", {})
        coverage = data.get("coverage", {})
        st.markdown(
            f"**Coverage:** {coverage.get('mapped_to_core', 0)} mapped · "
            f"{coverage.get('with_templates', 0)} with templates · {coverage.get('total_traits', 0)} total"
        )
        if data.get("resolved_error"):
            st.info(f"Core resolved: {data['resolved_error']}")
        if data.get("curiosity_error"):
            st.info(f"Curiosity: {data['curiosity_error']}")

        rows = data.get("top_curiosity", [])
        if rows:
            st.markdown("#### Top curiosity traits")
            st.dataframe(rows, hide_index=True)
            motivators = _collect_motivators(coach, rows)
            if motivators:
                st.download_button(
                    "Copy motivators",
                    data="\n\n".join(motivators).encode("utf-8"),
                    file_name=f"credna_{coach_id}_{data.get('user_id')}_motivators.txt",
                )
        else:
            st.info("No curious traits available for this user.")


def _render_actions_panel(registry: Dict[str, Any], coach: Dict[str, Any], coach_id: str, context: WriteProtectContext) -> None:
    st.subheader("Actions")
    _render_import_controls(registry, coach_id, context)
    credna_enabled_save = credna_store.is_save_enabled()
    payload = credna_store.load_registry(context)
    bytes_data, mime, file_name = _export_registry_payload(payload)
    st.download_button(
        "Export registry",
        data=bytes_data,
        mime=mime,
        file_name=file_name,
    )

    if credna_store.can_revert():
        if st.button("Revert last change"):
            credna_store.revert_last()
            st.experimental_rerun()

    if credna_enabled_save and not context.write_protect:
        note = st.text_input("Save note", key="_credna_save_note")
        if st.button("Persist registry", type="primary"):
            current = credna_store.load_registry(context)
            try:
                credna_store.save_registry(current, context, note=note)
            except PermissionError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive guard
                st.error(f"Unable to save registry: {exc}")
            else:
                st.success("CReDNA registry saved.")
    else:
        st.caption("Saving disabled until `CREDNA_SAVE_ENABLED=true` and WRITE_PROTECT=false.")


def _render_import_controls(registry: Dict[str, Any], coach_id: str, context: WriteProtectContext) -> None:
    import_enabled, _ = schema_utils.get_flag_bool("CREDNA_IMPORT_ENABLED", False)
    if not import_enabled:
        st.caption("Enable `CREDNA_IMPORT_ENABLED` in CP+ to import from persona contracts.")
        return

    with st.expander("Import from persona contracts", expanded=False):
        personas = credna_import.list_personas()
        if not personas:
            st.info("No personas discovered in the registry.")
            return
        persona_options = {f"{item['id']} ({item['style_presets']} presets)": item["id"] for item in personas}
        persona_label = st.selectbox("Persona", list(persona_options.keys()))
        persona_id = persona_options[persona_label]

        if st.button("Preview import", key="_credna_preview_import"):
            preview = credna_import.build_import_preview(registry, coach_id, persona_id)
            st.session_state[SESSION_IMPORT_PREVIEW_KEY] = preview
            st.session_state[SESSION_IMPORT_SELECTION_KEY] = []

        preview_state = st.session_state.get(SESSION_IMPORT_PREVIEW_KEY)
        if isinstance(preview_state, Mapping) and preview_state.get("ok"):
            suggestions = preview_state.get("suggestions", [])
            st.caption(
                f"{len(suggestions)} new trait(s) available · {preview_state.get('summary', {}).get('skipped', 0)} already present."
            )
            default_selection = st.session_state.get(SESSION_IMPORT_SELECTION_KEY, [])
            selected_ids = st.multiselect(
                "Select traits to import",
                [entry.get("trait_id") for entry in suggestions],
                default=default_selection,
            )
            st.session_state[SESSION_IMPORT_SELECTION_KEY] = selected_ids

            if selected_ids and st.button("Apply import", key="_credna_apply_import"):
                selected_traits = [entry for entry in suggestions if entry.get("trait_id") in selected_ids]
                updated_registry = credna_import.apply_import(registry, coach_id, selected_traits)
                credna_store.set_registry(updated_registry)
                st.success(f"Added {len(selected_traits)} trait(s) to coach `{coach_id}`.")
                st.session_state.pop(SESSION_IMPORT_PREVIEW_KEY, None)
                st.session_state.pop(SESSION_IMPORT_SELECTION_KEY, None)
                st.experimental_rerun()
        elif isinstance(preview_state, Mapping) and preview_state.get("error"):
            st.info(preview_state.get("error"))


def _graph_to_dot(graph: Mapping[str, Any]) -> str:
    lines = ["digraph G {", "rankdir=LR;"]
    for node in graph.get("nodes", []):
        node_id = node.get("id")
        label = node.get("label") or node_id
        weight = node.get("weight", 0)
        has_templates = "✔" if node.get("has_templates") else "✖"
        lines.append(
            f'"{node_id}" [label="{label}\\nweight={weight}\\ntemplates={has_templates}"];'
        )
    for edge in graph.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        label = edge.get("type")
        lines.append(f'"{source}" -> "{target}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


def _collect_motivators(coach: Mapping[str, Any], traits: List[Mapping[str, Any]]) -> List[str]:
    lookup = {trait_id: trait for trait_id, trait in credna_ops.coach_trait_iterator(coach)}
    motivators: List[str] = []
    for entry in traits:
        trait_id = entry.get("trait")
        trait = lookup.get(trait_id)
        if not trait:
            continue
        templates = trait.get("templates") if isinstance(trait.get("templates"), Mapping) else {}
        neutral = templates.get("neutral")
        if isinstance(neutral, str) and neutral.strip():
            motivators.append(f"[{trait_id}] {neutral.strip()}")
    return motivators


def _export_registry_payload(payload: Mapping[str, Any]) -> Tuple[bytes, str, str]:
    try:
        import yaml  # type: ignore

        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        return text.encode("utf-8"), "application/x-yaml", "credna_registry.yaml"
    except Exception:
        import json

        text = json.dumps(payload, indent=2, ensure_ascii=False)
        return text.encode("utf-8"), "application/json", "credna_registry.json"


__all__ = ["render_credna_studio"]
