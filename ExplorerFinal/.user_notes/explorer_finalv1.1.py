# ExplorerFinal/explorer_final.py
# Streamlit Explorer that talks to UCN/RR and shows Core-resolved snapshot.
import streamlit as st
import requests, os, json
from pathlib import Path

st.set_page_config(page_title="ReDNA • Explorer", layout="wide")

# ---- Config ----
UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011")
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015")
USR_FILE   = Path(__file__).resolve().parent / ".users.json"

def load_users():
    try:
        return json.loads(USR_FILE.read_text())
    except Exception:
        return ["demo_user"]

def save_users(u):
    USR_FILE.write_text(json.dumps(u, indent=2))

users = load_users()

st.sidebar.header("explorer final")
st.sidebar.caption("Import Legacy Min")

# User pick / add / delete
curr = st.sidebar.selectbox("User", users, index=0)
new_user = st.sidebar.text_input("Add new user")
colA, colB = st.sidebar.columns(2)
if colA.button("Add", use_container_width=True) and new_user.strip():
    if new_user not in users:
        users.insert(0, new_user.strip())
        save_users(users)
    st.rerun()
if colB.button("Delete user", use_container_width=True):
    if curr in users:
        users.remove(curr)
        save_users(users)
    st.rerun()

# status lights
def ping(url):
    try:
        r = requests.get(url, timeout=3)
        return r.ok
    except Exception:
        return False

st.sidebar.markdown("---")
c1, c2 = st.sidebar.columns(2)
c1.metric("UCN/RR", "UP" if ping(f"{UCNRR_BASE}/health") else "DOWN")
c2.metric("Core",   "UP" if ping(f"{CORE_BASE}/health") else "DOWN")
st.sidebar.markdown(f"UCNRR_BASE =\n[{UCNRR_BASE}]({UCNRR_BASE})")

st.title("🧬 ReDNA • Explorer")

# --- Legacy Import ---
st.subheader("Legacy Import")
lcol1, lcol2, lcol3 = st.columns([2,2,1])
legacy_key = lcol1.text_input("Legacy key (dot path)", value="PaDNA.LooksDNA.EyeDNA.IrisColor")
legacy_val = lcol2.text_input("Legacy value", value="Blue")
if lcol3.button("Import"):
    try:
        r = requests.post(f"{UCNRR_BASE}/legacy_import", json={"user_id": curr, "legacy_key": legacy_key, "legacy_value": legacy_val}, timeout=20)
        r.raise_for_status()
        st.success("Ingest OK and recomputed.")
    except Exception as e:
        st.error(f"Ingest failed: {e}")

# --- Free-text ingest ---
st.subheader("Free-text Ingest")
txt = st.text_area("Describe yourself", height=120, value="I am bald and the hair I have left is reddish.")
if st.button("Submit text"):
    try:
        r = requests.post(f"{UCNRR_BASE}/ingest_text", json={"user_id": curr, "text": txt}, timeout=20)
        r.raise_for_status()
        st.success("Text ingested and processed.")
    except Exception as e:
        st.error(f"Ingest failed: {e}")

# --- Resolved snapshot viewer (from Core) ---
st.subheader("Resolved Snapshot")
try:
    res = requests.get(f"{CORE_BASE}/health", timeout=5)
    if res.ok:
        # read the on-disk resolved.json directly for reliability
        core_data_dir = Path(os.getenv("CORE_DATA_DIR", Path(__file__).parents[1] / "ReDNACoreDemo" / "data"))
        resolved_path = core_data_dir / "users" / curr / "resolved.json"
        if resolved_path.exists():
            st.code(resolved_path.read_text(), language="json")
        else:
            st.code(json.dumps({"info": "no resolved data"}, indent=2), language="json")
    else:
        st.warning("Core health not OK.")
except Exception as e:
    st.error(f"Snapshot error: {e}")

# --- UCN/RR debugger ---
with st.expander("🧪 UCN/RR Debugger", expanded=False):
    st.caption(f"UCNRR_BASE = {UCNRR_BASE}")
    test_text = st.text_input("Test text", value="I am bald and the hair I have left is reddish.")
    if st.button("POST /ingest_text (debug)"):
        try:
            r = requests.post(f"{UCNRR_BASE}/ingest_text", json={"user_id": curr, "text": test_text}, timeout=20)
            st.code(json.dumps(r.json(), indent=2), language="json")
        except Exception as e:
            st.error(f"/ingest_text failed: {e}")