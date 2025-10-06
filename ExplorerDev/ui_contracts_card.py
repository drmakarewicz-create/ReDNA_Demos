"""UI Contracts card — probes Head Coach shells for basic guarantees."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
import streamlit as st

DEFAULT_REACT_URL = os.getenv("HC_REACT_URL", "http://127.0.0.1:3000")
DEFAULT_STREAMLIT_URL = os.getenv("HC_STREAMLIT_URL", "http://127.0.0.1:8501")
CHECK_TIMEOUT = 5.0


@dataclass
class CheckResult:
    name: str
    outcome: str
    details: str = ""


def _fetch_json(url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        response = requests.get(url, timeout=CHECK_TIMEOUT)
    except requests.RequestException as exc:
        return None, str(exc)
    if response.status_code >= 400:
        return None, f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError as exc:
        return None, f"Invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "Unexpected payload type"
    return payload, None


def _check_status(url: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        response = requests.get(url, timeout=CHECK_TIMEOUT)
    except requests.RequestException as exc:
        return None, str(exc)
    return response.status_code, None


def _build_probe_url(base: str, *, include_format: bool = True) -> str:
    base = base.strip()
    if not base:
        return base

    parsed = urlparse(base)
    path = parsed.path or ""
    if not path.endswith('/'):
        path = path.rstrip('/')
    if not path.endswith('/'):
        path = f"{path}/"

    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if 'ui_debug' not in query_pairs:
        query_pairs['ui_debug'] = '1'
    if include_format:
        if 'format' not in query_pairs:
            query_pairs['format'] = 'json'
    else:
        query_pairs.pop('format', None)

    new_query = urlencode(query_pairs)
    rebuilt = parsed._replace(path=path, query=new_query)
    return urlunparse(rebuilt)


def _run_checks(endpoint: str) -> List[CheckResult]:
    debug_json_url = _build_probe_url(endpoint, include_format=True)
    overview, json_error = _fetch_json(debug_json_url)
    if overview is not None:
        return _checks_from_payload(overview)

    html_probe_url = _build_probe_url(endpoint, include_format=False)
    status, status_error = _check_status(html_probe_url)
    if status == 200:
        reason = json_error or "Debug JSON unavailable"
        return _warn_only_checks(reason)

    detail = status_error or (f"HTTP {status}" if status is not None else json_error or "No response from shell")
    return [CheckResult("Reachable", "UNREACHABLE", detail or "Probe failed")]


def _checks_from_payload(payload: Dict[str, Any]) -> List[CheckResult]:
    checks: List[CheckResult] = [CheckResult("Reachable", "PASS")]

    composer = payload.get("composer_rendered")
    if composer is True:
        checks.append(CheckResult("Composer anchored", "PASS"))
    elif composer is False:
        checks.append(CheckResult("Composer anchored", "FAIL", "composer_rendered reported false"))
    else:
        checks.append(CheckResult("Composer anchored", "WARN", "composer_rendered not reported"))

    persona = payload.get("active_persona")
    persona_key = None
    persona_label = None
    if isinstance(persona, dict):
        persona_key = persona.get("key") or persona.get("persona_key")
        persona_label = persona.get("label") or persona.get("persona_label")
    else:
        persona_key = payload.get("persona_key")
        persona_label = payload.get("persona_label")
    if persona_key and persona_label:
        checks.append(CheckResult("Persona switch", "PASS"))
    elif persona_key or persona_label:
        checks.append(CheckResult("Persona switch", "WARN", "Persona metadata incomplete"))
    else:
        checks.append(CheckResult("Persona switch", "WARN", "Persona metadata missing"))

    unabridged = payload.get("unabridged_anchor_ok")
    if unabridged is None:
        unabridged = payload.get("unabridged_anchor")
    if unabridged is True:
        checks.append(CheckResult("Unabridged link", "PASS"))
    elif unabridged is False:
        checks.append(CheckResult("Unabridged link", "FAIL", "Unabridged anchor missing"))
    else:
        checks.append(CheckResult("Unabridged link", "WARN", "Unabridged anchor not reported"))

    asks_visible = payload.get("asks_panel_visible")
    if asks_visible is None:
        asks_visible = payload.get("coach_asks") in {"visible", "empty"}
    if asks_visible is True:
        checks.append(CheckResult("Coach Asks panel", "PASS"))
    elif asks_visible is False:
        checks.append(CheckResult("Coach Asks panel", "FAIL", "Coach Asks panel hidden"))
    else:
        checks.append(CheckResult("Coach Asks panel", "WARN", "Coach Asks panel not reported"))

    overlay_ok = payload.get("overlay_ok")
    if overlay_ok is None:
        overlay_ok = payload.get("overlay_supported")
    if overlay_ok is True:
        checks.append(CheckResult("Debug overlay", "PASS"))
    elif overlay_ok is False:
        checks.append(CheckResult("Debug overlay", "FAIL", "Debug overlay disabled"))
    else:
        checks.append(CheckResult("Debug overlay", "WARN", "Overlay status not reported"))

    return checks


def _warn_only_checks(reason: Optional[str]) -> List[CheckResult]:
    message = reason or "Debug JSON not available"
    return [
        CheckResult("Reachable", "PASS"),
        CheckResult("Composer anchored", "WARN", message),
        CheckResult("Persona switch", "WARN", message),
        CheckResult("Unabridged link", "WARN", message),
        CheckResult("Coach Asks panel", "WARN", message),
        CheckResult("Debug overlay", "WARN", message),
    ]


def render_ui_contracts_card() -> None:
    st.subheader("UI Contracts — Head Coach Shells")
    st.caption(
        "Smoke tests for React (Track A) and Streamlit (Track B) shells. "
        "URLs are auto-normalised with `?ui_debug=1`; override as needed above."
    )

    react_url = st.text_input("React shell base", value=DEFAULT_REACT_URL)
    streamlit_url = st.text_input("Streamlit shell base", value=DEFAULT_STREAMLIT_URL)

    if st.button("Run checks", type="primary"):
        with st.spinner("Probing shells…"):
            time.sleep(0.1)  # let the spinner render
            results = {
                "React": _run_checks(react_url),
                "Streamlit": _run_checks(streamlit_url),
            }

        columns = st.columns(len(results))
        for (label, checks), column in zip(results.items(), columns):
            with column:
                st.markdown(f"### {label}")
                for check in checks:
                    badge = check.outcome
                    tone = {
                        "PASS": "✅",
                        "WARN": "⚠️",
                        "FAIL": "❌",
                        "UNREACHABLE": "🚫",
                    }.get(badge, "•")
                    st.write(f"{tone} **{check.name}** — {badge}")
                    if check.details:
                        st.caption(check.details)
        st.caption("Legend: ✅ PASS · ⚠️ WARN (not validated) · ❌ FAIL · 🚫 UNREACHABLE")
