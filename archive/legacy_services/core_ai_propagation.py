# core_ai_propagation.py
"""
Core AI helper to propose propagation/inference after a trait change.
- Strict JSON-only responses (schema enforced)
- Retries once if the first reply isn't valid JSON
- Safe fallback returns a minimal, deterministic plan
- Exposed function: propose_propagation(change_event, neighborhood) -> dict
"""

import json
from typing import Dict, Any

from prompt_loader import load_prompts
from llama3_client import chat, DEBUG

FORMAT_RULES = """
You MUST reply with ONLY a single JSON object (no prose, no markdown, no code fences).
Schema EXACTLY:
{
  "propagation_plan": [{"path": "<string>", "action": "<align|recompute_rollup|check>", "reason": "<string>"}],
  "contradictions": [{"path": "<string>", "severity": "<low|med|high>", "note": "<string>"}],
  "checks": [{"prompt": "<string>"}]
}
- Keys must exist; empty arrays allowed.
- Do not include any extra keys.
- Do not include surrounding text.
"""

def _build_system_prompt() -> str:
    # Layer the base prompts then append strict formatting rules
    return load_prompts("core_ai.md", "core_ai_propagation.md") + "\n\n" + FORMAT_RULES.strip() + "\n"

def _parse_first_json(text: str):
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

def propose_propagation(change_event: Dict[str, Any],
                        neighborhood: Dict[str, Any]) -> Dict[str, Any]:
    system_text = _build_system_prompt()
    payload = {"change_event": change_event, "neighborhood": neighborhood}

    fallback = {
        "propagation_plan": [
            {"path": change_event["path"].split(".")[0], "action": "recompute_rollup", "reason": "direct change"}
        ],
        "contradictions": [],
        "checks": [{"prompt": f"Confirm {change_event['path']} change is persistent and not a typo."}]
    }

    # --- Attempt 1
    resp = chat(system_text, json.dumps(payload, ensure_ascii=False))
    if not resp.get("ok"):
        if DEBUG:
            print(f"[AI-DEBUG] Core propagation fallback reason: {resp.get('reason')}")
        return fallback

    txt = resp.get("text", "")
    if DEBUG:
        print(f"[AI-DEBUG] Core raw reply (first 400 chars): {txt[:400]!r}")

    parsed = _parse_first_json(txt)

    # --- If not valid JSON, retry once with even stricter reminder
    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] Core parse failure on first try; retrying with stricter format reminder.")
        strict_system = system_text + "\nCRITICAL: Respond with JSON ONLY per the schema. Any prose will be discarded.\n"
        strict_user = json.dumps(payload, ensure_ascii=False) + "\n\nReturn ONLY the JSON object."
        resp2 = chat(strict_system, strict_user)
        if not resp2.get("ok"):
            if DEBUG:
                print(f"[AI-DEBUG] Core second-call failure: {resp2.get('reason')}")
            return fallback
        txt2 = resp2.get("text", "")
        if DEBUG:
            print(f"[AI-DEBUG] Core second raw reply (first 400 chars): {txt2[:400]!r}")
        parsed = _parse_first_json(txt2)

    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] Core could not extract JSON after retry. Using fallback.")
        return fallback

    # Light sanity checks
    try:
        plan = parsed.get("propagation_plan", [])
        contr = parsed.get("contradictions", [])
        checks = parsed.get("checks", [])
        if not isinstance(plan, list) or not isinstance(contr, list) or not isinstance(checks, list):
            if DEBUG:
                print("[AI-DEBUG] Core parse sanity check failed (arrays missing). Using fallback.")
            return fallback
        return {"propagation_plan": plan, "contradictions": contr, "checks": checks}
    except Exception as e:
        if DEBUG:
            print(f"[AI-DEBUG] Core value error: {e}")
        return fallback