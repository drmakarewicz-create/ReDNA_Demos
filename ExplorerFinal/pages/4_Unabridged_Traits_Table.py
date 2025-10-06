# ExplorerFinal/pages/4_Unabridged_Traits_Table.py
from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

import pandas as pd
import streamlit as st

from ui.nav import side_nav, render_top_nav
from ui.session import (
    get_user_id,
    render_user_banner,
    core_get_resolved_flat,
    core_get_last_holistic,
    load_trait_catalog,
)


st.set_page_config(page_title="Unabridged Traits — ReDNA Explorer", layout="wide")
side_nav(active="unabridged")
render_top_nav(active="unabridged")

st.markdown("<div id='unabridged'></div>", unsafe_allow_html=True)

st.title("Unabridged Traits")
render_user_banner()

user_id = get_user_id()
if not user_id:
    st.info("Pick an active user in Explorer to view their trait catalog.")
    st.stop()

resolved = core_get_resolved_flat(user_id)
resolved_rows = resolved.get("rows", []) if isinstance(resolved, dict) else []
resolved_map = {row.get("path"): row for row in resolved_rows if row.get("path")}

holistic_snapshot = core_get_last_holistic(user_id)
paths_map = holistic_snapshot.get("paths", {}) if isinstance(holistic_snapshot, dict) else {}
holistic_all = set(paths_map.get("all", []) or [])
holistic_implied = set(paths_map.get("implied", []) or [])
holistic_reasons = holistic_snapshot.get("implied_reasons", {}) if isinstance(holistic_snapshot, dict) else {}

catalog = load_trait_catalog()
records = []
implied_flags: list[bool] = []


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: Any) -> str:
    if text is None:
        return ""
    stringified = str(text)
    if not stringified:
        return ""
    return _HTML_TAG_RE.sub("", unescape(stringified)).strip()


def _format_value(value: Any) -> str:
    """Convert structured trait values into a friendly display string."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [part for part in (_format_value(item) for item in value) if part]
        return ", ".join(parts)
    if isinstance(value, dict):
        cleaned = {str(k): _format_value(v) for k, v in value.items()}
        try:
            return json.dumps(cleaned, sort_keys=True)
        except Exception:
            return _strip_html(cleaned)
    return _strip_html(str(value))


def _is_sensitive(meta: Any, row: Any) -> bool:
    sensitivity_meta = str((meta or {}).get("sensitivity") or "").lower()
    if sensitivity_meta in {"high", "restricted"}:
        return True
    if (meta or {}).get("sensitivity_flag"):
        return True
    if isinstance(row, dict):
        sensitivity_row = str(row.get("sensitivity") or "").lower()
        if sensitivity_row in {"high", "restricted"}:
            return True
        if row.get("sensitivity_flag"):
            return True
    return False

for path, meta in sorted(catalog.items()):
    clean_path = _strip_html(path)
    row = resolved_map.get(path)
    provenance = row.get("provenance") if row else {}
    reasons = row.get("reasons") if row else []
    choices = meta.get("choices") or meta.get("enum")
    if isinstance(choices, dict):
        choices_display = ", ".join(f"{k}: {v}" for k, v in choices.items())
    elif isinstance(choices, (list, tuple)):
        choices_display = ", ".join(str(c) for c in choices)
    else:
        choices_display = str(choices) if choices else ""

    notes = meta.get("instructions") or meta.get("notes") or meta.get("description") or meta.get("help") or ""

    if row:
        curiosity = row.get("curiosity")
        if curiosity is None and row.get("confidence") is not None:
            curiosity = round(100 - (row.get("confidence") or 0) * 100, 1)
        record_state = "resolved"
    else:
        curiosity = 100
        record_state = "pending"

    holistic_marker = "H" if row and path in holistic_all else ""
    implied_reason = holistic_reasons.get(path) if row else None
    implied_flag = bool(implied_reason or (row and path in holistic_implied))

    sensitive = _is_sensitive(meta, row)
    trait_label = f"🔒 {clean_path}" if sensitive else clean_path

    records.append({
        "Trait": trait_label,
        "State": record_state,
        "Value": _format_value(row.get("value")) if row else "",
        "UCN": row.get("ucn") if row else None,
        "RR": row.get("rr") if row else None,
        "Curiosity": curiosity,
        "Source": _strip_html((provenance or {}).get("source", "")) if row else "",
        "Actor": _strip_html((provenance or {}).get("from", "")) if row else "",
        "Reasons": ", ".join(_strip_html(reason) for reason in reasons if reason) if reasons else "",
        "Type": meta.get("type", ""),
        "Notes": _strip_html(row.get("notes", {}).get("summary")) if row and isinstance(row.get("notes"), dict) else _strip_html(notes),
        "Choices": _strip_html(choices_display),
        "Holistic": holistic_marker,
        "Implied reason": _strip_html(implied_reason) if implied_reason else "",
        "Governance": "🔒 Sensitive" if sensitive else "",
    })
    implied_flags.append(implied_flag)

for path, row in resolved_map.items():
    if path in catalog:
        continue
    provenance = row.get("provenance") or {}
    reasons = row.get("reasons") or []
    holistic_marker = "H" if path in holistic_all else ""
    implied_reason = holistic_reasons.get(path)
    implied_flag = bool(implied_reason or path in holistic_implied)
    sensitive = _is_sensitive({}, row)
    trait_fallback = _strip_html(path)
    trait_label = f"🔒 {trait_fallback}" if sensitive else trait_fallback

    records.append({
        "Trait": trait_label,
        "State": "resolved",
        "Value": _format_value(row.get("value")),
        "UCN": row.get("ucn"),
        "RR": row.get("rr"),
        "Curiosity": row.get("curiosity"),
        "Source": _strip_html(provenance.get("source", "")),
        "Actor": _strip_html(provenance.get("from", "")),
        "Reasons": ", ".join(_strip_html(reason) for reason in reasons if reason) if reasons else "",
        "Type": "",
        "Notes": _strip_html(row.get("notes", {}).get("summary")) if isinstance(row.get("notes"), dict) else "",
        "Choices": "",
        "Holistic": holistic_marker,
        "Implied reason": _strip_html(implied_reason) if implied_reason else "",
        "Governance": "🔒 Sensitive" if sensitive else "",
    })
    implied_flags.append(implied_flag)

if not records:
    st.info("No catalog entries available.")
else:
    df = pd.DataFrame(records)
    if "Holistic" not in df.columns:
        df["Holistic"] = ""
    if "Implied reason" not in df.columns:
        df["Implied reason"] = ""
    df["RR_numeric"] = pd.to_numeric(df["RR"], errors="coerce")
    df.sort_values(by=["RR_numeric", "Trait"], ascending=[False, True], inplace=True, na_position="last")
    df_display = df.drop(columns=["RR_numeric"])
    df_display["UCN"] = df_display["UCN"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "") if "UCN" in df_display.columns else df_display
    df_display["RR"] = df_display["RR"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "")
    df_display["Curiosity"] = df_display["Curiosity"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "")

    for column in df_display.columns:
        if df_display[column].dtype == object:
            df_display[column] = df_display[column].map(_strip_html)

    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.caption("H = adjusted by holistic pass. 🔒 indicates governance-sensitive traits. Implied traits appear with lighter text.")
