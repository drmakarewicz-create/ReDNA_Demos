"""
Human intelligence aggregation helpers (Evergreen Phase 2).

Combines empathy telemetry + curiosity debt to surface a compact snapshot
for Life OS surfaces. Designed to be read-only and safe when telemetry
does not yet exist (returns neutral defaults).
"""

from __future__ import annotations

import json
import math
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from .curiosity.curiosity_engine_v3 import CuriosityEngineV3
from .storage import CORE_DATA_ROOT

EMPATHY_HISTORY_LIMIT = 60
DEFAULT_WINDOW_DAYS = 7
TREND_EPSILON = 0.015


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    try:
        # Handle "Z" suffix manually for older Python
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Empathy telemetry
# ---------------------------------------------------------------------------

def _load_empathy_history(
    user_id: str,
    *,
    data_root: Path,
    window_days: int,
    limit: int = EMPATHY_HISTORY_LIMIT,
) -> List[Dict[str, Any]]:
    """Return recent empathy telemetry entries (newest last)."""

    path = data_root / "telemetry" / "empathy" / f"{user_id}.jsonl"
    if not path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    entries: Deque[Dict[str, Any]] = deque(maxlen=limit)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_timestamp(payload.get("ts"))
            if ts is None:
                continue
            payload["_ts"] = ts
            if ts >= cutoff:
                entries.append(payload)

    return list(entries)


def _summarise_empathy(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute empathy snapshot + simple trend from telemetry history."""

    if not history:
        return {
            "latest": None,
            "trend": {"direction": "steady", "trust_delta": 0.0, "rapport_delta": 0.0, "intensity_delta": 0.0},
            "samples": 0,
            "window_days": DEFAULT_WINDOW_DAYS,
            "history": [],
        }

    latest = history[-1]
    latest_metrics = latest.get("bonding_metrics") or {}
    latest_trust = float(latest_metrics.get("trust_score", 0.5))
    latest_rapport = float(latest_metrics.get("rapport_score", 0.5))
    latest_intensity = float(latest.get("intensity", 0.0))

    previous = history[:-1]
    if previous:
        trust_avg = mean(float((item.get("bonding_metrics") or {}).get("trust_score", 0.5)) for item in previous)
        rapport_avg = mean(float((item.get("bonding_metrics") or {}).get("rapport_score", 0.5)) for item in previous)
        intensity_avg = mean(float(item.get("intensity", 0.0)) for item in previous)
    else:
        trust_avg = latest_trust
        rapport_avg = latest_rapport
        intensity_avg = latest_intensity

    trust_delta = round(latest_trust - trust_avg, 4)
    rapport_delta = round(latest_rapport - rapport_avg, 4)
    intensity_delta = round(latest_intensity - intensity_avg, 4)

    magnitude = max(abs(trust_delta), abs(rapport_delta))
    if magnitude > TREND_EPSILON:
        direction = "up" if (trust_delta + rapport_delta) >= 0 else "down"
    else:
        direction = "steady"

    latest_snapshot = {
        "timestamp": latest["_ts"].isoformat(),
        "emotional_state": latest.get("emotional_state"),
        "intensity": latest_intensity,
        "confidence": float(latest.get("confidence", 0.0)),
        "primary_needs": latest.get("primary_needs", []),
        "recommended_actions": latest.get("recommended_actions", []),
        "bonding_metrics": {
            "trust_score": latest_trust,
            "rapport_score": latest_rapport,
            "turns_observed": int(latest_metrics.get("turns_observed", 0)),
            "positive_turns": int(latest_metrics.get("positive_turns", 0)),
        },
    }

    condensed_history: List[Dict[str, Any]] = []
    for item in history[-15:]:  # cap for response size
        metrics = item.get("bonding_metrics") or {}
        condensed_history.append(
            {
                "timestamp": (_parse_timestamp(item.get("_ts")) or datetime.now(timezone.utc)).isoformat(),
                "emotional_state": item.get("emotional_state"),
                "intensity": float(item.get("intensity", 0.0)),
                "trust_score": float(metrics.get("trust_score", 0.5)),
                "rapport_score": float(metrics.get("rapport_score", 0.5)),
            }
        )

    return {
        "latest": latest_snapshot,
        "trend": {
            "direction": direction,
            "trust_delta": trust_delta,
            "rapport_delta": rapport_delta,
            "intensity_delta": intensity_delta,
        },
        "samples": len(history),
        "window_days": DEFAULT_WINDOW_DAYS,
        "history": condensed_history,
    }


# ---------------------------------------------------------------------------
# Curiosity debt snapshot
# ---------------------------------------------------------------------------

def _load_curiosity_debt(
    user_id: str,
    *,
    data_root: Path,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return sorted debt entries and the last saved agenda (if any)."""

    engine = CuriosityEngineV3(data_root=data_root)
    debt_records = engine.debt_tracker.load(user_id)

    items = sorted(
        (
            {
                "target": target,
                "debt_score": float(record.score),
                "last_seen": record.last_seen,
                "namespace": target.split(".", 1)[0] if "." in target else target,
            }
            for target, record in debt_records.items()
        ),
        key=lambda entry: entry["debt_score"],
        reverse=True,
    )

    agenda_path = data_root / "curiosity" / "agendas" / f"{user_id}.json"
    previous_agenda = None
    if agenda_path.exists():
        try:
            previous_agenda = json.loads(agenda_path.read_text())
        except json.JSONDecodeError:
            previous_agenda = None

    return items, previous_agenda


def _summarise_curiosity(
    user_id: str,
    *,
    data_root: Path,
    top_n: int = 3,
) -> Dict[str, Any]:
    """Return curiosity snapshot with top gaps + trend against last agenda."""

    items, previous_agenda = _load_curiosity_debt(user_id, data_root=data_root)
    top_items = items[:top_n]

    current_avg = mean((item["debt_score"] for item in top_items)) if top_items else 0.0
    previous_avg = 0.0
    if previous_agenda and isinstance(previous_agenda.get("items"), Iterable):
        previous_items: List[Dict[str, Any]] = []
        for entry in previous_agenda["items"]:
            if not isinstance(entry, dict):
                continue
            previous_items.append(
                {
                    "debt_score": float(entry.get("debt_score", 0.0)),
                    "target": entry.get("target"),
                }
            )
        previous_items.sort(key=lambda entry: entry["debt_score"], reverse=True)
        top_previous = previous_items[:top_n]
        previous_avg = mean((entry["debt_score"] for entry in top_previous)) if top_previous else 0.0

    debt_delta = round(current_avg - previous_avg, 4)
    if abs(debt_delta) > TREND_EPSILON:
        direction = "up" if debt_delta > 0 else "down"
    else:
        direction = "steady"

    stale_threshold = datetime.now(timezone.utc) - timedelta(days=DEFAULT_WINDOW_DAYS)
    stale_count = 0
    for item in top_items:
        ts = _parse_timestamp(item.get("last_seen"))
        if ts and ts < stale_threshold:
            stale_count += 1

    # Build daily prompt preview
    engine = CuriosityEngineV3(data_root=data_root)
    prompt_payload = engine.generate_daily_prompt(user_id=user_id, limit=top_n)

    friendly_items = [
        {
            "target": item["target"],
            "namespace": item.get("namespace"),
            "debt_score": round(float(item["debt_score"]), 3),
            "last_seen": item.get("last_seen"),
        }
        for item in top_items
    ]

    return {
        "top_gaps": friendly_items,
        "trend": {
            "direction": direction,
            "average_debt": round(float(current_avg), 3),
            "delta": debt_delta,
            "stale_targets": stale_count,
        },
        "snapshot": {
            "total_records": len(items),
            "generated_at": prompt_payload.get("generated_at"),
            "prompt": prompt_payload.get("prompt"),
            "daily_questions": prompt_payload.get("items", []),
        },
    }


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def build_human_intel_snapshot(
    user_id: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Return combined empathy + curiosity telemetry for Life OS UI surfaces.

    The response is intentionally compact and avoids raising when telemetry
    is missing so that DevX tooling can surface graceful empty states.
    """

    if data_root is None:
        data_root = CORE_DATA_ROOT

    empathy_history = _load_empathy_history(
        user_id,
        data_root=data_root,
        window_days=max(1, window_days),
    )
    empathy = _summarise_empathy(empathy_history)
    curiosity = _summarise_curiosity(user_id, data_root=data_root)

    earliest_ts = min(
        (_parse_timestamp(entry.get("_ts")) for entry in empathy_history),
        default=None,
    )
    summary_window = max(
        window_days,
        math.ceil(
            (datetime.now(timezone.utc) - earliest_ts).days
        )
        if earliest_ts
        else window_days,
    )

    return {
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": summary_window,
        "empathy": empathy,
        "curiosity": curiosity,
    }


__all__ = ["build_human_intel_snapshot"]
