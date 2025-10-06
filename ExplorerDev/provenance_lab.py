"""Developer-facing UI for provenance diff and replay tooling."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import streamlit as st

from ExplorerDev.ui.components import (
    BundleCandidate,
    UserCandidate,
    download_buttons,
    list_known_users,
    list_recent_bundles,
    list_recent_user_bundles,
)
from ReDNACoreDemo.core import provenance_replay, storage


_DIFF_STATE_KEY = "_provenance_diff_state"
_REPLAY_STATE_KEY = "_provenance_replay_state"


@dataclass
class _DiffContext:
    path_a: Path
    path_b: Path
    resolved_a: Dict[str, Any]
    resolved_b: Dict[str, Any]


def render_provenance_lab(repo_root: Path) -> None:
    """Render the provenance tooling surface inside Dev Explorer."""

    st.subheader("Provenance Lab")
    st.caption("Compare resolved bundles or replay stored events without leaving Dev Explorer.")

    _render_help_sidebar(repo_root)

    diff_tab, replay_tab = st.tabs(["Diff", "Replay"])
    with diff_tab:
        _render_diff_tab(repo_root)
    with replay_tab:
        _render_replay_tab(repo_root)


def _render_help_sidebar(repo_root: Path) -> None:
    help_lines = [
        "**Pro Tip**: Bundles live under `ReDNACoreDemo/data/checkpoints/<user>/bundle-*.json`.",
        "Resolved demo users live under `ReDNACoreDemo/data/demo_users/*.json`.",
        "Event replays read from `ReDNACoreDemo/data/checkpoints/<user>/events/*.json`.",
    ]
    sidebar = st.sidebar.container()
    sidebar.markdown("### Provenance Hints")
    for line in help_lines:
        sidebar.markdown(line)
    sidebar.caption(f"Repo root: `{repo_root}`")
    sidebar.link_button("Open Core Docs (/docs)", "http://127.0.0.1:8015/docs", type="secondary")


def _render_diff_tab(repo_root: Path) -> None:
    st.markdown("### Provenance Diff")
    st.write("Select two bundle snapshots to see trait-level changes, then export as needed.")

    bundle_options = list_recent_bundles(repo_root)

    _render_quick_diff_shortcuts(bundle_options, repo_root)

    with st.form("prov_diff_form"):
        col_a, col_b = st.columns(2)
        selected_a = col_a.selectbox(
            "Bundle A",
            options=bundle_options,
            format_func=_format_bundle_option,
            key="prov_diff_select_a",
        )
        selected_b = col_b.selectbox(
            "Bundle B",
            options=bundle_options,
            format_func=_format_bundle_option,
            key="prov_diff_select_b",
        )
        manual_a = col_a.text_input(
            "Path override (A)",
            key="prov_diff_manual_a",
            placeholder="Optional absolute or repo-relative path",
        )
        manual_b = col_b.text_input(
            "Path override (B)",
            key="prov_diff_manual_b",
            placeholder="Optional absolute or repo-relative path",
        )

        submitted = st.form_submit_button("Run provenance diff", type="primary")

    diff_state: Dict[str, Any] = st.session_state.setdefault(_DIFF_STATE_KEY, {})

    if submitted:
        try:
            context = _build_diff_context(selected_a, selected_b, manual_a, manual_b, repo_root)
        except FileNotFoundError as exc:
            diff_state["error"] = f"{exc}. Verify the path and retry."
            diff_state.pop("rows", None)
            diff_state.pop("meta", None)
        except ValueError as exc:
            diff_state["error"] = f"{exc}. Fix the source file and run again."
            diff_state.pop("rows", None)
            diff_state.pop("meta", None)
        except Exception as exc:  # noqa: BLE001 - user facing error
            diff_state["error"] = str(exc)
            diff_state.pop("rows", None)
            diff_state.pop("meta", None)
        else:
            rows = _diff_rows(context)
            diff_state.clear()
            diff_state.update(
                {
                    "rows": rows,
                    "meta": {
                        "path_a": str(context.path_a),
                        "path_b": str(context.path_b),
                        "changed_count": sum(1 for row in rows if row.get("changed")),
                        "command": _diff_command(context.path_a, context.path_b),
                    },
                }
            )

    if diff_state.get("error"):
        st.error(diff_state["error"])
        return

    rows: List[Dict[str, Any]] = diff_state.get("rows") or []
    if not rows:
        st.info("Select bundle snapshots and run the diff to see results.")
        return

    meta = diff_state.get("meta", {})
    _render_diff_summary(meta)

    filter_cols = st.columns([2, 1, 1])
    search_term = filter_cols[0].text_input(
        "Search traits",
        value=diff_state.get("search", ""),
        key="prov_diff_search_box",
        placeholder="Filter by trait id, value, or reason",
    )
    containers = sorted({row["container"] for row in rows})
    default_selection = diff_state.get("container_selection") or containers
    selected_containers = filter_cols[1].multiselect(
        "Container",
        options=containers,
        default=default_selection,
        key="prov_diff_container_filter",
    )
    changed_only = filter_cols[2].checkbox(
        "Changed only",
        value=diff_state.get("changed_only", True),
        key="prov_diff_changed_only",
    )

    diff_state["search"] = search_term
    diff_state["container_selection"] = selected_containers
    diff_state["changed_only"] = changed_only

    filtered_rows = _filter_diff_rows(rows, search_term, selected_containers, changed_only)

    st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    download_buttons(
        filtered_rows,
        filename_prefix="provenance_diff",
        csv_columns=(
            "container",
            "trait_id",
            "from_value",
            "to_value",
            "from_ucn",
            "to_ucn",
            "reasons_from",
            "reasons_to",
        ),
        key="prov_diff_export",
    )


def _render_diff_summary(meta: Mapping[str, Any]) -> None:
    changed_count = int(meta.get("changed_count") or 0)
    badge_html = (
        "<span style=\"display:inline-flex;align-items:center;padding:0.25rem 0.6rem;"
        "border-radius:999px;background:#f0f2ff;color:#1c3fb7;font-size:0.85rem;"
        "font-weight:600;margin-bottom:0.35rem;\">"
        f"{changed_count} trait{'s' if changed_count != 1 else ''} changed"
        "</span>"
    )
    st.markdown(badge_html, unsafe_allow_html=True)
    st.caption(
        "Comparing:\n"
        f"• {meta.get('path_a', '(missing)')}\n"
        f"• {meta.get('path_b', '(missing)')}"
    )
    command = meta.get("command")
    if command:
        st.code(command, language="bash")


def _render_quick_diff_shortcuts(bundle_options: List[BundleCandidate], repo_root: Path) -> None:
    user_sets = list_recent_user_bundles(repo_root, per_user=2, limit_users=6)
    if not user_sets:
        return

    st.markdown("#### Quick Picks")
    st.caption("Jump to recent bundle pairs per user without hunting for paths.")

    for user_set in user_sets:
        if len(user_set.bundles) < 2:
            continue
        latest = user_set.bundles[0]
        previous = user_set.bundles[1]
        cols = st.columns([3, 2, 1])
        with cols[0]:
            st.markdown(f"**{user_set.user_id}**")
            st.caption(_bundle_summary(previous, latest))
        with cols[1]:
            st.caption(
                f"A: {previous.label}\n\nB: {latest.label}",
            )
        with cols[2]:
            if st.button(
                "Diff latest",
                key=f"prov_diff_quick_{user_set.user_id}",
            ):
                _apply_quick_diff(bundle_options, previous, latest, repo_root)


def _bundle_summary(previous: BundleCandidate, latest: BundleCandidate) -> str:
    prev_time = dt.datetime.fromtimestamp(previous.mtime)
    latest_time = dt.datetime.fromtimestamp(latest.mtime)
    return (
        f"Prev: {prev_time:%Y-%m-%d %H:%M:%S}\n"
        f"Latest: {latest_time:%Y-%m-%d %H:%M:%S}"
    )


def _apply_quick_diff(
    bundle_options: List[BundleCandidate],
    previous: BundleCandidate,
    latest: BundleCandidate,
    repo_root: Path,
) -> None:
    candidate_a = _match_candidate(bundle_options, previous)
    candidate_b = _match_candidate(bundle_options, latest)

    if candidate_a is None or candidate_b is None:
        st.session_state.setdefault(_DIFF_STATE_KEY, {})[
            "error"
        ] = "Quick diff failed: bundle not found in options."
        st.experimental_rerun()
        return

    st.session_state["prov_diff_select_a"] = candidate_a
    st.session_state["prov_diff_select_b"] = candidate_b
    st.session_state["prov_diff_manual_a"] = ""
    st.session_state["prov_diff_manual_b"] = ""

    diff_state: Dict[str, Any] = st.session_state.setdefault(_DIFF_STATE_KEY, {})

    try:
        context = _build_diff_context(candidate_a, candidate_b, "", "", repo_root)
        rows = _diff_rows(context)
    except Exception as exc:  # noqa: BLE001
        diff_state.clear()
        diff_state["error"] = f"Quick diff failed: {exc}"
    else:
        diff_state.clear()
        diff_state.update(
            {
                "rows": rows,
                "meta": {
                    "path_a": str(context.path_a),
                    "path_b": str(context.path_b),
                    "changed_count": sum(1 for row in rows if row.get("changed")),
                    "command": _diff_command(context.path_a, context.path_b),
                },
            }
        )

    st.experimental_rerun()


def _match_candidate(options: Sequence[BundleCandidate], target: BundleCandidate) -> BundleCandidate | None:
    for candidate in options:
        if candidate.path == target.path:
            return candidate
    return target if target in options else None


def _diff_command(path_a: Path, path_b: Path) -> str:
    return (
        "python -m ReDNACoreDemo.core.provenance_diff "
        f"--a \"{path_a}\" --b \"{path_b}\""
    )


def _render_replay_tab(repo_root: Path) -> None:
    st.markdown("### Provenance Replay")
    st.write("Rebuild a user's resolved state as of a specific timestamp.")

    known_users = list_known_users(repo_root)
    replay_state: Dict[str, Any] = st.session_state.setdefault(_REPLAY_STATE_KEY, {})

    now_btn_col, _ = st.columns([1, 3])
    if now_btn_col.button("Set until to Now (UTC)", key="prov_replay_now"):
        now_utc = dt.datetime.now(tz=dt.timezone.utc)
        replay_state["date"] = now_utc.date()
        replay_state["time"] = now_utc.time().replace(microsecond=0)

    with st.form("prov_replay_form"):
        user_col, trait_col = st.columns([2, 1])
        selected_user = user_col.selectbox(
            "User",
            options=known_users,
            format_func=lambda item: item.label if isinstance(item, UserCandidate) else str(item),
            key="prov_replay_user_select",
        )
        manual_user = user_col.text_input(
            "User override",
            value=replay_state.get("manual_user", ""),
            key="prov_replay_user_manual",
            placeholder="Optional explicit user id",
        )

        default_date = replay_state.get("date") or dt.datetime.now(tz=dt.timezone.utc).date()
        default_time = replay_state.get("time") or dt.time(0, 0)
        date_value = user_col.date_input("Until date (UTC)", value=default_date, key="prov_replay_date")
        time_value = user_col.time_input("Until time (UTC)", value=default_time, key="prov_replay_time")

        trait_filter_value = trait_col.text_area(
            "Trait filter (one per line)",
            value=replay_state.get("traits_raw", ""),
            height=120,
            key="prov_replay_traits",
            placeholder="Optional precise trait ids, e.g. PaDNA.EyeDNA.Color",
        )

        compare_current = trait_col.checkbox(
            "Compare to current",
            value=bool(replay_state.get("compare_current")),
            key="prov_replay_compare",
        )

        submitted = st.form_submit_button("Replay events", type="primary")

    replay_state.update(
        {
            "manual_user": manual_user,
            "date": date_value,
            "time": time_value,
            "traits_raw": trait_filter_value,
            "compare_current": compare_current,
        }
    )

    if not submitted:
        if replay_state.get("rows"):
            _render_replay_results(replay_state)
        else:
            st.info("Choose a user and replay point, then run the replay to inspect results.")
        return

    until_ts = _combine_datetime(date_value, time_value)
    user_id = manual_user.strip() or (selected_user.user_id if isinstance(selected_user, UserCandidate) else str(selected_user))

    if not user_id:
        replay_state["error"] = "User id required to run replay."
        replay_state.pop("rows", None)
        _render_replay_status(replay_state)
        return

    traits = _parse_traits(trait_filter_value)

    try:
        with st.spinner("Replaying stored events…"):
            resolved, _, _, applied = provenance_replay.replay_user_events(
                user_id,
                until=until_ts,
                include_state=True,
            )
    except FileNotFoundError:
        replay_state["error"] = f"No stored events found for user '{user_id}'."
        replay_state.pop("rows", None)
        replay_state.pop("meta", None)
        _render_replay_status(replay_state)
        return
    except Exception as exc:  # noqa: BLE001 - user facing
        replay_state["error"] = str(exc)
        replay_state.pop("rows", None)
        replay_state.pop("meta", None)
        _render_replay_status(replay_state)
        return

    if not applied:
        replay_state["error"] = None
        replay_state["info"] = "No events applied; pick an earlier timestamp or a user with events."
        replay_state["rows"] = []
        replay_state["meta"] = {
            "user": user_id,
            "until": until_ts.isoformat() if until_ts else "(latest)",
            "applied": 0,
            "compare_current": compare_current,
        }
        _render_replay_status(replay_state)
        return

    if traits:
        resolved_subset = {trait: resolved.get(trait) for trait in traits if trait in resolved}
    else:
        resolved_subset = resolved

    current_resolved: Dict[str, Any] | None = None
    if compare_current:
        try:
            current_resolved, _, _ = storage.read_user_state(user_id)
        except Exception:
            current_resolved = None

    rows = _replay_rows(resolved_subset, current_resolved)

    replay_state.clear()
    replay_state.update(
        {
            "rows": rows,
            "meta": {
                "user": user_id,
                "until": until_ts.isoformat() if until_ts else "(latest)",
                "applied": len(applied),
                "compare_current": bool(current_resolved) if compare_current else False,
            },
            "error": None,
            "info": None,
            "manual_user": manual_user,
            "date": date_value,
            "time": time_value,
            "traits_raw": trait_filter_value,
            "compare_current": compare_current,
        }
    )

    _render_replay_results(replay_state)


def _render_replay_status(replay_state: Mapping[str, Any]) -> None:
    error = replay_state.get("error")
    info = replay_state.get("info")
    if error:
        st.error(error)
    elif info:
        st.info(info)


def _render_replay_results(replay_state: Mapping[str, Any]) -> None:
    _render_replay_status(replay_state)
    rows: List[Dict[str, Any]] = replay_state.get("rows") or []
    meta = replay_state.get("meta") or {}

    if rows:
        st.caption(
            f"User: {meta.get('user', 'n/a')} | Until: {meta.get('until', 'n/a')} | Applied events: {meta.get('applied', 0)}"
        )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        download_buttons(
            rows,
            filename_prefix="provenance_replay",
            csv_columns=("container", "trait_id", "value", "ucn", "reasons", "delta"),
            key="prov_replay_export",
        )
    else:
        if not replay_state.get("error"):
            st.info("Replay completed but no traits matched the current filters.")


def _combine_datetime(date_value: dt.date, time_value: dt.time) -> dt.datetime | None:
    if not date_value and not time_value:
        return None
    naive = dt.datetime.combine(date_value, time_value)
    return naive.replace(tzinfo=dt.timezone.utc)


def _parse_traits(raw: str) -> List[str]:
    tokens: List[str] = []
    for line in raw.splitlines():
        token = line.strip()
        if token:
            tokens.append(token)
    return tokens


def _format_bundle_option(candidate: BundleCandidate | None) -> str:
    if not isinstance(candidate, BundleCandidate):
        return "(none)"
    when = dt.datetime.fromtimestamp(candidate.mtime)
    return f"{candidate.label} — {when:%Y-%m-%d %H:%M:%S}"


def _build_diff_context(
    selected_a: BundleCandidate | None,
    selected_b: BundleCandidate | None,
    manual_a: str,
    manual_b: str,
    repo_root: Path,
) -> _DiffContext:
    path_a = _coerce_path(manual_a, selected_a, repo_root)
    path_b = _coerce_path(manual_b, selected_b, repo_root)
    if not path_a or not path_b:
        raise ValueError("Both bundle paths are required.")

    resolved_a = _load_resolved(path_a)
    resolved_b = _load_resolved(path_b)

    return _DiffContext(path_a=path_a, path_b=path_b, resolved_a=resolved_a, resolved_b=resolved_b)


def _coerce_path(
    manual: str,
    candidate: BundleCandidate | None,
    repo_root: Path,
) -> Path | None:
    manual = manual.strip()
    if manual:
        base = Path(manual)
        if not base.is_absolute():
            base = (repo_root / manual).resolve()
        else:
            base = base.resolve()
        if not base.exists():
            raise FileNotFoundError(f"Path not found: {base}")
        return base

    if isinstance(candidate, BundleCandidate):
        return candidate.path
    return None


def _load_resolved(path: Path) -> Dict[str, Any]:
    candidate = path
    if candidate.is_dir():
        nested = candidate / storage.RESOLVED_FILENAME
        if nested.exists():
            candidate = nested
        else:
            raise FileNotFoundError(
                f"Directory {candidate} does not contain {storage.RESOLVED_FILENAME}"
            )

    text = candidate.read_text()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:  # noqa: F841 - keep exact message
        raise ValueError(f"Failed to parse JSON at {candidate}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("resolved"), dict):
        return payload["resolved"]
    if isinstance(payload, dict):
        flattened = _flatten_bundle_like(payload)
        if flattened:
            return flattened
        return payload
    raise ValueError(f"Unsupported payload structure at {candidate}")


def _flatten_bundle_like(payload: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    ignore_keys = {"schema_version", "meta", "provenance", "snapshots", "Evidence"}
    resolved: Dict[str, Dict[str, Any]] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping):
            keys = set(value.keys())
            if {"resolved_value", "ucn"}.issubset(keys):
                resolved[prefix] = {
                    "resolved_value": value.get("resolved_value"),
                    "ucn": value.get("ucn"),
                    "reasons": value.get("reasons", []),
                }
                return
            for child_key, child_value in value.items():
                if prefix == "" and child_key in ignore_keys:
                    continue
                child_prefix = f"{prefix}.{child_key}" if prefix else child_key
                walk(child_prefix, child_value)
        elif isinstance(value, list):
            # Lists do not carry resolved trait structure here.
            return
        else:
            if prefix:
                resolved[prefix] = {
                    "resolved_value": value,
                    "ucn": None,
                    "reasons": [],
                }

    walk("", payload)
    return resolved


def _snapshot(entry: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(entry, Mapping):
        return {"resolved_value": None, "ucn": None, "reasons": []}
    reasons = entry.get("reasons")
    if isinstance(reasons, (list, tuple)):
        reason_list = list(reasons)
    elif reasons is None:
        reason_list = []
    else:
        reason_list = [str(reasons)]
    return {
        "resolved_value": entry.get("resolved_value"),
        "ucn": entry.get("ucn"),
        "reasons": reason_list,
    }


def _diff_rows(context: _DiffContext) -> List[Dict[str, Any]]:
    resolved_a = context.resolved_a
    resolved_b = context.resolved_b
    all_traits = sorted(set(resolved_a.keys()) | set(resolved_b.keys()))
    rows: List[Dict[str, Any]] = []

    for trait in all_traits:
        snap_a = _snapshot(resolved_a.get(trait))
        snap_b = _snapshot(resolved_b.get(trait))
        changed = snap_a != snap_b
        rows.append(
            {
                "container": _container_of(trait),
                "trait_id": trait,
                "from_value": snap_a["resolved_value"],
                "to_value": snap_b["resolved_value"],
                "from_ucn": snap_a["ucn"],
                "to_ucn": snap_b["ucn"],
                "reasons_from": ", ".join(str(item) for item in snap_a["reasons"]),
                "reasons_to": ", ".join(str(item) for item in snap_b["reasons"]),
                "changed": changed,
            }
        )

    return rows


def _filter_diff_rows(
    rows: Sequence[Mapping[str, Any]],
    search_term: str,
    selected_containers: Sequence[str],
    changed_only: bool,
) -> List[Dict[str, Any]]:
    normalized_term = search_term.strip().lower()
    allowed = set(selected_containers) if selected_containers else {row["container"] for row in rows}
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if allowed and row.get("container") not in allowed:
            continue
        if changed_only and not row.get("changed"):
            continue
        if normalized_term:
            haystack = " ".join(
                str(row.get(key, ""))
                for key in ("trait_id", "from_value", "to_value", "reasons_from", "reasons_to")
            ).lower()
            if normalized_term not in haystack:
                continue
        filtered.append(dict(row))
    return filtered


def _container_of(trait_id: str) -> str:
    return trait_id.split(".")[0] if "." in trait_id else trait_id


def _replay_rows(
    resolved: Mapping[str, Any],
    current_resolved: Mapping[str, Any] | None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for trait in sorted(resolved.keys()):
        snap = _snapshot(resolved.get(trait))
        current_snap = _snapshot(current_resolved.get(trait)) if current_resolved else None
        delta = None
        if current_snap and current_snap != snap:
            delta = _describe_delta(snap, current_snap)
        rows.append(
            {
                "container": _container_of(trait),
                "trait_id": trait,
                "value": snap["resolved_value"],
                "ucn": snap["ucn"],
                "reasons": ", ".join(str(item) for item in snap["reasons"]),
                "delta": delta or "",
            }
        )
    return rows


def _describe_delta(previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    changes = []
    if previous.get("resolved_value") != current.get("resolved_value"):
        changes.append("value differs")
    if previous.get("ucn") != current.get("ucn"):
        changes.append("ucn differs")
    if previous.get("reasons") != current.get("reasons"):
        changes.append("reasons differ")
    return ", ".join(changes)
