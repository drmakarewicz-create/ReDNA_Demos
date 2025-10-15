"""Holistic review entry-point for Core."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, TypedDict

from . import inference_rules, reconcile, rr_engine
from core_ai import core_ai_expand, core_llm_is_available

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from core_ai import CoreLLMConfig

LoaderFn = Callable[[str], Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]]


class HolisticReport(TypedDict, total=False):
    ok: bool
    user_id: str
    time_ms: float
    async_: bool
    ucn_rr_updates: List[Dict[str, Any]]
    implied_additions: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    warnings: List[str]
    llm_considered: List[str]
    llm_updates: List[Dict[str, Any]]
    llm_skipped: List[str]
    llm_warnings: List[str]
    llm_time_ms: float


def run_holistic(
    user_id: str,
    *,
    loader: LoaderFn,
    baselines: Optional[Dict[str, Any]] = None,
    time_budget_ms: Optional[int] = None,
    use_llm: bool = False,
    llm_config: Optional["CoreLLMConfig"] = None,
    llm_budget_ms: Optional[int] = None,
) -> Tuple[HolisticReport, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Run a holistic review pass and return report + updated state."""

    start = time.perf_counter()
    resolved_doc, evidence_doc, flat_doc = loader(user_id)
    resolved_map = _ensure_resolved_map(resolved_doc)

    updates: List[Dict[str, Any]] = []
    implied: List[Dict[str, Any]] = []
    warnings: List[str] = []

    now_iso = _now_iso()

    for path, entry in resolved_map.items():
        if not isinstance(entry, dict):
            continue
        value = _extract_value(entry)
        if value is None:
            continue

        old_ucn = entry.get("ucn")
        new_ucn = _backfill_ucn(entry)
        entry["ucn"] = new_ucn

        previous_rr = entry.get("rr")
        new_rr = rr_engine.compute_rr(path, value, new_ucn, baselines, previous_rr=previous_rr)
        entry["rr"] = new_rr
        entry["curiosity"] = max(0.0, min(100.0, 100.0 - new_rr))

        rr_engine.apply_floors(entry)
        entry.setdefault("provenance", {})
        entry.setdefault("reasons", [])
        entry.setdefault("notes", {})
        entry["provenance"]["step"] = "core-holistic"
        entry["notes"].setdefault("summary", "Normalized by holistic review")
        _append_note(entry, f"Holistic review normalization applied on {now_iso}.")
        entry["updated_ts"] = now_iso
        entry.setdefault("value", value)
        entry.setdefault("value_type", _value_type(value))

        if _changed(old_ucn, entry["ucn"]) or _changed(previous_rr, new_rr):
            updates.append(
                {
                    "path": path,
                    "old": {
                        "ucn": old_ucn,
                        "rr": previous_rr,
                        "curiosity": None if previous_rr is None else max(0.0, 100.0 - float(previous_rr)),
                    },
                    "new": {
                        "ucn": entry["ucn"],
                        "rr": entry["rr"],
                        "curiosity": entry.get("curiosity"),
                    },
                }
            )

    suggestions = inference_rules.infer(resolved_map)
    for suggestion in suggestions:
        path = suggestion.path
        existing = resolved_map.get(path)
        existing_value = _extract_value(existing)
        if existing and existing_value not in (None, "", "unknown", "Unknown"):
            # Skip if trait already has a meaningful value
            continue

        entry = {
            "value": suggestion.value,
            "value_type": _value_type(suggestion.value),
            "ucn": float(suggestion.ucn),
            "reasons": [f"Implied by rule: {suggestion.reason}"],
            "provenance": {
                "source": "core",
                "step": "core-holistic",
                "reason": suggestion.reason,
            },
            "notes": {
                "summary": "Implied by holistic inference",
                "evidence": [f"Rule {suggestion.reason} applied"],
            },
            "updated_ts": now_iso,
        }
        entry["rr"] = rr_engine.compute_rr(path, suggestion.value, entry["ucn"], baselines)
        entry["curiosity"] = max(0.0, min(100.0, 100.0 - entry["rr"]))
        rr_engine.apply_floors(entry)
        resolved_map[path] = entry
        implied.append(
            {
                "path": path,
                "value": suggestion.value,
                "ucn": entry["ucn"],
                "reason": suggestion.reason,
            }
        )

    contradictions = reconcile.find_contradictions(resolved_map)
    if contradictions:
        warnings.append(f"{len(contradictions)} potential contradictions detected")
    reconcile.apply(contradictions, resolved_map)

    llm_considered: List[str] = []
    llm_updates: List[Dict[str, Any]] = []
    llm_skipped: List[str] = []
    llm_warnings: List[str] = []
    llm_time_ms = 0.0

    if use_llm and core_llm_is_available(llm_config):
        targets = _collect_llm_targets(resolved_map, contradictions)
        llm_considered = sorted(targets.keys())
        if targets:
            llm_start = time.perf_counter()
            try:
                suggestions = core_ai_expand(
                    llm_config,  # type: ignore[arg-type]
                    user_id=user_id,
                    resolved=resolved_map,
                    new_paths=targets,
                    allow_overwrite_paths=targets.keys(),
                )
            except Exception as exc:  # pragma: no cover - defensive
                suggestions = {}
                llm_warnings.append(f"Holistic LLM error: {exc}")
            llm_time_ms = (time.perf_counter() - llm_start) * 1000.0
            if llm_budget_ms and llm_time_ms > float(llm_budget_ms):
                llm_warnings.append(
                    f"Holistic LLM exceeded budget ({llm_time_ms:.0f} ms > {llm_budget_ms} ms)"
                )

            for path, meta in suggestions.items():
                merge_result = _merge_llm_suggestion(
                    path,
                    meta,
                    resolved_map,
                    baselines,
                    now_iso,
                )
                if merge_result is None:
                    continue
                previous, updated = merge_result
                llm_updates.append(
                    {
                        "path": path,
                        "old": previous,
                        "new": {
                            "value": _extract_value(updated),
                            "ucn": updated.get("ucn"),
                            "rr": updated.get("rr"),
                        },
                    }
                )

            llm_skipped = sorted(set(llm_considered) - set(suggestions.keys()))
        else:
            llm_warnings.append("Holistic LLM enabled but no qualifying traits were found.")
    elif use_llm and not core_llm_is_available(llm_config):
        llm_warnings.append("Holistic LLM enabled but Core LLM configuration is unavailable.")

    resolved_doc["resolved"] = resolved_map
    resolved_doc.setdefault("user_id", user_id)
    resolved_doc["last_holistic_ts"] = now_iso

    flat_doc = {
        "user_id": resolved_doc.get("user_id", user_id),
        "rows": _build_flat_rows(resolved_map),
        "updated_ts": now_iso,
    }

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    report: HolisticReport = {
        "ok": True,
        "user_id": user_id,
        "time_ms": round(elapsed_ms, 3),
        "async_": bool(time_budget_ms and elapsed_ms > float(time_budget_ms)),
        "ucn_rr_updates": updates,
        "implied_additions": implied,
        "contradictions": contradictions,
        "warnings": warnings,
    }

    if use_llm:
        report["llm_considered"] = llm_considered
        report["llm_updates"] = llm_updates
        report["llm_skipped"] = llm_skipped
        report["llm_warnings"] = llm_warnings
        report["llm_time_ms"] = round(llm_time_ms, 3)

    return report, resolved_doc, evidence_doc, flat_doc


LLM_LOW_UCN_THRESHOLD = 650.0
MAX_LLM_TARGETS = 20


def _collect_llm_targets(
    resolved_map: Dict[str, Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    targets: Dict[str, Dict[str, Any]] = {}

    for path, entry in resolved_map.items():
        if not isinstance(entry, dict):
            continue
        value = _extract_value(entry)
        ucn = entry.get("ucn")
        provenance = entry.get("provenance") if isinstance(entry.get("provenance"), dict) else {}
        if provenance.get("step") == "core-holistic-llm":
            continue
        if value in (None, "", "unknown", "Unknown"):
            targets[path] = {
                "value": value,
                "ucn": ucn,
                "reasons": entry.get("reasons", []),
            }
        elif isinstance(ucn, (int, float)) and float(ucn) < LLM_LOW_UCN_THRESHOLD:
            targets[path] = {
                "value": value,
                "ucn": ucn,
                "reasons": entry.get("reasons", []),
            }
        if len(targets) >= MAX_LLM_TARGETS:
            break

    if contradictions:
        for issue in contradictions:
            candidate = issue.get("path")
            if isinstance(candidate, str) and candidate:
                targets.setdefault(candidate, {
                    "value": _extract_value(resolved_map.get(candidate)),
                    "ucn": resolved_map.get(candidate, {}).get("ucn") if isinstance(resolved_map.get(candidate), dict) else None,
                    "reasons": issue.get("reasons", []),
                })
            for extra in issue.get("paths") or []:
                if isinstance(extra, str) and extra:
                    targets.setdefault(extra, {
                        "value": _extract_value(resolved_map.get(extra)),
                        "ucn": resolved_map.get(extra, {}).get("ucn") if isinstance(resolved_map.get(extra), dict) else None,
                        "reasons": issue.get("reasons", []),
                    })
            if len(targets) >= MAX_LLM_TARGETS:
                break

    truncated: Dict[str, Dict[str, Any]] = {}
    for path in targets.keys():
        truncated[path] = {
            "value": targets[path].get("value"),
            "ucn": targets[path].get("ucn"),
            "reasons": targets[path].get("reasons", []),
        }
        if len(truncated) >= MAX_LLM_TARGETS:
            break
    return truncated


def _merge_llm_suggestion(
    path: str,
    suggestion: Dict[str, Any],
    resolved_map: Dict[str, Dict[str, Any]],
    baselines: Optional[Dict[str, Any]],
    now_iso: str,
) -> Optional[Tuple[Optional[Dict[str, Any]], Dict[str, Any]]]:
    value = suggestion.get("resolved_value")
    if value is None:
        return None

    ucn = suggestion.get("ucn") if isinstance(suggestion.get("ucn"), (int, float)) else 110.0
    reasons = suggestion.get("reasons") if isinstance(suggestion.get("reasons"), list) else ["core-holistic-llm"]
    provenance = suggestion.get("provenance") if isinstance(suggestion.get("provenance"), dict) else {}

    previous_entry = resolved_map.get(path)
    previous_snapshot = None
    if isinstance(previous_entry, dict):
        previous_snapshot = {
            "value": _extract_value(previous_entry),
            "ucn": previous_entry.get("ucn"),
            "rr": previous_entry.get("rr"),
        }

    entry: Dict[str, Any] = {
        "value": value,
        "value_type": _value_type(value),
        "ucn": float(ucn),
        "reasons": reasons,
        "provenance": {
            **(previous_entry.get("provenance") if isinstance(previous_entry, dict) and isinstance(previous_entry.get("provenance"), dict) else {}),
            **provenance,
            "source": provenance.get("source", "core"),
            "step": "core-holistic-llm",
        },
        "updated_ts": now_iso,
    }

    entry["rr"] = rr_engine.compute_rr(path, value, entry["ucn"], baselines)
    entry["curiosity"] = max(0.0, min(100.0, 100.0 - entry["rr"]))
    rr_engine.apply_floors(entry)

    notes = suggestion.get("notes") if isinstance(suggestion.get("notes"), dict) else {}
    entry["notes"] = {
        "summary": notes.get("summary", "Holistic LLM inference"),
        "evidence": notes.get("evidence", []),
    }
    _append_note(entry, f"Holistic LLM inference on {now_iso}.")

    resolved_map[path] = entry
    return previous_snapshot, entry


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _ensure_resolved_map(resolved_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    resolved = resolved_doc.get("resolved")
    if not isinstance(resolved, dict):
        resolved = {}
        resolved_doc["resolved"] = resolved
    return resolved


def _extract_value(entry: Optional[Dict[str, Any]]) -> Optional[Any]:
    if not isinstance(entry, dict):
        return None
    if entry.get("value") not in (None, ""):
        return entry.get("value")
    return entry.get("resolved_value")


def _backfill_ucn(entry: Dict[str, Any]) -> float:
    ucn = entry.get("ucn")
    if isinstance(ucn, (int, float)) and ucn >= rr_engine.MIN_PRESENT_UCN:
        return float(ucn)

    confidence = entry.get("confidence")
    if isinstance(confidence, (int, float)):
        if confidence <= 1.0:
            guess = confidence * 1000.0
        else:
            guess = confidence * 10.0
        return float(max(rr_engine.MIN_PRESENT_UCN, min(1000.0, guess)))

    provenance = entry.get("provenance") if isinstance(entry.get("provenance"), dict) else {}
    source = str(provenance.get("source", "")).lower()

    if "canonical" in source or "manual" in source:
        return 900.0
    if "photo" in source:
        return 820.0
    if "ucnrr" in source or "model" in source or "core-ai" in source:
        return 720.0
    return 600.0


def _append_note(entry: Dict[str, Any], message: str) -> None:
    notes = entry.setdefault("notes", {})
    evidence = notes.setdefault("evidence", [])
    if isinstance(evidence, list) and message not in evidence:
        evidence.append(message)


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, bool):
            return "boolean"
        return "number"
    return "string"


def _build_flat_rows(resolved: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path, entry in resolved.items():
        if not isinstance(entry, dict):
            continue
        row = {
            "path": path,
            "value": entry.get("value", entry.get("resolved_value")),
            "value_type": entry.get("value_type", _value_type(entry.get("value"))),
            "confidence": entry.get("confidence"),
            "provenance": entry.get("provenance"),
            "ucn": entry.get("ucn"),
            "reasons": entry.get("reasons"),
            "flags": entry.get("flags"),
            "status": entry.get("status"),
            "rr": entry.get("rr"),
            "curiosity": entry.get("curiosity"),
            "notes": entry.get("notes"),
            "updated_ts": entry.get("updated_ts"),
            "canonical_path": entry.get("canonical_path"),
            "canonical_value": entry.get("canonical_value"),
            "original_path": entry.get("provenance", {}).get("original_path") if isinstance(entry.get("provenance"), dict) else None,
            "value_alias": entry.get("provenance", {}).get("value_alias") if isinstance(entry.get("provenance"), dict) else None,
            "path_alias": entry.get("provenance", {}).get("path_alias") if isinstance(entry.get("provenance"), dict) else None,
        }
        rows.append(row)
    return rows


def _changed(old: Optional[Any], new: Optional[Any]) -> bool:
    if old is None and new is None:
        return False
    if isinstance(old, float) and isinstance(new, float):
        return not math.isclose(old, new, rel_tol=1e-6)
    return old != new


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["HolisticReport", "run_holistic"]
