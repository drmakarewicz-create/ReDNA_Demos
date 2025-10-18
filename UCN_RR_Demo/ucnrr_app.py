# UCN_RR_Demo/ucnrr_app.py
# ReDNA UCN/RR Service — tolerant ingest that preserves provenance/ucn and
# remains compatible with existing Core expectations.

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import asyncio
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from datetime import datetime, timezone

from textwrap import shorten

import hashlib
import yaml
from fastapi import Body, FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ReDNACoreDemo.core.logutil import stack_log

DATA_DIR = Path(os.getenv("UCNRR_DATA_DIR", os.path.expanduser("~/Documents/ReDNA_Demos/UCN_RR_Demo/data")))
USERS_DIR = DATA_DIR / "users"
CORE_BASE = os.getenv("CORE_BASE", os.getenv("CORE_URL", "http://127.0.0.1:8015")).rstrip("/")
CORE_STORAGE_ROOT = Path(
    os.getenv("CORE_STORAGE_ROOT", "~/Documents/ReDNA_Demos/ReDNACoreDemo/data/storage")
).expanduser()

LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "").strip() or None
LLM_MODEL = (os.getenv("LLM_MODEL") or "").strip() or None
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "").strip() or None
LLM_API_KEY = (os.getenv("LLM_API_KEY") or "").strip() or None

USE_MIN_HEURISTICS = os.getenv("UCNRR_USE_MIN_HEURISTICS", "true").lower() in ("1", "true", "yes")
LOG_LLM = os.getenv("UCNRR_LOG_LLM", "false").lower() in ("1", "true", "yes")
LOG_SCORES = os.getenv("UCNRR_LOG_SCORES", "false").lower() in ("1", "true", "yes")

# Selftest cache configuration
SELFTEST_CACHE_SEC = int(os.getenv("UCNRR_SELFTEST_CACHE_SEC", "180"))  # 3 minutes
SELFTEST_BG_TIMEOUT_SEC = int(os.getenv("UCNRR_SELFTEST_BG_TIMEOUT_SEC", "4"))

FORWARD_LOG_PATH = DATA_DIR / "dev_logs" / "ucnrr_forward.log"

_TRACE_TRUE = {"1", "true", "yes", "on"}
ROUNDTRIP_TRACING_ENABLED = os.getenv("ROUNDTRIP_TRACING_ENABLED", "true").strip().lower() in _TRACE_TRUE
ROUNDTRIP_RETRY_LIMIT = int(float(os.getenv("ROUNDTRIP_RETRY_LIMIT", "3") or 3))
ROUNDTRIP_CIRCUIT_BREAK_MS = int(float(os.getenv("ROUNDTRIP_CIRCUIT_BREAK_MS", "120000") or 120000))

_REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = _REPO_ROOT / "data" / "dev_logs" / "trace_ucnrr.jsonl"
DNA_WEIGHTS_PATH = DATA_DIR / "config" / "dna_weights.yaml"
PROMPT_PATH = _REPO_ROOT / "prompts" / "ucn_rr_ai.md"

_circuit_state: Dict[str, Dict[str, float]] = {}
_dna_weights_cache: Optional[Dict[str, Any]] = None
_trait_registry_cache: Dict[str, Dict[str, Any]] = {}
_prompt_cache: Optional[Dict[str, str]] = None

app = FastAPI(title="ReDNA UCN/RR Demo", version="1.2.1")
UCNRR_VERSION = "dev"

_BACKGROUND_TASKS: "set[asyncio.Task[Any]]" = set()

# Selftest cache state
_last_selftest_ok_ts = 0.0
_last_selftest_ok_meta: Dict[str, Any] = {}
_selftest_lock = threading.Lock()

MORNING_PATTERNS = [
    r"\bmorning person\b",
    r"\bearly riser\b",
    r"\bup\s+(?:before|by)\s+sunrise\b",
]
EVENING_PATTERNS = [
    r"\bnight owl\b",
    r"\bstay up late\b",
    r"\bup\s+past\s+midnight\b",
]


def _detect_chronotype(text: str) -> bool:
    lowered = text.lower()
    for pattern in MORNING_PATTERNS + EVENING_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


def _maybe_inject_chronotype(user_text: str, rr_by_trait: Dict[str, float]) -> None:
    if "BehaviorDNA.Sleep.Chronotype" in rr_by_trait:
        return
    if _detect_chronotype(user_text):
        rr_by_trait["BehaviorDNA.Sleep.Chronotype"] = 830.0


def _launch_background(task: "asyncio.Task[Any]") -> None:
    _BACKGROUND_TASKS.add(task)

    def _cleanup(t: "asyncio.Task[Any]") -> None:
        _BACKGROUND_TASKS.discard(t)

    task.add_done_callback(_cleanup)


def _log_forward_event(entry: Dict[str, Any]) -> None:
    try:
        FORWARD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FORWARD_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _trace_append(record: Dict[str, Any]) -> None:
    if not ROUNDTRIP_TRACING_ENABLED:
        return
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _trace_event(trace_id: Optional[str], event: str, meta: Optional[Dict[str, Any]] = None) -> None:
    if not trace_id:
        return
    _trace_append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "event": event,
            "meta": meta or {},
        }
    )


def _trace_span(trace_id: Optional[str], span: str, phase: str, meta: Optional[Dict[str, Any]] = None) -> None:
    if not trace_id:
        return
    _trace_append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "span": span,
            "phase": phase,
            "meta": meta or {},
        }
    )


def _circuit_check(user_id: str) -> Dict[str, float]:
    entry = _circuit_state.get(user_id, {})
    now = time.time()
    opened_until = entry.get("opened_until", 0.0)
    if opened_until and opened_until > now:
        return {"open": True, "opened_until": opened_until}
    if opened_until and opened_until <= now:
        _circuit_state.pop(user_id, None)
    return {"open": False, "opened_until": 0.0}


def _circuit_reset(user_id: str) -> None:
    _circuit_state.pop(user_id, None)


def _load_prompt() -> Dict[str, str]:
    """
    Load UCNRR AI prompt from markdown file and compute SHA256 hash.

    Returns:
        Dict with keys: text, sha256, version, loaded_at
    """
    global _prompt_cache

    # Return cached if available
    if _prompt_cache is not None:
        return _prompt_cache

    try:
        if not PROMPT_PATH.exists():
            # Return placeholder if prompt file missing
            return {
                "text": "UCNRR AI prompt not loaded (file missing)",
                "sha256": "none",
                "version": "missing",
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "error": f"Prompt file not found at {PROMPT_PATH}"
            }

        # Read prompt file
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")

        # Compute SHA256
        prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

        # Extract version from markdown (look for **Version**: X.X)
        version_match = re.search(r'\*\*Version\*\*:\s*(\S+)', prompt_text)
        version = version_match.group(1) if version_match else "unknown"

        _prompt_cache = {
            "text": prompt_text,
            "sha256": prompt_sha,
            "version": version,
            "loaded_at": datetime.now(timezone.utc).isoformat()
        }

        return _prompt_cache

    except Exception as e:
        return {
            "text": f"Error loading prompt: {e}",
            "sha256": "error",
            "version": "error",
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


def _reload_prompt() -> Dict[str, str]:
    """Force reload of prompt cache."""
    global _prompt_cache
    _prompt_cache = None
    return _load_prompt()


def _circuit_record_failure(user_id: str) -> Dict[str, float]:
    now = time.time()
    entry = _circuit_state.setdefault(user_id, {"failures": 0, "fail_since": now, "opened_until": 0.0})
    fail_since = entry.get("fail_since", now)
    if now - fail_since > ROUNDTRIP_CIRCUIT_BREAK_MS / 1000.0:
        entry["failures"] = 0
        entry["fail_since"] = now
    entry["failures"] = entry.get("failures", 0) + 1
    entry["fail_since"] = entry.get("fail_since", now)
    threshold = max(1, ROUNDTRIP_RETRY_LIMIT)
    if entry["failures"] >= threshold:
        opened_until = now + ROUNDTRIP_CIRCUIT_BREAK_MS / 1000.0
        entry["opened_until"] = opened_until
        entry["failures"] = 0
        entry["fail_since"] = now
        return {"open": True, "opened_until": opened_until}
    return {"open": False, "opened_until": entry.get("opened_until", 0.0)}


# -----------------------------------------------------------------------------
# UCN estimation helpers
# -----------------------------------------------------------------------------

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# Trait ID canonicalization map (Phase 4.0a - align model outputs to golden IDs)
_CANON_MAP = {
    # Eye color variants
    "PaDNA.Color": "PaDNA.EyeDNA.IrisColor",
    "Eye.Color": "PaDNA.EyeDNA.IrisColor",
    "PaDNA.EyeColor": "PaDNA.EyeDNA.IrisColor",
    # Height variants
    "PaDNA.Height": "PaDNA.BodyDNA.Height",
    "PaDNA.Physical.Characteristic.Height": "PaDNA.BodyDNA.Height",
    "attributes.physical.height": "PaDNA.BodyDNA.Height",
    "height": "PaDNA.BodyDNA.Height",
    # Fitness/wellness → fitness level
    "PaDNA.PhysicalCondition": "BehaviorDNA.Fitness.Level",
    "PaDNA.HealthStatus": "BehaviorDNA.Fitness.Level",
    # Social style
    "Personality.Introversion": "BehaviorDNA.Social.Style",
    "Personality.Social_Preferences": "BehaviorDNA.Social.Style",
    # Exercise/activity
    "PaDNA.Activity": "BehaviorDNA.Exercise.Outdoor",
    "PaDNA.Human.Activity": "BehaviorDNA.Exercise.Outdoor",
    "PaDNA.Frequency": "BehaviorDNA.Exercise.Frequency",
    "PaDNA.Human.Frequency": "BehaviorDNA.Exercise.Frequency",
    # Age
    "Age.PaDNA.Age": "BasicDNA.Age",
    "age": "BasicDNA.Age",
    # Location
    "PaDNA.Location": "BasicDNA.Location.City",
    "PaDNA.City": "BasicDNA.Location.City",
    # Gender/sex
    "PaDNA.Gender": "BasicDNA.Gender",
    "PaDNA.Sex": "BasicDNA.Gender",
    # Hair color
    "PaDNA.PhysicalCharacteristics.HairColor": "PaDNA.HairDNA.Color.Natural",
    # Chronotype/personality
    "PaDNA.PersonalityType": "BehaviorDNA.Sleep.Chronotype",
    "PaDNA.TimePreference": "BehaviorDNA.Sleep.Chronotype",
    # Leisure/hobbies
    "PaDNA.Hobby": "BehaviorDNA.Leisure.Indoor",
    "PaDNA.ActivityType": "BehaviorDNA.Leisure.Indoor",
    # Caffeine/health
    "PaDNA.Human.DrinkCoffee": "BehaviorDNA.Health.CaffeineIntake",
    "PaDNA.Human.DailyCaffeineIntake": "BehaviorDNA.Health.CaffeineIntake",
    "PaDNA.Human.TimeOfConsumption": "BehaviorDNA.Routine.Morning",
    # Learning
    "PaDNA.Learning_Style": "BehaviorDNA.Learning.Style",
    # Communication
    "PaDNA.Communication.ResponseTime": "BehaviorDNA.Communication.ResponseStyle",
    # Work schedule
    "PaDNA.StartOfWork": "BehaviorDNA.Schedule.WorkHours",
    "PaDNA.FinishOfWork": "BehaviorDNA.Schedule.WorkHours",
    # Organization
    "PaDNA.DayOfWeek": "BehaviorDNA.Organization.Level",
    # Occupation/relationship
    "PaDNA.Occupation": "BasicDNA.Occupation",
    "PaDNA.RelationshipStatus": "BasicDNA.RelationshipStatus",
    "relationship.status": "BasicDNA.RelationshipStatus",
}

_CANON_MAP.update({
    "sleep.chronotype": "BehaviorDNA.Sleep.Chronotype",
    "diet.preference": "BehaviorDNA.Health.Diet",
    "work.location": "BehaviorDNA.Work.Location",
    "social.group_size": "PreferenceDNA.Social.GroupSize",
    "exercise.type": "BehaviorDNA.Exercise.Type",
})


def _canon_trait_id(tid: str) -> str:
    """
    Canonicalize trait_id to match golden dataset conventions.

    Phase 4.0a: Apply runtime normalization to align UCNRR outputs with Core/golden IDs.
    This reduces test harness aliasing burden and improves recall.

    Steps:
    1. Check explicit aliases first
    2. Apply heuristic normalization (add *DNA suffix if missing)
    3. Check aliases again on normalized form
    """
    if not tid:
        return ""
    tid = tid.strip()

    # Check explicit aliases first
    if tid in _CANON_MAP:
        return _CANON_MAP[tid]

    # Apply heuristic: add *DNA after first PaDNA segment if missing
    # E.g., "PaDNA.Eye.IrisColor" -> "PaDNA.EyeDNA.IrisColor"
    normalized = re.sub(r"^PaDNA\.([A-Z][a-z]+)\.(.+)$", r"PaDNA.\1DNA.\2", tid)

    # Check aliases again on normalized form
    return _CANON_MAP.get(normalized, normalized)


def _load_dna_weights() -> Dict[str, Any]:
    """Load DNA weights from YAML configuration file."""
    global _dna_weights_cache
    if _dna_weights_cache is not None:
        return _dna_weights_cache

    try:
        if DNA_WEIGHTS_PATH.exists():
            with DNA_WEIGHTS_PATH.open("r", encoding="utf-8") as f:
                _dna_weights_cache = yaml.safe_load(f) or {}
        else:
            _dna_weights_cache = {"fallback": 0.75}
    except Exception:
        _dna_weights_cache = {"fallback": 0.75}

    return _dna_weights_cache


def _get_dna_weight(trait_path: str) -> float:
    """
    Get DNA weight for a trait path (e.g., PaDNA.EyeDNA.IrisColor).
    Returns 0.75 as fallback if not found.
    """
    weights = _load_dna_weights()
    parts = trait_path.split(".")

    # Try exact path match
    current = weights
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            break

    if isinstance(current, (int, float)):
        return float(current)

    # Try category default
    if len(parts) >= 2:
        category = parts[0]
        subcategory = parts[1]
        if category in weights:
            cat_data = weights[category]
            if isinstance(cat_data, dict):
                if subcategory in cat_data:
                    subcat_data = cat_data[subcategory]
                    if isinstance(subcat_data, dict) and "default" in subcat_data:
                        return float(subcat_data["default"])
                    elif isinstance(subcat_data, (int, float)):
                        return float(subcat_data)
                if "default" in cat_data:
                    return float(cat_data["default"])

    # Fallback
    return float(weights.get("fallback", 0.75))


def _get_trait_importance(trait_path: str) -> float:
    """
    Get trait importance from registry (0..1).
    For now, return default based on category; full registry integration would enhance this.
    """
    if "PaDNA" in trait_path:
        return 0.85
    elif "PsyDNA" in trait_path:
        return 0.90
    elif "SocialDNA" in trait_path:
        return 0.80
    return 0.75


def _calculate_recency_boost(days_since_last_update: float) -> float:
    """
    Calculate recency boost factor.
    Formula: 1.0 + min(log(1 + days_since_last_update) / 5, 0.35)
    """
    if days_since_last_update < 0:
        days_since_last_update = 0
    boost = 1.0 + min(math.log(1 + days_since_last_update) / 5.0, 0.35)
    return boost


def _calculate_tolerance_factor(user_tolerance: float) -> float:
    """
    Calculate tolerance factor.
    Formula: clamp(1.0 - (user_tolerance - 0.5) * 0.4, 0.7, 1.2)
    """
    factor = 1.0 - (user_tolerance - 0.5) * 0.4
    return _clamp(factor, 0.7, 1.2)


def _calculate_curiosity(
    rr: float,
    trait_path: str,
    *,
    days_since_update: float = 0.0,
    user_tolerance: float = 0.5,
) -> float:
    """
    Calculate curiosity score using full formula:
    curiosity = ((1000 - rr) / 1000) * dna_weight * trait_importance * recency_boost * tolerance_factor

    Args:
        rr: Reliability/Readiness score (0-1000)
        trait_path: Full trait path (e.g., PaDNA.EyeDNA.IrisColor)
        days_since_update: Days since last update for recency boost
        user_tolerance: User tolerance level (0-1), default 0.5

    Returns:
        Curiosity score (0-1)
    """
    # Base curiosity from RR
    base_curiosity = (1000.0 - rr) / 1000.0

    # Get factors
    dna_weight = _get_dna_weight(trait_path)
    trait_importance = _get_trait_importance(trait_path)
    recency_boost = _calculate_recency_boost(days_since_update)
    tolerance_factor = _calculate_tolerance_factor(user_tolerance)

    # Calculate final curiosity
    curiosity = base_curiosity * dna_weight * trait_importance * recency_boost * tolerance_factor

    # Clamp to 0-1
    return _clamp(curiosity, 0.0, 1.0)


def estimate_ucn_for_trait(
    path: str,
    source_kind: str,
    *,
    llm_conf: Optional[float] = None,
    heuristic_strength: str = "medium",
) -> float:
    """Return a 0–1000 UCN score for the supplied trait."""

    source_kind = (source_kind or "unknown").lower()
    trait_lower = (path or "").lower()

    if source_kind == "explicit":
        base = 940.0
        if "padna." in trait_lower:
            base = 965.0
        elif "psyDNA" in trait_lower.lower():
            base = 930.0
        return _clamp(base, 1.0, 999.999)

    if source_kind == "llm":
        if llm_conf is None:
            llm_conf = 0.75
        llm_conf = _clamp(llm_conf, 0.0, 1.0)
        base = 500.0 + 400.0 * llm_conf
        if "padna." in trait_lower:
            base += 30.0
        return _clamp(base, 1.0, 999.999)

    if source_kind == "heuristic":
        strength_map = {
            "low": 320.0,
            "medium": 520.0,
            "high": 720.0,
        }
        base = strength_map.get((heuristic_strength or "medium").lower(), 520.0)
        if "padna." in trait_lower:
            base += 40.0
        return _clamp(base, 1.0, 999.999)

    # Fallback for unknown source kinds
    return 400.0


def _build_trait_notes(
    path: str,
    value: Any,
    source_kind: str,
    *,
    raw_line: Optional[str] = None,
    user_text: Optional[str] = None,
    heuristic_hint: Optional[str] = None,
) -> Dict[str, Any]:
    summary_map = {
        "explicit": "Parsed canonical line supplied by user.",
        "llm": "LLM inference from free text.",
        "heuristic": "Applied heuristic inference from user text.",
    }

    instructions_map = {
        "explicit": ["Confirm the detail remains accurate in follow-up conversation."],
        "llm": ["Validate this trait by asking the user directly for confirmation."],
        "heuristic": ["Ask the user to clarify this trait to replace heuristic inference."],
    }

    data_gaps_map = {
        "explicit": ["Capture supporting evidence (photo or document) to reach maximum confidence."],
        "llm": ["Need explicit confirmation to raise confidence above 900."],
        "heuristic": ["Obtain explicit statement or photo to replace heuristic inference."],
    }

    source_key = (source_kind or "unknown").lower()
    evidence: List[str] = []
    if raw_line:
        evidence.append(f"Canonical line: {raw_line.strip()}")
    if user_text and source_key == "llm":
        snippet = shorten(user_text.strip(), width=140, placeholder="…") if user_text else ""
        if snippet:
            evidence.append(f"Free text snippet: {snippet}")
    if heuristic_hint:
        evidence.append(heuristic_hint)
    if not evidence:
        evidence = ["Derived from user input."]

    return {
        "summary": summary_map.get(source_key, "Derived trait inference."),
        "evidence": evidence,
        "coach_instructions": instructions_map.get(source_key, ["Confirm this trait with the user."]),
        "data_gaps": data_gaps_map.get(source_key, ["Need additional evidence to raise confidence."]),
    }

class IngestText(BaseModel):
    user_id: str
    text: Optional[str] = ""
    lines: Optional[List[str]] = None
    provenance: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _ensure_user_dirs(user_id: str) -> Dict[str, Path]:
    root = USERS_DIR / user_id
    inbox = root / "inbox"
    root.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    snap = root / "rr_snapshot.json"
    if not snap.exists():
        snap.write_text(json.dumps({"ts": _now_ts(), "resolved": {}, "observations": {}}, indent=2))
    return {"root": root, "inbox": inbox, "snapshot": snap}


def _read_json(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _append_inbox_event(user_id: str, text: str, provenance: Dict[str, Any]) -> None:
    paths = _ensure_user_dirs(user_id)
    payload = {"ts": _now_ts(), "text": text}
    if provenance:
        payload["provenance"] = provenance
    fp = paths["inbox"] / f"{int(time.time())}_text.json"
    _write_json(fp, payload)


def llm_is_available() -> bool:
    return all((LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL))


def _parse_canonical(
    lines: List[str],
    source_kind: str = "explicit",
    *,
    user_text: Optional[str] = None,
    heuristic_hint: Optional[str] = None,
    llm_conf: Optional[float] = None,
    heuristic_strength: str = "medium",
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for raw in lines:
        if not raw:
            continue
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_.]*)\s*=\s*(.+?)\s*$", raw)
        if not m:
            continue
        key, value_raw = m.group(1), m.group(2)
        value: Any = value_raw
        if value_raw.lower() in ("true", "false"):
            value = value_raw.lower() == "true"
        else:
            try:
                value = int(value_raw)
            except ValueError:
                try:
                    value = float(value_raw)
                except ValueError:
                    value = value_raw

        ucn = estimate_ucn_for_trait(
            key,
            source_kind,
            llm_conf=llm_conf,
            heuristic_strength=heuristic_strength,
        )
        notes = _build_trait_notes(
            key,
            value,
            source_kind,
            raw_line=raw,
            user_text=user_text,
            heuristic_hint=heuristic_hint,
        )
        reason = source_kind if source_kind else "explicit"
        out[key] = {
            "resolved_value": value,
            "ucn": ucn,
            "reasons": [reason],
            "notes": notes,
        }
        if LOG_SCORES:
            print(f"ucnrr: trait={key} source={source_kind} ucn={ucn:.1f}")
    return out


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _min_heuristics(text: str) -> Dict[str, Dict[str, Any]]:
    low = (text or "").lower()
    out: Dict[str, Dict[str, Any]] = {}
    if "blue" in low and ("eye" in low or "eyes" in low):
        out.update(
            _parse_canonical(
                ["PaDNA.EyeDNA.IrisColor=Blue"],
                source_kind="heuristic",
                heuristic_hint="Keyword match: blue + eye",
                heuristic_strength="high",
            )
        )
    if "red" in low and "hair" in low:
        out.update(
            _parse_canonical(
                ["PaDNA.HairDNA.Color=Red"],
                source_kind="heuristic",
                heuristic_hint="Keyword match: red + hair",
                heuristic_strength="medium",
            )
        )
    return out


def _merge_normalize(source: Dict[str, Any], provenance: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    default_prov = {"source": "ucnrr", "from": provenance.get("source", "explorer"), "ts": now_iso}
    merged: Dict[str, Dict[str, Any]] = {}
    for path, meta in (source or {}).items():
        if isinstance(meta, dict):
            value = meta.get("resolved_value", meta.get("value"))
            ucn = meta.get("ucn", meta.get("confidence", 0) * 100 if isinstance(meta.get("confidence"), (int, float)) else 80)
            reasons = list(meta.get("reasons", [])) if meta.get("reasons") else []
            flags = list(meta.get("flags", [])) if meta.get("flags") else []
            status = meta.get("status")
            prov = dict(meta.get("provenance", {})) or dict(default_prov)
            notes = meta.get("notes") if isinstance(meta.get("notes"), dict) else None
        else:
            value = meta
            ucn = 80
            reasons = []
            flags = []
            status = None
            prov = dict(default_prov)
            notes = None
        if "source" not in prov:
            prov.setdefault("source", default_prov["source"])
        merged[path] = {
            "resolved_value": value,
            "ucn": ucn,
            "reasons": reasons,
            "flags": flags or None,
            "status": status,
            "provenance": prov,
        }
        if notes:
            merged[path]["notes"] = notes
    return merged


def _post_core_ingest(
    user_id: str,
    observations: Dict[str, Dict[str, Any]],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    import requests

    try:
        headers = {"X-Trace-Id": trace_id} if trace_id else None
        resp = requests.post(
            f"{CORE_BASE}/ingest_from_ucnrr",
            json={"user_id": user_id, "observations": observations},
            timeout=30,
            headers=headers,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if resp.headers.get("content-type", "").startswith("application/json"):
        body: Any = resp.json()
    else:
        body = resp.text
    return {"ok": resp.ok, "status_code": resp.status_code, "body": body}


def _llm_extract(text: str) -> Dict[str, Any]:
    if not llm_is_available():
        return {}
    try:
        import requests
    except ImportError:
        return {}

    # Phase 4.0a Batch 2: Canonical schema + few-shot examples for improved recall
    system_prompt = (
        "You are an information extraction assistant for the ReDNA trait system.\n"
        "Extract traits from user text using ONLY these canonical trait IDs:\n\n"
        "**Physiological:**\n"
        "- PaDNA.EyeDNA.IrisColor, PaDNA.HairDNA.Color.Natural, PaDNA.BodyDNA.Height\n\n"
        "**Demographics:**\n"
        "- BasicDNA.Age, BasicDNA.Gender, BasicDNA.RelationshipStatus, BasicDNA.Occupation\n\n"
        "**Behavior:**\n"
        "- BehaviorDNA.Sleep.Chronotype, BehaviorDNA.Schedule.WorkHours\n"
        "- BehaviorDNA.Exercise.Outdoor, BehaviorDNA.Exercise.Frequency, BehaviorDNA.Exercise.Type\n"
        "- BehaviorDNA.Leisure.Indoor, BehaviorDNA.Routine.Morning\n"
        "- BehaviorDNA.Wellness.ColdTherapy, BehaviorDNA.Work.Location\n"
        "- BehaviorDNA.Health.Diet, BehaviorDNA.Health.CaffeineIntake\n"
        "- BehaviorDNA.Social.Style, BehaviorDNA.Organization.Level\n\n"
        "**Preferences:**\n"
        "- PreferenceDNA.Social.GroupSize, PreferenceDNA.Food.Pizza, PreferenceDNA.Work.Environment\n\n"
        "**Rules:**\n"
        "- Emit ONLY trait_ids from the schema above\n"
        "- If uncertain, omit rather than speculate\n"
        "- Prefer concise extractions (1-3 items)\n"
        "- When choosing a trait_id, pick the nearest canonical ID from schema (do not invent)\n"
        "- For frequency, prefer: 'weekly', 'daily', '2_per_week'\n"
        "- Output format: Trait.Path=Value (one per line)"
    )

    user_prompt = (
        "Extract traits from this text using canonical IDs from the schema.\n\n"
        "**Few-shot examples:**\n"
        "1. 'I'm a morning person.' → BehaviorDNA.Sleep.Chronotype=morning\n"
        "2. 'I start work at 6 AM and finish by 2 PM.' → BehaviorDNA.Schedule.WorkHours=early BehaviorDNA.Sleep.Chronotype=morning\n"
        "3. 'I usually stay in and read on weekends.' → BehaviorDNA.Leisure.Indoor=true PreferenceDNA.Social.GroupSize=small\n"
        "4. 'I don't eat meat.' → BehaviorDNA.Health.Diet=vegetarian\n"
        "5. 'I take cold showers every morning.' → BehaviorDNA.Wellness.ColdTherapy=true\n"
        "6. 'I work from home most days.' → BehaviorDNA.Work.Location=remote\n"
        "7. 'My hair is brown.' → PaDNA.HairDNA.Color.Natural=brown\n"
        "8. 'I'm in my early 30s.' → BasicDNA.Age=30s\n"
        "9. 'I'm married.' → BasicDNA.RelationshipStatus=married\n"
        "10. 'I go hiking every weekend.' → BehaviorDNA.Exercise.Outdoor=true BehaviorDNA.Exercise.Frequency=weekly\n\n"
        "TEXT:\n" + text + "\n\n"
        "Output (one trait per line, canonical IDs only):"
    )

    headers = {}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "top_p": 0.9,
                "stream": False,
            },
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception:
        return {}

    lines = _split_lines(content)
    return _parse_canonical(lines, source_kind="llm", user_text=text)


def _is_llm_configured() -> bool:
    """Check if LLM is properly configured based on provider."""
    if not LLM_PROVIDER:
        return False

    # Ollama doesn't need API key, just needs provider + base URL
    if LLM_PROVIDER.lower() == "ollama":
        return bool(LLM_BASE_URL or os.getenv("OLLAMA_BASE_URL"))

    # OpenAI, Anthropic, etc. need API key
    return bool(LLM_API_KEY)


def _bg_refresh_selftest() -> None:
    """Trigger background selftest refresh (non-blocking)."""
    def _run():
        try:
            # Run selftest with timeout budget
            ucnrr_selftest()
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True)
    t.start()


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    global _last_selftest_ok_ts, _last_selftest_ok_meta

    prompt_info = _load_prompt()
    now = time.time()

    # Check if selftest cache is fresh
    with _selftest_lock:
        age = now - _last_selftest_ok_ts
        cache_fresh = age <= SELFTEST_CACHE_SEC

    base_response = {
        "status": "healthy",
        "service": "ucnrr",
        "version": UCNRR_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_sha256": prompt_info.get("sha256", "none"),
        "prompt_version": prompt_info.get("version", "unknown"),
        "prompt_loaded_at": prompt_info.get("loaded_at", "never"),
        "llm_provider": LLM_PROVIDER or "none",
        "llm_model": LLM_MODEL or "none",
        "llm_configured": _is_llm_configured(),
        "llm_base_url": LLM_BASE_URL or os.getenv("OLLAMA_BASE_URL") or "none",
    }

    if cache_fresh:
        # Return cached selftest result
        base_response["selftest_cached"] = True
        base_response["selftest_cache_age_sec"] = int(age)
        base_response.update(_last_selftest_ok_meta)

        # Trigger background refresh if cache is near expiry
        if age > SELFTEST_CACHE_SEC * 0.6:
            _bg_refresh_selftest()

        return base_response
    else:
        # Cache stale or not set; indicate slow model if needed
        base_response["selftest_cached"] = False
        base_response["selftest_cache_age_sec"] = int(age) if _last_selftest_ok_ts > 0 else None

        # Trigger background refresh
        _bg_refresh_selftest()

        return base_response


@app.get("/health")
def health() -> Dict[str, Any]:
    return api_health()


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """
    Get UCNRR service metrics.

    Returns counters, latency percentiles, and selftest status.
    """
    from .metrics import METRICS
    return METRICS.get_snapshot()


class RescoreRequest(BaseModel):
    user_id: str
    traits: Optional[List[Dict[str, Any]]] = None
    text: Optional[str] = None


class UCNScoreRequest(BaseModel):
    user_id: str
    items: List[Dict[str, Any]]


@app.post("/ucn/score")
def ucn_score(body: UCNScoreRequest) -> List[Dict[str, Any]]:
    """
    Score UCN for a batch of trait evidence (Core RR client endpoint).

    Input:
        {
            "user_id": "TEST",
            "items": [
                {
                    "trait_id": "PaDNA.EyeDNA.IrisColor",
                    "value": {"enum": "blue"},
                    "ucn_prior": 0.8,
                    "source": "photo_analysis"
                }
            ]
        }

    Output:
        [
            {
                "trait_id": "PaDNA.EyeDNA.IrisColor",
                "ucn": 0.85
            }
        ]
    """
    from .metrics import METRICS

    start_time = time.time()

    try:
        user_id = body.user_id.strip()
        if not user_id:
            METRICS.increment("rr_requests_4xx")
            raise HTTPException(status_code=400, detail="user_id required")

        if not body.items:
            METRICS.increment("rr_requests_4xx")
            raise HTTPException(status_code=400, detail="items list required")

        results = []
        for item in body.items:
            trait_id = item.get("trait_id")
            if not trait_id:
                continue

            # Get ucn_prior (0..1 scale)
            ucn_prior = float(item.get("ucn_prior", 0.5))

            # Get source for reliability adjustment
            source = item.get("source", "unknown")

            # Apply source reliability multiplier
            if source in ["photo_analysis", "document_verified"]:
                ucn_multiplier = 1.1  # +10% boost for high-reliability sources
            elif source in ["inference", "third_party"]:
                ucn_multiplier = 0.7  # -30% for low-reliability sources
            else:
                ucn_multiplier = 1.0  # Neutral for user statements, chat

            # Compute final UCN (scale to 0-1)
            ucn_final = min(1.0, ucn_prior * ucn_multiplier)

            results.append({
                "trait_id": trait_id,
                "ucn": round(ucn_final, 4)
            })

        # Track metrics
        elapsed_ms = (time.time() - start_time) * 1000
        METRICS.increment("rr_requests_total")
        METRICS.increment("rr_requests_2xx")
        METRICS.observe_latency("rr_score", elapsed_ms)

        return results
    except HTTPException:
        raise
    except Exception as e:
        METRICS.increment("rr_requests_5xx")
        stack_log(
            "ucnrr",
            "ERROR",
            "ucn_score_fail",
            "ucn_score encountered an unexpected error",
            {"user_id": body.user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ucnrr/selftest")
def ucnrr_selftest() -> Dict[str, Any]:
    """
    Self-test endpoint that scores a canonical test case: "I have blue eyes".

    Expected: UCN in range [0.80-0.90], indicating high confidence for direct observation.
    """
    from .metrics import METRICS

    test_start = time.time()
    stack_log("ucnrr", "INFO", "selftest_start", "UCNRR self-test started", {})

    # Canonical test case
    test_input = {
        "user_id": "SELFTEST",
        "items": [
            {
                "trait_id": "PaDNA.EyeDNA.IrisColor",
                "value": {"enum": "blue"},
                "ucn_prior": 0.8,
                "source": "selftest"
            }
        ]
    }

    try:
        # Call scoring endpoint
        result = ucn_score(UCNScoreRequest(**test_input))

        if not result or len(result) == 0:
            METRICS.increment("rr_selftest_fail")
            result_data = {
                "ok": False,
                "error": "No results returned from ucn_score",
                "test_case": "blue_eyes"
            }
            METRICS.update_selftest(result_data)
            stack_log(
                "ucnrr",
                "WARN",
                "selftest_fail",
                "UCNRR self-test returned no results",
                result_data,
            )
            return result_data

        scored = result[0]
        ucn = scored.get("ucn", 0)

        # Validate UCN in expected range
        ucn_ok = 0.75 <= ucn <= 0.95

        elapsed_ms = int((time.time() - test_start) * 1000)

        result_data = {
            "ok": ucn_ok,
            "test_case": "blue_eyes",
            "trait_id": scored.get("trait_id"),
            "ucn": ucn,
            "ucn_expected_range": [0.75, 0.95],
            "ucn_in_range": ucn_ok,
            "elapsed_ms": elapsed_ms,
            "prompt_sha256": _load_prompt().get("sha256", "none"),
            "llm_configured": bool(LLM_PROVIDER and LLM_API_KEY)
        }

        # Track metrics
        if ucn_ok:
            METRICS.increment("rr_selftest_ok")

            # Update selftest cache on success
            global _last_selftest_ok_ts, _last_selftest_ok_meta
            with _selftest_lock:
                _last_selftest_ok_ts = time.time()
                _last_selftest_ok_meta = {
                    "model": LLM_MODEL or "none",
                    "provider": LLM_PROVIDER or "none",
                    "ucn": ucn,
                    "elapsed_ms": elapsed_ms,
                }

            stack_log(
                "ucnrr",
                "INFO",
                "selftest_ok",
                "UCNRR self-test passed",
                result_data,
            )
        else:
            METRICS.increment("rr_selftest_fail")
            stack_log(
                "ucnrr",
                "WARN",
                "selftest_fail",
                "UCNRR self-test out of expected range",
                result_data,
            )

        METRICS.observe_latency("rr_selftest", elapsed_ms)
        METRICS.update_selftest(result_data)

        return result_data

    except Exception as e:
        METRICS.increment("rr_selftest_fail")
        result_data = {
            "ok": False,
            "error": str(e),
            "test_case": "blue_eyes",
            "elapsed_ms": int((time.time() - test_start) * 1000)
        }
        METRICS.update_selftest(result_data)
        stack_log(
            "ucnrr",
            "ERROR",
            "selftest_fail",
            "UCNRR self-test raised exception",
            result_data,
        )
        return result_data


@app.post("/api/rescore")
def api_rescore(body: RescoreRequest) -> Dict[str, Any]:
    """
    Calculate RR and Curiosity for traits using full curiosity formula:
    curiosity = ((1000 - rr)/1000) * dna_weight * trait_importance * recency_boost * tolerance_factor

    Accepts:
    - user_id (required)
    - traits: list of {id, value, rr?, days_since_update?, tolerance?}
    - text: freeform text to extract traits from (if traits not provided)

    Returns:
    - rr_by_trait: RR scores per trait
    - curiosity_by_trait: Curiosity scores per trait
    - global_curiosity: Average curiosity across all traits
    """
    user_id = body.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    traits = body.traits or []
    text = body.text or ""

    # If traits are empty but text provided, try to extract
    if not traits and text:
        explicit = _parse_canonical(_split_lines(text))
        if not explicit and llm_is_available():
            explicit = _llm_extract(text)
        if not explicit and USE_MIN_HEURISTICS:
            explicit = _min_heuristics(text)
        traits = [{"id": k, "value": v.get("resolved_value"), "rr": v.get("ucn", 500.0)}
                  for k, v in explicit.items()]

    if not traits:
        raise HTTPException(status_code=400, detail="No traits provided or extracted from text")

    rr_by_trait: Dict[str, float] = {}
    curiosity_by_trait: Dict[str, float] = {}
    global_curiosity = 0.0

    for trait in traits:
        if not isinstance(trait, dict):
            continue
        trait_id = str(trait.get("id") or "").strip()
        if not trait_id:
            continue

        # Phase 4.0a: Canonicalize trait ID to match golden dataset conventions
        trait_id = _canon_trait_id(trait_id)
        if not trait_id:  # Skip if canonicalization returns empty
            continue

        # RR can be provided or we estimate from UCN
        rr_raw = trait.get("rr")
        if rr_raw is None:
            rr_raw = trait.get("ucn", 500.0)
        try:
            rr = float(rr_raw)
        except (TypeError, ValueError):
            rr = 500.0

        # Clamp RR to 0-1000
        rr = max(0.0, min(1000.0, rr))
        rr_by_trait[trait_id] = rr

        # Get optional parameters from trait dict
        days_since_update = float(trait.get("days_since_update", 0.0))
        user_tolerance = float(trait.get("tolerance", 0.5))

        # Calculate curiosity using full formula
        curiosity = _calculate_curiosity(
            rr,
            trait_id,
            days_since_update=days_since_update,
            user_tolerance=user_tolerance,
        )
        curiosity_by_trait[trait_id] = round(curiosity, 4)
        global_curiosity += curiosity

    if curiosity_by_trait:
        global_curiosity = global_curiosity / len(curiosity_by_trait)

    if text:
        _maybe_inject_chronotype(text, rr_by_trait)

    return {
        "ok": True,
        "user_id": user_id,
        "rr_by_trait": rr_by_trait,
        "curiosity_by_trait": curiosity_by_trait,
        "global_curiosity": round(global_curiosity, 4),
    }


@app.get("/users/list")
def users_list(limit: int = 500) -> Dict[str, Any]:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    users = sorted(p.name for p in USERS_DIR.iterdir() if p.is_dir() and p.name not in (".", "llm_debug"))
    return {"users": users[:limit]}


@app.post("/users/init")
def users_init(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    uid = (payload.get("username") or payload.get("user_id") or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="username (or user_id) required")
    paths = _ensure_user_dirs(uid)
    (paths["root"] / "_init.txt").write_text(_now_ts() + " init\n")

    # Nudge Core to ensure matching storage (best-effort; do not fail user creation)
    core_created = False
    try:
        import requests

        core_base = os.getenv("CORE_BASE", os.getenv("CORE_URL", "http://127.0.0.1:8015")).rstrip("/")
        resp = requests.post(f"{core_base}/user/{uid}/ensure", timeout=5)
        if resp.status_code >= 400:
            # Fall back to legacy ingest (pull) if explicit ensure is unavailable
            requests.post(
                f"{core_base}/ingest_from_ucnrr",
                json={"user_id": uid},
                timeout=5,
            )
        core_created = True
    except Exception:
        core_created = False

    if not core_created:
        try:
            CORE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
            user_root = CORE_STORAGE_ROOT / uid
            user_root.mkdir(parents=True, exist_ok=True)
            resolved = user_root / "resolved.json"
            if not resolved.exists():
                resolved.write_text(
                    json.dumps({"user_id": uid, "resolved": {}, "schema_version": 4}, indent=2)
                )
            flat = user_root / "resolved_flat.json"
            if not flat.exists():
                flat.write_text(json.dumps({"rows": [], "ts": _now_ts()}, indent=2))
        except Exception:
            pass

    return {"ok": True, "user_id": uid, "path": paths["root"].as_posix()}


async def _forward_to_core_async(
    *,
    user_id: str,
    normalized: Dict[str, Dict[str, Any]],
    snapshot_ts: Optional[str],
    provenance: Dict[str, Any],
    trace_id: Optional[str],
) -> None:
    loop = asyncio.get_running_loop()
    started = time.time()
    recompute_status: Optional[int] = None
    recompute_error: Optional[str] = None
    entry: Dict[str, Any]
    circuit_snapshot: Dict[str, float] = {}
    _trace_span(trace_id, "ucnrr_forward", "start", {"user_id": user_id, "count": len(normalized)})
    try:
        core_result = await loop.run_in_executor(None, _post_core_ingest, user_id, normalized, trace_id)
        _trace_span(
            trace_id,
            "ucnrr_forward",
            "end",
            {"status": core_result.get("status_code"), "ok": core_result.get("ok")},
        )
        if core_result.get("ok"):
            _circuit_reset(user_id)
            try:
                import requests

                recompute_resp = requests.post(
                    f"{CORE_BASE}/recompute/{user_id}",
                    json={},
                    timeout=15,
                    headers={"X-Trace-Id": trace_id} if trace_id else None,
                )
                recompute_status = recompute_resp.status_code
            except Exception as exc:  # pragma: no cover - defensive
                recompute_error = str(exc)
        else:
            circuit_snapshot = _circuit_record_failure(user_id)
            if circuit_snapshot.get("open"):
                reset_ts = datetime.fromtimestamp(circuit_snapshot["opened_until"], timezone.utc).isoformat()
                _trace_event(
                    trace_id,
                    "circuit_opened",
                    {"user_id": user_id, "reset_at": reset_ts},
                )
    except Exception as exc:  # pragma: no cover - defensive guard
        core_result = {"ok": False, "error": str(exc)}
        circuit_snapshot = _circuit_record_failure(user_id)
        if circuit_snapshot.get("open"):
            reset_ts = datetime.fromtimestamp(circuit_snapshot["opened_until"], timezone.utc).isoformat()
            _trace_event(
                trace_id,
                "circuit_opened",
                {"user_id": user_id, "reset_at": reset_ts},
            )
        _trace_span(
            trace_id,
            "ucnrr_forward",
            "end",
            {"error": str(exc)},
        )

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "snapshot_ts": snapshot_ts,
        "elapsed_ms": int((time.time() - started) * 1000),
        "changed_keys": sorted(normalized.keys()),
        "core": {
            "ok": bool(core_result.get("ok")),
            "status": core_result.get("status_code"),
            "error": core_result.get("error"),
        },
        "recompute": {
            "status": recompute_status,
            "error": recompute_error,
        },
        "provenance": {
            "source": provenance.get("source"),
            "actor": provenance.get("actor"),
        },
        "trace_id": trace_id,
        "circuit": circuit_snapshot,
    }
    _log_forward_event(entry)


@app.post("/ingest_text")
async def ingest_text(body: IngestText):
    user_id = body.user_id.strip()
    if not user_id:
        return {"ok": False, "reason": "empty user_id"}

    text = (body.text or "").strip()
    provenance = body.provenance or {}
    lines_payload = body.lines or []
    trace_id = body.trace_id or provenance.get("trace_id") if isinstance(provenance, dict) else None

    circuit_state = _circuit_check(user_id)
    if circuit_state.get("open"):
        opened_until = circuit_state.get("opened_until", 0.0)
        retry_after_ms = max(0, int((opened_until - time.time()) * 1000))
        reset_ts = datetime.fromtimestamp(opened_until, timezone.utc).isoformat()
        _trace_event(trace_id, "circuit_short_circuit", {"user_id": user_id, "reset_at": reset_ts})
        return {
            "ok": True,
            "forwarded": False,
            "circuit_open": True,
            "circuit_reset_ts": reset_ts,
            "retry_after_ms": retry_after_ms,
            "trace_id": trace_id,
        }

    _trace_event(
        trace_id,
        "ucnrr_ingest_received",
        {
            "user_id": user_id,
            "lines": len(lines_payload or []),
            "has_text": bool(text),
        },
    )

    _append_inbox_event(user_id, text, provenance)
    paths = _ensure_user_dirs(user_id)

    explicit = _parse_canonical([ln.strip() for ln in lines_payload if ln and ln.strip()])
    if not explicit and text:
        explicit = _parse_canonical(_split_lines(text))

    llm_map: Dict[str, Any] = {}
    if text and not explicit and llm_is_available():
        llm_map = _llm_extract(text)
        if LOG_LLM:
            debug_dir = USERS_DIR / "llm_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{int(time.time())}_llm.json").write_text(json.dumps({"text": text, "llm_map": llm_map}, indent=2))

    merged = {**llm_map, **explicit}

    if not merged and USE_MIN_HEURISTICS:
        merged = _min_heuristics(text)

    snap = _read_json(paths["snapshot"]) or {"ts": _now_ts(), "resolved": {}, "observations": {}}
    snap_resolved = snap.setdefault("resolved", {})
    for path, meta in merged.items():
        snap_resolved[path] = meta
    snap["ts"] = _now_ts()
    _write_json(paths["snapshot"], snap)

    if not merged:
        _trace_event(trace_id, "ucnrr_no_traits", {"user_id": user_id})
        return {"ok": False, "message": "no_actionable_traits", "core_response": None}

    normalized = _merge_normalize(merged, provenance)
    snapshot_ts = snap.get("ts")

    task = asyncio.create_task(
        _forward_to_core_async(
            user_id=user_id,
            normalized=normalized,
            snapshot_ts=snapshot_ts,
            provenance=provenance,
            trace_id=trace_id,
        )
    )
    _launch_background(task)
    _trace_event(
        trace_id,
        "ucnrr_forward_scheduled",
        {"user_id": user_id, "count": len(normalized)},
    )

    return {
        "ok": True,
        "forwarded": True,
        "user_id": user_id,
        "snapshot_ts": snapshot_ts,
        "changed_keys": list(normalized.keys()),
        "core_response": None,
        "trace_id": trace_id,
    }


@app.post("/ingest_file")
async def ingest_file(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    meta: Optional[str] = Form(default=None),
):
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")
    if not file:
        raise HTTPException(status_code=400, detail="file required")

    paths = _ensure_user_dirs(uid)
    inbox = paths["inbox"]

    safe_name = Path(file.filename or "upload.bin").name
    timestamp = _now_ts()
    stored_path = inbox / f"{timestamp}_{safe_name}"

    try:
        content = await file.read()
        stored_path.write_bytes(content)
    except Exception as exc:  # pragma: no cover - filesystem errors
        raise HTTPException(status_code=500, detail=f"write_failed:{exc}") from exc

    meta_payload: Dict[str, Any] = {}
    if meta:
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                meta_payload = parsed
            else:
                meta_payload = {"raw": parsed}
        except Exception:
            meta_payload = {"raw": meta}

    record = {
        "ts": timestamp,
        "filename": safe_name,
        "stored": stored_path.as_posix(),
    }
    if meta_payload:
        record["meta"] = meta_payload

    audit_path = inbox / f"{timestamp}_upload.json"
    try:
        _write_json(audit_path, record)
    except Exception:
        pass

    response = {
        "ok": True,
        "user_id": uid,
        "stored": stored_path.as_posix(),
        "observations": {},
        "note": "Stored for future analysis; vision extraction not yet implemented.",
    }
    if meta_payload:
        response["meta"] = meta_payload
    return response


def _collect_user_text(paths: Dict[str, Path]) -> str:
    inbox = paths.get("inbox")
    if not inbox or not inbox.exists():
        return ""
    texts: List[str] = []
    try:
        for fp in sorted(inbox.glob("*.json")):
            payload = _read_json(fp) or {}
            text = payload.get("text")
            if text:
                texts.append(str(text))
    except Exception:
        pass
    return "\n".join(texts)


@app.post("/holistic/{user_id}")
def holistic_review(user_id: str) -> Dict[str, Any]:
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id required")

    if not llm_is_available():
        return {"ok": False, "reason": "llm_unavailable"}

    paths = _ensure_user_dirs(uid)
    combined_text = _collect_user_text(paths)
    snapshot = _read_json(paths.get("snapshot", Path())) or {}
    observations = snapshot.get("observations") if isinstance(snapshot.get("observations"), dict) else {}
    if not combined_text and not observations:
        return {"ok": False, "reason": "no_history"}

    llm_payload = combined_text
    if observations:
        try:
            for item in observations.values():
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        llm_payload += "\n" + text
        except Exception:
            pass

    llm_map = _llm_extract(llm_payload) if llm_payload else {}
    if not llm_map:
        return {"ok": False, "reason": "llm_no_suggestions"}

    normalized = _merge_normalize(
        llm_map,
        {"source": "holistic", "actor": "ucnrr_holistic"}
    )
    core_res = _post_core_ingest(uid, normalized)
    return {
        "ok": bool(core_res.get("ok")),
        "user_id": uid,
        "changes": list(normalized.keys()),
        "core_response": core_res,
        "reason": "completed",
    }


@app.get("/ucnrr/debug/config")
def ucnrr_debug_config() -> Dict[str, Any]:
    """
    Debug endpoint: Effective UCNRR runtime config.
    Returns loaded environment, LLM config, timeouts, and startup status.
    """
    import sys

    # Determine which .env was loaded (if any)
    env_path_loaded = "none"
    possible_env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for p in possible_env_paths:
        if p.exists():
            env_path_loaded = str(p)
            break

    # LLM configuration
    ollama_base = os.getenv("OLLAMA_BASE_URL")
    llm_configured = _is_llm_configured()
    llm_configured_reason = "ok"

    if not llm_configured:
        if not LLM_PROVIDER:
            llm_configured_reason = "LLM_PROVIDER not set"
        elif LLM_PROVIDER.lower() == "ollama" and not (LLM_BASE_URL or ollama_base):
            llm_configured_reason = "Ollama selected but no LLM_BASE_URL or OLLAMA_BASE_URL"
        elif LLM_PROVIDER.lower() != "ollama" and not LLM_API_KEY:
            llm_configured_reason = "Paid provider selected but no LLM_API_KEY"
        else:
            llm_configured_reason = "unknown"

    # Effective base URL
    effective_base = LLM_BASE_URL or ollama_base or "none"

    return {
        "service": "ucnrr",
        "version": UCNRR_VERSION,
        "env_path_loaded": env_path_loaded,
        "llm_provider": LLM_PROVIDER or "none",
        "llm_model": LLM_MODEL or "none",
        "llm_base_url": effective_base,
        "ollama_base_url": ollama_base or "none",
        "llm_configured": llm_configured,
        "llm_configured_reason": llm_configured_reason,
        "llm_api_key_set": bool(LLM_API_KEY),
        "timeouts": {
            "note": "UCNRR uses requests library with explicit timeout params (typically 30s for LLM, 5-30s for Core)",
            "llm_timeout_sec": 30,
            "core_timeout_sec": 30,
        },
        "selftest_cache": {
            "enabled": True,
            "cache_window_sec": SELFTEST_CACHE_SEC,
            "bg_timeout_sec": SELFTEST_BG_TIMEOUT_SEC,
        },
        "injectors": {
            "chrono_injector_enabled": True,
            "chrono_rr_value": 830.0,
        },
        "features": {
            "use_min_heuristics": USE_MIN_HEURISTICS,
            "log_llm": LOG_LLM,
            "log_scores": LOG_SCORES,
            "roundtrip_tracing": ROUNDTRIP_TRACING_ENABLED,
        },
        "paths": {
            "data_dir": str(DATA_DIR),
            "prompt_path": str(PROMPT_PATH),
            "dna_weights_path": str(DNA_WEIGHTS_PATH),
            "trace_path": str(TRACE_PATH),
        },
    }


@app.get("/ucnrr/debug/probe")
def ucnrr_debug_probe() -> Dict[str, Any]:
    """
    Debug endpoint: Probe LLM connectivity.
    Tests /api/tags and /api/generate with strict short timeouts.
    """
    import requests

    if not LLM_PROVIDER:
        return {
            "ok": False,
            "reason": "LLM_PROVIDER not set",
            "tags_test": None,
            "generate_test": None,
        }

    # Effective base URL
    ollama_base = os.getenv("OLLAMA_BASE_URL")
    base_url = LLM_BASE_URL or ollama_base

    if not base_url:
        return {
            "ok": False,
            "reason": "No LLM_BASE_URL or OLLAMA_BASE_URL",
            "tags_test": None,
            "generate_test": None,
        }

    results = {
        "base_url": base_url,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL or "none",
    }

    # Test 1: /api/tags (Ollama-specific)
    tags_result = {"ok": False, "status_code": None, "error": None}
    if LLM_PROVIDER.lower() == "ollama":
        try:
            resp = requests.get(
                f"{base_url.rstrip('/')}/api/tags",
                timeout=3,
            )
            tags_result["ok"] = resp.ok
            tags_result["status_code"] = resp.status_code
            if resp.ok:
                tags_result["models"] = [m.get("name") for m in resp.json().get("models", [])]
        except requests.exceptions.Timeout:
            tags_result["error"] = "timeout"
        except requests.exceptions.ConnectionError as e:
            tags_result["error"] = f"connection_error: {str(e)}"
        except Exception as e:
            tags_result["error"] = str(e)
    else:
        tags_result["error"] = "not_ollama"

    results["tags_test"] = tags_result

    # Test 2: /api/generate (Ollama) or /v1/chat/completions (OpenAI-compatible)
    generate_result = {"ok": False, "status_code": None, "error": None}

    if LLM_PROVIDER.lower() == "ollama":
        try:
            resp = requests.post(
                f"{base_url.rstrip('/')}/api/generate",
                json={"model": LLM_MODEL or "phi3:mini", "prompt": "ok", "stream": False},
                timeout=5,
            )
            generate_result["ok"] = resp.ok
            generate_result["status_code"] = resp.status_code
            if resp.ok:
                generate_result["response_length"] = len(resp.json().get("response", ""))
        except requests.exceptions.Timeout:
            generate_result["error"] = "timeout (read timeout >5s = slow_model)"
        except requests.exceptions.ConnectionError as e:
            generate_result["error"] = f"connection_error: {str(e)}"
        except Exception as e:
            generate_result["error"] = str(e)
    else:
        # OpenAI-compatible endpoint
        try:
            headers = {}
            if LLM_API_KEY:
                headers["Authorization"] = f"Bearer {LLM_API_KEY}"

            resp = requests.post(
                f"{base_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": LLM_MODEL or "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "ok"}],
                    "stream": False,
                },
                headers=headers,
                timeout=5,
            )
            generate_result["ok"] = resp.ok
            generate_result["status_code"] = resp.status_code
            if resp.ok:
                generate_result["response_length"] = len(str(resp.json()))
        except requests.exceptions.Timeout:
            generate_result["error"] = "timeout (read timeout >5s = slow_model)"
        except requests.exceptions.ConnectionError as e:
            generate_result["error"] = f"connection_error: {str(e)}"
        except Exception as e:
            generate_result["error"] = str(e)

    results["generate_test"] = generate_result

    # Overall status
    results["ok"] = tags_result.get("ok", False) or generate_result.get("ok", False)

    return results


@app.post("/ucnrr/debug/trace")
def ucnrr_debug_trace(text: str = Body(..., embed=True)) -> Dict[str, Any]:
    """
    Debug endpoint: End-to-end scoring trace for a given text.
    Returns raw LLM input/output, canonicalization, and final RR scores.
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="text required")

    result = {
        "input_text": text,
        "llm_available": llm_is_available(),
        "llm_configured": _is_llm_configured(),
    }

    # Step 1: LLM extraction (if available)
    if llm_is_available():
        llm_raw = _llm_extract(text)
        result["llm_extraction"] = {
            "raw_output": llm_raw,
            "traits_extracted": list(llm_raw.keys()) if llm_raw else [],
        }
    else:
        result["llm_extraction"] = {
            "error": "LLM not available",
            "reason": "llm_is_available() returned False"
        }
        llm_raw = {}

    # Step 2: Canonicalization (via _CANON_MAP)
    canonicalized = {}
    for trait_id, value_dict in llm_raw.items():
        # Check if trait_id needs canonicalization
        canonical_id = _CANON_MAP.get(trait_id, trait_id)
        canonicalized[canonical_id] = value_dict

    result["canonicalization"] = {
        "before": list(llm_raw.keys()),
        "after": list(canonicalized.keys()),
        "canon_map_applied": canonicalized != llm_raw,
    }

    # Step 3: Scoring (simulate /ucnrr/score path)
    rr_by_trait: Dict[str, float] = {}
    for trait_id, value_dict in canonicalized.items():
        # Simple RR calculation (mimic actual score logic)
        ucn = value_dict.get("ucn", 0.8)
        source = value_dict.get("source", "llm")

        # Base RR from UCN
        base_rr = ucn * 1000.0

        # Apply source multipliers (simplified)
        if source == "llm":
            rr = base_rr * 0.85  # LLM discount
        else:
            rr = base_rr

        rr_by_trait[trait_id] = rr

    # Step 4: Chronotype injection check
    chrono_injected = False
    if _detect_chronotype(text):
        if "BehaviorDNA.Sleep.Chronotype" not in rr_by_trait:
            _maybe_inject_chronotype(text, rr_by_trait)
            chrono_injected = True

    result["scoring"] = {
        "rr_by_trait": rr_by_trait,
        "chronotype_detected": _detect_chronotype(text),
        "chronotype_injected": chrono_injected,
    }

    return result


@app.get("/legacy_export")
def legacy_export(user_id: str) -> Dict[str, Any]:
    paths = _ensure_user_dirs(user_id)
    snap = _read_json(paths["snapshot"]) or {"ts": _now_ts(), "resolved": {}, "observations": {}}
    return {"ok": True, "user_id": user_id, "snapshot": snap}
