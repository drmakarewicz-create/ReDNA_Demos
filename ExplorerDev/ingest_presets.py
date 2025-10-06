"""Preset payloads for the Diagnostics ingest harness."""

from __future__ import annotations

from typing import Any, Dict, List

_TEXT_PRESETS: List[Dict[str, Any]] = [
    {
        "key": "simple_note",
        "label": "Simple note",
        "body": "Just checking in on the latest engagement notes for this member.",
        "provenance": {"source": "devexp", "kind": "note", "tags": ["demo"]},
    },
    {
        "key": "relationship_cue",
        "label": "Relationship cue",
        "body": "Member mentioned appreciating thoughtful follow-ups and reflective prompts.",
        "provenance": {"source": "relationship_coach", "kind": "cue", "tags": ["relationship", "tone"]},
    },
    {
        "key": "photo_mention",
        "label": "Photo mention",
        "body": "Uploaded a new profile photo highlighting outdoor adventures.",
        "provenance": {"source": "photo_coach", "kind": "media", "tags": ["photo", "profile"]},
    },
]

_KV_PRESETS: List[Dict[str, Any]] = [
    {
        "key": "devexp_ping",
        "label": "devexp_ping token",
        "body": "devexp_ping={{uuid}}",
        "provenance": {"source": "devexp", "kind": "ping", "tags": ["diagnostics"]},
    },
    {
        "key": "style_traits",
        "label": "Style traits",
        "body": "eye_color=blue\nbudget_style=conservative\nconversation_pace=brisk",
        "provenance": {"source": "devexp", "kind": "traits", "tags": ["style"]},
    },
    {
        "key": "locale_context",
        "label": "Locale context",
        "body": "region=west_coast\nlocale=en_US\nlocal_events=bay_area_artwalk",
        "provenance": {"source": "devexp", "kind": "context", "tags": ["locale"]},
    },
]

_JSON_PRESETS: List[Dict[str, Any]] = [
    {
        "key": "minimal_contract",
        "label": "Minimal UCNRR contract",
        "body": (
            "{\n"
            "  \"user_id\": \"demo_user\",\n"
            "  \"text\": \"Member shared a concise update about their latest win.\",\n"
            "  \"provenance\": {\"source\": \"devexp\", \"kind\": \"note\"}\n"
            "}"
        ),
        "provenance": {},
    },
    {
        "key": "rich_contract",
        "label": "Rich contract",
        "body": (
            "{\n"
            "  \"user_id\": \"demo_user\",\n"
            "  \"text\": \"Member asked for next steps on their relationship growth plan.\",\n"
            "  \"provenance\": {\n"
            "    \"source\": \"relationship_coach\",\n"
            "    \"kind\": \"question\",\n"
            "    \"tags\": [\"relationship\", \"growth\"]\n"
            "  },\n"
            "  \"metadata\": {\n"
            "    \"channel\": \"sandbox_demo\",\n"
            "    \"importance\": \"informational\"\n"
            "  }\n"
            "}"
        ),
        "provenance": {},
    },
]

_PRESET_TABLE = {
    "text": _TEXT_PRESETS,
    "key=value": _KV_PRESETS,
    "json": _JSON_PRESETS,
}


def list_presets(payload_type: str) -> List[Dict[str, Any]]:
    """Return presets for the requested payload type."""

    normalized = (payload_type or "").strip().lower()
    return list(_PRESET_TABLE.get(normalized, ()))


def get_preset(payload_type: str, key: str) -> Dict[str, Any] | None:
    normalized = (payload_type or "").strip().lower()
    if not key:
        return None
    for entry in _PRESET_TABLE.get(normalized, ()):  # type: ignore[arg-type]
        if entry.get("key") == key:
            return dict(entry)
    return None
