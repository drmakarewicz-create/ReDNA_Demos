"""Helpers for loading, validating, and diffing trait container schemas."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root  # type: ignore

ensure_explorerdev_on_path()

import copy
import csv
import io
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests
import yaml

from ExplorerFinal.core import nudge_store


# ----- Runtime defaults -----------------------------------------------------------


REPO_ROOT = ensure_repo_root()
SYSTEM_PREFS_PATH = REPO_ROOT / "data" / "dev_system_prefs.json"

_DEFAULT_CORE_BASE = "http://127.0.0.1:8015"
_DEFAULT_UCNRR_BASE = "http://127.0.0.1:8011"
_DEFAULT_LLM_BASE = "http://127.0.0.1:11434"

_SYSTEM_PREFS_CACHE: Optional[Dict[str, Any]] = None
_SYSTEM_PREFS_MTIME: Optional[float] = None

DEV_TRUE_SET = {"1", "true", "yes", "on"}


_CORE_HEALTH_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None, "error": None}




def _load_system_prefs() -> Dict[str, Any]:
    global _SYSTEM_PREFS_CACHE, _SYSTEM_PREFS_MTIME

    current_mtime: Optional[float] = None
    try:
        stat_result = SYSTEM_PREFS_PATH.stat()
        current_mtime = float(stat_result.st_mtime)
    except FileNotFoundError:
        _SYSTEM_PREFS_CACHE = {}
        _SYSTEM_PREFS_MTIME = None
        return _SYSTEM_PREFS_CACHE
    except Exception:  # pragma: no cover - non-critical
        current_mtime = None

    if (
        _SYSTEM_PREFS_CACHE is not None
        and _SYSTEM_PREFS_MTIME is not None
        and current_mtime is not None
        and current_mtime <= _SYSTEM_PREFS_MTIME
    ):
        return _SYSTEM_PREFS_CACHE

    try:
        payload = json.loads(SYSTEM_PREFS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            _SYSTEM_PREFS_CACHE = payload
        else:
            _SYSTEM_PREFS_CACHE = {}
    except Exception:  # pragma: no cover - prefs are advisory only
        _SYSTEM_PREFS_CACHE = {}

    _SYSTEM_PREFS_MTIME = current_mtime
    return _SYSTEM_PREFS_CACHE


_SERVICE_KEY_MAP = {
    "CORE_BASE_URL": ("service_console", "core_base"),
    "UCNRR_BASE_URL": ("service_console", "ucnrr_base"),
    "LLM_BASE_URL": ("service_console", "llm_base"),
}


def _get_pref(name: str) -> Optional[str]:
    prefs = _load_system_prefs()
    if not prefs:
        return None

    direct = prefs.get(name)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    path = _SERVICE_KEY_MAP.get(name)
    if path:
        node: Any = prefs
        for key in path:
            if not isinstance(node, Mapping):
                node = None
                break
            node = node.get(key)
        if isinstance(node, str) and node.strip():
            return node.strip()

    return None


# ----- Flag helpers --------------------------------------------------------------


def _parse_bool_flag(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in DEV_TRUE_SET:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def get_flag_bool(name: str, default: bool = False) -> Tuple[bool, str]:
    env_raw = os.getenv(name)
    env_value = _parse_bool_flag(env_raw)
    if env_value is not None:
        return bool(env_value), "env"

    pref_raw = _get_pref(name)
    pref_value = _parse_bool_flag(pref_raw)
    if pref_value is not None:
        return bool(pref_value), "prefs"

    return bool(default), "default"


def get_flag_str(name: str, default: str = "") -> Tuple[str, str]:
    env_raw = os.getenv(name)
    if env_raw is not None:
        return str(env_raw).strip(), "env"

    pref_raw = _get_pref(name)
    if pref_raw is not None:
        return str(pref_raw).strip(), "prefs"

    return str(default), "default"


def get_flag_float(name: str, default: float = 0.0) -> Tuple[float, str]:
    env_raw = os.getenv(name)
    if env_raw is not None:
        try:
            return float(env_raw), "env"
        except (TypeError, ValueError):
            pass

    pref_raw = _get_pref(name)
    if pref_raw is not None:
        try:
            return float(pref_raw), "prefs"
        except (TypeError, ValueError):
            pass

    return float(default), "default"


def get_flag_int(name: str, default: int = 0) -> Tuple[int, str]:
    env_raw = os.getenv(name)
    if env_raw is not None:
        try:
            return int(float(env_raw)), "env"
        except (TypeError, ValueError):
            pass

    pref_raw = _get_pref(name)
    if pref_raw is not None:
        try:
            return int(float(pref_raw)), "prefs"
        except (TypeError, ValueError):
            pass

    return int(default), "default"


def invalidate_system_prefs_cache() -> None:
    """Clear cached dev system preferences so fresh reads pick up changes."""

    global _SYSTEM_PREFS_CACHE, _SYSTEM_PREFS_MTIME
    _SYSTEM_PREFS_CACHE = None
    _SYSTEM_PREFS_MTIME = None


def _resolve_base(
    primary_env: str,
    *,
    fallback_env: Optional[str],
    pref_key: str,
    default: str,
) -> Tuple[str, str]:
    env_value = os.getenv(primary_env)
    if env_value:
        return str(env_value).rstrip("/"), "env"

    if fallback_env:
        fallback_value = os.getenv(fallback_env)
        if fallback_value:
            return str(fallback_value).rstrip("/"), "env"

    pref_value = _get_pref(pref_key)
    if pref_value:
        return str(pref_value).rstrip("/"), "prefs"

    return str(default).rstrip("/"), "default"


def core_base_state(default: Optional[str] = None) -> Tuple[str, str]:
    return _resolve_base(
        "CORE_BASE_URL",
        fallback_env="CORE_BASE",
        pref_key="CORE_BASE_URL",
        default=default or _DEFAULT_CORE_BASE,
    )


def ucnrr_base_state(default: Optional[str] = None) -> Tuple[str, str]:
    return _resolve_base(
        "UCNRR_BASE_URL",
        fallback_env="UCNRR_BASE",
        pref_key="UCNRR_BASE_URL",
        default=default or _DEFAULT_UCNRR_BASE,
    )


def llm_base_state(default: Optional[str] = None) -> Tuple[str, str]:
    env_value = os.getenv("LLM_BASE_URL")
    if env_value:
        return str(env_value).rstrip("/"), "env"

    pref_value = _get_pref("LLM_BASE_URL")
    if pref_value:
        return str(pref_value).rstrip("/"), "prefs"

    return str(default or _DEFAULT_LLM_BASE).rstrip("/"), "default"


# ----- Data model -----------------------------------------------------------------


TraitRecord = Dict[str, Any]
ContainerRecord = Dict[str, Any]
SchemaDoc = Dict[str, Any]


STATUS_ACTIVE = "active"
STATUS_DEPRECATED = "deprecated"
STATUS_DRAFT = "draft"

DEFAULT_DECAY = "steady"
DEFAULT_SENSITIVITY = "medium"
DEFAULT_CURIOSITY = "baseline"

VALID_SENSITIVITY = {"low", "medium", "high", "restricted"}
DEFAULT_DECAY_OPTIONS = {"fast", "medium", "slow"}

OBSERVATIONAL_CONTAINER_IDS = {
    "conversational_dynamics",
    "communication_tone",
    "interaction_preferences",
    "cognitive_signatures",
    "rapport_markers",
    "meta_interaction_habits",
}

PADNA_CONTAINER_PREFIXES = ("padna_",)


@dataclass(slots=True)
class SchemaValidationMessage:
    source: str
    level: str
    message: str
    subject: Optional[str] = None


@dataclass(slots=True)
class SchemaValidationResult:
    json_errors: List[SchemaValidationMessage] = field(default_factory=list)
    json_warnings: List[SchemaValidationMessage] = field(default_factory=list)
    ai_feedback: List[SchemaValidationMessage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.json_errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "json_errors": [msg.__dict__ for msg in self.json_errors],
            "json_warnings": [msg.__dict__ for msg in self.json_warnings],
            "ai_feedback": [msg.__dict__ for msg in self.ai_feedback],
            "ok": self.ok,
        }


@dataclass(slots=True)
class ContainerMetrics:
    container_id: str
    label: str
    trait_count: int
    coverage: Dict[str, int]
    status: str
    sensitive: bool = False
    category: str = "general"


@dataclass(slots=True)
class CoverageRow:
    container_id: str
    container_label: str
    known: int
    partial: int
    unknown: int


@dataclass(slots=True)
class TraitCuriosity:
    container_id: str
    trait_id: str
    trait_label: str
    curiosity: float
    simulated_ucn: float
    sensitivity_flag: bool
    default_decay: str
    weight: float = 1.0
    data_source: Optional[str] = None
    rr: Optional[float] = None


@dataclass(slots=True)
class MotivatorTemplateResult:
    container_id: str
    trait_id: str
    trait_label: str
    template: Optional[str]
    tone_used: str
    template_source: str
    trait_source: str


@dataclass(slots=True)
class SchemaDiff:
    containers_added: List[str] = field(default_factory=list)
    containers_removed: List[str] = field(default_factory=list)
    containers_changed: List[str] = field(default_factory=list)
    traits_added: Dict[str, List[str]] = field(default_factory=dict)
    traits_removed: Dict[str, List[str]] = field(default_factory=dict)
    traits_changed: Dict[str, List[str]] = field(default_factory=dict)

    def has_changes(self) -> bool:
        return any(
            (
                self.containers_added,
                self.containers_removed,
                self.containers_changed,
                self.traits_added,
                self.traits_removed,
                self.traits_changed,
            )
        )

    def summary_rows(self) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for container_id in self.containers_added:
            rows.append({"kind": "container", "change": "added", "id": container_id})
        for container_id in self.containers_removed:
            rows.append({"kind": "container", "change": "removed", "id": container_id})
        for container_id in self.containers_changed:
            rows.append({"kind": "container", "change": "updated", "id": container_id})

        def _flatten(items: Dict[str, List[str]], change: str) -> None:
            for container_id, trait_ids in items.items():
                for trait_id in trait_ids:
                    rows.append({
                        "kind": "trait",
                        "change": change,
                        "id": trait_id,
                        "container": container_id,
                    })

        _flatten(self.traits_added, "added")
        _flatten(self.traits_removed, "removed")
        _flatten(self.traits_changed, "updated")
        return rows


# ----- Load / Save ----------------------------------------------------------------


def schema_path(repo_root: Path) -> Path:
    return repo_root / "core_config" / "trait_schema.yaml"


def draft_directory(repo_root: Path) -> Path:
    return repo_root / "data" / "dev_schema_drafts"


def draft_path(repo_root: Path) -> Path:
    return draft_directory(repo_root) / "trait_schema.WIP.json"


def log_path(repo_root: Path) -> Path:
    return repo_root / "data" / "dev_logs" / "container_changes.log"


def curiosity_flag_enabled() -> bool:
    value, _ = get_flag_bool("CORE_CURIOSITY_ENABLED", False)
    return value


def curiosity_flag_state() -> Tuple[bool, str]:
    return get_flag_bool("CORE_CURIOSITY_ENABLED", False)


def core_base_url(default: Optional[str] = None) -> str:
    return core_base_state(default)[0]


def ucnrr_base_url(default: Optional[str] = None) -> str:
    return ucnrr_base_state(default)[0]


def llm_base_url(default: Optional[str] = None) -> str:
    return llm_base_state(default)[0]


def core_health_snapshot(*, ttl: float = 5.0, timeout: float = 2.0) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _CORE_HEALTH_CACHE
    now = time.time()
    if now - (_CORE_HEALTH_CACHE.get("ts") or 0.0) < ttl:
        return _CORE_HEALTH_CACHE.get("payload"), _CORE_HEALTH_CACHE.get("error")

    url = core_base_url().rstrip("/") + "/health"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload: Optional[Dict[str, Any]]
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                payload = None
        except Exception:
            payload = None
        _CORE_HEALTH_CACHE = {"ts": now, "payload": payload, "error": None}
        return payload, None
    except Exception as exc:
        _CORE_HEALTH_CACHE = {"ts": now, "payload": None, "error": str(exc)}
        return None, str(exc)


def core_curiosity_status(*, ttl: float = 5.0, timeout: float = 2.0) -> Tuple[Optional[bool], Optional[str]]:
    payload, error = core_health_snapshot(ttl=ttl, timeout=timeout)
    if isinstance(payload, Mapping):
        value = payload.get("curiosity_enabled")
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            return value.strip().lower() in DEV_TRUE_SET, None
    return None, error


def fetch_core_resolved_flat(
    user_id: str,
    *,
    core_base: Optional[str] = None,
    timeout: float = 3.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch the flat resolved snapshot for ``user_id`` from Core."""

    base_url = (core_base or core_base_url()).rstrip("/")
    resolved_url = f"{base_url}/resolved/flat/{user_id}"
    try:
        response = requests.get(resolved_url, timeout=timeout)
        if response.status_code == 404:
            return None, "Core resolved snapshot not found for user."
        response.raise_for_status()
        try:
            payload: Any = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, Mapping):
            return dict(payload), None
        return None, "Resolved payload malformed."
    except Exception as exc:
        return None, str(exc)


def load_live_curiosity_snapshot(
    user_id: str,
    *,
    core_base: Optional[str] = None,
    limit: int = 100,
    timeout: float = 3.0,
) -> LiveCuriositySnapshot:
    base_url = (core_base or core_base_url()).rstrip("/")
    curiosity_url = f"{base_url}/curiosity/{user_id}"
    ensure_url = f"{base_url}/user/{user_id}/ensure"
    fetched_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    top_traits: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    error_message: Optional[str] = None
    error_detail: Optional[str] = None
    curiosity_enabled: Optional[bool] = None
    resolved_stub: Dict[str, Any] = {}

    try:
        # Warm the user session in Core without treating failures as fatal.
        requests.post(ensure_url, timeout=min(timeout, 6.0))
    except Exception:  # pragma: no cover - best-effort call
        pass

    params = {"limit": max(1, min(int(limit), 200))}
    try:
        curiosity_resp = requests.get(curiosity_url, params=params, timeout=timeout)
        if curiosity_resp.status_code == 404:
            error_message = "Curiosity endpoint unavailable (flag off?)."
        else:
            curiosity_resp.raise_for_status()
            curiosity_json: Any
            try:
                curiosity_json = curiosity_resp.json()
            except ValueError:
                curiosity_json = None
            if isinstance(curiosity_json, Mapping):
                raw_flag = curiosity_json.get("curiosity_enabled")
                if isinstance(raw_flag, bool):
                    curiosity_enabled = raw_flag
                elif isinstance(raw_flag, str):
                    curiosity_enabled = raw_flag.strip().lower() in DEV_TRUE_SET

                raw_rows = curiosity_json.get("items")
                if not isinstance(raw_rows, list):
                    raw_rows = curiosity_json.get("top_traits") if isinstance(curiosity_json.get("top_traits"), list) else []

                raw_counts = curiosity_json.get("source_counts")
                if isinstance(raw_counts, Mapping):
                    for key, value in raw_counts.items():
                        try:
                            source_counts[str(key).upper()] = int(value)
                        except (TypeError, ValueError):
                            continue

                parsed_rows: List[Dict[str, Any]] = []
                for entry in raw_rows or []:
                    if not isinstance(entry, Mapping):
                        continue
                    container_id = str(entry.get("container") or entry.get("container_id") or "").strip()
                    trait_id = str(entry.get("trait_id") or entry.get("trait") or "").strip()
                    if not container_id or not trait_id:
                        continue
                    curiosity_val = _safe_float(entry.get("curiosity"))
                    if curiosity_val is None:
                        curiosity_val = 0.0
                    curiosity_val = max(0.0, min(curiosity_val, 1.0))
                    ucn_val = _safe_float(entry.get("ucn"))
                    if ucn_val is not None and ucn_val > 1.0:
                        ucn_val = max(0.0, min(ucn_val, 100.0)) / 100.0

                    weight_val = _safe_float(entry.get("weight"))
                    if weight_val is None or weight_val <= 0.0:
                        weight_val = 1.0

                    raw_source = entry.get("source") or entry.get("curiosity_source")
                    source_label = str(raw_source).strip() if isinstance(raw_source, str) else ""
                    normalized_source = source_label.upper() if source_label else "UNKNOWN"
                    source_counts[normalized_source] = source_counts.get(normalized_source, 0) + 1

                    rr_val = _safe_float(entry.get("rr"))
                    if rr_val is not None and rr_val > 1.0:
                        rr_val = max(0.0, min(rr_val, 100.0)) / 100.0
                    if rr_val is not None:
                        rr_val = max(0.0, min(rr_val, 1.0))

                    parsed_rows.append(
                        {
                            "container_id": container_id,
                            "trait_id": trait_id,
                            "curiosity": curiosity_val,
                            "ucn": ucn_val,
                            "resolved_value": entry.get("resolved_value"),
                            "weight": weight_val,
                            "source": source_label or normalized_source,
                            "rr": rr_val,
                        }
                    )
                    resolved_stub[trait_id] = {
                        "container_id": container_id,
                        "curiosity": curiosity_val,
                        "ucn": ucn_val,
                        "resolved_value": entry.get("resolved_value"),
                        "curiosity_weight": weight_val,
                        "curiosity_source": normalized_source,
                        "weight": weight_val,
                        "rr": rr_val,
                        "curiosity_rr": rr_val,
                    }
                top_traits = parsed_rows
    except requests.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        reason = getattr(getattr(exc, "response", None), "reason", "") or ""
        snippet = ""
        response_obj = getattr(exc, "response", None)
        if response_obj is not None:
            try:
                body_text = response_obj.text or ""
            except Exception:  # pragma: no cover - log-safe path
                body_text = ""
            snippet = " ".join(body_text.split()).strip()
            if len(snippet) > 120:
                snippet = snippet[:120] + "…"
        if status is not None:
            status_label = f"HTTP {status}"
            if reason:
                status_label += f" {reason}"
            error_message = f"Curiosity fetch failed: {status_label}"
            detail_parts = [status_label]
            if snippet:
                detail_parts.append(snippet)
            error_detail = " :: ".join(detail_parts)
        else:
            error_message = f"Curiosity fetch failed: {exc}"
            error_detail = str(exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        error_message = f"Curiosity fetch error: {exc}"
        error_detail = str(exc)

    if not resolved_stub and top_traits:
        for row in top_traits:
            if not isinstance(row, Mapping):
                continue
            trait_id = str(row.get("trait_id") or row.get("trait") or "").strip()
            container_id = str(row.get("container_id") or row.get("container") or "").strip()
            if not trait_id or not container_id:
                continue
            curiosity_val = _safe_float(row.get("curiosity")) or 0.0
            ucn_val = _safe_float(row.get("ucn"))
            weight_val = _safe_float(row.get("weight"))
            if weight_val is None or weight_val <= 0.0:
                weight_val = 1.0
            raw_source = row.get("source") or row.get("curiosity_source")
            source_label = str(raw_source).strip() if isinstance(raw_source, str) else ""
            normalized_source = source_label.upper() if source_label else "UNKNOWN"
            rr_val = _safe_float(row.get("rr"))
            if rr_val is not None and rr_val > 1.0:
                rr_val = max(0.0, min(rr_val, 100.0)) / 100.0
            if rr_val is not None:
                rr_val = max(0.0, min(rr_val, 1.0))
            resolved_stub[trait_id] = {
                "container_id": container_id,
                "curiosity": curiosity_val,
                "ucn": ucn_val,
                "resolved_value": row.get("resolved_value"),
                "curiosity_weight": weight_val,
                "curiosity_source": normalized_source,
                "weight": weight_val,
                "rr": rr_val,
                "curiosity_rr": rr_val,
            }

    return LiveCuriositySnapshot(
        user_id=user_id,
        resolved=resolved_stub,
        top_traits=top_traits,
        fetched_at=fetched_at,
        error=error_message,
        curiosity_enabled=curiosity_enabled,
        error_detail=error_detail,
        source_counts=source_counts or None,
    )


def ensure_seed_schema(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    seed = {
        "version": 2,
        "generated_at": now,
        "curiosity_weights": {"identity": 1.0},
        "containers": [
            {
                "id": "identity",
                "label": "Identity",
                "status": STATUS_ACTIVE,
                "description": "Core identifying attributes used as fallbacks when the canonical schema is missing.",
                "traits": [
                    {
                        "id": "identity.full_name",
                        "label": "Full Name",
                        "type": "text",
                        "default_curiosity": DEFAULT_CURIOSITY,
                        "default_decay": "medium",
                        "sensitivity_flag": False,
                        "computed": False,
                        "last_updated": now,
                        "links": [],
                    }
                ],
            }
        ],
    }
    path.write_text(yaml.safe_dump(seed, sort_keys=False), encoding="utf-8")


def load_schema(repo_root: Path) -> SchemaDoc:
    path = schema_path(repo_root)
    ensure_seed_schema(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trait_schema.yaml must contain a mapping at the root level.")
    containers = data.get("containers")
    if not isinstance(containers, list):
        data["containers"] = []
    return data


def load_saved_draft(repo_root: Path) -> Optional[SchemaDoc]:
    path = draft_path(repo_root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def clone_schema(schema: SchemaDoc) -> SchemaDoc:
    return copy.deepcopy(schema)


def export_schema_csv(schema: SchemaDoc) -> str:
    containers: Sequence[ContainerRecord] = schema.get("containers", [])  # type: ignore[assignment]
    buffer: List[List[str]] = []
    header = [
        "container_id",
        "container_label",
        "container_status",
        "trait_id",
        "trait_label",
        "type",
        "decay",
        "sensitivity",
        "curiosity",
        "coverage",
        "computed",
        "last_updated",
        "motivator_neutral",
        "motivator_gentle",
        "motivator_blunt",
        "motivator_long",
    ]
    buffer.append(header)
    for container in containers:
        traits: Sequence[TraitRecord] = container.get("traits", [])  # type: ignore[assignment]
        for trait in traits:
            row = [
                str(container.get("id", "")),
                str(container.get("label", "")),
                str(container.get("status", STATUS_ACTIVE)),
                str(trait.get("id", "")),
                str(trait.get("label", "")),
                str(trait.get("type", "")),
                str(trait.get("decay", "")),
                str(trait.get("sensitivity", "")),
                str(trait.get("curiosity", "")),
                str(trait.get("coverage", "")),
                json.dumps(bool(trait.get("computed", False))),
                str(trait.get("last_updated", "")),
                str((trait.get("motivators") or {}).get("neutral", "")),
                str((trait.get("motivators") or {}).get("gentle", "")),
                str((trait.get("motivators") or {}).get("blunt", "")),
                str((trait.get("motivators") or {}).get("long", "")),
            ]
            buffer.append(row)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(buffer)
    return output.getvalue()


# ----- Metrics --------------------------------------------------------------------


def _iter_containers(schema: SchemaDoc) -> Iterable[ContainerRecord]:
    containers = schema.get("containers", [])
    if isinstance(containers, list):
        for container in containers:
            if isinstance(container, dict):
                yield container


def _iter_traits(container: ContainerRecord) -> Iterable[TraitRecord]:
    traits = container.get("traits", [])
    if isinstance(traits, list):
        for trait in traits:
            if isinstance(trait, dict):
                yield trait


def container_is_sensitive(container: Optional[ContainerRecord]) -> bool:
    if not isinstance(container, dict):
        return False
    if bool(container.get("sensitive")):
        return True
    for trait in _iter_traits(container):
        if trait.get("sensitivity_flag"):
            return True
        sensitivity = str(trait.get("sensitivity") or "").lower()
        if sensitivity in {"high", "restricted"}:
            return True
    return False


def infer_container_category(
    container_id: str,
    container: Optional[ContainerRecord],
) -> str:
    if container_is_sensitive(container) or any(
        container_id.startswith(prefix) for prefix in PADNA_CONTAINER_PREFIXES
    ):
        return "padna"
    if container_id in OBSERVATIONAL_CONTAINER_IDS:
        return "observational"
    return "general"


def container_metrics(schema: SchemaDoc) -> List[ContainerMetrics]:
    metrics: List[ContainerMetrics] = []
    for container in _iter_containers(schema):
        coverage_counts = {"known": 0, "partial": 0, "unknown": 0}
        for trait in _iter_traits(container):
            status = str(trait.get("coverage") or "unknown").lower()
            if status not in coverage_counts:
                status = "unknown"
            coverage_counts[status] += 1
        container_id = str(container.get("id", ""))
        metrics.append(
            ContainerMetrics(
                container_id=container_id,
                label=str(container.get("label", "")),
                trait_count=sum(coverage_counts.values()),
                coverage=coverage_counts,
                status=str(container.get("status", STATUS_ACTIVE)),
                sensitive=container_is_sensitive(container),
                category=infer_container_category(container_id, container),
            )
        )
    return metrics


def locate_container(schema: SchemaDoc, container_id: str) -> Optional[ContainerRecord]:
    for container in _iter_containers(schema):
        if str(container.get("id")) == container_id:
            return container
    return None


def locate_trait(container: ContainerRecord, trait_id: str) -> Optional[TraitRecord]:
    for trait in _iter_traits(container):
        if str(trait.get("id")) == trait_id:
            return trait
    return None


_MOTIVATOR_TONE_FALLBACKS: Tuple[str, ...] = ("gentle", "neutral", "blunt", "long")


def _normalize_tone_key(tone: str) -> str:
    token = str(tone or "").strip().lower()
    if token in {"gentle", "neutral", "blunt", "long"}:
        return token
    if token == "kind":
        return "gentle"
    if token == "direct":
        return "blunt"
    return "neutral"


def _select_template_from_trait(
    trait: Optional[Mapping[str, Any]],
    tone: str,
) -> Tuple[Optional[str], str]:
    if not isinstance(trait, Mapping):
        return None, tone
    motivators = trait.get("motivators") if isinstance(trait.get("motivators"), Mapping) else {}
    if not motivators:
        return None, tone

    normalized = _normalize_tone_key(tone)
    candidates: List[str] = [normalized]
    for fallback in _MOTIVATOR_TONE_FALLBACKS:
        if fallback not in candidates:
            candidates.append(fallback)
    for candidate in candidates:
        template = motivators.get(candidate)
        if isinstance(template, str) and template.strip():
            return template.strip(), candidate
    for key, template in motivators.items():
        if isinstance(template, str) and template.strip():
            return template.strip(), str(key)
    return None, tone


def resolve_motivator_template(
    base_schema: SchemaDoc,
    draft_schema: Optional[SchemaDoc],
    container_id: str,
    trait_id: str,
    tone: str,
) -> MotivatorTemplateResult:
    normalized_tone = _normalize_tone_key(tone)
    trait_label = trait_id
    template: Optional[str] = None
    tone_used = normalized_tone
    template_source = "fallback"
    trait_source = "missing"

    def _find_trait(schema: Optional[SchemaDoc]) -> Optional[TraitRecord]:
        if not schema:
            return None
        container = locate_container(schema, container_id)
        if not container:
            return None
        return locate_trait(container, trait_id)

    draft_trait = _find_trait(draft_schema)
    if draft_trait:
        trait_label = str(draft_trait.get("label") or trait_label)
        draft_template, tone_used_candidate = _select_template_from_trait(draft_trait, normalized_tone)
        if draft_template:
            template = draft_template
            tone_used = tone_used_candidate
            template_source = "draft"
            trait_source = "draft"

    if template is None:
        base_trait = _find_trait(base_schema)
        if base_trait:
            trait_label = str(base_trait.get("label") or trait_label)
            base_template, base_tone = _select_template_from_trait(base_trait, normalized_tone)
            if base_template:
                template = base_template
                tone_used = base_tone
                template_source = "live"
                trait_source = "live"
            elif trait_source == "missing":
                trait_source = "live"
        elif trait_source == "missing":
            trait_source = "missing"

    if template is None:
        template_source = "fallback"

    return MotivatorTemplateResult(
        container_id=container_id,
        trait_id=trait_id,
        trait_label=trait_label,
        template=template,
        tone_used=tone_used,
        template_source=template_source,
        trait_source=trait_source,
    )


# ----- Diff -----------------------------------------------------------------------


def diff_schemas(base: SchemaDoc, draft: SchemaDoc) -> SchemaDiff:
    diff = SchemaDiff()

    base_map = {str(c.get("id")): c for c in _iter_containers(base)}
    draft_map = {str(c.get("id")): c for c in _iter_containers(draft)}

    base_ids = set(base_map)
    draft_ids = set(draft_map)

    diff.containers_added = sorted(draft_ids - base_ids)
    diff.containers_removed = sorted(base_ids - draft_ids)
    shared_ids = base_ids & draft_ids

    for container_id in sorted(shared_ids):
        base_container = base_map[container_id]
        draft_container = draft_map[container_id]
        if _containers_differ(base_container, draft_container):
            diff.containers_changed.append(container_id)

        base_traits = {str(t.get("id")): t for t in _iter_traits(base_container)}
        draft_traits = {str(t.get("id")): t for t in _iter_traits(draft_container)}

        base_trait_ids = set(base_traits)
        draft_trait_ids = set(draft_traits)

        added = sorted(draft_trait_ids - base_trait_ids)
        removed = sorted(base_trait_ids - draft_trait_ids)
        changed: List[str] = []

        for trait_id in sorted(base_trait_ids & draft_trait_ids):
            if _traits_differ(base_traits[trait_id], draft_traits[trait_id]):
                changed.append(trait_id)

        if added:
            diff.traits_added[container_id] = added
        if removed:
            diff.traits_removed[container_id] = removed
        if changed:
            diff.traits_changed[container_id] = changed

    return diff


def _containers_differ(a: ContainerRecord, b: ContainerRecord) -> bool:
    shallow_keys = {"label", "status", "description"}
    for key in shallow_keys:
        if (a.get(key) or "") != (b.get(key) or ""):
            return True
    return False


def _traits_differ(a: TraitRecord, b: TraitRecord) -> bool:
    for key in _TRAIT_COMPARE_FIELDS:
        if _normalize_trait_field(a.get(key)) != _normalize_trait_field(b.get(key)):
            return True
    return False


def _container_diff_details(a: ContainerRecord, b: ContainerRecord) -> Dict[str, Dict[str, Any]]:
    details: Dict[str, Dict[str, Any]] = {}
    for key in ("label", "status", "description"):
        old_value = str(a.get(key) or "")
        new_value = str(b.get(key) or "")
        if old_value != new_value:
            details[key] = {"from": old_value, "to": new_value}
    return details


_TRAIT_COMPARE_FIELDS: Tuple[str, ...] = (
    "label",
    "type",
    "decay",
    "sensitivity",
    "curiosity",
    "coverage",
    "computed",
    "last_updated",
    "links",
    "status",
    "default_decay",
    "default_curiosity",
    "sensitivity_flag",
    "motivators",
)


def _trait_diff_details(a: TraitRecord, b: TraitRecord) -> Dict[str, Dict[str, Any]]:
    details: Dict[str, Dict[str, Any]] = {}
    for key in _TRAIT_COMPARE_FIELDS:
        if _normalize_trait_field(a.get(key)) != _normalize_trait_field(b.get(key)):
            details[key] = {
                "from": _json_safe(a.get(key)),
                "to": _json_safe(b.get(key)),
            }
    return details


def _normalize_trait_field(value: Any) -> Any:
    if isinstance(value, list):
        return sorted([_normalize_trait_field(item) for item in value])
    if isinstance(value, dict):
        return {k: _normalize_trait_field(v) for k, v in sorted(value.items())}
    return value


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return repr(value)


# ----- Validation -----------------------------------------------------------------


def validate_schema(draft: SchemaDoc) -> SchemaValidationResult:
    result = SchemaValidationResult()

    if not isinstance(draft, dict):
        result.json_errors.append(
            SchemaValidationMessage(
                source="json",
                level="error",
                message="Schema root must be a JSON object (mapping).",
            )
        )
        return result

    containers = draft.get("containers")
    if not isinstance(containers, list):
        result.json_errors.append(
            SchemaValidationMessage(
                source="json",
                level="error",
                message="`containers` must be a list of container objects.",
            )
        )
        containers = []

    seen_container_ids: set[str] = set()

    for idx, container in enumerate(containers):
        prefix = f"containers[{idx}]"
        if not isinstance(container, dict):
            result.json_errors.append(
                SchemaValidationMessage(
                    source="json",
                    level="error",
                    message="Each container must be a mapping/object.",
                    subject=prefix,
                )
            )
            continue

        container_id = str(container.get("id") or "").strip()
        if not container_id:
            result.json_errors.append(
                SchemaValidationMessage(
                    source="json",
                    level="error",
                    message="Container is missing required `id`.",
                    subject=prefix,
                )
            )
        elif container_id in seen_container_ids:
            result.json_errors.append(
                SchemaValidationMessage(
                    source="json",
                    level="error",
                    message=f"Duplicate container id `{container_id}` detected.",
                    subject=prefix,
                )
            )
        else:
            seen_container_ids.add(container_id)

        if not str(container.get("label") or "").strip():
            result.json_warnings.append(
                SchemaValidationMessage(
                    source="json",
                    level="warning",
                    message="Container is missing a `label`.",
                    subject=prefix,
                )
            )

        traits = container.get("traits")
        if not isinstance(traits, list):
            result.json_errors.append(
                SchemaValidationMessage(
                    source="json",
                    level="error",
                    message="Container `traits` must be a list.",
                    subject=prefix,
                )
            )
            continue

        seen_trait_ids: set[str] = set()
        for t_idx, trait in enumerate(traits):
            subject = f"{prefix}.traits[{t_idx}]"
            if not isinstance(trait, dict):
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message="Trait entries must be mappings/objects.",
                        subject=subject,
                    )
                )
                continue

            trait_id = str(trait.get("id") or "").strip()
            if not trait_id:
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message="Trait missing required `id`.",
                        subject=subject,
                    )
                )
            elif trait_id in seen_trait_ids:
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message=f"Duplicate trait id `{trait_id}` in container `{container_id}`.",
                        subject=subject,
                    )
                )
            else:
                seen_trait_ids.add(trait_id)

            if not str(trait.get("label") or "").strip():
                result.json_warnings.append(
                    SchemaValidationMessage(
                        source="json",
                        level="warning",
                        message="Trait missing human-readable `label`.",
                        subject=subject,
                    )
                )

            if not str(trait.get("type") or "").strip():
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message="Trait missing required `type`.",
                        subject=subject,
                    )
                )

            computed = trait.get("computed")
            if computed not in {True, False, None}:
                result.json_warnings.append(
                    SchemaValidationMessage(
                        source="json",
                        level="warning",
                        message="Trait `computed` should be boolean.",
                        subject=subject,
                    )
                )

            default_curiosity = trait.get("default_curiosity")
            if default_curiosity is not None:
                if not isinstance(default_curiosity, (int, float)):
                    result.json_errors.append(
                        SchemaValidationMessage(
                            source="json",
                            level="error",
                            message="`default_curiosity` must be numeric between 0 and 1.",
                            subject=subject,
                        )
                    )
                elif not (0.0 <= float(default_curiosity) <= 1.0):
                    result.json_errors.append(
                        SchemaValidationMessage(
                            source="json",
                            level="error",
                            message="`default_curiosity` must be between 0 and 1.",
                            subject=subject,
                        )
                    )

            default_decay = trait.get("default_decay")
            if default_decay is not None and str(default_decay) not in DEFAULT_DECAY_OPTIONS:
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message="`default_decay` must be one of fast/medium/slow.",
                        subject=subject,
                    )
                )

            sensitivity_flag = trait.get("sensitivity_flag")
            if sensitivity_flag not in {None, True, False}:
                result.json_errors.append(
                    SchemaValidationMessage(
                        source="json",
                        level="error",
                        message="`sensitivity_flag` must be boolean when provided.",
                        subject=subject,
                    )
                )

            motivators = trait.get("motivators")
            if motivators is not None:
                if not isinstance(motivators, dict):
                    result.json_errors.append(
                        SchemaValidationMessage(
                            source="json",
                            level="error",
                            message="`motivators` must be a mapping with tone keys.",
                            subject=subject,
                        )
                    )
                else:
                    allowed_keys = {"neutral", "gentle", "blunt", "long"}
                    for tone_key, template in motivators.items():
                        if tone_key not in allowed_keys:
                            result.json_errors.append(
                                SchemaValidationMessage(
                                    source="json",
                                    level="error",
                                    message=f"Unsupported motivator tone `{tone_key}`.",
                                    subject=subject,
                                )
                            )
                            continue
                        if template is not None and not isinstance(template, str):
                            result.json_errors.append(
                                SchemaValidationMessage(
                                    source="json",
                                    level="error",
                                    message="Motivator templates must be strings.",
                                    subject=subject,
                                )
                            )

    return result


# ----- Mutations ------------------------------------------------------------------


def upsert_container(schema: SchemaDoc, payload: ContainerRecord) -> None:
    container_id = str(payload.get("id") or "").strip()
    if not container_id:
        raise ValueError("Container id is required for upsert.")
    existing = locate_container(schema, container_id)
    if existing is None:
        schema.setdefault("containers", []).append(copy.deepcopy(payload))
    else:
        existing.update(copy.deepcopy(payload))


def remove_container(schema: SchemaDoc, container_id: str) -> bool:
    containers = schema.get("containers")
    if not isinstance(containers, list):
        return False
    for idx, container in enumerate(containers):
        if str(container.get("id")) == container_id:
            del containers[idx]
            return True
    return False


def upsert_trait(schema: SchemaDoc, container_id: str, payload: TraitRecord) -> None:
    container = locate_container(schema, container_id)
    if container is None:
        raise KeyError(f"Container `{container_id}` not found.")
    traits_obj = container.setdefault("traits", [])
    if not isinstance(traits_obj, list):
        traits_obj = []
        container["traits"] = traits_obj
    trait_id = str(payload.get("id") or "").strip()
    if not trait_id:
        raise ValueError("Trait id is required for upsert.")
    for idx, trait in enumerate(traits_obj):
        if not isinstance(trait, dict):
            continue
        if str(trait.get("id")) == trait_id:
            traits_obj[idx] = copy.deepcopy(payload)
            return
    traits_obj.append(copy.deepcopy(payload))


def remove_trait(schema: SchemaDoc, container_id: str, trait_id: str) -> bool:
    container = locate_container(schema, container_id)
    if container is None:
        return False
    traits = container.get("traits")
    if not isinstance(traits, list):
        return False
    for idx, trait in enumerate(traits):
        if str(trait.get("id")) == trait_id:
            del traits[idx]
            return True
    return False


# ----- Migration preview ----------------------------------------------------------


def impacted_traits(diff: SchemaDiff) -> Dict[str, List[str]]:
    impact: Dict[str, List[str]] = {}
    for mapping in (diff.traits_added, diff.traits_removed, diff.traits_changed):
        for container_id, trait_ids in mapping.items():
            impact.setdefault(container_id, [])
            for trait_id in trait_ids:
                if trait_id not in impact[container_id]:
                    impact[container_id].append(trait_id)
    for container_id in diff.containers_removed:
        impact.setdefault(container_id, [])
    for container_id in diff.containers_added:
        impact.setdefault(container_id, [])
    return impact


def scan_core_impacts(
    repo_root: Path, trait_ids: Sequence[str]
) -> Tuple[int, Dict[str, List[str]]]:
    users_dir = repo_root / "ReDNACoreDemo" / "data" / "storage" / "users"
    if not users_dir.exists():
        return 0, {}

    impacted_users: Dict[str, List[str]] = {}
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        resolved_flat = user_dir / "resolved_flat.json"
        if not resolved_flat.exists():
            continue
        try:
            payload = json.loads(resolved_flat.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        matches: List[str] = []
        for row in rows:
            trait_path = str(row.get("path") or "") if isinstance(row, dict) else ""
            if trait_path in trait_ids:
                matches.append(trait_path)
        if matches:
            impacted_users[user_dir.name] = sorted(set(matches))

    return len(impacted_users), impacted_users


# ----- Simulation helpers ---------------------------------------------------------


def _container_core_mutations(change: str, container_id: str, trait_count: int) -> List[str]:
    if change == "add":
        return [
            f"Create container `{container_id}` in Core trait registry.",
            f"Register {trait_count} trait definition(s) under the new container.",
        ]
    if change == "remove":
        return [
            f"Archive container `{container_id}` before removing from Core registry.",
            "Purge container references from analytics caches and previews.",
        ]
    return [
        f"Update container `{container_id}` metadata in Core registry.",
    ]


def _container_backfill(change: str, trait_count: int) -> List[str]:
    if change == "add":
        return [
            "Warm new container during next Core sync; existing users will adopt defaults automatically.",
        ]
    if change == "remove":
        return [
            "Snapshot affected user containers before deletion for potential rollback.",
            "Remove stale trait buckets from storage once archival completes.",
        ]
    return [
        "Notify downstream services (Explorer, AI coaches) of container metadata update.",
    ]


def _container_rollback(change: str, container_id: str) -> List[str]:
    if change == "add":
        return [f"Delete container `{container_id}` from draft and redeploy original schema."]
    if change == "remove":
        return [f"Restore container `{container_id}` from saved backup and re-run validation."]
    return ["Revert metadata fields in draft and re-run Container Studio validation."]


def _trait_core_mutations(
    change: str,
    container_id: str,
    trait_id: str,
    changed_fields: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    if change == "add":
        return [
            f"Insert trait `{trait_id}` into container `{container_id}` manifest.",
            "Propagate new trait metadata to Core schema + analytics indices.",
        ]
    if change == "remove":
        return [
            f"Archive resolved values for trait `{trait_id}` before removal.",
            "Remove trait definition from container manifest and Core registry.",
        ]
    changed_labels = ", ".join(sorted(changed_fields.keys())) if changed_fields else "metadata"
    return [
        f"Update trait `{trait_id}` fields: {changed_labels}.",
        "Refresh Core schema caches and explorer manifests for the updated trait.",
    ]


def _trait_backfill(
    change: str,
    trait: Optional[TraitRecord],
    changed_fields: Optional[Dict[str, Dict[str, Any]]],
) -> List[str]:
    if change == "add":
        if trait and bool(trait.get("computed", False)):
            return [
                "Computed trait — ensure recomputation jobs include the new definition.",
                "No bulk backfill required; values derive on demand.",
            ]
        return [
            "Seed default value across existing users (coverage → unknown).",
            "Queue backfill job to populate analytics aggregates for the new trait.",
        ]
    if change == "remove":
        return [
            "Archive historical values for reporting, then delete trait data from user storage.",
            "Invalidate cached Explorer views referencing the removed trait.",
        ]

    hints: List[str] = []
    changed = set(changed_fields.keys() if changed_fields else [])
    if {"decay", "default_decay"} & changed:
        hints.append("Recalculate decay projections and publish updated expectations.")
    if {"curiosity", "default_curiosity"} & changed:
        hints.append("Re-run curiosity scoring pipelines for the impacted trait.")
    if {"sensitivity", "sensitivity_flag"} & changed:
        hints.append("Notify moderation tooling of sensitivity changes and re-apply guardrails.")
    if "links" in changed:
        hints.append("Rebuild trait link graph for Container Studio + Explorer views.")
    if "computed" in changed:
        hints.append("Validate computation pipeline for the trait and rerun derived metrics.")
    if not hints:
        hints.append("Spot-check recent user records to confirm trait data remains consistent.")
    return hints


def _trait_rollback(change: str, trait_id: str) -> List[str]:
    if change == "add":
        return [f"Remove trait `{trait_id}` from draft schema and discard pending backfills."]
    if change == "remove":
        return [f"Reintroduce trait `{trait_id}` from backup JSON, then re-sync Explorer manifests."]
    return [f"Restore previous trait definition for `{trait_id}` from version control."]


def build_apply_plan(
    repo_root: Path,
    base_schema: SchemaDoc,
    draft_schema: SchemaDoc,
    diff: SchemaDiff,
) -> Dict[str, Any]:
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    summary = {
        "containers": {
            "added": list(diff.containers_added),
            "removed": list(diff.containers_removed),
            "changed": list(diff.containers_changed),
        },
        "traits": {
            "added": {k: list(v) for k, v in diff.traits_added.items()},
            "removed": {k: list(v) for k, v in diff.traits_removed.items()},
            "changed": {k: list(v) for k, v in diff.traits_changed.items()},
        },
    }

    impact_map = impacted_traits(diff)
    trait_ids: List[str] = sorted({tid for traits in impact_map.values() for tid in traits})
    user_count = 0
    impacted_users: Dict[str, List[str]] = {}
    if trait_ids:
        try:
            user_count, impacted_users = scan_core_impacts(repo_root, trait_ids)
        except Exception:
            user_count = 0
            impacted_users = {}

    sample_users: Dict[str, List[str]] = {}
    truncated = False
    if impacted_users:
        for idx, (user_id, traits) in enumerate(sorted(impacted_users.items())):
            if idx >= 5:
                truncated = True
                break
            sample_users[user_id] = traits

    actions: List[Dict[str, Any]] = []

    for container_id in diff.containers_added:
        container = locate_container(draft_schema, container_id) or {}
        traits = list(
            trait.get("id")
            for trait in (container.get("traits") or [])
            if isinstance(trait, dict) and trait.get("id")
        )
        actions.append(
            {
                "scope": "container",
                "container_id": container_id,
                "change": "add",
                "label": container.get("label"),
                "core_mutations": _container_core_mutations("add", container_id, len(traits)),
                "backfill": _container_backfill("add", len(traits)),
                "rollback_hints": _container_rollback("add", container_id),
                "traits": traits,
            }
        )

    for container_id in diff.containers_removed:
        container = locate_container(base_schema, container_id) or {}
        traits = list(
            trait.get("id")
            for trait in (container.get("traits") or [])
            if isinstance(trait, dict) and trait.get("id")
        )
        actions.append(
            {
                "scope": "container",
                "container_id": container_id,
                "change": "remove",
                "label": container.get("label"),
                "core_mutations": _container_core_mutations("remove", container_id, len(traits)),
                "backfill": _container_backfill("remove", len(traits)),
                "rollback_hints": _container_rollback("remove", container_id),
                "traits": traits,
            }
        )

    for container_id in diff.containers_changed:
        base_container = locate_container(base_schema, container_id) or {}
        draft_container = locate_container(draft_schema, container_id) or {}
        detail = _container_diff_details(base_container, draft_container)
        actions.append(
            {
                "scope": "container",
                "container_id": container_id,
                "change": "update",
                "label": draft_container.get("label", base_container.get("label")),
                "changed_fields": detail,
                "core_mutations": _container_core_mutations("update", container_id, len(detail)),
                "backfill": _container_backfill("update", len(detail)),
                "rollback_hints": _container_rollback("update", container_id),
            }
        )

    def _trait_action_payload(
        change: str,
        container_id: str,
        trait_id: str,
        base_trait: Optional[TraitRecord],
        draft_trait: Optional[TraitRecord],
    ) -> Dict[str, Any]:
        changed_fields = {}
        if change == "update" and base_trait and draft_trait:
            changed_fields = _trait_diff_details(base_trait, draft_trait)
        trait_ref = draft_trait if change in {"add", "update"} else base_trait
        return {
            "scope": "trait",
            "container_id": container_id,
            "trait_id": trait_id,
            "change": change,
            "label": (trait_ref or {}).get("label"),
            "changed_fields": changed_fields,
            "core_mutations": _trait_core_mutations(change, container_id, trait_id, changed_fields),
            "backfill": _trait_backfill(change, trait_ref, changed_fields),
            "rollback_hints": _trait_rollback(change, trait_id),
        }

    for container_id, trait_ids in diff.traits_added.items():
        for trait_id in trait_ids:
            draft_trait = locate_trait(locate_container(draft_schema, container_id) or {}, trait_id)
            actions.append(
                _trait_action_payload("add", container_id, trait_id, None, draft_trait)
            )

    for container_id, trait_ids in diff.traits_removed.items():
        for trait_id in trait_ids:
            base_trait = locate_trait(locate_container(base_schema, container_id) or {}, trait_id)
            actions.append(
                _trait_action_payload("remove", container_id, trait_id, base_trait, None)
            )

    for container_id, trait_ids in diff.traits_changed.items():
        for trait_id in trait_ids:
            base_trait = locate_trait(locate_container(base_schema, container_id) or {}, trait_id)
            draft_trait = locate_trait(locate_container(draft_schema, container_id) or {}, trait_id)
            actions.append(
                _trait_action_payload("update", container_id, trait_id, base_trait, draft_trait)
            )

    plan: Dict[str, Any] = {
        "generated_at": timestamp,
        "summary": summary,
        "impacts": {
            "trait_ids": trait_ids,
            "user_count_estimate": user_count,
        },
        "actions": actions,
        "notes": [
            "Preview only — no files were written.",
            "Use Container Studio Apply (phase 3) to execute mutations when ready.",
        ],
    }

    if sample_users:
        plan["impacts"]["sample_users"] = sample_users
        if truncated:
            plan["impacts"]["sample_users_truncated"] = True

    return plan



def resolve_baseline_mean(
    baseline_index: Optional[Dict[str, Any]],
    container_id: str,
    trait_id: str,
) -> Optional[float]:
    if not baseline_index:
        return None

    containers = (
        baseline_index.get("containers") if isinstance(baseline_index.get("containers"), dict) else {}
    )
    container_entry = containers.get(container_id)
    if isinstance(container_entry, dict):
        trait_map = (
            container_entry.get("traits") if isinstance(container_entry.get("traits"), dict) else {}
        )
        trait_entry = trait_map.get(trait_id)
        if isinstance(trait_entry, dict) and trait_entry.get("source") == "explicit":
            mean = trait_entry.get("mean_ucn")
            if isinstance(mean, (int, float)):
                return float(mean)
        if container_entry.get("source") == "explicit":
            mean = container_entry.get("mean_ucn")
            if isinstance(mean, (int, float)):
                return float(mean)
    return None


def _normalized_live_ucn(entry: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("ucn")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(numeric, 100.0)) / 100.0


def _trait_lookup(schema: SchemaDoc) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for container in _iter_containers(schema):
        container_id = str(container.get("id", ""))
        container_label = str(container.get("label", container_id))
        for trait in _iter_traits(container):
            trait_id = str(trait.get("id", ""))
            if not trait_id:
                continue
            lookup[trait_id] = {
                "container_id": container_id,
                "container_label": container_label,
                "trait": trait,
            }
    return lookup


def coverage_dashboard(
    schema: SchemaDoc,
    *,
    baseline_index: Optional[Dict[str, Any]] = None,
    live_resolved: Optional[Dict[str, Any]] = None,
) -> List[CoverageRow]:
    rows: List[CoverageRow] = []
    for container in _iter_containers(schema):
        container_id = str(container.get("id", ""))
        label = str(container.get("label", container_id))
        known = partial = unknown = 0
        for trait in _iter_traits(container):
            trait_id = str(trait.get("id", ""))
            if live_resolved is not None:
                entry = live_resolved.get(trait_id) if isinstance(live_resolved, dict) else None
                score = _normalized_live_ucn(entry)
            else:
                score = resolve_baseline_mean(baseline_index, container_id, trait_id)
                if score is None:
                    score = 0.0
            score = float(score or 0.0)
            if score >= 0.7:
                known += 1
            elif score >= 0.3:
                partial += 1
            else:
                unknown += 1
        rows.append(
            CoverageRow(
                container_id=container_id,
                container_label=label,
                known=known,
                partial=partial,
                unknown=unknown,
            )
        )
    return rows


def curiosity_heatmap(
    schema: SchemaDoc,
    *,
    baseline_index: Optional[Dict[str, Any]] = None,
    live_snapshot: Optional[LiveCuriositySnapshot] = None,
    top_n: int = 10,
) -> List[TraitCuriosity]:
    if live_snapshot and not live_snapshot.error:
        return _live_curiosity_heatmap(schema, live_snapshot, top_n=top_n)

    items: List[TraitCuriosity] = []
    for container in _iter_containers(schema):
        container_id = str(container.get("id", ""))
        for trait in _iter_traits(container):
            trait_id = str(trait.get("id", ""))
            trait_label = str(trait.get("label", trait_id))
            simulated_ucn = resolve_baseline_mean(baseline_index, container_id, trait_id)
            if simulated_ucn is None:
                simulated_ucn = 0.0
            simulated_ucn = max(0.0, min(float(simulated_ucn), 1.0))
            base_curiosity = 1.0 - simulated_ucn
            policy_curiosity = trait.get("default_curiosity")
            if isinstance(policy_curiosity, (int, float)):
                curiosity_value = (float(policy_curiosity) + base_curiosity) / 2.0
            else:
                curiosity_value = base_curiosity
            curiosity_value = max(0.0, min(curiosity_value, 1.0))
            sensitivity_flag = bool(trait.get("sensitivity_flag", False))
            default_decay = str(trait.get("default_decay", "medium"))
            items.append(
                TraitCuriosity(
                    container_id=container_id,
                    trait_id=trait_id,
                    trait_label=trait_label,
                    curiosity=curiosity_value,
                    simulated_ucn=simulated_ucn,
                    sensitivity_flag=sensitivity_flag,
                    default_decay=default_decay,
                )
            )
    items.sort(key=lambda item: item.curiosity, reverse=True)
    return items[:top_n]


def _live_curiosity_heatmap(
    schema: SchemaDoc,
    snapshot: LiveCuriositySnapshot,
    *,
    top_n: int,
) -> List[TraitCuriosity]:
    lookup = _trait_lookup(schema)
    resolved = snapshot.resolved if isinstance(snapshot.resolved, dict) else {}

    entries: List[TraitCuriosity] = []

    def _append(
        trait_id: str,
        curiosity_value: float,
        source_entry: Optional[Mapping[str, Any]],
        row_data: Optional[Mapping[str, Any]] = None,
    ) -> None:
        meta = lookup.get(trait_id)
        if not meta:
            return
        trait = meta.get("trait") if isinstance(meta.get("trait"), Mapping) else {}
        container_id = meta.get("container_id", "")
        trait_label = str(trait.get("label", trait_id))
        decay = str(trait.get("default_decay", trait.get("decay", "medium")))
        sensitivity_flag = str(trait.get("sensitivity", "medium")).lower() == "restricted"
        normalized_ucn = _normalized_live_ucn(source_entry) or 0.0
        weight_val = 1.0
        for candidate in (row_data, source_entry):
            if not isinstance(candidate, Mapping):
                continue
            candidate_weight = _safe_float(candidate.get("weight"))
            if candidate_weight is None:
                candidate_weight = _safe_float(candidate.get("curiosity_weight"))
            if candidate_weight is not None and candidate_weight > 0.0:
                weight_val = float(candidate_weight)
                break
        if weight_val <= 0.0:
            weight_val = 1.0

        data_source = None
        for candidate in (row_data, source_entry):
            if not isinstance(candidate, Mapping):
                continue
            raw_source = candidate.get("source") or candidate.get("curiosity_source")
            if isinstance(raw_source, str) and raw_source.strip():
                data_source = raw_source.strip()
                break

        rr_val = None
        for candidate in (row_data, source_entry):
            if not isinstance(candidate, Mapping):
                continue
            candidate_rr = _safe_float(candidate.get("rr"))
            if candidate_rr is None:
                candidate_rr = _safe_float(candidate.get("curiosity_rr"))
            if candidate_rr is None:
                continue
            if candidate_rr > 1.0:
                candidate_rr = max(0.0, min(candidate_rr, 100.0)) / 100.0
            rr_val = max(0.0, min(candidate_rr, 1.0))
            break

        entries.append(
            TraitCuriosity(
                container_id=container_id,
                trait_id=trait_id,
                trait_label=trait_label,
                curiosity=max(0.0, min(float(curiosity_value), 1.0)),
                simulated_ucn=max(0.0, min(normalized_ucn, 1.0)),
                sensitivity_flag=sensitivity_flag,
                default_decay=decay,
                weight=weight_val,
                data_source=data_source,
                rr=rr_val,
            )
        )

    seen: set[str] = set()
    for row in snapshot.top_traits:
        if not isinstance(row, Mapping):
            continue
        trait_id = str(row.get("trait_id") or row.get("trait") or "").strip()
        if not trait_id or trait_id in seen:
            continue
        seen.add(trait_id)
        curiosity_value = row.get("curiosity")
        try:
            curiosity_float = float(curiosity_value)
        except (TypeError, ValueError):
            curiosity_float = 0.0
        source_entry = resolved.get(trait_id) if isinstance(resolved, dict) else None
        _append(trait_id, curiosity_float, source_entry, row)
        if len(entries) >= top_n:
            break

    if len(entries) < top_n:
        for trait_id, meta in lookup.items():
            if trait_id in seen:
                continue
            source_entry = resolved.get(trait_id) if isinstance(resolved, dict) else None
            entry_curiosity = None
            if isinstance(source_entry, Mapping):
                try:
                    entry_curiosity = float(source_entry.get("curiosity"))
                except (TypeError, ValueError):
                    entry_curiosity = None
            if entry_curiosity is None:
                continue
            _append(trait_id, entry_curiosity, source_entry)
            if len(entries) >= top_n:
                break

    entries.sort(key=lambda item: item.curiosity, reverse=True)
    return entries[:top_n]


@dataclass(slots=True)
class LiveCuriositySnapshot:
    user_id: str
    resolved: Dict[str, Any]
    top_traits: List[Dict[str, Any]]
    fetched_at: str
    error: Optional[str] = None
    curiosity_enabled: Optional[bool] = None
    error_detail: Optional[str] = None
    source_counts: Optional[Dict[str, int]] = None


@dataclass(slots=True)
class FeedbackAggregate:
    path: str
    container_id: Optional[str]
    trait_id: Optional[str]
    helpful: int
    not_helpful: int
    score: float
    last_ts: Optional[str]


def _lookup_resolved_entry(resolved_payload: Mapping[str, Any], trait_id: str) -> Optional[Mapping[str, Any]]:
    if not isinstance(resolved_payload, Mapping):
        return None
    direct = resolved_payload.get(trait_id)
    if isinstance(direct, Mapping):
        return direct
    traits_node = resolved_payload.get("traits")
    if isinstance(traits_node, Mapping):
        entry = traits_node.get(trait_id)
        if isinstance(entry, Mapping):
            return entry
    for value in resolved_payload.values():
        if isinstance(value, Mapping) and trait_id in value and isinstance(value[trait_id], Mapping):
            return value[trait_id]
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric


def fetch_feedback_aggregates(
    user_id: Optional[str] = None,
    *,
    write_protect: bool,
) -> Dict[str, FeedbackAggregate]:
    """Return feedback aggregates keyed by trait path.

    When ``user_id`` is provided the results are filtered to that user; otherwise
    the aggregate spans the entire feedback log.
    """

    raw = nudge_store.load_feedback_aggregates(user_id=user_id, write_protect=write_protect)
    aggregates: Dict[str, FeedbackAggregate] = {}
    for path, payload in raw.items():
        if not isinstance(payload, Mapping):
            continue
        helpful = int(payload.get("helpful", 0) or 0)
        not_helpful = int(payload.get("not_helpful", 0) or 0)
        try:
            score = float(payload.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        aggregates[path] = FeedbackAggregate(
            path=path,
            container_id=str(payload.get("container") or "") or None,
            trait_id=str(payload.get("trait_id") or "") or None,
            helpful=helpful,
            not_helpful=not_helpful,
            score=score,
            last_ts=str(payload.get("last_ts") or "") or None,
        )
    return aggregates


def compute_feedback_multiplier(
    base_curiosity: Any,
    aggregate: Optional[FeedbackAggregate],
    *,
    feedback_k: float = 0.2,
) -> Tuple[float, float]:
    """Return ``(multiplier, weighted_curiosity)`` for planning purposes.

    The multiplier is clamped to the ``[0.5, 1.5]`` window to prevent extreme
    swings while still reflecting the overall sentiment score.
    """

    curiosity_value = _safe_float(base_curiosity) or 0.0
    score = aggregate.score if aggregate else 0.0
    multiplier = 1.0 + (feedback_k * score)
    multiplier = max(0.5, min(multiplier, 1.5))
    return multiplier, curiosity_value * multiplier


def fetch_live_curiosity_rows(
    user_id: str,
    *,
    top_n: int,
    timeout: float,
    core_base: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str], LiveCuriositySnapshot]:
    curiosity_status, health_error = core_curiosity_status(ttl=5.0, timeout=timeout)
    if curiosity_status is False:
        fetched_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        snapshot = LiveCuriositySnapshot(
            user_id=user_id,
            resolved={},
            top_traits=[],
            fetched_at=fetched_at,
            error="Curiosity disabled via Core /health.",
            curiosity_enabled=False,
            error_detail="Curiosity disabled via Core /health.",
        )
        return [], "Curiosity disabled via Core /health.", snapshot

    snapshot = load_live_curiosity_snapshot(
        user_id,
        core_base=core_base,
        limit=max(top_n, 25),
        timeout=timeout,
    )
    snapshot.curiosity_enabled = curiosity_status if curiosity_status is not None else snapshot.curiosity_enabled
    rows: List[Dict[str, Any]] = []
    error = snapshot.error
    if error and curiosity_status is None and health_error:
        error = f"Core health unreachable: {health_error}"

    if not error:
        for row in snapshot.top_traits[:top_n]:
            if not isinstance(row, Mapping):
                continue
            container_id = str(row.get("container_id") or row.get("container") or "").strip()
            trait_id = str(row.get("trait_id") or row.get("trait") or "").strip()
            if not container_id or not trait_id:
                continue
            curiosity = _safe_float(row.get("curiosity")) or 0.0
            curiosity = max(0.0, min(curiosity, 1.0))
            ucn_value: Any = row.get("ucn")
            normalized_ucn = _safe_float(ucn_value)
            if normalized_ucn is not None and normalized_ucn > 1.0:
                normalized_ucn = max(0.0, min(normalized_ucn, 100.0)) / 100.0
            rows.append(
                {
                    "container_id": container_id,
                    "trait_id": trait_id,
                    "curiosity": curiosity,
                    "ucn": normalized_ucn,
                    "resolved_value": row.get("resolved_value"),
                    "source": "live",
                }
            )

    return rows, error, snapshot


def simulated_curiosity_rows(schema_doc: SchemaDoc, *, top_n: int = 5) -> List[Dict[str, Any]]:
    items = curiosity_heatmap(schema_doc, top_n=top_n)
    rows: List[Dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "container_id": getattr(item, "container_id", ""),
                "trait_id": getattr(item, "trait_id", ""),
                "curiosity": getattr(item, "curiosity", 0.0),
                "ucn": getattr(item, "simulated_ucn", None),
                "resolved_value": None,
                "source": "simulated",
            }
        )
    return rows
