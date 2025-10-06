"""Dev regression card consolidating smoke checks for Explorer teams."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import streamlit as st

from ReDNACoreDemo.core import planner, storage
from ReDNACoreDemo.core.policy import evaluate_nudge_policy

_SAMPLE_GAPS = [
    {"container": "PsyDNA", "gap": "attachment_style", "confidence": 0.72},
    {"container": "BehDNA", "gap": "fitness_habits", "confidence": 0.58},
    {"container": "PaDNA.HairDNA", "gap": "style", "confidence": 0.41},
]

_SAMPLE_NUDGES = [
    {
        "label": "Fresh TTL",
        "payload": {
            "now": "2025-01-01T12:00:00Z",
            "last_sent": "2024-12-31T09:00:00Z",
            "ttl": 1440,
            "snooze": 120,
            "rate_cap_per_day": 3,
            "sent_count_today": 1,
        },
    },
    {
        "label": "TTL active",
        "payload": {
            "now": "2025-01-01T12:00:00Z",
            "last_sent": "2025-01-01T11:20:00Z",
            "ttl": 90,
        },
    },
    {
        "label": "Rate capped",
        "payload": {
            "now": "2025-01-01T12:00:00Z",
            "rate_cap_per_day": 2,
            "sent_count_today": 2,
        },
    },
]


def _run_command(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _render_command_section() -> None:
    st.subheader("Inference Harness")
    if st.button("Run smoke suite", key="reg_card_harness"):
        with st.spinner("Running inference harness…"):
            result = _run_command(["python3", "-m", "ReDNACoreDemo.core_inference_harness", "--suite", "smoke"])
        status = "PASS" if result.returncode == 0 else "FAIL"
        st.code(result.stdout or "(no stdout)")
        if result.stderr:
            st.error(result.stderr)
        tone = st.success if result.returncode == 0 else st.error
        tone(f"Harness {status} (exit {result.returncode})")


def _render_planner_section() -> None:
    st.subheader("Curiosity Planner")
    if st.button("Generate sample asks", key="reg_card_planner"):
        with st.spinner("Preparing ask queue preview…"):
            temp_user = f"regcard_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            ask_queue = planner.plan_gaps(temp_user, _SAMPLE_GAPS, limit=5)
        st.json(ask_queue)
        st.info(f"Queued {len(ask_queue)} ask(s) for {temp_user} (written under data/users/)")


def _render_policy_section() -> None:
    st.subheader("Nudge Policy")
    if st.button("Evaluate sample payloads", key="reg_card_policy"):
        rows = []
        for sample in _SAMPLE_NUDGES:
            result = evaluate_nudge_policy(sample["payload"])
            rows.append({"scenario": sample["label"], **result})
        st.table(rows)


def _render_migration_section() -> None:
    st.subheader("Bundle Migration")
    if st.button("Verify v1 → v2 migration", key="reg_card_migration"):
        payload = {
            "meta": {"version": "1.0", "user_id": "regcard_demo"},
            "resolved": {"PaDNA.HairDNA.Style": {"resolved_value": "Curly"}},
            "evidence": {"items": []},
            "observations": None,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            temp_path = Path(handle.name)
        try:
            migrated = storage.import_bundle(temp_path, apply=False)
        finally:
            temp_path.unlink(missing_ok=True)
        st.json(migrated.get("meta", {}))
        st.success("Migration completed in-memory. Meta shown above.")


def render_regression_card(context) -> None:  # context kept for future hooks
    st.title("Regression Card")
    st.caption("Quick smoke checks for inference, planner, policy, and bundle migrations.")

    _render_command_section()
    st.markdown("---")
    _render_planner_section()
    st.markdown("---")
    _render_policy_section()
    st.markdown("---")
    _render_migration_section()
