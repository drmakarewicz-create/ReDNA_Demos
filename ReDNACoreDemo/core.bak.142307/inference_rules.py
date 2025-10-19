"""Rule-based inference helpers for holistic review."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml optional
    yaml = None

_RULES_PATH_ENV = "CORE_INFERENCE_RULES_PATH"
_DEFAULT_RULES_PATH = Path(__file__).resolve().parents[1] / "data/config/inference_rules.yaml"


@dataclass
class InferenceSuggestion:
    path: str
    value: Any
    ucn: float
    reason: str


class InferenceEngine:
    def __init__(self, rules_path: Optional[Path] = None) -> None:
        self._rules_path = rules_path or Path(os.getenv(_RULES_PATH_ENV, str(_DEFAULT_RULES_PATH)))
        self._rules = self._load_rules()

    def _load_rules(self) -> List[Dict[str, Any]]:
        if yaml is None or not self._rules_path.exists():
            return []
        try:
            with self._rules_path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
            rules = payload.get("rules")
            return [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []
        except Exception:
            return []

    def infer(self, resolved: Dict[str, Dict[str, Any]]) -> List[InferenceSuggestion]:
        suggestions: List[InferenceSuggestion] = []
        if not self._rules:
            return suggestions

        for rule in self._rules:
            conditions = rule.get("conditions") if isinstance(rule.get("conditions"), list) else []
            suggest = rule.get("suggest") if isinstance(rule.get("suggest"), dict) else None
            if not conditions or not suggest:
                continue
            if self._matches(conditions, resolved):
                path = str(suggest.get("path")) if suggest.get("path") else None
                value = suggest.get("value")
                if not path:
                    continue
                ucn = float(suggest.get("ucn", 300.0))
                reason = str(suggest.get("reason", rule.get("name", "inference")))
                suggestions.append(InferenceSuggestion(path=path, value=value, ucn=ucn, reason=reason))
        return suggestions

    def _matches(self, conditions: Iterable[Dict[str, Any]], resolved: Dict[str, Dict[str, Any]]) -> bool:
        for cond in conditions:
            path = cond.get("path")
            if not isinstance(path, str):
                return False
            entry = resolved.get(path)
            value = _extract_value(entry)
            if value is None:
                return False
            if "equals" in cond:
                expected = cond["equals"]
                if not _value_equals(value, expected):
                    return False
            elif "in" in cond:
                candidates = cond["in"] if isinstance(cond["in"], list) else []
                if not any(_value_equals(value, candidate) for candidate in candidates):
                    return False
            else:
                return False
        return True


def _extract_value(entry: Optional[Dict[str, Any]]) -> Optional[Any]:
    if not isinstance(entry, dict):
        return None
    if entry.get("value") is not None:
        return entry.get("value")
    return entry.get("resolved_value")


def _value_equals(value: Any, expected: Any) -> bool:
    if isinstance(value, str) and isinstance(expected, str):
        return value.strip().lower() == expected.strip().lower()
    return value == expected


_ENGINE = InferenceEngine()


def infer(resolved: Dict[str, Dict[str, Any]]) -> List[InferenceSuggestion]:
    return _ENGINE.infer(resolved)


def rule_count() -> int:
    return len(getattr(_ENGINE, "_rules", []))


__all__ = ["InferenceEngine", "InferenceSuggestion", "infer", "rule_count"]
