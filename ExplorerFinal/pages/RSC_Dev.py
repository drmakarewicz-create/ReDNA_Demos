"""Transactional Relationship Synergy Coach dev surface."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import streamlit as st

from ExplorerFinal.ui.nav import render_rsc_disabled_banner

try:
    from ReDNACoreDemo.rsc import transactions as rsc_tx
except Exception as exc:  # pragma: no cover - surface unavailable
    st.error(f"RSC transactions module unavailable: {exc}")
    st.stop()

PERSONA_DEV_TABS = os.getenv("PERSONA_DEV_TABS", "false").strip().lower() in {"1", "true", "yes", "on"}

if not PERSONA_DEV_TABS:
    st.warning("Persona dev tabs are disabled. Set PERSONA_DEV_TABS=true to access RSC dev tools.")
    st.stop()

st.set_page_config(page_title="RSC Dev", layout="wide")

if render_rsc_disabled_banner():
    if hasattr(st, "page_link"):
        st.page_link("../ExplorerDev/explorer_dev.py", label="Open Dev Explorer", icon="🛠️")
    else:
        st.link_button("Open Dev Explorer", "../ExplorerDev/explorer_dev.py")
    st.stop()
st.title("🤝 Relationship Synergy Coach Dev")

st.caption(
    "Create short-term RSC sessions, test consent flow, and inspect shared micro-action feeds."
)

# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------
st.subheader("Create transactional RSC")
with st.form("create_rsc_form"):
    creator_id = st.text_input("Creator user id", value="user_alpha")
    partner_id = st.text_input("Partner user id", value="user_beta")
    scope = st.selectbox(
        "Scope",
        [
            "first_date",
            "trust_building",
            "purchase_planning",
            "conflict_debrief",
        ],
        index=0,
    )
    expiry_minutes = st.slider("Expiry (minutes)", 15, 7 * 24 * 60, 180, step=15)
    honesty_ceiling = st.selectbox("Honesty ceiling", ["gentle", "balanced", "direct", "candid"], index=1)
    partner_focus = st.text_input(
        "Shared context (masked)",
        value="Focus on __PARTNER_NAME__ feeling heard during check-ins.",
    )
    submitted = st.form_submit_button("Create session")
    if submitted:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
            session = rsc_tx.create_transaction_rsc(
                creator_id,
                partner_id,
                scope,
                expires_at,
                honesty_ceiling,
                shared_context={"focus": partner_focus},
            )
            st.success(
                f"Created session {session.session_id} with consent token {session.consent_token}"
            )
            st.experimental_rerun()
        except Exception as exc:  # pragma: no cover - guard for runtime errors
            st.error(f"Failed to create session: {exc}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Existing sessions overview
# ---------------------------------------------------------------------------
sessions = rsc_tx.list_sessions()
if not sessions:
    st.info("No RSC sessions yet. Create one to inspect consent flows.")
    st.stop()

session_map: Dict[str, rsc_tx.RscSession] = {
    f"{s.session_id} | scope={s.scope} | accepted={s.accepted}": s for s in sessions
}

selected_label = st.selectbox("Active session", list(session_map.keys()), index=len(session_map) - 1)
active_session = session_map[selected_label]

snapshot = rsc_tx.session_snapshot(active_session.session_id)
cols = st.columns([2, 2])
with cols[0]:
    st.markdown("**Session details**")
    st.json(
        {
            "session_id": snapshot["session_id"],
            "creator_id": snapshot["creator_id"],
            "partner_id": snapshot["partner_id"],
            "scope": snapshot["scope"],
            "expires_at": snapshot["expires_at"],
            "accepted": snapshot["accepted"],
            "revoked": snapshot.get("revoked", False),
            "honesty_ceiling": snapshot["honesty_ceiling"],
            "expired": snapshot.get("expired"),
        },
        expanded=False,
    )
with cols[1]:
    st.markdown("**Shared context preview**")
    st.json(snapshot.get("shared_context", {}), expanded=False)

st.markdown("**Consent token**: `{}'".format(active_session.consent_token))

# ---------------------------------------------------------------------------
# Consent & lifecycle controls
# ---------------------------------------------------------------------------
ctl_cols = st.columns(4)
with ctl_cols[0]:
    accept_user = st.text_input("Partner accepting user id", value=active_session.partner_id)
with ctl_cols[1]:
    accept_token = st.text_input("Consent token", value=active_session.consent_token)
with ctl_cols[2]:
    if st.button("Accept session", use_container_width=True):
        try:
            rsc_tx.accept_rsc(active_session.session_id, accept_user, accept_token)
            st.success("Partner accepted the session.")
            st.experimental_rerun()
        except Exception as exc:
            st.error(str(exc))
with ctl_cols[3]:
    if st.button("Expire now", use_container_width=True):
        try:
            rsc_tx.expire_session(active_session.session_id)
            st.success("Session expired immediately.")
            st.experimental_rerun()
        except Exception as exc:
            st.error(str(exc))

revoke_reason = st.text_input("Revoke reason", value="boundary updated")
if st.button("Revoke session", type="secondary"):
    try:
        rsc_tx.revoke_session(active_session.session_id, active_session.creator_id, revoke_reason)
        st.warning("Session revoked by creator.")
        st.experimental_rerun()
    except Exception as exc:
        st.error(str(exc))

st.markdown("---")

# ---------------------------------------------------------------------------
# Micro-action feed
# ---------------------------------------------------------------------------
st.subheader("Shared micro-action feed")
feed = rsc_tx.shared_feed(active_session.session_id)
if feed:
    st.json(feed, expanded=False)
else:
    st.caption("No actions yet.")

st.markdown("**Post micro-action**")
feed_cols = st.columns([1, 1, 1])
with feed_cols[0]:
    author = st.text_input("Author id", value=active_session.creator_id)
with feed_cols[1]:
    honesty = st.selectbox("Honesty level", ["gentle", "balanced", "direct", "candid"], index=1)
with feed_cols[2]:
    action_text = st.text_input("Micro-action text", value="Ask for their highlight of the day.")

if st.button("Post action", use_container_width=True):
    try:
        rsc_tx.post_micro_action(
            active_session.session_id,
            author,
            {"type": "prompt", "text": action_text},
            honesty_level=honesty,
        )
        st.success("Action logged.")
        st.experimental_rerun()
    except Exception as exc:
        st.error(str(exc))

st.markdown("---")

st.caption(
    "Honesty ceiling is enforced on every action. Shared context masks the token `__PARTNER_NAME__` to prevent attribution leaks."
)
