"""AI helper routines for Container Studio.

The functions in this module are intentionally defensive: they attempt to
leverage the configured LLM endpoint, but fall back to deterministic heuristics
so that the UI remains functional even when the model is offline.
"""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path  # type: ignore

ensure_explorerdev_on_path()

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from ExplorerDev.schema_utils import SchemaValidationMessage, _iter_containers, _iter_traits


@dataclass(slots=True)
class LLMConfig:
    base_url: str
    model: str
    timeout: int = 45


@dataclass(slots=True)
class AIResponse:
    ok: bool
    messages: List[str]
    traits: List[Dict[str, Any]]
    links: Dict[str, List[str]]
    raw: Optional[str] = None


def validate_schema_hints(schema: Dict[str, Any]) -> List[SchemaValidationMessage]:
    messages: List[SchemaValidationMessage] = []
    for container in _iter_containers(schema):
        cid = str(container.get("id") or "?")
        label = str(container.get("label") or "")
        if len(label.strip().split()) <= 1:
            messages.append(
                SchemaValidationMessage(
                    source="ai",
                    level="warning",
                    message="Container label is terse; add context for reviewers.",
                    subject=cid,
                )
            )
        for trait in _iter_traits(container):
            tid = str(trait.get("id") or "") or "?"
            label = str(trait.get("label") or "")
            decay = str(trait.get("decay") or "")
            sensitivity = str(trait.get("sensitivity") or "").lower()
            if not decay:
                messages.append(
                    SchemaValidationMessage(
                        source="ai",
                        level="warning",
                        message="Decay missing — set explicit decay to avoid silent defaults.",
                        subject=tid,
                    )
                )
            if len(label.split()) == 1:
                messages.append(
                    SchemaValidationMessage(
                        source="ai",
                        level="info",
                        message="Label is short; consider adding qualifier or user-facing phrasing.",
                        subject=tid,
                    )
                )
            if sensitivity and sensitivity not in {"low", "medium", "restricted"}:
                messages.append(
                    SchemaValidationMessage(
                        source="ai",
                        level="warning",
                        message="Sensitivity should be `low`, `medium`, or `restricted` for draft review.",
                        subject=tid,
                    )
                )
    return messages


def build_prompt_meta(
    *,
    tone: str,
    formality: int,
    warmth: int,
    directness: int,
    micro_actions: Sequence[str],
) -> str:
    tone_token = re.sub(r"[^a-z0-9]+", "", str(tone or "neutral").lower()) or "neutral"

    def _clamp(value: Any) -> int:
        try:
            return max(0, min(100, int(value)))
        except Exception:
            return 0

    formality_score = _clamp(formality)
    warmth_score = _clamp(warmth)
    directness_score = _clamp(directness)

    clean_micro: List[str] = []
    for action in micro_actions:
        token = re.sub(r"[^a-z0-9_-]+", "", str(action or "").lower())
        if token and token not in clean_micro:
            clean_micro.append(token)

    micro_serial = ",".join(clean_micro) if clean_micro else "none"
    return (
        f"[tone={tone_token}; formality={formality_score}; warmth={warmth_score}; "
        f"directness={directness_score}; micro={micro_serial}]"
    )


def propose_traits(
    *,
    container_id: str,
    prompt: str,
    existing_ids: Sequence[str],
    llm: Optional[LLMConfig] = None,
) -> AIResponse:
    heuristic_trait = _heuristic_proposal(container_id, prompt, existing_ids)
    messages = ["Generated trait draft using deterministic heuristics."]
    raw = None

    if llm:
        template = _trait_proposal_prompt(container_id, prompt, existing_ids)
        response = _call_llm(template, llm, temperature=0.2)
        if response:
            llm_traits = _extract_traits(response)
            if llm_traits:
                heuristic_trait = []  # prefer LLM suggestions
                messages = ["LLM provided trait proposals; review before saving draft."]
                raw = response
                return AIResponse(True, messages, llm_traits, {}, raw)
            else:
                messages.append("LLM response did not contain structured traits; used fallback.")
                raw = response

    return AIResponse(True, messages, heuristic_trait, {}, raw)


def refine_trait(
    *,
    trait: Dict[str, Any],
    prompt: str,
    llm: Optional[LLMConfig] = None,
) -> AIResponse:
    refined = dict(trait)
    messages = ["Applied heuristic refinement (updated label + timestamp)."]
    refined["label"] = _title_case(refined.get("label", ""))
    refined["last_updated"] = _iso_now()
    raw = None

    if llm:
        template = _trait_refine_prompt(trait, prompt)
        response = _call_llm(template, llm, temperature=0.1)
        if response:
            data = _safe_json(response)
            if isinstance(data, dict):
                refined.update({k: v for k, v in data.items() if v is not None})
                messages = ["LLM refinement applied; verify enum choices before saving."]
                raw = response
                return AIResponse(True, messages, [refined], {}, raw)
            raw = response
            messages.append("LLM response malformed; fallback heuristics retained.")

    return AIResponse(True, messages, [refined], {}, raw)


def suggest_links(
    *,
    container_id: str,
    trait_ids: Sequence[str],
    prompt: str,
    llm: Optional[LLMConfig] = None,
) -> AIResponse:
    links: Dict[str, List[str]] = {}
    raw = None
    for src in trait_ids:
        links[src] = [tid for tid in trait_ids if tid != src]
    messages = ["Generated deterministic cross-links for selected traits."]

    if llm:
        template = _links_prompt(container_id, trait_ids, prompt)
        response = _call_llm(template, llm, temperature=0.1)
        parsed = _safe_json(response) if response else None
        if isinstance(parsed, dict):
            normalised = {
                str(k): [str(v) for v in values if isinstance(v, (str, int))]
                for k, values in parsed.items()
                if isinstance(values, Iterable)
            }
            if normalised:
                links = normalised
                messages = ["LLM suggested relationship links; review for accuracy."]
                raw = response
        elif response:
            messages.append("LLM response malformed; retained fallback cross-links.")
            raw = response

    return AIResponse(True, messages, [], links, raw)


# ----- Helpers --------------------------------------------------------------------


def _heuristic_proposal(container_id: str, prompt: str, existing_ids: Sequence[str]) -> List[Dict[str, Any]]:
    base = _slugify(prompt or f"{container_id}_trait")
    candidate = f"{container_id}.{base}" if container_id else base
    qualifier = 1
    while candidate in existing_ids:
        qualifier += 1
        candidate = f"{container_id}.{base}{qualifier}" if container_id else f"{base}{qualifier}"
    return [
        {
            "id": candidate,
            "label": _title_case(base.replace("_", " ")),
            "type": "score",
            "decay": "steady",
            "sensitivity": "medium",
            "curiosity": "baseline",
            "coverage": "unknown",
            "computed": False,
            "links": [],
            "last_updated": _iso_now(),
        }
    ]


def _trait_proposal_prompt(container_id: str, prompt: str, existing_ids: Sequence[str]) -> str:
    headline = f"Existing traits: {', '.join(existing_ids) or 'none'}"
    return (
        "You are the schema steward for the Container Studio. Based on the context,"
        " produce JSON with a `traits` array. Each trait needs id, label, type, decay,"
        " curiosity, sensitivity, computed (bool), and links (list)."\
        f"\nContainer: {container_id}\nContext: {prompt}\n{headline}"
    )


def _trait_refine_prompt(trait: Dict[str, Any], prompt: str) -> str:
    body = json.dumps(trait, indent=2)
    return (
        "Refine the following trait definition. Respond with JSON containing optional"
        " keys to update. Do not invent ids."\
        f"\nTrait:\n{body}\nContext:\n{prompt}"
    )


def _links_prompt(container_id: str, trait_ids: Sequence[str], prompt: str) -> str:
    return (
        "Return JSON mapping trait ids to related trait ids (list of strings)."
        " Focus on implies/depends_on suggestions. Only include provided ids."\
        f"\nContainer: {container_id}\nTraits: {list(trait_ids)}\nContext:\n{prompt}"
    )


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text or "trait").strip("_")
    return cleaned.lower() or "trait"


def _title_case(text: str) -> str:
    if not text:
        return ""
    return " ".join(word.capitalize() for word in text.split())


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _call_llm(prompt: str, config: LLMConfig, *, temperature: float) -> Optional[str]:
    base = config.base_url.rstrip("/")
    url = f"{base}/api/generate"
    payload = {
        "model": config.model,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=config.timeout)
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    try:
        body = response.json()
    except ValueError:
        return response.text[:2000]
    if isinstance(body, dict):
        return str(body.get("response") or body.get("text") or body)
    return str(body)


def _extract_traits(response: str) -> List[Dict[str, Any]]:
    data = _safe_json(response)
    if isinstance(data, dict):
        payload = data.get("traits")
    else:
        payload = data
    if isinstance(payload, list):
        traits: List[Dict[str, Any]] = []
        for entry in payload:
            if isinstance(entry, dict) and entry.get("id"):
                traits.append(entry)
        return traits
    return []


def _safe_json(blob: str) -> Any:
    if not blob:
        return None
    try:
        return json.loads(blob)
    except Exception:
        return None
