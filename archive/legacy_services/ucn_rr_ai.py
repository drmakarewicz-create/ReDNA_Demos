# ucn_rr_ai.py
"""
UCN/RR AI-side scorer with strict JSON enforcement.
- Forces model to return ONLY a tiny JSON object; retries once if needed.
- Safe fallback preserves existing behavior if AI disabled or parsing fails.
- Exposed function: score_confidence(node, evidence) -> dict
"""

import json
from typing import Dict, Any

from prompt_loader import load_prompts
from llama3_client import chat, DEBUG  # DEBUG flag for helpful printing


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


FORMAT_RULES = """
You MUST reply with ONLY a single JSON object (no prose, no markdown, no code fences).
Schema EXACTLY:
{"ucn": <number 0..1000>, "rr": <number 0..1>, "why": "<<=200 chars reason>"}
No additional keys. No surrounding text. Minified or pretty is fine, but it must be valid JSON.
"""


def _build_system_prompt() -> str:
    # Layer the base prompts, then add format rules to the end so they’re freshest in context.
    return load_prompts("ucn_rr_ai.md", "ucn_rr_confidence.md") + "\n\n" + FORMAT_RULES.strip() + "\n"


def _parse_first_json(text: str) -> Dict[str, Any] | None:
    # Extract the first JSON object if present
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def score_confidence(node: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    base_ucn = float(node.get("prior_ucn", 400.0))
    base_rr  = float(node.get("prior_rr", 0.5))
    baseline = {"ucn": base_ucn, "rr": base_rr, "curiosity": 1000.0 - base_ucn, "why": "baseline"}

    system_text = _build_system_prompt()
    payload = {"node": node, "evidence": evidence}

    # --- Attempt 1
    resp = chat(system_text, json.dumps(payload, ensure_ascii=False))
    if not resp.get("ok"):
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR fallback reason: {resp.get('reason')}")
        return baseline

    text = resp.get("text", "")
    if DEBUG:
        print(f"[AI-DEBUG] UCN/RR raw reply (first 400 chars): {text[:400]!r}")

    parsed = _parse_first_json(text)

    # --- If no JSON returned, Retry once with a stricter reminder
    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] UCN/RR parse failure on first try; retrying with stricter format reminder.")
        strict_system = system_text + "\nCRITICAL: Respond with JSON ONLY per the schema. Any prose will be discarded.\n"
        strict_user   = json.dumps(payload, ensure_ascii=False) + "\n\nReturn ONLY the JSON object."
        resp2 = chat(strict_system, strict_user)
        if not resp2.get("ok"):
            if DEBUG:
                print(f"[AI-DEBUG] UCN/RR second-call failure: {resp2.get('reason')}")
            return baseline
        text2 = resp2.get("text", "")
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR second raw reply (first 400 chars): {text2[:400]!r}")
        parsed = _parse_first_json(text2)

    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] UCN/RR could not extract JSON after retry. Using baseline.")
        return baseline

    # Validate & clamp
    try:
        u = float(parsed.get("ucn", base_ucn))
        r = float(parsed.get("rr", base_rr))
        w = str(parsed.get("why", ""))[:200]
        u = _clamp(u, 0.0, 1000.0)
        r = _clamp(r, 0.0, 1.0)
        return {"ucn": u, "rr": r, "curiosity": 1000.0 - u, "why": w}
    except Exception as e:
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR value error: {e}")
        return baseline