# UCN_RR_Demo/ucnrr_ui.py
# -------------------------------------------------------------------
# UCN/RR Operator UI:
#  - Lists per-user folders under ./data/users/
#  - Opens the latest bundle for a selected user
#  - Lets you tweak common traits (eye/hair/skin/height/etc.)
#  - Recomputes RR (same safe coverage metric used by the API placeholder)
#  - Saves a new timestamped bundle back to the user's folder
#  - Exports the current bundle to Core via the local API proxy (/core/save)
#
# Run:
#   streamlit run ucnrr_ui.py
# Requirements:
#   - UCN/RR API running on localhost:8011 (uvicorn app:app --reload --port 8011)
#   - Core API running on localhost:8010
# -------------------------------------------------------------------
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

try:
    import requests
except Exception:
    requests = None

ROOT = Path(__file__).resolve().parent
USERS_DIR = ROOT / "data" / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)

UCNRR_API = "http://localhost:8011"  # change in sidebar if needed

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ts_name(prefix: str="bundle") -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

def latest_json_in(folder: Path) -> Optional[Path]:
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None

def compute_rr(bundle: Dict[str, Any]) -> float:
    traits = ((bundle.get("Prefs") or {}).get("traits")) or {}
    filled = sum(1 for _, v in traits.items() if v not in (None, "", [], {}))
    score = 5.0 * min(filled, 10) + 1.0 * max(filled - 10, 0)
    return max(0.0, min(100.0, score))

def load_latest(user_id: str) -> Dict[str, Any]:
    p = USERS_DIR / user_id
    f = latest_json_in(p)
    if not f:
        raise FileNotFoundError(f"No bundle found for {user_id}")
    return json.loads(f.read_text())

def save_new_version(user_id: str, bundle: Dict[str, Any]) -> str:
    p = USERS_DIR / user_id
    p.mkdir(parents=True, exist_ok=True)
    out = p / ts_name()
    out.write_text(json.dumps(bundle, indent=2))
    return out.name

def export_to_core(env: str, user_id: str, bundle: Dict[str, Any], api_base: str) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests not available in this environment")
    url = api_base.rstrip("/") + "/core/save"  # proxy from UCN/RR → Core
    r = requests.post(url, json={"env": env, "user_id": user_id, "bundle": bundle}, timeout=8)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status": r.status_code, "text": r.text}
    if r.status_code != 200 or not data.get("ok"):
        raise RuntimeError(f"core/save failed: {data}")
    return data

def safe_get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def safe_set(d: Dict[str, Any], path: str, value):
    cur = d
    parts = path.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value

# ---- UI ----
st.set_page_config(page_title="UCN/RR Operator UI", page_icon="🧭", layout="wide")
st.title("UCN/RR Operator UI")
st.caption("Inspect, tweak, recompute, and export bundles from the staging yard to Core.")

with st.sidebar:
    st.subheader("Connections")
    UCN_RR = st.text_input("UCN/RR API", UCNRR_API)
    ENV = st.text_input("Environment", "dev")

    # Discover users
    users = sorted([p.name for p in USERS_DIR.iterdir() if p.is_dir()])
    user_id = st.selectbox("User", users) if users else None

    st.markdown("---")
    st.caption(f"Data dir: {USERS_DIR}")

if not users:
    st.info("No users found yet. Save a bundle from Explorer first.")
    st.stop()

if not user_id:
    st.warning("Pick a user in the sidebar.")
    st.stop()

colL, colR = st.columns([0.6, 0.4])

with colL:
    st.subheader(f"User: {user_id}")
    try:
        bundle = load_latest(user_id)
    except Exception as e:
        st.error(str(e))
        st.stop()

    traits = (bundle.get("Prefs") or {}).get("traits") or {}

    # Editable traits
    st.write("### Traits")
    eye = st.selectbox("Eye color", ["", "blue", "brown", "green", "hazel", "gray", "amber"], index=0 if not traits.get("eye_color") else ["","blue","brown","green","hazel","gray","amber"].index(traits.get("eye_color","")))
    hair = st.text_input("Hair color", traits.get("hair_color", ""))
    skin = st.text_input("Skin tone", traits.get("skin_tone", ""))
    height = st.text_input("Height", traits.get("height", ""))
    gender = st.selectbox("Gender", ["", "male", "female", "nonbinary", "other"], index=0 if not traits.get("gender") else ["","male","female","nonbinary","other"].index(traits.get("gender","")))
    orientation = st.selectbox("Orientation", ["", "straight", "gay", "bi", "queer", "other"], index=0 if not traits.get("orientation") else ["","straight","gay","bi","queer","other"].index(traits.get("orientation","")))
    rel = st.selectbox("Relationship status", ["", "single", "in_a_relationship", "married", "complicated"], index=0 if not traits.get("relationship_status") else ["","single","in_a_relationship","married","complicated"].index(traits.get("relationship_status","")))
    love = st.selectbox("Love language", ["", "quality_time", "acts_of_service", "words_of_affirmation", "physical_touch", "receiving_gifts"],
                        index=0 if not traits.get("love_language_pref") else ["","quality_time","acts_of_service","words_of_affirmation","physical_touch","receiving_gifts"].index(traits.get("love_language_pref","")))

    # Apply changes to a working copy
    edited = json.loads(json.dumps(bundle))  # deep copy
    mapping = {
        "Prefs.traits.eye_color": eye or None,
        "Prefs.traits.hair_color": hair or None,
        "Prefs.traits.skin_tone": skin or None,
        "Prefs.traits.height": height or None,
        "Prefs.traits.gender": gender or None,
        "Prefs.traits.orientation": orientation or None,
        "Prefs.traits.relationship_status": rel or None,
        "Prefs.love_language_pref": love or None,
    }
    for k, v in mapping.items():
        if v is None or v == "":
            continue
        safe_set(edited, k, v)

    # Recompute RR (local placeholder) and attach provenance entry
    if st.button("Recompute RR (local)"):
        rr = compute_rr(edited)
        edited.setdefault("scores", {})
        edited["scores"]["rr_overall"] = rr
        edited.setdefault("provenance", []).append(
            {"at": iso_now(), "path": "scores.rr_overall", "value": rr, "source": "ucnrr-ui-local"}
        )
        st.success(f"RR updated ≈ {rr:.1f}")

    # Save new version under the user's folder
    if st.button("Save New Version to UCN/RR staging"):
        fn = save_new_version(user_id, edited)
        st.success(f"Saved: {fn}")

    st.write("### Current bundle (editable copy shown)")
    st.json(edited)

with colR:
    st.subheader("Summary")
    scores = (bundle.get("scores") or {})
    st.metric("RR (current)", None if scores.get("rr_overall") is None else round(float(scores["rr_overall"]), 1))
    st.caption("Raw (current latest on disk)")
    st.json(bundle)

    st.markdown("---")
    st.subheader("Export to Core")
    st.caption("Sends the edited bundle via UCN/RR API → Core API.")
    if st.button("Export edited bundle to Core"):
        try:
            res = export_to_core(env=ENV, user_id=user_id, bundle=edited, api_base=UCN_RR)
            st.success(f"Exported to Core ✓  core_id={res.get('core_id')}")
        except Exception as e:
            st.error(f"Export failed: {e}")

st.caption("Tip: Keep this UI open while Explorer saves new bundles; refresh the User list via sidebar if needed.")