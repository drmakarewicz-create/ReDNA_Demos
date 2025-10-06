# app.py
# SingleCoach Demo (ReDNA / RSC)
# -----------------------------------------------------------
# Updates in this version:
# - Quick Actions moved into the SIDEBAR to avoid breaking the chat flow.
# - Each action has a clear help tooltip describing what it does.
# - Optional compact Quick Actions row beneath the input (OFF by default).
#
# What this demo shows
# - Per-issue (topic-specific) camouflage + follow-up depth
# - Intake with name/pronouns (Jordan, Alex, etc.)
# - Conversational window (Statement -> Response -> Response-to-Response...)
# - Llama3 via Ollama by default; easy switch to OpenAI later
# - No watchdog required
#
# How to run
#   pip install streamlit requests
#   streamlit run app.py
#
# Ollama defaults (local):
#   - Ensure `ollama serve` is running and you've pulled a model:
#       ollama pull llama3
#   - The app will POST to http://localhost:11434/api/chat
#
# To switch to OpenAI later:
#   - Set PROVIDER="openai" in the UI or via env var
#   - Provide OPENAI_API_KEY in the sidebar
#   - Choose a model (e.g., gpt-4o-mini or gpt-4.1)
# -----------------------------------------------------------

import os
import time
from typing import Dict, List
import requests
import streamlit as st

# ----------------------------
# Constants & Small Utilities
# ----------------------------

DEFAULT_PROVIDER = os.environ.get("PROVIDER", "ollama")  # 'ollama' or 'openai'
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

CAMOUFLAGE_OPTIONS = [
    ("Direct / Plain", "direct"),
    ("Polite / Softened", "soft"),
    ("Heavily Camouflaged", "heavy")
]

FOLLOWUP_DEPTH_OPTIONS = [
    ("Keep it high-level", "shallow"),
    ("Probe a bit", "medium"),
    ("Go deep until I say stop", "deep")
]

PRONOUN_CHOICES = [
    ("she/her", "she/her"),
    ("he/him", "he/him"),
    ("they/them", "they/them")
]

def ensure_state():
    ss = st.session_state
    ss.setdefault("provider", DEFAULT_PROVIDER)
    ss.setdefault("ollama_model", DEFAULT_OLLAMA_MODEL)
    ss.setdefault("openai_model", DEFAULT_OPENAI_MODEL)
    ss.setdefault("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

    # Intake & identities
    ss.setdefault("coach_name", "SingleCoach")
    ss.setdefault("user_name", "Alex")
    ss.setdefault("partner_name", "Jordan")
    ss.setdefault("partner_pronouns", "she/her")  # default per your note
    ss.setdefault("intake_confirmed", False)

    # Issues (topic -> settings)
    ss.setdefault("topics", {})  # {topic: {"camouflage": "soft", "depth": "medium", "history": []}}
    ss.setdefault("current_topic", "")
    ss.setdefault("pending_probe", False)

    # UI options
    ss.setdefault("show_compact_actions", False)

def pronoun_parts(pronouns: str):
    if pronouns == "she/her":
        return {"subj": "she", "obj": "her", "poss": "her", "poss_pron": "hers"}
    if pronouns == "he/him":
        return {"subj": "he", "obj": "him", "poss": "his", "poss_pron": "his"}
    return {"subj": "they", "obj": "them", "poss": "their", "poss_pron": "theirs"}

# ----------------------------
# LLM Clients
# ----------------------------

def call_ollama(model: str, messages: List[Dict], temperature: float = 0.5, top_p: float = 0.9) -> str:
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature, "top_p": top_p},
        "stream": False
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"(Ollama error: {e}). Tip: ensure `ollama serve` is running and the model '{model}' is pulled."

def call_openai(model: str, messages: List[Dict], api_key: str, temperature: float = 0.5, top_p: float = 0.9) -> str:
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = "https://api.openai.com/v1/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": temperature, "top_p": top_p}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(OpenAI error: {e}). Double-check API key and model."

def chat_complete(messages: List[Dict], temperature: float = 0.5) -> str:
    ss = st.session_state
    if ss["provider"] == "openai":
        if not ss["openai_api_key"]:
            return "(OpenAI API key missing. Enter it in the sidebar.)"
        return call_openai(ss["openai_model"], messages, ss["openai_api_key"], temperature=temperature)
    return call_ollama(ss["ollama_model"], messages, temperature=temperature)

# ----------------------------
# Prompting & History
# ----------------------------

def system_coach_instructions(topic: str, camouflage: str, depth: str) -> str:
    style_map = {
        "direct": "Be clear, candid, and unambiguous. Use plain language and gently assertive tone.",
        "soft": "Be kind and diplomatic. Cushion difficult points, preserve face, and avoid triggering defensiveness.",
        "heavy": "Heavily camouflage sensitive points with euphemisms, indirect suggestions, and affirmations before critique."
    }
    depth_map = {
        "shallow": "Address the surface concern and offer one actionable next step. Do not probe further unless asked.",
        "medium": "Offer a thoughtful response and ask 1–2 gentle, specific follow-up questions to clarify willingness to go deeper.",
        "deep": "Probe iteratively in a short loop, asking targeted follow-ups until the user indicates they want to stop."
    }
    return f"""
You are SingleCoach, a relationship specialist coach inside the ReDNA demo.
Topic: "{topic}"
Camouflage stance: {camouflage.upper()} -> {style_map.get(camouflage, "")}
Follow-up depth: {depth.upper()} -> {depth_map.get(depth, "")}

Rules:
- Always respect the speaker's goals and consent.
- Before delivering sensitive feedback, preface with a quick empathy frame that matches the camouflage stance.
- Keep responses concise and practical. Offer examples of phrasing a message.
- If depth=deep, end your response with a short, respectful probe that invites another turn, unless the user says stop.
- Use the partner's chosen pronouns correctly throughout.
"""

def get_topic_state(topic: str) -> Dict:
    ss = st.session_state
    if topic not in ss["topics"]:
        ss["topics"][topic] = {"camouflage": "soft", "depth": "medium", "history": []}
    return ss["topics"][topic]

def set_topic_settings(topic: str, camouflage: str, depth: str):
    ss = st.session_state
    _ = get_topic_state(topic)
    ss["topics"][topic]["camouflage"] = camouflage
    ss["topics"][topic]["depth"] = depth

def push_history(topic: str, role: str, content: str):
    ss = st.session_state
    state = get_topic_state(topic)
    state["history"].append({"role": role, "content": content, "ts": time.time()})

def build_messages_for_model(topic: str, user_turn: str) -> List[Dict]:
    ss = st.session_state
    coach_name = ss["coach_name"]
    user_name = ss["user_name"]
    partner_name = ss["partner_name"]

    sys = system_coach_instructions(topic, ss["topics"][topic]["camouflage"], ss["topics"][topic]["depth"])
    sys += f"\nPartner: {partner_name} ({ss['partner_pronouns']}). Use pronouns accurately.\n"
    sys += f"Speaker is {user_name}. Address them respectfully and succinctly as a professional coach.\n"
    sys += "When offering sample phrasing to say to the partner, put it in quotes.\n"

    recent = ss["topics"][topic]["history"][-6:]
    messages = [{"role": "system", "content": sys}]
    for msg in recent:
        role = "assistant" if msg["role"] == "coach" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_turn})
    return messages

def coach_reply(topic: str, user_turn: str) -> str:
    messages = build_messages_for_model(topic, user_turn)
    return chat_complete(messages, temperature=0.6)

def render_transcript(history: List[Dict]):
    for msg in history:
        with st.chat_message("assistant" if msg["role"] == "coach" else "user"):
            st.markdown(msg["content"])

# ----------------------------
# UI
# ----------------------------

st.set_page_config(page_title="SingleCoach Demo • ReDNA", page_icon="🧭", layout="wide")
ensure_state()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## ⚙️ Demo Settings")
    st.selectbox("LLM Provider", ["ollama", "openai"],
                 index=0 if st.session_state["provider"] == "ollama" else 1, key="provider")
    if st.session_state["provider"] == "ollama":
        st.text_input("Ollama model", key="ollama_model")
        st.caption("Tip: `ollama pull llama3` then run `ollama serve`.")
    else:
        st.text_input("OpenAI API Key", type="password", key="openai_api_key")
        st.text_input("OpenAI model", key="openai_model")

    st.checkbox("Show compact Quick Actions under input", key="show_compact_actions",
                help="When ON, a small row of actions appears under the chat input. "
                     "By default actions live only here in the sidebar.")

    st.markdown("---")
    with st.expander("💡 Quick Actions", expanded=True):
        st.caption("One-click prompts that send a short instruction to your coach for this topic.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Suggest phrasing",
                         help="Asks the coach to propose 2–3 short, copy-ready messages to send to your partner, "
                              "matching the current camouflage stance."):
                topic = st.session_state.get("current_topic", "")
                if topic:
                    prompt = 'Please propose 2–3 short example messages I could send to my partner about this topic, reflecting the camouflage stance.'
                    push_history(topic, "user", prompt)
                    push_history(topic, "coach", coach_reply(topic, prompt))
                    st.rerun()
        with c2:
            if st.button("Should we go deeper?",
                         help="Asks the coach if deeper exploration is recommended now. "
                              "If yes, it will ask 2 targeted but respectful questions."):
                topic = st.session_state.get("current_topic", "")
                if topic:
                    prompt = "Given my last few messages, do you recommend going deeper on this topic right now? If yes, ask me 2 targeted but respectful questions."
                    push_history(topic, "user", prompt)
                    push_history(topic, "coach", coach_reply(topic, prompt))
                    st.rerun()
        c3, c4 = st.columns(2)
        with c3:
            if st.button("Action steps",
                         help="Summarizes the discussion into 1–2 concrete next steps aligned with the current stance."):
                topic = st.session_state.get("current_topic", "")
                if topic:
                    prompt = "Please summarize this into 1–2 concrete next steps I can take this week, aligned with the camouflage stance."
                    push_history(topic, "user", prompt)
                    push_history(topic, "coach", coach_reply(topic, prompt))
                    st.rerun()
        with c4:
            st.caption("Adjust stance in the main panel under Topic settings.")

    st.markdown("---")
    st.markdown("### Quick Help")
    st.caption(
        "- Camouflage & Depth are **per issue**, not global.\n"
        "- Set Jordan’s pronouns in Intake, then pick or create a topic.\n"
        "- Use the chat box for natural back-and-forth; Quick Actions live here to stay out of your way."
    )

# ---------- MAIN ----------
st.title("SingleCoach • Relationship Specialist Demo")

# Intake
with st.expander("🔎 Intake (Names & Pronouns)", expanded=not st.session_state["intake_confirmed"]):
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.text_input("Your name", key="user_name")
        st.text_input("Partner name", key="partner_name")
    with c2:
        pron = st.selectbox("Partner pronouns", [p[1] for p in PRONOUN_CHOICES],
                            index=[p[1] for p in PRONOUN_CHOICES].index(st.session_state["partner_pronouns"]))
        st.session_state["partner_pronouns"] = pron
    with c3:
        st.text_input("Coach name", key="coach_name")
        st.checkbox("I confirm these details are correct", key="intake_confirmed")
    parts = pronoun_parts(st.session_state["partner_pronouns"])
    st.caption(f"Coach will refer to {st.session_state['partner_name']} as "
               f"{parts['subj']}/{parts['obj']} with possessives {parts['poss']}/{parts['poss_pron']}.")

# Topic selection
st.markdown("### 🎯 Issue / Topic")
topic_cols = st.columns([2, 1, 1])
with topic_cols[0]:
    existing = list(st.session_state["topics"].keys())
    selected = st.selectbox("Pick an existing topic or type a new one", existing + ["➕ Create new…"])
with topic_cols[1]:
    new_topic_name = st.text_input("If new, enter topic title", value="" if selected != "➕ Create new…" else "")
with topic_cols[2]:
    if st.button("Set Topic", use_container_width=True):
        chosen = new_topic_name.strip() if selected == "➕ Create new…" else selected
        if not chosen:
            st.warning("Enter a topic name or pick an existing one.")
        else:
            st.session_state["current_topic"] = chosen
            get_topic_state(chosen)

topic = st.session_state["current_topic"]
if not topic:
    st.info("Select or create a topic to begin (e.g., 'Housework expectations' or 'Intimacy concerns').")
    st.stop()

# Per-topic stance
st.markdown(f"#### Topic: **{topic}**")
state = get_topic_state(topic)
with st.container():
    s1, s2, s3 = st.columns([1.25, 1.25, 1])
    with s1:
        camo_label = st.selectbox("Camouflage stance (for this topic)",
                                  [c[0] for c in CAMOUFLAGE_OPTIONS],
                                  index=[c[1] for c in CAMOUFLAGE_OPTIONS].index(state["camouflage"]))
        camo_value = CAMOUFLAGE_OPTIONS[[c[0] for c in CAMOUFLAGE_OPTIONS].index(camo_label)][1]
    with s2:
        depth_label = st.selectbox("Follow-up depth (for this topic)",
                                   [d[0] for d in FOLLOWUP_DEPTH_OPTIONS],
                                   index=[d[1] for d in FOLLOWUP_DEPTH_OPTIONS].index(state["depth"]))
        depth_value = FOLLOWUP_DEPTH_OPTIONS[[d[0] for d in FOLLOWUP_DEPTH_OPTIONS].index(depth_label)][1]
    with s3:
        if st.button("Save Topic Settings", use_container_width=True, help="Applies the stance only to this topic."):
            set_topic_settings(topic, camo_value, depth_value)
            st.success("Saved per-topic stance.")

# Conversation
st.markdown("### 💬 Conversation")
render_transcript(state["history"])

# Chat input
st.markdown("#### Speak to your coach")
user_input = st.chat_input(f"Share your thought about '{topic}' (or reply to Coach)...")

# Compact quick actions under input (optional)
if st.session_state["show_compact_actions"]:
    cqa1, cqa2, cqa3 = st.columns(3)
    if cqa1.button("Suggest phrasing"):
        prompt = 'Please propose 2–3 short example messages I could send to my partner about this topic, reflecting the camouflage stance.'
        push_history(topic, "user", prompt); push_history(topic, "coach", coach_reply(topic, prompt)); st.rerun()
    if cqa2.button("Should we go deeper?"):
        prompt = "Given my last few messages, do you recommend going deeper on this topic right now? If yes, ask me 2 targeted but respectful questions."
        push_history(topic, "user", prompt); push_history(topic, "coach", coach_reply(topic, prompt)); st.rerun()
    if cqa3.button("Action steps"):
        prompt = "Please summarize this into 1–2 concrete next steps I can take this week, aligned with the camouflage stance."
        push_history(topic, "user", prompt); push_history(topic, "coach", coach_reply(topic, prompt)); st.rerun()

# Deep-mode hint
if state["depth"] == "deep":
    st.caption("🔁 Deep mode: Coach will keep probing until you say 'stop', 'that's enough', or change depth to shallow/medium.")

# Handle user turn
if user_input:
    push_history(topic, "user", user_input)
    lower = user_input.strip().lower()
    if any(w in lower for w in ["stop", "that's enough", "thats enough", "enough", "move on", "new topic"]):
        st.session_state["pending_probe"] = False
        coach_msg = "Got it. We can pause the deeper probing here. Would you like to capture an action step for this topic, or switch topics?"
        push_history(topic, "coach", coach_msg)
        st.rerun()

    reply = coach_reply(topic, user_input)
    push_history(topic, "coach", reply)
    if state["depth"] == "deep":
        st.session_state["pending_probe"] = True
    st.rerun()

# Footer
st.markdown("---")
st.caption(
    "Demo notes: Camouflage & Depth are **per topic** and adjustable anytime. "
    "Pronouns are clarified at intake and respected. "
    "Quick Actions live in the sidebar to keep the chat area clean."
)