"""Container Studio UI wiring for the Dev Explorer."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path  # type: ignore

ensure_explorerdev_on_path()

import copy
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import streamlit as st

try:  # optional dependency for richer tables
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional
    pd = None

from ExplorerDev.ai_suggester import (
    AIResponse,
    LLMConfig,
    propose_traits,
    refine_trait,
    suggest_links,
    validate_schema_hints,
)
from ExplorerDev.rr_baseline_utils import load_demo_baselines
from ExplorerDev.curiosity_utils import curiosity_chip_label, resolve_curiosity_mode
from ExplorerDev.schema_utils import (
    CoverageRow,
    LiveCuriositySnapshot,
    SchemaDiff,
    SchemaValidationResult,
    core_curiosity_status,
    build_apply_plan,
    clone_schema,
    container_metrics,
    coverage_dashboard,
    curiosity_heatmap,
    diff_schemas,
    draft_path,
    export_schema_csv,
    infer_container_category,
    impacted_traits,
    load_schema,
    load_live_curiosity_snapshot,
    locate_container,
    locate_trait,
    log_path,
    remove_container,
    remove_trait,
    resolve_baseline_mean,
    scan_core_impacts,
    upsert_container,
    upsert_trait,
    validate_schema,
)
from ExplorerDev.write_utils import WriteProtectContext, write_guard


DRAFT_KEY = "_schema_draft"
DRAFT_DIRTY_KEY = "_schema_draft_dirty"
STATE_KEY = "_container_studio_state"
MIGRATION_PREVIEW_KEY = "_container_migration_preview"
APPLY_PLAN_KEY = "_container_apply_plan_preview"
AI_FEEDBACK_KEY = "_container_ai_feedback"
SELECTED_CONTAINER_KEY = "_selected_container_id"
SELECTED_TRAIT_KEY = "_selected_trait_id"
FLASH_KEY = "_container_flash"
LIVE_MODE_KEY = "_core_curiosity_live_mode"
LIVE_USER_KEY = "_core_curiosity_user"
LIVE_SNAPSHOT_KEY = "_core_curiosity_snapshot"
LIVE_ERROR_KEY = "_core_curiosity_error"
FILTER_OBSERVATIONAL_KEY = "_studio_show_observational"
FILTER_PADNA_KEY = "_studio_show_padna"


def _render_env_lock_pill() -> None:
    st.markdown(
        "<span style='display:inline-flex;align-items:center;gap:0.35rem;"
        "padding:0.15rem 0.6rem;border-radius:999px;background:rgba(0,0,0,0.05);"
        "font-size:0.7rem;font-weight:600;' title='Change in Control Panel Plus or relaunch without env override.'>"
        "🔒 Controlled by CP+ (env)</span>",
        unsafe_allow_html=True,
    )


def _safe_rerun() -> None:
    """Trigger a rerun while supporting legacy Streamlit versions."""

    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return

    legacy_fn = getattr(st, "experimental_rerun", None)
    if callable(legacy_fn):  # pragma: no cover - backward compatibility path
        legacy_fn()


def _category_visible(category: str) -> bool:
    show_observational = st.session_state.get(FILTER_OBSERVATIONAL_KEY, True)
    show_padna = st.session_state.get(FILTER_PADNA_KEY, True)
    if category == "observational":
        return show_observational
    if category == "padna":
        return show_padna
    return True


def _container_visible(container_id: str, schema: Dict[str, Any]) -> bool:
    container = locate_container(schema, container_id)
    category = infer_container_category(container_id, container)
    return _category_visible(category)


def _fetch_live_snapshot(user_id: str, *, force: bool = False) -> Optional[LiveCuriositySnapshot]:
    if not user_id:
        st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
        st.session_state.pop(LIVE_ERROR_KEY, None)
        return None

    cached = st.session_state.get(LIVE_SNAPSHOT_KEY)
    if (
        not force
        and isinstance(cached, LiveCuriositySnapshot)
        and cached.user_id == user_id
    ):
        return cached

    snapshot = load_live_curiosity_snapshot(user_id)
    st.session_state[LIVE_SNAPSHOT_KEY] = snapshot
    st.session_state[LIVE_ERROR_KEY] = snapshot.error
    return snapshot


def _set_selected_container(
    state: "StudioState",
    container_id: Optional[str],
    *,
    clear_trait: bool = True,
    trigger_rerun: bool = False,
) -> None:
    _set_selected_container_id(container_id)
    state.selected_container = container_id
    if clear_trait:
        state.selected_trait = None
        _set_selected_trait_id(None, rerun=False)
    if trigger_rerun:
        _safe_rerun()


def _get_selected_container_id() -> Optional[str]:
    return st.session_state.get(SELECTED_CONTAINER_KEY)


def _set_selected_container_id(container_id: Optional[str]) -> None:
    st.session_state[SELECTED_CONTAINER_KEY] = container_id
    if container_id is not None:
        st.session_state.pop(f"trait_select_{container_id}", None)
    st.session_state[SELECTED_TRAIT_KEY] = None


def _get_selected_trait_id() -> Optional[str]:
    return st.session_state.get(SELECTED_TRAIT_KEY)


def _set_selected_trait_id(trait_id: Optional[str], *, rerun: bool = True) -> None:
    st.session_state[SELECTED_TRAIT_KEY] = trait_id
    if rerun:
        _safe_rerun()


def _queue_flash(level: str, message: str) -> None:
    flash_bucket = st.session_state.setdefault(FLASH_KEY, [])
    flash_bucket.append({"level": level, "message": message})


def _drain_flash() -> None:
    messages: List[Dict[str, str]] = st.session_state.pop(FLASH_KEY, [])  # type: ignore[assignment]
    for item in messages:
        level = item.get("level", "info")
        message = item.get("message", "")
        if not message:
            continue
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)


def _focus_trait_editor(
    state: "StudioState",
    draft: Dict[str, Any],
    container_id: str,
    trait_id: Optional[str],
) -> None:
    if not container_id:
        return
    _set_selected_container(state, container_id, clear_trait=False)

    if trait_id:
        container = locate_container(draft, container_id)
        if not (container and locate_trait(container, trait_id)):
            _queue_flash("info", f"Trait `{trait_id}` not found in current draft.")
            trait_id = None

    if trait_id:
        state.selected_trait = trait_id
        _set_selected_trait_id(trait_id, rerun=False)
        state.editor = {
            "action": "edit_trait",
            "container_id": container_id,
            "trait_id": trait_id,
        }
        focus_message = f"Focused: {container_id} / {trait_id}"
    else:
        state.selected_trait = None
        _set_selected_trait_id(None, rerun=False)
        state.editor = {
            "action": "edit_container",
            "container_id": container_id,
        }
        focus_message = f"Focused: {container_id} (all traits)"
    st.session_state["_scroll_to_editor"] = True
    _queue_flash("success", focus_message)
    _safe_rerun()


def _pick_focus_trait(draft: Dict[str, Any], container_id: str) -> Optional[str]:
    container = locate_container(draft, container_id)
    if not container:
        return None
    traits = container.get("traits") if isinstance(container.get("traits"), list) else []
    for trait in traits:
        coverage = str(trait.get("coverage") or "").lower()
        if coverage not in {"known", ""}:
            return trait.get("id")
    if traits:
        return traits[0].get("id")
    return None


def _render_trait_selector(
    trait_ids: Sequence[str],
    container_id: str,
    draft: Dict[str, Any],
    state: "StudioState",
    trait_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[str]:
    trait_map = trait_map or {tid: {} for tid in trait_ids}
    search_key = f"trait_search_{container_id}"
    search_form_key = f"trait_search_form_{container_id}"
    trait_select_key = f"trait_select_{container_id}"

    existing_query = st.session_state.get(search_key, "")
    with st.form(key=search_form_key):
        query = st.text_input(
            "Search traits",
            value=existing_query,
            key=f"trait_search_input_{container_id}",
            placeholder="Filter by id or label...",
        )
        submitted = st.form_submit_button("Focus first match")

    st.session_state[search_key] = query
    lowered = query.strip().lower()

    def _matches(trait_id: str) -> bool:
        if not lowered:
            return True
        meta = trait_map.get(trait_id, {})
        candidates = [trait_id.lower()]
        label = meta.get("Label") or meta.get("label")
        if isinstance(label, str):
            candidates.append(label.lower())
        return any(lowered in candidate for candidate in candidates if candidate)

    filtered_ids = [tid for tid in trait_ids if _matches(tid)]

    if submitted:
        if filtered_ids:
            _focus_trait_editor(state, draft, container_id, filtered_ids[0])
            return filtered_ids[0]
        _queue_flash("info", "No traits match the current search.")

    if not filtered_ids:
        st.caption("No traits match the current filter. Showing all traits.")
        filtered_ids = list(trait_ids)

    options = [""] + filtered_ids
    current_tid = _get_selected_trait_id() or st.session_state.get(trait_select_key, "") or ""
    if current_tid not in options:
        current_tid = ""
        st.session_state[trait_select_key] = ""
    index = options.index(current_tid) if options else 0

    def _format(option: str) -> str:
        if not option:
            return "Select a trait"
        meta = trait_map.get(option, {})
        label = meta.get("Label") or meta.get("label") or option
        coverage_label = meta.get("Coverage") or meta.get("coverage")
        return f"{option} · {label} ({coverage_label})" if coverage_label else f"{option} · {label}"

    chosen = st.selectbox(
        "Select a trait",
        options,
        index=index,
        key=trait_select_key,
        format_func=_format,
    )

    if chosen != current_tid:
        _set_selected_trait_id(chosen or None, rerun=False)
    return chosen or None


def _load_trait_snapshot(
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    container_id: Optional[str],
    trait_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not container_id or not trait_id:
        return None
    container = locate_container(draft, container_id)
    snapshot = locate_trait(container, trait_id) if container else None
    if snapshot:
        return copy.deepcopy(snapshot)
    container_live = locate_container(base_schema, container_id)
    snapshot = locate_trait(container_live, trait_id) if container_live else None
    return copy.deepcopy(snapshot) if snapshot else None


def _summarize_trait_diff(
    before: Optional[Dict[str, Any]],
    after: Dict[str, Any],
) -> List[str]:
    before = before or {}
    changes: List[str] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        if before.get(key) != after.get(key):
            before_val = before.get(key)
            after_val = after.get(key)
            changes.append(f"{key}: {before_val!r} → {after_val!r}")
    return changes


@dataclass(slots=True)
class StudioState:
    selected_container: Optional[str] = None
    selected_trait: Optional[str] = None
    editor: Optional[Dict[str, Any]] = None
    last_notification: Optional[str] = None


def render_container_studio(
    *,
    repo_root: Path,
    context: WriteProtectContext,
    llm_config: Optional[LLMConfig],
) -> None:
    st.subheader("🧬 Container Studio")
    st.caption("Manage container schemas, run validation, and prepare drafts.")
    _drain_flash()

    base_schema = load_schema(repo_root)
    draft = _ensure_draft(base_schema)

    state = _load_state(draft)
    metrics = container_metrics(draft)

    diff = diff_schemas(base_schema, draft)
    validation = validate_schema(draft)
    validation.ai_feedback = validate_schema_hints(draft)

    baseline_bundle = load_demo_baselines(repo_root)
    baseline_index = baseline_bundle.get("resolved")

    live_snapshot: Optional[LiveCuriositySnapshot] = None
    live_active = False
    live_error: Optional[str] = None

    st.markdown("#### Curiosity data source")
    mode_info = resolve_curiosity_mode(LIVE_MODE_KEY)
    core_curiosity_flag, core_health_error = core_curiosity_status()
    source_cols = st.columns([1.2, 1.6, 0.8])

    with source_cols[0]:
        if mode_info.forced:
            st.session_state[LIVE_MODE_KEY] = mode_info.effective_live
        elif LIVE_MODE_KEY not in st.session_state:
            st.session_state[LIVE_MODE_KEY] = mode_info.effective_live

        live_mode = st.toggle(
            "Live curiosity (Core)",
            value=st.session_state.get(LIVE_MODE_KEY, mode_info.effective_live),
            key=LIVE_MODE_KEY,
            help="Use live curiosity from the Core service when enabled.",
            disabled=mode_info.forced or not mode_info.flag_value,
        )
        st.caption(f"Mode: {curiosity_chip_label(mode_info)}")
        if mode_info.forced:
            _render_env_lock_pill()

    default_user = st.session_state.get(
        LIVE_USER_KEY,
        os.getenv("CORE_CURIOSITY_SAMPLE_USER", "demo_user"),
    )
    with source_cols[1]:
        user_input = st.text_input(
            "Core user id",
            value=default_user,
            key=LIVE_USER_KEY,
            disabled=not mode_info.flag_value or not mode_info.effective_live,
            help="User whose resolved traits will power live curiosity.",
        )
    with source_cols[2]:
        refresh_requested = st.button(
            "Refresh live data",
            key="refresh_live_curiosity",
            disabled=(not mode_info.flag_value)
            or (not mode_info.effective_live)
            or not user_input.strip(),
        )

    if not mode_info.flag_value:
        if mode_info.forced:
            st.info("Curiosity mode locked to simulation via CP+ environment override.")
        else:
            st.info("Curiosity engine flag is OFF (CORE_CURIOSITY_ENABLED). Using simulation data.")
        st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
        st.session_state.pop(LIVE_ERROR_KEY, None)
        st.session_state["_core_curiosity_live_enabled"] = False
    elif not mode_info.effective_live:
        st.caption("Simulation mode — using demo baselines for coverage and curiosity.")
        st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
        st.session_state.pop(LIVE_ERROR_KEY, None)
        st.session_state["_core_curiosity_live_enabled"] = False
    else:
        user_key = st.session_state.get(LIVE_USER_KEY, "").strip()
        if not user_key:
            st.info("Enter a Core user id to pull live curiosity data.")
            st.session_state["_core_curiosity_live_enabled"] = False
        else:
            snapshot = _fetch_live_snapshot(user_key, force=refresh_requested)
            live_snapshot = snapshot
            live_error = snapshot.error if snapshot else st.session_state.get(LIVE_ERROR_KEY)
            live_active = bool(snapshot and not snapshot.error)
            if core_curiosity_flag is False:
                st.warning("Live curiosity unavailable: disabled in Core /health.")
            elif live_error:
                error_lower = str(live_error).lower()
                if "404" in error_lower or "flag off" in error_lower or "disabled" in error_lower:
                    st.warning(f"Live curiosity unavailable: {live_error}")
                else:
                    st.error(f"Live curiosity fetch failed: {live_error}")
            elif core_health_error:
                st.warning(f"Core health unreachable: {core_health_error}")
            elif snapshot:
                st.caption(
                    f"Live data from Core user `{user_key}` fetched {snapshot.fetched_at}."
                )
            st.session_state["_core_curiosity_live_enabled"] = live_active

    if live_active and live_snapshot:
        st.session_state["_core_curiosity_snapshot"] = live_snapshot
    else:
        st.session_state.pop("_core_curiosity_snapshot", None)

    left_col, main_col, right_col = st.columns([1.2, 2.5, 1.7])

    with left_col:
        _render_container_list(metrics, state)

    with main_col:
        _render_coverage_dashboard(
            draft,
            baseline_index,
            state,
            live_snapshot,
        )
        st.markdown("---")
        _render_curiosity_heatmap(
            draft,
            baseline_index,
            state,
            live_snapshot,
            live_active=live_active,
        )
        st.markdown("---")
        _render_container_detail(
            draft,
            state,
            llm_config,
            baseline_index,
            live_snapshot,
            live_active=live_active,
        )

    with right_col:
        _render_editor_panel(repo_root, draft, base_schema, state, context, diff)
        st.markdown("---")
        _render_validation_panel(validation)
        st.markdown("---")
        _render_diff_summary(diff)
        st.markdown("---")
        _render_export_and_preview(
            repo_root=repo_root,
            context=context,
            base_schema=base_schema,
            draft=draft,
            diff=diff,
        )


def _ensure_draft(base_schema: Dict[str, Any]) -> Dict[str, Any]:
    if DRAFT_KEY not in st.session_state:
        st.session_state[DRAFT_KEY] = clone_schema(base_schema)
        st.session_state[DRAFT_DIRTY_KEY] = False
    return st.session_state[DRAFT_KEY]


def _load_state(draft: Dict[str, Any]) -> StudioState:
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = StudioState()
    state: StudioState = st.session_state[STATE_KEY]

    containers = [c for c in draft.get("containers", []) if isinstance(c, dict)]
    default_container = str(containers[0].get("id") or "") if containers else None

    container_id = _get_selected_container_id()
    if not container_id and default_container:
        container_id = default_container
        _set_selected_container_id(container_id)
    elif container_id:
        if not any(str(c.get("id")) == container_id for c in containers):
            container_id = default_container
            _set_selected_container_id(container_id)

    state.selected_container = container_id

    trait_id = _get_selected_trait_id()
    if container_id:
        container = locate_container(draft, container_id)
        valid_traits = {
            str(trait.get("id"))
            for trait in (container.get("traits") or [])
            if isinstance(trait, dict)
        }
        if not trait_id or trait_id not in valid_traits:
            trait_id = None
            _set_selected_trait_id(None, rerun=False)
    else:
        trait_id = None
        _set_selected_trait_id(None, rerun=False)

    state.selected_trait = trait_id
    return state


def _render_container_list(metrics: Sequence[Any], state: StudioState) -> None:
    st.markdown("#### Containers")
    if not metrics:
        st.info("No containers defined yet. Add one to get started.")
        if st.button("Add container", key="add_container_left_empty"):
            _open_editor("add_container")
        return

    if FILTER_OBSERVATIONAL_KEY not in st.session_state:
        st.session_state[FILTER_OBSERVATIONAL_KEY] = True
    if FILTER_PADNA_KEY not in st.session_state:
        st.session_state[FILTER_PADNA_KEY] = True

    filter_cols = st.columns(2)
    with filter_cols[0]:
        st.toggle(
            "Show conversational / observational",
            value=st.session_state.get(FILTER_OBSERVATIONAL_KEY, True),
            key=FILTER_OBSERVATIONAL_KEY,
            help="Hide when focusing only on biometric or legacy containers.",
        )
    with filter_cols[1]:
        st.toggle(
            "Show PaDNA / biometric (🔒)",
            value=st.session_state.get(FILTER_PADNA_KEY, True),
            key=FILTER_PADNA_KEY,
            help="Biometric-adjacent containers include sensitive governance-locked traits.",
        )

    filtered_metrics = [metric for metric in metrics if _category_visible(getattr(metric, "category", "general"))]
    if not filtered_metrics:
        st.info("No containers match the current filters; showing all for context.")
        filtered_metrics = list(metrics)

    options = [metric.container_id for metric in filtered_metrics]
    labels = {
        metric.container_id: _format_container_label(metric)
        for metric in filtered_metrics
    }
    default_idx = options.index(state.selected_container) if state.selected_container in options else 0
    selected = st.radio(
        "Select a container",
        options,
        index=default_idx,
        format_func=lambda container_id: labels.get(container_id, container_id),
        key="container_radio",
    )
    if selected != state.selected_container:
        _set_selected_container_id(selected)
        state.selected_container = selected
        state.selected_trait = None
        state.editor = None
        _safe_rerun()
        return

    st.button("Add container", key="add_container_left", on_click=_open_editor, args=("add_container",))


def _format_container_label(metric: Any) -> str:
    coverage = metric.coverage
    lock = " 🔒" if getattr(metric, "sensitive", False) else ""
    return (
        f"{metric.label or metric.container_id}{lock}\n"
        f"{metric.trait_count} traits · Known {coverage['known']} · Partial {coverage['partial']} · Unknown {coverage['unknown']}"
    )


def _render_coverage_dashboard(
    draft: Dict[str, Any],
    baseline_index: Optional[Dict[str, Any]],
    state: StudioState,
    live_snapshot: Optional[LiveCuriositySnapshot],
) -> None:
    st.markdown("#### Coverage Dashboard")
    rows = coverage_dashboard(
        draft,
        baseline_index=baseline_index,
        live_resolved=live_snapshot.resolved if live_snapshot and not live_snapshot.error else None,
    )
    if not rows:
        st.caption("No containers defined yet.")
        return

    filtered_rows: List[CoverageRow] = [row for row in rows if _container_visible(row.container_id, draft)]
    if not filtered_rows:
        st.caption("No containers match the current filters.")
        return

    table = [
        {
            "Container": row.container_label,
            "Known": row.known,
            "Partial": row.partial,
            "Unknown": row.unknown,
        }
        for row in filtered_rows
    ]
    if pd:
        st.dataframe(pd.DataFrame(table))  # type: ignore[arg-type]
    else:
        st.table(table)

    st.caption("Click a row to focus the container in the editor.")
    for row in filtered_rows:
        total = max(1, row.known + row.partial + row.unknown)
        known_pct = int(round((row.known / total) * 100))
        partial_pct = int(round((row.partial / total) * 100))
        unknown_pct = max(0, 100 - known_pct - partial_pct)
        label = (
            f"{row.container_label}\n"
            f"Known {row.known} ({known_pct}%) · Partial {row.partial} ({partial_pct}%) · "
            f"Unknown {row.unknown} ({unknown_pct}%)"
        )
        if st.button(
            label,
            key=f"coverage_focus_{row.container_id}",
            help="Open container in editor",
        ):
            trait_focus = None
            _focus_trait_editor(state, draft, row.container_id, trait_focus)
            return


def _render_curiosity_heatmap(
    draft: Dict[str, Any],
    baseline_index: Optional[Dict[str, Any]],
    state: StudioState,
    live_snapshot: Optional[LiveCuriositySnapshot],
    *,
    live_active: bool,
) -> None:
    st.markdown("#### Curiosity Heatmap (Top 10)")
    items = curiosity_heatmap(
        draft,
        baseline_index=baseline_index,
        live_snapshot=live_snapshot if live_active else None,
        top_n=10,
    )
    items = [item for item in items if _container_visible(item.container_id, draft)]
    ucn_label = "Live UCN" if live_active else "Simulated UCN"
    if live_active and live_snapshot:
        st.caption(f"Source: From Core · user `{live_snapshot.user_id}`")
    else:
        st.caption("Source: Simulated (demo baselines)")
    if not items:
        st.caption("No traits available for curiosity simulation with current filters.")
        return

    table = [
        {
            "Trait": f"{item.container_id}.{item.trait_id}",
            "Curiosity": round(item.curiosity, 3),
            ucn_label: round(item.simulated_ucn, 3),
            "Sensitive": "Yes" if item.sensitivity_flag else "No",
            "Default Decay": item.default_decay,
        }
        for item in items
    ]

    if pd:
        df = pd.DataFrame(table)  # type: ignore[arg-type]
        st.bar_chart(df.set_index("Trait")["Curiosity"])
        st.dataframe(df)
    else:
        st.table(table)

    st.caption("Click a row to focus the trait and open motivators.")
    for item in items:
        trait_label = f"{item.container_id}.{item.trait_id}"
        subtitle = (
            f"Curiosity {item.curiosity:.3f} · {ucn_label} {item.simulated_ucn:.3f} · "
            f"Sensitive {'Yes' if item.sensitivity_flag else 'No'} · Default decay {item.default_decay}"
        )
        if st.button(
            f"{trait_label}\n{subtitle}",
            key=f"curiosity_focus_{item.container_id}_{item.trait_id}",
            help="Open trait in editor",
        ):
            _focus_trait_editor(state, draft, item.container_id, item.trait_id)
            return


def _render_container_detail(
    draft: Dict[str, Any],
    state: StudioState,
    llm_config: Optional[LLMConfig],
    baseline_index: Optional[Dict[str, Any]],
    live_snapshot: Optional[LiveCuriositySnapshot],
    *,
    live_active: bool,
) -> None:
    container_id = state.selected_container
    if not container_id:
        st.info("Select or add a container to begin.")
        return

    container = locate_container(draft, container_id)
    if container is None:
        st.warning("Container not found in draft schema.")
        return

    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown(f"### {container.get('label') or container_id}")
        status = str(container.get("status") or "active").capitalize()
        st.caption(f"Status: {status}")
        if container.get("description"):
            st.write(container.get("description"))

    with header_cols[1]:
        st.button("Edit container", key=f"edit_container_{container_id}", on_click=_open_editor, kwargs={"action": "edit_container", "container_id": container_id})
        st.button(
            "Deprecate",
            key=f"deprecate_container_{container_id}",
            on_click=_open_editor,
            kwargs={"action": "deprecate_container", "container_id": container_id},
        )
        st.button(
            "Remove",
            key=f"remove_container_{container_id}",
            on_click=_open_editor,
            kwargs={"action": "remove_container", "container_id": container_id},
        )

    traits = container.get("traits") if isinstance(container.get("traits"), list) else []
    tone_preference = str(st.session_state.get("_sandbox_last_tone", "neutral")).lower()
    if tone_preference not in {"gentle", "neutral", "blunt"}:
        tone_preference = "neutral"
    rows: List[Dict[str, Any]] = []
    ucn_label = "Live UCN" if live_active else "Simulated UCN"
    live_resolved = (
        live_snapshot.resolved if live_snapshot and not live_snapshot.error else {}
    )
    for trait in traits:
        if not isinstance(trait, dict):
            continue
        trait_id = str(trait.get("id"))
        if live_active and isinstance(live_resolved, dict):
            entry = live_resolved.get(trait_id)
        else:
            entry = None

        if isinstance(entry, dict) and live_active:
            try:
                resolved_ucn = float(entry.get("ucn", 0.0))
            except (TypeError, ValueError):
                resolved_ucn = 0.0
            normalized_ucn = max(0.0, min(resolved_ucn, 100.0)) / 100.0
            curiosity_value = entry.get("curiosity")
            try:
                blended_curiosity = float(curiosity_value if curiosity_value is not None else 1.0 - normalized_ucn)
            except (TypeError, ValueError):
                blended_curiosity = 1.0 - normalized_ucn
        else:
            simulated_ucn = resolve_baseline_mean(baseline_index, container_id, trait_id) or 0.0
            normalized_ucn = max(0.0, min(simulated_ucn, 1.0))
            base_curiosity = 1.0 - normalized_ucn
            override_curiosity = trait.get("default_curiosity")
            if isinstance(override_curiosity, (int, float)):
                blended_curiosity = (float(override_curiosity) + base_curiosity) / 2.0
            else:
                blended_curiosity = base_curiosity
        blended_curiosity = max(0.0, min(blended_curiosity, 1.0))
        rows.append(
            {
                "ID": trait_id,
                "Label": trait.get("label"),
                "Type": trait.get("type"),
                "Decay": trait.get("decay"),
                "Sensitivity": trait.get("sensitivity"),
                ucn_label: round(normalized_ucn, 3),
                "Curiosity Score": round(blended_curiosity, 3),
                "Coverage": trait.get("coverage"),
                "Default Decay": trait.get("default_decay", "inherit"),
                "Default Curiosity": trait.get("default_curiosity"),
                "Sensitive?": bool(trait.get("sensitivity_flag", False)),
                "Motivators": ", ".join(sorted((trait.get("motivators") or {}).keys()))
                if isinstance(trait.get("motivators"), dict)
                else "",
                "Computed": bool(trait.get("computed")),
                "Updated": trait.get("last_updated"),
                "Status": trait.get("status", "active"),
            }
        )

    st.markdown("#### Traits")
    if rows:
        if pd:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)  # type: ignore[arg-type]
        else:
            st.table(rows)

        trait_map = {row["ID"]: row for row in rows if row.get("ID")}
        trait_ids = list(trait_map.keys())
        chosen_trait = _render_trait_selector(trait_ids, container_id, draft, state, trait_map)
        state.selected_trait = chosen_trait
        if chosen_trait:
            state.editor = {
                "action": "edit_trait",
                "container_id": container_id,
                "trait_id": chosen_trait,
            }
        else:
            state.editor = None
    else:
        st.info("This container has no traits yet. Use AI assist or the editor to add one.")
        state.selected_trait = None
        _set_selected_trait_id(None, rerun=False)

    action_cols = st.columns(4)
    action_cols[0].button(
        "Add trait",
        key=f"add_trait_{container_id}",
        on_click=_open_editor,
        kwargs={"action": "add_trait", "container_id": container_id},
    )
    action_cols[1].button(
        "Edit",
        key=f"edit_trait_{container_id}",
        disabled=state.selected_trait is None,
        on_click=_open_editor,
        kwargs={
            "action": "edit_trait",
            "container_id": container_id,
            "trait_id": state.selected_trait,
        },
    )
    action_cols[2].button(
        "Deprecate",
        key=f"deprecate_trait_{container_id}",
        disabled=state.selected_trait is None,
        on_click=_open_editor,
        kwargs={
            "action": "deprecate_trait",
            "container_id": container_id,
            "trait_id": state.selected_trait,
        },
    )
    action_cols[3].button(
        "Remove",
        key=f"remove_trait_{container_id}",
        disabled=state.selected_trait is None,
        on_click=_open_editor,
        kwargs={
            "action": "remove_trait",
            "container_id": container_id,
            "trait_id": state.selected_trait,
        },
    )

    st.markdown("#### AI Assist")
    prompt = st.text_area(
        "Prompt for proposals",
        key=f"trait_prompt_{container_id}",
        placeholder="Describe desired traits, gaps, or refinements...",
    )
    assist_cols = st.columns(3)

    if assist_cols[0].button("Propose traits", key=f"ai_propose_{container_id}"):
        existing_ids = [row["ID"] for row in rows]
        response = propose_traits(
            container_id=container_id,
            prompt=prompt,
            existing_ids=existing_ids,
            llm=llm_config,
        )
        _apply_ai_traits(draft, container_id, response)

    if assist_cols[1].button("Refine trait", key=f"ai_refine_{container_id}", disabled=state.selected_trait is None):
        trait = locate_trait(container, state.selected_trait or "")
        if trait:
            response = refine_trait(trait=trait, prompt=prompt, llm=llm_config)
            _apply_ai_refinement(draft, container_id, response)

    if assist_cols[2].button("Link traits", key=f"ai_link_{container_id}", disabled=len(rows) < 2):
        selected_ids = [row["ID"] for row in rows]
        response = suggest_links(
            container_id=container_id,
            trait_ids=selected_ids,
            prompt=prompt,
            llm=llm_config,
        )
        _apply_ai_links(draft, container_id, response)

    ai_feedback: List[str] = st.session_state.get(AI_FEEDBACK_KEY, [])
    for message in ai_feedback:
        st.info(message)
    st.session_state[AI_FEEDBACK_KEY] = []

    st.markdown("#### Mock Head Coach motivators")
    if live_active and live_snapshot:
        st.caption(f"From Core live curiosity · user `{live_snapshot.user_id}`")
    else:
        st.caption("Simulation mode — using demo baselines")
    motivator_key = f"_motivator_preview_{container_id}"
    if st.button("Generate motivator prompts", key=f"motivator_button_{container_id}"):
        top_traits = curiosity_heatmap(
            draft,
            baseline_index=baseline_index,
            live_snapshot=live_snapshot if live_active else None,
            top_n=50,
        )
        previews: List[Dict[str, Any]] = []
        for item in top_traits:
            if item.container_id != container_id:
                continue
            trait_record = locate_trait(container, item.trait_id)
            if not trait_record:
                continue
            trait_label = trait_record.get("label") or item.trait_id
            motivators = trait_record.get("motivators") if isinstance(trait_record.get("motivators"), dict) else {}
            tone_candidates = [tone_preference, "neutral", "gentle", "blunt"]
            chosen_tone = "neutral"
            prompt_template = ""
            for tone in tone_candidates:
                template_candidate = str(motivators.get(tone) or "").strip()
                if template_candidate:
                    chosen_tone = tone
                    prompt_template = template_candidate
                    break
            long_form = str(motivators.get("long", "")).strip() if isinstance(motivators, dict) else ""
            context = {
                "trait": trait_label,
                "curiosity": f"{item.curiosity:.2f}",
            }
            if prompt_template:
                try:
                    prompt_text = prompt_template.format(**context)
                except Exception:
                    prompt_text = prompt_template
            else:
                prompt_text = (
                    f"Highlight {trait_label} — curiosity is {context['curiosity']}."
                    " Encourage the user to share a concrete example."
                )
            if item.sensitivity_flag:
                prompt_text += " (Handle with extra privacy due to sensitivity.)"
            previews.append(
                {
                    "trait": trait_label,
                    "curiosity": round(item.curiosity, 3),
                    "prompt": prompt_text,
                    "tone": chosen_tone,
                    "long": long_form,
                }
            )
            if len(previews) >= 5:
                break
        st.session_state[motivator_key] = previews

    motivators = st.session_state.get(motivator_key, [])
    if motivators:
        for preview in motivators:
            tone_label = preview.get("tone", "neutral")
            st.write(f"**{preview['trait']}** · curiosity {preview['curiosity']} · tone {tone_label}")
            st.caption(preview["prompt"])
            if preview.get("long"):
                st.caption(f"Long form: {preview['long']}")


def _render_editor_panel(
    repo_root: Path,
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    state: StudioState,
    context: WriteProtectContext,
    diff: SchemaDiff,
) -> None:
    st.markdown("<div id='container-studio-editor'></div>", unsafe_allow_html=True)
    st.markdown("#### Draft controls")
    write_status = "ON" if context.write_protect else "OFF"
    st.caption(f"Write-protect: {write_status}")

    if st.button(
        "Reset draft",
        key="reset_schema_draft_btn",
    ):
        st.session_state[DRAFT_KEY] = clone_schema(base_schema)
        st.session_state[DRAFT_DIRTY_KEY] = False
        st.success("Draft reset to live schema.")
        state.editor = None
        if state.selected_container:
            st.session_state.pop(f"trait_select_{state.selected_container}", None)
        state.selected_trait = None
        _set_selected_trait_id(None, rerun=False)
        _safe_rerun()

    disabled = context.write_protect
    if st.button(
        "Save draft",
        key="save_schema_draft_btn",
        disabled=disabled,
    ):
        if disabled:
            st.error("Write-protect enabled. Disable before saving drafts to disk.")
        else:
            _save_draft(repo_root, draft, base_schema, context)

    if st.button(
        "Copy draft to clipboard",
        key="copy_schema_draft_btn",
    ):
        st.code(json.dumps(draft, indent=2))

    if state.editor:
        st.markdown("---")
        _render_editor_form(draft, base_schema, state, context)
    elif state.selected_container and state.selected_trait:
        state.editor = {
            "action": "edit_trait",
            "container_id": state.selected_container,
            "trait_id": state.selected_trait,
        }
        st.markdown("---")
        _render_editor_form(draft, base_schema, state, context)
    elif diff.has_changes():
        st.info("Draft diverges from live schema. Review changes and save when ready.")
    else:
        st.caption("Draft matches live schema.")

    with st.expander("Session state", expanded=False):
        selected_container = st.session_state.get(SELECTED_CONTAINER_KEY)
        selected_trait = st.session_state.get(SELECTED_TRAIT_KEY)
        draft_has_trait = False
        if selected_container and selected_trait:
            container = locate_container(draft, selected_container)
            draft_has_trait = bool(container and locate_trait(container, selected_trait))
        st.json(
            {
                SELECTED_CONTAINER_KEY: selected_container,
                SELECTED_TRAIT_KEY: selected_trait,
                "draft_has_trait": draft_has_trait,
            }
        )

    if st.session_state.pop("_scroll_to_editor", False):
        st.markdown(
            "<script>var el = document.getElementById('container-studio-editor'); if (el) { el.scrollIntoView({behavior: 'smooth'}); }</script>",
            unsafe_allow_html=True,
        )


def _render_editor_form(
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    state: StudioState,
    context: WriteProtectContext,
) -> None:
    editor = state.editor or {}
    action = editor.get("action")
    container_id = editor.get("container_id")
    trait_id = editor.get("trait_id")

    if container_id:
        label = f"{container_id}"
        if trait_id:
            label = f"{container_id} / {trait_id}"
        else:
            label = f"{container_id} (all traits)"
        info_cols = st.columns([5, 1])
        info_cols[0].caption(f"Editing: {label}")
        with info_cols[1]:
            if trait_id:
                copy_html = (
                    "<button class='persona-action' type='button' "
                    f"onclick=\"navigator.clipboard.writeText({json.dumps(trait_id)})\">Copy trait id</button>"
                )
                st.markdown(copy_html, unsafe_allow_html=True)
    else:
        st.caption("Editing: (nothing selected)")

    st.markdown(f"**Editor: {action.replace('_', ' ').title()}**")

    if action == "add_container":
        _container_form(draft, state, is_edit=False)
    elif action == "edit_container":
        _container_form(draft, state, is_edit=True)
    elif action == "deprecate_container":
        _deprecate_container_form(draft, state)
    elif action == "remove_container":
        _remove_container_form(draft, state)
    elif action == "add_trait":
        _trait_form(
            draft,
            base_schema,
            state,
            context,
            is_edit=False,
            pending_action=None,
        )
    elif action in {"edit_trait", "deprecate_trait", "remove_trait"}:
        _trait_form(
            draft,
            base_schema,
            state,
            context,
            is_edit=True,
            pending_action=action,
        )
    else:
        st.warning("Unsupported editor action.")


def _container_form(draft: Dict[str, Any], state: StudioState, *, is_edit: bool) -> None:
    editor = state.editor or {}
    container_id = editor.get("container_id") if is_edit else ""
    container = locate_container(draft, container_id) if is_edit else None

    with st.form(key=f"container_form_{'edit' if is_edit else 'new'}"):
        cid = st.text_input("Container ID", value=container.get("id") if container else "")
        label = st.text_input("Label", value=container.get("label") if container else "")
        description = st.text_area(
            "Description",
            value=container.get("description") if container else "",
        )
        status = st.selectbox(
            "Status",
            options=["active", "draft", "deprecated"],
            index=["active", "draft", "deprecated"].index(container.get("status", "active")) if container else 0,
        )
        submitted = st.form_submit_button("Save container")

    if submitted:
        old_id = container.get("id") if container else None
        payload = {
            "id": cid.strip(),
            "label": label.strip() or cid.strip(),
            "description": description.strip(),
            "status": status,
            "traits": container.get("traits") if container else [],
        }
        if is_edit and old_id and old_id != payload["id"]:
            remove_container(draft, old_id)
        upsert_container(draft, payload)
        st.session_state[DRAFT_DIRTY_KEY] = True
        if old_id and old_id != payload["id"]:
            st.session_state.pop(f"trait_select_{old_id}", None)
        st.session_state.pop(f"trait_select_{payload['id']}", None)
        _set_selected_container(
            state,
            payload["id"],
            clear_trait=not is_edit or (old_id is not None and old_id != payload["id"]),
            trigger_rerun=False,
        )
        state.editor = None
        st.success("Container saved to draft.")
        _safe_rerun()


def _deprecate_container_form(draft: Dict[str, Any], state: StudioState) -> None:
    container_id = state.editor.get("container_id") if state.editor else None
    container = locate_container(draft, container_id or "") if container_id else None
    if not container:
        st.warning("Container not found in draft.")
        return

    with st.form(key=f"deprecate_container_{container_id}"):
        reason = st.text_area("Reason for deprecation", placeholder="Provide context for teammates")
        submitted = st.form_submit_button("Mark as deprecated")

    if submitted:
        container["status"] = "deprecated"
        container.setdefault("notes", {})["deprecation_reason"] = reason
        st.session_state[DRAFT_DIRTY_KEY] = True
        state.editor = None
        st.success("Container marked as deprecated in draft.")
        _safe_rerun()


def _remove_container_form(draft: Dict[str, Any], state: StudioState) -> None:
    container_id = state.editor.get("container_id") if state.editor else None
    with st.form(key=f"remove_container_{container_id}"):
        confirm = st.checkbox("Confirm removal from draft")
        submitted = st.form_submit_button("Remove container")

    if submitted and confirm and container_id:
        remove_container(draft, container_id)
        st.session_state[DRAFT_DIRTY_KEY] = True
        st.session_state.pop(f"trait_select_{container_id}", None)
        if state.selected_container == container_id:
            _set_selected_container(state, None, clear_trait=True, trigger_rerun=False)
        state.editor = None
        st.success("Container removed from draft.")
        _safe_rerun()


def _trait_form(
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    state: StudioState,
    context: WriteProtectContext,
    *,
    is_edit: bool,
    pending_action: Optional[str],
) -> None:
    editor = state.editor or {}
    container_id = editor.get("container_id")
    trait_id = editor.get("trait_id")

    if not container_id:
        st.warning("Select a container first.")
        return

    container = locate_container(draft, container_id)
    if container is None:
        st.warning("Container not found in draft.")
        return

    trait_snapshot = _load_trait_snapshot(draft, base_schema, container_id, trait_id) if is_edit else None
    trait_dict: Dict[str, Any] = trait_snapshot or {}
    field_prefix = trait_id or "new_trait"

    tone_preference = str(st.session_state.get("_sandbox_last_tone", "neutral")).lower()
    if tone_preference not in {"gentle", "neutral", "blunt"}:
        tone_preference = "neutral"

    breadcrumb = f"{container_id} / {trait_dict.get('id') or trait_id or 'new_trait'}"
    st.markdown(f"**{breadcrumb}**")
    st.caption(f"Coach tone preset: {tone_preference.title()}")

    if pending_action == "deprecate_trait":
        st.warning("Deprecate requested – review details and confirm below.")
    elif pending_action == "remove_trait":
        st.warning("Remove requested – type the trait id to confirm in the danger zone below.")

    motivators_dict = trait_dict.get("motivators") if isinstance(trait_dict.get("motivators"), dict) else {}

    decay_options = ["steady", "slow", "fast", "none"]
    curiosity_options = ["baseline", "heightened", "low"]
    sensitivity_options = ["low", "medium", "high", "restricted"]
    coverage_options = ["known", "partial", "unknown"]
    decay_policy_options = ["inherit", "fast", "medium", "slow"]

    default_decay = str(trait_dict.get("decay", "steady"))
    if default_decay not in decay_options:
        default_decay = "steady"
    default_curiosity_label = str(trait_dict.get("curiosity", "baseline"))
    if default_curiosity_label not in curiosity_options:
        default_curiosity_label = "baseline"
    default_sensitivity = str(trait_dict.get("sensitivity", "medium"))
    if default_sensitivity not in sensitivity_options:
        default_sensitivity = "medium"
    default_coverage = str(trait_dict.get("coverage", "unknown"))
    if default_coverage not in coverage_options:
        default_coverage = "unknown"
    default_decay_policy = str(trait_dict.get("default_decay", "inherit"))
    if default_decay_policy not in decay_policy_options:
        default_decay_policy = "inherit"

    has_override = isinstance(trait_dict.get("default_curiosity"), (int, float))
    default_override_value = float(trait_dict.get("default_curiosity", 0.75) or 0.75)

    last_updated_default = str(
        trait_dict.get("last_updated") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    form_key = f"trait_form_{field_prefix}"
    with st.form(key=form_key):
        tid = st.text_input(
            "Trait ID",
            value=trait_dict.get("id", trait_id or ""),
            key=f"{field_prefix}__id",
        )
        label = st.text_input(
            "Label",
            value=trait_dict.get("label", trait_dict.get("id", "")),
            key=f"{field_prefix}__label",
        )
        type_value = st.text_input(
            "Type",
            value=str(trait_dict.get("type", "score")),
            key=f"{field_prefix}__type",
        )
        decay = st.selectbox(
            "Decay",
            options=decay_options,
            index=decay_options.index(default_decay),
            key=f"{field_prefix}__decay",
        )
        curiosity = st.selectbox(
            "Curiosity",
            options=curiosity_options,
            index=curiosity_options.index(default_curiosity_label),
            key=f"{field_prefix}__curiosity",
        )
        sensitivity = st.selectbox(
            "Sensitivity",
            options=sensitivity_options,
            index=sensitivity_options.index(default_sensitivity),
            key=f"{field_prefix}__sensitivity",
        )
        coverage = st.selectbox(
            "Coverage",
            options=coverage_options,
            index=coverage_options.index(default_coverage),
            key=f"{field_prefix}__coverage",
        )
        computed = st.checkbox(
            "Computed",
            value=bool(trait_dict.get("computed", False)),
            key=f"{field_prefix}__computed",
        )
        last_updated = st.text_input(
            "Last updated",
            value=last_updated_default,
            key=f"{field_prefix}__last_updated",
        )
        decay_policy = st.selectbox(
            "Default decay policy",
            options=decay_policy_options,
            index=decay_policy_options.index(default_decay_policy),
            key=f"{field_prefix}__default_decay",
        )
        use_override = st.checkbox(
            "Override curiosity",
            value=has_override,
            key=f"{field_prefix}__use_override",
        )
        override_value = st.number_input(
            "Default curiosity (0-1)",
            min_value=0.0,
            max_value=1.0,
            value=float(default_override_value),
            step=0.05,
            key=f"{field_prefix}__override_value",
        )
        sensitivity_flag = st.checkbox(
            "Mark as sensitive",
            value=bool(trait_dict.get("sensitivity_flag", False)),
            key=f"{field_prefix}__sensitivity_flag",
        )

        st.markdown("**Motivator templates by tone**")
        neutral_template = st.text_area(
            "Neutral tone",
            value=str(motivators_dict.get("neutral", "")),
            help="Use {trait} and {curiosity} placeholders.",
            height=120,
            key=f"{field_prefix}__mot_neutral",
        )
        gentle_template = st.text_area(
            "Gentle tone",
            value=str(motivators_dict.get("gentle", "")),
            help="Softer encouragement; optional.",
            height=120,
            key=f"{field_prefix}__mot_gentle",
        )
        blunt_template = st.text_area(
            "Blunt tone",
            value=str(motivators_dict.get("blunt", "")),
            help="Direct reminder; optional.",
            height=120,
            key=f"{field_prefix}__mot_blunt",
        )
        long_template = st.text_area(
            "Long form (optional)",
            value=str(motivators_dict.get("long", "")),
            help="Extended context or script when the coach needs more detail.",
            height=120,
            key=f"{field_prefix}__mot_long",
        )

        submitted = st.form_submit_button("Save trait", key=f"{field_prefix}__save_trait")

    if submitted:
        payload: Dict[str, Any] = copy.deepcopy(trait_dict)
        tid_clean = tid.strip()
        payload["id"] = tid_clean
        payload["label"] = (label or tid_clean).strip()
        payload["type"] = type_value.strip() or "score"
        payload["decay"] = decay
        payload["curiosity"] = curiosity
        payload["sensitivity"] = sensitivity
        payload["coverage"] = coverage
        payload["computed"] = bool(computed)
        payload["last_updated"] = last_updated.strip() or datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload["links"] = list(payload.get("links", []))
        payload["status"] = payload.get("status", "active")

        if decay_policy != "inherit":
            payload["default_decay"] = decay_policy
        elif "default_decay" in payload:
            payload.pop("default_decay")

        if use_override:
            payload["default_curiosity"] = round(float(override_value), 3)
        elif "default_curiosity" in payload:
            payload.pop("default_curiosity")

        if sensitivity_flag:
            payload["sensitivity_flag"] = True
        elif "sensitivity_flag" in payload:
            payload.pop("sensitivity_flag")

        motivators_payload: Dict[str, str] = {}
        for tone_key, template in (
            ("neutral", neutral_template),
            ("gentle", gentle_template),
            ("blunt", blunt_template),
            ("long", long_template),
        ):
            if template and template.strip():
                motivators_payload[tone_key] = template.strip()
        if motivators_payload:
            payload["motivators"] = motivators_payload
        elif "motivators" in payload:
            payload.pop("motivators")

        _handle_save_trait(
            draft=draft,
            base_schema=base_schema,
            container_id=container_id,
            old_trait_id=trait_id,
            payload=payload,
            previous_snapshot=trait_snapshot,
            state=state,
            context=context,
        )
        return

    if is_edit and trait_id:
        st.markdown("---")
        action_cols = st.columns(2)
        if action_cols[0].button(
            "Deprecate trait",
            key=f"{field_prefix}__deprecate",
        ):
            _handle_deprecate_trait(
                draft=draft,
                base_schema=base_schema,
                container_id=container_id,
                trait_id=trait_id,
                state=state,
                context=context,
            )
            return

        with action_cols[1]:
            remove_prompt = st.text_input(
                "Type trait id to confirm removal",
                key=f"{field_prefix}__remove_confirm",
            )
            if st.button(
                "Remove trait",
                key=f"{field_prefix}__remove",
            ):
                _handle_remove_trait(
                    draft=draft,
                    container_id=container_id,
                    trait_id=trait_id,
                    confirmation=remove_prompt,
                    state=state,
                    context=context,
                )
                return

    with st.expander("Editor debug", expanded=False):
        has_draft_record = bool(locate_trait(container, (trait_id or "")))
        st.json(
            {
                "write_protect": context.write_protect,
                "selected_container": _get_selected_container_id(),
                "selected_trait": _get_selected_trait_id(),
                "has_draft_record": has_draft_record,
            }
        )


def _handle_save_trait(
    *,
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    container_id: str,
    old_trait_id: Optional[str],
    payload: Dict[str, Any],
    previous_snapshot: Optional[Dict[str, Any]],
    state: StudioState,
    context: WriteProtectContext,
) -> None:
    trait_id = payload.get("id", "").strip()
    if not trait_id:
        st.error("Trait ID is required.")
        return

    new_payload = copy.deepcopy(payload)

    container = locate_container(draft, container_id)
    if container is None:
        st.error(f"Container `{container_id}` not found in draft.")
        return

    if old_trait_id and old_trait_id != trait_id:
        remove_trait(draft, container_id, old_trait_id)

    upsert_trait(draft, container_id, new_payload)
    st.session_state[DRAFT_DIRTY_KEY] = True

    state.selected_trait = trait_id
    _set_selected_trait_id(trait_id, rerun=False)
    st.session_state.pop(f"trait_select_{container_id}", None)
    state.editor = None

    changes = _summarize_trait_diff(previous_snapshot, new_payload)
    message = f"Trait `{trait_id}` saved to draft."
    if changes:
        joined = "; ".join(changes[:5])
        if len(changes) > 5:
            joined += "; …"
        message += f" Changes: {joined}"

    _queue_flash("success", message)
    if context.write_protect:
        _queue_flash("warning", "Write-protect ON — changes remain in the in-memory draft until saved.")

    _safe_rerun()


def _handle_deprecate_trait(
    *,
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    container_id: str,
    trait_id: str,
    state: StudioState,
    context: WriteProtectContext,
) -> None:
    snapshot = _load_trait_snapshot(draft, base_schema, container_id, trait_id)
    if snapshot is None:
        st.error(f"Trait `{trait_id}` not found.")
        return

    snapshot["status"] = "deprecated"
    snapshot["deprecated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    upsert_trait(draft, container_id, snapshot)
    st.session_state[DRAFT_DIRTY_KEY] = True

    st.session_state.pop(f"trait_select_{container_id}", None)
    state.selected_trait = None
    _set_selected_trait_id(None, rerun=False)
    state.editor = None

    _queue_flash("success", f"Trait `{trait_id}` marked as deprecated in draft.")
    if context.write_protect:
        _queue_flash("warning", "Write-protect ON — changes remain in the in-memory draft until saved.")

    _safe_rerun()


def _handle_remove_trait(
    *,
    draft: Dict[str, Any],
    container_id: str,
    trait_id: str,
    confirmation: str,
    state: StudioState,
    context: WriteProtectContext,
) -> None:
    if confirmation.strip() != trait_id:
        st.error("Type the trait id exactly to confirm removal.")
        return

    removed = remove_trait(draft, container_id, trait_id)
    if not removed:
        st.error(f"Trait `{trait_id}` not found in draft.")
        return

    st.session_state[DRAFT_DIRTY_KEY] = True
    st.session_state.pop(f"trait_select_{container_id}", None)
    state.selected_trait = None
    _set_selected_trait_id(None, rerun=False)
    state.editor = None

    _queue_flash("success", f"Trait `{trait_id}` removed from draft.")
    if context.write_protect:
        _queue_flash("warning", "Write-protect ON — changes remain in the in-memory draft until saved.")

    _safe_rerun()


def _render_validation_panel(validation: SchemaValidationResult) -> None:
    st.markdown("#### Validation")
    if validation.ok and not validation.ai_feedback:
        st.success("Schema draft passes validation checks.")
        return

    if validation.json_errors:
        st.error("JSON schema issues detected:")
        for msg in validation.json_errors:
            st.write(f"• ({msg.subject or 'root'}) {msg.message}")

    if validation.json_warnings:
        st.warning("Warnings:")
        for msg in validation.json_warnings:
            st.write(f"• ({msg.subject or 'root'}) {msg.message}")

    if validation.ai_feedback:
        st.info("AI review suggestions:")
        for msg in validation.ai_feedback:
            st.write(f"• ({msg.subject or 'context'}) {msg.message}")


def _render_diff_summary(diff: SchemaDiff) -> None:
    st.markdown("#### Draft diff vs live")
    if not diff.has_changes():
        st.caption("No changes detected.")
        return
    rows = diff.summary_rows()
    st.table(rows)


def _render_export_and_preview(
    *,
    repo_root: Path,
    context: WriteProtectContext,
    base_schema: Dict[str, Any],
    draft: Dict[str, Any],
    diff: SchemaDiff,
) -> None:
    st.markdown("#### Preview & Export")

    csv_blob = export_schema_csv(base_schema)
    st.download_button(
        "Export current schema CSV",
        data=csv_blob,
        file_name="trait_schema.csv",
        mime="text/csv",
    )

    if not diff.has_changes():
        st.session_state.pop(APPLY_PLAN_KEY, None)

    if st.button("Preview migration impact", key="preview_migration_btn"):
        impact_map = impacted_traits(diff)
        trait_ids = sorted({tid for traits in impact_map.values() for tid in traits})
        user_count, users = scan_core_impacts(repo_root, trait_ids)
        st.session_state[MIGRATION_PREVIEW_KEY] = {
            "trait_ids": trait_ids,
            "user_count": user_count,
            "users": users,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    preview = st.session_state.get(MIGRATION_PREVIEW_KEY)
    if preview:
        st.info(
            f"Preview generated {preview['generated_at']}: {preview['user_count']} user(s) impacted by"
            f" {len(preview['trait_ids'])} trait(s)."
        )
        with st.expander("Impacted users"):
            st.json(preview["users"])

    plan_btn = st.button(
        "Build apply plan (preview)",
        key="build_apply_plan_btn",
        disabled=not diff.has_changes(),
    )
    if plan_btn and diff.has_changes():
        plan = build_apply_plan(repo_root, base_schema, draft, diff)
        st.session_state[APPLY_PLAN_KEY] = plan
        st.success("Apply plan preview generated. Download below.")

    plan_preview = st.session_state.get(APPLY_PLAN_KEY)
    if plan_preview:
        plan_blob = json.dumps(plan_preview, indent=2)
        st.download_button(
            "Download apply plan preview",
            data=plan_blob,
            file_name="trait_schema_apply_plan.preview.json",
            mime="application/json",
            key="download_apply_plan_btn",
        )
        with st.expander("Apply plan details", expanded=False):
            st.json(plan_preview)


def _open_editor(action: str, *, container_id: Optional[str] = None, trait_id: Optional[str] = None) -> None:
    state: StudioState = st.session_state.setdefault(STATE_KEY, StudioState())
    state.editor = {
        "action": action,
        "container_id": container_id,
        "trait_id": trait_id,
    }


def _apply_ai_traits(draft: Dict[str, Any], container_id: str, response: AIResponse) -> None:
    if not response.traits:
        st.session_state.setdefault(AI_FEEDBACK_KEY, []).append("AI proposal did not return any traits.")
        return
    for trait in response.traits:
        try:
            upsert_trait(draft, container_id, trait)
        except Exception as exc:  # defensive guard for malformed payloads
            st.session_state.setdefault(AI_FEEDBACK_KEY, []).append(f"Skipped trait: {exc}")
    st.session_state[DRAFT_DIRTY_KEY] = True
    st.session_state.setdefault(AI_FEEDBACK_KEY, []).extend(response.messages)
    _safe_rerun()


def _apply_ai_refinement(draft: Dict[str, Any], container_id: str, response: AIResponse) -> None:
    if not response.traits:
        st.session_state.setdefault(AI_FEEDBACK_KEY, []).append("AI refinement returned no updates.")
        return
    trait = response.traits[0]
    upsert_trait(draft, container_id, trait)
    st.session_state[DRAFT_DIRTY_KEY] = True
    st.session_state.setdefault(AI_FEEDBACK_KEY, []).extend(response.messages)
    _safe_rerun()


def _apply_ai_links(draft: Dict[str, Any], container_id: str, response: AIResponse) -> None:
    container = locate_container(draft, container_id)
    if not container:
        return
    for trait_id, links in response.links.items():
        trait = locate_trait(container, trait_id)
        if trait is None:
            continue
        trait["links"] = sorted(set(map(str, links)))
    if response.links:
        st.session_state[DRAFT_DIRTY_KEY] = True
    st.session_state.setdefault(AI_FEEDBACK_KEY, []).extend(response.messages)
    _safe_rerun()


def _save_draft(
    repo_root: Path,
    draft: Dict[str, Any],
    base_schema: Dict[str, Any],
    context: WriteProtectContext,
) -> None:
    try:
        write_guard(context, action="save schema draft")
    except PermissionError as exc:
        st.error(str(exc))
        return

    path = draft_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, indent=2), encoding="utf-8")

    diff = diff_schemas(base_schema, draft)

    try:
        write_guard(context, action="record container change log")
    except PermissionError:
        st.warning("Draft saved but could not append to container change log (write-protect?).")
    else:
        log = log_path(repo_root)
        log.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "path": str(path),
            "diff": diff.summary_rows(),
        }
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    st.session_state[DRAFT_DIRTY_KEY] = False
    st.success(f"Draft saved to {path}.")
