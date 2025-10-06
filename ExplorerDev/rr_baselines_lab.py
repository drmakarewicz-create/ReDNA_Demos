"""RR Baselines Lab module for Dev Explorer."""

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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

try:  # optional dependency for nicer tables
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional
    pd = None

from ExplorerDev.rr_baseline_utils import (
    WriteProtectContext,
    export_config_as_csv,
    get_effective_baseline,
    get_session_draft,
    is_demo_enabled,
    load_change_log,
    load_demo_baselines,
    load_demo_config,
    preflight_import,
    save_demo_baselines,
    set_session_draft,
    set_session_toggle,
    resolve_baselines,
    validate_demo_baselines,
)


STATE_KEY = "_rr_baselines_lab_state"
IMPORT_PREVIEW_KEY = "_rr_import_preview"


@dataclass(slots=True)
class LabState:
    selected_container: Optional[str] = None
    selected_trait: Optional[str] = None


def _safe_rerun() -> None:
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return
    legacy_fn = getattr(st, "experimental_rerun", None)
    if callable(legacy_fn):  # pragma: no cover - compatibility path
        legacy_fn()


def render_rr_baselines_lab(repo_root: Path, context: WriteProtectContext) -> None:
    bundle = load_demo_baselines(repo_root)
    file_config = bundle["config"]
    canonical = bundle["canonical"]

    working_config = get_session_draft(file_config)
    _ensure_state_defaults(working_config)

    st.subheader("🧪 RR Baselines Lab")
    st.caption(
        "Simulate community baselines for demo Resonance Reports without touching Core's live priors."
    )

    state = _get_state()

    _render_top_toggle(repo_root, context, working_config)

    if is_demo_enabled(repo_root):
        st.success("Demo baselines active — Dev Explorer previews use simulated priors.")
    else:
        st.caption("Live community baselines currently in effect.")

    note_value = st.text_area(
        "Baseline note",
        value=str(working_config.get("note", "")),
        help="Optional note stored alongside the demo baseline file.",
        key="rr_baseline_note",
    )
    if note_value != str(working_config.get("note", "")):
        working_config["note"] = note_value
        set_session_draft(working_config)

    resolved = resolve_baselines(working_config, canonical)
    containers = list(working_config.get("containers", {}).keys())
    if containers:
        if state.selected_container not in containers:
            state.selected_container = containers[0]
    else:
        state.selected_container = None
        state.selected_trait = None

    left_col, main_col, right_col = st.columns([1.2, 2.5, 1.8])

    with left_col:
        _render_container_list(working_config, state)

    with main_col:
        _render_container_detail(
            working_config,
            canonical,
            resolved,
            state,
            context,
        )

    with right_col:
        _render_tools_panel(
            repo_root,
            context,
            working_config,
            file_config,
            canonical,
        )


def _get_state() -> LabState:
    state = st.session_state.get(STATE_KEY)
    if isinstance(state, LabState):
        return state
    state = LabState()
    st.session_state[STATE_KEY] = state
    return state


def _ensure_state_defaults(config: Dict[str, Any]) -> None:
    containers = list(config.get("containers", {}).keys())
    state = _get_state()
    if containers and state.selected_container not in containers:
        state.selected_container = containers[0]
        state.selected_trait = None


def _render_top_toggle(repo_root: Path, context: WriteProtectContext, config: Dict[str, Any]) -> None:
    global_conf = config.setdefault("global", {})
    current_flag = bool(global_conf.get("use_demo_baselines", False))
    effective_flag = is_demo_enabled(repo_root)
    toggle_value = st.toggle(
        "Use simulated community baselines",
        value=current_flag or effective_flag,
        help="When ON, demo priors override live community stats during Dev Explorer previews.",
    )

    if toggle_value != current_flag:
        global_conf["use_demo_baselines"] = bool(toggle_value)
        set_session_toggle(toggle_value)
        set_session_draft(config)
        if context.write_protect:
            st.info("Write-protect ON — toggle change stays in this session only.")


def _render_container_list(config: Dict[str, Any], state: LabState) -> None:
    st.markdown("#### Containers")
    containers = config.get("containers") if isinstance(config.get("containers"), dict) else {}
    if not containers:
        st.info("No container baselines yet. Add one below.")
    else:
        labels = []
        keys: List[str] = []
        for name, payload in sorted(containers.items()):
            trait_count = len(payload.get("traits", {})) if isinstance(payload.get("traits"), dict) else 0
            labels.append(f"{name} · {trait_count} trait baseline(s)")
            keys.append(name)

        selected = st.radio(
            "Container",
            options=keys,
            index=keys.index(state.selected_container) if state.selected_container in keys else 0,
            format_func=lambda name, labels_map=dict(zip(keys, labels)): labels_map.get(name, name),
            key="rr_container_radio",
        )
        if selected != state.selected_container:
            state.selected_container = selected
            state.selected_trait = None

    st.markdown("---")
    with st.expander("Add container baseline"):
        _render_add_container_form(config)


def _render_add_container_form(config: Dict[str, Any]) -> None:
    with st.form("rr_add_container_form"):
        name = st.text_input("Container name")
        mean = st.number_input("Mean UCN", min_value=0.0, max_value=1.0, value=0.45, step=0.01)
        std = st.number_input("Std UCN", min_value=0.0, max_value=1.0, value=0.10, step=0.01)
        sample = st.number_input("Sample size", min_value=1, value=50, step=1)
        submitted = st.form_submit_button("Add container")
    if submitted:
        container_id = name.strip()
        if not container_id:
            st.warning("Container name required.")
            return
        containers = config.setdefault("containers", {})
        if container_id in containers:
            st.warning("Container already exists.")
            return
        containers[container_id] = {
            "mean_ucn": float(mean),
            "std_ucn": float(std),
            "sample_size": int(sample),
            "traits": {},
        }
        set_session_draft(config)
        st.success(f"Container '{container_id}' added to draft.")


def _render_container_detail(
    config: Dict[str, Any],
    canonical: Dict[str, Any],
    resolved: Dict[str, Any],
    state: LabState,
    context: WriteProtectContext,
) -> None:
    container_id = state.selected_container
    if not container_id:
        st.info("Select a container to inspect baselines.")
        return

    containers = config.get("containers") if isinstance(config.get("containers"), dict) else {}
    container_entry = containers.get(container_id, {}) if isinstance(containers.get(container_id), dict) else {}
    resolved_container = resolved.get("containers", {}).get(container_id, {})

    st.markdown(f"### {container_id}")
    summary_rows = _table_rows_for_container(container_id, resolved_container)
    if pd and summary_rows:
        df = pd.DataFrame(summary_rows)  # type: ignore[arg-type]
        ordered = [
            "scope",
            "mean_ucn",
            "std_ucn",
            "sample_size",
            "sparkline",
            "source_chip",
        ]
        existing_cols = [col for col in ordered if col in df.columns]
        st.dataframe(df[existing_cols])
    else:
        st.table(summary_rows)

    _render_container_edit_form(config, container_id, container_entry, context)

    st.markdown("#### Trait baselines")
    traits = container_entry.get("traits") if isinstance(container_entry.get("traits"), dict) else {}
    trait_ids = sorted(traits.keys())

    table_rows = _table_rows_for_traits(container_id, traits, resolved_container)
    if table_rows:
        if pd:
            df = pd.DataFrame(table_rows)  # type: ignore[arg-type]
            ordered = [
                "scope",
                "mean_ucn",
                "std_ucn",
                "sample_size",
                "sparkline",
                "effective_source",
                "source_chip",
            ]
            existing_cols = [col for col in ordered if col in df.columns]
            st.dataframe(df[existing_cols])
        else:
            st.table(table_rows)
    else:
        st.info("No explicit trait baselines — traits inherit container/default values.")

    if trait_ids:
        with st.expander("Batch edit traits"):
            selected_traits = st.multiselect(
                "Select traits",
                trait_ids,
                key=f"rr_batch_select_{container_id}",
            )
            helper = "Leave blank to keep the existing value."
            col_mean, col_std, col_sample = st.columns(3)
            mean_input = col_mean.text_input(
                "Mean (0-1)",
                value="",
                key=f"rr_batch_mean_{container_id}",
                help=helper,
            )
            std_input = col_std.text_input(
                "Std (0-1)",
                value="",
                key=f"rr_batch_std_{container_id}",
                help=helper,
            )
            sample_input = col_sample.text_input(
                "Sample size",
                value="",
                key=f"rr_batch_sample_{container_id}",
                help=helper,
            )

            if st.button(
                "Apply batch updates",
                key=f"rr_batch_apply_{container_id}",
                disabled=not selected_traits,
            ):
                errors: List[str] = []
                update_mean: Optional[float] = None
                update_std: Optional[float] = None
                update_sample: Optional[int] = None

                if mean_input.strip():
                    try:
                        update_mean = float(mean_input)
                        if not 0.0 <= update_mean <= 1.0:
                            raise ValueError
                    except ValueError:
                        errors.append("Mean must be between 0 and 1.")
                if std_input.strip():
                    try:
                        update_std = float(std_input)
                        if not 0.0 <= update_std <= 1.0:
                            raise ValueError
                    except ValueError:
                        errors.append("Std must be between 0 and 1.")
                if sample_input.strip():
                    try:
                        update_sample = int(float(sample_input))
                        if update_sample < 1:
                            raise ValueError
                    except ValueError:
                        errors.append("Sample size must be ≥ 1.")

                if errors:
                    for msg in errors:
                        st.error(msg)
                else:
                    for trait_name in selected_traits:
                        trait_entry = traits.setdefault(trait_name, {})
                        if update_mean is not None:
                            trait_entry["mean_ucn"] = update_mean
                        if update_std is not None:
                            trait_entry["std_ucn"] = update_std
                        if update_sample is not None:
                            trait_entry["sample_size"] = update_sample
                    set_session_draft(config)
                    st.success(f"Updated {len(selected_traits)} trait baseline(s).")

    options = ["—"] + trait_ids
    selected = st.selectbox("Edit trait baseline", options, key="rr_trait_select")
    state.selected_trait = selected if selected != "—" else None

    if state.selected_trait:
        _render_trait_edit_form(config, container_id, state.selected_trait, context)

    st.markdown("---")
    _render_add_trait_form(config, container_id, context)


def _render_container_edit_form(
    config: Dict[str, Any],
    container_id: str,
    entry: Dict[str, Any],
    context: WriteProtectContext,
) -> None:
    with st.form(f"rr_container_edit_{container_id}"):
        mean_value = float(entry.get("mean_ucn", 0.45))
        std_value = float(entry.get("std_ucn", 0.10))
        sample_value = int(entry.get("sample_size", 50))
        mean = st.number_input(
            "Mean UCN",
            min_value=0.0,
            max_value=1.0,
            value=mean_value,
            step=0.01,
            key=f"rr_container_mean_{container_id}",
        )
        std = st.number_input(
            "Std UCN",
            min_value=0.0,
            max_value=1.0,
            value=std_value,
            step=0.01,
            key=f"rr_container_std_{container_id}",
        )
        sample = st.number_input(
            "Sample size",
            min_value=1,
            value=sample_value,
            step=1,
            key=f"rr_container_sample_{container_id}",
        )
        submitted = st.form_submit_button("Save container baseline")

    if submitted:
        container_entry = config.setdefault("containers", {}).setdefault(container_id, {})
        container_entry["mean_ucn"] = float(mean)
        container_entry["std_ucn"] = float(std)
        container_entry["sample_size"] = int(sample)
        set_session_draft(config)
        st.success("Container baseline updated in draft.")

    if st.button("Reset to defaults", key=f"rr_reset_container_{container_id}"):
        config.setdefault("containers", {}).pop(container_id, None)
        set_session_draft(config)
        st.success("Container baseline reset to defaults.")

    if st.button("Remove container baseline", key=f"rr_remove_container_{container_id}"):
        config.setdefault("containers", {}).pop(container_id, None)
        set_session_draft(config)
        _get_state().selected_container = None
        st.success("Container baseline removed from draft.")


def _render_trait_edit_form(
    config: Dict[str, Any],
    container_id: str,
    trait_id: str,
    context: WriteProtectContext,
) -> None:
    trait_entry = (
        config.setdefault("containers", {})
        .setdefault(container_id, {})
        .setdefault("traits", {})
        .get(trait_id, {})
    )
    with st.form(f"rr_trait_edit_{container_id}_{trait_id}"):
        mean_value = float(trait_entry.get("mean_ucn", 0.45))
        std_value = float(trait_entry.get("std_ucn", 0.10))
        sample_value = int(trait_entry.get("sample_size", 50))
        mean = st.number_input(
            "Trait mean UCN",
            min_value=0.0,
            max_value=1.0,
            value=mean_value,
            step=0.01,
            key=f"rr_trait_mean_{trait_id}",
        )
        std = st.number_input(
            "Trait std UCN",
            min_value=0.0,
            max_value=1.0,
            value=std_value,
            step=0.01,
            key=f"rr_trait_std_{trait_id}",
        )
        sample = st.number_input(
            "Trait sample size",
            min_value=1,
            value=sample_value,
            step=1,
            key=f"rr_trait_sample_{trait_id}",
        )
        submitted = st.form_submit_button("Save trait baseline")
    if submitted:
        traits = (
            config.setdefault("containers", {})
            .setdefault(container_id, {})
            .setdefault("traits", {})
        )
        traits[trait_id] = {
            "mean_ucn": float(mean),
            "std_ucn": float(std),
            "sample_size": int(sample),
        }
        set_session_draft(config)
        st.success("Trait baseline saved in draft.")

    action_cols = st.columns(2)
    if action_cols[0].button("Reset to container/default", key=f"rr_trait_reset_{trait_id}"):
        traits_map = (
            config.setdefault("containers", {})
            .setdefault(container_id, {})
            .setdefault("traits", {})
        )
        traits_map.pop(trait_id, None)
        set_session_draft(config)
        st.success("Trait baseline reset to container/default.")

    if action_cols[1].button("Remove trait baseline", key=f"rr_trait_remove_{trait_id}"):
        traits_map = (
            config.setdefault("containers", {})
            .setdefault(container_id, {})
            .setdefault("traits", {})
        )
        traits_map.pop(trait_id, None)
        set_session_draft(config)
        _get_state().selected_trait = None
        st.success("Trait baseline removed from draft.")


def _render_add_trait_form(config: Dict[str, Any], container_id: str, context: WriteProtectContext) -> None:
    with st.form(f"rr_add_trait_form_{container_id}"):
        trait_name = st.text_input("Trait name", key=f"rr_add_trait_name_{container_id}")
        mean = st.number_input("Mean UCN", min_value=0.0, max_value=1.0, value=0.45, step=0.01)
        std = st.number_input("Std UCN", min_value=0.0, max_value=1.0, value=0.10, step=0.01)
        sample = st.number_input("Sample size", min_value=1, value=50, step=1)
        submitted = st.form_submit_button("Add trait baseline")

    if submitted:
        trait_id = trait_name.strip()
        if not trait_id:
            st.warning("Trait name required.")
            return
        traits = (
            config.setdefault("containers", {})
            .setdefault(container_id, {})
            .setdefault("traits", {})
        )
        if trait_id in traits:
            st.warning("Trait baseline already exists. Use edit instead.")
            return
        traits[trait_id] = {
            "mean_ucn": float(mean),
            "std_ucn": float(std),
            "sample_size": int(sample),
        }
        set_session_draft(config)
        st.success(f"Trait '{trait_id}' added to container '{container_id}'.")


def _render_tools_panel(
    repo_root: Path,
    context: WriteProtectContext,
    working_config: Dict[str, Any],
    file_config: Dict[str, Any],
    canonical: Dict[str, Any],
) -> None:
    st.markdown("#### Import / Export")
    yaml_blob = _safe_yaml_dump(working_config)
    if yaml_blob:
        st.download_button(
            "Download YAML",
            data=yaml_blob,
            file_name="rr_demo_baselines.yaml",
            mime="application/x-yaml",
        )
    st.download_button(
        "Download CSV",
        data=export_config_as_csv(working_config),
        file_name="rr_demo_baselines.csv",
        mime="text/csv",
    )

    if context.write_protect:
        st.info("Write-protect ON — importing is disabled.")
    else:
        uploaded = st.file_uploader("Import baselines (YAML or CSV)", type=["yaml", "yml", "csv"])
        if uploaded is not None:
            try:
                content = uploaded.read().decode("utf-8")
            except UnicodeDecodeError:
                st.error("Unable to decode uploaded file. Use UTF-8 encoding.")
            else:
                new_config = _parse_import_payload(uploaded.name or "", content, file_config)
                preview = preflight_import(
                    repo_root,
                    new_config,
                    canonical=canonical,
                    existing=file_config,
                )
                st.session_state[IMPORT_PREVIEW_KEY] = preview
                st.success("Import parsed. Review the preflight summary below before applying.")

    preview = st.session_state.get(IMPORT_PREVIEW_KEY)
    if preview:
        _render_import_preview(preview, context, file_config)
        st.markdown("---")

    st.markdown("---")
    st.markdown("#### Validation")
    issues = validate_demo_baselines(working_config)
    if not issues:
        st.success("Draft passes validation.")
    else:
        for issue in issues:
            target = "error" if issue.level == "error" else "warning"
            st.write(f"**{target.upper()}** · {issue.scope}: {issue.message}")

    st.markdown("---")
    st.markdown("#### Draft controls")
    dirty = not _configs_equal(working_config, file_config)
    if dirty:
        st.info("Draft differs from saved demo baselines.")
    else:
        st.caption("Draft matches disk state.")

    if context.write_protect:
        st.info("Write-protect ON — saves are disabled.")
    else:
        if st.button("Save demo baselines", key="rr_save_baselines", disabled=bool(issues)):
            if issues:
                st.error("Fix validation errors before saving.")
            else:
                try:
                    save_demo_baselines(repo_root, working_config, context, previous=file_config)
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
                else:
                    st.success("Demo baselines saved.")
                    set_session_draft(load_demo_config(repo_root))

    if st.button("Reset draft to saved", key="rr_reset_draft"):
        set_session_draft(file_config)
        st.success("Draft reset to last saved state.")

    st.markdown("---")
    st.markdown("#### Change log")
    log_entries = load_change_log(repo_root)
    if not log_entries:
        st.caption("No changes logged yet.")
    else:
        for entry in log_entries:
            ts = entry.get("timestamp", "—")
            st.write(f"• {ts} — change recorded")

    st.markdown("---")
    _render_preview(repo_root, working_config, canonical)


def _render_import_preview(
    preview: Dict[str, Any],
    _context: WriteProtectContext,
    _file_config: Dict[str, Any],
) -> None:
    st.markdown("#### Import preflight summary")
    counts = preview.get("counts", {})
    unknown = preview.get("unknown", {})
    changes = preview.get("changes", {})
    issues = preview.get("issues", [])
    error_count = int(preview.get("error_count", 0) or 0)
    warning_count = int(preview.get("warning_count", 0) or 0)

    metric_cols = st.columns(3)
    metric_cols[0].metric("Containers", counts.get("containers", 0))
    metric_cols[1].metric("Trait baselines", counts.get("traits", 0))
    metric_cols[2].metric("Warnings", warning_count)

    if unknown.get("containers"):
        with st.expander("Unknown containers", expanded=True):
            for item in unknown["containers"]:
                st.write(f"• {item}")

    if unknown.get("traits"):
        with st.expander("Unknown traits", expanded=bool(unknown.get("traits"))):
            for item in unknown["traits"]:
                st.write(f"• {item}")

    if changes:
        change_lines: List[str] = []
        if changes.get("added"):
            change_lines.append(f"Added: {len(changes['added'])}")
        if changes.get("removed"):
            change_lines.append(f"Removed: {len(changes['removed'])}")
        if changes.get("changed"):
            change_lines.append(f"Adjusted: {len(changes['changed'])}")
        if changes.get("note_changed"):
            change_lines.append("Note updated")
        if change_lines:
            st.caption("; ".join(change_lines))

    if issues:
        st.write("**Validation findings**")
        for issue in issues:
            level = "ERROR" if issue.level == "error" else issue.level.upper()
            st.write(f"- {level} · {issue.scope}: {issue.message}")
    else:
        st.success("No validation findings detected.")

    buttons = st.columns(2)
    apply_disabled = error_count > 0
    with buttons[0]:
        if st.button(
            "Apply to draft",
            key="rr_import_apply",
            disabled=apply_disabled,
        ):
            if apply_disabled:
                st.error("Resolve import errors before applying the draft.")
            else:
                set_session_draft(preview["config"])
                st.session_state.pop(IMPORT_PREVIEW_KEY, None)
                st.success("Import applied to draft.")
                _safe_rerun()
                return
    with buttons[1]:
        if st.button("Discard preview", key="rr_import_discard"):
            st.session_state.pop(IMPORT_PREVIEW_KEY, None)
            st.info("Import preview cleared.")
            _safe_rerun()
            return


def _render_preview(repo_root: Path, config: Dict[str, Any], canonical: Dict[str, Any]) -> None:
    st.markdown("#### Preview effect")
    users_dir = repo_root / "ReDNACoreDemo" / "data" / "storage" / "users"
    if not users_dir.exists():
        st.caption("No Core user storage found. Run Core at least once to generate user data.")
        return

    user_ids = sorted([p.name for p in users_dir.iterdir() if p.is_dir()])
    if not user_ids:
        st.caption("No demo users available.")
        return

    user_id = st.selectbox("User", user_ids, key="rr_preview_user")
    if not user_id:
        return

    run_preview = st.button("Compute preview", key="rr_preview_button")
    if not run_preview:
        return

    flat_path = users_dir / user_id / "resolved_flat.json"
    if not flat_path.exists():
        st.warning("resolved_flat.json not found for this user.")
        return

    try:
        payload = json.loads(flat_path.read_text(encoding="utf-8"))
    except Exception as exc:
        st.error(f"Failed to read resolved data: {exc}")
        return

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        st.warning("Unexpected resolved data format; expected rows list.")
        return

    preview_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        ucn_value = row.get("ucn")
        if not path or not isinstance(ucn_value, (int, float)):
            continue
        container_id, trait_id = _split_path(path)
        demo = get_effective_baseline(
            repo_root,
            container_id,
            trait=trait_id,
            config=config,
            canonical=canonical,
            use_demo=True,
        )
        live = get_effective_baseline(
            repo_root,
            container_id,
            trait=trait_id,
            config=config,
            canonical=canonical,
            use_demo=False,
        )
        ucn_norm = float(ucn_value) / 1000.0
        preview_rows.append(
            {
                "trait": path,
                "user_ucn": round(ucn_norm, 3),
                "demo_mean": round(demo.get("mean_ucn", 0.0), 3),
                "live_mean": round(live.get("mean_ucn", 0.0), 3),
                "delta": round(demo.get("mean_ucn", 0.0) - live.get("mean_ucn", 0.0), 3),
                "demo_source": demo.get("source"),
                "live_source": live.get("source"),
            }
        )

    if not preview_rows:
        st.info("No UCN traits available for this user.")
        return

    if pd:
        st.dataframe(pd.DataFrame(preview_rows))  # type: ignore[arg-type]
    else:
        st.table(preview_rows)

    avg_delta = sum(row["delta"] for row in preview_rows) / len(preview_rows)
    st.caption(f"Average delta (demo - live): {avg_delta:+0.3f}")


def _split_path(path: str) -> (str, str):
    if "." in path:
        container, trait = path.rsplit(".", 1)
        return container, trait
    return "default", path


def _parse_import_payload(name: str, content: str, base: Dict[str, Any]) -> Dict[str, Any]:
    suffix = name.lower().split(".")[-1]
    if suffix == "csv":
        return _config_from_csv(content)
    return _safe_yaml_load(content, base)


def _safe_yaml_dump(config: Dict[str, Any]) -> Optional[str]:
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover - PyYAML missing
        st.caption("Install PyYAML to export YAML.")
        return None
    return yaml.safe_dump(config, sort_keys=False)


def _safe_yaml_load(content: str, base: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        st.error(f"PyYAML required for YAML import: {exc}")
        return base
    try:
        data = yaml.safe_load(content) or {}
    except Exception as exc:
        st.error(f"YAML import failed: {exc}")
        return base
    if not isinstance(data, dict):
        st.error("YAML import must produce a mapping.")
        return base
    return data


def _config_from_csv(text: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "schemaVersion": 1,
        "global": {"use_demo_baselines": False},
        "defaults": {},
        "containers": {},
    }
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return config
    header = [part.strip() for part in lines[0].split(",")]
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        row = dict(zip(header, parts))
        scope = row.get("scope", "")
        mean = _parse_float(row.get("mean_ucn"))
        std = _parse_float(row.get("std_ucn"))
        sample = _parse_int(row.get("sample_size"))
        if scope == "defaults":
            block = config.setdefault("defaults", {})
        elif scope.endswith("(container)"):
            name = scope.replace("(container)", "").strip()
            block = config.setdefault("containers", {}).setdefault(name, {})
        elif "." in scope:
            container, trait = scope.split(".", 1)
            block = (
                config.setdefault("containers", {})
                .setdefault(container.strip(), {})
                .setdefault("traits", {})
                .setdefault(trait.strip(), {})
            )
        else:
            continue
        if mean is not None:
            block["mean_ucn"] = mean
        if std is not None:
            block["std_ucn"] = std
        if sample is not None:
            block["sample_size"] = sample
    return config


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _configs_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _table_rows_for_container(container_id: str, resolved: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not resolved:
        return []
    return [
        {
            "scope": f"{container_id} (container)",
            "mean_ucn": resolved.get("mean_ucn"),
            "std_ucn": resolved.get("std_ucn"),
            "sample_size": resolved.get("sample_size"),
            "effective_source": resolved.get("source"),
        }
    ]


def _table_rows_for_traits(
    container_id: str,
    traits: Dict[str, Any],
    resolved: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    resolved_traits = resolved.get("traits") if isinstance(resolved.get("traits"), dict) else {}
    for trait_id, payload in traits.items():
        resolved_trait = resolved_traits.get(trait_id, {})
        rows.append(
            {
                "scope": f"{container_id}.{trait_id}",
                "mean_ucn": resolved_trait.get("mean_ucn", payload.get("mean_ucn")),
                "std_ucn": resolved_trait.get("std_ucn", payload.get("std_ucn")),
                "sample_size": resolved_trait.get("sample_size", payload.get("sample_size")),
                "effective_source": resolved_trait.get("source", "explicit"),
            }
        )
    return rows
