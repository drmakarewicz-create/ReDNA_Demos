"""Diagnostics snapshot utilities for Dev Explorer."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_repo_root
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_repo_root  # type: ignore

import csv
import hashlib
import io
import json
import os
import platform
import socket
import subprocess
import zipfile
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests

from ExplorerDev import registry_helpers, rr_baseline_utils, schema_utils
from ExplorerDev.scheduler_utils import SYSTEM_PREFS_PATH, load_scheduler_prefs
from ExplorerDev.write_utils import WriteProtectContext, write_guard


REPO_ROOT = ensure_repo_root()
SNAPSHOT_DIR = REPO_ROOT / "data" / "dev_snapshots"
DIAG_LOG_PATH = REPO_ROOT / "data" / "dev_logs" / "diagnostics.log"
SCHED_LOG_PATH = REPO_ROOT / "data" / "dev_logs" / "scheduler.log"
MAX_LOG_LINES = 1000
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
_IN_MEMORY_CACHE: Dict[str, bytes] = {}
_MAX_CACHE_ITEMS = 6
PROJECT_STATUS_PREFIX = "project_status"
PROJECT_STATUS_DIR = REPO_ROOT / "data" / "dev_logs"

PORT_TARGETS = {
    "Control Panel+": ("127.0.0.1", 8503),
    "Dev Explorer": ("127.0.0.1", 8520),
    "Main Explorer": ("127.0.0.1", 8502),
    "UCNRR": ("127.0.0.1", 8011),
    "Core": ("127.0.0.1", 8015),
}

FLAG_SPECS: Dict[str, Dict[str, Any]] = {
    "WRITE_PROTECT": {"type": "bool", "default": True},
    "DEV_EXPLORER_ENABLED": {"type": "bool", "default": True},
    "DEMO_BASELINES_ENABLED": {"type": "bool", "default": False},
    "CORE_CURIOSITY_ENABLED": {"type": "bool", "default": False},
    "HC_SEND_ENABLED": {"type": "bool", "default": False},
    "HC_OPS_ENABLED": {"type": "bool", "default": False},
    "HC_AB_ENABLED": {"type": "bool", "default": False},
    "NUDGE_INBOX_ENABLED": {"type": "bool", "default": False},
    "FEEDBACK_ENABLED": {"type": "bool", "default": True},
    "AUDIT_VIEWER_ENABLED": {"type": "bool", "default": True},
    "NUDGE_ACTIONS_ENABLED": {"type": "bool", "default": False},
    "NUDGE_DELIVER_TO_CHAT": {"type": "bool", "default": False},
    "NUDGE_RATE_LIMIT_PER_MIN": {"type": "int", "default": 20},
    "NUDGE_TTL_MIN": {"type": "int", "default": 1440},
    "NUDGE_SNOOZE_MIN": {"type": "int", "default": 120},
    "EXPLORER_UI_COMPACT": {"type": "bool", "default": False},
    "EXPLORER_UI_REDUCED_MOTION": {"type": "bool", "default": False},
    "DEV_LOOPTEST_USER_ID": {"type": "str", "default": "devexp_test"},
    "ROUNDTRIP_TRACING_ENABLED": {"type": "bool", "default": True},
    "ROUNDTRIP_RETRY_LIMIT": {"type": "int", "default": 3},
    "ROUNDTRIP_BACKOFF_MS": {"type": "int", "default": 900},
    "ROUNDTRIP_CIRCUIT_BREAK_MS": {"type": "int", "default": 120000},
    "ORS_AUTO_SNAPSHOT_ON_FAIL": {"type": "bool", "default": True},
}

MAJOR_MODULES_INFO: Dict[str, Dict[str, Any]] = {
    "ExplorerDev/explorer_dev.py": {
        "purpose": "Streamlit Developer Explorer shell (coach workshop, diagnostics, RR lab, CReDNA).",
        "functions": [
            "render_status_strip",
            "_render_head_coach_ops_card",
            "_render_ingest_harness",
            "render_container_studio",
            "render_credna_studio",
        ],
    },
    "ExplorerDev/diag_utils.py": {
        "purpose": "Loop test + ingest harness utilities, service console persistence and ORS tracing helpers.",
        "functions": [
            "load_service_settings",
            "run_loop_test",
            "run_ingest_round_trip",
            "run_prompt_source_checks",
        ],
    },
    "ExplorerDev/ors_console.py": {
        "purpose": "Observability console rendering: service pings, log tailer, trace explorer.",
        "functions": [
            "render_service_console",
            "render_log_tailer",
            "render_trace_explorer",
            "build_curl_snippet",
        ],
    },
    "ExplorerDev/container_studio.py": {
        "purpose": "Trait schema editor with AI assists and diff/validation utilities.",
        "functions": [
            "render_container_studio",
            "_focus_trait_editor",
            "validate_schema",
        ],
    },
    "ExplorerDev/rr_baseline_utils.py": {
        "purpose": "RR demo baselines loader/validator and write-guarded persistence helpers.",
        "functions": [
            "load_demo_baselines",
            "validate_demo_baselines",
            "save_demo_baselines",
            "resolve_baselines",
        ],
    },
    "ExplorerDev/credna/credna_store.py": {
        "purpose": "CReDNA registry session store, undo stack, and audit logging.",
        "functions": [
            "load_registry",
            "set_registry",
            "save_registry",
            "revert_last",
        ],
    },
    "ExplorerDev/credna/credna_ops.py": {
        "purpose": "Coach trait graph utilities, coverage snapshots, persona→coach mapping.",
        "functions": [
            "resolve_coach_for_persona",
            "find_trait_template",
            "build_coach_snapshot",
        ],
    },
    "ExplorerDev/audit_utils.py": {
        "purpose": "Audit log helpers (JSONL tail loading, encryption stub metadata, rollback).",
        "functions": [
            "load_jsonl",
            "encrypt_log",
            "rollback_last_change",
        ],
    },
    "ExplorerDev/credna/credna_ui.py": {
        "purpose": "Streamlit UI for CReDNA Studio (graph, coverage, live snapshot, imports).",
        "functions": ["render_credna_studio"],
    },
    "ExplorerDev/schema_utils.py": {
        "purpose": "Shared schema + flag helpers (trait diffs, base URLs, curiosity fetch).",
        "functions": [
            "get_flag_bool",
            "diff_schemas",
            "fetch_core_resolved_flat",
        ],
    },
    "ExplorerFinal/explorer_final.py": {
        "purpose": "Main end-user Explorer app with sticky header, inbox, draft chat, API bridges.",
        "functions": [
            "render_nudge_inbox",
            "render_draft_chat",
            "ucnrr_ingest_text",
            "core_resolved",
        ],
    },
    "ExplorerFinal/ui/nudge_inbox.py": {
        "purpose": "Inbox UI with batch actions, TTL/snooze management, cohort filters.",
        "functions": [
            "render_nudge_inbox",
            "dismiss_expired",
        ],
    },
    "ExplorerFinal/core/nudge_store.py": {
        "purpose": "Nudge persistence layer (enqueue, accept/dismiss, ops scheduling, draft chat).",
        "functions": [
            "enqueue",
            "accept",
            "snooze",
            "load_ops",
        ],
    },
    "ExplorerFinal/ui/components.py": {
        "purpose": "Shared Explorer UI components (sticky header, chips, CSS, shortcuts).",
        "functions": [
            "render_sticky_header",
            "render_css_once",
            "render_chips",
        ],
    },
    "ExplorerDev/snapshot_utils.py": {
        "purpose": "Diagnostics snapshot packaging, RR baseline exports, service health checks.",
        "functions": [
            "collect_snapshot",
            "fetch_health",
            "effective_rr_csv",
        ],
    },
    "UCN_RR_Demo/ucnrr_app.py": {
        "purpose": "UCN/RR FastAPI service (ingest, forward to Core, curiosity retries, tracing).",
        "functions": [
            "estimate_ucn_for_trait",
            "app.get('/health')",
            "app.post('/ingest_text')",
            "_circuit_record_failure",
        ],
    },
    "ReDNACoreDemo/core/api.py": {
        "purpose": "Core FastAPI endpoints (ingest bundle, recompute, curiosity, resolved snapshots).",
        "functions": [
            "build_app",
            "app.get('/health')",
            "app.post('/ingest_bundle')",
            "app.get('/curiosity/{user_id}')",
        ],
    },
    "control_panel_plus.py": {
        "purpose": "Control Panel+ Streamlit app for managing ports, env flags, and service launches.",
        "functions": [
            "_load_env_flags",
            "_apply_env_flags",
            "_render_env_flags_panel",
        ],
    },
}

DEFAULT_OPTIONS = {
    "status": True,
    "prefs": True,
    "rr_baselines": True,
    "schema": True,
    "personas": True,
    "logs": True,
    "health": True,
}

DEV_TRUE_SET = {"1", "true", "yes", "on"}


def _utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if len(stripped) <= 6:
        return "*" * len(stripped)
    tail = stripped[-4:]
    return f"{'*' * (len(stripped) - 4)}{tail}"


def redact_env(env: Mapping[str, Any]) -> Dict[str, str]:
    masked: Dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str):
            continue
        if not key.startswith("DEV_") and not key.startswith("LLM_"):
            continue
        str_value = str(value) if value is not None else ""
        masked[key] = _mask_secret(str_value)
    return masked


def _cache_snapshot(snapshot_id: str, data: bytes) -> None:
    _IN_MEMORY_CACHE[snapshot_id] = data
    while len(_IN_MEMORY_CACHE) > _MAX_CACHE_ITEMS:
        oldest = next(iter(_IN_MEMORY_CACHE))
        if oldest == snapshot_id:
            break
        _IN_MEMORY_CACHE.pop(oldest, None)


def tail(path: Path, n: int = MAX_LOG_LINES) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            dq: deque[str] = deque(maxlen=n)
            for line in handle:
                dq.append(line.rstrip("\n"))
    except Exception:
        return ""
    return "\n".join(dq)


def _effective_rr_rows(repo_root: Path) -> List[List[str]]:
    data = rr_baseline_utils.load_demo_baselines(repo_root)
    resolved = data.get("resolved", {})
    defaults = resolved.get("defaults", {}) if isinstance(resolved.get("defaults"), dict) else {}
    rows: List[List[str]] = []

    def _format_row(scope: str, container: str, trait: str, payload: Mapping[str, Any]) -> List[str]:
        return [
            scope,
            container,
            trait,
            f"{float(payload.get('mean_ucn', 0.0)):.4f}",
            f"{float(payload.get('std_ucn', 0.0)):.4f}",
            str(int(payload.get("sample_size", 0) or 0)),
            str(payload.get("source") or "unknown"),
        ]

    rows.append(_format_row("default", "", "", defaults))

    containers = resolved.get("containers", {}) if isinstance(resolved.get("containers"), dict) else {}
    for container_id, payload in containers.items():
        if not isinstance(payload, Mapping):
            continue
        rows.append(_format_row("container", container_id, "", payload))
        traits = payload.get("traits", {}) if isinstance(payload.get("traits"), dict) else {}
        for trait_id, trait_payload in traits.items():
            if not isinstance(trait_payload, Mapping):
                continue
            rows.append(_format_row("trait", container_id, trait_id, trait_payload))

    return rows


def effective_rr_csv(repo_root: Path) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["scope", "container", "trait", "mean_ucn", "std_ucn", "sample_size", "source"])
    for row in _effective_rr_rows(repo_root):
        writer.writerow(row)
    return buffer.getvalue()


def schema_diff(repo_root: Path) -> Dict[str, Any]:
    base: Dict[str, Any]
    draft: Optional[Dict[str, Any]] = None
    warnings: List[str] = []

    try:
        base = schema_utils.load_schema(repo_root)
    except Exception as exc:
        return {
            "warnings": [f"Unable to load live schema: {exc}"],
            "diff": [],
            "counts": {},
        }

    draft_path = schema_utils.draft_path(repo_root)
    if draft_path.exists():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"Unable to read draft schema: {exc}")
    else:
        warnings.append("Draft schema not present.")

    if not isinstance(draft, dict):
        return {
            "warnings": warnings,
            "diff": [],
            "counts": {},
        }

    diff_result = schema_utils.diff_schemas(base, draft)
    summary = diff_result.summary_rows()
    counts = {
        "containers_added": len(diff_result.containers_added),
        "containers_removed": len(diff_result.containers_removed),
        "containers_changed": len(diff_result.containers_changed),
        "traits_added": sum(len(v) for v in diff_result.traits_added.values()),
        "traits_removed": sum(len(v) for v in diff_result.traits_removed.values()),
        "traits_changed": sum(len(v) for v in diff_result.traits_changed.values()),
    }
    return {
        "warnings": warnings,
        "diff": summary,
        "counts": counts,
    }


def _health_payload(url: Optional[str], *, timeout: float = 0.75) -> Dict[str, Any]:
    if not url:
        return {"configured": False, "error": "not configured"}
    target = url.rstrip("/")
    try:
        response = requests.get(f"{target}/health", timeout=timeout)
        payload = {
            "configured": True,
            "status": response.status_code,
        }
        try:
            payload["body"] = response.json()
        except ValueError:
            payload["body"] = response.text[:2048]
        return payload
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        return {
            "configured": True,
            "error": str(exc),
        }


def fetch_health(timeout: float = 0.75) -> Dict[str, Any]:
    uc_base = schema_utils.ucnrr_base_url()
    core_base = schema_utils.core_base_url()
    llm_base = schema_utils.llm_base_url()
    return {
        "ucnrr": _health_payload(uc_base, timeout=timeout),
        "core": _health_payload(core_base, timeout=timeout),
        "llm": _health_payload(llm_base, timeout=timeout),
    }


def _status_payload(context: WriteProtectContext) -> Dict[str, Any]:
    enabled_raw = os.getenv("DEV_EXPLORER_ENABLED")
    enabled = True if enabled_raw is None else enabled_raw.strip().lower() in DEV_TRUE_SET

    prefs = load_scheduler_prefs()
    cadence = "Off"
    scheduler_cfg = prefs.get("holistic_scheduler") if isinstance(prefs, dict) else {}
    if isinstance(scheduler_cfg, dict):
        cadence = str(scheduler_cfg.get("cadence") or "off")

    demo_enabled = rr_baseline_utils.is_demo_enabled(REPO_ROOT)
    baseline_path = rr_baseline_utils.current_baselines_path(REPO_ROOT)

    return {
        "DEV_EXPLORER_ENABLED": enabled,
        "WRITE_PROTECT": bool(getattr(context, "write_protect", False)),
        "DEMO_BASELINES": demo_enabled,
        "RR_BASELINES_MODE": "demo" if demo_enabled else "live",
        "RR_BASELINES_PATH": str(baseline_path),
        "scheduler_cadence": cadence,
        "timestamp": _iso_now(),
    }


def _persona_import_details(persona_imports: Sequence[str]) -> Dict[str, Any]:
    modules = registry_helpers.discover_persona_modules(persona_imports)
    registry_helpers.ensure_relationship_coach_contract(modules)
    module_rows = [module.to_dict() for module in modules]
    return {
        "modules": module_rows,
    }


def _persona_registry_snapshot() -> Dict[str, Any]:
    try:
        result = registry_helpers.load_persona_registry(mode="warn")
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "items": result.items,
        "errors": result.errors,
        "imported": result.imported,
        "failures": result.failures,
        "total": result.total,
        "version": result.version,
        "generated_at": result.generated_at,
        "validation_mode": result.validation_mode,
    }


def _schema_artifacts(repo_root: Path) -> Dict[str, Optional[str]]:
    live_path = schema_utils.schema_path(repo_root)
    draft_path = schema_utils.draft_path(repo_root)
    artifacts: Dict[str, Optional[str]] = {
        "trait_schema.yaml": None,
        "trait_schema.WIP.json": None,
    }

    if live_path.exists():
        artifacts["trait_schema.yaml"] = live_path.read_text(encoding="utf-8")
    if draft_path.exists():
        artifacts["trait_schema.WIP.json"] = draft_path.read_text(encoding="utf-8")
    return artifacts


def _rr_baseline_artifacts(repo_root: Path) -> Dict[str, Optional[str]]:
    data = rr_baseline_utils.load_demo_baselines(repo_root)
    demo_path = rr_baseline_utils.demo_baselines_path(repo_root)

    demo_yaml: Optional[str] = None
    if demo_path.exists():
        try:
            demo_yaml = demo_path.read_text(encoding="utf-8")
        except Exception:
            demo_yaml = None

    return {
        "effective.csv": effective_rr_csv(repo_root),
        "demo_raw.yaml": demo_yaml,
    }


def _persona_import_strings(persona_imports: Sequence[Tuple[str, str]]) -> List[str]:
    return [path for _, path in persona_imports]


def _add_entry(
    entries: List[Tuple[str, bytes]],
    summary: List[Dict[str, Any]],
    warnings: List[str],
    zip_path: str,
    content: Optional[str],
    *,
    include_large: bool,
) -> None:
    if content is None:
        return
    data = content.encode("utf-8")
    if not include_large and len(data) > MAX_FILE_BYTES:
        warnings.append(f"Skipped {zip_path} (> {MAX_FILE_BYTES} bytes). Enable large files to include.")
        return
    entries.append((zip_path, data))
    summary.append({"path": zip_path, "size": len(data)})


def collect_snapshot(
    context: WriteProtectContext,
    *,
    in_memory: bool,
    options: Optional[Mapping[str, bool]] = None,
    include_large: bool = False,
    persona_imports: Optional[Sequence[Tuple[str, str]]] = None,
    note: Optional[str] = None,
    extra_meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        opts: Dict[str, bool] = {**DEFAULT_OPTIONS}
        if options:
            opts.update({k: bool(v) for k, v in options.items()})

        timestamp = _utc_timestamp()
        snapshot_id = timestamp
        root = f"snapshot_{timestamp}"
        entries: List[Tuple[str, bytes]] = []
        summary: List[Dict[str, Any]] = []
        warnings: List[str] = []

        status_payload = _status_payload(context)
        if opts.get("status"):
            status_bytes = json.dumps(status_payload, indent=2).encode("utf-8")
            entries.append((f"{root}/status.json", status_bytes))
            summary.append({"path": f"{root}/status.json", "size": len(status_bytes)})

            env_payload = redact_env(os.environ)
            env_bytes = json.dumps(env_payload, indent=2).encode("utf-8")
            entries.append((f"{root}/env_redacted.json", env_bytes))
            summary.append({"path": f"{root}/env_redacted.json", "size": len(env_bytes)})

        if opts.get("prefs") and SYSTEM_PREFS_PATH.exists():
            try:
                prefs_text = SYSTEM_PREFS_PATH.read_text(encoding="utf-8")
                _add_entry(
                    entries,
                    summary,
                    warnings,
                    f"{root}/prefs/dev_system_prefs.json",
                    prefs_text,
                    include_large=include_large,
                )
            except Exception as exc:
                warnings.append(f"Unable to read dev_system_prefs.json: {exc}")

        if opts.get("rr_baselines"):
            rr_artifacts = _rr_baseline_artifacts(REPO_ROOT)
            for name, text in rr_artifacts.items():
                _add_entry(
                    entries,
                    summary,
                    warnings,
                    f"{root}/rr_baselines/{name}",
                    text,
                    include_large=include_large,
                )

        schema_summary = None
        if opts.get("schema"):
            schema_artifacts = _schema_artifacts(REPO_ROOT)
            for name, text in schema_artifacts.items():
                _add_entry(
                    entries,
                    summary,
                    warnings,
                    f"{root}/schema/{name}",
                    text,
                    include_large=include_large,
                )
            diff_payload = schema_diff(REPO_ROOT)
            schema_summary = diff_payload
            diff_bytes = json.dumps(diff_payload, indent=2).encode("utf-8")
            entries.append((f"{root}/schema/diff.json", diff_bytes))
            summary.append({"path": f"{root}/schema/diff.json", "size": len(diff_bytes)})

        if opts.get("personas"):
            import_paths = _persona_import_strings(persona_imports or [])
            persona_details = _persona_import_details(import_paths)
            registry_snapshot = _persona_registry_snapshot()
            import_bytes = json.dumps(persona_details, indent=2).encode("utf-8")
            entries.append((f"{root}/personas/import_details.json", import_bytes))
            summary.append({"path": f"{root}/personas/import_details.json", "size": len(import_bytes)})
            registry_bytes = json.dumps(registry_snapshot, indent=2).encode("utf-8")
            entries.append((f"{root}/personas/registry_snapshot.json", registry_bytes))
            summary.append({"path": f"{root}/personas/registry_snapshot.json", "size": len(registry_bytes)})

        if opts.get("logs"):
            diag_tail = tail(DIAG_LOG_PATH, MAX_LOG_LINES)
            if diag_tail:
                _add_entry(
                    entries,
                    summary,
                    warnings,
                    f"{root}/logs/diagnostics_tail.log",
                    diag_tail,
                    include_large=include_large,
                )
            else:
                warnings.append("Diagnostics log unavailable or empty.")

            sched_tail = tail(SCHED_LOG_PATH, MAX_LOG_LINES)
            if sched_tail:
                _add_entry(
                    entries,
                    summary,
                    warnings,
                    f"{root}/logs/scheduler_tail.log",
                    sched_tail,
                    include_large=include_large,
                )
            else:
                warnings.append("Scheduler log unavailable or empty.")

        if opts.get("health"):
            health_payload = fetch_health()
            health_bytes = json.dumps(health_payload, indent=2).encode("utf-8")
            entries.append((f"{root}/health/services.json", health_bytes))
            summary.append({"path": f"{root}/health/services.json", "size": len(health_bytes)})

        files_for_meta = list(summary)
        write_protect_flag = bool(getattr(context, "write_protect", False))
        final_in_memory = bool(in_memory or write_protect_flag)
        meta = {
            "created_at": _iso_now(),
            "timestamp": timestamp,
            "snapshot_id": snapshot_id,
            "storage": "memory" if final_in_memory else "disk",
            "write_protect": write_protect_flag,
            "note": (note or "").strip(),
            "options": opts,
            "include_large": include_large,
            "file_count": len(entries) + 1,
            "warnings": warnings,
            "schema_diff": schema_summary or {},
            "files": files_for_meta,
        }

        if extra_meta:
            for key, value in extra_meta.items():
                meta[key] = value

        meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
        entries.append((f"{root}/meta.json", meta_bytes))
        summary.append({"path": f"{root}/meta.json", "size": len(meta_bytes)})

        total_size = sum(len(data) for _, data in entries)

        zip_bytes: Optional[bytes] = None
        disk_path: Optional[Path] = None

        if final_in_memory:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for zip_path, data in entries:
                    zf.writestr(zip_path, data)
            zip_bytes = zip_buffer.getvalue()
        else:
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            zip_name = f"devexp_snapshot_{snapshot_id}.zip"
            disk_path = SNAPSHOT_DIR / zip_name
            write_guard(context, action="write diagnostics snapshot")
            with disk_path.open("wb") as fh:
                with zipfile.ZipFile(fh, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for zip_path, data in entries:
                        zf.writestr(zip_path, data)
            try:
                zip_bytes = disk_path.read_bytes()
            except Exception:
                zip_bytes = None

        if zip_bytes is not None:
            _cache_snapshot(snapshot_id, zip_bytes)

        computed_size = (
            len(zip_bytes)
            if zip_bytes is not None
            else (disk_path.stat().st_size if disk_path else total_size)
        )

        result = {
            "ok": True,
            "snapshot_id": snapshot_id,
            "zip_bytes": zip_bytes,
            "size": computed_size,
            "path": str(disk_path) if disk_path else None,
            "note": (note or "").strip(),
            "meta": meta,
            "summary": {
                "files": summary,
                "warnings": warnings,
            },
        }
        return result
    except Exception as exc:  # pragma: no cover - defensive catch
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _snapshot_filename(snapshot_id: str) -> str:
    return f"devexp_snapshot_{snapshot_id}.zip"


def _snapshot_path(snapshot_id: str) -> Path:
    return SNAPSHOT_DIR / _snapshot_filename(snapshot_id)


def _meta_zip_path(snapshot_id: str) -> str:
    return f"snapshot_{snapshot_id}/meta.json"


def get_snapshot_bytes(snapshot_id: str) -> Optional[bytes]:
    if snapshot_id in _IN_MEMORY_CACHE:
        return _IN_MEMORY_CACHE[snapshot_id]
    path = _snapshot_path(snapshot_id)
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None
    _cache_snapshot(snapshot_id, data)
    return data


def _load_meta_from_zipdata(snapshot_id: str, data: bytes) -> Optional[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            with zf.open(_meta_zip_path(snapshot_id)) as handle:
                return json.load(handle)
    except Exception:
        return None


def _load_meta_from_path(snapshot_id: str, path: Path) -> Optional[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            with zf.open(_meta_zip_path(snapshot_id)) as handle:
                return json.load(handle)
    except Exception:
        return None


def get_snapshot_meta(snapshot_id: str) -> Optional[Dict[str, Any]]:
    data = get_snapshot_bytes(snapshot_id)
    if data is not None:
        meta = _load_meta_from_zipdata(snapshot_id, data)
        if meta is not None:
            return meta
    path = _snapshot_path(snapshot_id)
    if not path.exists():
        return None
    return _load_meta_from_path(snapshot_id, path)


def list_snapshots(include_memory: bool = True) -> List[Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}

    def _ensure_row(snapshot_id: str) -> Dict[str, Any]:
        if snapshot_id not in rows:
            rows[snapshot_id] = {
                "id": snapshot_id,
                "created_at": "",
                "created_ts": 0.0,
                "size": 0,
                "note": "",
                "files": 0,
                "path": None,
                "source": set(),
            }
        return rows[snapshot_id]

    if include_memory:
        for snapshot_id, data in _IN_MEMORY_CACHE.items():
            meta = _load_meta_from_zipdata(snapshot_id, data)
            row = _ensure_row(snapshot_id)
            row["source"].add("memory")
            size = len(data)
            row["size"] = max(row["size"], size)
            if meta:
                created_at = meta.get("created_at") or meta.get("timestamp")
                if created_at:
                    row["created_at"] = created_at
                row["note"] = meta.get("note", row.get("note", ""))
                files = meta.get("file_count") or len(meta.get("files", [])) or row.get("files", 0)
                row["files"] = max(row.get("files", 0), int(files))

    if SNAPSHOT_DIR.exists():
        for path in SNAPSHOT_DIR.glob("devexp_snapshot_*.zip"):
            snapshot_id = path.stem.replace("devexp_snapshot_", "")
            row = _ensure_row(snapshot_id)
            row["source"].add("disk")
            row["path"] = str(path)
            try:
                size = path.stat().st_size
                row["size"] = max(row.get("size", 0), size)
                mtime = path.stat().st_mtime
                row["created_ts"] = max(row.get("created_ts", 0.0), mtime)
            except Exception:
                pass
            meta = _load_meta_from_path(snapshot_id, path)
            if meta:
                created_at = meta.get("created_at") or meta.get("timestamp")
                if created_at:
                    row["created_at"] = created_at
                files = meta.get("file_count") or len(meta.get("files", []))
                if files:
                    row["files"] = max(row.get("files", 0), int(files))
                note_val = meta.get("note")
                if note_val:
                    row["note"] = note_val

    results: List[Dict[str, Any]] = []
    for snapshot_id, row in rows.items():
        created_at = row.get("created_at")
        created_ts = row.get("created_ts", 0.0)
        if not created_at and created_ts:
            created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
        row_output = {
            "id": snapshot_id,
            "created_at": created_at or "",
            "size": row.get("size", 0),
            "note": row.get("note", ""),
            "files": row.get("files", 0),
            "path": row.get("path"),
            "source": ",".join(sorted(row.get("source", []))) or ("memory" if snapshot_id in _IN_MEMORY_CACHE else ""),
        }
        results.append(row_output)

    def _sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
        created = item.get("created_at") or ""
        try:
            dt = created
            if created.endswith("Z"):
                dt = created[:-1] + "+00:00"
            ts = datetime.fromisoformat(dt).timestamp()
        except Exception:
            ts = 0.0
        return (int(ts), item.get("id", ""))

    results.sort(key=_sort_key, reverse=True)
    return results


def delete_snapshot(snapshot_id: str, context: WriteProtectContext) -> bool:
    removed = False
    if snapshot_id in _IN_MEMORY_CACHE:
        _IN_MEMORY_CACHE.pop(snapshot_id, None)
        removed = True

    path = _snapshot_path(snapshot_id)
    if path.exists():
        if getattr(context, "write_protect", False):
            raise PermissionError("Write-protect ON — cannot delete snapshots.")
        write_guard(context, action="delete snapshot")
        try:
            path.unlink()
            removed = True
        except Exception as exc:
            raise RuntimeError(f"Unable to delete snapshot {snapshot_id}: {exc}") from exc
    return removed


def expire_snapshots(days: int, context: WriteProtectContext) -> List[str]:
    if days <= 0:
        return []
    if getattr(context, "write_protect", False):
        raise PermissionError("Write-protect ON — cannot expire snapshots.")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed: List[str] = []
    if not SNAPSHOT_DIR.exists():
        return removed
    for path in SNAPSHOT_DIR.glob("devexp_snapshot_*.zip"):
        snapshot_id = path.stem.replace("devexp_snapshot_", "")
        created_at = None
        meta = _load_meta_from_path(snapshot_id, path)
        if meta and meta.get("created_at"):
            created_str = meta["created_at"]
            if created_str.endswith("Z"):
                created_str = created_str[:-1] + "+00:00"
            try:
                created_at = datetime.fromisoformat(created_str)
            except Exception:
                created_at = None
        if created_at is None:
            try:
                created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except Exception:
                created_at = None
        if created_at and created_at < cutoff:
            delete_snapshot(snapshot_id, context)
            removed.append(snapshot_id)
    return removed


def trim_snapshots(max_keep: int, context: WriteProtectContext) -> List[str]:
    if max_keep < 0:
        return []
    if getattr(context, "write_protect", False):
        raise PermissionError("Write-protect ON — cannot trim snapshots.")
    if not SNAPSHOT_DIR.exists():
        return []
    files = sorted(SNAPSHOT_DIR.glob("devexp_snapshot_*.zip"), key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    removed: List[str] = []
    for index, path in enumerate(files):
        if index < max_keep:
            continue
        snapshot_id = path.stem.replace("devexp_snapshot_", "")
        delete_snapshot(snapshot_id, context)
        removed.append(snapshot_id)
    return removed


# ---------------------------------------------------------------------------
# Project Status Pack v2 helpers
# ---------------------------------------------------------------------------


def _safe_json_load(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _list_directory(path: Path) -> List[str]:
    if not path.exists() or not path.is_dir():
        return []
    entries: List[str] = []
    for child in sorted(path.iterdir()):
        name = child.name + ("/" if child.is_dir() else "")
        entries.append(name)
    return entries


def _check_port(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _latest_file(directory: Path, pattern: str) -> Optional[Path]:
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    return candidates[0] if candidates else None


def _load_latest_status(repo_root: Path = REPO_ROOT) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    latest = _latest_file(PROJECT_STATUS_DIR, f"{PROJECT_STATUS_PREFIX}_*.json")
    if latest is None:
        return None, None
    return latest, _safe_json_load(latest)


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    token = str(value).strip().lower()
    if not token:
        return default
    if token in DEV_TRUE_SET:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_flag_value(spec: Dict[str, Any], value: Any) -> Any:
    kind = spec.get("type", "str")
    default = spec.get("default")
    if kind == "bool":
        return _parse_bool(value, bool(default))
    if kind == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)
    if kind == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
    return str(value).strip() if value is not None else str(default)


def _collect_flag_inventory() -> Dict[str, Dict[str, Any]]:
    prefs = load_scheduler_prefs()
    env_flags = prefs.get("env_flags") if isinstance(prefs, Mapping) else {}
    inventory: Dict[str, Dict[str, Any]] = {}
    for flag_name, spec in FLAG_SPECS.items():
        env_raw = os.getenv(flag_name)
        if env_raw is not None:
            value = _coerce_flag_value(spec, env_raw)
            inventory[flag_name] = {"value": value, "source": "env"}
            continue
        pref_value = None
        if isinstance(env_flags, Mapping):
            pref_value = env_flags.get(flag_name)
        if pref_value is not None:
            value = _coerce_flag_value(spec, pref_value)
            inventory[flag_name] = {"value": value, "source": "prefs"}
            continue
        inventory[flag_name] = {"value": spec.get("default"), "source": "default"}
    return inventory


def _collect_data_directories(repo_root: Path = REPO_ROOT) -> Dict[str, List[str]]:
    directories = {
        "data/dev_config": _list_directory(repo_root / "data" / "dev_config"),
        "data/dev_logs": _list_directory(repo_root / "data" / "dev_logs"),
        "data/dev_credna": _list_directory(repo_root / "data" / "dev_credna"),
        "data/dev_schema_drafts": _list_directory(repo_root / "data" / "dev_schema_drafts"),
        "data/dev_snapshots": _list_directory(repo_root / "data" / "dev_snapshots"),
        "data/dev_users": _list_directory(repo_root / "data" / "dev_users"),
    }
    return directories


def _collect_major_modules() -> List[Dict[str, Any]]:
    modules: List[Dict[str, Any]] = []
    for path, info in MAJOR_MODULES_INFO.items():
        modules.append(
            {
                "path": path,
                "purpose": info.get("purpose", ""),
                "functions": list(info.get("functions", [])),
            }
        )
    modules.sort(key=lambda item: item["path"])
    return modules


def _core_curiosity_details(core_base: str, user_id: str, timeout: float = 1.5) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "core_base": core_base,
        "curiosity_endpoint": None,
        "http_status": None,
        "error": None,
    }
    if not core_base:
        result["error"] = "core base missing"
        return result
    target = core_base.rstrip("/") + f"/curiosity/{user_id}"
    try:
        response = requests.get(target, timeout=timeout)
        result["http_status"] = response.status_code
    except requests.RequestException as exc:
        result["error"] = str(exc)
    openapi_target = core_base.rstrip("/") + "/openapi.json"
    try:
        response = requests.get(openapi_target, timeout=timeout)
        if response.status_code == 200:
            body = response.json()
            paths = body.get("paths") if isinstance(body, Mapping) else {}
            result["curiosity_endpoint"] = bool(paths and any("/curiosity/{" in key for key in paths.keys()))
        else:
            result["curiosity_endpoint"] = False
    except requests.RequestException:
        result["curiosity_endpoint"] = None
    return result


def _load_log_tail(path: Path, fallback: str = "") -> str:
    tail_content = tail(path, 20)
    if tail_content:
        return tail_content
    return fallback


def _parse_diagnostics_log() -> Dict[str, Any]:
    log_path = REPO_ROOT / "data" / "dev_logs" / "diagnostics.log"
    if not log_path.exists():
        return {"status": "missing"}
    last_line = ""
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line.strip()
    except Exception:
        return {"status": "error"}
    if not last_line:
        return {"status": "empty"}
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return {"status": "corrupt"}
    result = payload.get("result") or "unknown"
    warn = any(step.get("warn") for step in payload.get("steps", []) if isinstance(step, Mapping))
    status = "PASS" if result == "ok" and not warn else ("WARN" if result == "ok" else "FAIL")
    return {
        "status": status,
        "raw": payload,
    }


def _latest_snapshot_info() -> Dict[str, Any]:
    latest = _latest_file(REPO_ROOT / "data" / "dev_snapshots", "devexp_snapshot_*.zip")
    if latest is None:
        return {"snapshot_id": None, "path": None}
    snapshot_id = latest.stem.replace("devexp_snapshot_", "")
    return {
        "snapshot_id": snapshot_id,
        "path": str(latest),
    }


def _latest_jsonl_entry(path: Path, action_filter: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    last_line = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                entry = json.loads(text)
                if action_filter:
                    if entry.get("action") == action_filter:
                        last_line = text
                else:
                    last_line = text
    except Exception:
        return None
    if not last_line:
        return None
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None


def _collect_golden_path() -> Dict[str, Any]:
    diagnostics = _parse_diagnostics_log()
    snapshot = _latest_snapshot_info()
    nudges_log = _latest_jsonl_entry(REPO_ROOT / "data" / "dev_logs" / "nudges.jsonl")
    actions_log = _latest_jsonl_entry(REPO_ROOT / "data" / "dev_logs" / "nudge_actions.jsonl", action_filter="accept")
    golden: Dict[str, Any] = {
        "diagnostics_loop_test": diagnostics,
        "snapshot_run": snapshot,
        "head_coach_preview": {"status": "unknown"},
        "send_to_inbox": nudges_log or {"status": "no-data"},
        "accept_in_inbox": actions_log or {"status": "no-data"},
    }
    return golden


def _collect_versions() -> Dict[str, Any]:
    versions: Dict[str, Any] = {
        "timestamp": _iso_now(),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    try:
        import streamlit  # type: ignore

        versions["streamlit"] = getattr(streamlit, "__version__", "unknown")
    except Exception:
        versions["streamlit"] = "unavailable"
    try:
        import fastapi  # type: ignore

        versions["fastapi"] = getattr(fastapi, "__version__", "unknown")
    except Exception:
        versions["fastapi"] = "unavailable"
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL)
        versions["git_commit"] = commit.decode("utf-8").strip()
    except Exception:
        versions["git_commit"] = None
    return versions


def _compute_diff(current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not previous:
        return {
            "flags_changed": list(current["flags"].keys()),
            "modules_added": [module["path"] for module in current.get("major_modules", [])],
            "data_changes": list(current.get("data_directories", {}).keys()),
        }
    diff: Dict[str, Any] = {
        "flags_changed": [],
        "modules_added": [],
        "data_changes": [],
    }
    prev_flags = previous.get("flags", {})
    for name, entry in current.get("flags", {}).items():
        prev_entry = prev_flags.get(name)
        if prev_entry is None or prev_entry.get("value") != entry.get("value") or prev_entry.get("source") != entry.get("source"):
            diff["flags_changed"].append(name)
    prev_modules = {item.get("path") for item in previous.get("major_modules", [])}
    for module in current.get("major_modules", []):
        if module.get("path") not in prev_modules:
            diff["modules_added"].append(module.get("path"))
    prev_dirs = previous.get("data_directories", {})
    for directory, listing in current.get("data_directories", {}).items():
        prev_listing = prev_dirs.get(directory)
        if prev_listing is None:
            diff["data_changes"].append(directory)
        else:
            if list(prev_listing) != list(listing):
                diff["data_changes"].append(directory)
    return diff


def gather_project_status(
    *,
    write_context: Optional[WriteProtectContext] = None,
    include_diff: bool = True,
) -> Dict[str, Any]:
    flags = _collect_flag_inventory()
    health = fetch_health(timeout=1.2)
    dev_loop_user = str(flags.get("DEV_LOOPTEST_USER_ID", {}).get("value") or "devexp_test")
    core_base = schema_utils.core_base_url()
    curiosity_info = _core_curiosity_details(core_base, dev_loop_user)
    ports: Dict[str, Dict[str, Any]] = {}
    cp_settings = _safe_json_load(REPO_ROOT / "cp_settings.json") or {}
    port_overrides = {
        "Control Panel+": cp_settings.get("cp_port", 8503),
        "Main Explorer": cp_settings.get("explorer_port", PORT_TARGETS["Main Explorer"][1]),
        "UCNRR": cp_settings.get("ucnrr_port", PORT_TARGETS["UCNRR"][1]),
        "Core": cp_settings.get("core_port", PORT_TARGETS["Core"][1]),
        "Dev Explorer": cp_settings.get("devexp_port", PORT_TARGETS["Dev Explorer"][1]),
    }
    for name, default in PORT_TARGETS.items():
        host, fallback_port = default
        port_value = int(port_overrides.get(name, fallback_port))
        ports[name] = {
            "host": host,
            "port": port_value,
            "listening": _check_port(host, port_value),
        }
    data_dirs = _collect_data_directories()
    modules = _collect_major_modules()
    golden_path = _collect_golden_path()
    versions = _collect_versions()
    latest_path, previous_json = _load_latest_status()
    diff = _compute_diff({
        "flags": flags,
        "major_modules": modules,
        "data_directories": data_dirs,
    }, previous_json) if include_diff else {}
    result = {
        "generated_at": _iso_now(),
        "write_protect": bool(getattr(write_context, "write_protect", False)),
        "flags": flags,
        "health": health,
        "core_curiosity": curiosity_info,
        "ports": ports,
        "data_directories": data_dirs,
        "major_modules": modules,
        "golden_path": golden_path,
        "versions": versions,
        "previous_status_file": str(latest_path) if latest_path else None,
        "diff": diff,
    }
    return result


def render_project_status_markdown(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Project Status Pack v2")
    lines.append("")
    versions = payload.get("versions", {})
    lines.append(f"Generated: {versions.get('timestamp', payload.get('generated_at'))}")
    if versions.get("git_commit"):
        lines.append(f"Commit: `{versions['git_commit']}`")
    lines.append("")

    lines.append("## Flags & Sources")
    lines.append("")
    lines.append("| Flag | Value | Source |")
    lines.append("| --- | --- | --- |")
    for name, entry in sorted(payload.get("flags", {}).items()):
        lines.append(f"| {name} | `{entry.get('value')}` | {entry.get('source')} |")
    lines.append("")

    lines.append("## Service Health & Curiosity")
    lines.append("")
    core_health = payload.get("health", {}).get("core", {})
    lines.append(f"- Core /health status: {core_health.get('status', 'n/a')}")
    body = core_health.get("body")
    if isinstance(body, Mapping):
        lines.append(f"  - curiosity_enabled: {body.get('curiosity_enabled')}")
    curiosity = payload.get("core_curiosity", {})
    lines.append(
        f"- `/curiosity/{{user}}` last HTTP: {curiosity.get('http_status')} (error: {curiosity.get('error')})"
    )
    lines.append(
        f"- OpenAPI lists curiosity endpoint: {curiosity.get('curiosity_endpoint')}"
    )
    lines.append("")

    lines.append("## Port Status")
    lines.append("")
    lines.append("| Service | Host | Port | Listening |")
    lines.append("| --- | --- | --- | --- |")
    for name, info in payload.get("ports", {}).items():
        lines.append(
            f"| {name} | {info.get('host')} | {info.get('port')} | {'yes' if info.get('listening') else 'no'} |"
        )
    lines.append("")

    lines.append("## Data Directories")
    lines.append("")
    for directory, listing in payload.get("data_directories", {}).items():
        lines.append(f"- **{directory}**")
        if listing:
            for item in listing:
                lines.append(f"  - {item}")
        else:
            lines.append("  - (empty)")
    lines.append("")

    lines.append("## Major Modules")
    lines.append("")
    for module in payload.get("major_modules", []):
        lines.append(f"- `{module.get('path')}` — {module.get('purpose')}")
        for fn in module.get("functions", []):
            lines.append(f"  - `{fn}`")
    lines.append("")

    lines.append("## Golden Path Checklist")
    lines.append("")
    gp = payload.get("golden_path", {})
    diag = gp.get("diagnostics_loop_test", {})
    lines.append(f"1. Diagnostics → Loop test: **{diag.get('status', 'unknown')}**")
    snapshot = gp.get("snapshot_run", {})
    lines.append(
        f"2. Snapshot + Run: snapshot_id = `{snapshot.get('snapshot_id')}`"
    )
    preview = gp.get("head_coach_preview", {})
    lines.append(
        f"3. Head Coach Preview → Generate: status = {preview.get('status', 'unknown')}"
    )
    send = gp.get("send_to_inbox", {})
    count = send.get("count") if isinstance(send, Mapping) else None
    user = send.get("user_id") if isinstance(send, Mapping) else None
    lines.append(
        f"4. Send to Inbox: user={user or 'n/a'}, count={count if count is not None else 'n/a'}"
    )
    accept = gp.get("accept_in_inbox", {})
    lines.append(
        f"5. Main Explorer → Inbox → Accept: status={accept.get('status', 'n/a')}"
    )
    lines.append("")

    lines.append("## Diff Since Previous Snapshot")
    lines.append("")
    diff = payload.get("diff", {})
    lines.append(f"- Flags changed: {', '.join(diff.get('flags_changed', [])) or 'none'}")
    lines.append(f"- Modules added: {', '.join(diff.get('modules_added', [])) or 'none'}")
    lines.append(f"- Data changes: {', '.join(diff.get('data_changes', [])) or 'none'}")
    lines.append("")

    lines.append("## Versions")
    lines.append("")
    for key, value in versions.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    return "\n".join(lines)


def _project_status_filename(timestamp: str, suffix: str) -> Path:
    PROJECT_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECT_STATUS_DIR / f"{PROJECT_STATUS_PREFIX}_{timestamp}.{suffix}"


def generate_project_status(
    write_context: Optional[WriteProtectContext] = None,
    *,
    persist: bool = True,
) -> Dict[str, Any]:
    payload = gather_project_status(write_context=write_context)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    payload["generated_at"] = _iso_now()
    payload["timestamp"] = timestamp
    markdown = render_project_status_markdown(payload)
    json_path: Optional[Path] = None
    md_path: Optional[Path] = None
    if persist and not getattr(write_context, "write_protect", False):
        json_path = _project_status_filename(timestamp, "json")
        md_path = _project_status_filename(timestamp, "md")
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
    return {
        "data": payload,
        "markdown": markdown,
        "json_path": str(json_path) if json_path else None,
        "markdown_path": str(md_path) if md_path else None,
    }


def get_latest_project_status() -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    path, data = _load_latest_status()
    return (str(path) if path else None, data)
