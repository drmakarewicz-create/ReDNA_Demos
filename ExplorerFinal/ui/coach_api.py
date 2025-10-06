from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

import requests

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from streamlit.runtime.uploaded_file_manager import UploadedFile
else:  # pragma: no cover - runtime alias
    UploadedFile = Any

from .persona_router import (
    apply_style as persona_apply_style,
    compose_system_prompt as persona_compose_system_prompt,
    get_persona,
    list_personas,
)
try:
    from ExplorerFinal.ui.tone.rc_filters import scrub as rc_scrub  # type: ignore
except Exception:  # pragma: no cover
    def rc_scrub(text: str) -> str:
        return text


UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8015").rstrip("/")

LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "llama"
LLM_MODEL = os.getenv("LLM_MODEL") or "llama3"
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY") or None
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "45"))

CORE_USE_LLM = os.getenv("CORE_USE_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}
CORE_HOLISTIC_USE_LLM = os.getenv("CORE_HOLISTIC_USE_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}

UCNRR_TIMEOUT = int(os.getenv("HC_UCNRR_TIMEOUT", "25"))
CORE_TIMEOUT = int(os.getenv("HC_CORE_TIMEOUT", "20"))

ANALYTICS_ENABLE_SWITCH_LOGS = os.getenv("ANALYTICS_ENABLE_SWITCH_LOGS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ANALYTICS_SWITCH_LOG_PATH = Path(os.getenv("ANALYTICS_SWITCH_LOG", "data/analytics/switch_events.jsonl"))

MAX_CONTEXT_ROWS = 30
MAX_CHAT_HISTORY = 12
TOP_PLAN_LIMIT = 10

_SWITCH_VERBS = (
    "switch",
    "hand off",
    "handoff",
    "hand-off",
    "bring",
    "bring in",
    "call in",
    "call on",
    "loop in",
    "tap in",
    "ping",
    "pull in",
    "tag",
    "invite",
    "ask",
    "summon",
    "queue",
    "rope in",
    "let's get",
    "let's bring",
)

@dataclass
class PersonaSwitchMatch:
    target_id: str
    matched_phrase: str
    reason: str


def _persona_alias_map() -> Dict[str, Tuple[str, str]]:
    mapping: Dict[str, Tuple[str, str]] = {}
    try:
        personas = list_personas()
    except Exception:
        personas = []

    for meta in personas:
        pid = (meta.get("id") or "").strip()
        if not pid:
            continue
        base_aliases = {pid}
        base_aliases.add(pid.replace("_", " "))
        title = str(meta.get("title") or meta.get("display_name") or meta.get("name") or "").strip()
        if title:
            base_aliases.add(title)
            title_lower = title.lower()
            if title_lower.endswith(" coach"):
                base_aliases.add(title_lower[:-6])
        for alias in base_aliases:
            cleaned = alias.strip().lower()
            if len(cleaned) < 3:
                continue
            reason = "display_name" if alias != pid else "id_alias"
            mapping.setdefault(cleaned, (pid, reason))

        for intent in meta.get("handoff_intents") or []:
            phrase = ""
            match_type = "contains"
            if isinstance(intent, str):
                phrase = intent
            elif isinstance(intent, dict):
                phrase = str(intent.get("phrase") or "")
                match_type = str(intent.get("match_type") or "contains").lower()
            phrase_clean = phrase.strip().lower()
            if not phrase_clean or match_type == "regex":
                continue
            mapping.setdefault(phrase_clean, (pid, "handoff_intent"))

    static_aliases = {
        "head coach": "head_coach",
        "relationship coach": "relationship_coach",
        "rc": "relationship_coach",
        "photo coach": "photo",
        "photo-coach": "photo",
        "padna coach": "padna",
        "onboarding coach": "onboarding",
    }
    for alias, pid in static_aliases.items():
        mapping.setdefault(alias, (pid, "static_alias"))

    return dict(sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True))


def _is_direct_address(text: str, alias: str) -> bool:
    alias = alias.strip()
    if not alias:
        return False
    lowered = text.strip()
    if lowered == alias or lowered == alias + "?" or lowered == alias + "!":
        return True
    prefixes = ("", "hey ", "hi ", "hello ", "dear ", "coach ")
    suffixes = (",", ":", " -", "—", "?", "!", " please", " can", " what", " how", " let's")
    for prefix in prefixes:
        candidate = prefix + alias
        for suffix in suffixes:
            if text.startswith(candidate + suffix):
                return True
    return False


def _detect_persona_switch(text: str, current_persona: str) -> Optional[PersonaSwitchMatch]:
    if not text:
        return None
    lowered = text.lower()
    try:
        personas = list_personas()
    except Exception:
        personas = []

    for meta in personas:
        pid = (meta.get("id") or "").strip()
        if not pid or pid == current_persona:
            continue
        intents = meta.get("handoff_intents") or []
        for intent in intents:
            phrase = ""
            match_type = "contains"
            reason = "handoff_intent"
            if isinstance(intent, str):
                phrase = intent
            elif isinstance(intent, dict):
                phrase = str(intent.get("phrase") or "")
                match_type = str(intent.get("match_type") or "contains").lower()
                reason = str(intent.get("reason") or "handoff_intent")
            phrase_clean = phrase.strip()
            if not phrase_clean:
                continue
            lowered_phrase = phrase_clean.lower()
            matched = False
            if match_type == "contains" and lowered_phrase in lowered:
                matched = True
            elif match_type == "startswith" and lowered.startswith(lowered_phrase):
                matched = True
            elif match_type == "regex":
                try:
                    if re.search(phrase_clean, lowered):
                        matched = True
                except re.error:
                    continue
            if matched:
                return PersonaSwitchMatch(target_id=pid, matched_phrase=phrase_clean, reason=reason)

    alias_map = _persona_alias_map()
    for alias, payload in alias_map.items():
        persona_id, alias_reason = payload
        pattern = r"\\b" + re.escape(alias) + r"\\b"
        matches = list(re.finditer(pattern, lowered))
        if not matches:
            continue
        if _is_direct_address(lowered, alias):
            return PersonaSwitchMatch(target_id=persona_id, matched_phrase=alias, reason="direct_alias")
        match = matches[0]
        alias_index = match.start()
        window_start = max(0, alias_index - 40)
        window_end = min(len(lowered), match.end() + 40)
        leading_window = lowered[window_start:alias_index]
        trailing_window = lowered[alias_index:window_end]
        if any(verb in leading_window for verb in _SWITCH_VERBS) or any(
            verb in trailing_window for verb in _SWITCH_VERBS
        ):
            return PersonaSwitchMatch(target_id=persona_id, matched_phrase=alias, reason=alias_reason)
    return None


def _switch_acknowledgement(
    *,
    current_persona: str,
    current_title: str,
    target_persona: Optional[str],
) -> Dict[str, Any]:
    if not target_persona or target_persona == current_persona:
        title = current_title or current_persona.replace("_", " ").title()
        return {
            "assistant_text": f"I’m already here as the {title}. Let’s keep working together.",
            "persona_id": current_persona,
            "persona_title": current_title,
            "switch_ack": True,
            "ucnrr_reply": {"ok": True, "reason": "persona_already_active"},
        }

    target_meta = get_persona(target_persona) or {}
    target_title = (
        target_meta.get("title")
        or target_meta.get("name")
        or target_persona.replace("_", " ").title()
    )
    return {
        "assistant_text": f"Bringing in the {target_title} now — they’ll take point from here.",
        "persona_id": current_persona,
        "persona_title": current_title,
        "next_persona": target_persona,
        "next_persona_title": target_title,
        "switch_ack": True,
        "ucnrr_reply": {"ok": True, "reason": "persona_switch"},
    }


@dataclass
class ServiceResult:
    ok: bool
    status: int
    data: Any
    error: Optional[str] = None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_switch_event(*, from_persona: str, to_persona: str, matched_phrase: str, reason: str) -> None:
    if not ANALYTICS_ENABLE_SWITCH_LOGS:
        return
    try:
        ANALYTICS_SWITCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "from": from_persona,
            "to": to_persona,
            "matched_phrase": matched_phrase,
            "reason": reason,
            "ts": _iso_now(),
        }
        with ANALYTICS_SWITCH_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception:
        # Logging is best-effort; errors should not block persona switching.
        return


def _safe_request(call: callable) -> ServiceResult:
    try:
        resp = call()
    except requests.RequestException as exc:  # pragma: no cover - network failure branch
        status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
        return ServiceResult(False, status, None, error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return ServiceResult(False, 0, None, error=str(exc))

    status = getattr(resp, "status_code", 0)
    if status and status >= 400:
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text if hasattr(resp, "text") else None
        return ServiceResult(False, status, payload, error=f"http_{status}")

    try:
        data = resp.json()
    except Exception:
        data = resp.text if hasattr(resp, "text") else None
    return ServiceResult(True, status, data)


def _format_float(value: Any) -> Optional[str]:
    try:
        return f"{float(value):.5f}"
    except Exception:
        return None


def _truncate(text: Optional[str], limit: int = 140) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


_CANONICAL_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*\s*=\s*.+$")



def _extract_microaction(assistant_text: str) -> Optional[Dict[str, Any]]:
    if not assistant_text:
        return None
    suggestion_line: Optional[str] = None
    for line in assistant_text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("suggestion"):
            suggestion_line = stripped.split(":", 1)[-1].strip() if ":" in stripped else stripped
            break
    if not suggestion_line:
        for line in assistant_text.splitlines():
            stripped = line.strip()
            if stripped and stripped[0] in {"-", "•"}:
                suggestion_line = stripped.lstrip("-• ")
                break
    if not suggestion_line:
        return None
    return {
        "title": suggestion_line,
        "why": "suggested during rc_chat",
        "suggested_by": "relationship_coach",
        "status": "proposed",
        "rr_impact_guess": 1.0,
        "created_ts": _iso_now(),
    }


def _background_capture_relationship(
    user_id: str,
    user_text: str,
    assistant_text: str,
    *,
    capture_enabled: bool,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    if not capture_enabled or not user_id or not user_text.strip():
        return {"ok": False, "reason": "disabled", "captured": 0}

    payload_lines: List[str] = []
    microaction = _extract_microaction(assistant_text)
    if microaction:
        import json as _json
        payload_lines.append(
            "RelDNA.MicroActions.Backlog=" + _json.dumps(microaction, ensure_ascii=False)
        )

    capture_provenance = dict(provenance)
    capture_provenance.update(
        {
            "source": "rc_chat",
            "persona_id": "relationship_coach",
            "mode": "background_capture",
        }
    )
    if assistant_text:
        capture_provenance["assistant_summary"] = assistant_text[:160]

    payload = {
        "user_id": user_id,
        "text": user_text,
        "lines": payload_lines,
        "provenance": capture_provenance,
    }

    result = _safe_request(
        lambda: requests.post(
            f"{UCNRR_BASE}/ingest_text",
            json=payload,
            timeout=UCNRR_TIMEOUT,
        )
    )

    captured = 0
    changed = []
    if result.ok and isinstance(result.data, dict):
        changed = result.data.get("changed_keys") or []
        captured = len(changed)
    summary = {
        "ok": result.ok,
        "status": result.status,
        "captured": captured,
        "changed_keys": changed,
    }
    if not result.ok:
        summary["error"] = result.error
    return summary


def _extract_canonical_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").splitlines():
        candidate = raw.strip()
        if _CANONICAL_LINE_RE.match(candidate):
            lines.append(candidate)
    seen: List[str] = []
    for line in lines:
        if line not in seen:
            seen.append(line)
    return seen[:TOP_PLAN_LIMIT]


def _holistic_counts(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "ran": False,
            "async": False,
            "ucn_rr_updates": 0,
            "implied_additions": 0,
            "contradictions": 0,
            "llm_considered": 0,
            "llm_updates": 0,
            "llm_skipped": 0,
        }

    def _as_len(value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
        return 0

    counts = {
        "ucn_rr_updates": _as_len(payload.get("ucn_rr_updates")),
        "implied_additions": _as_len(payload.get("implied_additions")),
        "contradictions": _as_len(payload.get("contradictions")),
        "llm_considered": _as_len(payload.get("llm_considered")),
        "llm_updates": _as_len(payload.get("llm_updates")),
        "llm_skipped": _as_len(payload.get("llm_skipped")),
    }
    return {
        "ran": True,
        "async": bool(payload.get("async_")),
        **counts,
    }


def _holistic_badge(summary: Dict[str, Any]) -> Optional[str]:
    if not summary.get("ran"):
        return None
    llm_considered = summary.get("llm_considered", 0)
    if llm_considered or (CORE_HOLISTIC_USE_LLM and summary.get("ran")):
        return (
            "Holistic (LLM): "
            f"considered {llm_considered}, "
            f"updated {summary.get('llm_updates', 0)}, "
            f"implied {summary.get('implied_additions', 0)}, "
            f"contradictions {summary.get('contradictions', 0)}"
        )
    return (
        "Holistic: "
        f"{summary.get('ucn_rr_updates', 0)} adjusted, "
        f"{summary.get('implied_additions', 0)} implied, "
        f"{summary.get('contradictions', 0)} contradictions"
    )


def _resolved_context(resolved: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    resolved_map = resolved.get("resolved") if isinstance(resolved, dict) else {}
    if not isinstance(resolved_map, dict):
        return entries

    for path, meta in resolved_map.items():
        if not isinstance(meta, dict):
            continue
        curiosity = float(meta.get("curiosity", 0.0) or 0.0)
        reasons = meta.get("reasons")
        if isinstance(reasons, list):
            reasons = reasons[:3]
        provenance = meta.get("provenance")
        if isinstance(provenance, dict):
            provenance = {k: provenance.get(k) for k in ("source", "from", "actor", "ts", "model") if provenance.get(k) is not None}

        entries.append(
            {
                "path": path,
                "value": meta.get("value"),
                "ucn": _format_float(meta.get("ucn")),
                "rr": _format_float(meta.get("rr")),
                "curiosity": f"{curiosity:.5f}",
                "notes": _truncate(((meta.get("notes") or {}).get("summary"))),
                "reasons": reasons,
                "provenance": provenance,
            }
        )

    entries.sort(key=lambda row: float(row.get("curiosity", 0.0)), reverse=True)
    return entries[:MAX_CONTEXT_ROWS]


def _recent_changes(core_response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(core_response, dict):
        return {}
    return {
        "from_user": list(core_response.get("changed_from_caller", []) or []),
        "core_ai": list(core_response.get("added_by_core_ai", []) or []),
        "resolved_keys": list(core_response.get("resolved_keys", []) or []),
    }


def _chat_history_to_messages(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    if not history:
        return []
    trimmed = history[-MAX_CHAT_HISTORY:]
    messages: List[Dict[str, str]] = []
    for entry in trimmed:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _llm_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    return headers


def _llm_chat(messages: List[Dict[str, str]]) -> ServiceResult:
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
        "stream": False,
    }

    def _call():
        return requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            headers=_llm_headers(),
            json=payload,
            timeout=LLM_TIMEOUT,
        )

    return _safe_request(_call)


def coach_reply_llm(
    messages: List[Dict[str, str]],
    persona_ctx: Dict[str, Any],
    user_context: Dict[str, Any],
    dev_mode: bool,
) -> Dict[str, Any]:
    """
    Return the assistant reply text and optional developer artefacts.
    """
    system_prompt = persona_ctx.get("system", "")
    style = persona_ctx.get("style") or {}
    payload_messages = [{"role": "system", "content": system_prompt}] + messages

    llm_res = _llm_chat(payload_messages)
    if not llm_res.ok:
        fallback = (
            "I captured that update for Core just now. Let's keep the momentum—share another detail or ask for a plan refresh."
            if not dev_mode
            else "Pipeline response unavailable. Cross-check service health and retry once UCN/RR + Core are reachable."
        )
        return {
            "text": fallback,
            "reason": llm_res.error or "llm_unavailable",
        }

    data = llm_res.data or {}
    if isinstance(data, dict):
        message = (data.get("choices") or [{}])[0].get("message", {})
        content = message.get("content") or ""
    else:
        content = str(data)

    reply_text = content.strip() or "Let's keep going."
    canonical: List[str] = []

    parsed: Dict[str, Any] = {}
    if dev_mode:
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict) and parsed:
            reply_text = str(parsed.get("reply") or parsed.get("text") or reply_text).strip() or reply_text
            raw_canon = parsed.get("canonical")
            if isinstance(raw_canon, list):
                canonical = [str(item).strip() for item in raw_canon if str(item).strip()]
            free_text = parsed.get("free_text")
            if isinstance(free_text, str) and free_text.strip():
                canonical.append(free_text.strip())

    if not canonical:
        canonical = _extract_canonical_lines(content)
    if not canonical:
        canonical = _canonical_suggestions(user_context.get("top_curiosity", []))

    styled_text = persona_apply_style(style, reply_text)

    return {
        "text": styled_text,
        "reason": "ok",
        "canonical": canonical,
    }


def _prepare_observation_items(observations: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not observations:
        return items
    for entry in observations:
        if not isinstance(entry, dict):
            continue
        trait_id = entry.get("trait") or entry.get("trait_id")
        if not trait_id:
            continue
        value = entry.get("value")
        try:
            ucn_value = float(entry.get("ucn", 20.0) or 20.0)
        except (TypeError, ValueError):
            ucn_value = 20.0
        source_name = entry.get("source") or "head_coach_observation"
        payload: Dict[str, Any] = {
            "trait": trait_id,
            "value": value,
            "ucn": ucn_value,
            "source": f"observation:{source_name}",
            "when": entry.get("ts"),
            "kind": "observation",
        }
        provenance_reason = entry.get("provenance")
        if provenance_reason:
            payload["reasons"] = [provenance_reason]
        flags: List[str] = []
        if entry.get("decay", True):
            flags.append("decay")
        if flags:
            payload["flags"] = flags
        meta = {
            "container": entry.get("container"),
            "confidence": entry.get("confidence"),
            "ts": entry.get("ts"),
            "source": source_name,
            "raw": entry,
        }
        payload["meta"] = meta
        items.append(payload)
    return items


def coach_ingest_text(
    user_id: str,
    text: str,
    dev_mode: bool,
    history: Optional[List[Dict[str, Any]]] = None,
    *,
    persona_id: str = "head_coach",
    provenance_source: str = "head_coach_chat",
    observations: Optional[List[Dict[str, Any]]] = None,
    background_capture: bool = True,
) -> Dict[str, Any]:
    text = (text or "").strip()
    if not user_id:
        return {
            "assistant_text": "Pick a user before chatting so I know whose profile to update.",
            "ucnrr_reply": {"ok": False, "reason": "missing_user"},
        }
    if not text:
        return {
            "assistant_text": "Tell me what changed or what you’re curious about, and I’ll route it through Core.",
            "ucnrr_reply": {"ok": False, "reason": "empty_text"},
        }

    persona_meta = get_persona(persona_id) or get_persona("head_coach") or {}
    persona_title = persona_meta.get("title") or persona_meta.get("name") or persona_id
    persona_tools = persona_meta.get("tools") or []

    can_ingest = "ingest_text" in persona_tools or persona_id == "head_coach"
    can_get_resolved = "get_resolved" in persona_tools or persona_id == "head_coach"

    provenance = {
        "actor": "user",
        "source": provenance_source,
        "persona_id": persona_id,
        "ui": "explorer_final",
        "ts": _iso_now(),
    }

    reply: Dict[str, Any] = {
        "persona_id": persona_id,
        "persona_title": persona_title,
        "persona_tools": persona_tools,
    }

    switch_match = _detect_persona_switch(text, persona_id)
    if switch_match:
        switch_target = switch_match.target_id if get_persona(switch_match.target_id) else None
        reply.update(
            _switch_acknowledgement(
                current_persona=persona_id,
                current_title=persona_title,
                target_persona=switch_target,
            )
        )
        if switch_target:
            _log_switch_event(
                from_persona=persona_id,
                to_persona=switch_target,
                matched_phrase=switch_match.matched_phrase,
                reason=switch_match.reason,
            )
        return reply

    core_response: Dict[str, Any] = {}
    observation_reply: Dict[str, Any] = {"ok": False, "reason": "no_observations"}

    if can_ingest:
        payload = {
            "user_id": user_id,
            "text": text,
            "lines": [],
            "provenance": provenance,
        }

        ucnrr_result = _safe_request(
            lambda: requests.post(
                f"{UCNRR_BASE}/ingest_text",
                json=payload,
                timeout=UCNRR_TIMEOUT,
            )
        )

        reply["ucnrr_reply"] = {
            "ok": ucnrr_result.ok,
            "status": ucnrr_result.status,
            "reason": ucnrr_result.error,
            "data": ucnrr_result.data if not ucnrr_result.ok else None,
        }

        if ucnrr_result.ok and isinstance(ucnrr_result.data, dict):
            reply["ucnrr_reply"].update(ucnrr_result.data)
            core_response = ucnrr_result.data.get("core_response") or {}
        else:
            reply["assistant_text"] = (
                "I couldn’t reach UCN/RR just now. Double-check the service and we can resend that message."
                if not dev_mode
                else "UCN/RR ingestion failed — inspect logs and retry once the service responds (see status pill)."
            )
    else:
        reply["ucnrr_reply"] = {
            "ok": False,
            "reason": "persona_cannot_ingest",
            "message": f"{persona_title} observes but does not record new data.",
        }

    if background_capture:
        obs_items = _prepare_observation_items(observations)
        if obs_items:
            obs_payload = {
                "user_id": user_id,
                "items": obs_items,
                "bundle_type": "observation",
                "source": provenance_source,
            }
            obs_result = _safe_request(
                lambda: requests.post(
                    f"{CORE_BASE}/ingest_bundle",
                    json=obs_payload,
                    timeout=CORE_TIMEOUT,
                )
            )
            observation_reply = {
                "ok": obs_result.ok,
                "status": obs_result.status,
                "reason": obs_result.error,
                "count": len(obs_items),
                "data": obs_result.data,
            }
        else:
            observation_reply = {"ok": False, "reason": "no_items"}
    else:
        observation_reply = {"ok": False, "reason": "capture_disabled"}

    reply["observation_reply"] = observation_reply

    core_resolved: Dict[str, Any] = {}
    if can_get_resolved:
        core_resolved_res = _safe_request(
            lambda: requests.get(
                f"{CORE_BASE}/resolved/{user_id}",
                timeout=CORE_TIMEOUT,
            )
        )
        if core_resolved_res.ok and isinstance(core_resolved_res.data, dict):
            core_resolved = core_resolved_res.data
            reply["core_resolved"] = core_resolved
        else:
            reply["core_error"] = {
                "status": core_resolved_res.status,
                "reason": core_resolved_res.error,
                "data": core_resolved_res.data,
            }
    else:
        reply["core_error"] = {
            "reason": "persona_cannot_access_core",
        }
        reply.setdefault("core_resolved", core_resolved)

    holistic_counts = (
        _holistic_counts(core_response.get("holistic")) if isinstance(core_response, dict) else {"ran": False}
    )
    reply["holistic"] = holistic_counts

    user_context = {
        "top_curiosity": _resolved_context(core_resolved),
        "recent_changes": _recent_changes(core_response),
        "holistic": holistic_counts if holistic_counts.get("ran") else None,
    }

    persona_ctx = {
        "id": persona_id,
        "title": persona_title,
        "style": persona_meta.get("style") or {},
        "tools": persona_tools,
        "system": persona_compose_system_prompt(
            persona_meta,
            dev_mode=dev_mode,
            user_context=user_context,
            persona_id=persona_id,
            display_name=persona_title,
        ),
    }

    chat_messages = _chat_history_to_messages(history)
    if not chat_messages or chat_messages[-1].get("role") != "user" or chat_messages[-1].get("content") != text:
        chat_messages.append({"role": "user", "content": text})

    llm_payload = coach_reply_llm(chat_messages, persona_ctx, user_context, dev_mode)
    reply["assistant_text"] = llm_payload.get("text", "Let’s keep going.")
    if persona_id == "relationship_coach":
        reply["assistant_text"] = rc_scrub(reply["assistant_text"])
    if llm_payload.get("reason") != "ok":
        reply["llm_reason"] = llm_payload.get("reason")
    if llm_payload.get("canonical"):
        reply["canonical_suggestions"] = llm_payload.get("canonical")

    if persona_id == "relationship_coach":
        reply["rc_capture"] = _background_capture_relationship(
            user_id,
            text,
            reply["assistant_text"],
            capture_enabled=background_capture,
            provenance=provenance,
        )

    reply["added_by_core_ai"] = core_response.get("added_by_core_ai", [])
    reply["recent_changes"] = user_context["recent_changes"]
    reply["top_curiosity"] = user_context["top_curiosity"]
    return reply


def coach_upload_files(
    user_id: str,
    files: List[UploadedFile],
    *,
    persona_id: str = "head_coach",
    provenance_source: str = "head_coach_upload",
) -> List[Dict[str, Any]]:
    if not user_id:
        return [
            {
                "ok": False,
                "reason": "missing_user",
            }
        ]

    persona_meta = get_persona(persona_id) or get_persona("head_coach") or {}
    persona_title = persona_meta.get("title") or persona_meta.get("name") or persona_id
    tools = persona_meta.get("tools") or []
    can_upload = "ingest_file" in tools or persona_id == "head_coach"

    results: List[Dict[str, Any]] = []
    if not can_upload:
        return [
            {
                "ok": False,
                "reason": "persona_cannot_upload",
                "message": f"{persona_title} stores guidance only; file ingest is disabled.",
            }
        ]
    for file in files:
        if file is None:
            continue
        filename = getattr(file, "name", "upload")
        mimetype = getattr(file, "type", "application/octet-stream") or "application/octet-stream"
        meta = {
            "actor": "user",
            "source": provenance_source,
            "persona_id": persona_id,
            "filename": filename,
            "mimetype": mimetype,
            "ts": _iso_now(),
        }
        try:
            file_bytes = file.getvalue() if hasattr(file, "getvalue") else file.read()
        except Exception as exc:  # pragma: no cover - streamlit edge case
            results.append({
                "ok": False,
                "filename": filename,
                "reason": f"read_error:{exc}",
            })
            continue

        def _call():
            return requests.post(
                f"{UCNRR_BASE}/ingest_file",
                data={"user_id": user_id, "meta": json.dumps(meta)},
                files={"file": (filename, file_bytes, mimetype)},
                timeout=UCNRR_TIMEOUT,
            )

        service_res = _safe_request(_call)
        payload: Dict[str, Any] = {
            "ok": service_res.ok,
            "filename": filename,
            "reason": service_res.error,
            "status": service_res.status,
        }
        if service_res.ok and isinstance(service_res.data, dict):
            payload.update(service_res.data)
        else:
            payload["data"] = service_res.data
        results.append(payload)

    return results


def apply_canonical_lines(
    user_id: str,
    lines: List[str],
    *,
    persona_id: str = "head_coach",
    actor: str = "assistant",
    source: str = "head_coach",
) -> Dict[str, Any]:
    if not user_id:
        return {"ok": False, "reason": "missing_user"}
    lines = [line.strip() for line in lines if line and line.strip()]
    if not lines:
        return {"ok": False, "reason": "empty_lines"}

    persona_meta = get_persona(persona_id) or get_persona("head_coach") or {}
    tools = persona_meta.get("tools") or []
    persona_title = persona_meta.get("title") or persona_meta.get("name") or persona_id

    if "ingest_text" not in tools and persona_id != "head_coach":
        return {
            "ok": False,
            "reason": "persona_cannot_ingest",
            "message": f"{persona_title} cannot apply canonical lines automatically.",
        }

    payload = {
        "user_id": user_id,
        "text": "",
        "lines": lines,
        "provenance": {
            "actor": actor,
            "source": source,
            "persona_id": persona_id,
            "ui": "explorer_final",
            "ts": _iso_now(),
        },
    }

    result = _safe_request(
        lambda: requests.post(
            f"{UCNRR_BASE}/ingest_text",
            json=payload,
            timeout=UCNRR_TIMEOUT,
        )
    )

    return {
        "ok": result.ok,
        "status": result.status,
        "reason": result.error,
        "data": result.data,
    }


def record_free_text(
    user_id: str,
    text: str,
    *,
    persona_id: str = "head_coach",
    actor: str = "user",
    source: str = "head_coach",
) -> Dict[str, Any]:
    payload = {
        "user_id": user_id,
        "text": text,
        "lines": [],
        "provenance": {
            "actor": actor,
            "source": source,
            "persona_id": persona_id,
            "ui": "explorer_final",
            "ts": _iso_now(),
        },
    }

    result = _safe_request(
        lambda: requests.post(
            f"{UCNRR_BASE}/ingest_text",
            json=payload,
            timeout=UCNRR_TIMEOUT,
        )
    )

    return {
        "ok": result.ok,
        "status": result.status,
        "reason": result.error,
        "data": result.data,
    }


def _partition_rows(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    know: List[Dict[str, Any]] = []
    confirm: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []

    for row in rows:
        rr_val = float(row.get("rr", 0.0) or 0.0)
        curiosity_val = float(row.get("curiosity", 0.0) or 0.0)
        if rr_val >= 70:
            know.append(row)
        elif 40 <= rr_val < 70:
            confirm.append(row)
        else:
            gaps.append(row)
        if curiosity_val >= 60 and row not in gaps:
            gaps.append(row)

    know.sort(key=lambda r: float(r.get("rr", 0.0) or 0.0), reverse=True)
    confirm.sort(key=lambda r: float(r.get("curiosity", 0.0) or 0.0), reverse=True)
    gaps.sort(key=lambda r: float(r.get("curiosity", 0.0) or 0.0), reverse=True)

    return know[:TOP_PLAN_LIMIT], confirm[:TOP_PLAN_LIMIT], gaps[:TOP_PLAN_LIMIT]


def _canonical_suggestions(rows: Iterable[Dict[str, Any]]) -> List[str]:
    suggestions: List[str] = []
    for row in rows:
        path = row.get("path")
        value = row.get("value")
        if not path:
            continue
        if value is None or str(value).strip() == "":
            suggestions.append(f"{path}=<value>")
        else:
            suggestions.append(f"{path}={value}")
    return suggestions[:TOP_PLAN_LIMIT]


def _deterministic_plan(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    know, confirm, gaps = _partition_rows(rows)
    plan = {
        "what_we_know": know,
        "what_to_confirm": confirm,
        "biggest_gaps": gaps,
        "next_best_questions": _canonical_suggestions(gaps or confirm or know),
    }
    return plan


def _plan_summary_with_llm(plan: Dict[str, Any], user_id: str) -> Optional[str]:
    summary_context = json.dumps({"user_id": user_id, "plan": plan}, ensure_ascii=False)
    messages = [
        {
            "role": "system",
            "content": (
                "You are the Head Coach strategy writer. Summarize the plan in <=250 words, "
                "keeping tone confident and supportive. Highlight top curiosity areas and next actions."
            ),
        },
        {
            "role": "user",
            "content": summary_context,
        },
    ]
    llm_res = _llm_chat(messages)
    if not llm_res.ok:
        return None
    data = llm_res.data or {}
    if isinstance(data, dict):
        return (
            (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        ).strip()
    return str(data)


def generate_game_plan(user_id: str) -> Dict[str, Any]:
    if not user_id:
        return {"ok": False, "reason": "missing_user"}

    resolved_res = _safe_request(
        lambda: requests.get(
            f"{CORE_BASE}/resolved/flat/{user_id}",
            timeout=CORE_TIMEOUT,
        )
    )
    if not resolved_res.ok or not isinstance(resolved_res.data, dict):
        return {
            "ok": False,
            "reason": resolved_res.error or "core_unavailable",
            "status": resolved_res.status,
            "data": resolved_res.data,
        }

    rows = resolved_res.data.get("rows") or []
    plan_body = _deterministic_plan(rows)
    summary = None
    if CORE_USE_LLM:
        summary = _plan_summary_with_llm(plan_body, user_id)

    plan = {
        "ok": True,
        "user_id": user_id,
        "generated_at": _iso_now(),
        "sections": plan_body,
        "summary": summary,
    }

    def _call():
        return requests.post(
            f"{CORE_BASE}/coach/plan/{user_id}",
            json=plan,
            timeout=CORE_TIMEOUT,
        )

    store_res = _safe_request(_call)
    if not store_res.ok:
        plan["storage"] = {
            "ok": False,
            "reason": store_res.error,
            "status": store_res.status,
            "data": store_res.data,
        }
    else:
        plan["storage"] = store_res.data if isinstance(store_res.data, dict) else {"ok": True}

    return plan


def run_holistic_review(user_id: str) -> Dict[str, Any]:
    if not user_id:
        return {"ok": False, "reason": "missing_user"}

    hol_res = _safe_request(
        lambda: requests.post(
            f"{CORE_BASE}/holistic/{user_id}",
            json={},
            timeout=CORE_TIMEOUT,
        )
    )

    response: Dict[str, Any] = {
        "ok": hol_res.ok,
        "status": hol_res.status,
        "reason": hol_res.error,
    }

    if hol_res.ok and isinstance(hol_res.data, dict):
        report = hol_res.data
        response["data"] = report
        response["ok"] = bool(report.get("ok", True))
        if not response["ok"]:
            response["reason"] = report.get("reason") or response.get("reason")
        summary = _holistic_counts(report)
        if summary.get("ran"):
            response["summary"] = summary
            badge = _holistic_badge(summary)
            if badge:
                response["badge"] = badge
    else:
        response["data"] = hol_res.data
        return response

    resolved_res = _safe_request(
        lambda: requests.get(
            f"{CORE_BASE}/resolved/{user_id}",
            timeout=CORE_TIMEOUT,
        )
    )

    if resolved_res.ok:
        response["core_resolved"] = resolved_res.data
        response["top_curiosity"] = _resolved_context(resolved_res.data)
    else:
        response["core_error"] = {
            "status": resolved_res.status,
            "reason": resolved_res.error,
            "data": resolved_res.data,
        }

    return response
