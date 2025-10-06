# control_and_benchmarks.py
# ReDNA • Unified Control Panel + Explorer Benchmarks (Benchmarks 1–3)
# - Control: health checks, port tester, env overrides, AI (Ollama/Llama3) sanity test
# - Benchmarks: onboarding seed + WYR, Dev Mode separation, post-onboarding customization
# - Enforces "no bypass": Explorer traffic goes through UCN/RR (never writes Core directly)

import os, io, json, time, subprocess, shlex
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import requests
import streamlit as st

# --------------- Page config ---------------
st.set_page_config(
    page_title="ReDNA • Control + Benchmarks",
    page_icon="🧪",
    layout="centered",
)

# --------------- Helpers ---------------
TIMEOUT = 10

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def http_get(url: str, params: Optional[dict] = None) -> Optional[requests.Response]:
    try:
        return requests.get(url, params=params or {}, timeout=TIMEOUT)
    except Exception:
        return None

def http_post(url: str, payload: dict) -> Optional[requests.Response]:
    try:
        return requests.post(url, json=payload, timeout=TIMEOUT)
    except Exception:
        return None

def ping_health(base: str) -> bool:
    if not base:
        return False
    base = base.rstrip("/")
    # try /health first, then root
    for path in ("/health", "/"):
        r = http_get(base + path)
        if r and r.status_code < 500:
            return True
    return False

def ingest_trait(ucnrr_base: str, user_id: str, key: str, value: Any,
                 provenance: str, evidence_type: str) -> bool:
    payload = {
        "user_id": user_id,
        "trait_key": key,
        "trait_value": value,
        "provenance": provenance,
        "evidence_type": evidence_type,
        "timestamp": now_iso(),
    }
    r = http_post(f"{ucnrr_base.rstrip('/')}/ucnrr/ingest_trait", payload)
    return bool(r and r.status_code < 300)

def recompute(ucnrr_base: str, user_id: str, reason: str) -> bool:
    r = http_post(f"{ucnrr_base.rstrip('/')}/ucnrr/recompute",
                  {"user_id": user_id, "reason": reason, "timestamp": now_iso()})
    return bool(r and r.status_code < 300)

def snapshot(ucnrr_base: str, user_id: str) -> Optional[dict]:
    r = http_get(f"{ucnrr_base.rstrip('/')}/ucnrr/snapshot", {"user_id": user_id})
    if r and r.status_code < 300:
        try:
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

# --------------- Sidebar (global config) ---------------
st.sidebar.title("⚙️ Configuration")

CORE_BASE = st.sidebar.text_input("Core Base URL", os.environ.get("CORE_BASE", "http://localhost:8015")).rstrip("/")
UCNRR_BASE = st.sidebar.text_input("UCN/RR Base URL", os.environ.get("UCNRR_BASE", "http://localhost:8011")).rstrip("/")
APP_USER_ID = st.sidebar.text_input("User ID", os.environ.get("APP_USER_ID", "demo_user")).strip() or "demo_user"

USE_UCNRR = st.sidebar.selectbox("USE_UCNRR (required)", ["true", "false"],
                                 index=0 if os.environ.get("USE_UCNRR", "true").lower()=="true" else 1)
if USE_UCNRR != "true":
    st.sidebar.error("USE_UCNRR must be TRUE. This app enforces UCN/RR as the arbiter (no Core writes).")

st.sidebar.markdown("---")
st.sidebar.subheader("AI Backend (optional)")
LLM_ENDPOINT = st.sidebar.text_input("LLM Endpoint (e.g., Ollama)", os.environ.get("LLM_ENDPOINT", "http://localhost:11434")).rstrip("/")
LLM_MODEL = st.sidebar.text_input("LLM Model", os.environ.get("LLM_MODEL", "llama3")).strip() or "llama3"

st.sidebar.markdown("---")
st.sidebar.caption("Tip: Core → UCN/RR → Explorer (this panel) → UCN/RR → Core. Explorer never writes Core directly.")

# --------------- Tabs ---------------
tab_control, tab_bench, tab_ai = st.tabs(["🖥️ Control Panel", "🧪 Benchmarks (1–3)", "🤖 AI Controls"])

# ========================= CONTROL PANEL =========================
with tab_control:
    st.header("🖥️ Control Panel")
    st.caption("Start/stop is optional; health checks + port tester are the essentials. RR is user-visible; raw UCN is Dev-only elsewhere.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Core", "UP" if ping_health(CORE_BASE) else "—")
    with c2:
        st.metric("UCN/RR", "UP" if ping_health(UCNRR_BASE) else "—")
    with c3:
        st.metric("User", APP_USER_ID or "—")

    st.subheader("🔌 Port / Endpoint Tester")
    st.caption("Ping any base URL + path (e.g., http://localhost:8011/health). Useful to confirm UCN/RR just like Core.")
    tcol1, tcol2 = st.columns([3,1])
    with tcol1:
        test_url = st.text_input("URL to test", value=f"{UCNRR_BASE}/health" if UCNRR_BASE else "")
    with tcol2:
        if st.button("Test"):
            if not test_url:
                st.warning("Enter a URL to test.")
            else:
                r = http_get(test_url)
                if r is None:
                    st.error("No response (connection error).")
                else:
                    st.success(f"HTTP {r.status_code}")
                    with st.expander("Response headers / body"):
                        st.json(dict(r.headers))
                        # Try to parse JSON; if not, show text
                        try:
                            st.json(r.json())
                        except Exception:
                            st.code(r.text or "(no body)")

    st.markdown("---")
    st.subheader("🚀 Optional: Launch Commands")
    st.caption("If you have local scripts, you can run them here (advanced). Leave blank if you prefer your own runner.")
    lc1, lc2 = st.columns(2)
    with lc1:
        core_cmd = st.text_input("Core start command (optional)", value="")
        ucnrr_cmd = st.text_input("UCN/RR start command (optional)", value="")
    with lc2:
        explorer_cmd = st.text_input("Explorer start command (optional)", value="")
        shell_mode = st.checkbox("Run in shell=True (dangerous on Windows), else execve-like", value=False)

    def _spawn(cmd: str):
        if not cmd.strip():
            st.warning("No command set.")
            return
        try:
            if shell_mode:
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(shlex.split(cmd))
            st.success("Launched.")
        except Exception as e:
            st.error(f"Launch failed: {e}")

    lcol1, lcol2, lcol3 = st.columns(3)
    with lcol1:
        if st.button("Start Core"):
            _spawn(core_cmd)
    with lcol2:
        if st.button("Start UCN/RR"):
            _spawn(ucnrr_cmd)
    with lcol3:
        if st.button("Start Explorer"):
            _spawn(explorer_cmd)

# ========================= BENCHMARKS =========================
with tab_bench:
    st.header("🧪 Explorer Benchmarks (1–3)")
    if USE_UCNRR != "true":
        st.error("USE_UCNRR must be TRUE. Enable it in the sidebar to run benchmarks.")
        st.stop()

    # Session cache
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
        }
    S = st.session_state.benchmarks

    # Health snapshot row
    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        st.metric("Core", "UP" if ping_health(CORE_BASE) else "—")
    with hc2:
        st.metric("UCN/RR", "UP" if ping_health(UCNRR_BASE) else "—")
    with hc3:
        st.metric("User", APP_USER_ID or "—")

    st.divider()
    st.subheader("🔧 Developer Mode (manual toggle)")
    dev_left, dev_right = st.columns([1,2])
    with dev_left:
        if st.toggle("Developer Mode", value=S["dev_mode"],
                     help="Shows raw UCN/curiosity/audit in Dev Console (never shown to end users)."):
            S["dev_mode"] = True
            S["b2_dev_mode_on"] = True
        else:
            S["dev_mode"] = False
            S["b2_dev_mode_off"] = True
    with dev_right:
        st.info("Dev Mode shows internals for builders only; end users see RR/benchmarks (not raw UCN).", icon="ℹ️")

    st.divider()
    st.subheader("✅ Benchmark 1 — Onboarding seed → Head Coach assignment → WYR")
    st.caption("Enter basics and answer one WYR. Expect a small RR bump (~0.5–1.5% per action).")

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
            if not ping_health(UCNRR_BASE):
                st.error("UCN/RR appears down. Start it and try again.")
            else:
                ok = True
                for k, v in [
                    ("age_range", age_range),
                    ("gender", gender),
                    ("orientation", orientation),
                    ("relationship_status", relationship),
                    ("language", lang),
                ]:
                    ok = ok and ingest_trait(UCNRR_BASE, APP_USER_ID, k, v, "onboarding_form", "self_report")
                if ok:
                    S["b1_onboarding_seed"] = True
                else:
                    st.error("Failed to send onboarding traits to UCN/RR.")

                if wyr_choice != "Skip":
                    ok = ingest_trait(UCNRR_BASE, APP_USER_ID, "wyr_response",
                                      {"q": wyr_q, "choice": wyr_choice}, "onboarding_wyr", "interaction")
                    if ok:
                        S["b1_wyr"] = True
                    else:
                        st.warning("WYR ingest failed (continuing).")

                recompute(UCNRR_BASE, APP_USER_ID, "benchmark_1_onboarding")
                time.sleep(0.4)

                # establish baseline if first run
                if S["baseline_rr"] is None:
                    data0 = snapshot(UCNRR_BASE, APP_USER_ID)
                    S["baseline_rr"] = data0.get("rr_percentile") if data0 else None

                # show latest
                data = snapshot(UCNRR_BASE, APP_USER_ID)
                S["last_rr"] = data.get("rr_percentile") if data else None

                st.write("**Post-Benchmark 1 RR:**", rr_display(data))
                if S["dev_mode"] and data:
                    with st.expander("Developer Console (Dev-only)", expanded=False):
                        dev = dev_extract(data)
                        st.json(dev)

    row_b1 = st.columns(2)
    with row_b1[0]:
        st.success("Onboarding seed captured") if S["b1_onboarding_seed"] else st.info("Onboarding not yet captured")
    with row_b1[1]:
        st.success("WYR recorded") if S["b1_wyr"] else st.info("No WYR yet")

    st.divider()
    st.subheader("✅ Benchmark 2 — User-facing vs Developer Mode")
    st.caption("Only RR is user-facing; raw UCN/audits stay in Dev Console.")
    recompute(UCNRR_BASE, APP_USER_ID, "benchmark_2_view_modes")
    time.sleep(0.2)
    data2 = snapshot(UCNRR_BASE, APP_USER_ID)
    st.write("**Benchmark 2 RR:**", rr_display(data2))
    if S["dev_mode"] and data2:
        with st.expander("Developer Console (Dev-only)", expanded=False):
            st.json(dev_extract(data2))

    st.divider()
    st.subheader("✅ Benchmark 3 — Post-Onboarding customization (gender + style)")
    st.caption("Pick a coach gender & style. Expect a small RR nudge and clear tone/voice change.")
    style_map = {
        "Empathetic Listener": "empathetic",
        "Adventurous Explorer": "adventurous",
        "Wise Mentor": "wise",
        "Random": "random",
    }
    with st.form("b3_form"):
        coach_gender = st.selectbox("Coach Gender", ["female","male","nonbinary","unspecified"], index=0)
        coach_style_label = st.selectbox("Coach Style", list(style_map.keys()), index=0)
        prompt_line = st.text_input("One-liner voice test", value="Give me a one-sentence pep talk.")
        run_b3 = st.form_submit_button("Run Benchmark 3")
        if run_b3:
            if not ping_health(UCNRR_BASE):
                st.error("UCN/RR appears down. Start it and try again.")
            else:
                ok = ingest_trait(UCNRR_BASE, APP_USER_ID, "coach_gender_pref", coach_gender, "post_onboarding", "preference")
                ok = ok and ingest_trait(UCNRR_BASE, APP_USER_ID, "coach_style_pref", style_map[coach_style_label], "post_onboarding", "preference")
                if ok:
                    st.success("Customization saved via UCN/RR.")
                    st.session_state.benchmarks["b3_customization_saved"] = True
                else:
                    st.error("Customization failed.")

                recompute(UCNRR_BASE, APP_USER_ID, "benchmark_3_customization")
                time.sleep(0.4)
                data3 = snapshot(UCNRR_BASE, APP_USER_ID)
                st.write("**Post-Benchmark 3 RR:**", rr_display(data3))
                if S["dev_mode"] and data3:
                    with st.expander("Developer Console (Dev-only)", expanded=False):
                        st.json(dev_extract(data3))

                # Simulated stylistic responses (wire to Head Coach LLM later)
                style = style_map[coach_style_label]
                S["b3_voice_check"] = True
                st.markdown("**Voice Check**")
                if style == "empathetic":
                    st.write("Coach (Empathetic): You’ve got this—one small step today builds momentum for tomorrow.")
                elif style == "adventurous":
                    st.write("Coach (Adventurous): Let’s go—pick the bold path and we’ll course-correct on the fly!")
                elif style == "wise":
                    st.write("Coach (Wise): Strength grows from intention—begin with one thoughtful action now.")
                else:
                    st.write("Coach (Random): New day, new map—roll the dice and learn something fun.")

    row_b3 = st.columns(2)
    with row_b3[0]:
        st.success("Customization saved") if S["b3_customization_saved"] else st.info("Not customized yet")
    with row_b3[1]:
        st.success("Voice check done") if S["b3_voice_check"] else st.info("No voice test yet")

    st.divider()
    st.subheader("📊 Summary & Export")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("Baseline RR", f"{S['baseline_rr']:.1f}%" if isinstance(S["baseline_rr"], (int,float)) else "—")
    with s2:
        st.metric("Latest RR", f"{S['last_rr']:.1f}%" if isinstance(S["last_rr"], (int,float)) else "—")
    with s3:
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
    st.download_button("Download Benchmarks Report (JSON)",
                       data=json.dumps(report, indent=2, default=str),
                       file_name="benchmarks_1_3_report.json",
                       mime="application/json")

# ========================= AI CONTROLS =========================
with tab_ai:
    st.header("🤖 AI Controls (LLM Sanity Test)")
    st.caption("Quick ping to your local LLM (e.g., Ollama at http://localhost:11434). Safe to skip if you’re not using it yet.")

    prompt = st.text_area("Prompt", "Say a peppy one-liner like a friendly Head Coach.", height=80)
    if st.button("Run LLM Test"):
        try:
            # Minimal Ollama-style request; adjust to your provider as needed.
            r = http_post(f"{LLM_ENDPOINT}/api/generate", {"model": LLM_MODEL, "prompt": prompt})
            if not r:
                st.error("No response from LLM endpoint.")
            elif r.status_code >= 300:
                st.error(f"LLM returned HTTP {r.status_code}: {r.text[:400]}")
            else:
                # Ollama streams line-delimited JSON; collect text chunks if present.
                text = ""
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        text += obj.get("response", "")
                    except Exception:
                        text += line
                st.success("LLM response:")
                st.write(text.strip() or "(empty)")
        except Exception as e:
            st.error(f"LLM call failed: {e}")

st.markdown("---")
st.caption("ReDNA • Control + Benchmarks • Explorer never writes Core directly; UCN/RR is the arbiter/staging layer.")