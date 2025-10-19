from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import CuriosityItem
from ReDNACoreDemo.core.storage import ensure_dirs_for_user

OPEN_STATUSES = {"queued", "asked"}
REASON_MULTIPLIERS = {
    "contradiction": 1.5,
    "novel_signal": 1.3,
    "policy_borderline": 1.2,
    "low_confidence": 1.0,
    "value_missing": 0.9,
    "schema_repair_low_conf": 0.8,
}

_ITEM_INDEX: Dict[str, str] = {}
_ITEM_CACHE: Dict[str, CuriosityItem] = {}
_LOCK = threading.Lock()


def _queue_path(user_id: str) -> Path:
    dirs = ensure_dirs_for_user(user_id)
    return dirs["udir"] / "curiosity.jsonl"


def _serialize(item: CuriosityItem) -> str:
    return json.dumps(item.model_dump(mode="json"), ensure_ascii=True)


def _deserialize(line: str) -> CuriosityItem:
    data = json.loads(line)
    return CuriosityItem.model_validate(data)


def _register_items(user_id: str, items: List[CuriosityItem]) -> None:
    for item in items:
        _ITEM_INDEX[item.id] = user_id
        _ITEM_CACHE[item.id] = item


def _load_items(user_id: str) -> List[CuriosityItem]:
    path = _queue_path(user_id)
    items: List[CuriosityItem] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(_deserialize(line))
                except Exception:
                    continue
    _register_items(user_id, items)
    return items


def _write_items(user_id: str, items: List[CuriosityItem]) -> None:
    path = _queue_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(_serialize(item) + "\n")
    tmp_path.replace(path)
    _register_items(user_id, items)


def _expire_items(items: List[CuriosityItem]) -> bool:
    changed = False
    now = datetime.now(timezone.utc)
    for item in items:
        if item.status in OPEN_STATUSES and item.expires_at and item.expires_at < now:
            item.status = "expired"
            changed = True
    return changed


def _can_enqueue(
    items: List[CuriosityItem],
    trait_id: str,
    reason_code: str,
    cooldown_key: str,
    cooldown_sec: int,
    max_open_per_user: int,
    max_open_per_trait: int,
) -> bool:
    now = datetime.now(timezone.utc)
    open_items = [item for item in items if item.status in OPEN_STATUSES]
    if len(open_items) >= max_open_per_user:
        return False

    open_for_trait = [item for item in open_items if item.trait_id == trait_id]
    if len(open_for_trait) >= max_open_per_trait:
        return False

    for item in open_items:
        if item.trait_id != trait_id:
            continue
        if item.reason_code != reason_code:
            continue
        if item.cooldown_key != cooldown_key:
            continue
        reference = item.asked_at or item.created_at
        if reference and (now - reference).total_seconds() < cooldown_sec:
            return False

    return True


def _recalculate_information_gain(item: CuriosityItem) -> float:
    inputs = item.inputs or {}

    probability = inputs.get("p")
    if probability is not None:
        try:
            probability = float(probability)
        except (TypeError, ValueError):
            probability = None
    rr_score = inputs.get("rr")
    learned_rr = inputs.get("learned_rr") or inputs.get("base_rr")

    uncertainty = 0.5
    if probability is not None:
        probability = max(0.0, min(1.0, probability))
        uncertainty = 1.0 - abs(probability - 0.5) * 2.0
    elif rr_score is not None and learned_rr is not None:
        try:
            rr_score = float(rr_score)
            learned_rr = float(learned_rr)
            uncertainty = 1.0 - min(1.0, abs(rr_score - learned_rr) / 100.0)
        except (TypeError, ValueError):
            uncertainty = 0.5

    impact_weight = inputs.get("impact_weight") or 0.5
    try:
        impact_weight = float(impact_weight)
    except (TypeError, ValueError):
        impact_weight = 0.5

    created_at = item.created_at
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
    recency_weight = math.exp(-age_hours / 168.0)

    reason_mult = REASON_MULTIPLIERS.get(item.reason_code, 1.0)
    ig = uncertainty * impact_weight * recency_weight * reason_mult
    return max(0.0, min(1.0, ig))


def enqueue(
    item: CuriosityItem,
    *,
    max_open_per_user: int,
    max_open_per_trait: int,
    cooldown_sec: int,
) -> Optional[CuriosityItem]:
    with _LOCK:
        items = _load_items(item.user_id)
        changed = _expire_items(items)
        if changed:
            _write_items(item.user_id, items)
            items = _load_items(item.user_id)

        if not _can_enqueue(
            items,
            item.trait_id,
            item.reason_code,
            item.cooldown_key,
            cooldown_sec,
            max_open_per_user,
            max_open_per_trait,
        ):
            return None

        items.append(item)
        _write_items(item.user_id, items)
        return item


def list_items(
    user_id: str,
    *,
    status: Optional[str] = "queued",
    limit: int = 20,
    min_information_gain: float = 0.0,
) -> List[CuriosityItem]:
    with _LOCK:
        items = _load_items(user_id)
        expired_changed = _expire_items(items)
        recalc_changed = False

        results: List[CuriosityItem] = []
        for item in items:
            new_ig = _recalculate_information_gain(item)
            if not math.isclose(new_ig, item.expected_information_gain, rel_tol=1e-6):
                item.expected_information_gain = new_ig
                recalc_changed = True

            if status and item.status != status:
                continue
            if item.expected_information_gain < min_information_gain:
                continue
            results.append(item.model_copy(deep=True))

        if expired_changed or recalc_changed:
            _write_items(user_id, items)

        results.sort(key=lambda entry: entry.expected_information_gain, reverse=True)
        if len(results) > limit:
            results = results[:limit]
        return results


def _locate_item(item_id: str) -> Optional[Tuple[str, List[CuriosityItem], CuriosityItem]]:
    user_id = _ITEM_INDEX.get(item_id)
    if not user_id:
        return None
    items = _load_items(user_id)
    for item in items:
        if item.id == item_id:
            return user_id, items, item
    return None


def ack(item_id: str) -> Optional[CuriosityItem]:
    with _LOCK:
        located = _locate_item(item_id)
        if not located:
            return None
        user_id, items, item = located
        if item.status == "queued":
            item.status = "asked"
            item.asked_at = datetime.now(timezone.utc)
            _write_items(user_id, items)
        return item.model_copy(deep=True)


def answer(item_id: str, answer_text: str, follow_up_event_id: Optional[str] = None) -> Optional[CuriosityItem]:
    with _LOCK:
        located = _locate_item(item_id)
        if not located:
            return None
        user_id, items, item = located
        item.status = "answered"
        item.answer_text = answer_text
        item.answered_at = datetime.now(timezone.utc)
        if follow_up_event_id:
            item.inputs["follow_up_event_id"] = follow_up_event_id
        _write_items(user_id, items)
        return item.model_copy(deep=True)


def dismiss(item_id: str, reason: Optional[str] = None) -> Optional[CuriosityItem]:
    with _LOCK:
        located = _locate_item(item_id)
        if not located:
            return None
        user_id, items, item = located
        item.status = "dismissed"
        item.dismiss_reason = reason
        item.dismissed_at = datetime.now(timezone.utc)
        _write_items(user_id, items)
        return item.model_copy(deep=True)


def get_item(item_id: str) -> Optional[CuriosityItem]:
    with _LOCK:
        located = _locate_item(item_id)
        if not located:
            return None
        _, _, item = located
        return item.model_copy(deep=True)


def ttl_cleanup(user_id: str) -> None:
    with _LOCK:
        items = _load_items(user_id)
        if _expire_items(items):
            _write_items(user_id, items)
