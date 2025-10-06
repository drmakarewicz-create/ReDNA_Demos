"""Core AI helpers for LLM-backed trait expansion.

This module keeps the call surface small so app.py can stay lean.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests


@dataclass
class CoreLLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 15
    max_context: int = 200
    temperature: float = 0.15


def core_llm_is_available(cfg: Optional[CoreLLMConfig]) -> bool:
    return bool(cfg and cfg.model and cfg.base_url)


def _trim_resolved(resolved: Dict[str, Any], max_items: int, limit: Optional[Sequence[str]] = None,
                   exclude: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    exclude_set = set(exclude or [])
    if limit:
        items: List[Tuple[str, Any]] = [(path, resolved.get(path)) for path in limit if path in resolved]
    else:
        items = list(resolved.items())
    trimmed: Dict[str, Any] = {}
    for path, entry in items:
        if not entry or path in exclude_set:
            continue
        trimmed[path] = {
            "value": entry.get("value"),
            "ucn": entry.get("ucn"),
            "confidence": entry.get("confidence"),
            "reasons": entry.get("reasons", [])[:2],
        }
        if len(trimmed) >= max_items:
            break
    return trimmed


def build_messages(cfg: CoreLLMConfig, resolved: Dict[str, Any], new_paths: Dict[str, Any],
                   limit_paths: Optional[Sequence[str]] = None, exclude_paths: Optional[Iterable[str]] = None) -> List[Dict[str, str]]:
    context = _trim_resolved(resolved, cfg.max_context, limit_paths, exclude_paths)
    new_obs = {path: new_paths[path] for path in new_paths if path not in (exclude_paths or [])}

    system_prompt = (
        "You are ReDNA Core. Given existing trait resolutions and new observations, "
        "infer additional likely traits strictly when the evidence is strong. "
        "Output JSON with the shape: {\"changes\": {\"Trait.Path\": {\"resolved_value\": value, \"ucn\": number, \"reasons\": [\"...\"]}}}. "
        "Use conservative confidence scores (ucn 90-140). Only add traits you are confident about."
    )

    user_prompt = {
        "resolved_context": context,
        "new_observations": new_obs,
        "instructions": "Return only JSON. Do not repeat values already present unless you have a better, higher-confidence inference."
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]


def call_llm(cfg: CoreLLMConfig, messages: List[Dict[str, str]]) -> Optional[str]:
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    payload = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "top_p": 0.9,
        "stream": False,
    }

    resp = requests.post(
        f"{cfg.base_url}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )


def parse_changes(raw: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not raw:
        return {}

    text = raw.strip()
    candidate = text
    if "{" in text and "}" in text:
        candidate = text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(candidate)
    except Exception:
        return {}

    changes = data.get("changes") if isinstance(data, dict) else None
    if not isinstance(changes, dict):
        return {}

    cleaned: Dict[str, Dict[str, Any]] = {}
    for path, entry in changes.items():
        if not isinstance(path, str):
            continue
        if not isinstance(entry, dict):
            continue
        value = entry.get("resolved_value")
        if value is None:
            continue
        ucn = entry.get("ucn")
        reasons = entry.get("reasons") if isinstance(entry.get("reasons"), list) else []
        cleaned[path] = {
            "resolved_value": value,
            "ucn": ucn if isinstance(ucn, (int, float)) else None,
            "reasons": reasons,
            "provenance": entry.get("provenance") if isinstance(entry.get("provenance"), dict) else {},
        }
    return cleaned


def core_ai_expand(
    cfg: CoreLLMConfig,
    user_id: str,
    resolved: Dict[str, Any],
    new_paths: Dict[str, Any],
    exclude_paths: Optional[Iterable[str]] = None,
    limit_paths: Optional[Sequence[str]] = None,
    allow_overwrite_paths: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    if not core_llm_is_available(cfg):
        return {}

    start = time.time()
    messages = build_messages(cfg, resolved, new_paths, limit_paths, exclude_paths)
    try:
        raw = call_llm(cfg, messages)
    except Exception as exc:
        print(f"[core-ai] user={user_id} error={exc}")
        return {}

    suggestions = parse_changes(raw)
    elapsed = int((time.time() - start) * 1000)

    exclude_set = set(exclude_paths or [])
    exclude_set.update(new_paths.keys())
    overwrite_allowed = set(allow_overwrite_paths or [])

    prepared: Dict[str, Dict[str, Any]] = {}
    for path, entry in suggestions.items():
        if not path or path in exclude_set:
            continue
        if path in resolved and path not in overwrite_allowed:
            continue
        reasons = entry.get("reasons") or []
        provenance = entry.get("provenance") or {}
        provenance.update({
            "source": "core-ai",
            "model": cfg.model,
            "provider": cfg.provider,
        })
        prepared[path] = {
            "resolved_value": entry.get("resolved_value"),
            "ucn": entry.get("ucn") or 110,
            "reasons": reasons or ["core-ai inference"],
            "provenance": provenance,
        }

    print(f"[core-ai] user={user_id} in={len(new_paths)} added={len(prepared)} model={cfg.model} ms={elapsed}")
    return prepared


def map_to_canonical(
    cfg: Optional[CoreLLMConfig],
    *,
    raw_path: str,
    raw_value: Any,
    trait_aliases: Dict[str, Any],
    value_aliases: Dict[str, Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Use the core LLM to map a raw observation onto a canonical PaDNA trait."""

    if not core_llm_is_available(cfg):
        return None

    sample: List[Dict[str, Any]] = []
    for canonical, spec in list(trait_aliases.items())[:60]:
        if not isinstance(canonical, str):
            continue
        entry: Dict[str, Any] = {"path": canonical}
        aliases = spec.get("aliases") if isinstance(spec, dict) else None
        if isinstance(aliases, (list, tuple)):
            entry["aliases"] = list(aliases)[:6]
        values = value_aliases.get(canonical) if isinstance(value_aliases, dict) else None
        if isinstance(values, dict):
            entry["value_examples"] = list({v for v in values.values() if isinstance(v, str)})[:6]
        sample.append(entry)

    payload = {
        "raw_path": raw_path,
        "raw_value": raw_value,
        "candidate_traits": sample,
        "context": context or {},
        "instructions": (
            "Select the best matching canonical trait path and normalised value. "
        'Return JSON: {"canonical_path": str, "canonical_value": value, '
        '"confidence": number between 0 and 1, "notes": str}.'
        ),
    }

    system_prompt = (
        "You are ReDNA Core's canonicalization module. "
        "Given messy trait keys/values, choose the best PaDNA trait path from the provided candidates. "
        "Prefer high-confidence matches and honour enumerations when possible."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    try:
        raw = call_llm(cfg, messages)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[core-ai] canonicalize error={exc}")
        return None

    if not raw:
        return None

    text = raw.strip()
    candidate = text
    if "{" in text and "}" in text:
        candidate = text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(candidate)
    except Exception:
        return None

    canonical_path = data.get("canonical_path") if isinstance(data, dict) else None
    if not isinstance(canonical_path, str):
        return None

    canonical_value = data.get("canonical_value") if isinstance(data, dict) else None
    confidence = data.get("confidence") if isinstance(data, dict) else None
    notes = data.get("notes") if isinstance(data, dict) else None

    result: Dict[str, Any] = {
        "canonical_path": canonical_path,
        "canonical_value": canonical_value,
    }
    if isinstance(confidence, (int, float)):
        result["confidence"] = max(0.0, min(1.0, float(confidence)))
    if isinstance(notes, str):
        result["notes"] = notes
    return result
