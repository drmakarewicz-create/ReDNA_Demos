# ExplorerUCNCoreConnectDemo.py
# -------------------------------------------------------------------
# Explorer ⇄ UCN/RR ⇄ Core connect harness
# - Import a JSON bundle, preview, and save to UCN/RR staging
# - NEW: One-click Export to Core (via UCN/RR gateway with compute/normalize)
# - NEW: Load from Core (via UCN/RR proxy)
#
# Assumes:
#   UCN/RR API at http://localhost:8011
#   Core API at  http://localhost:8010  (reached via UCN/RR proxy)
#
# Safe behaviors:
# - Graceful error messages (no crashes)
# - Optional auto compute/normalize/snapshot on gateway save
# -------------------------------------------------------------------
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import streamlit as st

try:
    import requests
except Exception:
    requests = None


# -------------------------
# Helpers
# -------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def init_state():
    ss = st.session_state
    ss.setdefault("app_version", "explorer-ucn-core-connect-demo/1.1.0")
    ss.setdefault("bundle", {
        "schema_version": "redna.bundle/3.0",
        "Prefs": {"traits": {"wyr_log": []}},
        "PaDNA": {},
        "scores": {"rr_overall": 0.0, "ucn_overall": None, "curiosity_overall": None},
        "provenance": []
    })
    ss.setdefault("env", "dev")
    ss.setdefault("user_id", f"demo_{uuid.uuid4().hex[:6]}")
    ss.setdefault("ucnrr_url", "http://localhost:8011")
    ss.setdefault("last_save_id", None)
    ss.setdefault("last_core_id", None)
    ss.setdefault("last_load_time", None)
    ss.setdefault("last_rr", None)
    ss.setdefault("last_ucn", None)
    ss.setdefault("last_curiosity", None)
    # default gateway flags
    ss.setdefault("gw_compute", "auto")            # auto | off
    ss.setdefault("gw_normalize", "on")            # on | off
    ss.setdefault("gw_snapshot", "on")             # on | off

def _require_requests():
    if requests is None:
        raise RuntimeError("The 'requests' module is not available in this environment.")

def _get(url: str, timeout: int = 8) -> Dict[str, Any]:
    _require_requests()
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} → status={r.status_code}, text={r.text[:200]}")
    return r.json()

def _post(url: str, payload: Dict[str, Any], timeout: int = 8) -> Dict[str, Any]:
    _require_requests()
    r = requests.post(url, json=payload, timeout=timeout)
    if r.status_code != 200:
        # try to surface structured error if possible
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:200]}
        raise RuntimeError(f"POST {url} → status={r.status_code}, data={data}")
    return r.json()

def save_to_ucnrr(base: str, env: str, user_id: str, bundle: Dict[str, Any],
                  compute: str, normalize: str, snapshot: str, to_core: str = "off") -> Dict[str, Any]:
    url = base.rstrip("/") + f"/gateway/save?compute={compute}&normalize={normalize}&persist_snapshot={snapshot}&to_core={to_core}"
    return _post(url, {"env": env, "user_id": user_id, "bundle": bundle})

def load_from_ucnrr(base: str, env: str, user_id: str) -> Dict[str, Any]:
    url = base.rstrip("/") + f"/gateway/latest?env={env}&user_id={user_id}"
    return _get(url)

def load_from_core_via_ucnrr(base: str, env: str, user_id: str) -> Dict[str, Any]:
    url = base.rstrip("/") + f"/core/latest?env={env}&user_id={user_id}"
    return _get(url)


# -------------------------
# App
# -------------------------
def main():
    st.set_page_config(page_title="Explorer • UCN/RR/Core Connect Demo", page_icon="🧭", layout="wide")
    init_state()
    ss = st.session_state

    with st.sidebar:
        st.header("Explorer • Connect")
        ss.ucnrr_url = st.text_input("UCN/RR URL", ss.ucnrr_url)
        ss.env = st.text_input("Environment", ss.env)
        ss.user_id = st.text_input("User ID", ss.user_id)

        st.divider()
        st.subheader("Gateway options")
        ss.gw_compute = st.selectbox("Compute", ["auto", "off"], index=0 if ss.gw_compute == "auto" else 1)
        ss.gw_normalize = st.selectbox("Normalize", ["on", "off"], index=0 if ss.gw_normalize == "on" else 1)
        ss.gw_snapshot = st.selectbox("Persist snapshot", ["on", "off"], index=0 if ss.gw_snapshot == "on" else 1)

        st.divider()
        st.caption(f"App: {ss.app_version}")

    st.title("ExplorerUCNCoreConnectDemo")
    st.caption("Phase 1–2: Import rich JSON • Save to UCN/RR • Load from UCN/RR • Export to Core • Load from Core (via UCN/RR)")

    with st.expander("Import JSON bundle"):
        up = st.file_uploader("Choose JSON", type=["json"])
        if up is not None:
            try:
                ss.bundle = json.load(up)
                st.success("Imported.")
            except Exception as e:
                st.error(f"Parse error: {e}")

    # Action buttons row
    c1, c2, c3, c4 = st.columns([0.28, 0.28, 0.22, 0.22])

    with c1:
        if st.button("Save → UCN/RR (staging)"):
            try:
                res = save_to_ucnrr(
                    ss.ucnrr_url, ss.env, ss.user_id, ss.bundle,
                    compute=ss.gw_compute, normalize=ss.gw_normalize, snapshot=ss.gw_snapshot, to_core="off"
                )
                ss.last_save_id = res.get("ucnrr_id")
                rr = (res.get("rr") or {}).get("overall")
                u = (res.get("ucn") or {}).get("overall")
                c = (res.get("curiosity") or {}).get("overall")
                ss.last_rr, ss.last_ucn, ss.last_curiosity = rr, u, c
                st.success(f"Saved to UCN/RR ✓  id={ss.last_save_id or 'ok'}  |  RR≈{rr if rr is not None else '–'}")
            except Exception as e:
                st.warning(f"Save failed: {e}")

    with c2:
        if st.button("Export to Core (via UCN/RR)"):
            try:
                res = save_to_ucnrr(
                    ss.ucnrr_url, ss.env, ss.user_id, ss.bundle,
                    compute=ss.gw_compute, normalize=ss.gw_normalize, snapshot=ss.gw_snapshot, to_core="on"
                )
                ss.last_save_id = res.get("ucnrr_id")
                rr = (res.get("rr") or {}).get("overall")
                u = (res.get("ucn") or {}).get("overall")
                c = (res.get("curiosity") or {}).get("overall")
                ss.last_rr, ss.last_ucn, ss.last_curiosity = rr, u, c
                chained = res.get("chained_core") or {}
                ss.last_core_id = chained.get("core_id")
                st.success(f"Exported ✓  UCN/RR id={ss.last_save_id or 'ok'}  → Core id={ss.last_core_id or 'ok'}  |  RR≈{rr if rr is not None else '–'}")
            except Exception as e:
                st.error(f"Export failed: {e}")

    with c3:
        if st.button("Load ← UCN/RR"):
            try:
                res = load_from_ucnrr(ss.ucnrr_url, ss.env, ss.user_id)
                ss.bundle = res.get("bundle") or ss.bundle
                ss.last_load_time = utc_now_iso()
                st.success("Loaded latest from UCN/RR ✓")
            except Exception as e:
                st.warning(f"Load failed: {e}")

    with c4:
        if st.button("Load ← Core (via UCN/RR)"):
            try:
                res = load_from_core_via_ucnrr(ss.ucnrr_url, ss.env, ss.user_id)
                ss.bundle = res.get("bundle") or ss.bundle
                ss.last_load_time = utc_now_iso()
                st.success("Loaded latest from Core (via UCN/RR) ✓")
            except Exception as e:
                st.warning(f"Load from Core failed: {e}")

    st.divider()

    col1, col2 = st.columns([0.55, 0.45])
    with col1:
        st.subheader("Snapshot")
        traits = (ss.bundle.get("Prefs") or {}).get("traits") or {}
        # Prefer last computed numbers from gateway responses if present
        rr_display = ss.last_rr if ss.last_rr is not None else ((ss.bundle.get("scores") or {}).get("rr_overall"))
        st.metric("RR (user-visible)", value=None if rr_display is None else round(float(rr_display), 1))
        st.json({
            "eye_color": traits.get("eye_color"),
            "hair_color": traits.get("hair_color"),
            "skin_tone": traits.get("skin_tone"),
            "height": traits.get("height"),
            "gender": traits.get("gender"),
            "orientation": traits.get("orientation"),
            "relationship_status": traits.get("relationship_status"),
            "love_language_pref": traits.get("love_language_pref"),
        })

        st.caption(f"Last save: {ss.last_save_id or '—'} | Core id: {ss.last_core_id or '—'} | Last load: {ss.last_load_time or '—'}")

    with col2:
        st.subheader("Raw bundle")
        st.json(ss.bundle)

        st.subheader("Latest scores (from gateway responses)")
        st.json({
            "rr.overall": ss.last_rr,
            "ucn.overall": ss.last_ucn,
            "curiosity.overall": ss.last_curiosity
        })

    st.caption("Tip: Use the sidebar toggles to control compute/normalize/snapshot behavior on the gateway.")

if __name__ == "__main__":
    main()