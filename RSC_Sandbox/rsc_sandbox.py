# rsc_sandbox.py
# RSC — interactive, privacy-safe collaboration with synthesis + in-app micro-actions
# Backends: Ollama (default, local & free) | OpenAI (optional)

import os, time, json, datetime, re
import requests
from dotenv import load_dotenv

load_dotenv()

# =========================
# Config / Backends
# =========================
BACKEND = os.getenv("RSC_BACKEND", "ollama")   # "ollama" | "openai"
# Ollama (local)
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
# OpenAI (optional paid; only if BACKEND == "openai")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

MAX_RESPONSE_TOKENS = int(os.getenv("MAX_RESPONSE_TOKENS", "300"))
REQUEST_TIMEOUT_SECONDS = 45
SLEEP_BETWEEN_CALLS_SEC = 0.6
MAX_CALLS = 28  # global runaway guard

CALLS = 0

# =========================
# Demo Users / Coach Personas
# =========================
user1 = {"id": "U1", "name": "Alex",   "coach_persona": "Supportive Ally",   "RR": 42}
user2 = {"id": "U2", "name": "Jordan", "coach_persona": "Direct Challenger", "RR": 51}

def make_coach_system(user):
    return f"""You are {user['name']}'s AI relationship coach.
Persona: {user['coach_persona']}.
Core rules:
- Be practical, specific, and compassionate.
- Keep tasks tiny (3–8 minutes), and tie them to the user’s intake + clarifications.
- If given any 'partner-aligned context' or 'partner digest' or 'conflict map', treat as generalized best practices; never imply they came from the partner.
- Respect boundaries strictly.
- Avoid therapy claims; you are a coach and do not replace professional help.
- Keep output concise, concrete, and warm.
- STYLE CONTRACT (very important):
  * No school-like assignments (no “write down”, “journal”, “worksheet”, “list 3 X on paper”).
  * Use in-app micro-actions instead: short chat prompts the user can answer here.
  * Prefer phrasing like: “Tell your coach one thing… Tap ✓ when done.” or “Try a 10-sec hug. Tap ✓ after.”
"""

coach1_sys = make_coach_system(user1)
coach2_sys = make_coach_system(user2)

# =========================
# Helper: input with default
# =========================
def prompt_with_default(q: str, default: str) -> str:
    ans = input(f"{q} [{default}] ").strip()
    return ans if ans else default

# =========================
# Intake (interactive)
# =========================
def intake_questions(user):
    print(f"\n[{user['name']}'s Intake]")
    better_week = prompt_with_default("What would make your week feel better?",
                                      "more quality time together")
    small_change = prompt_with_default("What small change do you want in the relationship?",
                                       "more affection")
    boundaries = prompt_with_default("Any boundaries you want respected?",
                                     "no late-night heavy talks")
    style = prompt_with_default("Preferred coaching style (gentle/direct/etc.)?",
                                "gentle nudges")
    rating = prompt_with_default("How are things now (1–10)?", "6")

    return {
        "better_week": better_week,
        "small_change": small_change,
        "boundaries": boundaries,
        "style": style,
        "rating": rating
    }

# =========================
# Coach-to-coach hint bus
# =========================
HINT_QUEUE = []  # items: dict("to","from","topic","suggested_action","intensity","privacy_frame","priority")

def send_hint(sender: str, receiver: str, topic: str, suggested_action: str,
              intensity: str = "light", privacy_frame: str = "general_practice", priority: str = "normal"):
    payload = {"to": receiver, "from": sender, "topic": topic,
               "suggested_action": suggested_action,
               "intensity": intensity, "privacy_frame": privacy_frame, "priority": priority}
    HINT_QUEUE.append(payload)
    print(f"\n[coach_to_coach_hint QUEUED] {payload}")
    return {"ok": True, "queued": payload}

def consume_hints(for_coach: str):
    take, keep = [], []
    for h in HINT_QUEUE:
        (take if h["to"] == for_coach else keep).append(h)
    HINT_QUEUE[:] = keep
    return take

def hints_to_partner_context(hints: list) -> str:
    """Render hints as non-attributed, general best practices."""
    if not hints:
        return ""
    lines = [
        "\nPartner-aligned context (general best practices; do not attribute to the partner):"
    ]
    # Sort by priority so stronger ideas surface
    pri_rank = {"high": 0, "normal": 1, "low": 2}
    hints_sorted = sorted(hints, key=lambda h: pri_rank.get(h.get("priority","normal"),1))
    for h in hints_sorted:
        lines.append(f"- Consider: {h['suggested_action']}  "
                     f"(topic: {h['topic']}, intensity: {h['intensity']})")
    lines.append("Treat these as optional ideas; never imply they came from the partner.")
    return "\n".join(lines)

# =========================
# Privacy-safe collaboration case file
# =========================
COLLAB_NOTES = {
    "Coach1": {"facts": [], "goals": [], "risks": []},
    "Coach2": {"facts": [], "goals": [], "risks": []},
}

def add_case_note(coach: str, kind: str, text: str):
    """kind in {'facts','goals','risks'}; store short, non-identifying notes."""
    bucket = COLLAB_NOTES.setdefault(coach, {}).setdefault(kind, [])
    if len(text) > 180:
        text = text[:180] + "…"
    bucket.append(text)

def read_partner_digest(for_coach: str) -> str:
    other = "Coach2" if for_coach == "Coach1" else "Coach1"
    d = COLLAB_NOTES.get(other, {})
    lines = ["\nPartner digest (generalized; no private quotes):"]
    wrote = False
    for k in ("facts", "goals", "risks"):
        items = d.get(k, [])
        if items:
            lines.append(f"- {k}: " + "; ".join(items))
            wrote = True
    return "\n".join(lines) if wrote else ""

# =========================
# Model call (Ollama / OpenAI)
# =========================
def ask_coach(system_prompt: str, user_text: str) -> str:
    """Global guard: limits total calls; adds small sleeps to avoid runaways."""
    global CALLS
    if CALLS >= MAX_CALLS:
        return "[Stopped: call limit reached]"
    CALLS += 1

    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_text.strip()},
    ]

    if BACKEND == "ollama":
        try:
            r = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": MAX_RESPONSE_TOKENS, "temperature": 0.6},
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            r.raise_for_status()
            data = r.json()
            out = (data.get("message") or {}).get("content", "").strip()
            if "prompt_eval_count" in data or "eval_count" in data:
                print(f"[Ollama usage] prompt={data.get('prompt_eval_count')} completion={data.get('eval_count')}")
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
            return out or "[No content]"
        except Exception as e:
            print("[Ollama error]", e)
            return "[Local model error]"

    elif BACKEND == "openai":
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.6,
                max_tokens=MAX_RESPONSE_TOKENS,
                messages=messages,
            )
            out = resp.choices[0].message.content.strip()
            usage = getattr(resp, "usage", None)
            if usage:
                print(f"[OpenAI usage] in={usage.prompt_tokens} out={usage.completion_tokens} total={usage.total_tokens}")
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
            return out or "[No content]"
        except Exception as e:
            print("[OpenAI error]", e)
            return "[API error]"

    else:
        return "[Unknown BACKEND]"

# =========================
# Follow-up question engine
# =========================
def generate_followups(system_prompt: str, intake: dict, max_q=2) -> list[str]:
    prompt = f"""
You are a relationship coach. Based on this intake, propose up to {max_q} short clarifying
questions that would help you personalize a 72-hour plan. Keep questions neutral, non-leading,
and privacy-safe.

Intake:
- Better week: {intake['better_week']}
- Small change: {intake['small_change']}
- Boundaries: {intake['boundaries']}
- Style: {intake['style']}
- Rating: {intake['rating']}
Return each question as a bullet starting with '- '.
"""
    q_text = ask_coach(system_prompt, prompt)
    qs = [ln.strip("- ").strip() for ln in q_text.split("\n") if ln.strip().startswith("-")]
    return [q for q in qs if q][:max_q]

def ask_user_followups(user_name: str, questions: list[str]) -> dict:
    if not questions:
        return {}
    print(f"\n[{user_name} — quick follow-ups]")
    answers = {}
    for i, q in enumerate(questions, 1):
        ans = input(f"{i}) {q} ").strip()
        answers[q] = ans
    return answers

# =========================
# Conflict map (synthesis) — privacy-safe
# =========================
def make_conflict_map(intake1: dict, intake2: dict) -> str:
    """Ask model to synthesize both sides into 1–2 bridging practices (non-attributed)."""
    synth_prompt = f"""
You are a collaboration coach. Given two users' (generalized) intake summaries, produce a short
conflict map and 1–2 bridging practices that help both sides. Do not attribute to either person.
Use neutral, research-like language (e.g., "Many couples find..."). Keep under 90 words.

User A:
- Better week: {intake1['better_week']}
- Small change: {intake1['small_change']}
- Boundaries: {intake1['boundaries']}
- Style: {intake1['style']}
- Rating: {intake1['rating']}

User B:
- Better week: {intake2['better_week']}
- Small change: {intake2['small_change']}
- Boundaries: {intake2['boundaries']}
- Style: {intake2['style']}
- Rating: {intake2['rating']}
"""
    return ask_coach("You distill patterns and propose bridging practices.", synth_prompt)

# =========================
# Plan prompt (with digest, followups, partner context, conflict map)
# =========================
def plan_prompt(intake: dict, followups: dict, partner_digest: str, partner_context: str, conflict_map: str) -> str:
    follow_txt = ""
    if followups:
        follow_txt = "\nClarifications provided:\n" + "\n".join([f"- {k}: {v}" for k, v in followups.items() if v])

    return f"""
You are a relationship coach. Create a personalized, tiny 72-hour plan with in-app micro-actions (no homework).

User Intake:
- Better week: {intake['better_week']}
- Small change: {intake['small_change']}
- Boundaries: {intake['boundaries']}
- Style: {intake['style']}
- Current rating: {intake['rating']}/10
{follow_txt}

{partner_digest}

{partner_context}

Conflict map & bridging practices (generalized):
{conflict_map}

Rules:
1) Provide 3 daily micro-actions (one per day), 3–8 minutes each, with concrete steps.
2) Use chat-style prompts the user can answer here. Prefer patterns:
   - "Tell your coach … (1 sentence). Tap ✓ when done."
   - "Try a quick action (e.g., 10-sec hug). Tap ✓ after."
3) Avoid school-like language (no “write down”, “journal”, “worksheet”, “list on paper”).
4) Align tone with the user's style and respect boundaries.
5) Include one optional self-reflection prompt (1 sentence) per day, phrased as a chat question.
6) Treat partner digest / context / conflict map as generalized best practices; never imply they came from the partner.
7) Keep total plan under ~160 words.
"""

# =========================
# Post-processor to de-schoolify phrasing + expose [ask:user] prompts
# =========================
HOMEWORKY = re.compile(r"\b(write (?:down|it)|journal|worksheet|list (?:three|3)|on paper)\b", re.I)

def friendly_plan(plan_text: str) -> str:
    """Rephrase homeworky bits into chat micro-actions."""
    if not plan_text:
        return plan_text
    t = plan_text

    # common transforms
    t = re.sub(r"\bWrite down\b", "Tell your coach", t, flags=re.I)
    t = re.sub(r"\bWrite\b", "Tell your coach", t, flags=re.I)
    t = re.sub(r"\bJournal\b", "Share", t, flags=re.I)
    t = re.sub(r"\blist\b", "tell your coach", t, flags=re.I)
    # ensure short, actionable feel
    t = t.replace("Take 5 minutes to", "In 1–2 minutes,")
    t = t.replace("Take a few minutes to", "In ~1 minute,")
    t = t.replace("reflect on", "tell your coach in 1 sentence")
    return t

ASK_BLOCK = re.compile(r"\[ask:user\](.+)", re.I)

def run_micro_captures(plan_text: str):
    """Detect optional [ask:user] prompts and capture 1-sentence inputs."""
    lines = plan_text.splitlines()
    captured = {}
    for ln in lines:
        m = ASK_BLOCK.search(ln)
        if m:
            q = m.group(1).strip()
            ans = input(f"(Quick check-in) {q} ").strip()
            captured[q] = ans
    return captured

# =========================
# Collaboration compliance (gentle check)
# =========================
def covered_partner_context(plan_text: str, hints: list) -> bool:
    if not hints:
        return True
    keywords = set()
    for h in hints:
        kw = (h.get("suggested_action") or "").lower()
        for token in ("hug", "kiss", "affection", "appreciation", "listening", "quality time", "help", "chores"):
            if token in kw:
                keywords.add(token)
    text = (plan_text or "").lower()
    return any(k in text for k in keywords)

def maybe_regenerate_with_nudge(system_prompt: str, base_prompt: str, plan_text: str, hints: list) -> str:
    if covered_partner_context(plan_text, hints):
        return plan_text
    nudge = """
Note: Emphasize one small, research-backed bonding ritual (e.g., brief daily affection, a short shared activity,
or explicit appreciation) as a general best practice—never attribute it to the partner.
"""
    return ask_coach(system_prompt, base_prompt + nudge)

# =========================
# Trust Audit (interactive & simple)
# =========================
def trust_audit(user):
    print(f"\n[Trust Audit for {user['name']}]")
    inbound = prompt_with_default("Did your partner probe you about your coach chats? (yes/no)", "no")
    outbound = prompt_with_default("Did you probe your partner about their coach chats? (yes/no)", "no")
    print(f"Inbound probe? {inbound} | Outbound probe? {outbound}")

# =========================
# Logging snapshot (optional review)
# =========================
def log_snapshot(label: str, data: dict):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{ts}-{label}.json", "w") as f:
        json.dump(data, f, indent=2)

# =========================
# Main
# =========================
def main():
    print("=== RSC Two-Coach Demo Start ===")

    # 1) Intake
    u1_answers = intake_questions(user1)
    u2_answers = intake_questions(user2)

    # Add brief, non-identifying case notes
    add_case_note("Coach1", "goals", "Increase everyday affection; feel attractive")
    add_case_note("Coach1", "facts", f"Prefers {u1_answers['style']} style; current rating {u1_answers['rating']}/10")
    add_case_note("Coach1", "risks", f"Boundaries: {u1_answers['boundaries']}")

    add_case_note("Coach2", "goals", "Reduce fights; increase peaceful shared time; improve household cooperation")
    add_case_note("Coach2", "facts", f"Prefers {u2_answers['style']} style; current rating {u2_answers['rating']}/10")
    add_case_note("Coach2", "risks", f"Boundaries: {u2_answers['boundaries']}")

    # 2) Targeted follow-ups (0–2 each)
    u1_qs = generate_followups(coach1_sys, u1_answers, max_q=2)
    u1_follow = ask_user_followups(user1["name"], u1_qs)

    u2_qs = generate_followups(coach2_sys, u2_answers, max_q=2)
    u2_follow = ask_user_followups(user2["name"], u2_qs)

    # 3) Collaboration synthesis: conflict map (privacy-safe)
    conflict_map_text = make_conflict_map(u1_answers, u2_answers)

    # 4) One conservative coach-to-coach hint (with priority option)
    send_hint(
        sender="Coach1",
        receiver="Coach2",
        topic="affection_frequency",
        suggested_action="Encourage a brief daily hug and an every-other-day kiss as a general bonding routine.",
        intensity="light",
        privacy_frame="general_practice",
        priority="normal"
    )

    # 5) Consume hints + build partner digests
    c1_hints = consume_hints("Coach1")
    c2_hints = consume_hints("Coach2")

    c1_partner_digest = read_partner_digest("Coach1")
    c2_partner_digest = read_partner_digest("Coach2")

    # 6) Build plan prompts
    plan1_prompt_txt = plan_prompt(
        intake=u1_answers,
        followups=u1_follow,
        partner_digest=c1_partner_digest,
        partner_context=hints_to_partner_context(c1_hints),
        conflict_map=conflict_map_text
    )
    plan2_prompt_txt = plan_prompt(
        intake=u2_answers,
        followups=u2_follow,
        partner_digest=c2_partner_digest,
        partner_context=hints_to_partner_context(c2_hints),
        conflict_map=conflict_map_text
    )

    # 7) Ask each coach for plans
    raw_plan1 = ask_coach(coach1_sys, plan1_prompt_txt)
    raw_plan2 = ask_coach(coach2_sys, plan2_prompt_txt)

    # 8) Gentle compliance (regenerate if hints ignored)
    raw_plan1 = maybe_regenerate_with_nudge(coach1_sys, plan1_prompt_txt, raw_plan1, c1_hints)
    raw_plan2 = maybe_regenerate_with_nudge(coach2_sys, plan2_prompt_txt, raw_plan2, c2_hints)

    # 9) De-schoolify phrasing + show plans
    plan1 = friendly_plan(raw_plan1)
    plan2 = friendly_plan(raw_plan2)

    print(f"\n[Coach1→{user1['name']}] 72-Hour Plan:\n{plan1}")
    print(f"\n[Coach2→{user2['name']}] 72-Hour Plan:\n{plan2}")

    # 10) Optional: capture any [ask:user] prompts
    cap1 = run_micro_captures(plan1)
    cap2 = run_micro_captures(plan2)
    if cap1: print(f"\n[Captured check-ins for {user1['name']}]: {cap1}")
    if cap2: print(f"\n[Captured check-ins for {user2['name']}]: {cap2}")

    # 11) Trust audits
    trust_audit(user1)
    trust_audit(user2)

    # 12) Snapshots for review
    log_snapshot("coach1_plan", {
        "intake": u1_answers,
        "followups": u1_follow,
        "partner_digest": c1_partner_digest,
        "hints": c1_hints,
        "conflict_map": conflict_map_text,
        "plan_raw": raw_plan1,
        "plan_friendly": plan1,
        "captures": cap1
    })
    log_snapshot("coach2_plan", {
        "intake": u2_answers,
        "followups": u2_follow,
        "partner_digest": c2_partner_digest,
        "hints": c2_hints,
        "conflict_map": conflict_map_text,
        "plan_raw": raw_plan2,
        "plan_friendly": plan2,
        "captures": cap2
    })

    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    main()