"""Developer Explorer shell for ReDNA demos."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root
except Exception:  # pragma: no cover - fallback when invoked directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root  # type: ignore

_bootstrap_info = ensure_explorerdev_on_path()

# Remaining imports are safe after bootstrap above
import csv
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import traceback
from html import escape
from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta, time as dt_time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import uuid

import requests
import streamlit as st
from urllib.parse import urlencode

try:  # optional dependency; mirror Control Panel Plus behaviour
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

try:  # optional dependency for a richer table view
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None

try:  # optional dependency for analytics charts
    import altair as alt  # type: ignore
except Exception:  # pragma: no cover
    alt = None  # type: ignore

try:
    from ReDNACoreDemo.core import persona_registry  # type: ignore
    from ReDNACoreDemo.core.persona_registry import dump_registry_snapshot  # type: ignore
except Exception:  # pragma: no cover
    persona_registry = None  # type: ignore
    dump_registry_snapshot = None  # type: ignore

from ExplorerDev import audit_utils, registry_helpers, snapshot_utils
from ExplorerDev.ai_suggester import LLMConfig, build_prompt_meta
from ExplorerDev.container_studio import (
    DRAFT_KEY,
    LIVE_ERROR_KEY,
    LIVE_MODE_KEY,
    LIVE_SNAPSHOT_KEY,
    LIVE_USER_KEY,
    SELECTED_CONTAINER_KEY,
    SELECTED_TRAIT_KEY,
    render_container_studio,
)
from ExplorerDev.diag_utils import (
    DIAGNOSTICS_LOG_PATH,
    SCHEDULER_LOG_PATH,
    build_loop_config,
    load_service_settings,
    apply_service_settings,
    ping_endpoint,
    run_ingest_round_trip,
    run_loop_test,
    run_prompt_source_checks,
    save_service_settings,
)
from ExplorerDev.ingest_presets import get_preset, list_presets
from ExplorerDev.health_utils import check_health
from ExplorerDev.curiosity_utils import curiosity_chip_label, resolve_curiosity_mode
from ExplorerDev.rr_baseline_utils import change_log_path as rr_change_log_path, current_baselines_path, is_demo_enabled
from ExplorerDev.credna import credna_ops, credna_store
from ExplorerDev.credna.credna_ui import render_credna_studio
from ExplorerDev.rr_baselines_lab import render_rr_baselines_lab
from ExplorerDev.regression_card import render_regression_card
from ExplorerDev.ui_contracts_card import render_ui_contracts_card
from ExplorerDev.provenance_lab import render_provenance_lab
from ExplorerDev.scheduler_utils import (
    append_run_history,
    load_run_history,
    load_scheduler_prefs,
    run_now_probe,
    save_scheduler_prefs,
)
from ExplorerDev.nudge_bus import enqueue as enqueue_nudge, log_path as nudge_log_path
from ExplorerDev.schema_utils import (
    FeedbackAggregate,
    LiveCuriositySnapshot,
    core_base_state,
    core_base_url,
    curiosity_flag_state,
    compute_feedback_multiplier,
    get_flag_bool,
    get_flag_float,
    get_flag_str,
    fetch_feedback_aggregates,
    fetch_live_curiosity_rows,
    load_live_curiosity_snapshot,
    load_saved_draft,
    load_schema,
    locate_container,
    locate_trait,
    llm_base_state,
    llm_base_url,
    resolve_motivator_template,
    simulated_curiosity_rows,
    ucnrr_base_state,
    ucnrr_base_url,
)
from ExplorerDev.write_utils import write_guard
from ExplorerDev.ors_console import render_ors_console
from ExplorerDev.dev_tools_ui import render_dev_tools
from ExplorerFinal.core import nudge_store


DEV_TRUE_SET = {"1", "true", "yes", "on"}

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8015").rstrip("/")
REACT_BASE = os.getenv("REACT_BASE", "http://127.0.0.1:3000").rstrip("/")
CPPP_BASE = os.getenv("CP_PLUS_PLUS_BASE", "http://127.0.0.1:8501").rstrip("/")
CORE_CURIOSITY_ENABLED = os.getenv("CORE_CURIOSITY_ENABLED", "false").strip().lower() in DEV_TRUE_SET
CORE_CURIOSITY_HEALTH_PATH = os.getenv("CORE_CURIOSITY_HEALTH_PATH", "/curiosity/health")
UCNRR_RECOMPUTE_NOTICE_KEY = "_ucnrr_recompute_notice"


def _coerce_epoch(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            return int(float(token))
        if isinstance(value, (int, float)):
            return int(value)
    except (TypeError, ValueError):
        return None
    return None


def _format_ucnrr_ts(ts_value: int) -> str:
    try:
        if ts_value > 1_000_000_000_000:
            dt = datetime.fromtimestamp(ts_value / 1000.0, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(ts_value, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return str(ts_value)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


@st.cache_data(ttl=5.0, show_spinner=False)
def fetch_ucnrr_health(core_base: str) -> Dict[str, Any]:
    if not core_base:
        return {"reachable": False, "reason": "core base missing"}

    url = core_base.rstrip("/") + "/ui/ucnrr/health"
    try:
        response = requests.get(url, timeout=1.5)
    except requests.RequestException as exc:  # pragma: no cover - network failures
        return {"reachable": False, "reason": str(exc)}

    status = response.status_code
    if status == 404:
        return {"reachable": False, "reason": "endpoint not configured", "status": status}
    if status != 200:
        return {"reachable": False, "reason": f"http {status}", "status": status}

    try:
        payload = response.json()
    except ValueError:
        return {"reachable": False, "reason": "invalid json", "status": status}

    if isinstance(payload, dict):
        payload.setdefault("status", status)
        return payload

    return {"reachable": False, "reason": "unexpected payload", "status": status}


@st.cache_data(ttl=5.0, show_spinner=False)
def fetch_core_errors(core_base: str, *, limit: int = 200) -> Dict[str, Any]:
    if not core_base:
        return {"ok": False, "reason": "core base missing"}

    url = core_base.rstrip("/") + f"/ui/debug/errors?limit={limit}"
    try:
        response = requests.get(url, timeout=1.5)
    except requests.RequestException as exc:  # pragma: no cover - network failures
        return {"ok": False, "reason": str(exc)}

    status = response.status_code
    if status == 404:
        return {"ok": False, "reason": "endpoint not available", "status": status}
    if status != 200:
        return {"ok": False, "reason": f"http {status}", "status": status}

    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "reason": "invalid json"}

    return {"ok": True, "payload": payload}


def _trigger_ucnrr_recompute(core_base: str, user_id: str) -> Tuple[str, str]:
    if not core_base:
        return "error", "Core base URL missing."
    if not user_id:
        return "warning", "Set an active user before running recompute."

    url = core_base.rstrip("/") + f"/recompute/{user_id}"
    try:
        response = requests.post(url, timeout=10)
    except requests.RequestException as exc:  # pragma: no cover - network failures
        return "error", f"Recompute failed: {exc}"

    if response.status_code == 404:
        return "info", "Not configured (404)."
    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            if isinstance(body, Mapping):
                detail = str(body.get("message") or body.get("error") or body.get("detail") or "").strip()
        except ValueError:
            detail = (response.text or "").strip()
        detail = detail[:200]
        if not detail:
            detail = "Recompute failed."
        return "error", f"HTTP {response.status_code}: {detail}"

    message = "Recompute triggered."
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, Mapping):
        if payload.get("ok"):
            count = payload.get("resolved_count")
            if isinstance(count, int):
                message = f"Recompute complete ({count} traits)."
        elif payload.get("message"):
            message = str(payload.get("message"))

    return "success", message


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024.0
    return f"{size} B"


def _get_nav_params() -> Dict[str, Any]:
    """Return the current query params as a dict, resilient to Streamlit versions."""

    try:
        return dict(st.query_params)
    except Exception:
        pass
    try:
        legacy_params = st.experimental_get_query_params()
    except Exception:
        return {}
    if not isinstance(legacy_params, Mapping):
        return {}
    normalized: Dict[str, Any] = {}
    for key, value in legacy_params.items():
        if isinstance(value, list):
            normalized[key] = value[0] if value else None
        else:
            normalized[key] = value
    return normalized


REPO_ROOT = ensure_repo_root()
ENV_PATH = REPO_ROOT / ".env"

if load_dotenv and ENV_PATH.exists():
    load_dotenv(ENV_PATH)


PERSONA_IMPORTS: Sequence[Tuple[str, str]] = (
    ("relationship_coach", "ExplorerFinal.ui.personas.relationship_coach"),
    ("photo", "ExplorerFinal.ui.personas.photo"),
    ("padna", "ExplorerFinal.ui.personas.padna"),
)

REGISTRY_SNAPSHOT_PATH = REPO_ROOT / "data/dev_persona_registry.json"
EXPLORER_FINAL_ROOT = REPO_ROOT / "ExplorerFinal"
PERSONA_SWITCH_LOG_PATH = REPO_ROOT / "data/dev_logs/persona_switch.log"
PRESET_BUNDLES = {
    "Demo A": REPO_ROOT / "snapshots/ExplorerDemo/tests/sample_head_coach_bundle.json",
    "Demo B": REPO_ROOT / "snapshots/ExplorerDemo/tests/sample_head_coach_bundle_b.json",
    "Demo C": REPO_ROOT / "snapshots/ExplorerDemo/tests/head_coach_demo_bundle2.json",
}

USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
USER_ACTION_STATE_KEY = "_user_mgmt_pending"
USER_RESULT_STATE_KEY = "_user_mgmt_result"
USER_DELETE_CONFIRM_KEY = "_user_mgmt_delete_confirm"
DIAG_STEP_LABELS = {
    "explorer_to_ucnrr": "Explorer → UCN/RR",
    "ucnrr_to_core": "UCN/RR → Core",
    "core_recompute": "Core recompute",
    "ucnrr_to_explorer": "Core → Explorer readback",
}
SANDBOX_TONE_OPTIONS = ["Gentle", "Neutral", "Blunt"]
SANDBOX_MICRO_ACTIONS = {
    "Ask for one example": "example",
    "Offer next step": "next_step",
    "Summarize in one line": "summary",
    "Ask for confirmation": "confirm",
}

HEAD_COACH_INTENTS = {
    "None": {"token": "", "suffix": ""},
    "Check-in": {
        "token": "check_in",
        "suffix": "Close with a warm prompt for a quick status update from the member.",
    },
    "Clarify": {
        "token": "clarify",
        "suffix": "Invite the member to clarify any details that feel vague or uncertain.",
    },
    "Next step": {
        "token": "next_step",
        "suffix": "Suggest a concrete next step the member can take after reading the motivator.",
    },
    "Accountability": {
        "token": "accountability",
        "suffix": "Highlight an accountability angle so the member knows what to follow through on.",
    },
}


def _coerce_int(value: Any, default: int = 50, lo: int = 0, hi: int = 100) -> int:
    try:
        coerced = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, coerced))


def _norm_tone(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token == "gentle":
        return "Gentle"
    if token == "blunt":
        return "Blunt"
    return "Neutral"


REGISTRY_STYLE_BLOCK = """
<style>
.dev-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.55rem;
    border-radius: 1rem;
    border: 1px solid var(--stColorSecondary); 
    background: rgba(0, 0, 0, 0.03);
    font-size: 0.85rem;
    font-weight: 500;
    margin-right: 0.35rem;
    margin-bottom: 0.25rem;
    white-space: nowrap;
}
.dev-chip strong {
    font-weight: 600;
}
.dev-chip--warn {
    border-color: #c77700;
    background: #fff6e6;
    color: #8a4f00;
}
.dev-chip--ok {
    border-color: #1d8f4d;
    background: #e7f6ed;
    color: #10532d;
}
.registry-chip-wrap {
    display: flex;
    flex-wrap: wrap;
}
.registry-chip-wrap .dev-chip:last-child {
    margin-right: 0;
}
.import-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.5rem;
}
.import-table th {
    text-align: left;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
    padding: 0.25rem 0.4rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}
.import-table td {
    padding: 0.35rem 0.4rem;
    vertical-align: top;
    font-size: 0.85rem;
}
.status-badge {
    display: inline-block;
    padding: 0 0.45rem;
    border-radius: 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid rgba(0, 0, 0, 0.15);
}
.status-badge.ok {
    background: #e4f7ec;
    color: #136f34;
    border-color: #8fd4a7;
}
.status-badge.skipped {
    background: #f2f2f2;
    color: #5a5a5a;
}
.status-badge.error {
    background: #ffe6e6;
    color: #a11e1e;
    border-color: #e89c9c;
}
.persona-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.75rem;
}
.persona-table thead th {
    text-align: left;
    font-size: 0.8rem;
    padding: 0.3rem 0.45rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    position: sticky;
    top: 0;
    background: var(--background-color);
    z-index: 2;
}
.persona-table tbody tr {
    border-bottom: 1px solid rgba(0, 0, 0, 0.07);
    transition: background-color 0.15s ease;
}
.persona-table tbody tr:hover {
    background: rgba(36, 99, 178, 0.08);
}
.persona-table tbody tr.selected {
    background: rgba(36, 99, 178, 0.16);
}
.persona-table tbody tr.selected:hover {
    background: rgba(36, 99, 178, 0.16);
}
.persona-table tbody tr.skipped {
    opacity: 0.55;
}
.persona-table tbody tr.skipped:hover {
    background: rgba(36, 99, 178, 0.08);
}
.persona-table td {
    padding: 0.4rem 0.45rem;
    font-size: 0.85rem;
    vertical-align: top;
}
.persona-table td .status-note {
    font-size: 0.75rem;
    color: var(--secondary-text-color);
}
.persona-table td .action-button {
    background: transparent;
    border: none;
    padding: 0;
    font: inherit;
    text-align: left;
    width: 100%;
    cursor: pointer;
}
.persona-table td .action-button:hover {
    text-decoration: underline;
}
.persona-table td .action-button:disabled {
    cursor: not-allowed;
    color: #999;
}
.persona-sticky-header {
    position: sticky;
    top: 3.5rem;
    z-index: 10;
    background: var(--background-color);
    padding: 0.75rem 0.25rem 0.4rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    margin-bottom: 0.5rem;
}
.persona-sticky-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
}
.persona-sticky-row .spacer {
    flex-grow: 1;
}
.persona-sticky-row .jump-link {
    font-size: 0.8rem;
    margin-left: 0.35rem;
}
.persona-sticky-row .jump-link a {
    text-decoration: none;
}
.persona-action {
    border: 1px solid var(--stColorSecondary);
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.03);
    padding: 0.25rem 0.85rem;
    font-size: 0.8rem;
    cursor: pointer;
}
.persona-action:hover {
    background: rgba(0, 0, 0, 0.08);
}
.prompt-source-order {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
}
.prompt-source-order li {
    list-style: none;
    font-size: 0.85rem;
}
.prompt-source-order li.active {
    font-weight: 600;
}
.sandbox-disabled {
    border: 1px solid #4a80d4;
    background: #e6f0ff;
    padding: 0.75rem;
    border-radius: 0.5rem;
}
</style>
"""


def _ensure_persona_registry_styles() -> None:
    if st.session_state.get("_persona_registry_styles_injected"):
        return
    st.markdown(REGISTRY_STYLE_BLOCK, unsafe_allow_html=True)
    st.session_state["_persona_registry_styles_injected"] = True


def _safe_rerun() -> None:
    """Trigger a rerun across Streamlit versions."""

    import streamlit as st  # local import to avoid circulars during typing

    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return

    legacy_fn = getattr(st, "experimental_rerun", None)
    if callable(legacy_fn):  # pragma: no cover - backward compatibility path
        legacy_fn()


def _get_loop_user_id() -> str:
    import streamlit as st
    from ExplorerDev.schema_utils import get_flag_str

    stored = st.session_state.get("_loop_user_id")
    if isinstance(stored, str):
        trimmed = stored.strip()
        if trimmed:
            return trimmed

    default_value, _ = get_flag_str("DEV_LOOPTEST_USER_ID", "devexp_test")
    return (default_value or "devexp_test").strip() or "devexp_test"


def _set_loop_user_id(value: Any, defer_rerun: bool = False) -> None:
    import streamlit as st

    text = str(value or "").strip()
    st.session_state["_loop_user_id"] = text
    if defer_rerun:
        st.session_state["_deferred_rerun"] = True


def _get_head_coach_user_id() -> str:
    import streamlit as st

    value = st.session_state.get("_head_coach_user_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _get_loop_user_id()


def _set_head_coach_user_id(value: Any, defer_rerun: bool = False) -> None:
    import streamlit as st

    st.session_state["_head_coach_user_id"] = str(value or "").strip()
    if defer_rerun:
        st.session_state["_deferred_rerun"] = True


def _render_env_lock_pill() -> None:
    st.markdown(
        "<span style='display:inline-flex;align-items:center;gap:0.35rem;"
        "padding:0.15rem 0.6rem;border-radius:999px;background:rgba(0,0,0,0.05);"
        "font-size:0.7rem;font-weight:600;' title='Change in Control Panel Plus or relaunch without env override.'>"
        "🔒 Controlled by CP+ (env)</span>",
        unsafe_allow_html=True,
    )


def _handle_copy(label: str, value: str) -> None:
    st.session_state["_status_strip_copy_notice"] = {
        "label": label,
        "value": value,
    }


def _hydrate_uuid(template: str) -> str:
    if "{{uuid}}" not in template:
        return template
    return template.replace("{{uuid}}", str(uuid.uuid4()))


def _render_ingest_harness(context: DevWriteContext) -> None:
    st.subheader("Ingest Harness")
    st.caption("Craft test evidence, send it through UCNRR/Core, and inspect the round-trip impact.")

    mode_info = resolve_curiosity_mode(LIVE_MODE_KEY)
    st.caption(f"Curiosity mode: {curiosity_chip_label(mode_info)}")
    if mode_info.forced:
        _render_env_lock_pill()

    default_user = _get_loop_user_id()
    st.session_state.setdefault("_ingest_user_id", default_user)

    user_cols = st.columns([3, 1])
    with user_cols[0]:
        user_value = st.text_input(
            "User id",
            key="_ingest_user_id",
            help="Target user that will receive the ingest evidence.",
        ).strip()
    with user_cols[1]:
        if st.button("Use Diagnostics id", key="ingest_use_diag_id"):
            st.session_state["_ingest_user_id"] = _get_loop_user_id()
            _safe_rerun()
            return

    if not user_value:
        user_value = default_user

    DEFAULT_BODIES = {
        "text": "Just checking in on this member's latest engagement notes.",
        "key=value": "devexp_ping={{uuid}}",
        "json": (
            "{\n"
            "  \"user_id\": \"\",\n"
            "  \"text\": \"Member shared a short update worth logging.\",\n"
            "  \"provenance\": {\"source\": \"devexp\", \"kind\": \"note\"}\n"
            "}"
        ),
    }

    type_options = [("Text", "text"), ("Key=Value", "key=value"), ("JSON", "json")]
    st.session_state.setdefault("_ingest_payload_label", "Text")
    label_to_type = {label: token for label, token in type_options}
    type_label = st.radio(
        "Payload type",
        [label for label, _ in type_options],
        key="_ingest_payload_label",
        horizontal=True,
    )
    payload_type = label_to_type.get(type_label, "text")

    prev_payload_type = st.session_state.get("_ingest_payload_type_norm")
    if prev_payload_type != payload_type:
        st.session_state["_ingest_payload_type_norm"] = payload_type
        st.session_state["_ingest_selected_preset"] = ""
        st.session_state["_ingest_body"] = _hydrate_uuid(DEFAULT_BODIES.get(payload_type, ""))

    st.session_state.setdefault(
        "_ingest_body",
        _hydrate_uuid(DEFAULT_BODIES.get(payload_type, "")),
    )
    st.session_state.setdefault("_ingest_prov_source", "devexp")
    st.session_state.setdefault("_ingest_prov_kind", "note")
    st.session_state.setdefault("_ingest_prov_tags", "")
    st.session_state.setdefault("_ingest_selected_preset", "")

    presets = list_presets(payload_type)
    preset_options = ["" ] + [entry["key"] for entry in presets]
    preset_labels = {"": "— No preset —"}
    for entry in presets:
        preset_labels[entry["key"]] = str(entry.get("label") or entry["key"])

    previous_preset = st.session_state.get("_ingest_selected_preset", "")
    current_preset = st.selectbox(
        "Preset",
        options=preset_options,
        index=preset_options.index(previous_preset) if previous_preset in preset_options else 0,
        format_func=lambda key: preset_labels.get(key, key),
        key="_ingest_selected_preset",
    )

    if current_preset != previous_preset:
        if current_preset:
            preset_payload = get_preset(payload_type, current_preset)
            if preset_payload:
                body_template = str(preset_payload.get("body") or "")
                st.session_state["_ingest_body"] = _hydrate_uuid(body_template)
                prov_block = preset_payload.get("provenance") or {}
                if isinstance(prov_block, Mapping):
                    if prov_block.get("source"):
                        st.session_state["_ingest_prov_source"] = str(prov_block.get("source"))
                    if prov_block.get("kind"):
                        st.session_state["_ingest_prov_kind"] = str(prov_block.get("kind"))
                    tags = prov_block.get("tags")
                    if isinstance(tags, (list, tuple, set)):
                        st.session_state["_ingest_prov_tags"] = ", ".join(str(tag) for tag in tags)
                    elif isinstance(tags, str):
                        st.session_state["_ingest_prov_tags"] = tags
            _safe_rerun()
            return
        else:
            st.session_state["_ingest_body"] = _hydrate_uuid(DEFAULT_BODIES.get(payload_type, ""))
            _safe_rerun()
            return

    option_cols = st.columns([2, 1])
    with option_cols[0]:
        top_n = st.slider(
            "Top N traits",
            min_value=3,
            max_value=15,
            value=st.session_state.get("_ingest_top_n", 6),
            key="_ingest_top_n",
        )
    with option_cols[1]:
        capture_before = st.checkbox(
            "Capture 'before' snapshot",
            help="Fetch curiosity before sending to compute deltas.",
            key="_ingest_capture_before",
        )

    body_value = st.text_area(
        "Evidence body",
        key="_ingest_body",
        height=200,
        help="Payload sent to UCNRR. Editable regardless of preset.",
    )

    with st.expander("Provenance builder", expanded=False):
        st.text_input("Source", key="_ingest_prov_source")
        st.text_input("Kind", key="_ingest_prov_kind")
        st.text_input(
            "Tags (comma separated)",
            key="_ingest_prov_tags",
        )

    uc_base_value, _ = ucnrr_base_state()
    endpoint_display = (uc_base_value or "").rstrip("/") + "/ingest_text" if uc_base_value else "(UCNRR base not configured)"
    timeout_value, _ = get_flag_float("DEV_HTTP_TIMEOUT_SECONDS", 12.0)
    try:
        timeout_seconds = float(timeout_value)
    except (TypeError, ValueError):
        timeout_seconds = 12.0
    timeout_seconds = max(0.1, timeout_seconds)
    st.caption(f"Posting to: {endpoint_display} (timeout: {timeout_seconds:.1f}s)")

    button_cols = st.columns([1, 1, 1])
    send_clicked = button_cols[0].button(
        "Send evidence",
        type="primary",
        key="ingest_send_btn",
    )
    ping_clicked = button_cols[1].button("Ping UCNRR", key="ingest_ping_btn")
    clear_clicked = button_cols[2].button("Clear", key="ingest_clear_btn")

    notice_placeholder = st.empty()
    ping_result_placeholder = st.empty()

    if context.write_protect:
        notice_placeholder.caption("Write-protect ON — dry-run (no dev log entries).")

    if clear_clicked:
        st.session_state["_ingest_body"] = _hydrate_uuid(DEFAULT_BODIES.get(payload_type, ""))
        st.session_state["_ingest_prov_source"] = "devexp"
        st.session_state["_ingest_prov_kind"] = "note"
        st.session_state["_ingest_prov_tags"] = ""
        st.session_state["_ingest_selected_preset"] = ""
        _safe_rerun()
        return

    if ping_clicked:
        ping_result = ping_endpoint("ucnrr", uc_base_value or "", timeout=timeout_seconds)
        st.session_state["_ingest_ping_result"] = {
            "result": ping_result,
            "endpoint": uc_base_value,
        }

    ping_state = st.session_state.get("_ingest_ping_result")
    if isinstance(ping_state, dict):
        payload = ping_state.get("result", {}) if isinstance(ping_state.get("result"), dict) else {}
        ok = bool(payload.get("ok"))
        status = payload.get("status")
        body_preview = payload.get("body")
        with ping_result_placeholder.container():
            if ok:
                chip_html = (
                    "<span style='display:inline-block;margin-right:0.4rem;padding:0.2rem 0.55rem;"
                    "border-radius:999px;font-size:0.78rem;background:#4caf50;color:#fff;'>"
                    f"health {status if status is not None else 'n/a'}"
                    "</span>"
                )
                st.markdown(chip_html, unsafe_allow_html=True)
                st.success("UCNRR health OK")
            else:
                status_label = status if status is not None else "ERR"
                chip_html = (
                    "<span style='display:inline-block;margin-right:0.4rem;padding:0.2rem 0.55rem;"
                    "border-radius:999px;font-size:0.78rem;background:#d9534f;color:#fff;'>"
                    f"health {status_label}"
                    "</span>"
                )
                st.markdown(chip_html, unsafe_allow_html=True)
                st.warning("UCNRR health probe failed.")
            if body_preview:
                st.code(str(body_preview), language="json" if str(body_preview).startswith("{") else "text")

    provenance_payload = {
        "source": st.session_state.get("_ingest_prov_source", ""),
        "kind": st.session_state.get("_ingest_prov_kind", ""),
        "tags": st.session_state.get("_ingest_prov_tags", ""),
    }

    if send_clicked:
        if not user_value:
            st.error("User id is required before sending evidence.")
        else:
            with st.spinner("Sending evidence and collecting round-trip…"):
                try:
                    result = run_ingest_round_trip(
                        user_id=user_value,
                        payload_type=payload_type,
                        body=body_value,
                        provenance=provenance_payload,
                        write_context=context,
                        use_live_curiosity=mode_info.effective_live,
                        include_before=capture_before,
                        top_n=int(top_n),
                        timeout_override=timeout_seconds,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    result["inputs"] = {
                        "user_id": user_value,
                        "payload_type": payload_type,
                        "capture_before": bool(capture_before),
                        "top_n": int(top_n),
                    }
                    st.session_state["_ingest_last_result"] = result
                    st.session_state["_ingest_last_payload"] = {
                        "body": body_value,
                        "provenance": dict(provenance_payload),
                        "payload_type": payload_type,
                    }
                    if not context.write_protect and result.get("log_path"):
                        notice_placeholder.caption(
                            f"Log entry appended to {result['log_path']}"
                        )
                    elif context.write_protect:
                        notice_placeholder.caption(
                            "Write-protect ON — dry-run (no dev log entries)."
                        )

    result_state = st.session_state.get("_ingest_last_result")
    if not result_state:
        return

    st.markdown("#### Round-trip results")

    trace_id_value = result_state.get("trace_id") or result_state.get("ucnrr", {}).get("trace_id")
    if trace_id_value:
        trace_cols = st.columns([0.85, 0.15])
        with trace_cols[0]:
            st.caption("Trace ID")
            st.code(trace_id_value, language="text")
        with trace_cols[1]:
            st.markdown(
                "<button class='persona-action' type='button' style='margin-top:1.7rem' "
                f"onclick=\"navigator.clipboard.writeText({json.dumps(trace_id_value)})\">Copy</button>",
                unsafe_allow_html=True,
            )

    def _chip(text: str, color: str) -> str:
        safe = escape(text)
        return (
            "<span style='display:inline-block;margin-right:0.35rem;padding:0.2rem 0.55rem;"
            "border-radius:999px;font-size:0.78rem;background:" + color + ";color:#fff;'>"
            + safe
            + "</span>"
        )

    ack = result_state.get("ucnrr", {})
    ack_ok = bool(ack.get("ok"))
    ack_code = ack.get("http")
    ack_elapsed = ack.get("elapsed_ms")
    chips: List[str] = []
    if ack_code is not None:
        chips.append(_chip(f"UCNRR {ack_code}", "#4caf50" if ack_ok else "#d9534f"))
    if isinstance(ack_elapsed, (int, float)):
        chips.append(_chip(f"{ack_elapsed:.0f} ms", "#17a2b8"))
    if chips:
        st.markdown("".join(chips), unsafe_allow_html=True)

    preview = ack.get("preview") or ""
    transport_error = ack.get("error")
    if ack_ok:
        st.success("UCNRR acknowledged the evidence payload.")
    else:
        error_msg = transport_error or (f"HTTP {ack_code}" if ack_code is not None else "No response")
        st.error(f"UCNRR ingest failed: {error_msg}")

    circuit_info = ack.get("circuit") if isinstance(ack.get("circuit"), Mapping) else {}
    if circuit_info.get("open"):
        reset_label = circuit_info.get("reset_at") or "pending"
        retry_ms = circuit_info.get("retry_after_ms")
        if isinstance(retry_ms, (int, float)) and retry_ms > 0:
            st.warning(
                f"Circuit breaker open — forwarding paused. Retry after {retry_ms / 1000:.1f}s (reset ETA {reset_label})."
            )
        else:
            st.warning(f"Circuit breaker open — forwarding paused until {reset_label}.")
    elif circuit_info:
        st.caption("Circuit status: closed.")

    if preview:
        st.code(preview, language="json" if preview.strip().startswith("{") else "text")
    else:
        st.caption("No response body returned.")

    attempts = result_state.get("attempts") if isinstance(result_state.get("attempts"), list) else []
    if attempts:
        attempt_lines: List[str] = []
        for attempt in attempts:
            if not isinstance(attempt, Mapping):
                continue
            label = f"Attempt {attempt.get('attempt', '?')}"
            timeout_label = attempt.get("timeout")
            if isinstance(timeout_label, (int, float)):
                label += f" · timeout {timeout_label:.1f}s"
            if attempt.get("timed_out"):
                label += " · timed out"
            elif attempt.get("status") is not None:
                label += f" · status {attempt.get('status')}"
            elif attempt.get("error"):
                label += f" · error"
            attempt_lines.append(label)
        if attempt_lines:
            st.caption("; ".join(attempt_lines))

    ack_body_full = ack.get("body")
    if ack_body_full is not None:
        with st.expander("Show full UCNRR response", expanded=False):
            if isinstance(ack_body_full, (dict, list)):
                st.json(ack_body_full)
            else:
                st.code(str(ack_body_full))

    st.markdown("##### Core changes")
    core_changes = result_state.get("core_changes", {})
    changed_items = core_changes.get("changed") if isinstance(core_changes.get("changed"), list) else []
    if core_changes.get("ok") and changed_items:
        display_rows: List[Dict[str, Any]] = []
        for item in changed_items[:10]:
            if isinstance(item, Mapping):
                display_rows.append(
                    {
                        "trait": item.get("trait_id") or item.get("trait") or "?",
                        "old": item.get("old") or item.get("previous"),
                        "new": item.get("new") or item.get("current"),
                    }
                )
        if display_rows:
            if pd:
                st.dataframe(pd.DataFrame(display_rows))  # type: ignore[arg-type]
            else:
                st.table(display_rows)
        if len(changed_items) > 10:
            with st.expander("All core change rows"):
                st.json(changed_items)
        counts = core_changes.get("counts")
        if isinstance(counts, Mapping) and counts:
            count_parts = [f"{key}={counts[key]}" for key in counts]
            st.caption("Counts: " + ", ".join(count_parts))
    else:
        message = core_changes.get("message") or "No core change payload returned."
        st.caption(message)

    st.markdown("##### Curiosity deltas")
    curiosity = result_state.get("curiosity", {})
    mode_label = str(curiosity.get("mode") or "simulated")
    st.caption(f"Curiosity source: {mode_label}")
    if mode_label != "live":
        st.info("Curiosity deltas use simulated data — live curiosity is disabled.")

    before_error = curiosity.get("before_error")
    after_error = curiosity.get("after_error")
    if before_error:
        st.info(f"Before snapshot unavailable: {before_error}")
    if after_error:
        st.info(f"After snapshot unavailable: {after_error}")

    curiosity_attempts = curiosity.get("attempts") if isinstance(curiosity.get("attempts"), list) else []
    retry_limit = curiosity.get("retry_limit") or (3 if mode_label == "live" else 1)
    backoff_ms = curiosity.get("backoff_ms")
    if curiosity_attempts:
        attempt_summaries: List[str] = []
        for attempt in curiosity_attempts:
            if not isinstance(attempt, Mapping):
                continue
            label = f"{attempt.get('attempt', '?')}/{retry_limit}"
            delta_count = attempt.get("delta_count")
            if isinstance(delta_count, (int, float)):
                label += f" · Δ={int(delta_count)}"
            err = attempt.get("error")
            if err:
                label += " · error"
            attempt_summaries.append(label)
        if attempt_summaries:
            note = "; ".join(attempt_summaries)
            if isinstance(backoff_ms, (int, float)) and backoff_ms:
                note += f" · backoff {backoff_ms/1000:.2f}s"
            st.caption(f"Curiosity fetch attempts: {note}")

    delta_rows = curiosity.get("deltas") if isinstance(curiosity.get("deltas"), list) else []

    def _pct(value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value) * 100:.1f}%"
        return "—"

    if delta_rows:
        table_rows: List[Dict[str, Any]] = []
        for entry in delta_rows:
            if not isinstance(entry, Mapping):
                continue
            container_id = entry.get("container_id") or "?"
            trait_id = entry.get("trait_id") or "?"
            trait_path = f"{container_id}.{trait_id}" if container_id and trait_id else trait_id
            table_rows.append(
                {
                    "Trait": trait_path,
                    "Before": _pct(entry.get("curiosity_before")),
                    "After": _pct(entry.get("curiosity_after")),
                    "Δ": _pct(entry.get("delta")),
                    "UCN": _pct(entry.get("ucn_after")),
                }
            )
        if table_rows:
            if pd:
                st.dataframe(pd.DataFrame(table_rows))  # type: ignore[arg-type]
            else:
                st.table(table_rows)
    else:
        after_rows = curiosity.get("after") if isinstance(curiosity.get("after"), list) else []
        if after_rows:
            display_rows = []
            for entry in after_rows:
                if not isinstance(entry, Mapping):
                    continue
                container_id = entry.get("container_id") or ""
                trait_id = entry.get("trait_id") or ""
                trait_path = f"{container_id}.{trait_id}" if container_id and trait_id else trait_id
                display_rows.append(
                    {
                        "Trait": trait_path,
                        "Curiosity": _pct(entry.get("curiosity")),
                        "UCN": _pct(entry.get("ucn")),
                    }
                )
            if display_rows:
                st.caption("Showing after snapshot only; capture 'before' to compute deltas.")
                if pd:
                    st.dataframe(pd.DataFrame(display_rows))  # type: ignore[arg-type]
                else:
                    st.table(display_rows)
        else:
            st.caption("Curiosity snapshots unavailable.")

    log_path = result_state.get("log_path")
    if not context.write_protect and log_path:
        st.caption(f"Logged ingest round-trip to `{log_path}`.")

    timeout_hint = result_state.get("timeout_hint")
    if isinstance(timeout_hint, str) and timeout_hint:
        if "reachable" in timeout_hint:
            st.info(timeout_hint)
        else:
            st.error(timeout_hint)
        health_payload = result_state.get("health")
        if isinstance(health_payload, Mapping):
            status = health_payload.get("status")
            body = health_payload.get("body")
            st.caption(f"Health probe status: {status if status is not None else 'ERR'}")
            if body:
                st.code(
                    str(body),
                    language="json" if str(body).startswith("{") else "text",
                )

    auto_snapshot = result_state.get("auto_snapshot")
    if isinstance(auto_snapshot, Mapping):
        if auto_snapshot.get("ok") and auto_snapshot.get("snapshot_id"):
            st.info(f"Auto snapshot captured: {auto_snapshot.get('snapshot_id')}")
        elif auto_snapshot.get("error"):
            st.warning(f"Auto snapshot failed: {auto_snapshot.get('error')}")



def _ensure_live_curiosity_snapshot(*, force: bool = False) -> Optional[LiveCuriositySnapshot]:
    user_id = str(st.session_state.get(LIVE_USER_KEY, "")).strip()
    if not user_id:
        st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
        st.session_state.pop(LIVE_ERROR_KEY, None)
        st.session_state["_core_curiosity_live_enabled"] = False
        st.session_state.pop("_core_curiosity_source_counts", None)
        st.session_state.pop("_core_curiosity_last_fetch", None)
        st.session_state.pop("_core_curiosity_user", None)
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
    if snapshot and not snapshot.error:
        st.session_state["_core_curiosity_snapshot"] = snapshot
        st.session_state["_core_curiosity_live_enabled"] = True
        st.session_state["_core_curiosity_user"] = snapshot.user_id
        if snapshot.source_counts:
            st.session_state["_core_curiosity_source_counts"] = dict(snapshot.source_counts)
        else:
            st.session_state.pop("_core_curiosity_source_counts", None)
        st.session_state["_core_curiosity_last_fetch"] = snapshot.fetched_at
    elif snapshot and snapshot.error:
        st.session_state["_core_curiosity_live_enabled"] = False
        st.session_state.pop("_core_curiosity_source_counts", None)
    return snapshot


def _format_nudge_text(
    template: Optional[str],
    *,
    trait_label: str,
    curiosity_value: float,
    resolved_value: Any,
) -> str:
    curiosity_pct = curiosity_value * 100.0
    if template:
        context = {
            "trait": trait_label,
            "curiosity": f"{curiosity_pct:.1f}%",
            "value": resolved_value,
        }
        try:
            return template.format(**context)
        except Exception:
            return template
    base = f"Highlight {trait_label} — curiosity is {curiosity_pct:.1f}%"
    if resolved_value not in (None, ""):
        base += f" (current value: {resolved_value})"
    return base + ". Encourage a concrete example to deepen the data."


def _source_badge_html(source: Optional[str]) -> str:
    if not source:
        return ""
    color_map = {
        "env": "#f39c12",
        "prefs": "#1976d2",
        "default": "#6c757d",
        "session": "#8e44ad",
    }
    color = color_map.get(source, "#6c757d")
    return (
        "<span style=\"display:inline-block;margin-left:0.35rem;padding:0.1rem 0.4rem;"
        "border-radius:999px;font-size:0.65rem;font-weight:600;color:#fff;"
        f"background-color:{color};\">{escape(source)}</span>"
    )


def _probe_curiosity() -> Tuple[str, str]:
    """Probe Core curiosity endpoint, respecting environment flags and overrides."""

    if not CORE_CURIOSITY_ENABLED:
        return "off", "flag off"

    url = f"{CORE_BASE}{CORE_CURIOSITY_HEALTH_PATH}"
    try:
        response = requests.get(url, timeout=2.5)
    except Exception as exc:  # pragma: no cover - network failure path
        return "unknown", str(exc)

    if response.status_code == 200:
        return "live", "OK"
    if response.status_code == 404:
        return "not_configured", "endpoint missing"
    return "unknown", f"http {response.status_code}"


# Back-compat wrapper so older call sites keep working
def core_curiosity_status() -> Tuple[str, str]:
    return _probe_curiosity()


def _render_status_strip(context: DevWriteContext) -> None:
    enabled_value, enabled_source = get_flag_bool("DEV_EXPLORER_ENABLED", True)
    loop_skip_value, loop_skip_source = get_flag_bool("DEV_LOOP_SKIP_RECOMPUTE", False)
    write_protect_value, write_protect_source = get_flag_bool("WRITE_PROTECT", True)
    mode_info = resolve_curiosity_mode(LIVE_MODE_KEY)
    curiosity_value = mode_info.flag_value
    curiosity_source = mode_info.flag_source

    demo_info = is_demo_enabled(REPO_ROOT, with_source=True)
    if isinstance(demo_info, tuple):
        demo_enabled_value, demo_source = demo_info
    else:
        demo_enabled_value = bool(demo_info)
        demo_source = "default"

    llm_model_value = globals().get("LLM_MODEL") or os.getenv("LLM_MODEL") or "—"
    llm_base_value, llm_base_source = llm_base_state()
    uc_base_value, uc_base_source = ucnrr_base_state()
    core_base_value, core_base_source = core_base_state()

    scheduler_prefs = load_scheduler_prefs()
    cadence_label = "Off"
    if isinstance(scheduler_prefs, dict):
        scheduler_cfg = scheduler_prefs.get("holistic_scheduler")
        if isinstance(scheduler_cfg, dict):
            code = str(scheduler_cfg.get("cadence") or "off").lower()
            mapping = {"off": "Off", "15m": "15m", "hourly": "Hourly", "daily": "Daily"}
            cadence_label = mapping.get(code, code or "—")

    baseline_path = current_baselines_path(REPO_ROOT)
    curiosity_live = bool(mode_info.effective_live)
    curiosity_user = str(st.session_state.get("_core_curiosity_user") or "—")
    raw_source_counts = st.session_state.get("_core_curiosity_source_counts")
    normalized_counts: Dict[str, int] = {}
    if isinstance(raw_source_counts, Mapping):
        for key, value in raw_source_counts.items():
            try:
                normalized_counts[str(key).upper()] = int(value)
            except (TypeError, ValueError):
                continue
    curiosity_data_value = "simulated" if not curiosity_live else "pending"
    curiosity_data_color = "#6c757d"
    curiosity_data_tooltip = "Using simulated curiosity data." if not curiosity_live else "Fetch live curiosity to populate RR data."
    if curiosity_live:
        total_rows = sum(normalized_counts.values())
        last_fetch = st.session_state.get("_core_curiosity_last_fetch")
        if total_rows > 0:
            rr_count = normalized_counts.get("RR", 0)
            fallback_count = normalized_counts.get("UCN_FALLBACK", 0)
            other_count = total_rows - rr_count - fallback_count
            if fallback_count == 0 and other_count <= 0:
                curiosity_data_value = "RR (live)"
                curiosity_data_color = "#28a745"
            elif rr_count == 0 and other_count <= 0:
                curiosity_data_value = "UCN fallback"
                curiosity_data_color = "#ffc107"
            else:
                curiosity_data_value = "Mixed"
                curiosity_data_color = "#17a2b8"
            tooltip_parts = [f"RR: {rr_count}", f"Fallback: {fallback_count}"]
            if other_count > 0:
                tooltip_parts.append(f"Other: {other_count}")
            if isinstance(last_fetch, str) and last_fetch:
                tooltip_parts.append(f"Fetched {last_fetch}")
            curiosity_data_tooltip = "; ".join(tooltip_parts)
        else:
            curiosity_data_value = "pending"
            curiosity_data_color = "#6c757d"
            curiosity_data_tooltip = "Live curiosity fetched but no RR-derived rows yet."

    hc_send_value, hc_send_source = get_flag_bool("HC_SEND_ENABLED", False)
    hc_ab_value, hc_ab_source = get_flag_bool("HC_AB_ENABLED", False)
    hc_ops_value, hc_ops_source = get_flag_bool("HC_OPS_ENABLED", False)
    credna_enabled, credna_enabled_source = get_flag_bool("CREDNA_ENABLED", True)
    credna_import_enabled, credna_import_source = get_flag_bool("CREDNA_IMPORT_ENABLED", False)
    credna_save_enabled, credna_save_source = get_flag_bool("CREDNA_SAVE_ENABLED", False)
    credna_reports_enabled, credna_reports_source = get_flag_bool("CREDNA_REPORTS_ENABLED", True)
    inbox_enabled_value, inbox_source = get_flag_bool("NUDGE_INBOX_ENABLED", False)
    feedback_enabled_value, feedback_source = get_flag_bool("FEEDBACK_ENABLED", True)
    audit_viewer_enabled_value, audit_source = get_flag_bool("AUDIT_VIEWER_ENABLED", True)
    nudge_log = nudge_log_path().as_posix()

    chip_specs = []
    chip_specs.append(
        {
            "label": "DEV_EXPLORER_ENABLED",
            "value": "on" if enabled_value else "off",
            "bg": "#4caf50" if enabled_value else "#6c757d",
            "source": enabled_source,
        }
    )
    chip_specs.append(
        {
            "label": "WRITE_PROTECT",
            "value": "true (no writes)" if write_protect_value else "false",
            "bg": "#f0ad4e" if write_protect_value else "#4caf50",
            "source": write_protect_source,
        }
    )
    chip_specs.append(
        {
            "label": "recompute",
            "value": "skipped" if loop_skip_value else "enabled",
            "bg": "#268bd2" if loop_skip_value else "#4caf50",
            "source": loop_skip_source,
        }
    )
    chip_specs.append(
        {
            "label": "DEMO_BASELINES",
            "value": "on" if demo_enabled_value else "off",
            "bg": "#007bff" if demo_enabled_value else "#6c757d",
            "tooltip": baseline_path,
            "source": demo_source,
        }
    )
    chip_specs.append(
        {
            "label": "HC_SEND",
            "value": "on" if hc_send_value else "off",
            "bg": "#20c997" if hc_send_value else "#6c757d",
            "source": hc_send_source,
        }
    )
    chip_specs.append(
        {
            "label": "HC_AB",
            "value": "on" if hc_ab_value else "off",
            "bg": "#9b59b6" if hc_ab_value else "#6c757d",
            "source": hc_ab_source,
        }
    )
    chip_specs.append(
        {
            "label": "HC_OPS",
            "value": "on" if hc_ops_value else "off",
            "bg": "#ff6f61" if hc_ops_value else "#6c757d",
            "source": hc_ops_source,
        }
    )
    chip_specs.append(
        {
            "label": "CREDNA",
            "value": "on" if credna_enabled else "off",
            "bg": "#0081a7" if credna_enabled else "#6c757d",
            "source": credna_enabled_source,
        }
    )
    chip_specs.append(
        {
            "label": "CREDNA_IMPORT",
            "value": "on" if credna_import_enabled else "off",
            "bg": "#00afb9" if credna_import_enabled else "#6c757d",
            "source": credna_import_source,
        }
    )
    chip_specs.append(
        {
            "label": "CREDNA_SAVE",
            "value": "on" if credna_save_enabled else "off",
            "bg": "#f07167" if credna_save_enabled else "#6c757d",
            "source": credna_save_source,
        }
    )
    chip_specs.append(
        {
            "label": "CREDNA_REPORTS",
            "value": "on" if credna_reports_enabled else "off",
            "bg": "#7f78d2" if credna_reports_enabled else "#6c757d",
            "source": credna_reports_source,
        }
    )
    chip_specs.append(
        {
            "label": "NUDGE_INBOX",
            "value": "on" if inbox_enabled_value else "off",
            "bg": "#17a2b8" if inbox_enabled_value else "#6c757d",
            "tooltip": nudge_log if inbox_enabled_value else nudge_log,
            "source": inbox_source,
        }
    )
    chip_specs.append(
        {
            "label": "FEEDBACK",
            "value": "on" if feedback_enabled_value else "off",
            "bg": "#4caf50" if feedback_enabled_value else "#6c757d",
            "source": feedback_source,
        }
    )
    chip_specs.append(
        {
            "label": "AUDIT_VIEWER",
            "value": "on" if audit_viewer_enabled_value else "off",
            "bg": "#4caf50" if audit_viewer_enabled_value else "#6c757d",
            "source": audit_source,
        }
    )
    chip_specs.append(
        {
            "label": "RR_BASELINES",
            "value": "demo" if demo_enabled_value else "live",
            "bg": "#17a2b8" if demo_enabled_value else "#4caf50",
            "tooltip": baseline_path,
            "source": demo_source,
        }
    )
    chip_specs.append(
        {
            "label": "CURIOSITY_FLAG",
            "value": "on" if curiosity_value else "off",
            "bg": "#9c27b0" if curiosity_value else "#6c757d",
            "source": curiosity_source,
        }
    )
    chip_specs.append(
        {
            "label": "CURIOSITY_MODE",
            "value": curiosity_chip_label(mode_info),
            "bg": "#6f42c1" if curiosity_live else "#6c757d",
            "tooltip": f"User: {curiosity_user}",
            "source": mode_info.effective_source,
        }
    )
    chip_specs.append(
        {
            "label": "CURIOSITY_DATA",
            "value": curiosity_data_value,
            "bg": curiosity_data_color,
            "tooltip": curiosity_data_tooltip,
            "source": None,
        }
    )
    curiosity_state, curiosity_note = _probe_curiosity()
    state_lookup = {
        "live": ("Curiosity live (env)", "#4caf50"),
        "off": ("Curiosity off (env)", "#6c757d"),
        "not_configured": ("Curiosity n/a", "#268bd2"),
        "unknown": ("Curiosity unknown", "#f0ad4e"),
    }
    core_flag_value, core_flag_color = state_lookup.get(
        curiosity_state, state_lookup["unknown"]
    )
    core_tooltip = curiosity_note or "Curiosity probe"
    chip_specs.append(
        {
            "label": "CORE_CURIOSITY",
            "value": core_flag_value,
            "bg": core_flag_color,
            "tooltip": core_tooltip,
            "source": "env" if CORE_CURIOSITY_ENABLED else "env",
        }
    )

    def _chip_html(
        label: str,
        value: str,
        bg: str,
        *,
        tooltip: Optional[str] = None,
        source: Optional[str] = None,
    ) -> str:
        safe_label = escape(label)
        safe_value = escape(value)
        title_parts: List[str] = []
        if tooltip:
            title_parts.append(str(tooltip))
        if source:
            title_parts.append(f"Source: {source} (env → prefs → default)")
        title_attr = f" title='{escape(' | '.join(title_parts))}'" if title_parts else ""
        source_badge = _source_badge_html(source)
        return (
            "<span style=\"display:inline-block;margin-right:0.4rem;padding:0.2rem 0.45rem;"
            "border-radius:999px;font-size:0.8rem;color:#111;background-color:" + bg + ";\""
            + title_attr
            + ">"
            f"<strong>{safe_label}</strong>: {safe_value}{source_badge}"
            "</span>"
        )

    chips_html = "".join(
        _chip_html(
            spec["label"],
            spec["value"],
            spec["bg"],
            tooltip=spec.get("tooltip"),
            source=spec.get("source"),
        )
        for spec in chip_specs
    )

    banner_placeholder = st.empty()

    def _render_status_banner(current_ucnrr_health: Mapping[str, Any]) -> None:
        health_parts: List[str] = []

        for name, base, source in (
            ("LLM", llm_base_value or None, llm_base_source),
            ("Core", core_base_value or None, core_base_source),
        ):
            healthy = check_health(base)
            dot_color = "#33d17a" if healthy else "#6c757d"
            tooltip_str = str(base or "not configured")
            if source:
                tooltip_str += f" | source: {source}"
            tooltip_html = escape(tooltip_str)
            health_parts.append(
                "<span style=\"margin-right:0.6rem;font-size:0.8rem;\" title='"
                + tooltip_html
                + "'>"
                + f"<span style=\"color:{dot_color};font-size:1rem;\">●</span> {escape(name)}"
                + "</span>"
            )

        reachable = bool(current_ucnrr_health.get("reachable"))
        uc_label = "UCN/RR PASS" if reachable else "UCN/RR FAIL"
        uc_color = "#33d17a" if reachable else "#e5534b"
        last_ts_raw = _coerce_epoch(current_ucnrr_health.get("last_compute_ts"))
        ts_suffix = ""
        if last_ts_raw is not None:
            ts_suffix = " • " + _format_ucnrr_ts(last_ts_raw)
        reason = str(current_ucnrr_health.get("reason") or "")
        base_hint = str(current_ucnrr_health.get("base_url") or uc_base_value or "")
        status_code = current_ucnrr_health.get("status")
        tooltip_bits = []
        if base_hint:
            tooltip_bits.append(base_hint)
        if reason:
            tooltip_bits.append(reason)
        if status_code:
            tooltip_bits.append(f"status: {status_code}")
        tooltip_payload = escape(" | ".join(filter(None, tooltip_bits)))
        health_parts.append(
            "<span style=\"margin-right:0.6rem;font-size:0.8rem;\" title='"
            + tooltip_payload
            + "'>"
            + f"<span style=\"color:{uc_color};font-size:1rem;\">●</span> {escape(uc_label)}{escape(ts_suffix)}"
            + "</span>"
        )

        banner_html = (
            "<div style=\"padding:0.35rem 0.6rem; border-radius:6px; "
            "background-color:rgba(255,255,255,0.05); font-size:0.85rem; display:flex;"
            "justify-content:space-between; align-items:center;gap:0.75rem;flex-wrap:wrap;\">"
            f"<div style=\"flex:1 1 auto;\">{chips_html}</div>"
            f"<div style=\"flex:0 0 auto;white-space:nowrap;\">{''.join(health_parts)}</div>"
            "</div>"
        )
        banner_placeholder.markdown(banner_html, unsafe_allow_html=True)

    ucnrr_health = fetch_ucnrr_health(core_base_value or CORE_BASE)
    _render_status_banner(ucnrr_health)

    recompute_cols = st.columns([1, 3])
    with recompute_cols[0]:
        disabled_reason = None
        if write_protect_value:
            disabled_reason = "WRITE_PROTECT enabled"
        elif loop_skip_value:
            disabled_reason = "Recompute skipped via DEV_LOOP_SKIP_RECOMPUTE"
        elif not (core_base_value or CORE_BASE):
            disabled_reason = "Core base missing"

        button_clicked = st.button(
            "Recompute now (TEST)",
            key="ucnrr_recompute_button",
            disabled=disabled_reason is not None,
        )
        if disabled_reason:
            st.caption(disabled_reason)

    with recompute_cols[1]:
        notice = st.session_state.get(UCNRR_RECOMPUTE_NOTICE_KEY)
        if isinstance(notice, tuple) and len(notice) == 2:
            severity, message = notice
            if severity == "success":
                st.success(message)
            elif severity == "info":
                st.info(message)
            elif severity == "warning":
                st.warning(message)
            else:
                st.error(message)
        elif not (core_base_value or CORE_BASE):
            st.caption("Core base not configured.")

    if button_clicked:
        target_user = str(st.session_state.get(LIVE_USER_KEY, "")).strip()
        severity, message = _trigger_ucnrr_recompute(core_base_value or CORE_BASE, target_user)
        st.session_state[UCNRR_RECOMPUTE_NOTICE_KEY] = (severity, message)
        if severity == "success":
            fetch_ucnrr_health.clear()
            ucnrr_health = fetch_ucnrr_health(core_base_value or CORE_BASE)
            _render_status_banner(ucnrr_health)


    copy_items = [
        ("LLM_MODEL", str(llm_model_value), None),
        ("LLM_BASE_URL", str(llm_base_value), llm_base_source),
        ("Scheduler cadence", str(cadence_label or "—"), None),
    ]

    copy_cols = st.columns(len(copy_items))
    for (label, value, source), col in zip(copy_items, copy_cols):
        with col:
            col.caption(label)
            col.text_input(
                f"status_copy_{label}",
                value,
                key=f"_status_copy_input_{label}",
                help="",
                disabled=True,
                label_visibility="collapsed",
            )
            if source:
                col.markdown(_source_badge_html(source), unsafe_allow_html=True)
            col.button(
                "Copy",
                key=f"_status_copy_button_{label}",
                on_click=_handle_copy,
                args=(label, value),
            )

    notice = st.session_state.get("_status_strip_copy_notice")
    if notice:
        st.caption(
            f"Copied {notice['label']}: {notice['value']} — use Ctrl/Cmd+C from the field above."
        )


@dataclass(slots=True)
class DevWriteContext:
    write_protect: bool
    env_path: Path
    redirect_env_path: Path
    dev_user_root: Path
    dev_persona_root: Path
    last_env_write: Optional[Path] = None

    def ensure_dirs(self) -> None:
        if self.write_protect:
            return
        self.dev_user_root.mkdir(parents=True, exist_ok=True)
        self.dev_persona_root.mkdir(parents=True, exist_ok=True)

    def write_env_var(self, key: str, value: str) -> Path:
        write_guard(self, action=f"update environment variable {key}")
        target = self.env_path
        if target.exists():
            lines = target.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
        replaced = False
        for idx, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[idx] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={value}")
        target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self.last_env_write = target
        return target

def _hydrate_persona_modules(context: DevWriteContext) -> Dict[str, object]:
    explorer_path = str(EXPLORER_FINAL_ROOT)
    if explorer_path not in sys.path:
        sys.path.insert(0, explorer_path)

    module_results = registry_helpers.discover_persona_modules(
        module_path for _, module_path in PERSONA_IMPORTS
    )
    registry_helpers.ensure_relationship_coach_contract(module_results)

    successes: List[str] = []
    failures: Dict[str, str] = {}
    for module in module_results:
        if module.error:
            failures[module.module_name] = module.error
        else:
            successes.append(module.module_name)

    live_count = 0
    if persona_registry is not None:
        try:
            live_count = len(list(persona_registry.list_personas()))  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive guard
            failures["registry"] = traceback.format_exc().strip()

    if live_count and successes and persona_registry is not None and dump_registry_snapshot is not None:
        try:
            write_guard(context, action="write persona registry snapshot")
            dump_registry_snapshot(REGISTRY_SNAPSHOT_PATH)
        except PermissionError as exc:
            failures.setdefault("snapshot", str(exc))
        except Exception:  # pragma: no cover - snapshot failures are advisory
            failures.setdefault("snapshot", traceback.format_exc().strip())

    return {
        "successes": successes,
        "failures": failures,
        "count": live_count,
        "modules": [module.to_dict() for module in module_results],
    }


def _record_persona_switch(persona_id: str, origin: str, context: DevWriteContext) -> None:
    last_id = st.session_state.get("_persona_last_switch_id")
    if last_id == persona_id:
        return

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "persona_id": persona_id,
        "origin": origin or "unknown",
    }

    st.session_state["_persona_last_switch_id"] = persona_id

    if context.write_protect:
        buffer = st.session_state.setdefault("_persona_switch_buffer", [])  # type: ignore[attr-defined]
        buffer.append(event)
        return

    write_guard(context, action="append persona switch event")
    PERSONA_SWITCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PERSONA_SWITCH_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _validate_user_id(user_id: str) -> Optional[str]:
    if not user_id:
        return "Enter a user id before running an action."
    cleaned = user_id.strip()
    if len(cleaned) < 3:
        return "User id must be at least 3 characters long."
    if not USER_ID_PATTERN.match(cleaned):
        return "User id may only include letters, numbers, dots, underscores, or dashes."
    return None


def _resolve_user_dir(user_id: str, context: DevWriteContext) -> Path:
    user_dir = (context.dev_user_root / user_id).resolve()
    root = context.dev_user_root.resolve()
    if root not in user_dir.parents and user_dir != root:
        raise ValueError("Resolved user directory escapes the dev sandbox.")
    return user_dir


def _load_preset_bundle(preset_label: str) -> Tuple[Dict[str, Any], Path]:
    preset_path = PRESET_BUNDLES.get(preset_label)
    if preset_path is None:
        raise ValueError(f"Unknown preset '{preset_label}'.")
    if not preset_path.exists():
        raise ValueError(f"Preset bundle missing: {_relative_to_repo(preset_path)}")
    try:
        payload = json.loads(preset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Preset bundle is not valid JSON: {exc}") from exc
    return payload, preset_path


def _build_seed_preview(user_id: str, preset_label: str, context: DevWriteContext) -> Dict[str, Any]:
    _, preset_path = _load_preset_bundle(preset_label)
    user_dir = _resolve_user_dir(user_id, context)
    baseline_path = user_dir / "baseline.json"
    bundle_path = user_dir / "bundle.json"
    metadata_path = user_dir / "metadata.json"
    notes_path = user_dir / "notes"

    steps = []
    if user_dir.exists():
        steps.append(f"Reuse existing directory {_relative_to_repo(user_dir)}")
    else:
        steps.append(f"Create {_relative_to_repo(user_dir)}")
    steps.append(f"Write baseline.json from {_relative_to_repo(preset_path)}")
    steps.append("Write bundle.json for active state")
    steps.append("Update metadata.json with preset + timestamps")
    steps.append("Ensure notes/ folder exists for local experimentation")

    display_paths = []
    for path in (user_dir, baseline_path, bundle_path, metadata_path, notes_path):
        display = _relative_to_repo(path)
        if display not in display_paths:
            display_paths.append(display)

    return {
        "action": "seed",
        "user_id": user_id,
        "preset": preset_label,
        "steps": steps,
        "display_paths": display_paths,
        "details": {
            "user_dir": str(user_dir),
            "preset_path": str(preset_path),
            "baseline_path": str(baseline_path),
            "bundle_path": str(bundle_path),
            "metadata_path": str(metadata_path),
            "notes_path": str(notes_path),
        },
    }


def _build_reset_preview(user_id: str, context: DevWriteContext) -> Dict[str, Any]:
    user_dir = _resolve_user_dir(user_id, context)
    if not user_dir.exists():
        raise ValueError(f"User directory not found: {_relative_to_repo(user_dir)}")

    baseline_path = user_dir / "baseline.json"
    if not baseline_path.exists():
        raise ValueError(
            f"baseline.json missing for {_relative_to_repo(user_dir)} — seed the user first."
        )

    bundle_path = user_dir / "bundle.json"
    metadata_path = user_dir / "metadata.json"
    notes_path = user_dir / "notes"
    volatile_paths = [
        str(path)
        for path in user_dir.iterdir()
        if path.name not in {"baseline.json", "metadata.json"}
    ]

    steps = []
    if volatile_paths:
        steps.append(f"Remove {len(volatile_paths)} volatile artefact(s)")
    else:
        steps.append("No volatile artefacts detected — bundle will still be refreshed")
    steps.append("Restore bundle.json from baseline.json")
    steps.append("Touch metadata.json with reset timestamp")
    steps.append("Ensure notes/ folder exists for sandbox use")

    display_paths = []
    for raw in volatile_paths + [str(bundle_path), str(metadata_path), str(notes_path)]:
        display = _relative_to_repo(Path(raw))
        if display not in display_paths:
            display_paths.append(display)

    return {
        "action": "reset",
        "user_id": user_id,
        "steps": steps,
        "display_paths": display_paths,
        "details": {
            "user_dir": str(user_dir),
            "baseline_path": str(baseline_path),
            "bundle_path": str(bundle_path),
            "metadata_path": str(metadata_path),
            "volatile_paths": volatile_paths,
        },
    }


def _build_delete_preview(user_id: str, context: DevWriteContext) -> Dict[str, Any]:
    user_dir = _resolve_user_dir(user_id, context)
    if not user_dir.exists():
        raise ValueError(f"User directory not found: {_relative_to_repo(user_dir)}")

    steps = [f"Remove {_relative_to_repo(user_dir)}"]

    return {
        "action": "delete",
        "user_id": user_id,
        "steps": steps,
        "display_paths": [_relative_to_repo(user_dir)],
        "details": {"user_dir": str(user_dir)},
    }


def _user_action_dry_run(preview: Dict[str, Any], message: str) -> Dict[str, Any]:
    return {
        "action": preview.get("action"),
        "user_id": preview.get("user_id"),
        "ok": True,
        "dry_run": True,
        "message": message,
        "paths": preview.get("display_paths", []),
    }


def _execute_seed_user(preview: Dict[str, Any], context: DevWriteContext) -> Dict[str, Any]:
    preset_path = Path(preview["details"]["preset_path"])
    payload, _ = _load_preset_bundle(preview.get("preset", ""))
    payload["id"] = preview["user_id"]

    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta.setdefault("source", "DevExplorer")
        meta["seeded_at"] = datetime.now(timezone.utc).isoformat()
    else:
        payload["meta"] = {
            "source": "DevExplorer",
            "seeded_at": datetime.now(timezone.utc).isoformat(),
        }

    serialised = json.dumps(payload, indent=2)
    user_dir = Path(preview["details"]["user_dir"])
    baseline_path = Path(preview["details"]["baseline_path"])
    bundle_path = Path(preview["details"]["bundle_path"])
    metadata_path = Path(preview["details"]["metadata_path"])
    notes_path = Path(preview["details"]["notes_path"])
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        write_guard(context, action=f"seed demo user {preview['user_id']}")
    except PermissionError as exc:
        return _user_action_dry_run(preview, str(exc))

    user_dir.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(serialised, encoding="utf-8")
    bundle_path.write_text(serialised, encoding="utf-8")
    notes_path.mkdir(parents=True, exist_ok=True)

    metadata = {
        "user_id": preview["user_id"],
        "preset": preview.get("preset"),
        "seeded_at": timestamp,
        "source": _relative_to_repo(preset_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "action": "seed",
        "user_id": preview["user_id"],
        "ok": True,
        "dry_run": False,
        "message": f"Seeded '{preview['user_id']}' from {preview.get('preset')}.",
        "paths": preview.get("display_paths", []),
    }


def _execute_reset_user(preview: Dict[str, Any], context: DevWriteContext) -> Dict[str, Any]:
    baseline_path = Path(preview["details"]["baseline_path"])
    if not baseline_path.exists():
        raise ValueError("baseline.json missing; seed the user before resetting.")

    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"baseline.json is invalid JSON: {exc}") from exc

    payload["id"] = preview["user_id"]
    serialised = json.dumps(payload, indent=2)

    bundle_path = Path(preview["details"]["bundle_path"])
    metadata_path = Path(preview["details"]["metadata_path"])
    volatile_paths = [Path(raw) for raw in preview["details"].get("volatile_paths", [])]
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        write_guard(context, action=f"reset user {preview['user_id']}")
    except PermissionError as exc:
        return _user_action_dry_run(preview, str(exc))

    for path in volatile_paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                continue

    bundle_path.write_text(serialised, encoding="utf-8")

    metadata: Dict[str, Any]
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}
    metadata["last_reset"] = timestamp
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    notes_path = Path(preview["details"]["user_dir"]) / "notes"
    notes_path.mkdir(parents=True, exist_ok=True)

    return {
        "action": "reset",
        "user_id": preview["user_id"],
        "ok": True,
        "dry_run": False,
        "message": f"Reset '{preview['user_id']}' using baseline.json.",
        "paths": preview.get("display_paths", []),
    }


def _execute_delete_user(preview: Dict[str, Any], context: DevWriteContext) -> Dict[str, Any]:
    user_dir = Path(preview["details"]["user_dir"])

    try:
        write_guard(context, action=f"delete user {preview['user_id']}")
    except PermissionError as exc:
        return _user_action_dry_run(preview, str(exc))

    if user_dir.exists():
        shutil.rmtree(user_dir)

    return {
        "action": "delete",
        "user_id": preview["user_id"],
        "ok": True,
        "dry_run": False,
        "message": f"Deleted '{preview['user_id']}' from dev storage.",
        "paths": preview.get("display_paths", []),
    }


def _execute_user_action(preview: Dict[str, Any], context: DevWriteContext) -> Dict[str, Any]:
    action = preview.get("action")
    if action == "seed":
        return _execute_seed_user(preview, context)
    if action == "reset":
        return _execute_reset_user(preview, context)
    if action == "delete":
        return _execute_delete_user(preview, context)
    raise ValueError(f"Unsupported user management action: {action}")
st.set_page_config(
    page_title="Dev Explorer",
    page_icon="🛠️",
    layout="wide",
)

enabled, _ = get_flag_bool("DEV_EXPLORER_ENABLED", True)

if not enabled:
    st.title("🛠️ Developer Explorer")
    st.warning("Dev Explorer is disabled.")
    st.markdown(
        "Set `DEV_EXPLORER_ENABLED=true` (default) in your environment before launching this page."
    )
    st.code("DEV_EXPLORER_ENABLED=true streamlit run ExplorerDev/explorer_dev.py")
    st.stop()


WRITE_PROTECT, _ = get_flag_bool("WRITE_PROTECT", True)
DEV_WRITE_CONTEXT = DevWriteContext(
    write_protect=WRITE_PROTECT,
    env_path=ENV_PATH,
    redirect_env_path=REPO_ROOT / "persona_config/dev_overrides/.env.dev",
    dev_user_root=REPO_ROOT / "data/dev_users",
    dev_persona_root=REPO_ROOT / "persona_config/dev_overrides",
)
DEV_WRITE_CONTEXT.ensure_dirs()


if "persona_import_result" not in st.session_state:
    st.session_state["persona_import_result"] = _hydrate_persona_modules(DEV_WRITE_CONTEXT)


LLM_BASE_URL = llm_base_url()
LLM_MODEL = os.getenv("LLM_MODEL") or "llama3"
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "45"))
if "LLMConfig" in globals() and LLMConfig is not None:  # type: ignore[truthy-bool]
    try:
        LLM_CONFIG = LLMConfig(base_url=LLM_BASE_URL, model=LLM_MODEL, timeout=LLM_TIMEOUT)  # type: ignore[misc]
    except TypeError:  # pragma: no cover - defensive guard if constructor changes
        LLM_CONFIG = None
else:
    LLM_CONFIG = None


def _resolve_users_dir() -> Path:
    redna_core_data = os.getenv("REDNA_CORE_DATA")
    core_data_dir = os.getenv("CORE_DATA_DIR")
    if redna_core_data:
        root = Path(redna_core_data).expanduser().resolve()
    elif core_data_dir:
        root = Path(core_data_dir).expanduser().resolve()
    else:
        root = (REPO_ROOT / "ReDNACoreDemo/data/storage").resolve()
    return root / "users"


def _placeholder(title: str, description: str) -> None:
    st.subheader(title)
    st.markdown(description)
    st.info("Module scaffolded. Implementation arrives in the next milestone.")


def _format_handoff(intents: Sequence[Dict[str, str]] | Sequence[str]) -> str:
    formatted: List[str] = []
    for item in intents or []:  # type: ignore[arg-type]
        if isinstance(item, str):
            formatted.append(item)
        elif isinstance(item, dict):
            phrase = item.get("phrase") or ""
            match_type = item.get("match_type")
            if phrase and match_type:
                formatted.append(f"{phrase} ({match_type})")
            elif phrase:
                formatted.append(phrase)
    return ", ".join(formatted)


def _format_style_presets(presets: Sequence[Dict[str, str]] | Sequence[str]) -> str:
    labels: List[str] = []
    for preset in presets or []:  # type: ignore[arg-type]
        if isinstance(preset, str):
            labels.append(preset)
        elif isinstance(preset, dict):
            label = preset.get("label") or preset.get("id")
            if label:
                labels.append(label)
    return ", ".join(labels)


def _persona_prompt_paths(persona_id: str) -> Dict[str, Path]:
    base = REPO_ROOT / "persona_config/dev_overrides" / persona_id
    return {
        "system": base / "system.md",
        "opening": base / "opening.md",
    }
def _build_sandbox_meta(prefs: Dict[str, Any]) -> str:
    tone = str(prefs.get("tone") or "neutral")
    formality = int(prefs.get("formality", 50))
    warmth = int(prefs.get("warmth", 50))
    directness = int(prefs.get("directness", 50))
    micro_actions = prefs.get("micro_actions")
    if not isinstance(micro_actions, list):
        micro_actions = []
    return build_prompt_meta(
        tone=tone,
        formality=formality,
        warmth=warmth,
        directness=directness,
        micro_actions=micro_actions,
    )


def _generate_sandbox_reply(
    bundle: Dict[str, str],
    user_message: str,
    *,
    meta: str | None = None,
) -> str:
    system_prompt = bundle.get("system", "")
    opening = bundle.get("opening", "")
    prompt_parts: List[str] = []
    if meta:
        prompt_parts.append(meta)
    if system_prompt:
        prompt_parts.append(system_prompt)
    if opening:
        prompt_parts.append(opening)
    prompt_parts.append(user_message)
    prompt = "\n\n".join(part for part in prompt_parts if part)

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(
            f"{LLM_BASE_URL}/api/generate",
            json=payload,
            timeout=LLM_TIMEOUT,
        )
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise RuntimeError(f"LLM request failed: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"LLM error {response.status_code}: {response.text}")

    try:
        data = response.json()
    except Exception as exc:  # pragma: no cover - invalid JSON
        raise RuntimeError(f"Invalid LLM response: {exc}") from exc

    reply_text = data.get("response") or data.get("text") or "(no reply)"
    return str(reply_text).strip()


def _compute_reply_diff(reply_a: str, reply_b: str) -> str:
    if reply_a.strip() == reply_b.strip():
        return ""

    diff_lines = list(
        difflib.unified_diff(
            reply_a.splitlines(),
            reply_b.splitlines(),
            fromfile="A",
            tofile="B",
            lineterm="",
        )
    )
    if not diff_lines:
        return ""

    # Drop the file header for a tighter inline diff if available
    if len(diff_lines) > 2 and diff_lines[0].startswith("--- ") and diff_lines[1].startswith("+++ "):
        diff_lines = diff_lines[2:]
    return "\n".join(diff_lines)


def _show_persona_registry(context: DevWriteContext) -> None:
    st.subheader("Persona Registry")
    _ensure_persona_registry_styles()
    mode_info = resolve_curiosity_mode(LIVE_MODE_KEY)
    core_curiosity_flag, core_health_error = core_curiosity_status()
    hc_send_enabled, hc_send_source = get_flag_bool("HC_SEND_ENABLED", False)
    hc_ab_enabled, _ = get_flag_bool("HC_AB_ENABLED", False)
    hc_ops_enabled, hc_ops_source = get_flag_bool("HC_OPS_ENABLED", False)
    snapshot_status: Optional[LiveCuriositySnapshot] = None
    toggle_cols = st.columns([1.2, 1.6, 0.8])
    coach_toggle_key = f"{LIVE_MODE_KEY}_coach"

    def _sync_coach_curiosity() -> None:
        st.session_state[LIVE_MODE_KEY] = bool(st.session_state.get(coach_toggle_key, False))

    with toggle_cols[0]:
        if mode_info.forced:
            st.session_state[coach_toggle_key] = mode_info.effective_live
        elif coach_toggle_key not in st.session_state:
            st.session_state[coach_toggle_key] = mode_info.effective_live
        live_mode = st.toggle(
            "Live curiosity (Core)",
            value=st.session_state.get(coach_toggle_key, mode_info.effective_live),
            key=coach_toggle_key,
            disabled=mode_info.forced or not mode_info.flag_value,
            help="Share the Container Studio curiosity mode while coaching.",
            on_change=_sync_coach_curiosity,
        )
        st.caption(f"Mode: {curiosity_chip_label(mode_info)}")
        if mode_info.forced:
            _render_env_lock_pill()
    if not mode_info.forced:
        st.session_state[LIVE_MODE_KEY] = bool(st.session_state.get(coach_toggle_key, False))
    else:
        st.session_state[LIVE_MODE_KEY] = mode_info.effective_live

    default_user = st.session_state.get(
        LIVE_USER_KEY,
        os.getenv("CORE_CURIOSITY_SAMPLE_USER", "demo_user"),
    )
    coach_user_key = f"{LIVE_USER_KEY}_coach"
    if coach_user_key not in st.session_state:
        st.session_state[coach_user_key] = default_user
    with toggle_cols[1]:
        user_input = st.text_input(
            "Core user id",
            value=st.session_state.get(coach_user_key, default_user),
            key=coach_user_key,
            disabled=not mode_info.flag_value or not mode_info.effective_live,
        )
        if mode_info.effective_live and mode_info.flag_value:
            st.session_state[LIVE_USER_KEY] = user_input
        else:
            st.session_state.pop(LIVE_USER_KEY, None)
    with toggle_cols[2]:
        refresh = st.button(
            "Refresh live data",
            key="refresh_live_coach",
            disabled=not mode_info.effective_live
            or not mode_info.flag_value
            or not str(st.session_state.get(LIVE_USER_KEY, "")).strip(),
        )

    if not mode_info.flag_value:
        if mode_info.forced:
            st.info("Curiosity mode locked to simulation via CP+ environment override.")
        else:
            st.info("Curiosity engine flag OFF — using simulation data for workshop panels.")
        st.session_state["_core_curiosity_live_enabled"] = False
    elif not mode_info.effective_live:
        st.caption("Curiosity simulation mode — using demo baselines.")
        st.session_state["_core_curiosity_live_enabled"] = False
    else:
        user_token = str(st.session_state.get(LIVE_USER_KEY, "")).strip()
        if not user_token:
            st.info("Enter a Core user id to pull live curiosity data.")
            st.session_state["_core_curiosity_live_enabled"] = False
        else:
            if core_curiosity_flag is False:
                st.warning("Live curiosity unavailable: disabled in Core /health.")
                st.session_state["_core_curiosity_live_enabled"] = False
            else:
                snapshot_status = _ensure_live_curiosity_snapshot(force=refresh)
                if snapshot_status:
                    snapshot_status.curiosity_enabled = (
                        core_curiosity_flag if core_curiosity_flag is not None else snapshot_status.curiosity_enabled
                    )
                if snapshot_status and snapshot_status.error:
                    error_lower = str(snapshot_status.error).lower()
                    if (
                        core_curiosity_flag is False
                        or "404" in error_lower
                        or "flag off" in error_lower
                        or "disabled" in error_lower
                    ):
                        st.warning(f"Live curiosity unavailable: {snapshot_status.error}")
                    else:
                        st.error(f"Live curiosity fetch failed: {snapshot_status.error}")
                    st.session_state["_core_curiosity_live_enabled"] = False
                elif snapshot_status:
                    st.caption(
                        f"Live curiosity from Core user `{snapshot_status.user_id}` fetched {snapshot_status.fetched_at}."
                    )
                elif core_health_error:
                    st.warning(f"Core health unreachable: {core_health_error}")
                    st.session_state["_core_curiosity_live_enabled"] = False

    if snapshot_status and not snapshot_status.error:
        st.session_state["_core_curiosity_live_enabled"] = True
        top_rows = [row for row in snapshot_status.top_traits[:5] if isinstance(row, dict)]
        if top_rows:
            st.markdown("**Top curiosity traits (Core)**")
            for row in top_rows:
                trait_id = row.get("trait_id") or row.get("trait") or "?"
                container_id = row.get("container_id") or "?"
                curiosity_val = row.get("curiosity", 0.0)
                try:
                    curiosity_float = float(curiosity_val)
                except (TypeError, ValueError):
                    curiosity_float = 0.0
                weight_val = row.get("weight")
                try:
                    weight_float = float(weight_val)
                except (TypeError, ValueError):
                    weight_float = 1.0
                rr_val = row.get("rr")
                try:
                    rr_float = float(rr_val) * 100.0 if rr_val is not None else None
                except (TypeError, ValueError):
                    rr_float = None
                source_label = row.get("source") or row.get("curiosity_source") or ""
                detail_parts = [f"curiosity {curiosity_float * 100:.1f}%"]
                if rr_float is not None:
                    detail_parts.append(f"RR {rr_float:.1f}%")
                if abs(weight_float - 1.0) > 0.01:
                    detail_parts.append(f"w={weight_float:.2f}")
                if source_label:
                    detail_parts.append(str(source_label))
                st.write(
                    f"- `{container_id}.{trait_id}` " + "; ".join(detail_parts)
                )

    def _render_head_coach_ops_card(
        *,
        target_user: str,
        persona_id: str,
        selected_cohort_value: Optional[str],
    ) -> None:
        st.markdown("---")
        st.subheader("Head Coach Ops")
        st.caption("Define demo cadences and trigger Top 1 sends without leaving Dev Explorer.")

        if not target_user:
            st.info("Enter a target user in the preview panel to configure schedules.")
            return

        if context.write_protect:
            st.info("Write-protect ON — schedules persist for this session only.")

        if not hc_send_enabled:
            st.info("Head Coach send disabled — enable HC_SEND_ENABLED to enqueue bundles.")

        ops_config = nudge_store.load_ops(target_user, write_protect=context.write_protect)
        entries = ops_config.get("entries", [])
        weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        if entries:
            for entry in entries:
                entry_id = entry.get("id") or f"ops_{uuid.uuid4().hex[:6]}"
                entry_days = entry.get("weekdays") or list(range(7))
                days_label = ",".join(weekday_labels[idx] for idx in entry_days)
                time_label = f"{int(entry.get('hour', 9)) :02d}:{int(entry.get('minute', 0)) :02d} UTC"
                cohort_label = entry.get("cohort") or "—"
                next_run_ts = entry.get("next_run_ts") or "—"
                last_run_ts = entry.get("last_run_ts") or "—"

                cols = st.columns([0.32, 0.2, 0.24, 0.24])
                with cols[0]:
                    st.markdown(f"**{entry.get('label') or 'Schedule'}**")
                    st.caption(f"Persona: {entry.get('persona_id')}")
                    st.caption(f"Cohort: {cohort_label}")
                with cols[1]:
                    st.caption(f"Days: {days_label or 'Daily'}")
                    st.caption(f"Time: {time_label}")
                with cols[2]:
                    st.caption(f"Next run: {next_run_ts}")
                    st.caption(f"Last run: {last_run_ts}")
                with cols[3]:
                    persona_mismatch = entry.get("persona_id") != persona_id
                    run_disabled = persona_mismatch or not hc_send_enabled
                    run_help = (
                        "Switch persona to match schedule."
                        if persona_mismatch
                        else "Enable HC_SEND_ENABLED to enqueue bundles."
                    )
                    if st.button(
                        "Run now",
                        key=f"ops_run_{entry_id}",
                        disabled=run_disabled,
                        help=run_help,
                    ):
                        _run_head_coach_preview(use_simulated=not effective_live)
                        latest_preview = st.session_state.get(head_coach_state_key)
                        items_payload: List[Dict[str, Any]] = []
                        if isinstance(latest_preview, dict) and latest_preview.get("items"):
                            if latest_preview.get("persona_id") == persona_id:
                                items_payload = list(latest_preview.get("items", []))[:1]
                        if not items_payload:
                            st.warning("Preview empty — generate motivators first.")
                        else:
                            cohort_override = entry.get("cohort") or selected_cohort_value
                            _enqueue_payload(
                                items_payload,
                                "Ops run",
                                cohort=cohort_override,
                            )
                            nudge_store.mark_ops_run(
                                target_user,
                                entry_id,
                                write_protect=context.write_protect,
                            )
                            st.success("Top 1 enqueued via Ops schedule.")
                            _safe_rerun()
                            return

                    if st.button(
                        "Delete",
                        key=f"ops_delete_{entry_id}",
                        help="Remove this schedule.",
                    ):
                        nudge_store.delete_ops_entry(
                            target_user,
                            entry_id,
                            write_protect=context.write_protect,
                        )
                        _safe_rerun()
                        return
        else:
            st.info("No schedules yet. Add one below to automate demo sends.")

        with st.expander("Add schedule"):
            day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            default_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            with st.form(f"ops_add_form_{target_user}"):
                persona_value = st.text_input("Persona id", value=persona_id)
                days_selected = st.multiselect(
                    "Days",
                    day_labels,
                    default=default_days,
                    help="Choose which days to run this schedule.",
                )
                hour_value = int(
                    st.number_input("Hour (UTC)", min_value=0, max_value=23, value=9, step=1)
                )
                minute_value = int(
                    st.number_input("Minute", min_value=0, max_value=59, value=0, step=5)
                )
                label_default = f"Top 1 {','.join(days_selected) or 'Daily'} {hour_value:02d}:{minute_value:02d}"
                label_value = st.text_input("Label", value=label_default)
                cohort_entry: Optional[str] = None
                if hc_ab_enabled:
                    cohort_choice = st.selectbox(
                        "Cohort",
                        ["None", "A", "B"],
                        index=0 if not selected_cohort_value else (1 if selected_cohort_value == "A" else 2),
                        help="Optional: preset cohort tag for bundles from this schedule.",
                    )
                    cohort_entry = None if cohort_choice == "None" else cohort_choice
                submit = st.form_submit_button("Save schedule")
                if submit:
                    if not persona_value.strip():
                        st.warning("Persona id is required.")
                    elif not days_selected:
                        st.warning("Select at least one day.")
                    else:
                        entry_payload = {
                            "persona_id": persona_value.strip(),
                            "label": label_value.strip() or f"{persona_value.strip()} cadence",
                            "weekdays": [day_labels.index(day) for day in days_selected],
                            "hour": hour_value,
                            "minute": minute_value,
                            "cohort": cohort_entry,
                        }
                        nudge_store.upsert_ops_entry(
                            target_user,
                            entry_payload,
                            write_protect=context.write_protect,
                        )
                        st.success("Schedule saved.")
                        _safe_rerun()
                        return

    mode_default = st.session_state.get("_validation_mode", "strict")
    mode = st.radio(
        "Validation mode",
        options=("strict", "warn"),
        index=0 if mode_default == "strict" else 1,
        horizontal=True,
        key="_validation_mode_radio",
    )
    st.session_state["_validation_mode"] = mode

    result = st.session_state.get(
        "persona_import_result",
        {"successes": [], "failures": {}, "count": 0, "modules": []},
    )
    module_dicts: List[Dict[str, Any]] = list(result.get("modules", []))
    failures: Dict[str, str] = dict(result.get("failures", {}))

    status_col, button_col = st.columns([3, 1])

    with button_col:
        if st.button("Reload personas"):
            result = _hydrate_persona_modules(context)
            st.session_state["persona_import_result"] = result
            module_dicts = list(result.get("modules", []))
            failures = dict(result.get("failures", {}))

    module_total = len(PERSONA_IMPORTS)
    module_imports = [m for m in module_dicts if not m.get("error")]
    module_failure_map = {m["module_name"]: m.get("error") for m in module_dicts if m.get("error")}
    additional_failures = {k: v for k, v in failures.items() if k not in module_failure_map}
    failure_count = len(module_failure_map) + len(additional_failures)
    imported_count = len(module_imports)

    try:
        registry_result = registry_helpers.load_persona_registry(mode=mode)
    except FileNotFoundError as exc:
        st.error(f"Persona contract schema missing: {exc}")
        return
    except Exception as exc:  # pragma: no cover - defensive guard for helpers
        st.error(f"Unable to load persona registry: {exc}")
        return

    module_chip = (
        "<span class='dev-chip' title='Python persona modules discovered vs total declared imports'>"
        f"<strong>Modules:</strong> {imported_count}/{module_total} · failures {failure_count}"
        "</span>"
    )

    registry_total = registry_result.total or module_total
    registry_chip_variant = "dev-chip dev-chip--warn" if registry_result.failures else "dev-chip dev-chip--ok"
    registry_chip = (
        f"<span class='{registry_chip_variant}' "
        "title='Registered personas after schema hydration; counts exclude skipped modules.'>"
        f"<strong>Registry:</strong> {registry_result.imported}/{registry_total}"
        "</span>"
    )
    status_col.markdown(
        f"<div class='registry-chip-wrap'>{module_chip}{registry_chip}</div>",
        unsafe_allow_html=True,
    )
    if module_dicts:
        module_rows: List[Dict[str, str]] = []
        for module in module_dicts:
            persona = module.get("persona") if isinstance(module.get("persona"), dict) else None
            persona_id = str(persona.get("id")) if persona else "—"
            alias = module.get("alias") or "—"
            error_msg = module.get("error")
            status = "ok" if persona and not error_msg else "skipped"
            reason = error_msg or ("no persona contract found" if not persona else "—")
            module_rows.append(
                {
                    "module": module.get("module_name", ""),
                    "persona_id": persona_id,
                    "alias": alias,
                    "status": status,
                    "reason": reason,
                }
            )
        table_html = [
            "<table class='import-table'>",
            "<thead><tr><th>Status</th><th>Module</th><th>Persona id</th><th>Alias</th><th>Reason</th></tr></thead>",
            "<tbody>",
        ]
        for row in module_rows:
            status = row.get("status", "skipped")
            badge_class = "status-badge " + ("error" if status == "error" else status)
            badge_label = "ERR" if status == "error" else status.upper()
            reason = row.get("reason") or "—"
            table_html.append(
                "<tr>"
                f"<td><span class='{badge_class}'>{escape(badge_label)}</span></td>"
                f"<td>{escape(str(row.get('module', '')))}</td>"
                f"<td>{escape(str(row.get('persona_id', '')))}</td>"
                f"<td>{escape(str(row.get('alias', '—')))}</td>"
                f"<td>{escape(str(reason))}</td>"
                "</tr>"
            )
        table_html.append("</tbody></table>")
        with st.expander("Import details", expanded=False):
            st.markdown("".join(table_html), unsafe_allow_html=True)

    if additional_failures:
        with st.expander("Additional diagnostics"):
            for label, message in additional_failures.items():
                st.write(f"- **{label}**: {message}")

    if registry_result.errors:
        with st.expander("Validation issues", expanded=False):
            if registry_result.validation_mode == "warn":
                st.info("Personas below contain schema warnings but remain visible in the table above.")
            else:
                st.info("Personas listed below failed schema validation and were skipped.")
            error_rows = registry_result.errors
            if error_rows:
                if pd:
                    st.dataframe(pd.DataFrame(error_rows))  # type: ignore[arg-type]
                else:
                    st.table(error_rows)

    module_alias_map = {
        str(module.get("persona", {}).get("id")): module.get("alias")
        for module in module_dicts
        if isinstance(module.get("persona"), dict) and module.get("persona", {}).get("id")
    }

    entries = list(registry_result.items)
    existing_ids = {entry.get("id") for entry in entries}

    for module in module_dicts:
        persona = module.get("persona") if isinstance(module.get("persona"), dict) else None
        persona_id = str(persona.get("id")) if persona else ""
        if not persona or not persona_id or persona_id in existing_ids:
            continue
        raw_entry = {
            "id": persona_id,
            "label": persona.get("display_name"),
            "role": persona.get("role"),
            "prompt_assets": persona.get("prompt_assets", {}),
            "registration": persona,
        }
        try:
            normalized = registry_helpers.normalize_persona(raw_entry)
        except Exception:
            continue
        normalized["_module_alias"] = module.get("alias")
        entries.append(normalized)
        existing_ids.add(persona_id)

    if not entries and not module_dicts:
        st.info(
            "No personas registered yet. Open main Explorer once or click Reload to hydrate registrations."
        )
        return

    table_rows: List[Dict[str, object]] = []
    row_lookup: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        persona_id = str(entry.get("id") or "")
        display_name = entry.get("label") or persona_id
        version = entry.get("version") or registry_result.version or "–"
        greeting_template = entry.get("greeting_template") or ""
        handoff_list = entry.get("handoff_intents") or []
        style_list = entry.get("style_presets") or []
        warning = entry.get("_validation_warning") if isinstance(entry, dict) else None
        validation_display = "⚠︎ " + str(warning.get("message", "warning")) if warning else "OK"
        resolved_sources = entry.get("resolved_sources") if isinstance(entry.get("resolved_sources"), dict) else {}
        missing_roles = [
            role
            for role, info in resolved_sources.items()
            if isinstance(info, dict) and str(info.get("used")) == "missing"
        ]
        prompt_status = "⚠️ Missing prompts" if missing_roles else "OK"
        table_rows.append(
            {
                "id": persona_id,
                "version": version,
                "display_name": display_name,
                "greeting": greeting_template,
                "handoff_intents": _format_handoff(handoff_list),
                "style_presets": _format_style_presets(style_list),
                "validation": validation_display,
                "prompt_status": prompt_status,
                "import_alias": module_alias_map.get(persona_id, entry.get("_module_alias", "—")) or "—",
                "status": "ok",
                "reason": "—",
            }
        )
        row_lookup[persona_id] = {
            "entry": entry,
            "version": version,
            "display_name": display_name,
            "warning": warning,
            "status": "ok",
        }

    for module in module_dicts:
        persona = module.get("persona") if isinstance(module.get("persona"), dict) else None
        if persona:
            continue
        reason = module.get("error") or "no persona contract found"
        table_rows.append(
            {
                "id": f"(module:{module.get('module_name')})",
                "version": "—",
                "display_name": module.get("module_name"),
                "greeting": "—",
                "handoff_intents": "—",
                "style_presets": "—",
                "validation": f"skipped — {reason}",
                "prompt_status": "⚠️ Missing prompts",
                "import_alias": module.get("alias") or "—",
                "status": "skipped",
                "reason": reason,
            }
        )
        row_lookup[f"(module:{module.get('module_name')})"] = {
            "status": "skipped",
            "reason": reason,
            "module_name": module.get("module_name"),
        }

    selectable_rows = [row for row in table_rows if row.get("status") == "ok"]
    selected_id = st.session_state.get("_selected_persona_id") or st.session_state.get("_persona_selected_id")
    if selected_id not in row_lookup:
        selected_id = selectable_rows[0]["id"] if selectable_rows else None
    if selected_id:
        st.session_state["_selected_persona_id"] = selected_id
        st.session_state["_persona_selected_id"] = selected_id

    def _multiline_cell(value: object, limit: int = 160) -> str:
        if value is None:
            return "—"
        text = str(value).strip()
        if not text:
            return "—"
        if len(text) > limit:
            text = text[: limit - 3] + "..."
        return escape(text).replace("\n", "<br>")

    table_html = [
        "<table class='persona-table'>",
        "<thead><tr><th>Persona id</th><th>Display name</th><th>Greeting</th><th>Handoff intents</th><th>Style presets</th><th>Validation</th><th>Prompts</th><th>Alias / Notes</th></tr></thead>",
        "<tbody>",
    ]
    for row in table_rows:
        row_id = str(row.get("id"))
        row_status = str(row.get("status"))
        reason = row.get("reason") or ""
        classes: List[str] = []
        if row_id == selected_id:
            classes.append("selected")
        if row_status != "ok":
            classes.append("skipped")
        class_attr = f" class={' '.join(classes)}" if classes else ""
        tooltip = escape(str(reason)) if reason else "Registered persona"
        prompt_status = escape(str(row.get("prompt_status") or ""))
        validation = escape(str(row.get("validation") or ""))
        alias_note = _multiline_cell(row.get("import_alias"))
        if row_status != "ok" and reason:
            alias_note = (
                f"<span class='status-note'>{escape(str(row.get('display_name') or 'module'))}</span><br>"
                f"<span class='status-note'>Skipped · {escape(reason)}</span>"
            )
        table_html.append(
            f"<tr{class_attr} title='{tooltip}'>"
            f"<td>{escape(row_id)}</td>"
            f"<td>{_multiline_cell(row.get('display_name'))}</td>"
            f"<td>{_multiline_cell(row.get('greeting'))}</td>"
            f"<td>{_multiline_cell(row.get('handoff_intents'))}</td>"
            f"<td>{_multiline_cell(row.get('style_presets'))}</td>"
            f"<td>{validation}</td>"
            f"<td>{prompt_status}</td>"
            f"<td>{alias_note}</td>"
            "</tr>"
        )
    table_html.append("</tbody></table>")
    st.markdown("".join(table_html), unsafe_allow_html=True)

    if not selectable_rows:
        st.warning("No valid personas available for selection.")
        selected_meta = None
    else:
        option_ids = [row["id"] for row in selectable_rows]
        default_index = option_ids.index(selected_id) if selected_id in option_ids else 0

        def _persona_label(ident: str) -> str:
            meta = row_lookup.get(ident) or {}
            name = meta.get("display_name") or ident
            version = meta.get("version")
            if version and version not in ("—", "–"):
                return f"{name} ({ident}) · v{version}"
            return f"{name} ({ident})"

        selected_option = st.radio(
            "Select persona",
            option_ids,
            index=default_index,
            format_func=_persona_label,
            key="_persona_registry_select",
        )
        if selected_option != selected_id:
            st.session_state["_selected_persona_id"] = selected_option
            st.session_state["_persona_selected_id"] = selected_option
            _safe_rerun()
        selected_id = selected_option
        selected_meta = row_lookup.get(selected_id)

    selected_status = selected_meta.get("status") if isinstance(selected_meta, dict) else None
    display_name = (
        selected_meta.get("display_name") if isinstance(selected_meta, dict) else None
    ) or (selected_id or "")
    version_label = (
        selected_meta.get("version") if isinstance(selected_meta, dict) else registry_result.version or "–"
    )
    skip_reason = selected_meta.get("reason") if isinstance(selected_meta, dict) else None

    entry = (
        selected_meta.get("entry")
        if isinstance(selected_meta, dict) and selected_meta.get("status") == "ok"
        else None
    )
    registration = entry.get("registration") if isinstance(entry, dict) and isinstance(entry.get("registration"), dict) else {}
    greeting_template = entry.get("greeting_template") if isinstance(entry, dict) else ""
    greeting_preview = (
        greeting_template.replace("{user_name}", "Alex")
        if isinstance(greeting_template, str) and greeting_template
        else ""
    )

    resolved_sources = (
        entry.get("resolved_sources")
        if isinstance(entry, dict) and isinstance(entry.get("resolved_sources"), dict)
        else {}
    )
    bundle = (
        entry.get("prompt_bundle")
        if isinstance(entry, dict) and isinstance(entry.get("prompt_bundle"), dict)
        else {"system": "", "opening": ""}
    )

    sandbox_presets_map = st.session_state.setdefault("_sandbox_presets", {})

    def _micro_tokens(value: Any) -> List[str]:
        seen: Set[str] = set()
        tokens: List[str] = []
        if value is None:
            return tokens
        if isinstance(value, str):
            for item in value.split(","):
                token = item.strip()
                if token and token not in seen:
                    tokens.append(token)
                    seen.add(token)
            return tokens
        if isinstance(value, (list, tuple, set)):
            for item in value:
                token = str(item).strip()
                if token and token not in seen:
                    tokens.append(token)
                    seen.add(token)
            return tokens
        return tokens

    allowed_micro_tokens = set(SANDBOX_MICRO_ACTIONS.values())

    style_defaults_raw = entry.get("style_defaults") if isinstance(entry, dict) else {}
    style_defaults = {
        "tone": "Neutral",
        "formality": 50,
        "warmth": 50,
        "directness": 50,
        "micro_actions": [],
    }
    if isinstance(style_defaults_raw, dict) and style_defaults_raw:
        style_defaults["tone"] = _norm_tone(style_defaults_raw.get("tone"))
        style_defaults["formality"] = _coerce_int(
            style_defaults_raw.get("formality"),
            style_defaults["formality"],
        )
        style_defaults["warmth"] = _coerce_int(
            style_defaults_raw.get("warmth"),
            style_defaults["warmth"],
        )
        style_defaults["directness"] = _coerce_int(
            style_defaults_raw.get("directness"),
            style_defaults["directness"],
        )
        style_defaults["micro_actions"] = _micro_tokens(
            style_defaults_raw.get("micro_actions") or style_defaults_raw.get("micro")
        )
        style_defaults["micro_actions"] = [
            token for token in style_defaults["micro_actions"] if token in allowed_micro_tokens
        ]
    if style_defaults["tone"] not in SANDBOX_TONE_OPTIONS:
        style_defaults["tone"] = "Neutral"

    def _merge_presets(source: Any) -> Dict[str, Any]:
        merged = dict(style_defaults)
        if isinstance(source, dict):
            tone_candidate = _norm_tone(source.get("tone"))
            if tone_candidate in SANDBOX_TONE_OPTIONS:
                merged["tone"] = tone_candidate
            merged["formality"] = _coerce_int(source.get("formality"), merged["formality"])
            merged["warmth"] = _coerce_int(source.get("warmth"), merged["warmth"])
            merged["directness"] = _coerce_int(source.get("directness"), merged["directness"])
            tokens = _micro_tokens(source.get("micro_actions") or source.get("micro"))
            if tokens:
                merged["micro_actions"] = [token for token in tokens if token in allowed_micro_tokens]
        return merged

    persona_presets = _merge_presets(
        sandbox_presets_map.get(selected_id) if isinstance(sandbox_presets_map, dict) else None
    ) if selected_id else dict(style_defaults)
    if selected_id and isinstance(sandbox_presets_map, dict) and selected_id not in sandbox_presets_map:
        sandbox_presets_map[selected_id] = dict(persona_presets)

    head_coach_state_key = "_head_coach_preview"
    preview_state = st.session_state.get(head_coach_state_key)
    if isinstance(preview_state, dict) and preview_state.get("persona_id") != selected_id:
        preview_state = None

    curiosity_flag_value, curiosity_flag_source = curiosity_flag_state()
    live_requested = bool(st.session_state.get(LIVE_MODE_KEY, False))
    effective_live = live_requested and curiosity_flag_value

    timeout_value_raw, _ = get_flag_float("DEV_HTTP_TIMEOUT_SECONDS", 6.0)
    try:
        timeout_value = float(timeout_value_raw)
    except (TypeError, ValueError):
        timeout_value = 6.0

    micro_tokens = list(persona_presets.get("micro_actions", []))
    micro_label_map = {token: label for label, token in SANDBOX_MICRO_ACTIONS.items()}
    micro_labels = [micro_label_map.get(token, token) for token in micro_tokens if token in micro_label_map]

    st.session_state.setdefault("_head_coach_intent", "None")
    intent_label = st.session_state.get("_head_coach_intent", "None")
    intent_meta = HEAD_COACH_INTENTS.get(intent_label, HEAD_COACH_INTENTS["None"])

    tone_meta = {
        "tone": persona_presets["tone"],
        "formality": persona_presets["formality"],
        "warmth": persona_presets["warmth"],
        "directness": persona_presets["directness"],
        "micro_actions": micro_tokens,
        "intent_token": intent_meta.get("token", ""),
        "intent_label": intent_label,
    }

    head_cols = st.columns([2.6, 1.3, 1.0, 1.3, 1.0, 1.1])
    with head_cols[0]:
        user_default = _get_head_coach_user_id()
        user_input = st.text_input(
            "Head Coach user id",
            value=user_default,
            key="_head_coach_user_input",
            on_change=lambda: _set_head_coach_user_id(st.session_state.get("_head_coach_user_input", "")),
        )
        _set_head_coach_user_id(user_input)
        if st.button("Use Diagnostics id", key=f"headcoach_use_diag_{selected_id}"):
            diag_id = _get_loop_user_id()
            st.session_state.pop("_head_coach_user_input", None)
            _set_head_coach_user_id(diag_id, defer_rerun=True)
    with head_cols[1]:
        st.selectbox(
            "Intent",
            list(HEAD_COACH_INTENTS.keys()),
            key="_head_coach_intent",
            help="Add optional guidance to shape the motivator tone.",
        )
        display_meta = HEAD_COACH_INTENTS.get(st.session_state.get("_head_coach_intent", "None"), HEAD_COACH_INTENTS["None"])
        if display_meta.get("suffix"):
            st.caption(display_meta["suffix"])
    with head_cols[2]:
        mode_label = "Live (Core)" if effective_live else "Simulated"
        badge_html = _source_badge_html(curiosity_flag_source)
        st.markdown(
            f"**Curiosity mode** {badge_html}<br><span class='status-note'>{mode_label}</span>",
            unsafe_allow_html=True,
        )
        if live_requested and not curiosity_flag_value:
            st.caption("Flag disabled → using simulated curiosity.")
    with head_cols[3]:
        slider_value = st.slider(
            "Top N",
            min_value=3,
            max_value=10,
            value=int(st.session_state.get("_head_coach_top_n", 5)),
            key="_head_coach_top_n_slider",
        )
    top_n = int(slider_value)
    st.session_state["_head_coach_top_n"] = top_n
    intent_label = st.session_state.get("_head_coach_intent", "None")
    intent_meta = HEAD_COACH_INTENTS.get(intent_label, HEAD_COACH_INTENTS["None"])
    with head_cols[4]:
        tone_display = persona_presets["tone"].capitalize()
        st.markdown(f"**Tone** {tone_display}")
        st.caption(
            f"F{persona_presets['formality']} · W{persona_presets['warmth']} · D{persona_presets['directness']}"
        )
        if micro_labels:
            st.caption("Micro actions: " + ", ".join(micro_labels))
        deltas: List[str] = []
        if persona_presets["tone"] != style_defaults["tone"]:
            deltas.append(f"Tone → {persona_presets['tone']}")
        for key, label in (("formality", "Formality"), ("warmth", "Warmth"), ("directness", "Directness")):
            diff = int(persona_presets[key]) - int(style_defaults[key])
            if diff:
                sign = "+" if diff > 0 else ""
                deltas.append(f"{label} {sign}{diff}")
        if micro_tokens != style_defaults.get("micro_actions", []):
            deltas.append("Micro updated")
        if deltas:
            st.caption("Adjustments: " + ", ".join(deltas))
        else:
            st.caption("Using persona defaults.")
    with head_cols[5]:
        busy = bool(st.session_state.get("_head_coach_busy"))
        generate_clicked = st.button(
            "Generate live nudges",
            key=f"headcoach_generate_{selected_id}",
            disabled=busy,
        )

    def _run_head_coach_preview(use_simulated: bool = False) -> None:
        user_id = _get_head_coach_user_id().strip()
        if not user_id:
            st.warning("Enter a user id before generating motivators.")
            return
        st.session_state["_head_coach_busy"] = True
        try:
            with st.spinner("Building Head Coach preview…"):
                base_schema = load_schema(REPO_ROOT)
                draft_schema = st.session_state.get(DRAFT_KEY)
                if not isinstance(draft_schema, dict):
                    draft_schema = load_saved_draft(REPO_ROOT)
                if not isinstance(draft_schema, dict):
                    draft_schema = None

                mode_label = "simulated"
                rows: List[Dict[str, Any]] = []
                live_error_message: Optional[str] = None
                live_error_detail: Optional[str] = None
                snapshot: Optional[LiveCuriositySnapshot] = None

                if effective_live and not use_simulated:
                    rows, live_error_message, snapshot = fetch_live_curiosity_rows(
                        user_id,
                        top_n=top_n,
                        timeout=timeout_value,
                        core_base=core_base_url(),
                    )
                    if snapshot is not None:
                        st.session_state[LIVE_SNAPSHOT_KEY] = snapshot
                        st.session_state[LIVE_ERROR_KEY] = (
                            live_error_message or snapshot.error
                        )
                    else:
                        st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
                        st.session_state[LIVE_ERROR_KEY] = live_error_message

                    if not live_error_message and not rows:
                        live_error_message = "No live curiosity available for this user."

                    if live_error_message:
                        live_error_detail = (
                            getattr(snapshot, "error_detail", None) or live_error_message
                        )
                        rows = simulated_curiosity_rows(base_schema, top_n=top_n)
                        mode_label = "simulated"
                    else:
                        mode_label = "live"
                else:
                    rows = simulated_curiosity_rows(base_schema, top_n=top_n)
                    st.session_state.pop(LIVE_SNAPSHOT_KEY, None)
                    st.session_state.pop(LIVE_ERROR_KEY, None)

                if not rows:
                    st.session_state[head_coach_state_key] = {
                        "persona_id": selected_id,
                        "user_id": user_id,
                        "mode": mode_label,
                        "items": [],
                        "error": live_error_message or "No curiosity traits available for this user.",
                        "top_n": top_n,
                        "tone_meta": tone_meta,
                        "micro_labels": micro_labels,
                        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                        "live_error": live_error_message,
                        "live_error_detail": live_error_detail,
                        "intent_label": intent_label,
                    }
                    return

                feedback_aggregates: Dict[str, FeedbackAggregate] = fetch_feedback_aggregates(
                    None,
                    write_protect=DEV_WRITE_CONTEXT.write_protect,
                )
                feedback_k_value, _ = get_flag_float("FEEDBACK_WEIGHT_K", 0.2)
                try:
                    feedback_k = float(feedback_k_value)
                except (TypeError, ValueError):
                    feedback_k = 0.2

                scored_rows: List[Dict[str, Any]] = []
                for entry in rows:
                    enriched_row = dict(entry)
                    container_id = str(enriched_row.get("container_id") or "").strip()
                    trait_id = str(enriched_row.get("trait_id") or "").strip()
                    enriched_row["container_id"] = container_id
                    enriched_row["trait_id"] = trait_id

                    try:
                        curiosity_score = float(enriched_row.get("curiosity", 0.0))
                    except (TypeError, ValueError):
                        curiosity_score = 0.0
                    curiosity_score = max(0.0, min(curiosity_score, 1.0))
                    enriched_row["curiosity"] = curiosity_score

                    aggregate: Optional[FeedbackAggregate] = None
                    candidate_keys: List[str] = []
                    if container_id and trait_id:
                        candidate_keys.append(f"{container_id}.{trait_id}")
                    if trait_id:
                        candidate_keys.append(trait_id)
                    if container_id:
                        candidate_keys.append(container_id)

                    feedback_path_value: Optional[str] = None
                    if candidate_keys:
                        feedback_path_value = candidate_keys[0]
                    for key in candidate_keys:
                        agg_candidate = feedback_aggregates.get(key)
                        if agg_candidate:
                            aggregate = agg_candidate
                            feedback_path_value = agg_candidate.path or key
                            break

                    multiplier, planning_weight = compute_feedback_multiplier(
                        curiosity_score,
                        aggregate,
                        feedback_k=feedback_k,
                    )
                    enriched_row["planning_weight"] = planning_weight
                    enriched_row["feedback_multiplier"] = multiplier
                    enriched_row["feedback_score"] = aggregate.score if aggregate else 0.0
                    enriched_row["feedback_helpful"] = aggregate.helpful if aggregate else 0
                    enriched_row["feedback_not_helpful"] = aggregate.not_helpful if aggregate else 0
                    enriched_row["feedback_last_ts"] = aggregate.last_ts if aggregate else None
                    if feedback_path_value or (aggregate and aggregate.path):
                        enriched_row["feedback_path"] = str(
                            (aggregate.path if aggregate else feedback_path_value) or ""
                        ) or None
                    else:
                        enriched_row["feedback_path"] = None

                    scored_rows.append(enriched_row)

                if scored_rows:
                    scored_rows.sort(
                        key=lambda item: (
                            item.get("planning_weight") or 0.0,
                            item.get("curiosity") or 0.0,
                        ),
                        reverse=True,
                    )
                    rows = scored_rows

                credna_registry: Optional[Dict[str, Any]] = None
                credna_coach_payload: Optional[Dict[str, Any]] = None
                credna_coach_id: Optional[str] = None
                credna_coach_label: Optional[str] = None
                credna_enabled, _ = get_flag_bool("CREDNA_ENABLED", True)
                if credna_enabled and selected_id:
                    try:
                        credna_registry = credna_store.load_registry(DEV_WRITE_CONTEXT)
                    except Exception:
                        credna_registry = None
                    if credna_registry:
                        credna_coach_id = credna_ops.resolve_coach_for_persona(
                            credna_registry,
                            str(selected_id),
                            display_name=str(display_name or ""),
                        )
                        if credna_coach_id:
                            credna_coach_payload = credna_ops.get_coach(
                                credna_registry,
                                credna_coach_id,
                            )
                            if credna_coach_payload:
                                credna_coach_label = str(
                                    credna_coach_payload.get("label") or credna_coach_id
                                )

                fallback_pairs: List[Tuple[str, str]] = []
                items: List[Dict[str, Any]] = []

                for row in rows[:top_n]:
                    container_id = str(row.get("container_id") or "").strip()
                    trait_id = str(row.get("trait_id") or "").strip()
                    if not container_id or not trait_id:
                        continue
                    try:
                        curiosity_score = float(row.get("curiosity", 0.0))
                    except (TypeError, ValueError):
                        curiosity_score = 0.0
                    curiosity_score = max(0.0, min(curiosity_score, 1.0))

                    ucn_raw = row.get("ucn")
                    try:
                        ucn_value = float(ucn_raw)
                    except (TypeError, ValueError):
                        ucn_value = None
                    if ucn_value is not None:
                        ucn_value = max(0.0, min(ucn_value, 1.0))

                    resolution = resolve_motivator_template(
                        base_schema,
                        draft_schema,
                        container_id,
                        trait_id,
                        persona_presets["tone"],
                    )

                    effective_template = resolution.template
                    tone_used = resolution.tone_used
                    trait_label_value = resolution.trait_label
                    template_source = resolution.template_source or "fallback"
                    credna_meta: Optional[Dict[str, Any]] = None

                    if credna_coach_payload:
                        candidate = credna_ops.find_trait_template(
                            credna_coach_payload,
                            container_id,
                            trait_id,
                            persona_presets["tone"],
                        )
                        if candidate and candidate.get("template"):
                            credna_meta = candidate
                            effective_template = candidate.get("template")
                            tone_used = candidate.get("tone_used") or tone_used
                            trait_label_value = candidate.get("trait_label") or trait_label_value
                            template_source = "credna"

                    if not effective_template:
                        fallback_pairs.append((container_id, trait_id))

                    text = _format_nudge_text(
                        effective_template,
                        trait_label=trait_label_value,
                        curiosity_value=curiosity_score,
                        resolved_value=row.get("resolved_value"),
                    )
                    if micro_labels:
                        text = text.rstrip() + "\nMicro actions: " + ", ".join(micro_labels)
                    if intent_meta.get("suffix"):
                        text = text.rstrip() + "\n\n" + intent_meta["suffix"]

                    credna_provenance = credna_meta.get("provenance") if credna_meta and template_source == "credna" else None
                    credna_tone = credna_meta.get("tone_used") if credna_meta and template_source == "credna" else None

                    items.append(
                        {
                            "container": container_id,
                            "trait_id": trait_id,
                            "trait_label": trait_label_value,
                            "tone_used": tone_used,
                            "text": text,
                            "curiosity": curiosity_score,
                            "planning_weight": row.get("planning_weight"),
                            "feedback_multiplier": row.get("feedback_multiplier"),
                            "feedback_helpful": row.get("feedback_helpful"),
                            "feedback_not_helpful": row.get("feedback_not_helpful"),
                            "feedback_score": row.get("feedback_score"),
                            "feedback_last_ts": row.get("feedback_last_ts"),
                            "feedback_path": row.get("feedback_path"),
                            "ucn": ucn_value,
                            "template_source": template_source,
                            "source": "live" if mode_label == "live" else "simulated",
                            "resolved_value": row.get("resolved_value"),
                            "credna_coach_id": credna_coach_id if template_source == "credna" else None,
                            "credna_coach_label": credna_coach_label if template_source == "credna" else None,
                            "credna_provenance": credna_provenance,
                            "credna_tone_used": credna_tone,
                        }
                    )

                st.session_state[head_coach_state_key] = {
                    "persona_id": selected_id,
                    "user_id": user_id,
                    "mode": mode_label,
                    "items": items,
                    "error": None,
                    "top_n": top_n,
                    "tone_meta": tone_meta,
                    "micro_labels": micro_labels,
                    "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "fallback_pairs": fallback_pairs,
                    "live_error": live_error_message,
                    "live_error_detail": live_error_detail,
                    "intent_label": intent_label,
                    "feedback_k": feedback_k,
                }
        finally:
            st.session_state["_head_coach_busy"] = False

    if generate_clicked:
        _run_head_coach_preview(use_simulated=not effective_live)
        st.session_state["_devexp_scroll_target"] = "head-coach-preview"
        preview_state = st.session_state.get(head_coach_state_key)

    st.markdown("<a id='head-coach-preview'></a>", unsafe_allow_html=True)
    preview_container = st.container()
    with preview_container:
        st.subheader("Head Coach Preview")

        status_persona = str(selected_id or "—")
        status_user_raw = user_input.strip()
        status_user = status_user_raw or "—"
        preview_mode_token = str(
            preview_state.get("mode") if isinstance(preview_state, dict) else ("live" if effective_live else "simulated")
        ).lower()
        mode_display = "Live" if preview_mode_token == "live" else "Simulated"
        mode_badge = _source_badge_html(mode_info.effective_source)

        persona_chip = f"<span class='dev-chip'><strong>Persona:</strong> {escape(status_persona)}</span>"
        user_chip = f"<span class='dev-chip'><strong>User:</strong> {escape(status_user)}</span>"
        mode_chip = (
            "<span class='dev-chip'><strong>Mode:</strong> "
            f"{escape(mode_display)}{mode_badge}</span>"
        )

        feedback_k_state = (
            preview_state.get("feedback_k") if isinstance(preview_state, dict) else None
        )
        if isinstance(feedback_k_state, (int, float)):
            feedback_k_chip = (
                "<span class='dev-chip'><strong>Feedback k:</strong> "
                f"{feedback_k_state:.2f}</span>"
            )
        else:
            feedback_k_chip = ""

        if core_curiosity_flag is True:
            core_class = "dev-chip dev-chip--ok"
            core_label = "on"
        elif core_curiosity_flag is False:
            core_class = "dev-chip dev-chip--warn"
            core_label = "off"
        else:
            core_class = "dev-chip"
            core_label = "unknown"
        core_tooltip = core_health_error or "Reported by Core /health"
        core_chip = (
            f"<span class='{core_class}' title='{escape(core_tooltip)}'>"
            f"<strong>Core curiosity:</strong> {escape(core_label)}</span>"
        )

        core_base = core_base_url().rstrip("/")
        if status_user_raw:
            curiosity_href = f"{core_base}/curiosity/{status_user_raw}"
            url_chip = (
                "<span class='dev-chip'><strong>Live URL:</strong> "
                f"<a href='{escape(curiosity_href)}' target='_blank'>{escape(curiosity_href)}</a></span>"
            )
        else:
            placeholder = f"{core_base}/curiosity/{{user_id}}"
            url_chip = (
                "<span class='dev-chip'><strong>Live URL:</strong> "
                f"{escape(placeholder)}</span>"
            )

        status_html = (
            "<div class='persona-sticky-row'>"
            f"{persona_chip}{user_chip}{mode_chip}{feedback_k_chip}{core_chip}{url_chip}"
            "</div>"
        )
        st.markdown(status_html, unsafe_allow_html=True)

        target_default = st.session_state.get("_nudge_target_user") or _get_loop_user_id()
        target_user_input = st.text_input(
            "Send nudges to user",
            value=target_default,
            key="_nudge_target_user_input",
            help="Override the user receiving these motivators (defaults to Diagnostics loop user).",
        )
        target_user_value = target_user_input.strip() or target_default
        st.session_state["_nudge_target_user"] = target_user_value

        items = preview_state.get("items", []) if isinstance(preview_state, dict) else []
        live_error_message = (
            preview_state.get("live_error") if isinstance(preview_state, dict) else None
        )
        live_error_detail = (
            preview_state.get("live_error_detail") if isinstance(preview_state, dict) else None
        )
        preview_error = (
            preview_state.get("error") if isinstance(preview_state, dict) else None
        )

        selected_cohort: Optional[str] = None
        if items:
            if preview_mode_token != "live":
                if live_error_message:
                    st.warning(
                        f"Live curiosity failed: {live_error_message}. Showing simulated curiosity."
                    )
                else:
                    st.info("Showing simulated curiosity — enable live curiosity for Core data.")
            if live_error_message and live_error_detail:
                with st.expander("Why not live?", expanded=False):
                    st.code(live_error_detail)

            prepared_items: List[Dict[str, Any]] = [
                {
                    "container": item.get("container"),
                    "trait_id": item.get("trait_id"),
                    "text": item.get("text"),
                    "template_source": item.get("template_source"),
                    "source": item.get("source"),
                    "curiosity": item.get("curiosity"),
                    "ucn": item.get("ucn"),
                }
                for item in items
            ]

            tone_meta_payload = preview_state.get("tone_meta") or {}
            copy_payload = "\n".join(
                f"{idx}. {item.get('text', '')}" for idx, item in enumerate(items, 1)
            )
            export_payload = {
                "ts": preview_state.get("timestamp") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "user_id": preview_state.get("user_id"),
                "source": preview_state.get("mode"),
                "top_n": preview_state.get("top_n"),
                "persona_id": selected_id,
                "tone_meta": tone_meta_payload,
                "items": items,
                "cohort": None,
            }

            send_feedback_key = f"_hc_send_feedback_{selected_id}"

            if hc_ab_enabled:
                cohort_options = ["A", "B", "None"]
                default_choice = st.session_state.get("_headcoach_cohort", cohort_options[0])
                if default_choice not in cohort_options:
                    default_choice = cohort_options[0]
                selected_label = st.radio(
                    "Cohort",
                    cohort_options,
                    index=cohort_options.index(default_choice),
                    key="_headcoach_cohort",
                    horizontal=True,
                    help="Tag outgoing bundles with an A/B cohort label.",
                )
                selected_cohort = None if selected_label == "None" else selected_label
                export_payload["cohort"] = selected_cohort
            else:
                st.session_state.pop("_headcoach_cohort", None)
                selected_cohort = None

            if hc_send_enabled:
                copy_col, export_col, top_col, send_col, feedback_col = st.columns([0.18, 0.18, 0.2, 0.2, 0.24])
            else:
                copy_col, export_col, feedback_col = st.columns([0.25, 0.25, 0.5])
                top_col = None
                send_col = None

            copy_button_html = (
                "<button class='persona-action' type='button' "
                f"onclick=\"navigator.clipboard.writeText({json.dumps(copy_payload)})\">Copy all</button>"
            )
            with copy_col:
                st.markdown(copy_button_html, unsafe_allow_html=True)

            with export_col:
                st.download_button(
                    "Export JSON",
                    data=json.dumps(export_payload, indent=2),
                    file_name=f"head_coach_preview_{selected_id}_{preview_state.get('mode', 'sim')}.json",
                    mime="application/json",
                    key=f"headcoach_export_{selected_id}",
                )

            def _enqueue_payload(
                payload_items: List[Dict[str, Any]],
                label: str,
                *,
                cohort: Optional[str] = None,
            ) -> None:
                user_for_bundle = (
                    target_user_value
                    or str(preview_state.get("user_id") or status_user_raw or "").strip()
                )
                if not user_for_bundle:
                    st.warning("Specify a target user before sending nudges.")
                    return
                if not selected_id:
                    st.warning("Select a persona before sending nudges.")
                    return
                if not payload_items:
                    st.warning("Select at least one motivator to send.")
                    return

                snapshot_id = st.session_state.get("_latest_snapshot_id")
                segments = [
                    f"tone={tone_meta_payload.get('tone', '—')}",
                    f"formality={tone_meta_payload.get('formality', '—')}",
                    f"warmth={tone_meta_payload.get('warmth', '—')}",
                    f"directness={tone_meta_payload.get('directness', '—')}",
                ]
                intent_token = tone_meta_payload.get("intent_token")
                if intent_token:
                    segments.append(f"intent={intent_token}")
                tone_meta_string = "; ".join(segments)

                traits_used = [
                    {
                        "container": item.get("container"),
                        "trait_id": item.get("trait_id"),
                        "template": item.get("template_source"),
                    }
                    for item in payload_items
                ]
                text_concat = "||".join(item.get("text", "") for item in payload_items)
                content_hash = hashlib.sha256(text_concat.encode("utf-8")).hexdigest() if text_concat else ""

                provenance = {
                    "source": "dev_explorer",
                    "core_user_id": str(preview_state.get("user_id") or status_user_raw or ""),
                    "env": {
                        "WP": "true" if context.write_protect else "false",
                        "CUR": preview_state.get("mode") or ("live" if effective_live else "sim"),
                    },
                    "intent": intent_meta.get("token") or intent_label.lower(),
                    "intent_label": intent_label,
                    "traits": traits_used,
                }
                if content_hash:
                    provenance["content_hash"] = content_hash
                if cohort:
                    provenance["cohort"] = cohort

                try:
                    result = enqueue_nudge(
                        user_id=user_for_bundle,
                        persona_id=str(selected_id),
                        mode=str(preview_state.get("mode") or "simulated"),
                        items=payload_items,
                        tone_meta=tone_meta_string,
                        snapshot_id=snapshot_id,
                        provenance=provenance,
                        context=context,
                        cohort=cohort,
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:  # pragma: no cover - defensive guard
                    st.error(f"Unable to queue nudges: {exc}")
                    return

                if result.get("duplicate"):
                    st.session_state[send_feedback_key] = {
                        "status": "duplicate",
                        "message": "No changes — identical to the most recent inbox entry.",
                    }
                    return

                bundle_info = result.get("bundle") or {}
                st.session_state[send_feedback_key] = {
                    "status": "ok",
                    "label": label,
                    "count": len(payload_items),
                    "user": user_for_bundle,
                    "ts": bundle_info.get("ts"),
                    "snapshot_id": snapshot_id,
                    "bundle_id": bundle_info.get("id"),
                }

            if hc_send_enabled and top_col is not None:
                with top_col:
                    top_disabled = not prepared_items
                    top_clicked = st.button(
                        "Send Top 1",
                        key=f"headcoach_send_top_{selected_id}",
                        disabled=top_disabled,
                        help="Quick-send just the highest ranked motivator.",
                    )
                    if top_clicked:
                        _enqueue_payload(prepared_items[:1], "Top 1", cohort=selected_cohort)

            if hc_send_enabled and send_col is not None:
                with send_col:
                    send_disabled = not prepared_items
                    send_label = "Send to Nudge Inbox"
                    if hc_send_source == "env":
                        send_label = "Send (CP+ locked)"
                    send_clicked = st.button(
                        send_label,
                        key=f"headcoach_send_{selected_id}",
                        disabled=send_disabled,
                        help="Queues all motivators in the local Nudge Inbox (respecting write-protect).",
                    )
                    if send_clicked:
                        _enqueue_payload(prepared_items, "All", cohort=selected_cohort)

            with feedback_col:
                feedback = st.session_state.get(send_feedback_key)
                if isinstance(feedback, dict):
                    if feedback.get("status") == "duplicate":
                        st.info(feedback.get("message", "Duplicate bundle suppressed."))
                    elif feedback.get("status") == "ok":
                        label_text = feedback.get("label", "All")
                        msg = (
                            f"Queued {feedback.get('count', 0)} nudge(s) ({label_text}) for {feedback.get('user', '—')} "
                            f"→ {feedback.get('bundle_id', 'n/a')}"
                        )
                        st.success(msg)
                        snapshot_token = feedback.get("snapshot_id")
                        if snapshot_token:
                            st.caption(f"Snapshot link: {snapshot_token}")
                        if context.write_protect:
                            st.markdown(
                                "<span class='dev-chip dev-chip--warn'>Dry-run (write-protect ON)</span>",
                                unsafe_allow_html=True,
                            )
                        else:
                            log_file = nudge_log_path()
                            st.caption(f"Inbox persisted · log: {log_file.as_posix()}")
                elif not hc_send_enabled and send_feedback_key in st.session_state:
                    st.session_state.pop(send_feedback_key, None)
            
            tone_meta_preview = preview_state.get("tone_meta", {})
            tone_summary = (
                f"Tone {tone_meta_preview.get('tone', 'Neutral')} · F{tone_meta_preview.get('formality', 0)} "
                f"· W{tone_meta_preview.get('warmth', 0)} · D{tone_meta_preview.get('directness', 0)}"
            )
            if preview_state.get("micro_labels"):
                tone_summary += " · Micro: " + ", ".join(preview_state.get("micro_labels", []))
            if preview_state.get("intent_label") and preview_state.get("intent_label") != "None":
                tone_summary += f" · Intent: {preview_state.get('intent_label')}"
            if selected_cohort:
                tone_summary += f" · Cohort: {selected_cohort}"
            st.caption(tone_summary)

            fallback_pairs = preview_state.get("fallback_pairs") or []

            for idx, item in enumerate(items, 1):
                container_id = item.get("container") or ""
                trait_id = item.get("trait_id") or ""
                trait_label = item.get("trait_label") or trait_id
                curiosity_score = float(item.get("curiosity", 0.0))
                ucn_value = item.get("ucn")
                trait_path = f"{container_id}.{trait_id}" if container_id and trait_id else trait_label

                planning_weight_value = item.get("planning_weight")
                if not isinstance(planning_weight_value, (int, float)):
                    planning_weight_value = None

                multiplier_value = item.get("feedback_multiplier")
                if not isinstance(multiplier_value, (int, float)):
                    multiplier_value = None

                helpful_count = int(item.get("feedback_helpful", 0) or 0)
                not_helpful_count = int(item.get("feedback_not_helpful", 0) or 0)
                total_feedback = helpful_count + not_helpful_count

                try:
                    feedback_score_value = float(item.get("feedback_score", 0.0) or 0.0)
                except (TypeError, ValueError):
                    feedback_score_value = 0.0

                feedback_last_ts = str(item.get("feedback_last_ts") or "").strip() or None
                feedback_path_value = str(item.get("feedback_path") or "").strip() or None

                delta_percent = 0.0
                if multiplier_value is not None:
                    delta_percent = (multiplier_value - 1.0) * 100.0
                delta_label = f"{delta_percent:+.0f}%"
                tooltip_parts = [f"feedback: H={helpful_count}, NH={not_helpful_count}"]
                if total_feedback:
                    tooltip_parts.append(f"score={feedback_score_value:+.2f}")
                if feedback_last_ts:
                    tooltip_parts.append(f"last: {feedback_last_ts}")
                if feedback_path_value:
                    tooltip_parts.append(f"path: {feedback_path_value}")
                chip_class = "dev-chip"
                if delta_percent > 0.5:
                    chip_class = "dev-chip dev-chip--ok"
                elif delta_percent < -0.5:
                    chip_class = "dev-chip dev-chip--warn"
                feedback_chip_html = (
                    f"<span class='{chip_class}' title='{escape(' | '.join(tooltip_parts))}'>Δ {escape(delta_label)}</span>"
                )

                row_cols = st.columns([2.4, 3.4, 1.2])
                with row_cols[0]:
                    st.markdown(f"**{trait_label}**")
                    st.caption(trait_path)
                    copy_trait_html = (
                        "<button class='persona-action' type='button' "
                        f"onclick=\"navigator.clipboard.writeText({json.dumps(trait_path)})\">Copy id</button>"
                    )
                    st.markdown(copy_trait_html, unsafe_allow_html=True)
                with row_cols[1]:
                    st.write(item.get("text", ""))
                    badges: List[str] = [
                        f"<span class='dev-chip'>{'Live' if item.get('source') == 'live' else 'Simulated'}</span>",
                        f"<span class='dev-chip'>Template: {escape(str(item.get('template_source') or 'fallback'))}</span>",
                    ]
                    if item.get("template_source") == "credna":
                        coach_badge_label = item.get("credna_coach_label") or item.get("credna_coach_id") or "CReDNA"
                        badges.append(
                            f"<span class='dev-chip dev-chip--ok'>CReDNA: {escape(str(coach_badge_label))}</span>"
                        )
                    badges.append(feedback_chip_html)
                    badge_html = "".join(badges)
                    st.markdown(badge_html, unsafe_allow_html=True)
                    credna_prov = item.get("credna_provenance") if item.get("template_source") == "credna" else None
                    if credna_prov:
                        if isinstance(credna_prov, (list, tuple, set)):
                            prov_text = ", ".join(str(val) for val in credna_prov if val)
                        else:
                            prov_text = str(credna_prov)
                        if prov_text:
                            st.caption(f"CReDNA provenance: {prov_text}")
                with row_cols[2]:
                    st.markdown(f"Curiosity {curiosity_score * 100:.1f}%")
                    if planning_weight_value is not None:
                        st.caption(f"Planning weight {planning_weight_value * 100:.1f}%")
                    if isinstance(ucn_value, (int, float)):
                        st.markdown(f"UCN {ucn_value * 100:.1f}%")
                    resolved_value = item.get("resolved_value")
                    if resolved_value not in (None, ""):
                        st.caption(f"Value: {resolved_value}")
                    if container_id and trait_id:
                        deep_link = urlencode(
                            {
                                "nav": "Container Studio",
                                "container": container_id,
                                "trait": trait_id,
                            }
                        )
                        st.markdown(
                            f"[Open in Container Studio](?{deep_link}#container-studio-editor)",
                            unsafe_allow_html=False,
                        )

            if fallback_pairs:
                first_container, first_trait = fallback_pairs[0]
                deep_link = urlencode(
                    {
                        "nav": "Container Studio",
                        "container": first_container,
                        "trait": first_trait,
                    }
                )
                st.warning(
                    f"{len(fallback_pairs)} item(s) used fallback motivators — "
                    f"[jump to Container Studio](?{deep_link}#container-studio-editor) to author templates."
                )
        else:
            if preview_error:
                st.warning(preview_error)
            elif selected_id:
                st.info('Click "Generate live nudges" to build a Head Coach preview.')
            else:
                st.info("Select a persona to unlock Head Coach Preview.")

            if live_error_message:
                with st.expander("Why not live?", expanded=False):
                    st.code(live_error_detail or live_error_message)

    if hc_ops_enabled:
        _render_head_coach_ops_card(
            target_user=target_user_value,
            persona_id=str(selected_id or ""),
            selected_cohort_value=selected_cohort,
        )

    _render_ops_analytics(
        context,
        enabled=hc_ops_enabled,
        flag_source=hc_ops_source,
    )

    def _prompt_source_summary(resolved: Dict[str, Any]) -> Tuple[str, str]:
        if not resolved:
            return "n/a", "dev-chip dev-chip--warn"
        sources: List[str] = []
        for info in resolved.values():
            if isinstance(info, dict):
                used = str(info.get("used") or "").lower()
                if used:
                    sources.append(used)
        priority = ("dev_override", "live", "inline", "missing")
        for label in priority:
            if label in sources:
                if label == "missing":
                    return label, "dev-chip dev-chip--warn"
                if label == "inline":
                    return label, "dev-chip"
                return label, "dev-chip dev-chip--ok"
        if sources:
            label = sources[0]
            variant = "dev-chip"
            if label == "missing":
                variant = "dev-chip dev-chip--warn"
            elif label in ("dev_override", "live"):
                variant = "dev-chip dev-chip--ok"
            return label, variant
        return "missing", "dev-chip dev-chip--warn"

    style_defaults_available = bool(style_defaults_raw)

    if entry:
        prompt_label, prompt_variant = _prompt_source_summary(resolved_sources)
        prompt_chip = (
            f"<span class='{prompt_variant}'><strong>Prompt source:</strong> {escape(prompt_label)}</span>"
        )
        selected_chip = (
            "<span class='dev-chip dev-chip--ok' title='Selected persona'>"
            f"<strong>Persona:</strong> {escape(str(selected_id))} · {escape(str(display_name))} (v{escape(str(version_label))})"
            "</span>"
        )
    elif selected_id:
        prompt_chip = "<span class='dev-chip dev-chip--warn'><strong>Prompt source:</strong> n/a</span>"
        selected_chip = (
            "<span class='dev-chip dev-chip--warn' title='Persona skipped during registration'>"
            f"<strong>Persona:</strong> {escape(str(selected_id))} · {escape(str(display_name or 'skipped'))} (skipped)"
            "</span>"
        )
    else:
        prompt_chip = "<span class='dev-chip dev-chip--warn'><strong>Prompt source:</strong> n/a</span>"
        selected_chip = "<span class='dev-chip dev-chip--warn'>No persona selected</span>"

    style_chip = ""
    if selected_id:
        using_defaults = persona_presets == style_defaults
        state_label = "default" if using_defaults else "custom"
        style_chip = (
            "<span class='dev-chip'>"
            f"<strong>Sandbox style ({state_label}):</strong> {escape(str(persona_presets['tone']))} · "
            f"F{persona_presets['formality']} · W{persona_presets['warmth']} · D{persona_presets['directness']}"
            "</span>"
        )

    chips_html = (
        "<div class='persona-sticky-row'>"
        f"{selected_chip}{prompt_chip}{style_chip}"
        "</div>"
    )
    jump_html = (
        "<div class='persona-sticky-row'>"
        "<span class='jump-link'><a href='#persona-contract'>Contract</a></span>"
        "<span class='jump-link'><a href='#sandbox'>Jump to Sandbox</a></span>"
        "<span class='jump-link'><a href='#sandbox-ab'>A/B</a></span>"
        "<span class='jump-link'><a href='#head-coach-preview'>Head Coach Preview</a></span>"
        "</div>"
    )

    header_container = st.container()
    with header_container:
        st.markdown("<div class='persona-sticky-header'>", unsafe_allow_html=True)
        chip_col, action_col = st.columns([7, 3])
        with chip_col:
            st.markdown(chips_html, unsafe_allow_html=True)
            st.markdown(jump_html, unsafe_allow_html=True)
        with action_col:
            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button("Reload personas", key="_persona_reload_header"):
                    new_result = _hydrate_persona_modules(context)
                    st.session_state["persona_import_result"] = new_result
                    _safe_rerun()
            with action_cols[1]:
                if selected_id:
                    copy_button_html = (
                        "<button class='persona-action' type='button' "
                        f"onclick=\"navigator.clipboard.writeText({json.dumps(selected_id)})\">Copy persona id</button>"
                    )
                    st.markdown(copy_button_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<span class='status-note'>Select a persona to copy id</span>",
                        unsafe_allow_html=True,
                    )
        st.markdown("</div>", unsafe_allow_html=True)

    if not selected_id:
        st.info("Select a persona above to inspect the contract and run sandbox tests.")
        return

    if entry is None:
        st.markdown("<div id='persona-contract'></div>", unsafe_allow_html=True)
        st.subheader("Raw Persona Contract")
        st.caption(f"Persona: {selected_id} — {display_name}")
        st.warning("Persona skipped during registration; no contract payload available.")
        if skip_reason:
            st.info(f"Reason: {skip_reason}")
        with st.expander("Prompt context", expanded=False):
            st.write(skip_reason or "No prompt sources were resolved for this module.")

        st.markdown("<div id='sandbox'></div>", unsafe_allow_html=True)
        st.subheader("Sandbox Test Reply")
        st.caption(f"Persona: {selected_id} — {display_name}")
        st.markdown(
            "<div class='sandbox-disabled'>Sandbox disabled — persona skipped during registration.</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div id='sandbox-ab'></div>", unsafe_allow_html=True)
        st.subheader("A/B Sandbox")
        st.markdown(
            "<div class='sandbox-disabled'>Sandbox disabled — persona skipped during registration.</div>",
            unsafe_allow_html=True,
        )
        return

    warning_meta = selected_meta.get("warning") if isinstance(selected_meta, dict) else None

    st.markdown("<div id='persona-contract'></div>", unsafe_allow_html=True)
    st.subheader("Raw Persona Contract")
    st.caption(f"Persona: {selected_id} — {display_name}")
    st.markdown(f"**Greeting preview:** {greeting_preview or '–'}")

    if isinstance(warning_meta, dict):
        st.warning(
            f"Validation warning: {warning_meta.get('message', 'see registry issues')} (path: {warning_meta.get('path', '—')})"
        )

    presets_raw = entry.get("style_presets") or []
    if presets_raw:
        chip_labels: List[str] = []
        for preset in presets_raw:
            if isinstance(preset, str):
                label = preset
            elif isinstance(preset, dict):
                label = preset.get("label") or preset.get("id") or ""
            else:
                label = ""
            if label:
                chip_labels.append(f"`{label}`")
        st.markdown("**Style presets:** " + (" ".join(chip_labels) if chip_labels else "–"))
    else:
        st.markdown("**Style presets:** –")

    handoff_raw = entry.get("handoff_intents") or []
    if handoff_raw:
        lines: List[str] = []
        for intent in handoff_raw:
            if isinstance(intent, str):
                lines.append(f"- {intent}")
            elif isinstance(intent, dict):
                phrase = intent.get("phrase") or ""
                parts = []
                match_type = intent.get("match_type")
                if match_type:
                    parts.append(match_type)
                reason = intent.get("reason")
                if reason:
                    parts.append(reason)
                detail = phrase
                if parts:
                    detail += f" ({', '.join(parts)})"
                lines.append(f"- {detail}")
        st.markdown("**Handoff intents:**\n" + "\n".join(lines))
    else:
        st.markdown("**Handoff intents:** –")

    with st.expander("Registration payload"):
        st.json(registration or {"message": "No registration payload cached."})

    if context.write_protect:
        st.warning("Write-protect ON — prompt editing disabled in this mode.")
    else:
        edit_enabled = st.checkbox(
            "Edit in dev_overrides/",
            value=True,
            help="Writes to persona_config/dev_overrides/<persona_id>/",
        )
        if edit_enabled:
            prompt_paths = _persona_prompt_paths(selected_id)
            system_path = prompt_paths["system"]
            opening_path = prompt_paths["opening"]

            existing_system = system_path.read_text(encoding="utf-8") if system_path.exists() else ""
            existing_opening = opening_path.read_text(encoding="utf-8") if opening_path.exists() else ""

            system_md = st.text_area("system.md", existing_system, height=240)
            opening_md = st.text_area("opening.md", existing_opening, height=200)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Save to dev_overrides"):
                    try:
                        write_guard(context, action="save persona prompt overrides")
                    except PermissionError as exc:
                        st.error(str(exc))
                    else:
                        system_path.parent.mkdir(parents=True, exist_ok=True)
                        system_path.write_text(system_md, encoding="utf-8")
                        opening_path.write_text(opening_md, encoding="utf-8")
                        st.success(f"Saved overrides to {system_path.parent.relative_to(REPO_ROOT)}")

            with col_b:
                if st.button("Register dev overrides"):
                    try:
                        write_guard(context, action="register persona overrides")
                    except PermissionError as exc:
                        st.error(str(exc))
                        payload = {}
                    else:
                        try:
                            payload = persona_registry.get_raw_payload(selected_id) or {}  # type: ignore[attr-defined]
                        except Exception as exc:  # pragma: no cover
                            st.error(f"Unable to load raw payload: {exc}")
                            payload = {}

                    if payload:
                        prompt_assets = payload.get("prompt_assets") if isinstance(payload, dict) else {}
                        if isinstance(prompt_assets, dict):
                            prompt_assets["system"] = str(system_path.relative_to(REPO_ROOT))
                            templates = prompt_assets.get("dialogue_templates")
                            if isinstance(templates, list) and templates:
                                prompt_assets["dialogue_templates"][0] = str(opening_path.relative_to(REPO_ROOT))
                            else:
                                prompt_assets["dialogue_templates"] = [str(opening_path.relative_to(REPO_ROOT))]
                        try:
                            persona_registry.register_persona(payload)  # type: ignore[attr-defined]
                            st.success("Dev overrides registered. Reload any active Streamlit session to apply.")
                        except Exception as exc:  # pragma: no cover
                            st.error(f"Registration failed: {exc}")
                    else:
                        st.error("Raw payload unavailable; cannot register overrides.")

    st.markdown("<div id='sandbox'></div>", unsafe_allow_html=True)
    st.caption(f"Selected persona: {selected_id} — {display_name}")
    st.markdown("---")
    st.subheader("Sandbox Test Reply")
    st.caption("Dry-run only — no data saved or sent to Core.")

    system_info = resolved_sources.get("system") if isinstance(resolved_sources, dict) else None
    if isinstance(system_info, dict):
        origin = str(system_info.get("used") or "")
        _record_persona_switch(selected_id, origin, context)

    def _render_prompt_context_details(resolved: Dict[str, Any]) -> None:
        if not resolved:
            st.info("No prompt assets resolved for this persona.")
            return
        for role in ("system", "opening"):
            info = resolved.get(role)
            if not isinstance(info, dict):
                st.write(f"- {role}: missing")
                continue
            used = str(info.get("used") or "missing")
            dev_path = info.get("dev_path") or "—"
            live_path = info.get("live_path") or "—"
            inline_detail = "inline literal" if info.get("inline_bytes") else "—"
            order_steps = [
                ("dev_override", dev_path),
                ("live", live_path),
                ("inline", inline_detail),
                ("missing", "no source matched"),
            ]
            block = [f"<div><strong>{role.capitalize()}</strong></div>", "<ul class='prompt-source-order'>"]
            for label, detail in order_steps:
                class_attr = " class='active'" if used == label else ""
                safe_detail = escape(str(detail))
                block.append(f"<li{class_attr}><code>{label}</code> — {safe_detail}</li>")
            block.append("</ul>")
            st.markdown("".join(block), unsafe_allow_html=True)
            checks = info.get("checked") if isinstance(info.get("checked"), list) else []
            for check in checks:
                if not isinstance(check, dict):
                    continue
                source = check.get("source", "source")
                detail = check.get("detail") or "—"
                hit = "✓" if check.get("hit") else "×"
                st.write(f"  - {hit} {source}: {detail}")

    with st.expander("Prompt context", expanded=False):
        _render_prompt_context_details(resolved_sources)

    sandbox_keys = st.session_state.setdefault("_sandbox_persona_keys", {})  # type: ignore[attr-defined]
    if selected_id not in sandbox_keys:
        index = len(sandbox_keys)
        sandbox_keys[selected_id] = {
            "input_a": f"sandbox_input_a_{selected_id}_{index}",
            "input_b": f"sandbox_input_b_{selected_id}_{index}",
            "run_a": f"sandbox_run_a_{selected_id}_{index}",
            "run_b": f"sandbox_run_b_{selected_id}_{index}",
            "run_both": f"sandbox_run_both_{selected_id}_{index}",
        }
    sandbox_key_map = sandbox_keys[selected_id]

    tone_key = f"_sandbox_tone_{selected_id}"
    formality_key = f"_sandbox_formality_{selected_id}"
    warmth_key = f"_sandbox_warmth_{selected_id}"
    directness_key = f"_sandbox_directness_{selected_id}"
    micro_key = f"_sandbox_micro_{selected_id}"

    sandbox_presets_map = st.session_state.setdefault("_sandbox_presets", {})
    token_to_label = {token: label for label, token in SANDBOX_MICRO_ACTIONS.items()}

    reset_payload = st.session_state.pop("_sandbox_reset_pending", None)
    if isinstance(reset_payload, dict) and reset_payload.get("persona") == selected_id:
        sandbox_presets_map[selected_id] = dict(style_defaults)
        persona_presets = dict(style_defaults)
        st.session_state[tone_key] = style_defaults["tone"]
        st.session_state[formality_key] = style_defaults["formality"]
        st.session_state[warmth_key] = style_defaults["warmth"]
        st.session_state[directness_key] = style_defaults["directness"]
        default_micro_labels = [
            token_to_label[token]
            for token in style_defaults["micro_actions"]
            if token in token_to_label
        ]
        st.session_state[micro_key] = default_micro_labels
        st.session_state["_sandbox_reset_notice"] = selected_id

    def _parse_meta_components(meta_str: str) -> Dict[str, str]:
        components: Dict[str, str] = {}
        for part in str(meta_str).split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            components[key.strip().lower()] = value.strip()
        return components

    def _apply_replay_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        current_defaults = sandbox_presets_map.get(selected_id, {}) if isinstance(sandbox_presets_map, dict) else {}
        meta_map = _parse_meta_components(payload.get("meta", ""))

        tone_seed = meta_map.get("tone")
        if tone_seed is None:
            tone_seed = current_defaults.get("tone")
        tone_value = _norm_tone(tone_seed)

        formality_value = _coerce_int(meta_map.get("formality"), current_defaults.get("formality", 50))
        warmth_value = _coerce_int(meta_map.get("warmth"), current_defaults.get("warmth", 50))
        directness_value = _coerce_int(meta_map.get("directness"), current_defaults.get("directness", 50))

        micro_raw = (meta_map.get("micro") or "").lower()
        micro_tokens: List[str] = []
        micro_labels: List[str] = []
        if micro_raw not in {"", "none"}:
            for token in [item.strip() for item in micro_raw.split(",") if item.strip()]:
                label = token_to_label.get(token)
                if label and label not in micro_labels:
                    micro_labels.append(label)
                    micro_tokens.append(token)

        st.session_state[tone_key] = tone_value
        st.session_state[formality_key] = formality_value
        st.session_state[warmth_key] = warmth_value
        st.session_state[directness_key] = directness_value
        st.session_state[micro_key] = micro_labels

        scenario_a = payload.get("scenarioA") or {}
        scenario_b = payload.get("scenarioB") or {}
        st.session_state[sandbox_key_map["input_a"]] = scenario_a.get("input", "") or ""
        st.session_state[sandbox_key_map["input_b"]] = scenario_b.get("input", "") or ""

        sandbox_outputs_state = st.session_state.setdefault("_sandbox_ab_outputs", {})
        sandbox_outputs_state[selected_id] = {
            "A": scenario_a.get("reply", "") or "",
            "B": scenario_b.get("reply", "") or "",
        }
        st.session_state["_sandbox_ab_outputs"] = sandbox_outputs_state

        return {
            "tone": tone_value,
            "formality": formality_value,
            "warmth": warmth_value,
            "directness": directness_value,
            "micro_actions": micro_tokens,
        }

    pending_replay = st.session_state.pop("_pending_ab_replay", None)
    if isinstance(pending_replay, dict):
        if pending_replay.get("persona_id") == selected_id:
            new_presets = _apply_replay_payload(pending_replay)
            if new_presets:
                sandbox_presets_map[selected_id] = new_presets
        else:
            st.session_state["_pending_ab_replay"] = pending_replay

    replay_file = st.file_uploader(
        "Replay A/B session",
        type="json",
        key=f"ab_replay_{selected_id}",
        help="Load a previously exported A/B session to prefill inputs and replies.",
    )
    if replay_file is not None:
        try:
            replay_payload = json.load(replay_file)
        except json.JSONDecodeError as exc:
            st.error(f"Unable to parse replay file: {exc}")
        else:
            target_persona = replay_payload.get("persona_id")
            if target_persona and target_persona != selected_id:
                st.session_state["_pending_ab_replay"] = replay_payload
                st.session_state["_selected_persona_id"] = target_persona
                st.session_state["_persona_selected_id"] = target_persona
                st.success(f"Switching to persona {target_persona} from replay…")
                _safe_rerun()
                return
            new_presets = _apply_replay_payload(replay_payload)
            if new_presets:
                sandbox_presets_map[selected_id] = new_presets
                st.success("Replay loaded.")
            else:
                st.warning("Replay payload missing scenario content.")

    cached_presets = sandbox_presets_map.get(selected_id, {}) if isinstance(sandbox_presets_map, dict) else {}
    persona_presets = {
        "tone": _norm_tone(cached_presets.get("tone")),
        "formality": _coerce_int(cached_presets.get("formality"), 50),
        "warmth": _coerce_int(cached_presets.get("warmth"), 50),
        "directness": _coerce_int(cached_presets.get("directness"), 50),
        "micro_actions": [
            token
            for token in _micro_tokens(cached_presets.get("micro_actions"))
            if token in allowed_micro_tokens
        ],
    }

    if tone_key not in st.session_state:
        st.session_state[tone_key] = persona_presets["tone"]
    tone_selection = st.radio(
        "Tone preset",
        SANDBOX_TONE_OPTIONS,
        key=tone_key,
        horizontal=True,
    )
    st.session_state["_sandbox_last_tone"] = str(tone_selection).lower()

    if formality_key not in st.session_state:
        st.session_state[formality_key] = persona_presets["formality"]
    formality_selection = st.slider(
        "Formality",
        min_value=0,
        max_value=100,
        value=int(st.session_state[formality_key]),
        key=formality_key,
    )

    if warmth_key not in st.session_state:
        st.session_state[warmth_key] = persona_presets["warmth"]
    warmth_selection = st.slider(
        "Warmth",
        min_value=0,
        max_value=100,
        value=int(st.session_state[warmth_key]),
        key=warmth_key,
    )

    if directness_key not in st.session_state:
        st.session_state[directness_key] = persona_presets["directness"]
    directness_selection = st.slider(
        "Directness",
        min_value=0,
        max_value=100,
        value=int(st.session_state[directness_key]),
        key=directness_key,
    )

    default_micro_labels = [
        label
        for label, token in SANDBOX_MICRO_ACTIONS.items()
        if token in persona_presets["micro_actions"]
    ]
    if micro_key not in st.session_state:
        st.session_state[micro_key] = default_micro_labels
    micro_selection_labels = st.multiselect(
        "Micro-actions",
        list(SANDBOX_MICRO_ACTIONS.keys()),
        key=micro_key,
    )
    micro_tokens = [SANDBOX_MICRO_ACTIONS[label] for label in micro_selection_labels]

    sandbox_presets_map[selected_id] = {
        "tone": str(tone_selection),
        "formality": int(formality_selection),
        "warmth": int(warmth_selection),
        "directness": int(directness_selection),
        "micro_actions": micro_tokens,
    }

    current_meta = _build_sandbox_meta(sandbox_presets_map[selected_id])
    st.caption(f"Sandbox meta: {current_meta}")

    if st.session_state.get("_sandbox_reset_notice") == selected_id:
        st.success("Sandbox controls reset to persona defaults.")
        st.session_state.pop("_sandbox_reset_notice", None)

    meta_action_cols = st.columns([1, 1, 2])
    with meta_action_cols[0]:
        reset_disabled = not style_defaults_available
        if st.button(
            "Reset to persona defaults",
            key=f"sandbox_reset_btn_{selected_id}",
            disabled=reset_disabled,
        ):
            st.session_state["_sandbox_reset_pending"] = {"persona": selected_id}
            _safe_rerun()
        if reset_disabled:
            st.caption("Persona contract does not declare style defaults.")
    with meta_action_cols[1]:
        copy_button_html = (
            "<button class='persona-action' type='button' "
            f"onclick=\"navigator.clipboard.writeText({json.dumps(current_meta)})\">Copy meta</button>"
        )
        st.markdown(copy_button_html, unsafe_allow_html=True)
        st.caption("Copies current sandbox meta to the clipboard.")
    with meta_action_cols[2]:
        default_meta = _build_sandbox_meta(style_defaults)
        st.caption(f"Default meta: {default_meta}")

    input_cols = st.columns(2)
    message_a = input_cols[0].text_area(
        "Scenario A",
        key=sandbox_key_map["input_a"],
        height=160,
    )
    message_b = input_cols[1].text_area(
        "Scenario B",
        key=sandbox_key_map["input_b"],
        height=160,
    )

    run_cols = st.columns(3)
    run_a = run_cols[0].button(
        "Generate A",
        key=sandbox_key_map["run_a"],
        disabled=not message_a.strip(),
    )
    run_b = run_cols[1].button(
        "Generate B",
        key=sandbox_key_map["run_b"],
        disabled=not message_b.strip(),
    )
    run_both = run_cols[2].button(
        "Run A/B",
        key=sandbox_key_map["run_both"],
        disabled=not (message_a.strip() or message_b.strip()),
    )

    sandbox_outputs = st.session_state.setdefault("_sandbox_ab_outputs", {})
    persona_outputs = sandbox_outputs.setdefault(selected_id, {"A": "", "B": ""})

    errors: List[str] = []

    def _run_label(label: str, text: str) -> None:
        nonlocal persona_outputs
        try:
            reply_text = _generate_sandbox_reply(
                bundle,
                text.strip(),
                meta=current_meta,
            )
        except Exception as exc:  # pragma: no cover - surface LLM issues
            errors.append(f"{label}: {exc}")
        else:
            persona_outputs[label] = reply_text

    if bundle:
        if run_a or run_both:
            if message_a.strip():
                _run_label("A", message_a)
            else:
                errors.append("Scenario A is empty.")
        if run_b or run_both:
            if message_b.strip():
                _run_label("B", message_b)
            else:
                errors.append("Scenario B is empty.")
    elif run_a or run_b or run_both:
        errors.append("Prompt bundle missing – reload persona and try again.")

    st.session_state["_sandbox_ab_outputs"] = sandbox_outputs

    if errors:
        for err in errors:
            st.error(err)

    export_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "persona_id": selected_id,
        "prompt_source": prompt_label,
        "meta": current_meta,
        "scenarioA": {
            "input": message_a,
            "reply": persona_outputs.get("A", ""),
        },
        "scenarioB": {
            "input": message_b,
            "reply": persona_outputs.get("B", ""),
        },
    }
    st.download_button(
        "Export A/B session",
        data=json.dumps(export_payload, indent=2),
        file_name=f"ab_session_{selected_id}.json",
        mime="application/json",
        key=f"sandbox_export_{selected_id}",
    )

    st.markdown("<div id='sandbox-ab'></div>", unsafe_allow_html=True)
    st.subheader("A/B Sandbox")
    st.caption(f"Persona: {selected_id} — {display_name}")

    reply_cols = st.columns(2)
    reply_a = persona_outputs.get("A", "").strip()
    reply_b = persona_outputs.get("B", "").strip()

    with reply_cols[0]:
        st.subheader("Reply A")
        if reply_a:
            st.code(reply_a)
        else:
            st.caption("No reply generated yet.")

    with reply_cols[1]:
        st.subheader("Reply B")
        if reply_b:
            st.code(reply_b)
        else:
            st.caption("No reply generated yet.")

    if reply_a and reply_b:
        diff_text = _compute_reply_diff(reply_a, reply_b)
        st.markdown("#### A/B diff")
        if diff_text:
            st.code(diff_text, language="diff")
        else:
            st.caption("Replies are identical after normalization.")


def _render_env_bool(label: str, value: bool, *, disabled: bool) -> bool:
    return st.checkbox(label, value=value, disabled=disabled)


def _render_env_int(label: str, value: int, *, disabled: bool, min_value: int = 0) -> int:
    return st.number_input(label, value=value, min_value=min_value, step=1, disabled=disabled)



def _parse_iso_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(token)
        except ValueError:
            return None
    return None


def _normalize_cohort(value: Any) -> str:
    token = str(value).strip().upper() if value is not None else ""
    return token or "None"


def _render_ops_analytics(
    context: DevWriteContext,
    *,
    enabled: bool,
    flag_source: str,
) -> None:
    if not enabled:
        return

    st.markdown("### Head Coach Ops Analytics")
    st.caption(
        "Aggregates mailbox schedules, inbox state, and dev logs to surface Ops performance indicators."
    )

    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=14)
    date_range = st.date_input(
        "Date range",
        value=(default_start, today),
        max_value=today,
    )
    if isinstance(date_range, tuple):
        if len(date_range) >= 2:
            start_date, end_date = date_range[0], date_range[1]
        elif date_range:
            start_date = end_date = date_range[0]
        else:
            start_date, end_date = default_start, today
    else:
        start_date, end_date = default_start, today
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    start_dt = datetime.combine(start_date, dt_time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, dt_time.max.replace(microsecond=0)).replace(tzinfo=timezone.utc)

    write_guard_state = "dry-run" if context.write_protect else "live"
    st.caption(f"Flag source: {flag_source} · Writes: {write_guard_state}")

    ops_configs = nudge_store.list_ops_configs(write_protect=context.write_protect)
    mailbox_users = nudge_store.list_mailbox_users()

    enqueues = nudge_store.load_enqueue_log(limit=None, newest_first=False)
    actions = nudge_store.load_nudge_actions_log(limit=None, newest_first=False)

    enqueue_meta: Dict[str, Dict[str, Any]] = {}
    persona_options: Set[str] = set()
    cohort_options: Set[str] = set()
    user_options: Set[str] = set()

    for record in enqueues:
        nudge_id = str(record.get("nudge_id") or "")
        if not nudge_id:
            continue
        persona_id = str(record.get("persona_id") or "unknown")
        user_id = str(record.get("user_id") or "")
        cohort_value = _normalize_cohort(record.get("cohort"))
        enqueue_meta[nudge_id] = {
            "persona_id": persona_id,
            "user_id": user_id,
            "cohort": cohort_value,
            "ts": _parse_iso_ts(record.get("ts")),
        }
        persona_options.add(persona_id)
        cohort_options.add(cohort_value)
        if user_id:
            user_options.add(user_id)

    for user_id, config in ops_configs.items():
        user_options.add(user_id)
        for entry in config.get("entries", []):
            persona_options.add(str(entry.get("persona_id") or "unknown"))
            cohort_options.add(_normalize_cohort(entry.get("cohort")))

    cohort_options.add("None")
    persona_choices = sorted(persona_options)
    user_choices = sorted(user_options)
    cohort_choices = sorted(cohort_options)

    filter_cols = st.columns(3)
    with filter_cols[0]:
        selected_users = st.multiselect("Users", user_choices, default=user_choices)
    with filter_cols[1]:
        selected_personas = st.multiselect("Personas", persona_choices, default=persona_choices)
    with filter_cols[2]:
        selected_cohorts = st.multiselect("Cohorts", cohort_choices, default=cohort_choices)

    selected_users_set = set(selected_users)
    selected_personas_set = set(selected_personas)
    selected_cohorts_set = set(selected_cohorts)

    bundle_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    trait_counts: Dict[Tuple[str, str], int] = {}

    for user_id in mailbox_users:
        if selected_users_set and user_id not in selected_users_set:
            continue
        bundles = nudge_store.list_inbox(
            user_id,
            status_filter="all",
            limit=500,
            write_protect=context.write_protect,
        )
        for bundle in bundles:
            bundle_id = str(bundle.get("id") or "")
            if bundle_id:
                bundle_index[(user_id, bundle_id)] = bundle
            persona_id = str(bundle.get("persona_id") or "unknown")
            if selected_personas_set and persona_id not in selected_personas_set:
                continue
            cohort_value = _normalize_cohort(bundle.get("cohort"))
            if selected_cohorts_set and cohort_value not in selected_cohorts_set:
                continue
            if bundle.get("status") == "accepted":
                items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
                for item in items:
                    if not isinstance(item, Mapping):
                        continue
                    container = str(item.get("container") or "").strip()
                    trait_id = str(item.get("trait_id") or "").strip()
                    trait_path = (
                        f"{container}.{trait_id}" if container and trait_id else trait_id or container or "trait"
                    )
                    key = (persona_id, trait_path)
                    trait_counts[key] = trait_counts.get(key, 0) + 1

    run_history_counter: Dict[Tuple[date, str], int] = {}
    persona_outcomes: Dict[Tuple[str, str], int] = {}
    cohort_totals: Dict[str, Dict[str, int]] = {}
    actions_by_schedule: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}

    for record in actions:
        action_type = str(record.get("action") or "").lower()
        if action_type not in {"accept", "dismiss", "undo", "snooze"}:
            continue
        ts = _parse_iso_ts(record.get("ts"))
        if ts is None or ts < start_dt or ts > end_dt:
            continue
        user_id = str(record.get("user_id") or "")
        if selected_users_set and user_id not in selected_users_set:
            continue
        nudge_id = str(record.get("nudge_id") or "")
        meta = enqueue_meta.get(nudge_id)
        persona_id = str(meta.get("persona_id") if meta else "")
        if not persona_id:
            bundle = bundle_index.get((user_id, nudge_id))
            persona_id = str(bundle.get("persona_id") or "unknown") if bundle else "unknown"
        if selected_personas_set and persona_id not in selected_personas_set:
            continue
        cohort_value = _normalize_cohort(meta.get("cohort") if meta else None)
        if selected_cohorts_set and cohort_value not in selected_cohorts_set:
            continue

        day_key = ts.date()
        run_history_counter[(day_key, action_type)] = run_history_counter.get((day_key, action_type), 0) + 1
        persona_outcomes[(persona_id, action_type)] = persona_outcomes.get((persona_id, action_type), 0) + 1
        cohort_bucket = cohort_totals.setdefault(cohort_value, {"accept": 0, "dismiss": 0})
        if action_type == "accept":
            cohort_bucket["accept"] += 1
        elif action_type == "dismiss":
            cohort_bucket["dismiss"] += 1

        schedule_key = (user_id, persona_id, cohort_value)
        actions_by_schedule.setdefault(schedule_key, []).append({"date": day_key, "action": action_type})

    expected_rows: List[Dict[str, Any]] = []
    if start_date <= end_date:
        day_iter: List[date] = []
        cursor = start_date
        while cursor <= end_date:
            day_iter.append(cursor)
            cursor += timedelta(days=1)
        for user_id, config in ops_configs.items():
            if selected_users_set and user_id not in selected_users_set:
                continue
            for entry in config.get("entries", []):
                persona_id = str(entry.get("persona_id") or "unknown")
                if selected_personas_set and persona_id not in selected_personas_set:
                    continue
                cohort_value = _normalize_cohort(entry.get("cohort"))
                if selected_cohorts_set and cohort_value not in selected_cohorts_set:
                    continue
                weekdays_raw = entry.get("weekdays") if isinstance(entry.get("weekdays"), list) else list(range(7))
                weekdays = [int(val) % 7 for val in weekdays_raw]
                expected_runs = sum(1 for day in day_iter if day.weekday() in weekdays)
                schedule_actions = actions_by_schedule.get((user_id, persona_id, cohort_value), [])
                actual_attempts = sum(1 for item in schedule_actions if item["action"] in {"accept", "dismiss"})
                actual_accepts = sum(1 for item in schedule_actions if item["action"] == "accept")
                compliance = (actual_attempts / expected_runs) if expected_runs else None
                expected_rows.append(
                    {
                        "user_id": user_id,
                        "persona_id": persona_id,
                        "label": entry.get("label") or "—",
                        "cohort": cohort_value,
                        "expected_runs": expected_runs,
                        "actual_attempts": actual_attempts,
                        "actual_accepts": actual_accepts,
                        "compliance": compliance,
                    }
                )

    total_expected = sum(row["expected_runs"] for row in expected_rows)
    total_attempts = sum(row["actual_attempts"] for row in expected_rows)
    total_missed = max(total_expected - total_attempts, 0)

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Expected runs", str(total_expected))
    with metric_cols[1]:
        st.metric("Attempts recorded", str(total_attempts))
    with metric_cols[2]:
        compliance_pct = (total_attempts / total_expected * 100.0) if total_expected else 0.0
        st.metric("Compliance", f"{compliance_pct:.1f}%")

    run_history_data = [
        {"date": key[0], "action": key[1], "count": count}
        for key, count in sorted(run_history_counter.items())
    ]

    top_layout = st.columns(2)
    with top_layout[0]:
        st.markdown("#### Run History (accepted vs dismissed)")
        if run_history_data and alt is not None:
            chart = (
                alt.Chart(run_history_data)
                .mark_area(opacity=0.75)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("count:Q", stack="zero", title="Count"),
                    color=alt.Color("action:N", title="Action"),
                    tooltip=["date:T", "action:N", "count:Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        elif run_history_data:
            st.dataframe(run_history_data)
        else:
            st.info("No actions recorded for the selected period.")

    compliance_records = expected_rows
    with top_layout[1]:
        st.markdown("#### Schedule Compliance")
        if compliance_records and alt is not None and pd is not None:
            df = pd.DataFrame(compliance_records)
            table_df = df[[
                "user_id",
                "persona_id",
                "label",
                "cohort",
                "expected_runs",
                "actual_attempts",
                "actual_accepts",
                "compliance",
            ]].copy()
            table_df["compliance"] = table_df["compliance"].apply(
                lambda value: f"{value * 100:.1f}%" if isinstance(value, (int, float)) and value is not None else "—"
            )
            st.dataframe(table_df)

            donut_source = pd.DataFrame(
                [
                    {"status": "Completed", "count": total_attempts},
                    {"status": "Missed", "count": total_missed},
                ]
            )
            donut_chart = (
                alt.Chart(donut_source)
                .mark_arc(innerRadius=50)
                .encode(theta="count:Q", color="status:N", tooltip=["status:N", "count:Q"])
            )
            st.altair_chart(donut_chart, use_container_width=True)
        elif compliance_records:
            st.table(compliance_records)
        else:
            st.info("No schedules matched the current filters.")

    persona_outcomes_data = [
        {"persona_id": key[0], "action": key[1], "count": count}
        for key, count in persona_outcomes.items()
    ]

    cohort_rows = []
    for cohort_value, summary in cohort_totals.items():
        attempts = summary.get("accept", 0) + summary.get("dismiss", 0)
        helpful_rate = (summary.get("accept", 0) / attempts * 100.0) if attempts else 0.0
        cohort_rows.append(
            {
                "cohort": cohort_value,
                "accepts": summary.get("accept", 0),
                "dismisses": summary.get("dismiss", 0),
                "helpful_rate": helpful_rate,
            }
        )

    second_row = st.columns(2)
    with second_row[0]:
        st.markdown("#### Nudge Outcomes by Persona")
        if persona_outcomes_data and alt is not None:
            chart = (
                alt.Chart(persona_outcomes_data)
                .mark_bar()
                .encode(
                    x=alt.X("count:Q", title="Count"),
                    y=alt.Y("persona_id:N", sort="-x", title="Persona"),
                    color="action:N",
                    tooltip=["persona_id:N", "action:N", "count:Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        elif persona_outcomes_data:
            st.dataframe(persona_outcomes_data)
        else:
            st.info("No persona activity recorded for the range.")

    with second_row[1]:
        st.markdown("#### Cohort Comparison")
        if cohort_rows and alt is not None:
            chart = (
                alt.Chart(cohort_rows)
                .mark_bar()
                .encode(
                    x=alt.X("cohort:N", title="Cohort"),
                    y=alt.Y("helpful_rate:Q", title="Helpful %"),
                    color="cohort:N",
                    tooltip=["cohort:N", "accepts:Q", "dismisses:Q", "helpful_rate:Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        elif cohort_rows:
            st.table(cohort_rows)
        else:
            st.info("No cohort data for the selected filters.")

    trait_rows = [
        {"persona_id": persona_id, "trait": trait_path, "count": count}
        for (persona_id, trait_path), count in sorted(trait_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    st.markdown("#### Top Traits Nudged (accepted bundles)")
    if trait_rows:
        top_rows = trait_rows[:15]
        if alt is not None:
            chart = (
                alt.Chart(top_rows)
                .mark_bar()
                .encode(
                    x=alt.X("count:Q", title="Count"),
                    y=alt.Y("trait:N", title="Trait", sort="-x"),
                    color="persona_id:N",
                    tooltip=["persona_id:N", "trait:N", "count:Q"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.table(top_rows)
    else:
        st.info("No accepted bundles matched the current filters.")

    export_cols = st.columns(3)

    def _to_csv(rows: List[Dict[str, Any]]) -> Optional[str]:
        if not rows:
            return None
        if pd is not None:
            return pd.DataFrame(rows).to_csv(index=False)
        buffer = io.StringIO()
        fieldnames = sorted({field for row in rows for field in row.keys()})
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    with export_cols[0]:
        csv_payload = _to_csv(compliance_records)
        if csv_payload:
            st.download_button(
                "Export Compliance CSV",
                data=csv_payload,
                file_name="ops_compliance.csv",
                mime="text/csv",
            )
    with export_cols[1]:
        csv_history = _to_csv(run_history_data)
        if csv_history:
            st.download_button(
                "Export History CSV",
                data=csv_history,
                file_name="ops_history.csv",
                mime="text/csv",
            )
    with export_cols[2]:
        csv_traits = _to_csv(trait_rows)
        if csv_traits:
            st.download_button(
                "Export Traits CSV",
                data=csv_traits,
                file_name="ops_traits.csv",
                mime="text/csv",
            )

def _render_audit_viewer(
    context: DevWriteContext,
    *,
    enabled: bool,
    flag_source: str,
) -> None:
    if not enabled:
        return

    st.markdown("### Audit Viewer")
    st.caption(
        "Inspect write-guarded logs and backups. Use rollbacks cautiously when writes are enabled."
    )

    wp_label = "dry-run" if context.write_protect else "live"
    st.caption(f"Flag source: {flag_source} · Writes: {wp_label}")

    tabs = st.tabs(["RR Baselines", "CReDNA", "Nudge Actions", "Feedback"])

    # RR Baselines -----------------------------------------------------------------
    rr_path = rr_change_log_path(REPO_ROOT)
    with tabs[0]:
        st.caption(f"Change log: {rr_path}")
        rr_limit = st.slider("Rows", min_value=10, max_value=300, value=100, key="rr_audit_limit")
        rr_entries = audit_utils.load_jsonl(rr_path, limit=rr_limit)
        if rr_entries:
            if pd is not None:
                st.dataframe(pd.DataFrame(rr_entries))
            else:
                st.json(rr_entries)
        else:
            st.info("No RR baseline changes recorded yet.")

        controls = st.columns(2)
        with controls[0]:
            if st.button("Mark encrypted", key="rr_audit_encrypt"):
                result = audit_utils.encrypt_log(rr_path, write_context=context)
                st.success(f"Marked encrypted at {result.get('timestamp')}")
        with controls[1]:
            if context.write_protect:
                st.caption("Write-protect ON — rollback disabled.")
            elif st.button("Rollback last change", key="rr_audit_rollback"):
                result = audit_utils.rollback_last_change(
                    "rr_baselines",
                    repo_root=REPO_ROOT,
                    write_context=context,
                )
                if result.get("ok"):
                    st.success(f"Restored from {result.get('restored_from')}")
                else:
                    st.error(result.get("error", "Rollback failed."))

    # CReDNA -----------------------------------------------------------------------
    credna_path = credna_store.AUDIT_LOG_PATH
    with tabs[1]:
        st.caption(f"CReDNA audit log: {credna_path}")
        credna_limit = st.slider("Rows", min_value=10, max_value=300, value=150, key="credna_audit_limit")
        credna_entries = audit_utils.load_jsonl(credna_path, limit=credna_limit)
        if credna_entries:
            if pd is not None:
                st.dataframe(pd.DataFrame(credna_entries))
            else:
                st.json(credna_entries)
        else:
            st.info("CReDNA log empty.")

        controls = st.columns(2)
        with controls[0]:
            if st.button("Mark encrypted", key="credna_audit_encrypt"):
                result = audit_utils.encrypt_log(credna_path, write_context=context)
                st.success(f"Marked encrypted at {result.get('timestamp')}")
        with controls[1]:
            if context.write_protect:
                st.caption("Write-protect ON — rollback disabled.")
            elif st.button("Rollback last change", key="credna_audit_rollback"):
                result = audit_utils.rollback_last_change(
                    "credna_registry",
                    repo_root=REPO_ROOT,
                    write_context=context,
                )
                if result.get("ok"):
                    st.success(f"Restored from {result.get('restored_from')}")
                else:
                    st.error(result.get("error", "Rollback failed."))

    # Nudge actions ----------------------------------------------------------------
    action_path = nudge_store.get_action_log_path()
    with tabs[2]:
        st.caption(f"Action log: {action_path}")
        filter_cols = st.columns(3)
        with filter_cols[0]:
            action_limit = st.slider("Rows", min_value=20, max_value=400, value=200, key="nudge_actions_limit")
        with filter_cols[1]:
            user_filter = st.text_input("Filter by user id", key="nudge_actions_user")
        with filter_cols[2]:
            persona_filter = st.text_input("Filter by persona", key="nudge_actions_persona")

        action_entries = audit_utils.load_jsonl(action_path, limit=action_limit)
        if user_filter:
            action_entries = [row for row in action_entries if str(row.get("user_id", "")).startswith(user_filter)]
        if persona_filter:
            action_entries = [row for row in action_entries if str(row.get("persona_id", "")).startswith(persona_filter)]

        if action_entries:
            if pd is not None:
                st.dataframe(pd.DataFrame(action_entries))
            else:
                st.json(action_entries)
        else:
            st.info("No log entries for the current filter.")

        rollback_cols = st.columns(2)
        with rollback_cols[0]:
            if st.button("Mark encrypted", key="nudge_actions_encrypt"):
                result = audit_utils.encrypt_log(action_path, write_context=context)
                st.success(f"Marked encrypted at {result.get('timestamp')}")
        with rollback_cols[1]:
            if context.write_protect:
                st.caption("Write-protect ON — rollback disabled.")
            else:
                inbox_user = st.text_input("Rollback inbox for user", key="nudge_actions_user_target")
                if st.button("Rollback last inbox change", key="nudge_actions_rollback"):
                    user_id = inbox_user.strip()
                    if not user_id:
                        st.warning("Enter a user id for rollback.")
                    else:
                        result = audit_utils.rollback_last_change(
                            "nudge_inbox",
                            repo_root=REPO_ROOT,
                            identifier=user_id,
                            write_context=context,
                        )
                        if result.get("ok"):
                            st.success(f"Restored inbox for {user_id} from {result.get('restored_from')}")
                        else:
                            st.error(result.get("error", "Rollback failed."))

    # Feedback ---------------------------------------------------------------------
    feedback_path = nudge_store.get_feedback_log_path()
    with tabs[3]:
        st.caption(f"Feedback log: {feedback_path}")
        feedback_limit = st.slider("Rows", min_value=20, max_value=400, value=200, key="feedback_audit_limit")
        feedback_entries = audit_utils.load_jsonl(feedback_path, limit=feedback_limit)
        if feedback_entries:
            if pd is not None:
                st.dataframe(pd.DataFrame(feedback_entries))
            else:
                st.json(feedback_entries)
        else:
            st.info("Feedback log empty.")

        if st.button("Mark encrypted", key="feedback_audit_encrypt"):
            result = audit_utils.encrypt_log(feedback_path, write_context=context)
            st.success(f"Marked encrypted at {result.get('timestamp')}")

def _show_holistic_scheduler(context: DevWriteContext) -> None:
    st.subheader("Holistic Scheduler")

    flash = st.session_state.pop("_scheduler_flash", None)
    if isinstance(flash, dict):
        message = flash.get("message") or ""
        if flash.get("kind") == "success":
            st.success(message)
        else:
            st.error(message)

    cadence_labels = ["Off", "15m", "Hourly", "Daily"]
    label_to_code = {"Off": "off", "15m": "15m", "Hourly": "hourly", "Daily": "daily"}
    code_to_label = {code: label for label, code in label_to_code.items()}

    prefs = load_scheduler_prefs()
    scheduler_prefs = prefs.get("holistic_scheduler") if isinstance(prefs.get("holistic_scheduler"), dict) else {}
    current_code = scheduler_prefs.get("cadence", "off")
    current_label = code_to_label.get(current_code, "Off")

    select_col, save_col = st.columns([3, 1])
    with select_col:
        selected_label = st.selectbox(
            "Cadence",
            cadence_labels,
            index=cadence_labels.index(current_label) if current_label in cadence_labels else 0,
        )
    with save_col:
        if st.button("Save cadence"):
            try:
                next_prefs = dict(prefs)
                next_prefs["holistic_scheduler"] = {
                    "cadence": label_to_code[selected_label],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                save_scheduler_prefs(next_prefs, context)
            except PermissionError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive guard
                st.error(f"Unable to save cadence: {exc}")
            else:
                st.success("Cadence updated.")
                prefs = next_prefs
                scheduler_prefs = next_prefs["holistic_scheduler"]
                current_label = selected_label

    history = load_run_history(context)
    last_entry = st.session_state.get("_scheduler_last")
    if not isinstance(last_entry, dict) and history:
        last_entry = history[0]

    run_disabled = context.write_protect
    if run_disabled:
        st.info("Write-protect ON — run now is disabled.")

    if st.button("Run now", disabled=run_disabled):
        if context.write_protect:
            st.info("Write-protect ON — skipping scheduler probe.")
        else:
            snapshot_note = f"Scheduler run now ({selected_label})"
            snapshot_result = snapshot_utils.collect_snapshot(
                context,
                in_memory=context.write_protect,
                persona_imports=PERSONA_IMPORTS,
                note=snapshot_note,
            )
            if not snapshot_result.get("ok"):
                st.error(snapshot_result.get("error") or "Unable to capture snapshot.")
            else:
                snapshot_id = snapshot_result.get("snapshot_id")
                if snapshot_id:
                    st.session_state["_latest_snapshot_id"] = snapshot_id
                result_flag, duration_ms, notes = run_now_probe()
                entry = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "trigger": "manual",
                    "cadence": label_to_code.get(selected_label, "manual"),
                    "result": result_flag,
                    "duration_ms": duration_ms,
                    "notes": notes,
                    "snapshot_id": snapshot_result.get("snapshot_id"),
                    "snapshot_note": snapshot_result.get("note"),
                    "snapshot_path": snapshot_result.get("path"),
                    "snapshot_storage": "memory" if snapshot_result.get("path") is None else "disk",
                }
                try:
                    append_run_history(entry, context, snapshot=snapshot_result)
                except PermissionError as exc:
                    st.session_state["_scheduler_flash"] = {"kind": "error", "message": str(exc)}
                except Exception as exc:  # pragma: no cover - advisory logging
                    st.session_state["_scheduler_flash"] = {
                        "kind": "error",
                        "message": f"Unable to append scheduler log: {exc}",
                    }
                else:
                    st.session_state["_scheduler_last"] = entry
                    message = "Scheduler probe succeeded." if result_flag == "ok" else "Scheduler probe encountered issues."
                    detail = f" ({notes})" if notes else ""
                    st.session_state["_scheduler_flash"] = {
                        "kind": "success" if result_flag == "ok" else "error",
                        "message": message + detail,
                    }
                _safe_rerun()
                return

    if isinstance(last_entry, dict):
        duration = last_entry.get("duration_ms")
        duration_text = f"{(duration or 0) / 1000:.2f}s" if isinstance(duration, (int, float)) else "—"
        ts = last_entry.get("ts") or last_entry.get("started_at") or "—"
        result_flag = last_entry.get("result") or ("ok" if last_entry.get("ok") else "fail")
        st.markdown(
            f"**Last run:** {ts} · Duration {duration_text} · {result_flag.upper()}"
        )
        notes = last_entry.get("notes") or ""
        if notes:
            st.caption(f"Notes: {notes}")
        snapshot_id = last_entry.get("snapshot_id")
        if snapshot_id:
            snapshot_note = last_entry.get("snapshot_note") or ""
            st.caption(f"Snapshot: {snapshot_id}")
            if snapshot_note:
                st.caption(f"Snapshot note: {snapshot_note}")
            snapshot_bytes = snapshot_utils.get_snapshot_bytes(snapshot_id)
            if snapshot_bytes:
                download_name = f"devexp_snapshot_{snapshot_id}.zip"
                st.download_button(
                    "Download snapshot",
                    data=snapshot_bytes,
                    file_name=download_name,
                    mime="application/zip",
                    key=f"scheduler_last_snapshot_{snapshot_id}",
                )
            else:
                st.warning("Snapshot bundle unavailable.")
    else:
        st.markdown("**Last run:** –")

    st.markdown("### Run history")
    if not history:
        st.info("No scheduler runs logged yet.")
        return

    page_key = "_scheduler_history_page"
    page_size = 10
    total_pages = max(1, (len(history) + page_size - 1) // page_size)
    current_page = int(st.session_state.get(page_key, 0))
    current_page = max(0, min(current_page, total_pages - 1))

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("◀ Prev", disabled=current_page <= 0, key="scheduler_prev"):
            st.session_state[page_key] = current_page - 1
            _safe_rerun()
    with col_info:
        col_info.markdown(f"Page {current_page + 1} of {total_pages}")
    with col_next:
        if st.button("Next ▶", disabled=current_page >= total_pages - 1, key="scheduler_next"):
            st.session_state[page_key] = current_page + 1
            _safe_rerun()

    start = current_page * page_size
    end = start + page_size
    rows: List[Dict[str, Any]] = []
    visible_entries: List[Dict[str, Any]] = []
    for entry in history[start:end]:
        ts = entry.get("ts") or entry.get("started_at") or ""
        trigger = entry.get("trigger") or "auto"
        cadence = entry.get("cadence") or "—"
        result_flag = entry.get("result") or ("ok" if entry.get("ok") else "fail")
        duration = entry.get("duration_ms")
        notes = entry.get("notes") or ""
        snapshot_id = entry.get("snapshot_id") or ""
        snapshot_note = entry.get("snapshot_note") or ""
        rows.append(
            {
                "ts": ts,
                "trigger": trigger,
                "cadence": cadence,
                "result": result_flag,
                "duration_ms": duration,
                "notes": notes,
                "snapshot_id": snapshot_id,
                "snapshot_note": snapshot_note,
            }
        )
        visible_entries.append(entry)

    if pd:
        st.dataframe(pd.DataFrame(rows))  # type: ignore[arg-type]
    else:
        st.table(rows)

    st.caption(f"Showing {len(rows)} of {len(history)} runs")

    st.markdown("#### Snapshot downloads")
    any_snapshot = False
    seen_snapshots: Set[str] = set()
    for idx, entry in enumerate(visible_entries):
        snapshot_id = entry.get("snapshot_id")
        if not snapshot_id or snapshot_id in seen_snapshots:
            continue
        seen_snapshots.add(snapshot_id)
        any_snapshot = True
        cols = st.columns([3, 3, 1])
        with cols[0]:
            st.write(f"Snapshot {snapshot_id}")
        with cols[1]:
            snapshot_note = entry.get("snapshot_note") or ""
            if snapshot_note:
                st.caption(f"Note: {snapshot_note}")
            else:
                st.caption("Note: —")
        with cols[2]:
            snapshot_bytes = snapshot_utils.get_snapshot_bytes(snapshot_id)
            if snapshot_bytes:
                st.download_button(
                    "Download",
                    data=snapshot_bytes,
                    file_name=f"devexp_snapshot_{snapshot_id}.zip",
                    mime="application/zip",
                    key=f"scheduler_history_snapshot_{snapshot_id}_{idx}",
                )
            else:
                st.button(
                    "Download",
                    disabled=True,
                    key=f"scheduler_history_snapshot_disabled_{snapshot_id}_{idx}",
                )
    if not any_snapshot:
        st.caption("No snapshots captured for the selected page.")

    if not context.write_protect:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["ts", "trigger", "cadence", "result", "duration_ms", "notes", "snapshot_id"])
        for entry in history:
            ts = entry.get("ts") or entry.get("started_at") or ""
            trigger = entry.get("trigger") or "auto"
            cadence = entry.get("cadence") or "—"
            result_flag = entry.get("result") or ("ok" if entry.get("ok") else "fail")
            duration = entry.get("duration_ms")
            notes = entry.get("notes") or ""
            writer.writerow([
                ts,
                trigger,
                cadence,
                result_flag,
                duration,
                notes,
                entry.get("snapshot_id") or "",
            ])
        st.download_button(
            "Download CSV",
            data=csv_buffer.getvalue(),
            file_name="scheduler_history.csv",
            mime="text/csv",
        )


def _show_soft_import_settings(context: DevWriteContext) -> None:
    st.subheader("Soft Import & Analytics Flags")

    raw_photo_strict = os.getenv("PHOTO_IMPORT_STRICT", "false").strip().lower() in DEV_TRUE_SET
    raw_soft_assist = os.getenv("ENABLE_SOFT_IMPORT_ASSIST", "true").strip().lower() in DEV_TRUE_SET
    raw_timeout = int(os.getenv("SOFT_IMPORT_ASSIST_TIMEOUT_MS", "60000") or 60000)
    raw_switch_logs = os.getenv("ANALYTICS_ENABLE_SWITCH_LOGS", "false").strip().lower() in DEV_TRUE_SET

    st.markdown(
        f"- `PHOTO_IMPORT_STRICT`: **{raw_photo_strict}**\n"
        f"- `ENABLE_SOFT_IMPORT_ASSIST`: **{raw_soft_assist}**\n"
        f"- `SOFT_IMPORT_ASSIST_TIMEOUT_MS`: **{raw_timeout}**\n"
        f"- `ANALYTICS_ENABLE_SWITCH_LOGS`: **{raw_switch_logs}**"
    )

    disabled = context.write_protect
    if disabled:
        st.warning("Write-protect ON — toggles disabled. Set `WRITE_PROTECT=false` to edit.")

    photo_strict = _render_env_bool("PHOTO_IMPORT_STRICT", raw_photo_strict, disabled=disabled)
    soft_assist = _render_env_bool("ENABLE_SOFT_IMPORT_ASSIST", raw_soft_assist, disabled=disabled)
    timeout_ms = _render_env_int("SOFT_IMPORT_ASSIST_TIMEOUT_MS", raw_timeout, disabled=disabled, min_value=1000)
    switch_logs = _render_env_bool("ANALYTICS_ENABLE_SWITCH_LOGS", raw_switch_logs, disabled=disabled)

    if st.button("Save soft-import & analytics flags", disabled=disabled):
        try:
            context.write_env_var("PHOTO_IMPORT_STRICT", "true" if photo_strict else "false")
            context.write_env_var("ENABLE_SOFT_IMPORT_ASSIST", "true" if soft_assist else "false")
            context.write_env_var("SOFT_IMPORT_ASSIST_TIMEOUT_MS", str(timeout_ms))
            context.write_env_var("ANALYTICS_ENABLE_SWITCH_LOGS", "true" if switch_logs else "false")
        except PermissionError as exc:
            st.error(str(exc))
        else:
            st.success("Flags saved. Restart Core services to apply.")


def _handle_user_management_action(
    action: str, user_id: str, preset: str, context: DevWriteContext
) -> None:
    error = _validate_user_id(user_id.strip())
    if error:
        st.error(error)
        return

    target_id = user_id.strip()

    try:
        if action == "seed":
            preview = _build_seed_preview(target_id, preset, context)
        elif action == "reset":
            preview = _build_reset_preview(target_id, context)
        elif action == "delete":
            preview = _build_delete_preview(target_id, context)
        else:
            st.error(f"Unsupported action '{action}'.")
            return
    except ValueError as exc:
        st.error(str(exc))
        return

    st.session_state[USER_ACTION_STATE_KEY] = preview
    if action == "delete":
        st.session_state[USER_DELETE_CONFIRM_KEY] = ""
    else:
        st.session_state.pop(USER_DELETE_CONFIRM_KEY, None)


def _render_user_action_modal(context: DevWriteContext) -> None:
    pending = st.session_state.get(USER_ACTION_STATE_KEY)
    if not isinstance(pending, dict):
        return

    action = pending.get("action", "")
    titles = {
        "seed": "Confirm seeding demo user",
        "reset": "Confirm reset",
        "delete": "Confirm hard delete",
    }
    title = titles.get(action, "Confirm action")

    container = st.container()
    with container:
        st.markdown(f"### {title}")
        st.markdown(f"**User:** `{pending.get('user_id', '')}`")

        steps = pending.get("steps") or []
        if steps:
            st.markdown("**Planned steps**")
            for step in steps:
                st.write(f"- {step}")

        display_paths = pending.get("display_paths") or []
        if display_paths:
            st.markdown("**Affected paths**")
            for path in display_paths:
                st.write(f"- `{path}`")

        if context.write_protect:
            st.info("Write-protect ON — confirming runs a dry run only.")

        confirm_disabled = False
        if action == "delete":
            default_text = st.session_state.get(USER_DELETE_CONFIRM_KEY, "")
            confirm_text = st.text_input(
                "Type the user id to confirm",
                value=default_text,
                key="user_mgmt_delete_confirm_input",
            )
            st.session_state[USER_DELETE_CONFIRM_KEY] = confirm_text
            confirm_disabled = confirm_text.strip() != pending.get("user_id")
            if confirm_disabled:
                st.caption("Enter the user id exactly to enable deletion.")

        confirm_labels = {
            "seed": "Seed user",
            "reset": "Reset user",
            "delete": "Delete user",
        }
        confirm_label = confirm_labels.get(action, "Confirm")

        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button(
                confirm_label,
                type="primary",
                disabled=confirm_disabled,
                key="user_mgmt_confirm",
            ):
                try:
                    result = _execute_user_action(pending, context)
                except Exception as exc:  # pragma: no cover - defensive guard for UI
                    result = {
                        "action": action,
                        "user_id": pending.get("user_id"),
                        "ok": False,
                        "dry_run": False,
                        "message": f"{type(exc).__name__}: {exc}",
                        "paths": pending.get("display_paths", []),
                    }
                st.session_state[USER_RESULT_STATE_KEY] = result
                if result.get("ok"):
                    st.session_state.pop(USER_ACTION_STATE_KEY, None)
                    st.session_state.pop(USER_DELETE_CONFIRM_KEY, None)
                    _safe_rerun()
                    return

        with col_cancel:
            if st.button("Cancel", key="user_mgmt_cancel"):
                st.session_state.pop(USER_ACTION_STATE_KEY, None)
                st.session_state.pop(USER_DELETE_CONFIRM_KEY, None)
                _safe_rerun()
                return


def _render_user_action_result() -> None:
    result = st.session_state.get(USER_RESULT_STATE_KEY)
    if not isinstance(result, dict):
        return

    message = result.get("message") or "Action completed."
    if not result.get("ok"):
        st.error(message)
    elif result.get("dry_run"):
        st.info(f"Dry run — {message}")
    else:
        st.success(message)

    paths = result.get("paths") or []
    if paths:
        st.markdown("**Affected paths**")
        for path in paths:
            st.write(f"- `{path}`")


def _show_user_management(context: DevWriteContext) -> None:
    st.subheader("User Management")
    st.caption(
        "Seed demo users, reset volatile artefacts, or delete dev-only personas."
    )

    preset_options = list(PRESET_BUNDLES.keys())
    if not preset_options:
        st.warning("No preset bundles configured. Add entries to PRESET_BUNDLES.")
        return

    user_input = st.text_input("User id", key="user_mgmt_user_id")
    preset = st.selectbox("Preset bundle", preset_options, key="user_mgmt_preset")

    col_seed, col_reset, col_delete = st.columns(3)
    with col_seed:
        if st.button("Seed Demo User"):
            _handle_user_management_action("seed", user_input, preset, context)
    with col_reset:
        if st.button("Reset User"):
            _handle_user_management_action("reset", user_input, preset, context)
    with col_delete:
        if st.button("Hard Delete"):
            _handle_user_management_action("delete", user_input, preset, context)

    _render_user_action_modal(context)
    _render_user_action_result()



def _render_step_timeline(steps: List[Dict[str, Any]]) -> None:
    for step in steps:
        step_id = step.get("id") or step.get("name") or "step"
        label = DIAG_STEP_LABELS.get(step_id, step_id.replace("_", " "))
        ok = bool(step.get("ok"))
        warn = bool(step.get("warn"))
        if warn and ok:
            icon = "🛈"
        elif warn:
            icon = "⚠️"
        else:
            icon = "✅" if ok else "❌"
        elapsed = step.get("ms") if isinstance(step.get("ms"), (int, float)) else step.get("elapsed_ms")
        timing = f"{elapsed} ms" if isinstance(elapsed, (int, float)) else "–"
        http_status = step.get("http") or step.get("status")
        status_suffix = f" · HTTP {http_status}" if http_status else ""
        st.write(f"{icon} {label} · {timing}{status_suffix}")
        detail = step.get("detail") or step.get("error") or step.get("body") or ""
        if warn and detail:
            st.info(str(detail))
        elif ok and detail:
            st.caption(str(detail))
        elif not ok and detail:
            with st.expander(f"{label} details", expanded=False):
                st.code(str(detail))


def _show_diagnostics(context: DevWriteContext) -> None:
    audit_enabled, audit_source = get_flag_bool("AUDIT_VIEWER_ENABLED", True)
    if audit_enabled:
        loop_tab, audit_tab = st.tabs(["Loop Test", "Audit Viewer"])
        loop_container = loop_tab
    else:
        loop_container = st.container()
        audit_tab = None
    with loop_container:
        st.subheader("Data-Cycle Loop Test")
        target_snapshot_id = st.session_state.get("_snapshot_query_target")
        restore_config: Optional[Dict[str, Any]] = st.session_state.get("_snapshot_restore_config")

        if target_snapshot_id and st.session_state.get("_snapshot_restore_id") != target_snapshot_id:
            meta = snapshot_utils.get_snapshot_meta(target_snapshot_id)
            loop_meta = meta.get("loop_test") if isinstance(meta, dict) else None
            config_payload = loop_meta.get("config") if isinstance(loop_meta, dict) else None
            if isinstance(config_payload, dict):
                restore_config = dict(config_payload)
                st.session_state["_snapshot_restore_id"] = target_snapshot_id
                st.session_state["_snapshot_restore_config"] = restore_config
                restored_user = str(restore_config.get("user_id", "")).strip()
                if restored_user:
                    st.session_state.pop("looptest_user_id_input", None)
                    _set_loop_user_id(restored_user, defer_rerun=True)
            else:
                st.session_state.pop("_snapshot_restore_config", None)
                st.session_state.pop("_snapshot_restore_id", None)
                restore_config = None
        elif not target_snapshot_id:
            st.session_state.pop("_snapshot_restore_config", None)
            st.session_state.pop("_snapshot_restore_id", None)
            restore_config = None

        if target_snapshot_id and restore_config is None:
            st.warning(
                f"Snapshot `{target_snapshot_id}` does not contain loop-test configuration metadata."
            )

        default_user, default_user_source = get_flag_str("DEV_LOOPTEST_USER_ID", "devexp_test")
        default_user = default_user.strip() or "devexp_test"
        loop_user_default = _get_loop_user_id()
        input_value = st.text_input(
            "Loop-test user id",
            value=loop_user_default,
            key="looptest_user_id_input",
            on_change=lambda: _set_loop_user_id(st.session_state.get("looptest_user_id_input", "")),
        )
        _set_loop_user_id(input_value)
        effective_user = _get_loop_user_id()
        if not st.session_state.get("_loop_user_id"):
            st.caption(
                f"Using default: {default_user} ({default_user_source})"
            )

        def _run_loop_with_snapshot(
            note_label: str,
            *,
            config_override: Optional[Mapping[str, Any]] = None,
            source_snapshot_id: Optional[str] = None,
        ) -> None:
            loop_config = build_loop_config(effective_user, overrides=config_override)
            snapshot_note = f"{note_label} · user={loop_config['user_id']}"
            snapshot_result = snapshot_utils.collect_snapshot(
                context,
                in_memory=context.write_protect,
                persona_imports=PERSONA_IMPORTS,
                note=snapshot_note,
                extra_meta={"loop_test": {"config": loop_config}},
            )
            if not snapshot_result.get("ok"):
                st.error(snapshot_result.get("error") or "Unable to capture snapshot.")
                return
            snapshot_id = snapshot_result.get("snapshot_id")
            if snapshot_id:
                st.session_state["_latest_snapshot_id"] = snapshot_id
            with st.spinner("Running data-cycle loop..."):
                result = run_loop_test(context, config=loop_config)
            result["snapshot_id"] = snapshot_result.get("snapshot_id")
            result["snapshot_note"] = snapshot_result.get("note")
            result["snapshot_path"] = snapshot_result.get("path")
            st.session_state.pop("looptest_user_id_input", None)
            _set_loop_user_id(loop_config["user_id"], defer_rerun=True)
            st.session_state["_diagnostics_last_snapshot"] = snapshot_result
            if source_snapshot_id:
                result["replayed_from_snapshot"] = source_snapshot_id
            st.session_state["_diagnostics_last"] = result

        restore_id = st.session_state.get("_snapshot_restore_id") if restore_config else None
        if restore_config and restore_id:
            st.success(f"Replayed from snapshot `{restore_id}` — endpoints & timeouts restored.")
            if st.button("Clear restored config", key="clear_restore_config"):
                st.session_state.pop("_snapshot_restore_config", None)
                st.session_state.pop("_snapshot_restore_id", None)
                st.session_state.pop("_snapshot_query_target", None)
                _safe_rerun()
                return
            loop_cols = st.columns(3)
            with loop_cols[0]:
                if st.button("Run (current config)"):
                    _run_loop_with_snapshot("Loop test run")
            with loop_cols[1]:
                if st.button("Run (restored config)"):
                    _run_loop_with_snapshot(
                        f"Loop test run [restored {restore_id}]",
                        config_override=restore_config,
                        source_snapshot_id=restore_id,
                    )
            with loop_cols[2]:
                if st.button("Snapshot + Run loop test"):
                    _run_loop_with_snapshot("Snapshot loop test")
        else:
            loop_cols = st.columns(2)
            with loop_cols[0]:
                if st.button("Run loop test"):
                    _run_loop_with_snapshot("Loop test run")
            with loop_cols[1]:
                if st.button("Snapshot + Run loop test"):
                    _run_loop_with_snapshot("Snapshot loop test")

        result = st.session_state.get("_diagnostics_last")
        if isinstance(result, dict):
            outcome = result.get("result") or ("ok" if result.get("ok") else "fail")
            total_ms = result.get("total_ms")
            total_text = f"{total_ms} ms" if isinstance(total_ms, (int, float)) else "—"
            st.markdown(f"**Last run:** {outcome.upper()} · {total_text}")
            started = result.get("started_at")
            ended = result.get("ended_at")
            if started or ended:
                st.caption(f"Started {started or '–'} · Ended {ended or '–'}")
            config_used = result.get("config")
            if isinstance(config_used, dict):
                with st.expander("Loop configuration", expanded=False):
                    st.json(config_used)
            steps = result.get("steps") if isinstance(result.get("steps"), list) else []
            _render_step_timeline(steps)
            snapshot_id = result.get("snapshot_id")
            if snapshot_id:
                snapshot_note = result.get("snapshot_note") or ""
                st.caption(f"Snapshot: {snapshot_id}")
                if snapshot_note:
                    st.caption(f"Snapshot note: {snapshot_note}")
                replay_ref = result.get("replayed_from_snapshot")
                if replay_ref:
                    st.caption(f"Replayed from: {replay_ref}")
                snapshot_bytes = snapshot_utils.get_snapshot_bytes(snapshot_id)
                if snapshot_bytes:
                    st.download_button(
                        "Download loop snapshot",
                        data=snapshot_bytes,
                        file_name=f"devexp_snapshot_{snapshot_id}.zip",
                        mime="application/zip",
                        key=f"loop_snapshot_download_{snapshot_id}",
                    )
                else:
                    st.warning("Loop snapshot bundle unavailable.")
        else:
            st.info("Run the loop test to capture Explorer ↔ UCN/RR ↔ Core connectivity.")

        if st.button("Run quick checks", key="run_quick_checks_button"):
            summary = run_prompt_source_checks()
            st.session_state["_diagnostics_quick_checks"] = summary

        quick_summary = st.session_state.get("_diagnostics_quick_checks")
        missing_detected = False
        if isinstance(quick_summary, dict) and quick_summary:
            rows: List[Dict[str, str]] = []
            for persona_id, data in quick_summary.items():
                used = str(data.get("used") or "missing")
                if used == "missing":
                    missing_detected = True
                rows.append(
                    {
                        "persona": persona_id,
                        "used": used,
                        "system_path": str(data.get("system_path") or "—"),
                        "opening_path": str(data.get("opening_path") or "—"),
                    }
                )

            if pd:
                st.dataframe(pd.DataFrame(rows))  # type: ignore[arg-type]
            else:
                st.table(rows)

        if missing_detected:
            st.info("Some personas are missing prompt assets; they are marked as 'missing'.")

        st.markdown("---")
        st.subheader("Recent Core Errors")
        error_result = fetch_core_errors(CORE_BASE)
        if not error_result.get("ok"):
            reason = error_result.get("reason") or "unknown"
            status = error_result.get("status")
            if status == 404:
                st.info("Core does not expose `/ui/debug/errors` yet. Skipping error feed.")
            else:
                st.info(f"Unable to load error feed: {reason}")
        else:
            payload = error_result.get("payload")
            if isinstance(payload, dict):
                entries = payload.get("items") if isinstance(payload.get("items"), list) else payload.get("entries")
            else:
                entries = payload

            if isinstance(entries, list) and entries:
                for idx, entry in enumerate(entries[:20]):
                    header = entry.get("message") if isinstance(entry, dict) else f"Entry {idx + 1}"
                    with st.expander(header or f"Entry {idx + 1}", expanded=False):
                        st.json(entry)
            else:
                st.caption("No recent error entries reported by Core.")

        _render_ingest_harness(context)

        st.markdown("---")
        render_ors_console(context, last_ingest=st.session_state.get("_ingest_last_result"))
        st.markdown("---")
        st.subheader("Collect Diagnostics")
        st.caption("Bundle the current Dev Explorer state and recent logs into a shareable snapshot.")

        option_defs = [
            ("status", "Status & env (redacted)"),
            ("prefs", "Dev system prefs"),
            ("rr_baselines", "RR demo baselines"),
            ("schema", "Schema draft & diff"),
            ("personas", "Persona registry snapshot"),
            ("logs", "Recent logs"),
            ("health", "Service health payloads"),
        ]

        option_cols = st.columns(3)
        snapshot_options: Dict[str, bool] = {}
        for idx, (opt_key, label) in enumerate(option_defs):
            col = option_cols[idx % len(option_cols)]
            snapshot_options[opt_key] = col.checkbox(
                label,
                value=snapshot_utils.DEFAULT_OPTIONS.get(opt_key, True),
                key=f"diag_opt_{opt_key}",
            )

        snapshot_note_value = st.text_input(
            "Snapshot note (optional)",
            key="diag_snapshot_note",
            help="Stored inside meta.json for later reference.",
        )

        include_large = st.checkbox(
            "Include large files (≤5MB each)",
            value=False,
            key="diag_opt_include_large",
            help="Adds larger artefacts when available; leave off for faster downloads.",
        )

        if st.button("Collect diagnostics", type="primary", key="collect_diag_snap"):
            with st.spinner("Collecting diagnostics snapshot…"):
                result = snapshot_utils.collect_snapshot(
                    context,
                    in_memory=context.write_protect,
                    options=snapshot_options,
                    include_large=include_large,
                    persona_imports=PERSONA_IMPORTS,
                    note=snapshot_note_value,
                )
            st.session_state["_diag_snapshot_result"] = result

        snapshot_result = st.session_state.get("_diag_snapshot_result")
        if isinstance(snapshot_result, dict):
            if snapshot_result.get("ok"):
                files = snapshot_result.get("summary", {}).get("files", []) if isinstance(snapshot_result.get("summary"), dict) else []
                warnings = snapshot_result.get("summary", {}).get("warnings", []) if isinstance(snapshot_result.get("summary"), dict) else []
                size_val = int(snapshot_result.get("size") or 0)
                st.success(
                    f"Snapshot ready — {len(files)} artefacts · {_format_bytes(size_val)}"
                )

                snapshot_id = snapshot_result.get("snapshot_id")
                if snapshot_id:
                    st.session_state["_latest_snapshot_id"] = snapshot_id
                    st.caption(f"Snapshot ID: `{snapshot_id}`")

                path_value = snapshot_result.get("path")
                if path_value:
                    st.caption(f"Saved to `{path_value}`")

                zip_bytes = snapshot_result.get("zip_bytes")
                download_name = Path(path_value).name if path_value else "devexp_snapshot.zip"
                if isinstance(zip_bytes, (bytes, bytearray)) and zip_bytes:
                    st.download_button(
                        "Download snapshot",
                        data=zip_bytes,
                        file_name=download_name,
                        mime="application/zip",
                        key="collect_diag_download",
                    )
                elif path_value:
                    try:
                        file_bytes = Path(path_value).read_bytes()
                    except Exception as exc:
                        st.warning(f"Unable to load snapshot for download: {exc}")
                    else:
                        st.download_button(
                            "Download snapshot",
                            data=file_bytes,
                            file_name=Path(path_value).name,
                            mime="application/zip",
                            key="collect_diag_download_fallback",
                        )

                if files:
                    display_rows = files
                    if pd:
                        st.dataframe(pd.DataFrame(display_rows))  # type: ignore[arg-type]
                    else:
                        st.table(display_rows)

                if warnings:
                    for warning in warnings:
                        st.warning(str(warning))

                meta_payload = snapshot_result.get("meta")
                if isinstance(meta_payload, dict):
                    note_val = meta_payload.get("note")
                    if note_val:
                        st.caption(f"Note: {note_val}")
                    with st.expander("Snapshot metadata"):
                        st.json(meta_payload)
            else:
                error_text = snapshot_result.get("error") or "Snapshot failed."
                st.error(error_text)

        st.markdown("---")
        st.subheader("Snapshot Manager")
        target_snapshot_id = st.session_state.get("_snapshot_query_target")
        if target_snapshot_id:
            st.info(f"Snapshot deep-link active: `{target_snapshot_id}`")
        snapshots = snapshot_utils.list_snapshots()
        if snapshots:
            table_rows = [
                {
                    "Snapshot ID": item["id"],
                    "Created": item["created_at"],
                    "Size": _format_bytes(int(item.get("size", 0))),
                    "Files": item.get("files", 0),
                    "Note": item.get("note", ""),
                    "Source": item.get("source", ""),
                }
                for item in snapshots
            ]
            if pd:
                st.dataframe(pd.DataFrame(table_rows))  # type: ignore[arg-type]
            else:
                st.table(table_rows)
        else:
            st.info("No snapshots on disk or in memory yet.")

        target_found = False
        for snapshot in snapshots:
            snapshot_id = snapshot.get("id")
            if not snapshot_id:
                continue
            expanded_flag = snapshot_id == target_snapshot_id
            if expanded_flag:
                target_found = True
            with st.expander(f"Snapshot {snapshot_id}", expanded=expanded_flag):
                meta = snapshot_utils.get_snapshot_meta(snapshot_id) or {}
                st.caption(f"Created: {snapshot.get('created_at') or meta.get('created_at', '–')}")
                note_val = meta.get("note") or snapshot.get("note")
                if note_val:
                    st.caption(f"Note: {note_val}")
                st.json(meta or {"message": "meta.json unavailable"})

                snapshot_bytes = snapshot_utils.get_snapshot_bytes(snapshot_id)
                if snapshot_bytes:
                    st.download_button(
                        "Download snapshot",
                        data=snapshot_bytes,
                        file_name=f"devexp_snapshot_{snapshot_id}.zip",
                        mime="application/zip",
                        key=f"snapshot_mgr_download_{snapshot_id}",
                    )
                else:
                    st.warning("Snapshot bytes unavailable for download.")

                if st.button(
                    "Restore loop config",
                    key=f"snapshot_restore_{snapshot_id}",
                ):
                    st.session_state["_snapshot_query_target"] = snapshot_id
                    st.session_state.pop("_snapshot_restore_id", None)
                    _safe_rerun()
                    return

                if not context.write_protect:
                    confirm_text = st.text_input(
                        f"Type {snapshot_id} to delete",
                        key=f"snapshot_delete_confirm_{snapshot_id}",
                    )
                    delete_disabled = confirm_text.strip() != snapshot_id
                    if st.button(
                        "Delete snapshot",
                        key=f"snapshot_delete_{snapshot_id}",
                        disabled=delete_disabled,
                    ):
                        try:
                            snapshot_utils.delete_snapshot(snapshot_id, context)
                        except PermissionError as exc:
                            st.error(str(exc))
                        except Exception as exc:
                            st.error(f"Unable to delete snapshot: {exc}")
                        else:
                            st.success("Snapshot deleted.")
                            _safe_rerun()
                            return
                else:
                    st.info("Write-protect ON — deletion disabled.")

        if target_snapshot_id and not target_found:
            st.warning(f"Snapshot `{target_snapshot_id}` not found in current storage.")

        control_cols = st.columns(2)
        with control_cols[0]:
            expire_days = st.number_input(
                "Expire older than N days",
                min_value=1,
                value=30,
                key="snapshot_expire_days",
            )
            if st.button(
                "Expire snapshots",
                disabled=context.write_protect,
                key="snapshot_expire_button",
            ):
                try:
                    removed = snapshot_utils.expire_snapshots(int(expire_days), context)
                except PermissionError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Unable to expire snapshots: {exc}")
                else:
                    if removed:
                        st.success(f"Expired {len(removed)} snapshot(s): {', '.join(removed)}")
                    else:
                        st.info("No snapshots expired.")
                    _safe_rerun()
                    return

        with control_cols[1]:
            max_keep = st.number_input(
                "Keep newest K snapshots",
                min_value=0,
                value=5,
                key="snapshot_trim_keep",
            )
            if st.button(
                "Trim snapshots",
                disabled=context.write_protect,
                key="snapshot_trim_button",
            ):
                try:
                    removed = snapshot_utils.trim_snapshots(int(max_keep), context)
                except PermissionError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Unable to trim snapshots: {exc}")
                else:
                    if removed:
                        st.success(f"Removed {len(removed)} snapshot(s): {', '.join(removed)}")
                    else:
                        st.info("No snapshots removed.")
                    _safe_rerun()
                    return

        if st.session_state.get("_deferred_rerun"):
            st.session_state["_deferred_rerun"] = False
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()
            return

    params = _get_nav_params()
    nav_param = params.get("nav")
    snapshot_param = params.get("snapshot")
    persona_param = params.get("persona")
    container_param = params.get("container")
    trait_param = params.get("trait")
    preview_param = params.get("preview")
    user_param = params.get("user")
    preview_flag = (
        str(preview_param).lower() in {"1", "true", "yes", "on"}
        if preview_param is not None
        else False
    )

    if audit_enabled and audit_tab is not None:
        with audit_tab:
            _render_audit_viewer(
                context,
                enabled=True,
                flag_source=audit_source,
            )

    signature = (
        nav_param,
        snapshot_param,
        persona_param,
        container_param,
        trait_param,
        preview_param,
        user_param,
    )

    if st.session_state.get("_devexp_query_signature") != signature:
        if nav_param:
            section_options = {
                "Coach Workshop",
                "Container Studio",
                "RR Baselines Lab",
                "System Settings",
                "User Management",
                "Diagnostics",
                "Developer Tools",
            }
            if nav_param in section_options:
                st.session_state["_nav_section"] = nav_param

        if snapshot_param:
            st.session_state.setdefault("_snapshot_query_target", snapshot_param)
            st.session_state.setdefault("_nav_section", "Diagnostics")

        if persona_param:
            st.session_state["_selected_persona_id"] = persona_param
            st.session_state["_persona_selected_id"] = persona_param

        if container_param:
            st.session_state[SELECTED_CONTAINER_KEY] = container_param
        if trait_param:
            st.session_state[SELECTED_TRAIT_KEY] = trait_param
        if preview_flag:
            st.session_state["_devexp_scroll_target"] = "head-coach-preview"
        if user_param:
            st.session_state.setdefault("_devexp_loop_user", user_param)

        st.session_state["_devexp_query_signature"] = signature

st.title("🛠️ Developer Explorer")
st.caption("Internal console for coach workshops, ops tuning, and diagnostics.")

quick_link_cols = st.columns(3)
with quick_link_cols[0]:
    st.markdown(f"[Open Core]({CORE_BASE})")
with quick_link_cols[1]:
    st.markdown(f"[Open React HC]({REACT_BASE})")
with quick_link_cols[2]:
    st.markdown(f"[Open CP++]({CPPP_BASE})")

_render_status_strip(DEV_WRITE_CONTEXT)

bootstrap_cols = st.columns([3, 1])
bootstrap_status = _bootstrap_info.get("ok")
bootstrap_path = _bootstrap_info.get("path")
bootstrap_index = _bootstrap_info.get("sys_path_index")

with bootstrap_cols[0]:
    if bootstrap_status:
        st.caption(
            f"Imports OK — ExplorerDev parent on sys.path[{bootstrap_index}]: {bootstrap_path}"
        )
    else:
        st.error(
            "Import bootstrap failed — ExplorerDev not on path. Run from repository root."
        )

with bootstrap_cols[1]:
    if st.button("Re-run import check", key="rerun_import_check"):
        info = ensure_explorerdev_on_path()
        st.session_state["_bootstrap_info"] = info
        st.experimental_rerun()

if "_bootstrap_info" in st.session_state:
    _bootstrap_info = st.session_state.pop("_bootstrap_info")

if WRITE_PROTECT:
    st.warning(
        "Write-protect ON — Dev Explorer persists artefacts under `data/dev_users/` and `persona_config/dev_overrides/`. Set `WRITE_PROTECT=false` to write to live paths."
    )
else:
    st.success("Write-protect OFF — changes apply directly to live storage. Proceed with caution.")

with st.sidebar:
    st.header("Navigation")
    credna_enabled, _ = get_flag_bool("CREDNA_ENABLED", True)

    # Streamlined 8-section navigation (added Analytics)
    section_options: List[str] = [
        "Coach Workshop",
    ]
    if credna_enabled:
        section_options.append("CReDNA Studio")
    section_options.extend(
        [
            "Container Studio",
            "RR Baselines Lab",
            "Observability",
            "Governance & Audit",
            "Analytics",
            "Developer Tools",
        ]
    )

    default_section = st.session_state.get("_nav_section", "Coach Workshop")
    if default_section not in section_options:
        default_section = "Coach Workshop"
    section = st.radio(
        "Choose a module",
        section_options,
        index=section_options.index(default_section),
        help="Pick a Dev Explorer module to inspect or stage changes.",
        key="_nav_section",
    )

    st.markdown("---")
    st.markdown(
        "**Streamlined Navigation (8 sections)**\n\n"
        "This sandbox affects dev services only. Keep the main Explorer focused on the user journey."
    )

if section == "Coach Workshop":
    _show_persona_registry(DEV_WRITE_CONTEXT)

elif section == "CReDNA Studio":
    render_credna_studio(DEV_WRITE_CONTEXT)

elif section == "Container Studio":
    render_container_studio(
        repo_root=REPO_ROOT,
        context=DEV_WRITE_CONTEXT,
        llm_config=LLM_CONFIG,
    )

elif section == "RR Baselines Lab":
    render_rr_baselines_lab(REPO_ROOT, DEV_WRITE_CONTEXT)

elif section == "Observability":
    # Import new observability tab
    try:
        from ExplorerDev.tabs.observability import render_observability_tab
        render_observability_tab(DEV_WRITE_CONTEXT)
    except ImportError as exc:
        st.error(f"Unable to load Observability tab: {exc}")
        st.info("Fallback: Use legacy Diagnostics view")
        _show_diagnostics(DEV_WRITE_CONTEXT)

elif section == "Governance & Audit":
    # Import new governance tab
    try:
        from ExplorerDev.tabs.governance import render_governance_tab
        render_governance_tab(DEV_WRITE_CONTEXT)
    except ImportError as exc:
        st.error(f"Unable to load Governance & Audit tab: {exc}")

elif section == "Analytics":
    # Import new analytics tab
    try:
        from ExplorerDev.tabs.analytics import render_analytics_tab
        render_analytics_tab(DEV_WRITE_CONTEXT)
    except ImportError as exc:
        st.error(f"Unable to load Analytics tab: {exc}")

elif section == "Developer Tools":
    render_dev_tools(context=DEV_WRITE_CONTEXT)

scroll_target = st.session_state.pop("_devexp_scroll_target", None)
if isinstance(scroll_target, str) and scroll_target:
    anchor_ref = json.dumps(scroll_target)
    st.markdown(
        "<script>"  # noqa: S702 - safe inline script for in-page scroll
        "try {"
        "  const el = document.getElementById(" + anchor_ref + ");"
        "  if (el) { el.scrollIntoView({behavior: 'smooth'}); }"
        "} catch (err) { console && console.warn && console.warn('scroll failed', err); }"
        "</script>",
        unsafe_allow_html=True,
    )

st.markdown("## CReDNA (Coach ReDNA) modules")
st.info(
    "Coach Internals (CReDNA) — coming soon. See the roadmap section ‘CReDNA (Coach ReDNA) — planned’ for details."
)
st.info(
    "CReDNA Proposals & Review — coming soon. See the roadmap section ‘CReDNA (Coach ReDNA) — planned’ for details."
)

st.markdown("---")
st.caption(
    "This Dev Explorer shell is safe to commit. Modules stay inactive until follow-up prompts add real wiring."
)
