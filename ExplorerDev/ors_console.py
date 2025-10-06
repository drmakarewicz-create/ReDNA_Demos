"""Observability & Reliability Suite console helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import streamlit as st

from ExplorerDev.diag_utils import (
    apply_service_settings,
    load_service_settings,
    ping_endpoint,
    save_service_settings,
)
from ExplorerDev.snapshot_utils import tail
from ExplorerDev.tracing import trace_log_paths
from ExplorerDev.write_utils import WriteProtectContext


_LOG_DEFNS = [
    ("diagnostics.log", Path("data/dev_logs/diagnostics.log")),
    ("scheduler.log", Path("data/dev_logs/scheduler.log")),
]
_LOG_DEFNS.extend([(name, path) for name, path in trace_log_paths().items()])


def _header_badge(label: str, source: str) -> str:
    return (
        "<span style='display:inline-flex;align-items:center;gap:0.35rem;padding:0.2rem 0.55rem;"
        "border-radius:999px;background:#2c3e50;color:#fff;font-size:0.7rem;'>"
        f"{label}<span style='opacity:0.6;font-size:0.65rem;text-transform:uppercase'>{source}</span></span>"
    )


def render_service_console(context: WriteProtectContext, *, last_ingest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    st.subheader("Service Console")
    service_state = load_service_settings()

    ucnrr_effective = service_state.get("ucnrr_base", "")
    core_effective = service_state.get("core_base", "")
    llm_effective = service_state.get("llm_base", "")
    timeout_effective = service_state.get("timeout", 6.0)
    llm_timeout_effective = service_state.get("llm_timeout", 6.0)

    base_cols = st.columns(2)
    with base_cols[0]:
        st.markdown(_header_badge("UCNRR base", service_state.get("ucnrr_source", "prefs")), unsafe_allow_html=True)
    ucnrr_input = base_cols[0].text_input(
        "UCNRR base",
        value=ucnrr_effective,
        key="ors_ucnrr_base",
        label_visibility="collapsed",
    )
    with base_cols[1]:
        st.markdown(_header_badge("Core base", service_state.get("core_source", "prefs")), unsafe_allow_html=True)
    core_input = base_cols[1].text_input(
        "Core base",
        value=core_effective,
        key="ors_core_base",
        label_visibility="collapsed",
    )

    llm_cols = st.columns(2)
    with llm_cols[0]:
        st.markdown(_header_badge("LLM base", service_state.get("llm_source", "prefs")), unsafe_allow_html=True)
    llm_input = llm_cols[0].text_input(
        "LLM base",
        value=llm_effective,
        key="ors_llm_base",
        label_visibility="collapsed",
    )
    timeout_cols = st.columns(2)
    timeout_value = timeout_cols[0].number_input(
        "HTTP timeout (s)",
        min_value=0.1,
        max_value=60.0,
        step=0.5,
        value=float(timeout_effective),
        key="ors_timeout",
    )
    llm_timeout_value = timeout_cols[1].number_input(
        "LLM timeout (s)",
        min_value=0.1,
        max_value=60.0,
        step=0.5,
        value=float(llm_timeout_effective),
        key="ors_llm_timeout",
    )

    working_settings = {
        "ucnrr_base": ucnrr_input.strip(),
        "core_base": core_input.strip(),
        "llm_base": llm_input.strip(),
        "timeout": float(timeout_value),
        "llm_timeout": float(llm_timeout_value),
    }
    apply_service_settings(working_settings)

    if context.write_protect:
        st.info("Write-protect ON — edits persist only for this session.")
    else:
        if st.button("Save service settings", key="ors_save_settings"):
            try:
                save_service_settings(working_settings, context)
            except PermissionError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover
                st.error(f"Unable to save settings: {exc}")
            else:
                st.success("Service settings saved.")

    ping_cols = st.columns(3)
    results = st.session_state.setdefault("_ors_ping_results", {})
    if ping_cols[0].button("Ping UCNRR", key="ors_ping_ucnrr"):
        results["ucnrr"] = ping_endpoint("ucnrr", working_settings["ucnrr_base"], timeout=working_settings["timeout"])
    if ping_cols[1].button("Ping Core", key="ors_ping_core"):
        results["core"] = ping_endpoint("core", working_settings["core_base"], timeout=working_settings["timeout"])
    if ping_cols[2].button("Ping LLM", key="ors_ping_llm"):
        results["llm"] = ping_endpoint("llm", working_settings["llm_base"], timeout=working_settings["llm_timeout"])

    for name, payload in results.items():
        st.caption(f"Ping {name}")
        st.json(payload)

    curl_placeholder = st.empty()
    if isinstance(last_ingest, Mapping):
        curl = build_curl_snippet(last_ingest, working_settings)
        if curl:
            curl_placeholder.code(curl, language="bash")
    else:
        curl_placeholder.caption("Run an ingest to populate curl snippet.")
    return working_settings


def build_curl_snippet(last_ingest: Mapping[str, Any], service_state: Mapping[str, Any]) -> str:
    try:
        payload = dict(last_ingest.get("payload", {}))
    except Exception:
        payload = {}
    if not payload:
        return ""
    redacted = payload.copy()
    if "text" in redacted and isinstance(redacted["text"], str):
        redacted["text"] = redacted["text"][:160] + ("…" if len(redacted["text"]) > 160 else "")
    if "lines" in redacted and isinstance(redacted["lines"], list):
        redacted["lines"] = redacted["lines"][:5]
    curl = [
        "curl",
        "-X", "POST",
        f"'{service_state.get('ucnrr_base', '').rstrip('/')}/ingest_text'",
        "-H", "Content-Type: application/json",
        "-d",
        json.dumps(redacted, ensure_ascii=False),
    ]
    return " ".join(curl)


def render_log_tailer(context: WriteProtectContext) -> None:
    st.subheader("Log Tailer")
    auto_enabled = st.checkbox("Auto-refresh (5s)", value=False, key="_ors_log_auto")
    if auto_enabled:
        last_tick = st.session_state.get("_ors_log_tick", 0.0)
        now = time.time()
        if now - last_tick > 5.0:
            st.session_state["_ors_log_tick"] = now
            rerun = getattr(st, "rerun", None)
            if callable(rerun):
                rerun()
            else:
                st.experimental_rerun()

    selected = st.selectbox(
        "Log file",
        [label for label, _ in _LOG_DEFNS],
        key="_ors_log_choice",
    )
    path = next(path for label, path in _LOG_DEFNS if label == selected)
    resolved_path = Path.cwd() / path
    content = tail(resolved_path, n=500)
    if content:
        st.code(content, language="text")
    else:
        st.info("No log content available yet.")

    if not context.write_protect and resolved_path.exists():
        try:
            data = resolved_path.read_bytes()
        except Exception as exc:  # pragma: no cover
            st.warning(f"Unable to read log: {exc}")
        else:
            st.download_button(
                "Download log",
                data=data,
                file_name=resolved_path.name,
                mime="text/plain",
            )


def render_trace_explorer() -> None:
    st.subheader("Trace Explorer")
    trace_files = trace_log_paths()
    trace_id = st.text_input("Trace ID", key="_ors_trace_id")
    with st.expander("Advanced filters", expanded=False):
        start_iso = st.text_input("Start (ISO)", key="_ors_trace_start")
        end_iso = st.text_input("End (ISO)", key="_ors_trace_end")
    if not trace_id and not start_iso and not end_iso:
        st.info("Enter a trace ID or time range to search trace logs.")
        return

    rows: List[Dict[str, Any]] = []
    for component, path in trace_files.items():
        resolved = Path.cwd() / path
        if not resolved.exists():
            continue
        try:
            with resolved.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if trace_id and payload.get("trace_id") != trace_id:
                        continue
                    ts = payload.get("ts")
                    if start_iso and ts and ts < start_iso:
                        continue
                    if end_iso and ts and ts > end_iso:
                        continue
                    payload["component"] = component
                    rows.append(payload)
        except Exception:
            continue

    if not rows:
        st.warning("No trace records matched filters.")
        return

    rows.sort(key=lambda entry: entry.get("ts", ""))
    base_ts = rows[0].get("ts")
    st.caption(f"Results ({len(rows)} events)")
    for entry in rows:
        ts = entry.get("ts", "")
        component = entry.get("component", "?")
        span = entry.get("span") or entry.get("event") or "event"
        meta = entry.get("meta", {})
        col = st.container()
        with col:
            st.markdown(
                f"**[{component}] {span}** — {ts}",
            )
            if meta:
                st.json(meta)


def render_ors_console(context: WriteProtectContext, *, last_ingest: Optional[Dict[str, Any]]) -> None:
    working_state = render_service_console(context, last_ingest=last_ingest)
    st.markdown("---")
    render_log_tailer(context)
    st.markdown("---")
    render_trace_explorer()


__all__ = [
    "render_ors_console",
    "build_curl_snippet",
]
