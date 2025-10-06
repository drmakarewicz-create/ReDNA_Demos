# ReDNACoreDemo/core_ui.py
# -------------------------------------------------------------------
# Core Operator UI:
#  - Lists per-user folders under ./data/checkpoints/
#  - Opens the latest bundle for a selected user
#  - Lets you tweak common traits (eye/hair/skin/height/etc.)
#  - Saves a new timestamped bundle back into Core checkpoints
#  - (Phase 3) Exports the edited bundle back to UCN/RR (staging) so it
#    can be recomputed and/or returned to Explorer.
#
# Run:
#   streamlit run core_ui.py
#
# Requirements:
#   - Core API can be running separately on 8010 (not required for this UI).
#   - UCN/RR API on 8011 if you want to use "Export to UCN/RR".
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
CHECKPOINTS = ROOT / "data" / "checkpoints"
CHECKPOINTS.mkdir(parents=True, exist_ok=True)

DEFAULT_UCNRR_API = "http://localhost:8011"


# ---------- helpers ----------
def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ts_name(prefix: str="bundle") -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

def latest_json_in(folder: Path) -> Optional[Path]:
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None

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

def deep_copy(obj: Any) -> Any:
    return json.loads(json.dumps(obj))

def load_latest(user_id: str) -> Dict[str, Any]:
    user_dir = CHECKPOINTS / user_id
    f = latest_json_in(user_dir)
    if not f:
        raise FileNotFoundError(f"No bundle found for {user_id}")
    return json.loads(f.read_text())

def save_new_version(user_id: str, bundle: Dict[str, Any]) -> str:
    user_dir = CHECKPOINTS / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    out = user_dir / ts_name()
    out.write_text(json.dumps(bundle, indent=2))
    return out.name

def export_to_ucnrr(env: str, user_id: str, bundle: Dict[str, Any], ucnrr_base: str) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests module not available")
    url = ucnrr_base.rstrip("/") + "/gateway/save"
    r = requests.post(url, json={"env": env, "user_id": user_id, "bundle": bundle}, timeout=8)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status": r.status_code, "text": r.text}
    if r.status_code != 200 or not data.get("ok"):
        raise RuntimeError(f"UCN/RR gateway/save failed: {data}")
    return data


# ---------- UI ----------
st.set_page_config(page_title="Core Operator UI", page_icon="📦", layout="wide")
st.title("Core Operator UI")
st.caption("View, edit, and version bundles stored in Core checkpoints. Optional: export edited bundles back to UCN/RR.")

with st.sidebar:
    st.subheader("Folders & Connections")
    st.caption(f"Checkpoints dir:\n`{CHECKPOINTS}`")

    # Discover users (each subfolder is a user)
    users = sorted([p.name for p in CHECKPOINTS.iterdir() if p.is_dir()])
    if not users:
        st.info("No users found yet. Export from UCN/RR to Core first.")
        st.stop()

    user_id = st.selectbox("User", users, index=0)
    ENV = st.text_input("Environment", "dev")

    st.markdown("---")
    st.subheader("Phase 3 bridge")
    UCNRR_API = st.text_input("UCN/RR API base", DEFAULT_UCNRR_API)
    st.caption("Use this to send the edited bundle back to UCN/RR staging.")

# Load latest bundle for the selected user
try:
    current = load_latest(user_id)
except Exception as e:
    st.error(str(e))
    st.stop()

# Work on a copy so you can compare vs current
edited = deep_copy(current)
traits = (edited.get("Prefs") or {}).get("traits") or {}

left, right = st.columns([0.6, 0.4])

with left:
    st.subheader(f"User: {user_id}")
    st.write("### Edit Traits")

    # Common editable fields
    eye = st.selectbox(
        "Eye color",
        ["", "blue", "brown", "green", "hazel", "gray", "amber"],
        index=0 if not traits.get("eye_color") else ["","blue","brown","green","hazel","gray","amber"].index(traits.get("eye_color",""))
    )
    hair = st.text_input("Hair color", traits.get("hair_color", ""))
    skin = st.text_input("Skin tone", traits.get("skin_tone", ""))
    height = st.text_input("Height", traits.get("height", ""))
    gender = st.selectbox(
        "Gender",
        ["", "male", "female", "nonbinary", "other"],
        index=0 if not traits.get("gender") else ["","male","female","nonbinary","other"].index(traits.get("gender",""))
    )
    orientation = st.selectbox(
        "Orientation",
        ["", "straight", "gay", "bi", "queer", "other"],
        index=0 if not traits.get("orientation") else ["","straight","gay","bi","queer","other"].index(traits.get("orientation",""))
    )
    rel = st.selectbox(
        "Relationship status",
        ["", "single", "in_a_relationship", "married", "complicated"],
        index=0 if not traits.get("relationship_status") else ["","single","in_a_relationship","married","complicated"].index(traits.get("relationship_status",""))
    )
    love = st.selectbox(
        "Love language",
        ["", "quality_time", "acts_of_service", "words_of_affirmation", "physical_touch", "receiving_gifts"],
        index=0 if not traits.get("love_language_pref") else ["","quality_time","acts_of_service","words_of_affirmation","physical_touch","receiving_gifts"].index(traits.get("love_language_pref",""))
    )

    # Apply edits
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

    # Optional provenance append
    if st.checkbox("Append provenance for these edits", value=True):
        edited.setdefault("provenance", []).append(
            {
                "at": iso_now(),
                "path": "Prefs.traits.* (multiple)",
                "value": {k: v for k, v in mapping.items() if v not in (None, "")},
                "source": "core-operator-ui",
            }
        )

    # Save a new checkpoint file in Core
    if st.button("Save New Version to Core checkpoints"):
        fn = save_new_version(user_id, edited)
        st.success(f"Saved: {fn}")

    st.write("### Edited bundle (preview)")
    st.json(edited)

with right:
    st.subheader("Current (latest in Core)")
    scores_now = (current.get("scores") or {})
    st.metric("RR (as stored)", None if scores_now.get("rr_overall") is None else round(float(scores_now["rr_overall"]), 1))
    st.json(current)

    st.markdown("---")
    st.subheader("Export to UCN/RR (Phase 3)")
    st.caption("Sends the **edited** bundle to UCN/RR → it will appear in UCN_RR_Demo/data/users/<user_id>/")
    if st.button("Export edited bundle to UCN/RR staging"):
        try:
            res = export_to_ucnrr(env=ENV, user_id=user_id, bundle=edited, ucnrr_base=UCNRR_API)
            st.success(f"Exported to UCN/RR ✓  ucnrr_id={res.get('ucnrr_id')}")
        except Exception as e:
            st.error(f"Export failed: {e}")

st.caption("Tip: After exporting to UCN/RR, open the UCN/RR Operator UI to recompute RR or send the result back to Explorer.")