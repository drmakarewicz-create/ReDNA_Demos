# ucn_rr_ai.py
"""
UCN/RR AI-side scorer with ingestion pipeline integration.

Maintains the legacy JSON-only reply contract while wiring Evergreen 9
(Data Ingestion Universality) telemetry via the shared ingestion pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from prompt_loader import load_prompts
from llama3_client import DEBUG, chat  # DEBUG flag for helpful printing

logger = logging.getLogger(__name__)

try:
    from ReDNACoreDemo.core.ingestion_pipeline import get_ingestion_pipeline
except Exception:  # pragma: no cover - pipeline optional outside full stack
    get_ingestion_pipeline = None  # type: ignore[assignment]

_PIPELINE = None


def _pipeline():
    global _PIPELINE
    if _PIPELINE is None and get_ingestion_pipeline:
        try:
            _PIPELINE = get_ingestion_pipeline()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to initialise ingestion pipeline: %s", exc)
            _PIPELINE = False
    return _PIPELINE if _PIPELINE is not False else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


FORMAT_RULES = """
You MUST reply with ONLY a single JSON object (no prose, no markdown, no code fences).
Schema EXACTLY:
{"ucn": <number 0..1000>, "rr": <number 0..1>, "why": "<<=200 chars reason>"}
No additional keys. No surrounding text. Minified or pretty is fine, but it must be valid JSON.
"""


def _build_system_prompt() -> str:
    # Layer the base prompts, then add format rules to the end so they’re freshest in context.
    return load_prompts("ucn_rr_ai.md", "ucn_rr_confidence.md") + "\n\n" + FORMAT_RULES.strip() + "\n"


def _parse_first_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def score_confidence(node: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    base_ucn = float(node.get("prior_ucn", 400.0))
    base_rr = float(node.get("prior_rr", 0.5))
    baseline = {"ucn": base_ucn, "rr": base_rr, "curiosity": 1000.0 - base_ucn, "why": "baseline"}

    system_text = _build_system_prompt()
    payload = {"node": node, "evidence": evidence}

    # --- Attempt 1
    resp = chat(system_text, json.dumps(payload, ensure_ascii=False))
    if not resp.get("ok"):
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR fallback reason: {resp.get('reason')}")
        result = baseline
        _record_ingestion(node, evidence, result, accepted=False)
        return result

    text = resp.get("text", "")
    if DEBUG:
        print(f"[AI-DEBUG] UCN/RR raw reply (first 400 chars): {text[:400]!r}")

    parsed = _parse_first_json(text)

    # --- If no JSON returned, Retry once with a stricter reminder
    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] UCN/RR parse failure on first try; retrying with stricter format reminder.")
        strict_system = system_text + "\nCRITICAL: Respond with JSON ONLY per the schema. Any prose will be discarded.\n"
        strict_user = json.dumps(payload, ensure_ascii=False) + "\n\nReturn ONLY the JSON object."
        resp2 = chat(strict_system, strict_user)
        if not resp2.get("ok"):
            if DEBUG:
                print(f"[AI-DEBUG] UCN/RR second-call failure: {resp2.get('reason')}")
            result = baseline
            _record_ingestion(node, evidence, result, accepted=False)
            return result
        text2 = resp2.get("text", "")
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR second raw reply (first 400 chars): {text2[:400]!r}")
        parsed = _parse_first_json(text2)

    if parsed is None:
        if DEBUG:
            print("[AI-DEBUG] UCN/RR could not extract JSON after retry. Using baseline.")
        result = baseline
        _record_ingestion(node, evidence, result, accepted=False)
        return result

    # Validate & clamp
    try:
        u = float(parsed.get("ucn", base_ucn))
        r = float(parsed.get("rr", base_rr))
        w = str(parsed.get("why", ""))[:200]
        u = _clamp(u, 0.0, 1000.0)
        r = _clamp(r, 0.0, 1.0)
        result = {"ucn": u, "rr": r, "curiosity": 1000.0 - u, "why": w}
        _record_ingestion(node, evidence, result, accepted=True)
        return result
    except Exception as exc:
        if DEBUG:
            print(f"[AI-DEBUG] UCN/RR value error: {exc}")
        result = baseline
        _record_ingestion(node, evidence, result, accepted=False)
        return result


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _record_ingestion(
    node: Dict[str, Any],
    evidence: Dict[str, Any],
    result: Dict[str, Any],
    *,
    accepted: bool,
) -> None:
    pipeline = _pipeline()
    if not pipeline:
        return

    user_id = _extract_user_id(node, evidence)
    if not user_id:
        return

    metadata = {
        "sensitivity_level": evidence.get("sensitivity_level", "standard"),
        "confidence_rr": result.get("rr"),
        "confidence_ucn": result.get("ucn"),
        "accepted": accepted,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    from_coach = evidence.get("from_coach") or evidence.get("source_coach") or "head_coach"
    to_coach = (
        node.get("coach_id")
        or evidence.get("target_coach")
        or evidence.get("handoff_target")
        or "ucn_rr"
    )
    reason = result.get("why") or evidence.get("reason")

    try:
        pipeline.capture_coach_handoff(
            user_id=str(user_id),
            from_coach=str(from_coach),
            to_coach=str(to_coach),
            reason=str(reason) if reason is not None else None,
            metadata=metadata,
            source="ucn_rr_score",
            actor="ucn_rr_ai",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to log UCN/RR ingestion for %s: %s", user_id, exc)


def _extract_user_id(node: Dict[str, Any], evidence: Dict[str, Any]) -> Optional[str]:
    for key in ("user_id", "userId", "id"):
        if isinstance(node.get(key), str):
            return node[key]
        if isinstance(evidence.get(key), str):
            return evidence[key]

    for container in (node.get("user"), evidence.get("user")):
        if isinstance(container, dict):
            for key in ("id", "user_id"):
                value = container.get(key)
                if isinstance(value, str):
                    return value
    return None


__all__ = ["score_confidence"]
