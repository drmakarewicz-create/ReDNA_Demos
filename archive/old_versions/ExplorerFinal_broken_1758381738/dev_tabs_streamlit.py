# dev_tabs_streamlit.py
# Shared helpers + renderers for ReDNA Explorer (UCN/RR ingest, Core resolved)
from typing import Any, Dict, List, Optional, Tuple
import os, json, requests, streamlit as st, pandas as pd

# -------------- HTTP utils --------------
def safe_get(url: str, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"_non_json": True, "status_code": r.status_code, "text_len": len(r.text)}
    except Exception:
        return None

def safe_post(url: str, payload: Dict[str, Any], timeout: float = 12.0) -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"_non_json": True, "status_code": r.status_code, "text_len": len(r.text)}
    except Exception:
        return None

def safe_options(url: str, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
    try:
        r = requests.options(url, timeout=timeout)
        return {"status_code": r.status_code, "allow": r.headers.get("Allow")}
    except Exception:
        return None

# -------------- Filesystem helpers --------------
def _scan_users_dir(path: str) -> List[str]:
    try:
        if not path or not os.path.isdir(path): return []
        names = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isdir(full) and not name.startswith("."):
                names.append(name)
        return sorted(names)
    except Exception:
        return []

def read_json(path: str) -> Optional[Any]:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        return None
    return None

def write_json(path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

# -------------- Users API --------------
def try_list_users(core_base: str, ucnrr_base: str, core_users_dir: str, ucnrr_users_dir: str) -> List[str]:
    candidates = [
        f"{core_base}/users/list?limit=500",
        f"{core_base}/user/ids",
        f"{core_base}/users",
        f"{ucnrr_base}/users/list?limit=500",
        f"{ucnrr_base}/user/ids",
    ]
    for url in candidates:
        data = safe_get(url)
        if not data:
            continue
        if "users" in data and isinstance(data["users"], list):
            users = data["users"]
            if users and isinstance(users[0], dict):
                ids = [u.get("user_id") for u in users if isinstance(u, dict) and u.get("user_id")]
                if ids: return sorted(set(ids))
            if users and isinstance(users[0], str):
                return sorted(set(users))
        if "user_ids" in data and isinstance(data["user_ids"], list):
            ids = [str(u) for u in data["user_ids"]]
            if ids: return sorted(set(ids))
    fs = sorted(set(_scan_users_dir(core_users_dir) + _scan_users_dir(ucnrr_users_dir)))
    return fs

def create_user(core_base: str, ucnrr_base: str, user_id: str) -> Dict[str, Any]:
    payload = {"user_id": user_id}
    res_core  = safe_post(f"{core_base}/user/create",  payload) or {}
    res_ucnrr = safe_post(f"{ucnrr_base}/user/create", payload) or {}
    ok = bool(res_core) or bool(res_ucnrr)
    return {"ok": ok, "core": bool(res_core), "ucnrr": bool(res_ucnrr)}

# -------------- Sidebar: Existing User --------------
def render_existing_user_login(core_base: str, ucnrr_base: str, core_users_dir: str, ucnrr_users_dir: str) -> Tuple[str, bool]:
    changed = False
    st.markdown("### Existing User")
    if st.button("Refresh user list", key="sid_refresh_users"):
        st.session_state["_users_cache"] = None
    users_cache = st.session_state.get("_users_cache")
    if users_cache is None:
        users_cache = try_list_users(core_base, ucnrr_base, core_users_dir, ucnrr_users_dir)
        st.session_state["_users_cache"] = users_cache
    options = ["—"] + users_cache if users_cache else ["—"]
    sel = st.selectbox("Select user", options=options, key="sid_existing_user_select")
    if sel != "—" and sel != st.session_state.get("user_id"):
        st.session_state["user_id"] = sel
        changed = True
    st.caption(f"Active User: `{st.session_state.get('user_id','—')}`")
    return st.session_state.get("user_id", "dev_user_001"), changed

# -------------- Diagnostics --------------
CORE_COMMIT_CANDIDATES: List[str] = [
    "/resolve/recompute","/resolve","/process","/commit",
    "/persist","/write","/save","/traits/resolve","/pipeline/commit","/pipeline/resolve",
]

def render_diagnostics_tab(core_base: str, ucnrr_base: str, user_id: str):
    st.markdown("### Diagnostics")
    cols = st.columns(3)
    with cols[0]:
        st.write("**Core**")
        st.json({
            "GET /health": safe_get(f"{core_base}/health"),
            "GET /openapi.json": safe_get(f"{core_base}/openapi.json"),
        })
    with cols[1]:
        st.write("**UCN/RR**")
        st.json({
            "GET /health": safe_get(f"{ucnrr_base}/health"),
            "GET /openapi.json": safe_get(f"{ucnrr_base}/openapi.json"),
        })
    with cols[2]:
        st.write("**Core Commit Candidates (OPTIONS)**")
        results = {}
        for s in CORE_COMMIT_CANDIDATES:
            opt = safe_options(f"{core_base}{s}")
            if opt:
                results[s] = opt
        st.json(results or {"note":"No commit endpoints found (expected if Core is read-only)."})
    note = st.session_state.get("_last_bridge_note")
    if note:
        st.info(f"Bridge: {note}")

# -------------- Feature tabs --------------
def render_tab_unabridged(core_base: str, ucnrr_base: str, user_id: str):
    flat = safe_get(f"{core_base}/resolved/flat/{user_id}") or {"rows":[]}
    rows = flat.get("rows") or flat.get("traits") or []
    if not rows:
        st.info("No flat resolved rows yet. Add freeform text on the main tab.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_tab_head_coach(core_base: str, ucnrr_base: str, user_id: str):
    colL, colR = st.columns([2,3])
    with colL:
        st.subheader("Status")
        st.json({"coach":"Head Coach","mode":"rapport-first","notes":"Wire to a /coach/status route when available."})
    with colR:
        st.subheader("Suggested Next Prompts")
        flat = safe_get(f"{core_base}/resolved/flat/{user_id}") or {"rows":[]}
        rows = flat.get("rows") or []
        suggestions: List[Dict[str, Any]] = []
        for r in rows:
            if (r.get("value") in (None, "", [])) and r.get("trait_key"):
                suggestions.append({
                    "trait_key": r["trait_key"],
                    "prompt": f"Could you share a bit more about {r['trait_key'].replace('.', ' → ')}?",
                    "curiosity": 100
                })
            if len(suggestions) >= 5:
                break
        if suggestions:
            st.dataframe(pd.DataFrame(suggestions), use_container_width=True, hide_index=True)
        else:
            st.info("No obvious gaps; add more evidence to generate prompts.")

def render_tab_onboarding(core_base: str, ucnrr_base: str, user_id: str):
    colL, colR = st.columns([2,3])
    with colL:
        st.subheader("Script / Steps (placeholder)")
        st.json({"steps":[
            {"id":"welcome","text":"Welcome to ReDNA!"},
            {"id":"demographics","fields":["first_name","age_range","relationship_status"]},
            {"id":"seed","text":"A few quick items to seed your profile."}
        ]})
    with colR:
        st.subheader("Collected (read-only)")
        flat = safe_get(f"{core_base}/resolved/flat/{user_id}") or {"rows":[]}
        st.dataframe(pd.DataFrame(flat.get("rows", [])), use_container_width=True, hide_index=True)

def render_tab_photo_refinement(core_base: str, photo_base: str, user_id: str):
    st.caption("Enable calls when your Photo service is running.")
    enable_actions = st.toggle("Enable actions", value=False, key="tab7_enable_actions")
    colL, colR = st.columns([2,3])
    with colL:
        upl = st.file_uploader("Upload portrait (optional)", type=["jpg","jpeg","png"], key="tab7_file")
        if upl and enable_actions:
            st.info("POST to photo service here (wire when available).")
        elif upl:
            st.info("Actions disabled. File not sent.")
    with colR:
        st.subheader("Photo-derived traits (placeholder)")
        st.info("Wire to Core /traits/derived or similar when available.")

def render_tab_avatar(core_base: str, photo_base: str, user_id: str):
    st.caption("Enable calls when your Avatar service is running.")
    enable_actions = st.toggle("Enable actions", value=False, key="tab8_enable_actions")
    colL, colR = st.columns([2,3])
    with colL:
        st.info("GET/POST to /pa_outbound/* when available.")
    with colR:
        st.subheader("PaDNA snapshot")
        flat = safe_get(f"{core_base}/resolved/flat/{user_id}") or {"rows":[]}
        st.dataframe(pd.DataFrame(flat.get("rows", [])), use_container_width=True, hide_index=True)