# ReDNACoreDemo/app.py
# ReDNA Core Service — tolerant ingest with backward compatibility
# - Accepts both {user_id, observations={...}} (current callers)
#   and {user_id, changes={...}} (new shape)
# - Preserves existing storage layout and env variables
# - Falls back to pulling from UCN/RR when no payload is provided

from __future__ import annotations

import json
import math
import os
import random
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from fastapi import Body, FastAPI, HTTPException

from core_ai import CoreLLMConfig, core_ai_expand, core_llm_is_available, map_to_canonical
from core.holistic import HolisticReport, run_holistic
from core import inference_rules
from core.storage import ensure_dirs_for_user as storage_ensure_dirs_for_user

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

APP_VERSION = "1.2.1"

# ----------------------------------------------------------------------------
# Storage roots — honour existing layout/env first
# ----------------------------------------------------------------------------
def _resolve_workspace_root() -> Path:
    raw = os.getenv("WORKSPACE_ROOT")
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2]


WORKSPACE_ROOT = _resolve_workspace_root()
REDNA_CORE_DATA = os.getenv("REDNA_CORE_DATA")
CORE_DATA_DIR = os.getenv("CORE_DATA_DIR")

if REDNA_CORE_DATA:
    CORE_ROOT = Path(REDNA_CORE_DATA).expanduser().resolve()
elif CORE_DATA_DIR:
    CORE_ROOT = Path(CORE_DATA_DIR).expanduser().resolve()
else:
    CORE_ROOT = (WORKSPACE_ROOT / "data").resolve()

CORE_ROOT.mkdir(parents=True, exist_ok=True)

USERS_DIR = CORE_ROOT / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)

UCNRR_BASE = os.getenv("UCNRR_URL", os.getenv("UCNRR_BASE", "http://127.0.0.1:8011")).rstrip("/")

STATS_DIR = CORE_ROOT / "_stats"
STATS_DIR.mkdir(parents=True, exist_ok=True)
TRAIT_STATS_PATH = STATS_DIR / "trait_ucn.json"

DEFAULT_BASELINES_PATH = Path(__file__).resolve().parent / "data/config/rr_baselines.yaml"
RR_BASELINES_PATH = Path(
    os.getenv("CORE_RR_BASELINES_PATH", str(DEFAULT_BASELINES_PATH))
).expanduser().resolve()

RR_SAMPLE_SIZE = int(os.getenv("CORE_RR_SAMPLE_SIZE", "100"))
RR_MIN_POINTS = int(os.getenv("CORE_RR_MIN_POINTS", "20"))
RR_PRIOR_SAMPLE = int(os.getenv("CORE_RR_PRIOR_SAMPLE", "50"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


CORE_USE_LLM = _env_bool("CORE_USE_LLM", False)
CORE_LLM_PROVIDER = os.getenv("CORE_LLM_PROVIDER")
CORE_LLM_MODEL = os.getenv("CORE_LLM_MODEL")
CORE_LLM_BASE_URL = os.getenv("CORE_LLM_BASE_URL")
CORE_LLM_API_KEY = os.getenv("CORE_LLM_API_KEY")
CORE_LLM_TIMEOUT = int(os.getenv("CORE_LLM_TIMEOUT", "15"))
CORE_LLM_MAX_CONTEXT = int(os.getenv("CORE_LLM_MAX_CONTEXT", "200"))

CORE_HOLISTIC_ON_INGEST = _env_bool("CORE_HOLISTIC_ON_INGEST", False)
CORE_HOLISTIC_MAX_MS = int(os.getenv("CORE_HOLISTIC_MAX_MS", "300"))
CORE_HOLISTIC_USE_LLM = _env_bool("CORE_HOLISTIC_USE_LLM", False)
CORE_HOLISTIC_LLM_BUDGET_MS = int(os.getenv("CORE_HOLISTIC_LLM_BUDGET_MS", "15000"))
CORE_HOLISTIC_SCHEDULE_ENABLED = _env_bool("CORE_HOLISTIC_SCHEDULE_ENABLED", True)
CORE_HOLISTIC_SCHEDULE_DAYS = float(os.getenv("CORE_HOLISTIC_SCHEDULE_DAYS", "7"))

_HOLISTIC_SCHEDULER_STOP = threading.Event()
_HOLISTIC_SCHEDULER_THREAD: Optional[threading.Thread] = None
_HOLISTIC_SCHEDULER_MIN_SECONDS = 60.0

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _now() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _user_paths(user_id: str) -> Dict[str, Path]:
    paths = storage_ensure_dirs_for_user(user_id)
    root = paths["udir"]
    return {
        "root": root,
        "resolved": paths["resolved"],
        "flat": root / "resolved_flat.json",
        "coach_plan": root / "coach_plan.json",
        "last_holistic": root / "last_holistic.json",
        "raw_imports": root / "raw_imports.json",
    }


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _append_raw_payload(user_id: str, raw_payload: Any, source: str = "photo-coach", meta: Optional[Dict[str, Any]] = None) -> None:
    if raw_payload is None:
        return
    try:
        serializable = json.loads(json.dumps(raw_payload))
    except Exception:
        serializable = {"value": str(raw_payload)}

    paths = _user_paths(user_id)
    doc = _read_json(paths["raw_imports"]) or {"items": []}
    items = doc.setdefault("items", [])
    entry = {
        "ts": _now_iso(),
        "source": source,
        "payload": serializable,
    }
    if meta:
        try:
            entry["meta"] = json.loads(json.dumps(meta))
        except Exception:
            entry["meta"] = meta
    items.append(entry)
    _write_json(paths["raw_imports"], doc)


def _norm_path(path: str) -> str:
    return re.sub(r"^PaDNA\.", "", (path or "").strip())


def _value_type_for(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_trait_stats() -> Dict[str, Any]:
    data = _read_json(TRAIT_STATS_PATH)
    return data if isinstance(data, dict) else {}


def _save_trait_stats(stats: Dict[str, Any]) -> None:
    _write_json(TRAIT_STATS_PATH, stats)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _holistic_review_due(user_id: str, now_dt: datetime, interval: timedelta) -> bool:
    if interval.total_seconds() <= 0:
        return False
    paths = _user_paths(user_id)
    last_doc = _read_json(paths["last_holistic"]) if paths["last_holistic"].exists() else {}
    last_ts = last_doc.get("ran_at")
    if not last_ts and isinstance(last_doc.get("report"), dict):
        last_ts = last_doc["report"].get("ran_at")
    parsed = _parse_iso_datetime(last_ts)
    if parsed is None:
        return True
    return now_dt - parsed >= interval


def _run_holistic_scheduler_tick(interval: timedelta) -> None:
    try:
        candidates = [path.name for path in USERS_DIR.iterdir() if path.is_dir()]
    except FileNotFoundError:
        return

    now_dt = datetime.now(timezone.utc)
    for user_id in candidates:
        if not user_id:
            continue
        if not _holistic_review_due(user_id, now_dt, interval):
            continue
        try:
            _run_holistic_and_store(user_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[holistic-scheduler] user={user_id} error={exc}")


def _holistic_scheduler_loop(interval_seconds: float) -> None:
    wait_seconds = max(_HOLISTIC_SCHEDULER_MIN_SECONDS, interval_seconds)
    interval = timedelta(seconds=interval_seconds)
    while not _HOLISTIC_SCHEDULER_STOP.is_set():
        _run_holistic_scheduler_tick(interval)
        _HOLISTIC_SCHEDULER_STOP.wait(wait_seconds)


def _start_holistic_scheduler() -> None:
    global _HOLISTIC_SCHEDULER_THREAD
    if _holistic_schedule_disabled():
        return
    if _HOLISTIC_SCHEDULER_THREAD and _HOLISTIC_SCHEDULER_THREAD.is_alive():
        return
    interval_days = max(CORE_HOLISTIC_SCHEDULE_DAYS, 0.0)
    interval_seconds = max(interval_days * 86400.0, _HOLISTIC_SCHEDULER_MIN_SECONDS)
    thread = threading.Thread(
        target=_holistic_scheduler_loop,
        args=(interval_seconds,),
        name="core-holistic-scheduler",
        daemon=True,
    )
    _HOLISTIC_SCHEDULER_STOP.clear()
    thread.start()
    _HOLISTIC_SCHEDULER_THREAD = thread


def _stop_holistic_scheduler() -> None:
    global _HOLISTIC_SCHEDULER_THREAD
    thread = _HOLISTIC_SCHEDULER_THREAD
    if not thread:
        return
    _HOLISTIC_SCHEDULER_STOP.set()
    thread.join(timeout=1.0)
    _HOLISTIC_SCHEDULER_THREAD = None


def _holistic_schedule_disabled() -> bool:
    return not CORE_HOLISTIC_SCHEDULE_ENABLED or CORE_HOLISTIC_SCHEDULE_DAYS <= 0


def _load_rr_baselines() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    defaults = {"mean": 700.0, "std": 150.0}
    meta = {
        "path": str(RR_BASELINES_PATH),
        "loaded": False,
        "reason": None,
    }
    if not RR_BASELINES_PATH.exists() or yaml is None:
        meta["reason"] = "missing" if not RR_BASELINES_PATH.exists() else "yaml_unavailable"
        return {"defaults": defaults, "traits": {}}, meta
    try:
        with RR_BASELINES_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        defaults_conf = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
        traits_conf = data.get("traits") if isinstance(data.get("traits"), dict) else {}
        merged_defaults = {**defaults, **{k: float(v) for k, v in defaults_conf.items() if isinstance(v, (int, float))}}
        meta["loaded"] = True
        return {"defaults": merged_defaults, "traits": traits_conf}, meta
    except Exception as exc:  # pragma: no cover - defensive
        meta["reason"] = f"error:{exc}"[:80]
        return {"defaults": defaults, "traits": {}}, meta


RR_BASELINES, RR_BASELINES_META = _load_rr_baselines()


def _baseline_for_trait(path: str) -> Dict[str, float]:
    trait_conf = RR_BASELINES.get("traits", {}).get(path, {}) if isinstance(RR_BASELINES.get("traits"), dict) else {}
    defaults = RR_BASELINES.get("defaults", {})
    mean = float(trait_conf.get("mean", defaults.get("mean", 700.0)))
    std = float(trait_conf.get("std", defaults.get("std", 150.0)))
    return {"mean": mean, "std": max(std, 1.0)}


DEFAULT_TRAIT_ALIASES_PATH = Path(__file__).resolve().parent / "data/config/trait_aliases.yaml"
TRAIT_ALIASES_PATH = Path(os.getenv("CORE_TRAIT_ALIASES_PATH", str(DEFAULT_TRAIT_ALIASES_PATH))).expanduser().resolve()


def _normalize_alias_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _load_trait_aliases(path: Path) -> Dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _build_trait_alias_indexes(conf: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    alias_lookup: Dict[str, str] = {}
    value_lookup: Dict[str, Dict[str, str]] = {}
    for canonical, spec in conf.items():
        if not isinstance(canonical, str) or not isinstance(spec, dict):
            continue
        alias_lookup[_normalize_alias_key(canonical)] = canonical
        alias_lookup[_normalize_alias_key(_norm_path(canonical))] = canonical
        aliases = spec.get("aliases") if isinstance(spec.get("aliases"), (list, tuple)) else []
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            alias_lookup[_normalize_alias_key(alias)] = canonical
            alias_lookup[_normalize_alias_key(_norm_path(alias))] = canonical
        value_aliases = spec.get("value_aliases") if isinstance(spec.get("value_aliases"), dict) else {}
        if value_aliases:
            mapped: Dict[str, str] = {}
            for alias_value, canonical_value in value_aliases.items():
                if not isinstance(alias_value, str):
                    continue
                mapped[_normalize_alias_key(alias_value)] = canonical_value
            if mapped:
                value_lookup[canonical] = mapped
    return alias_lookup, value_lookup


TRAIT_ALIASES_RAW = _load_trait_aliases(TRAIT_ALIASES_PATH)
TRAIT_ALIAS_LOOKUP, TRAIT_VALUE_ALIAS_LOOKUP = _build_trait_alias_indexes(TRAIT_ALIASES_RAW)


def _canonicalise_path(raw_path: str) -> Tuple[str, Optional[str], Optional[str]]:
    original = (raw_path or "").strip()
    if not original:
        return "", None, None
    canonical_full = TRAIT_ALIAS_LOOKUP.get(_normalize_alias_key(original))
    alias_source: Optional[str] = None
    if canonical_full:
        alias_source = original
    else:
        short = _norm_path(original)
        canonical_full = TRAIT_ALIAS_LOOKUP.get(_normalize_alias_key(short))
        if canonical_full:
            alias_source = original
    if not canonical_full and original.startswith("PaDNA."):
        canonical_full = original
    if canonical_full:
        storage_path = canonical_full
    else:
        storage_path = _norm_path(original)
    return storage_path, canonical_full if canonical_full else None, alias_source


def _canonicalise_value(canonical_full: Optional[str], value: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
    if canonical_full is None:
        return value, None
    lookup = TRAIT_VALUE_ALIAS_LOOKUP.get(canonical_full)
    if not lookup:
        return value, None

    def _match_alias(normalized: str) -> Optional[Any]:
        if normalized in lookup:
            return lookup[normalized]
        for alias_key, canonical in lookup.items():
            if isinstance(alias_key, str) and alias_key.startswith("~"):
                token = alias_key[1:]
                if token and token in normalized:
                    return canonical
        return None

    def _map_single(item: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
        if isinstance(item, bool):
            normalized = "true" if item else "false"
        else:
            normalized = _normalize_alias_key(item) if isinstance(item, str) else None

        if normalized:
            mapped = _match_alias(normalized)
            if mapped is not None:
                return mapped, {"alias": item, "canonical": mapped}
        return item, None

    if isinstance(value, list):
        mapped: List[Any] = []
        alias_hits: List[Any] = []
        for element in value:
            converted, meta = _map_single(element)
            mapped.append(converted)
            if meta:
                alias_hits.append(meta)
        if alias_hits:
            return mapped, {"aliases": value, "canonical": mapped}
        return value, None
    if isinstance(value, tuple):
        mapped_list: List[Any] = []
        alias_hits: List[Any] = []
        for element in value:
            converted, meta = _map_single(element)
            mapped_list.append(converted)
            if meta:
                alias_hits.append(meta)
        if alias_hits:
            return mapped_list, {"aliases": list(value), "canonical": mapped_list}
        return value, None
    mapped_value, info = _map_single(value)
    if info:
        return mapped_value, info
    return value, None


def _canonicalise_observation(raw_path: str, meta: Any) -> Tuple[str, Optional[str], Dict[str, Any], Dict[str, Any]]:
    storage_path, canonical_full, alias_source = _canonicalise_path(raw_path)
    transform: Dict[str, Any] = {}
    if isinstance(meta, dict):
        normalized_meta = dict(meta)
    else:
        normalized_meta = {"resolved_value": meta}
    value = normalized_meta.get("resolved_value", normalized_meta.get("value"))

    if canonical_full is None:
        cfg = _build_core_ai_config()
        ai_suggestion = map_to_canonical(
            cfg,
            raw_path=raw_path,
            raw_value=value,
            trait_aliases=TRAIT_ALIASES_RAW,
            value_aliases=TRAIT_VALUE_ALIAS_LOOKUP,
        )
        if ai_suggestion:
            candidate_path = ai_suggestion.get("canonical_path")
            if isinstance(candidate_path, str) and candidate_path:
                canonical_full = candidate_path
                storage_path = candidate_path
                suggested_value = ai_suggestion.get("canonical_value")
                if suggested_value is not None:
                    normalized_meta["resolved_value"] = suggested_value
                    value = suggested_value
                transform["ai_mapper"] = {
                    "path": candidate_path,
                    "confidence": ai_suggestion.get("confidence"),
                    "notes": ai_suggestion.get("notes"),
                }
                if alias_source is None:
                    alias_source = raw_path

    value = normalized_meta.get("resolved_value", normalized_meta.get("value"))
    canonical_value, value_info = _canonicalise_value(canonical_full, value)
    if value_info:
        if "resolved_value" in normalized_meta:
            normalized_meta["resolved_value"] = canonical_value
        elif "value" in normalized_meta:
            normalized_meta["value"] = canonical_value
        else:
            normalized_meta["resolved_value"] = canonical_value
        transform["value_alias"] = value_info
    if alias_source:
        transform["path_alias"] = alias_source
    return storage_path, canonical_full, normalized_meta, transform


def _percentile_value(sorted_values: List[float], percentile: float) -> Optional[float]:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _recompute_stats_entry(entry: Dict[str, Any]) -> None:
    users = entry.setdefault("users", {})
    values = [float(v) for v in users.values() if isinstance(v, (int, float))]
    entry["count"] = len(values)
    if not values:
        entry["ucn_values_sample"] = []
        entry["mean"] = entry["std"] = entry["p25"] = entry["p50"] = entry["p75"] = None
        entry["last_updated"] = _now()
        return

    entry["mean"] = sum(values) / len(values)
    entry["std"] = _std(values)
    sorted_vals = sorted(values)
    entry["p25"] = _percentile_value(sorted_vals, 0.25)
    entry["p50"] = _percentile_value(sorted_vals, 0.50)
    entry["p75"] = _percentile_value(sorted_vals, 0.75)
    if len(values) <= RR_SAMPLE_SIZE:
        entry["ucn_values_sample"] = values
    else:
        entry["ucn_values_sample"] = random.sample(values, RR_SAMPLE_SIZE)
    entry["last_updated"] = _now()


def _update_stats_entry(stats: Dict[str, Any], trait_path: str, user_id: str, ucn: float) -> None:
    entry = stats.setdefault(trait_path, {})
    users = entry.setdefault("users", {})
    users[user_id] = float(ucn)
    _recompute_stats_entry(entry)


def _generate_baseline_samples(trait_path: str, count: int) -> List[float]:
    cfg = _baseline_for_trait(trait_path)
    mean = cfg.get("mean", 700.0)
    std = max(cfg.get("std", 150.0), 1.0)
    return [_clamp(random.gauss(mean, std), 1.0, 999.999) for _ in range(max(count, 0))]


def _percentile_rank(values: List[float], target: float) -> float:
    if not values:
        return 0.5
    sorted_vals = sorted(values)
    less = sum(1 for v in sorted_vals if v < target)
    equal = sum(1 for v in sorted_vals if math.isclose(v, target, rel_tol=1e-9))
    n = len(sorted_vals)
    return _clamp((less + 0.5 * equal) / n, 0.0, 1.0)


def _compute_rr_and_curiosity(
    stats: Dict[str, Any],
    trait_path: str,
    user_id: str,
    ucn: float,
) -> Tuple[Optional[float], Optional[float], str, int]:
    entry = stats.get(trait_path) or {}
    users = entry.get("users") if isinstance(entry.get("users"), dict) else {}
    peer_values = [float(v) for uid, v in users.items() if uid != user_id and isinstance(v, (int, float))]
    method = "percentile"
    working = list(peer_values)
    if len(working) < RR_MIN_POINTS:
        working.extend(_generate_baseline_samples(trait_path, RR_PRIOR_SAMPLE))
        method = "prior+percentile"
    if not working:
        return None, None, method, len(peer_values)
    percentile = _percentile_rank(working, float(ucn))
    rr = round(_clamp(percentile * 100.0, 0.0, 100.0), 5)
    curiosity = round(_clamp(100.0 - rr, 0.0, 100.0), 5)
    return rr, curiosity, method, len(peer_values)


def _normalise_notes(notes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(notes, dict):
        return {}
    summary = str(notes.get("summary", "")).strip()
    return {
        "summary": summary,
        "evidence": [str(item).strip() for item in notes.get("evidence", []) if str(item).strip()],
        "coach_instructions": [
            str(item).strip() for item in notes.get("coach_instructions", []) if str(item).strip()
        ],
        "data_gaps": [str(item).strip() for item in notes.get("data_gaps", []) if str(item).strip()],
    }


def _merge_notes(*notes_items: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    def append_unique(dest: List[str], items: List[str]) -> None:
        for item in items:
            if item and item not in dest:
                dest.append(item)

    merged = {
        "summary": "",
        "evidence": [],
        "coach_instructions": [],
        "data_gaps": [],
    }
    for raw in notes_items:
        note = _normalise_notes(raw)
        if note.get("summary") and not merged["summary"]:
            merged["summary"] = note["summary"]
        append_unique(merged["evidence"], note.get("evidence", []))
        append_unique(merged["coach_instructions"], note.get("coach_instructions", []))
        append_unique(merged["data_gaps"], note.get("data_gaps", []))

    if not merged["summary"]:
        merged["summary"] = "Trait confidence updated."
    return merged


def _deterministic_notes(trait_path: str, rr: Optional[float], curiosity: Optional[float]) -> Dict[str, Any]:
    if rr is None or curiosity is None:
        return {}
    if rr >= 80:
        summary = f"High confidence ({rr} RR) for {trait_path}."
        instructions = ["Explore adjacent traits to deepen profile richness."]
        gaps = ["Capture supporting context if available, but priority is low."]
    elif rr >= 40:
        summary = f"Moderate confidence ({rr} RR) — consider light confirmation."
        instructions = ["Ask the user a confirming follow-up or request a quick example."]
        gaps = ["Direct confirmation or secondary evidence would reduce curiosity."]
    else:
        summary = f"Low comparative confidence ({rr} RR)."
        instructions = ["Plan focused questions to validate or correct this trait."]
        gaps = ["Need explicit statement or artifact to raise confidence."]
    return {
        "summary": summary,
        "evidence": [],
        "coach_instructions": instructions,
        "data_gaps": gaps,
    }


def _apply_rr_notes_and_stats(
    user_id: str,
    resolved: Dict[str, Any],
    updated_paths: Sequence[str],
    previous_resolved: Dict[str, Any],
    *,
    compute_rr: bool = True,
) -> Tuple[List[str], bool]:
    if not updated_paths:
        return [], False

    stats = _load_trait_stats()
    stats_updated = False
    persist_needed = False
    rr_updates: List[str] = []

    for path in sorted(set(updated_paths)):
        entry = resolved.get(path)
        if not isinstance(entry, dict):
            continue

        if not compute_rr:
            entry["updated_ts"] = _now_iso()
            persist_needed = True
            continue

        ucn = entry.get("ucn")
        if not isinstance(ucn, (int, float)):
            continue
        rr, curiosity, method, peer_count = _compute_rr_and_curiosity(stats, path, user_id, float(ucn))
        if rr is not None and curiosity is not None:
            if entry.get("rr") != rr or entry.get("curiosity") != curiosity:
                entry["rr"] = rr
                entry["curiosity"] = curiosity
                persist_needed = True
            else:
                entry.setdefault("rr", rr)
                entry.setdefault("curiosity", curiosity)

        deterministic = _deterministic_notes(path, rr, curiosity)
        existing_notes = previous_resolved.get(path, {}).get("notes")
        current_notes = entry.get("notes")
        merged_notes = _merge_notes(current_notes, deterministic, existing_notes)
        if merged_notes:
            if merged_notes != current_notes:
                persist_needed = True
            entry["notes"] = merged_notes

        entry["updated_ts"] = _now_iso()
        persist_needed = True

        _update_stats_entry(stats, path, user_id, float(ucn))
        stats_updated = True
        rr_updates.append(path)

        rr_display = rr if rr is not None else "NA"
        curiosity_display = curiosity if curiosity is not None else "NA"
        print(
            f"rr: trait={path} n={peer_count} rr={rr_display} curiosity={curiosity_display} method={method}"
        )

    if stats_updated:
        _save_trait_stats(stats)

    return rr_updates, persist_needed

def _entry_from_meta(meta: Any, default_prov: Dict[str, Any]) -> Dict[str, Any]:
    # Already in stored shape
    if isinstance(meta, dict) and {"value", "value_type", "confidence"}.issubset(meta.keys()):
        merged = dict(meta)
        # Ensure provenance exists
        prov = merged.get("provenance") or {}
        if "source" not in prov:
            prov = {**default_prov, **prov}
        merged["provenance"] = prov
        return merged

    # Normalise resolved_value/ucn/etc into stored schema
    if isinstance(meta, dict):
        value = meta.get("resolved_value", meta.get("value"))
        ucn = meta.get("ucn")
        reasons = meta.get("reasons")
        flags = meta.get("flags")
        status = meta.get("status")
        provenance = dict(meta.get("provenance", {})) or dict(default_prov)
        notes = meta.get("notes") if isinstance(meta.get("notes"), dict) else None
    else:
        value = meta
        ucn = None
        reasons = None
        flags = None
        status = None
        provenance = dict(default_prov)
        notes = None

    if "source" not in provenance:
        provenance.setdefault("source", "ucnrr")
    entry: Dict[str, Any] = {
        "value": value,
        "value_type": _value_type_for(value),
        "confidence": (float(ucn) / 1000.0) if isinstance(ucn, (int, float)) else None,
        "provenance": provenance,
    }
    if ucn is not None:
        entry["ucn"] = ucn
    if reasons:
        entry["reasons"] = reasons
    if flags:
        entry["flags"] = flags
    if status is not None:
        entry["status"] = status
    if notes:
        entry["notes"] = notes
    return entry


def _upsert_observation(
    resolved: Dict[str, Any],
    raw_path: str,
    meta: Any,
    default_prov: Dict[str, Any],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool, bool]:
    storage_path, canonical_full, normalized_meta, transform = _canonicalise_observation(raw_path, meta)
    if not storage_path:
        return None, None, False, False

    entry = _entry_from_meta(normalized_meta, default_prov)
    prov = entry.setdefault("provenance", {})
    if raw_path:
        prov.setdefault("original_path", raw_path)
    if canonical_full:
        entry["canonical_path"] = canonical_full
        entry.setdefault("canonical_value", entry.get("value"))
        prov.setdefault("canonical_path", canonical_full)
    if "value_alias" in transform:
        prov.setdefault("value_alias" if canonical_full else "value_alias_note", transform["value_alias"])
        entry.setdefault("canonical_value", entry.get("value"))
    if "path_alias" in transform:
        prov.setdefault("path_alias", transform["path_alias"])
    if "ai_mapper" in transform:
        prov.setdefault("canonical_mapper", transform["ai_mapper"])
        entry.setdefault("canonical_value", entry.get("value"))

    changed = resolved.get(storage_path) != entry
    if changed:
        resolved[storage_path] = entry

    alias_storage = _norm_path(raw_path)
    alias_removed = False
    if alias_storage and alias_storage != storage_path and alias_storage in resolved:
        if alias_storage != storage_path:
            resolved.pop(alias_storage, None)
            alias_removed = True

    return storage_path, normalized_meta, changed, alias_removed


def _pull_from_ucnrr(user_id: str) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{UCNRR_BASE}/legacy_export", params={"user_id": user_id}, timeout=10)
        if not resp.ok:
            return {}
        snap = (resp.json() or {}).get("snapshot") or {}
        resolved = snap.get("resolved") or {}
        return resolved if isinstance(resolved, dict) else {}
    except Exception:
        return {}


def _build_core_ai_config() -> Optional[CoreLLMConfig]:
    if not CORE_USE_LLM:
        return None

    provider = CORE_LLM_PROVIDER or os.getenv("LLM_PROVIDER")
    model = CORE_LLM_MODEL or os.getenv("LLM_MODEL")
    base_url = CORE_LLM_BASE_URL or os.getenv("LLM_BASE_URL")
    api_key = CORE_LLM_API_KEY or os.getenv("LLM_API_KEY")

    if not (provider and model and base_url):
        return None

    return CoreLLMConfig(
        provider=provider,
        model=model,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        timeout=CORE_LLM_TIMEOUT,
        max_context=CORE_LLM_MAX_CONTEXT,
    )


app = FastAPI(title="ReDNA Core Service", version=APP_VERSION)


@app.on_event("startup")
def _startup_scheduler() -> None:
    _start_holistic_scheduler()


@app.on_event("shutdown")
def _shutdown_scheduler() -> None:
    _stop_holistic_scheduler()


@app.get("/health")
def health() -> Dict[str, Any]:
    cfg = _build_core_ai_config()
    return {
        "ok": True,
        "data_dir": CORE_ROOT.as_posix(),
        "version": APP_VERSION,
        "core_ai_enabled": bool(core_llm_is_available(cfg)),
        "core_ai_provider": cfg.provider if cfg else None,
        "core_ai_model": cfg.model if cfg else None,
        "rr_engine": "percentile+prior",
        "rr_sample_size": RR_SAMPLE_SIZE,
        "rr_min_points": RR_MIN_POINTS,
        "rr_baselines_loaded": RR_BASELINES_META.get("loaded"),
        "rr_baselines_path": RR_BASELINES_META.get("path"),
        "rr_baselines_reason": RR_BASELINES_META.get("reason"),
        "holistic": {
            "enabled": CORE_HOLISTIC_ON_INGEST,
            "rules_loaded": inference_rules.rule_count() > 0,
            "baselines_loaded": bool(RR_BASELINES_META.get("loaded")),
            "time_budget_ms": CORE_HOLISTIC_MAX_MS,
        },
    }


@app.post("/user/{user_id}/ensure")
def ensure_user(user_id: str) -> Dict[str, Any]:
    paths = _user_paths(user_id)
    if not paths["resolved"].exists():
        _write_json(paths["resolved"], {"user_id": user_id, "resolved": {}, "schema_version": 4})
    if not paths["flat"].exists():
        _write_json(paths["flat"], {"rows": [], "ts": _now()})
    return {"ok": True, "user_dir": paths["root"].as_posix()}


@app.get("/resolved/{user_id}")
def get_resolved(user_id: str) -> Dict[str, Any]:
    paths = _user_paths(user_id)
    return _read_json(paths["resolved"]) or {"user_id": user_id, "resolved": {}, "schema_version": 4}


@app.get("/resolved/flat/{user_id}")
def get_resolved_flat(user_id: str) -> Dict[str, Any]:
    doc = get_resolved(user_id)
    rows = []
    for path, val in (doc.get("resolved") or {}).items():
        provenance = val.get("provenance") if isinstance(val.get("provenance"), dict) else {}
        canonical_path = val.get("canonical_path") or provenance.get("canonical_path")
        canonical_value = val.get("canonical_value", val.get("value"))
        original_path = provenance.get("original_path")
        value_alias = provenance.get("value_alias") or provenance.get("value_alias_note")
        path_alias = provenance.get("path_alias")
        rows.append({
            "path": path,
            "value": val.get("value"),
            "value_type": val.get("value_type"),
            "confidence": val.get("confidence"),
            "provenance": val.get("provenance"),
            "ucn": val.get("ucn"),
            "reasons": val.get("reasons"),
            "flags": val.get("flags"),
            "status": val.get("status"),
            "rr": val.get("rr"),
            "curiosity": val.get("curiosity"),
            "notes": val.get("notes"),
            "updated_ts": val.get("updated_ts"),
            "canonical_path": canonical_path,
            "canonical_value": canonical_value,
            "original_path": original_path,
            "value_alias": value_alias,
            "path_alias": path_alias,
        })
    return {"user_id": user_id, "rows": rows}


def _holistic_loader(user_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    paths = _user_paths(user_id)
    resolved_doc = _read_json(paths["resolved"]) or {"user_id": user_id, "resolved": {}, "schema_version": 4}
    flat_doc = _read_json(paths["flat"]) or {"user_id": user_id, "rows": []}
    evidence_doc: Dict[str, Any] = {"items": []}
    return resolved_doc, evidence_doc, flat_doc


def _holistic_saver(
    user_id: str,
    resolved_doc: Dict[str, Any],
    _evidence_doc: Dict[str, Any],
    flat_doc: Dict[str, Any],
) -> None:
    paths = _user_paths(user_id)
    _write_json(paths["resolved"], resolved_doc)
    _write_json(paths["flat"], flat_doc)


def _apply_incoming_observations(
    resolved: Dict[str, Any],
    incoming: Dict[str, Any],
    default_prov: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Dict[str, Any]], bool]:
    changed_paths: List[str] = []
    incoming_meta: Dict[str, Dict[str, Any]] = {}
    persist_needed = False

    for raw_path, meta in incoming.items():
        path, normalised_meta, changed, alias_removed = _upsert_observation(
            resolved,
            raw_path,
            meta,
            default_prov,
        )
        if not path:
            continue
        if changed:
            changed_paths.append(path)
            if normalised_meta is not None:
                incoming_meta[path] = normalised_meta
            persist_needed = True
        elif alias_removed:
            persist_needed = True

    return changed_paths, incoming_meta, persist_needed


def _holistic_summary(report: HolisticReport) -> Dict[str, Any]:
    updates = report.get("ucn_rr_updates") or []
    implied = report.get("implied_additions") or []
    contradictions = report.get("contradictions") or []
    llm_considered = report.get("llm_considered") or []
    llm_updates = report.get("llm_updates") or []
    llm_skipped = report.get("llm_skipped") or []
    return {
        "ran": True,
        "async": bool(report.get("async_")),
        "ucn_rr_updates": int(len(updates)),
        "implied_additions": int(len(implied)),
        "contradictions": int(len(contradictions)),
        "llm_considered": int(len(llm_considered)),
        "llm_updates": int(len(llm_updates)),
        "llm_skipped": int(len(llm_skipped)),
    }


def _persist_last_holistic(
    user_id: str,
    report: HolisticReport,
) -> Dict[str, Any]:
    summary = _holistic_summary(report)

    updates_paths = [
        item.get("path")
        for item in (report.get("ucn_rr_updates") or [])
        if isinstance(item, dict) and item.get("path")
    ]
    implied_entries = [
        item for item in (report.get("implied_additions") or []) if isinstance(item, dict) and item.get("path")
    ]
    implied_paths = [item["path"] for item in implied_entries]
    implied_reasons = {item["path"]: item.get("reason") for item in implied_entries}

    contradiction_targets: List[str] = []
    for item in report.get("contradictions") or []:
        if isinstance(item, dict):
            if isinstance(item.get("path"), str) and item.get("path"):
                contradiction_targets.append(item["path"])
            paths = item.get("paths")
            if isinstance(paths, list):
                for candidate in paths:
                    if isinstance(candidate, str) and candidate:
                        contradiction_targets.append(candidate)

    touched = sorted({*updates_paths, *implied_paths, *contradiction_targets})

    snapshot = {
        "user_id": user_id,
        "ran_at": _now_iso(),
        "async": summary["async"],
        "counts": {
            "ucn_rr_updates": summary["ucn_rr_updates"],
            "implied_additions": summary["implied_additions"],
            "contradictions": summary["contradictions"],
            "llm_considered": summary.get("llm_considered", 0),
            "llm_updates": summary.get("llm_updates", 0),
            "llm_skipped": summary.get("llm_skipped", 0),
        },
        "paths": {
            "all": touched,
            "ucn_rr_updates": updates_paths,
            "implied": implied_paths,
            "contradictions": contradiction_targets,
        },
        "implied_reasons": implied_reasons,
        "report": report,
    }

    if report.get("llm_considered") or report.get("llm_updates"):
        snapshot["llm"] = {
            "considered": report.get("llm_considered", []),
            "updates": report.get("llm_updates", []),
            "skipped": report.get("llm_skipped", []),
            "warnings": report.get("llm_warnings", []),
            "time_ms": report.get("llm_time_ms"),
        }

    paths = _user_paths(user_id)
    _write_json(paths["last_holistic"], snapshot)
    return summary


def _skip_holistic_summary() -> Dict[str, Any]:
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


def _run_holistic_and_store(user_id: str) -> Tuple[HolisticReport, Dict[str, Any]]:
    report, resolved_doc, evidence_doc, flat_doc = run_holistic(
        user_id,
        loader=_holistic_loader,
        baselines=RR_BASELINES,
        time_budget_ms=CORE_HOLISTIC_MAX_MS,
        use_llm=CORE_HOLISTIC_USE_LLM,
        llm_config=_build_core_ai_config(),
        llm_budget_ms=CORE_HOLISTIC_LLM_BUDGET_MS,
    )
    _holistic_saver(user_id, resolved_doc, evidence_doc, flat_doc)
    summary = _persist_last_holistic(user_id, report)
    return report, summary


@app.post("/holistic/{user_id}")
def holistic_endpoint(user_id: str) -> HolisticReport:
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    _user_paths(user_id)  # ensure dirs
    report, _summary = _run_holistic_and_store(user_id)
    return report


@app.post("/ingest_from_ucnrr")
def ingest_from_ucnrr(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    user_id = (payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    paths = _user_paths(user_id)
    if payload.get("raw_payload") is not None:
        meta: Dict[str, Any] = {}
        if isinstance(payload.get("raw_counts"), dict):
            meta["counts"] = payload["raw_counts"]
        if isinstance(payload.get("raw_notes"), list):
            meta["notes"] = payload["raw_notes"]
        _append_raw_payload(
            user_id,
            payload.get("raw_payload"),
            source="photo-coach",
            meta=meta or None,
        )

    doc = _read_json(paths["resolved"]) or {"user_id": user_id, "resolved": {}, "schema_version": 4}
    resolved = doc.setdefault("resolved", {})
    previous_resolved = {
        path: dict(entry)
        for path, entry in resolved.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }

    persist_needed = False
    incoming: Dict[str, Any] = {}
    if isinstance(payload.get("observations"), dict) and payload["observations"]:
        incoming = payload["observations"]
    elif isinstance(payload.get("changes"), dict) and payload["changes"]:
        incoming = payload["changes"]

    default_prov = {"source": "ucnrr"}
    caller_changed: List[str] = []
    incoming_meta: Dict[str, Dict[str, Any]] = {}

    if incoming:
        caller_changed, incoming_meta, persist_needed_flag = _apply_incoming_observations(
            resolved,
            incoming,
            default_prov,
        )
        persist_needed = persist_needed or persist_needed_flag
    else:
        pulled = _pull_from_ucnrr(user_id)
        if pulled:
            pulled_changed, _pulled_meta, persist_needed_flag = _apply_incoming_observations(
                resolved,
                pulled,
                default_prov,
            )
            if pulled_changed:
                caller_changed.extend(pulled_changed)
            persist_needed = persist_needed or persist_needed_flag
        else:
            ensure_user(user_id)

    cfg = _build_core_ai_config()
    ai_added_meta: Dict[str, Dict[str, Any]] = {}
    if core_llm_is_available(cfg):
        try:
            ai_added_meta = core_ai_expand(
                cfg,
                user_id=user_id,
                resolved=resolved,
                new_paths=incoming_meta,
                exclude_paths=incoming_meta.keys(),
            )
        except Exception as exc:
            print(f"[core-ai] user={user_id} expand_error={exc}")
            ai_added_meta = {}

    ai_added: List[str] = []
    rr_updates: List[str] = []
    if ai_added_meta:
        ai_default_prov = {"source": "core-ai"}
        for path, meta in ai_added_meta.items():
            entry = _entry_from_meta(meta, ai_default_prov)
            if resolved.get(path) == entry:
                continue
            if path in incoming_meta:
                # Skip paths supplied by caller in this transaction
                continue
            resolved[path] = entry
            ai_added.append(path)
            persist_needed = True

    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    compute_rr_curiosity = options.get("compute_rr_curiosity", True)

    updated_paths = list(set(caller_changed + ai_added))
    rr_updates, rr_persist = _apply_rr_notes_and_stats(
        user_id=user_id,
        resolved=resolved,
        updated_paths=updated_paths,
        previous_resolved=previous_resolved,
        compute_rr=bool(compute_rr_curiosity),
    )
    if rr_persist:
        persist_needed = True

    if persist_needed:
        doc["ts"] = _now()
        _write_json(paths["resolved"], doc)
        flat_rows = [{"path": k, **v} for k, v in sorted(resolved.items())]
        _write_json(paths["flat"], {"rows": flat_rows, "ts": _now()})

    if CORE_HOLISTIC_ON_INGEST:
        _, holistic_summary = _run_holistic_and_store(user_id)
    else:
        holistic_summary = _skip_holistic_summary()

    response = {
        "ok": True,
        "user_id": user_id,
        "changed": caller_changed + ai_added,
        "resolved_keys": list(resolved.keys()),
        "changed_from_caller": caller_changed,
        "added_by_core_ai": ai_added,
        "count": {
            "caller": len(caller_changed),
            "core_ai": len(ai_added),
            "total": len(caller_changed) + len(ai_added),
        },
        "holistic": holistic_summary,
    }

    if rr_updates:
        response["rr_curiosity_updated"] = rr_updates

    if ai_added and cfg:
        response["core_ai"] = {"model": cfg.model, "provider": cfg.provider}

    return response


@app.post("/import/padna_json")
def import_padna_json(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    user_id = (payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    observations: Dict[str, Any] = {}
    if isinstance(payload.get("observations"), dict):
        observations = payload["observations"]
    elif isinstance(payload.get("traits"), list):
        for item in payload["traits"]:
            if not isinstance(item, dict):
                continue
            path = (item.get("path") or "").strip()
            if not path:
                continue
            meta = dict(item)
            meta.pop("path", None)
            if "value" not in meta and "resolved_value" in meta:
                meta["value"] = meta["resolved_value"]
            observations[path] = meta

    if not observations:
        raise HTTPException(status_code=400, detail="observations required")

    default_prov = payload.get("default_provenance") if isinstance(payload.get("default_provenance"), dict) else {}
    provenance = {"source": "padna_import", **default_prov}

    paths = _user_paths(user_id)
    doc = _read_json(paths["resolved"]) or {"user_id": user_id, "resolved": {}, "schema_version": 4}
    resolved = doc.setdefault("resolved", {})
    previous_resolved = {
        path: dict(entry)
        for path, entry in resolved.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }

    changed_paths, _incoming_meta, persist_needed = _apply_incoming_observations(
        resolved,
        observations,
        provenance,
    )

    rr_updates: List[str] = []
    rr_updates, rr_persist = _apply_rr_notes_and_stats(
        user_id=user_id,
        resolved=resolved,
        updated_paths=changed_paths,
        previous_resolved=previous_resolved,
    )
    if rr_persist:
        persist_needed = True

    if persist_needed:
        doc["ts"] = _now()
        _write_json(paths["resolved"], doc)
        flat_rows = [{"path": k, **v} for k, v in sorted(resolved.items())]
        _write_json(paths["flat"], {"rows": flat_rows, "ts": _now()})

    if CORE_HOLISTIC_ON_INGEST:
        _, holistic_summary = _run_holistic_and_store(user_id)
    else:
        holistic_summary = _skip_holistic_summary()

    changed_unique = list(dict.fromkeys(changed_paths))

    return {
        "ok": True,
        "user_id": user_id,
        "imported": changed_unique,
        "count": len(changed_unique),
        "rr_curiosity_updated": rr_updates,
        "holistic": holistic_summary,
    }


@app.post("/coach/plan/{user_id}")
def coach_plan_upsert(user_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")

    plan = payload if isinstance(payload, dict) else {}
    paths = _user_paths(uid)
    plan["updated_ts"] = _now_iso()
    _write_json(paths["coach_plan"], plan)
    return {
        "ok": True,
        "user_id": uid,
        "path": paths["coach_plan"].as_posix(),
        "updated_ts": plan["updated_ts"],
    }


@app.get("/coach/plan/{user_id}")
def coach_plan_get(user_id: str) -> Dict[str, Any]:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")

    paths = _user_paths(uid)
    plan = _read_json(paths["coach_plan"])
    if not plan:
        return {}
    return plan


@app.post("/recompute/{user_id}")
def core_ai_recompute(user_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    cfg = _build_core_ai_config()
    if not core_llm_is_available(cfg):
        return {"ok": False, "reason": "core_ai_disabled", "holistic": _skip_holistic_summary()}

    paths = _user_paths(user_id)
    doc = _read_json(paths["resolved"]) or {"user_id": user_id, "resolved": {}, "schema_version": 4}
    resolved = doc.setdefault("resolved", {})
    if not resolved:
        summary = _run_holistic_and_store(user_id)[1] if CORE_HOLISTIC_ON_INGEST else _skip_holistic_summary()
        return {"ok": True, "user_id": user_id, "added_by_core_ai": [], "count": 0, "holistic": summary}

    previous_resolved = {
        path: dict(entry)
        for path, entry in resolved.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }

    body = payload or {}
    limit_paths = body.get("limit_paths")
    exclude_paths = body.get("exclude_paths")

    try:
        ai_added_meta = core_ai_expand(
            cfg,
            user_id=user_id,
            resolved=resolved,
            new_paths={},
            exclude_paths=exclude_paths,
            limit_paths=limit_paths,
        )
    except Exception as exc:
        print(f"[core-ai] recompute user={user_id} error={exc}")
        return {"ok": False, "reason": "core_ai_error", "holistic": _skip_holistic_summary()}

    ai_added: List[str] = []
    rr_updates: List[str] = []
    persist_needed = False
    if ai_added_meta:
        ai_default_prov = {"source": "core-ai"}
        for path, meta in ai_added_meta.items():
            entry = _entry_from_meta(meta, ai_default_prov)
            if resolved.get(path) == entry:
                continue
            resolved[path] = entry
            ai_added.append(path)
            persist_needed = True

        if ai_added:
            rr_updates, rr_persist = _apply_rr_notes_and_stats(
                user_id=user_id,
                resolved=resolved,
                updated_paths=ai_added,
                previous_resolved=previous_resolved,
            )

            if rr_persist:
                persist_needed = True

    if persist_needed or ai_added:
        doc["ts"] = _now()
        _write_json(paths["resolved"], doc)
        flat_rows = [{"path": k, **v} for k, v in sorted(resolved.items())]
        _write_json(paths["flat"], {"rows": flat_rows, "ts": _now()})
        if ai_added:
            ai_added = list(dict.fromkeys(ai_added))

    if CORE_HOLISTIC_ON_INGEST:
        _, holistic_summary = _run_holistic_and_store(user_id)
    else:
        holistic_summary = _skip_holistic_summary()

    return {
        "ok": True,
        "user_id": user_id,
        "added_by_core_ai": ai_added,
        "count": len(ai_added),
        "core_ai_model": cfg.model if cfg else None,
        "rr_curiosity_updated": rr_updates,
        "holistic": holistic_summary,
    }
