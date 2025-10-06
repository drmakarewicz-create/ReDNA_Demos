# app.py — RSC Sandbox (follow-ups + individualized plans + rating slider)
import streamlit as st
from typing import List

st.set_page_config(page_title="RSC Sandbox", page_icon="🧑‍🤝‍🧑", layout="wide")

# -------------------------
# Presets & helpers
# -------------------------
PRESETS = {
    "u1": {  # Alex
        "name": "Alex",
        "intake": {
            "better_week": [
                "If Jordan would stop acting like she is repulsed by me",
                "More kisses on lips from Jordan",
                "Feeling more attractive to Jordan",
                "More quality time together",
                "Feeling appreciated by Jordan",
            ],
            "small_change": [
                "She could act like she is attracted to me",
                "Jordan to initiate physical contact occasionally",
                "Jordan to compliment me once a day",
                "Jordan to flirt more",
                "Jordan to be more affectionate",
            ],
            "boundaries": [
                "Not ignoring me for long periods when we're together",
                "No yelling during fights",
                "Avoid sarcasm when upset",
                "Respect my need for space sometimes",
                "Don’t dismiss my feelings",
            ],
            "style": ["gentle nudges", "direct"],
        },
    },
    "u2": {  # Jordan
        "name": "Jordan",
        "intake": {
                "better_week": [
                    "Alex should stop fighting with me all the time",
                    "Alex helping out with chores more",
                    "More peaceful time together",
                    "Less stress around the house",
                    "Feeling supported by Alex",
                ],
                "small_change": [
                    "Alex should help out around the house more",
                    "Alex should surprise me by doing chores I usually do",
                    "Alex should offer to pay for a manicure or self-care",
                    "Alex should say thank you more",
                    "Alex should plan a nice date without me asking",
                ],
                "boundaries": [
                    "Stop constantly whining about sex",
                    "No late-night heavy talks when tired",
                    "Don’t interrupt me when I’m working",
                    "Respect my need to unwind quietly sometimes",
                    "No raising voice during arguments",
                ],
                "style": ["gentle nudges", "direct"],
        },
    },
}

def get_state():
    if "intake" not in st.session_state:
        st.session_state.intake = {
            "u1": {"style": "gentle nudges", "rating": 6},
            "u2": {"style": "gentle nudges", "rating": 6},
        }
    if "plans" not in st.session_state:
        st.session_state.plans = {"u1": None, "u2": None}
    if "followups" not in st.session_state:
        st.session_state.followups = {"u1": [], "u2": []}
get_state()

def has_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)

def tone(style: str, gentle_text: str, direct_text: str) -> str:
    return gentle_text if style == "gentle nudges" else direct_text

# -------------------------
# Follow-up generation
# -------------------------
def generate_followups(answers: dict, user_name: str) -> List[str]:
    qs = []
    bw  = answers.get("better_week", "")
    sc  = answers.get("small_change", "")
    bnd = answers.get("boundaries", "")
    style = answers.get("style", "gentle nudges")
    rating = answers.get("rating", 6)

    # Affection / intimacy threads
    if has_any(bw+sc, ["kiss", "attract", "affection", "sex", "physical"]):
        qs += [
            f"{user_name}, when do you feel most open to affection during a typical day?",
            f"What kind of non-sexual touch feels easiest to give/receive right now?",
            "Would a short, predictable routine (e.g., daily hug + every-other-day kiss) feel good or forced?",
            "If you could change one thing in how intimacy is approached, what’s the smallest step?",
        ]
    # Chores / support threads
    if has_any(bw+sc, ["chore", "house", "help", "clean", "laundry", "dishes"]):
        qs += [
            "Which single task would reduce stress the most if handled consistently?",
            "When is the best time-of-day for a 10-minute cleanup together?",
            "How do you like appreciation to be expressed when a task gets done?",
            "What would a fair split look like for just this week?",
        ]
    # Conflict / tone
    if has_any(bw+bnd, ["yell", "fighting", "argue", "raise", "sarcasm"]):
        qs += [
            "What are early signs the conversation is getting hot for you?",
            "Which repair attempt works best for you (humor, brief pause, physical touch, ‘Can we reset?’)?",
        ]
    # Distance / ignoring
    if has_any(bw+bnd, ["ignore", "distant", "space", "alone"]):
        qs += [
            "If you’re needing space, what’s the clearest way to signal it kindly?",
            "What short check-in would help you feel less overlooked (word, gesture, emoji)?",
        ]
    # Base questions influenced by rating
    if rating <= 4:
        qs += [
            "What would make next week feel 10% lighter?",
            "What’s one micro-win we could design for tomorrow?",
        ]
    else:
        qs += [
            "What is already working that we can double down on this week?",
        ]

    # Style-specific probe
    qs.append(
        tone(style,
             "If we tried just one gentle experiment this week, what would you pick?",
             "If we made one decisive change this week, what would you commit to?")
    )

    # Normalize length 4–8
    # remove duplicates while preserving order
    seen = set()
    uniq = []
    for q in qs:
        if q not in seen:
            uniq.append(q); seen.add(q)
    if len(uniq) < 4:
        uniq += ["Is there context I’m missing that would change my guidance?",
                 "Which time-of-day naturally fits a 5-minute connection?"][:4-len(uniq)]
    return uniq[:8]

# -------------------------
# Plan generation
# -------------------------
def coach_plan(answers: dict, user_name: str) -> str:
    bw  = answers.get("better_week", "")
    sc  = answers.get("small_change", "")
    bnd = answers.get("boundaries", "")
    style = answers.get("style", "gentle nudges")
    rating = answers.get("rating", 6)

    wants_affection = has_any(bw+sc, ["kiss","attract","affection","sex","physical"])
    wants_help      = has_any(bw+sc, ["chore","house","help","clean","laundry","dishes","tidy"])
    conflict       = has_any(bw+bnd, ["yell","fighting","argue","raise","sarcasm"])

    lines = [f"Hi {user_name}, here’s a **tentative** 72-hour plan (we’ll adapt as new info arrives):"]

    # Day 1
    if wants_help:
        lines.append(
            tone(style,
                 "Day 1: choose one task your partner usually handles and quietly complete it today. No announcement needed; let appreciation happen naturally.",
                 "Day 1: take over one recurring task today. Do it fully without prompting.")
        )
    elif wants_affection:
        lines.append(
            tone(style,
                 "Day 1: start a tiny affection ritual (a warm 5-second hug on greeting + a light good-night kiss).",
                 "Day 1: initiate a 5-second greeting hug and a good-night kiss.")
        )
    else:
        lines.append("Day 1: schedule a 10-minute shared activity you both enjoy (walk, coffee, playlist).")

    # Day 2
    if wants_affection and wants_help:
        lines.append(
            "Day 2: combine both needs — do a small household favor, then invite a 10-minute wind-down together (couch chat, hand on shoulder, no phones)."
        )
    elif wants_affection:
        lines.append(
            tone(style,
                 "Day 2: say one sincere appreciation out loud (something specific that made you feel seen).",
                 "Day 2: state one concrete appreciation out loud. Keep it short and specific.")
        )
    elif wants_help:
        lines.append(
            tone(style,
                 "Day 2: ask for a micro-agreement: one 10-minute task at a set time. Keep the ask light and specific.",
                 "Day 2: propose a clear micro-agreement: 10 minutes on a specific task at a set time.")
        )
    else:
        lines.append("Day 2: 10-minute tidy together — set a timer, high-five at the end.")

    # Day 3
    if conflict:
        lines.append(
            tone(style,
                 "Day 3: agree on a reset phrase you can both use when conversations heat up (e.g., ‘Can we reset?’). Practice once when calm.",
                 "Day 3: define a reset word for conflict (e.g., ‘Reset.’). Use it once to practice.")
        )
    else:
        lines.append(
            tone(style,
                 "Day 3: plan a tiny feel-good moment (cup of tea together, short walk, or playful check-in).",
                 "Day 3: plan a short shared activity and follow through (10–15 minutes, no phones).")
        )

    # Supportive guardrails based on rating
    if rating <= 3:
        lines.append("Bonus: if emotions spike, take a 5-minute pause then return. Your progress matters more than speed.")

    # Camouflaged collaboration hint (non-revealing)
    if wants_affection and wants_help:
        lines.append("_Hint: kindness outside the bedroom often makes intimacy talks easier._")

    return "\n".join(lines)

# -------------------------
# UI — left config column
# -------------------------
with st.sidebar:
    st.header("RSC Sandbox Settings")
    st.caption("This demo is local and uses simple heuristics (no paid API required).")

# -------------------------
# Intake forms
# -------------------------
st.title("🧑‍🤝‍🧑 RSC Sandbox Demo")

col1, col2 = st.columns(2)

with col1:
    st.subheader("User 1 (Alex) — Intake")
    for q, options in PRESETS["u1"]["intake"].items():
        val = st.selectbox(
            f"Alex: {q.replace('_',' ')}",
            options + ["(write your own)"],
            key=f"u1_{q}"
        )
        if val == "(write your own)":
            val = st.text_input(f"Custom response for Alex: {q}", key=f"u1_custom_{q}")
        st.session_state.intake["u1"][q] = val
    st.session_state.intake["u1"]["rating"] = st.slider("Alex: How are things now? (1–10)", 1, 10, st.session_state.intake["u1"].get("rating", 6), key="u1_rating")

with col2:
    st.subheader("User 2 (Jordan) — Intake")
    for q, options in PRESETS["u2"]["intake"].items():
        val = st.selectbox(
            f"Jordan: {q.replace('_',' ')}",
            options + ["(write your own)"],
            key=f"u2_{q}"
        )
        if val == "(write your own)":
            val = st.text_input(f"Custom response for Jordan: {q}", key=f"u2_custom_{q}")
        st.session_state.intake["u2"][q] = val
    st.session_state.intake["u2"]["rating"] = st.slider("Jordan: How are things now? (1–10)", 1, 10, st.session_state.intake["u2"].get("rating", 6), key="u2_rating")

# -------------------------
# Action buttons
# -------------------------
gen_cols = st.columns([1,1,2])
with gen_cols[0]:
    gen_follow = st.button("Preview potential follow-ups")
with gen_cols[1]:
    gen_plans = st.button("Generate 72-hour Plans")

# -------------------------
# Outputs
# -------------------------
if gen_follow:
    for uid, user in PRESETS.items():
        answers = st.session_state.intake[uid]
        st.session_state.followups[uid] = generate_followups(answers, user["name"])

if gen_plans:
    for uid, user in PRESETS.items():
        answers = st.session_state.intake[uid]
        st.session_state.plans[uid] = coach_plan(answers, user["name"])

# Follow-ups section
st.markdown("## Follow-Up Questions")
for uid, user in PRESETS.items():
    qs = st.session_state.followups.get(uid) or []
    with st.expander(f"Potential follow-ups for {user['name']} ({len(qs)})", expanded=True if gen_follow else False):
        if qs:
            for q in qs:
                st.write("• " + q)
        else:
            st.caption("Press “Preview potential follow-ups” after entering intake answers.")

# Plans section
st.markdown("## Coach Plans")
for uid, user in PRESETS.items():
    plan = st.session_state.plans.get(uid)
    with st.expander(f"{user['name']}'s 72-hour plan", expanded=True if gen_plans else False):
        if plan:
            st.text(plan)
        else:
            st.caption("Press “Generate 72-hour Plans” after entering intake answers.")