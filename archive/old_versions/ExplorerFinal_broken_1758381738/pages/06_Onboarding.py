from ui.nav import side_nav, hide_default_sidebar
hide_default_sidebar()
side_nav(active="photo")          # or "padna" / "head_coach" / "onboarding"

import streamlit as st
from ui.session import user_picker, get_user_id
from ui.nav import top_tabs, side_nav

st.set_page_config(page_title="Onboarding", layout="wide")
top_tabs(active="onboarding")
side_nav(active="explorer")

st.title("🧾 Onboarding")
user_picker("Active user")
uid = get_user_id()
if not uid:
    st.warning("Pick a user to continue.")
    st.stop()

st.info("Onboarding wrapper page inside Explorer. Add onboarding steps here.")