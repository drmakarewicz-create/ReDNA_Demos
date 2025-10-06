"""UI-facing registry for persona cards surfaced in the Head Coach UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional


@dataclass(slots=True)
class PersonaCard:
    id: str
    title: str
    accent: str
    icon: str = ""
    tagline: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    honesty_mode: str = "balanced"
    allowed_honesty: List[str] = field(default_factory=list)
    vibe_keywords: List[str] = field(default_factory=list)
    beta: bool = False
    dev_only: bool = False

    def payload(self) -> Dict[str, object]:
        data = asdict(self)
        data.pop("dev_only", None)
        return data


_CARDS: Dict[str, PersonaCard] = {}


def _coerce_card(payload: Mapping[str, object]) -> PersonaCard:
    required = {"id", "title", "accent"}
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"Missing card keys: {', '.join(missing)}")
    kwargs = dict(payload)
    kwargs.setdefault("icon", "")
    kwargs.setdefault("tagline", "")
    kwargs.setdefault("description", "")
    kwargs.setdefault("keywords", [])
    kwargs.setdefault("honesty_mode", "balanced")
    kwargs.setdefault("allowed_honesty", [])
    kwargs.setdefault("vibe_keywords", [])
    kwargs.setdefault("beta", False)
    kwargs.setdefault("dev_only", False)
    return PersonaCard(**kwargs)


def register_card(payload: Mapping[str, object]) -> None:
    card = _coerce_card(payload)
    _CARDS[card.id] = card


def get_card(persona_id: str) -> Optional[PersonaCard]:
    return _CARDS.get(persona_id)


def list_cards(*, include_dev: bool = False) -> List[Dict[str, object]]:
    cards: Iterable[PersonaCard] = _CARDS.values()
    if not include_dev:
        cards = [card for card in cards if not card.dev_only]
    return [card.payload() for card in cards]


def clear_cards() -> None:
    _CARDS.clear()


__all__ = [
    "PersonaCard",
    "register_card",
    "get_card",
    "list_cards",
    "clear_cards",
]
