from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from ExplorerFinal.ui.tone.rc_phrasebook import humanize as rc_humanize  # type: ignore
    from ExplorerFinal.ui.tone.rc_filters import scrub as rc_scrub  # type: ignore
except Exception:  # pragma: no cover
    rc_humanize = lambda items: []  # type: ignore
    rc_scrub = lambda text: text  # type: ignore

try:
    from ReDNACoreDemo.core import persona_registry as _persona_registry  # type: ignore
except Exception:
    _persona_registry = None  # type: ignore

try:
    from ReDNACoreDemo.ai.prompt_registry import get_persona_bundle  # type: ignore
except Exception:
    get_persona_bundle = None  # type: ignore

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "coach_personas.yaml"

RC_TONE_CONTRACT = (
    "Voice: warm, vivid, confidant-level. Keep sentences short and human.\n"
    "Use *you* or *you two*, never labels like \"introverted individual\".\n"
    "Reflect the user’s core feeling in **bold** once per reply so they feel seen.\n"
    "Weave one sensory detail or gentle metaphor when it truly helps clarity.\n"
    "Offer exactly one micro-action introduced with _Try: ..._ in italics.\n"
    "Avoid internal jargon (no RR/UCN, \"data points\", \"path=\").\n"
    "Ask at most one question per turn and place it at the end.\n"
)

_KEYWORD_MAP = {
    "nutrition": ["diet", "calorie", "food", "nutrition", "meal", "eat", "bbq", "vegan", "protein"],
    "strength": ["lift", "workout", "strength", "conditioning", "gym", "deadlift", "squat", "training", "recovery"],
    "data_scientist": ["ucn", "rr", "curiosity", "baseline", "over-fit", "stats", "confidence", "variance"],
    "ethics": ["consent", "law", "legal", "policy", "ethic", "privacy", "scrape", "breach"],
}



def _bundle_prompts(persona_id: str) -> Dict[str, Any]:
    if not get_persona_bundle:
        return {}
    bundle = get_persona_bundle(persona_id)
    if not bundle:
        return {}
    return {
        "system": bundle.system,
        "dialogue_templates": bundle.dialogue_templates,
        "micro_actions": bundle.micro_actions,
        "evaluations": bundle.evaluations,
    }


def _registration_payload(persona_id: str) -> Dict[str, Any]:
    if _persona_registry is None:
        return {}
    try:
        get_registration_payload = getattr(_persona_registry, "get_registration_payload")
    except AttributeError:
        return {}
    try:
        payload = get_registration_payload(persona_id)  # type: ignore[misc]
    except Exception:
        return {}
    return dict(payload or {})


def _persona_from_config(config: Any) -> Dict[str, Any]:
    prompts = _bundle_prompts(config.id)
    registration = _registration_payload(config.id)
    display_name = registration.get("display_name") or config.name
    return {
        "id": config.id,
        "title": display_name,
        "display_name": display_name,
        "greeting_template": registration.get("greeting_template"),
        "description": config.description,
        "prompt": prompts.get("system", ""),
        "keywords": list(config.keywords or []),
        "style": {"tone": config.tone.baseline},
        "rr_contract": {
            "base_increment": config.rr_contract.base_increment,
            "contradiction_escalation": config.rr_contract.contradiction_escalation,
        },
        "prompt_assets": prompts,
        "data_dependencies": {
            "bundle": list(config.data_dependencies.bundle),
            "session": list(config.data_dependencies.session),
            "optional": list(config.data_dependencies.optional),
        },
        "consent": {
            "needs_partner_opt_in": config.consent_requirements.needs_partner_opt_in,
            "share_scope": config.consent_requirements.share_scope,
        },
        "tone": {
            "baseline": config.tone.baseline,
            "escalations": dict(config.tone.escalations),
        },
        "handoff_intents": registration.get("handoff_intents", []),
        "style_presets": registration.get("style_presets", []),
        "metrics_keys": registration.get("metrics_keys", []),
    }

@lru_cache(maxsize=1)
def load_personas() -> Dict[str, Dict[str, Any]]:
    personas: Dict[str, Any] = {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        personas.update(data.get("personas") or {})
    if _persona_registry is not None:
        try:
            for summary in _persona_registry.list_personas():  # type: ignore[attr-defined]
                config = _persona_registry.get_persona(summary.id)
                if not config:
                    continue
                personas[summary.id] = _persona_from_config(config)
        except Exception:
            pass
    return {"personas": personas}


def list_personas() -> List[Dict[str, Any]]:
    personas = load_personas()["personas"]
    out: List[Dict[str, Any]] = []
    for pid, meta in personas.items():
        entry = dict(meta)
        entry["id"] = pid
        if "keywords" not in entry:
            entry["keywords"] = meta.get("keywords", [])
        out.append(entry)
    return out


def get_persona(persona_id: str) -> Optional[Dict[str, Any]]:
    return load_personas()["personas"].get(persona_id)


def route_intent(message: str, dev_mode: bool = False, *, default: str = "head_coach") -> str:
    text = (message or "").lower()
    personas = load_personas()["personas"]
    if not text:
        return default if default in personas else (next(iter(personas), default))

    for persona_id, meta in personas.items():
        intents = meta.get("handoff_intents") or []
        for intent in intents:
            phrase = ""
            match_type = "contains"
            if isinstance(intent, str):
                phrase = intent
            elif isinstance(intent, dict):
                phrase = str(intent.get("phrase") or "")
                match_type = str(intent.get("match_type") or "contains").lower()
            phrase_clean = phrase.strip().lower()
            if not phrase_clean:
                continue
            if match_type == "contains" and phrase_clean in text:
                return persona_id
            if match_type == "startswith" and text.startswith(phrase_clean):
                return persona_id
            if match_type == "regex":
                try:
                    if re.search(phrase_clean, text):
                        return persona_id
                except re.error:
                    continue

    for persona_id, keywords in _KEYWORD_MAP.items():
        if persona_id not in personas:
            continue
        if any(keyword in text for keyword in keywords):
            return persona_id

    for persona_id, meta in personas.items():
        dynamic_keywords = meta.get("keywords") or []
        if any(keyword in text for keyword in dynamic_keywords):
            return persona_id

    # Heuristic: questions about "why" or "how" with core/rr -> data scientist
    if "why" in text and ("core" in text or "rr" in text or "ucn" in text):
        if "data_scientist" in personas:
            return "data_scientist"

    if "ethic" in text or "compliance" in text:
        if "ethics" in personas:
            return "ethics"

    if "nutrition" in personas and any(word in text for word in ["eat", "food", "diet"]):
        return "nutrition"

    if "strength" in personas and any(word in text for word in ["train", "exercise", "lift"]):
        return "strength"

    return default if default in personas else (next(iter(personas), default))


def _format_curiosity_rows(rows: Optional[List[Dict[str, Any]]], limit: int = 15) -> str:
    if not rows:
        return ""
    lines = []
    for row in rows[:limit]:
        path = row.get("path")
        curiosity = row.get("curiosity")
        rr = row.get("rr")
        ucn = row.get("ucn")
        value = row.get("value")
        bit = f"{path}: value={value}"
        if curiosity is not None:
            bit += f", curiosity={curiosity}"
        if rr is not None:
            bit += f", rr={rr}"
        if ucn is not None:
            bit += f", ucn={ucn}"
        lines.append(f"- {bit}")
    return "\n".join(lines)


def _format_recent_changes(recent: Optional[Dict[str, Any]]) -> str:
    if not recent:
        return ""
    parts = []
    changed = recent.get("from_user") or []
    core_ai = recent.get("core_ai") or []
    if changed:
        parts.append("User-supplied updates: " + ", ".join(changed))
    if core_ai:
        parts.append("Core-AI additions: " + ", ".join(core_ai))
    return "\n".join(f"- {item}" for item in parts)


def compose_system_prompt(
    persona: Dict[str, Any],
    *,
    dev_mode: bool,
    user_context: Optional[Dict[str, Any]] = None,
    persona_id: Optional[str] = None,
    display_name: Optional[str] = None,
) -> str:
    prompt = (persona.get("prompt") or "").strip()
    guardrails = persona.get("guardrails") or {}
    style = persona.get("style") or {}
    persona_id = persona_id or persona.get("id")
    display_name = display_name or persona.get("title") or persona.get("name") or persona_id

    top_curiosity = []
    recent_changes = {}
    if user_context:
        top_curiosity = user_context.get("top_curiosity") or []
        recent_changes = user_context.get("recent_changes") or {}

    context_lines: List[str] = []
    curiosity_block = _format_curiosity_rows(top_curiosity)
    if curiosity_block:
        context_lines.append("Top curiosity traits:\n" + curiosity_block)

    recent_block = _format_recent_changes(recent_changes)
    if recent_block:
        context_lines.append("Recent pipeline updates:\n" + recent_block)

    guardrail_lines: List[str] = []
    avoid = guardrails.get("avoid") or []
    refer = guardrails.get("refer_out_if") or []
    if avoid:
        guardrail_lines.append("Avoid: " + ", ".join(avoid))
    if refer:
        guardrail_lines.append("Escalate or refer out if: " + ", ".join(refer))

    metadata_lines: List[str] = []
    if display_name:
        metadata_lines.append(f"Persona: {display_name}")
    if persona_id:
        metadata_lines.append(f"Persona ID: {persona_id}")
    relationship_notes: List[str] = []
    if persona_id == "relationship_coach":
        metadata_lines.append("Persona: Relationship Coach (RC)")
        metadata_lines.append("You are the Relationship Coach. You are NOT the Head Coach.")
        metadata_lines.append("Stay in RC voice at all times. The Head Coach runs silently in the background.")
        if user_context:
            paths = [row.get("path") for row in (user_context.get("top_curiosity") or []) if isinstance(row, dict)]
            friendly = rc_humanize([p for p in paths if p])
            if friendly:
                relationship_notes = friendly

    parts = []
    if metadata_lines:
        parts.append("\n".join(metadata_lines))
    parts.append(prompt)
    if persona_id == "relationship_coach" and RC_TONE_CONTRACT not in prompt:
        parts.append(RC_TONE_CONTRACT)
    if relationship_notes:
        parts.append("Relationship cues:\n- " + "\n- ".join(relationship_notes))
    if context_lines:
        parts.append("Context snippets:\n" + "\n\n".join(context_lines))
    if guardrail_lines:
        parts.append("Guardrails:\n- " + "\n- ".join(guardrail_lines))

    if dev_mode:
        parts.append(
            "Developer mode: You may expose reasoning, cite provenance, and include exact canonical test lines."
        )
    else:
        tone_hint = style.get("tone")
        if tone_hint:
            parts.append(f"Tone hint: respond in a {tone_hint} manner.")

    return "\n\n".join(part for part in parts if part)


def apply_style(style: Dict[str, Any], text: str) -> str:
    if not text:
        return text

    max_words = style.get("max_words")
    if max_words:
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words]) + "…"

    if style.get("bullets"):
        if "\n-" not in text and "\n•" not in text:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            if len(sentences) > 1:
                text = "\n".join(f"- {sentence}" for sentence in sentences)
            else:
                text = "- " + text.strip()

    return text
