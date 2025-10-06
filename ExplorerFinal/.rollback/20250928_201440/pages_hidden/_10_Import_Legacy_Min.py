# ExplorerFinal/pages/10_Import_Legacy_Min.py
import os, json
import streamlit as st
import requests

st.set_page_config(page_title="Import Legacy (minimal)", page_icon="🧪", layout="centered")

DEFAULT_CORE = os.environ.get("CORE_URL") or st.secrets.get("core_url", "http://127.0.0.1:8015")
st.caption(f"Core: {DEFAULT_CORE}")

st.header("Import Legacy (minimal)")

with st.form("ingest"):
    col1, col2 = st.columns(2)
    with col1:
        user_id = st.text_input("User ID", value="TEST")
        legacy_key = st.selectbox("Legacy Key", ["Eye Color", "Hair Color", "Freckles"])
        value = st.text_input("Value", value="blue")
    with col2:
        confidence = st.slider("Confidence", 0.0, 1.0, 0.60, 0.01)
        source = st.selectbox("Source", ["imported", "human", "file"])
    submitted = st.form_submit_button("Submit Entry")

if submitted:
    try:
        payload = {
            "user_id": user_id,
            "legacy_key": legacy_key,
            "value": value,
            "confidence": confidence,
            "source": source,
        }
        r = requests.post(f"{DEFAULT_CORE}/v1/ingest", json=payload, timeout=10)
        if r.ok:
            st.success("Ingest OK")
            st.json(r.json())
        else:
            st.error(f"Ingest failed: {r.status_code}")
            st.code(r.text, language="json")
    except Exception as e:
        st.error(f"Request error: {e}")

st.divider()
st.subheader("Resolved cache")

if st.button("Refresh resolved"):
    try:
        rr = requests.get(f"{DEFAULT_CORE}/v1/resolved/{user_id}", timeout=10)
        if rr.ok:
            st.json(rr.json())
        else:
            st.error(f"Resolved fetch failed: {rr.status_code}")
            st.code(rr.text, language="json")
    except Exception as e:
        st.error(f"Request error: {e}")