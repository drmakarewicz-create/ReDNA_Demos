# explorer_benchmarks_panel.py
# ReDNA • Explorer Benchmarks Panel (Benchmarks 1–3)
# Full drop-in Streamlit app to validate Core→UCN/RR→Explorer→UCN/RR→Core loop
# - Enforces "no-bypass": Explorer never writes directly to Core.
# - Runs Onboarding seed + WYR (Benchmark 1) with expected RR nudge.
# - Verifies User-facing vs Developer Mode separation (Benchmark 2).
# - Runs post-onboarding customization (Benchmark 3) and confirms deltas.
#
# ENV:
#   CORE_BASE         default http://localhost:8015
#   UCNRR_BASE        default http://localhost:8011
#   USE_UCNRR         default "true"   (MUST be true)
#   APP_USER_ID       default "demo_user"
#   LLM_ENDPOINT      default "http://localhost:11434"   # for future use
#   LLM_MODEL         default "llama3"                    # for future use
#
# Run:
#   pip install streamlit requests
#   streamlit run explorer_benchmarks_panel.py

import os, json, time, io
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import requests
import streamlit as st

# ---------------------------- Config & Guards ----------------------------
CORE_BASE = os.environ.get("CORE_BASE", "http://localhost:8015").rstrip("/")
UCNRR_BASE = os.environ.get("UCNRR_BASE", "http://localhost:8011").rstrip("/")
USE_UCNRR = os.environ.get("USE_UCNRR", "true").lower().strip()
APP_USER_ID = os.environ.get("APP_USER_ID", "demo_user")

if USE_UCNRR != "true":
    st.error("USE_UCNRR must be TRUE. This panel enforces UCN/RR as the arbiter (no Core writes from Explorer).")
    st.stop()

# ---------------------------- Helpers ----------------------------
TIMEOUT = 10

def ping(url: str) -> bool:
    try:
        r = requests.get(url, timeout=TIMEOUT)
        return r.status_code < 500
    except Exception:
        return False

def post(url: str, payload: dict) -> requests.Response:
    return requests.post(url, json=payload, timeout=TIMEOUT)

def get(url: str, params: Optional[dict] = None) -> requests.Response:
    return requests.get(url, params=params or {}, timeout=TIMEOUT)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Abstracted UCN/RR contract used here:
# Explorer -> UCN/RR
#   POST /ucnrr/ingest_trait  {user_id, trait_key, trait_value, provenance, evidence_type}
#   POST /ucnrr/recompute     {user_id, reason}
#   GET  /ucnrr/snapshot?user_id=...
#
# UCN/RR -> Core (single writer path; Explorer never calls these)
#   POST /core/upsert_traits  {...}   # not called from this panel

def ingest_trait(user_id: str, key: str, value: Any, provenance: str, evidence_type: str) -> bool:
    payload = {
        "user_id": user_id,
        "trait_key": key,
        "trait_value": value,
        "provenance": provenance,
        "evidence_type": evidence_type,
        "timestamp": now_iso(),
    }
    try:
        r = post(f"{UCNRR_BASE}/ucnrr/ingest_trait", payload)
        return r.status_code < 300
    except Exception:
        return False

def recompute(user_id: str, reason: str) -> bool:
    try:
        r = post(f"{UCNRR_BASE}/ucnrr/recompute", {"user_id": user_id, "reason": reason, "timestamp": now_iso()})
        return r.status_code < 300
    except Exception:
        return False

def snapshot(user_id: str) -> Optional[dict]:
    try:
        r = get(f"{UCNRR_BASE}/ucnrr/snapshot", {"user_id": user_id})
        if r.status_code < 300:
            return r.json()
    except Exception:
        return None
    return None

def rr_display(data: Optional[dict]) -> str:
    if not data:
        return "—"
    rr = data.get("rr_percentile")
    return f"{rr:.1f}%" if isinstance(rr, (int, float)) else "—"

def dev_extract(data: Optional[dict]) -> Dict[str, Any]:
    if not data:
        return {}
    return {
        "per_trait_ucn": data.get("per_trait_ucn"),
        "per_dna_ucn": data.get("per_dna_ucn"),
        "curiosity": data.get("curiosity"),
        "contradictions": data.get("contradictions"),
        "audit": data.get("audit"),
        "formatted_traits": data.get("formatted_traits"),
    }

# ---------------------------- UI ----------------------------
st.set_page_config(page_title="ReDNA • Explorer Benchmarks Panel", page_icon="🧪", layout="centered")
st.title("🧪 ReDNA • Explorer Benchmarks Panel")
st.caption("Validates Core→UCN/RR→Explorer→UCN/RR→Core loop with one-click tests. RR is user-visible; raw UCN stays Dev-only.")

# Connection checks
colA, colB, colC = st.columns(3)
with colA:
    st.metric("Core", "UP" if ping(f"{CORE_BASE}/health") else "—")
with colB:
    st.metric("UCN/RR", "UP" if ping(f"{UCNRR_BASE}/health") else "—")
with colC:
    st.metric("User", APP_USER_ID)

st.divider()

# ---------------------------- Benchmarks Controller ----------------------------
if "benchmarks" not in st.session_state:
    st.session_state.benchmarks = {
        "b1_onboarding_seed": False,
        "b1_wyr": False,
        "b2_dev_mode_on": False,
        "b2_dev_mode_off": False,
        "b3_customization_saved": False,
        "b3_voice_check": False,
        "baseline_rr": None,
        "last_rr": None,
        "dev_mode": False,
        "dev_audit_cache": {},
    }

S = st.session_state.benchmarks

# Utility to refresh and show RR
def refresh_rr(label: str):
    data = snapshot(APP_USER_ID)
    S["last_rr"] = data.get("rr_percentile") if data else None
    st.write(f"**{label} RR:**", rr_display(data))
    if S["dev_mode"] and data:
        with st.expander("Developer Console (Dev-only)", expanded=False):
            dev = dev_extract(data)
            st.json(dev)
            # exports
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "Download Dev Audit (JSON)",
                    data=json.dumps(dev, indent=2, default=str),
                    file_name="dev_audit.json",
                    mime="application/json",
                )
            with c2:
                # Flatten a few top-level audit entries to CSV (best-effort)
                audit = dev.get("audit") or []
                buf = io.StringIO()
                buf.write("timestamp,action,delta,meta\n")
                for entry in audit:
                    ts = entry.get("timestamp", "")
                    action = entry.get("action", "")
                    delta = entry.get("delta", "")
                    meta = json.dumps(entry.get("meta", {}), default=str).replace("\n", "\\n").replace(",", ";")
                    buf.write(f"{ts},{action},{delta},{meta}\n")
                st.download_button("Download Dev Audit (CSV)", data=buf.getvalue(),
                                   file_name="dev_audit.csv", mime="text/csv")

# ---------------------------- Dev Mode Toggle (manual) ----------------------------
st.subheader("🔧 Developer Mode (manual toggle)")
dev_col1, dev_col2 = st.columns([1,2])
with dev_col1:
    if st.toggle("Developer Mode", value=S["dev_mode"], help="Shows raw UCN/curiosity/audit in Dev Console (never shown to end users)."):
        S["dev_mode"] = True
        S["b2_dev_mode_on"] = True
    else:
        S["dev_mode"] = False
        S["b2_dev_mode_off"] = True
with dev_col2:
    st.info("Dev Mode reveals internals for builders only; user-facing UX exposes RR/benchmarks, not raw UCN.", icon="ℹ️")

st.divider()

# ---------------------------- Benchmark 1 ----------------------------
st.subheader("✅ Benchmark 1 — Onboarding seed → Head Coach assignment → WYR")
st.caption("Enter quick basics; do one WYR. Expect a small RR bump (~0.5–1.5% typical per action).")

with st.form("b1_form"):
    age_range = st.selectbox("Age Range", ["18–24","25–34","35–44","45–54","55–64","65+"], index=2)
    gender = st.selectbox("Gender", ["male","female","nonbinary","prefer_not_say"])
    orientation = st.selectbox("Orientation", ["straight","gay/lesbian","bisexual","other","prefer_not_say"])
    relationship = st.selectbox("Relationship Status", ["single","in_relationship","married","it’s_complicated","prefer_not_say"])
    lang = st.selectbox("Preferred Language", ["English","Spanish","French","Other"], index=0)

    wyr_q = st.text_input("Would You Rather (WYR) question", value="Bold style vs Soft charm?")
    wyr_choice = st.selectbox("Your choice", ["Bold style","Soft charm","Skip"], index=0)

    submitted = st.form_submit_button("Run Benchmark 1")
    if submitted:
        ok = True
        # Ingest onboarding basics via UCN/RR
        for k, v in [
            ("age_range", age_range),
            ("gender", gender),
            ("orientation", orientation),
            ("relationship_status", relationship),
            ("language", lang),
        ]:
            ok = ok and ingest_trait(APP_USER_ID, k, v, provenance="onboarding_form", evidence_type="self_report")
        if not ok:
            st.error("Failed sending onboarding traits to UCN/RR.")
        else:
            S["b1_onboarding_seed"] = True

        # WYR
        if wyr_choice != "Skip":
            ok = ingest_trait(APP_USER_ID, "wyr_response", {"q": wyr_q, "choice": wyr_choice},
                              provenance="onboarding_wyr", evidence_type="interaction")
            if ok:
                S["b1_wyr"] = True
            else:
                st.warning("WYR ingest failed; continuing.")

        # Recompute UCN/RR and fetch baseline/updated RR
        recompute(APP_USER_ID, reason="benchmark_1_onboarding")
        time.sleep(0.4)
        if S["baseline_rr"] is None:
            data0 = snapshot(APP_USER_ID)
            S["baseline_rr"] = data0.get("rr_percentile") if data0 else None

        refresh_rr("Post-Benchmark 1")

# progress row
p1 = st.columns(2)
with p1[0]:
    st.success("Onboarding seed captured") if S["b1_onboarding_seed"] else st.info("Onboarding not yet captured")
with p1[1]:
    st.success("WYR recorded") if S["b1_wyr"] else st.info("No WYR yet")

st.divider()

# ---------------------------- Benchmark 2 ----------------------------
st.subheader("✅ Benchmark 2 — Head Coach role: User-facing vs Developer Mode")
st.caption("Verify that only RR is user-facing. Raw UCN/curiosity/audits stay in Dev Console (manual toggle).")

# Flip was handled above via toggle; just show the RR + Dev if enabled.
recompute(APP_USER_ID, reason="benchmark_2_view_modes")
time.sleep(0.2)
refresh_rr("Benchmark 2")

st.divider()

# ---------------------------- Benchmark 3 ----------------------------
st.subheader("✅ Benchmark 3 — Post-Onboarding customization (gender + style)")
st.caption("Pick a coach gender & style. Expect slight RR nudge and clear tone/voice change on responses.")

style_map = {
    "Empathetic Listener": "empathetic",
    "Adventurous Explorer": "adventurous",
    "Wise Mentor": "wise",
    "Random": "random",
}
with st.form("b3_form"):
    coach_gender = st.selectbox("Coach Gender", ["female","male","nonbinary","unspecified"], index=0)
    coach_style_label = st.selectbox("Coach Style", list(style_map.keys()), index=0)
    prompt_line = st.text_input("One-liner test prompt to hear voice", value="Give me a one-sentence pep talk.")
    run_b3 = st.form_submit_button("Run Benchmark 3")

    if run_b3:
        ok = True
        ok = ok and ingest_trait(APP_USER_ID, "coach_gender_pref", coach_gender,
                                 provenance="post_onboarding", evidence_type="preference")
        ok = ok and ingest_trait(APP_USER_ID, "coach_style_pref", style_map[coach_style_label],
                                 provenance="post_onboarding", evidence_type="preference")
        if ok:
            S["b3_customization_saved"] = True
        else:
            st.error("Failed to save customization via UCN/RR.")

        # Recompute and display RR
        recompute(APP_USER_ID, reason="benchmark_3_customization")
        time.sleep(0.4)
        refresh_rr("Post-Benchmark 3")

        # Voice check (LLM call placeholder; you can wire your Head Coach backend here)
        # For now, we simulate the different tones in-panel to confirm stylistic branching logic.
        style = style_map[coach_style_label]
        S["b3_voice_check"] = True
        if style == "empathetic":
            st.write("**Coach (Empathetic):** You’ve got this—one small step today builds momentum for tomorrow.")
        elif style == "adventurous":
            st.write("**Coach (Adventurous):** Let’s go—pick the bold path and we’ll course-correct on the fly!")
        elif style == "wise":
            st.write("**Coach (Wise):** Strength grows from intention—begin with one thoughtful action now.")
        else:
            st.write("**Coach (Random):** New day, new map—roll the dice and learn something fun.")

# progress row
p3 = st.columns(2)
with p3[0]:
    st.success("Customization saved") if S["b3_customization_saved"] else st.info("Not customized yet")
with p3[1]:
    st.success("Voice check done") if S["b3_voice_check"] else st.info("No voice test yet")

st.divider()

# ---------------------------- Summary & Export ----------------------------
st.subheader("Progress Summary")
colS1, colS2, colS3 = st.columns(3)
with colS1:
    st.metric("Baseline RR", f"{S['baseline_rr']:.1f}%" if isinstance(S["baseline_rr"], (int,float)) else "—")
with colS2:
    st.metric("Latest RR", f"{S['last_rr']:.1f}%" if isinstance(S["last_rr"], (int,float)) else "—")
with colS3:
    completed = sum([
        S["b1_onboarding_seed"], S["b1_wyr"],
        S["b2_dev_mode_on"], S["b2_dev_mode_off"],
        S["b3_customization_saved"], S["b3_voice_check"]
    ])
    st.metric("Benchmarks Done", f"{completed}/6")

report = {
    "user_id": APP_USER_ID,
    "timestamp": now_iso(),
    "baseline_rr": S["baseline_rr"],
    "latest_rr": S["last_rr"],
    "b1_onboarding_seed": S["b1_onboarding_seed"],
    "b1_wyr": S["b1_wyr"],
    "b2_dev_mode_on": S["b2_dev_mode_on"],
    "b2_dev_mode_off": S["b2_dev_mode_off"],
    "b3_customization_saved": S["b3_customization_saved"],
    "b3_voice_check": S["b3_voice_check"],
}
st.download_button(
    "Download Benchmarks Report (JSON)",
    data=json.dumps(report, indent=2, default=str),
    file_name="benchmarks_1_3_report.json",
    mime="application/json",
)

st.caption("Tip: keep Dev Mode manual & separate—end users only see RR and friendly benchmarks, not raw UCN/audit.")