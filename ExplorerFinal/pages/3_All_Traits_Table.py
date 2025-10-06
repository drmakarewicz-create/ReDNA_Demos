# ExplorerFinal/pages/3_All_Traits_Table.py
from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.nav import side_nav, render_top_nav
from ui.session import (
    get_user_id,
    render_user_banner,
    core_get_resolved_flat,
    core_get_last_holistic,
)


st.set_page_config(page_title="All Traits — ReDNA Explorer", layout="wide")
side_nav(active="all_traits")
render_top_nav()

st.title("All Traits")
render_user_banner()

user_id = get_user_id()
if not user_id:
    st.info("Pick an active user in Explorer to view resolved traits.")
    st.stop()

resolved = core_get_resolved_flat(user_id)
rows = resolved.get("rows", []) if isinstance(resolved, dict) else []

if not rows:
    st.info("No resolved traits yet. Try sending freeform text from the Explorer tab.")
    st.stop()

holistic_snapshot = core_get_last_holistic(user_id)
paths_map = holistic_snapshot.get("paths", {}) if isinstance(holistic_snapshot, dict) else {}
holistic_all = set(paths_map.get("all", []) or [])
holistic_implied = set(paths_map.get("implied", []) or [])
holistic_reasons = holistic_snapshot.get("implied_reasons", {}) if isinstance(holistic_snapshot, dict) else {}

normalized = []
implied_flags: list[bool] = []
for row in rows:
    provenance = row.get("provenance") or {}
    reasons = row.get("reasons") or []
    flags = row.get("flags") or []
    path = row.get("path")
    holistic_marker = "H" if path in holistic_all else ""
    implied_reason = holistic_reasons.get(path)
    implied = path in holistic_implied
    normalized.append({
        "Holistic": holistic_marker,
        "Trait": row.get("path"),
        "Value": row.get("value"),
        "UCN": row.get("ucn") or (round((row.get("confidence") or 0) * 100, 1) if row.get("confidence") is not None else None),
        "RR": row.get("rr"),
        "Curiosity": row.get("curiosity"),
        "Source": provenance.get("source"),
        "Actor": provenance.get("from"),
        "Reasons": ", ".join(reasons) if reasons else "",
        "Flags": ", ".join(flags) if flags else "",
        "Notes": (row.get("notes", {}) or {}).get("summary"),
        "Status": row.get("status"),
        "Implied reason": implied_reason or "",
    })
    implied_flags.append(bool(implied_reason or implied))

if not normalized:
    st.info("No resolved traits yet.")
else:
    df = pd.DataFrame(normalized)
    column_order = [
        "Holistic",
        "Trait",
        "Value",
        "UCN",
        "RR",
        "Curiosity",
        "Source",
        "Actor",
        "Reasons",
        "Flags",
        "Notes",
        "Status",
        "Implied reason",
    ]
    df = df[column_order]
    df["RR_numeric"] = pd.to_numeric(df["RR"], errors="coerce")
    df.sort_values(by=["RR_numeric", "Trait"], ascending=[False, True], inplace=True, na_position="last")
    df_display = df.drop(columns=["RR_numeric"])
    df_display["UCN"] = df_display["UCN"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "")
    df_display["RR"] = df_display["RR"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "")
    df_display["Curiosity"] = df_display["Curiosity"].map(lambda x: f"{x:.5f}" if pd.notnull(x) else "")

    tooltip_df = pd.DataFrame("", index=df_display.index, columns=df_display.columns)
    for idx, marker in enumerate(df_display["Holistic"].tolist()):
        if marker:
            tooltip_df.iat[idx, df_display.columns.get_loc("Holistic")] = "Adjusted by holistic pass"
        if implied_flags[idx] and df_display.at[df_display.index[idx], "Implied reason"]:
            tooltip_df.iat[idx, df_display.columns.get_loc("Value")] = f"Implied by rule: {df_display.at[df_display.index[idx], 'Implied reason']}"

    def _style_row(row: pd.Series) -> list[str]:
        idx = row.name
        return ["opacity: 0.6" if implied_flags[idx] else "" for _ in row]

    styled = (
        df_display.style.apply(_style_row, axis=1)
        .set_tooltips(tooltip_df)
        .set_properties(**{"white-space": "normal"})
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("H = adjusted by holistic pass. Implied traits appear with lighter text.")
