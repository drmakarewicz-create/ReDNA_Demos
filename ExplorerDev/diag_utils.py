"""Diagnostics helpers for Dev Explorer loop tests."""

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

import hashlib
import json
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import requests
from requests import exceptions as req_exc
import streamlit as st

from ExplorerDev import registry_helpers, snapshot_utils, tracing
from ExplorerDev.scheduler_utils import (
    SYSTEM_PREFS_PATH,
    load_scheduler_prefs,
    save_scheduler_prefs,
)
from ExplorerDev.schema_utils import (
    core_base_url,
    fetch_live_curiosity_rows,
    get_flag_bool,
    get_flag_int,
    get_flag_float,
    get_flag_str,
    load_schema,
    llm_base_url,
    simulated_curiosity_rows,
    ucnrr_base_url,
)
from ExplorerDev.write_utils import WriteProtectContext, write_guard


REPO_ROOT = ensure_repo_root()
DIAGNOSTICS_LOG_PATH = REPO_ROOT / "data/dev_logs/diagnostics.log"
SCHEDULER_LOG_PATH = REPO_ROOT / "data/dev_logs/scheduler.log"
INGEST_LOG_PATH = REPO_ROOT / "data/dev_logs/ingest.log"
_MAX_RING_SIZE = 200
SERVICE_PREFS_KEY = "service_console"
DEFAULT_SERVICE_SETTINGS = {
    "ucnrr_base": ucnrr_base_url(),
    "core_base": core_base_url(),
    "llm_base": llm_base_url(),
    "timeout": get_flag_float("DEV_HTTP_TIMEOUT_SECONDS", 12.0)[0],
    "llm_timeout": get_flag_float("DEV_LLM_TIMEOUT_SECONDS", 6.0)[0],
}


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    return default


def _timeout_seconds() -> float:
    value, _ = get_flag_float("DEV_HTTP_TIMEOUT_SECONDS", 12.0)
    return float(value)


def _path_fragment(path: str) -> str:
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_service_settings(raw: Mapping[str, Any] | None) -> Dict[str, Any]:
    data = dict(DEFAULT_SERVICE_SETTINGS)
    if isinstance(raw, Mapping):
        if raw.get("ucnrr_base"):
            data["ucnrr_base"] = str(raw.get("ucnrr_base")).strip() or data["ucnrr_base"]
        if raw.get("core_base"):
            data["core_base"] = str(raw.get("core_base")).strip() or data["core_base"]
        if raw.get("llm_base"):
            data["llm_base"] = str(raw.get("llm_base")).strip() or data["llm_base"]
        data["timeout"] = max(0.1, _safe_float(raw.get("timeout"), data["timeout"]))
        data["llm_timeout"] = max(0.1, _safe_float(raw.get("llm_timeout"), data["llm_timeout"]))
    for key in ("ucnrr_base", "core_base", "llm_base"):
        data[key] = data[key].rstrip("/")
    return data


def load_service_settings() -> Dict[str, Any]:
    prefs = load_scheduler_prefs()
    if not isinstance(prefs, dict):
        prefs = {}
    settings = _sanitize_service_settings(prefs.get(SERVICE_PREFS_KEY))
    return settings


def apply_service_settings(settings: Mapping[str, Any]) -> None:
    os.environ["UCNRR_BASE_URL"] = str(settings.get("ucnrr_base", ""))
    os.environ["CORE_BASE_URL"] = str(settings.get("core_base", ""))
    if settings.get("llm_base"):
        os.environ["LLM_BASE_URL"] = str(settings.get("llm_base"))
    os.environ["DEV_HTTP_TIMEOUT_SECONDS"] = str(settings.get("timeout", DEFAULT_SERVICE_SETTINGS["timeout"]))
    os.environ["DEV_LLM_TIMEOUT_SECONDS"] = str(settings.get("llm_timeout", DEFAULT_SERVICE_SETTINGS["llm_timeout"]))


def save_service_settings(
    settings: Mapping[str, Any],
    write_context: WriteProtectContext,
) -> Dict[str, Any]:
    clean = _sanitize_service_settings(settings)
    prefs = load_scheduler_prefs()
    if not isinstance(prefs, dict):
        prefs = {}
    prefs[SERVICE_PREFS_KEY] = clean
    save_scheduler_prefs(prefs, write_context)
    apply_service_settings(clean)
    return clean


def _normalize_tags(raw: Any) -> List[str]:
    tags: List[str] = []
    if isinstance(raw, (list, tuple, set)):
        for entry in raw:
            token = str(entry or "").strip()
            if token:
                tags.append(token)
    elif isinstance(raw, str):
        for token in raw.split(","):
            cleaned = token.strip()
            if cleaned:
                tags.append(cleaned)
    return tags


def _compose_provenance(payload: Mapping[str, Any]) -> Dict[str, Any]:
    provenance: Dict[str, Any] = {}
    source = str(payload.get("source") or "").strip()
    kind = str(payload.get("kind") or "").strip()
    tags = _normalize_tags(payload.get("tags"))
    if source:
        provenance["source"] = source
    if kind:
        provenance["kind"] = kind
    if tags:
        provenance["tags"] = tags
    extra = payload.get("extra")
    if isinstance(extra, Mapping):
        for key, value in extra.items():
            if key not in provenance and value not in (None, ""):
                provenance[key] = value
    return provenance


def _build_ingest_payload(
    *,
    payload_type: str,
    body: str,
    user_id: str,
    provenance: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized = (payload_type or "").strip().lower()
    if normalized not in {"text", "key=value", "json"}:
        raise ValueError(f"Unsupported payload type: {payload_type}")

    user_id = (user_id or "").strip()
    if not user_id:
        raise ValueError("User id is required for ingest payloads.")

    provenance_block = _compose_provenance(provenance)

    if normalized == "json":
        try:
            parsed = json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON parse error: {exc.msg} (line {exc.lineno}, column {exc.colno})"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise ValueError("JSON payload must be an object with key/value pairs.")
        payload_obj = dict(parsed)
        payload_obj.setdefault("user_id", user_id)
        if provenance_block:
            existing_prov = payload_obj.get("provenance")
            if isinstance(existing_prov, Mapping):
                merged = dict(existing_prov)
                for key, value in provenance_block.items():
                    if key not in merged or merged[key] in (None, ""):
                        merged[key] = value
                payload_obj["provenance"] = merged
            else:
                payload_obj["provenance"] = provenance_block
        elif "provenance" not in payload_obj:
            payload_obj["provenance"] = {}
        return payload_obj

    text_value = str(body or "").strip()
    payload_obj = {
        "user_id": user_id,
        "text": text_value,
        "provenance": provenance_block,
    }
    return payload_obj


def run_ingest_round_trip(
    *,
    user_id: str,
    payload_type: str,
    body: str,
    provenance: Mapping[str, Any],
    write_context: WriteProtectContext,
    use_live_curiosity: bool,
    include_before: bool,
    top_n: int = 8,
    timeout_override: Optional[float] = None,
) -> Dict[str, Any]:
    payload = _build_ingest_payload(
        payload_type=payload_type,
        body=body,
        user_id=user_id,
        provenance=provenance,
    )

    tracing_enabled, _ = get_flag_bool("ROUNDTRIP_TRACING_ENABLED", True)
    retry_limit, _ = get_flag_int("ROUNDTRIP_RETRY_LIMIT", 3)
    backoff_ms, _ = get_flag_float("ROUNDTRIP_BACKOFF_MS", 900.0)
    circuit_window_ms, _ = get_flag_float("ROUNDTRIP_CIRCUIT_BREAK_MS", 120000.0)
    auto_snapshot_enabled, _ = get_flag_bool("ORS_AUTO_SNAPSHOT_ON_FAIL", True)

    trace_id = tracing.new_trace_id() if tracing_enabled else ""
    if trace_id:
        payload.setdefault("provenance", {})['trace_id'] = trace_id
        payload["trace_id"] = trace_id

    timeout = _timeout_seconds()
    if timeout_override is not None:
        try:
            timeout = float(timeout_override)
        except (TypeError, ValueError):
            timeout = _timeout_seconds()
    timeout = max(0.1, min(timeout, 60.0))
    uc_base = ucnrr_base_url()
    core_base = core_base_url()
    if not uc_base:
        raise ValueError("UCNRR base URL is not configured.")

    curiosity_mode = "live" if use_live_curiosity else "simulated"

    before_rows: List[Dict[str, Any]] = []
    before_error: Optional[str] = None
    if use_live_curiosity and include_before:
        before_rows, before_error, _ = fetch_live_curiosity_rows(
            user_id,
            top_n=top_n,
            timeout=timeout,
            core_base=core_base,
        )

    endpoint = uc_base.rstrip("/") + "/ingest_text"
    attempts: List[Dict[str, Any]] = []
    response = None
    transport_error: Optional[str] = None
    timeout_triggered = False

    current_timeout = timeout
    max_attempts = 2
    tracing.log_event(
        component="devexp",
        trace_id=trace_id,
        event="ingest_prepare",
        meta={
            "user_id": user_id,
            "payload_type": payload_type,
            "retry_limit": retry_limit,
        },
        write_protect=context.write_protect,
    )

    for attempt_index in range(max_attempts):
        start = time.perf_counter()
        span_meta = {
            "attempt": attempt_index + 1,
            "timeout": current_timeout,
            "endpoint": endpoint,
        }
        tracing.start_span(
            component="devexp",
            trace_id=trace_id,
            span="ucnrr_post",
            meta=span_meta,
            write_protect=context.write_protect,
        )
        try:
            response = requests.post(endpoint, json=payload, timeout=current_timeout)
        except req_exc.Timeout as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            timeout_triggered = True
            transport_error = str(exc)
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "timeout": current_timeout,
                    "elapsed_ms": elapsed,
                    "status": None,
                    "timed_out": True,
                    "error": transport_error,
                }
            )
            response = None
            tracing.end_span(
                component="devexp",
                trace_id=trace_id,
                span="ucnrr_post",
                meta={**span_meta, "timed_out": True, "error": transport_error},
                write_protect=context.write_protect,
            )
            if attempt_index == 0:
                retry_timeout = max(1.0, min(current_timeout / 2.0, 6.0))
                current_timeout = retry_timeout
                continue
            break
        except requests.RequestException as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            transport_error = str(exc)
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "timeout": current_timeout,
                    "elapsed_ms": elapsed,
                    "status": None,
                    "timed_out": False,
                    "error": transport_error,
                }
            )
            response = None
            tracing.end_span(
                component="devexp",
                trace_id=trace_id,
                span="ucnrr_post",
                meta={**span_meta, "error": transport_error},
                write_protect=context.write_protect,
            )
            break
        else:
            elapsed = (time.perf_counter() - start) * 1000.0
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "timeout": current_timeout,
                    "elapsed_ms": elapsed,
                    "status": response.status_code,
                    "timed_out": False,
                }
            )
            transport_error = None
            tracing.end_span(
                component="devexp",
                trace_id=trace_id,
                span="ucnrr_post",
                meta={**span_meta, "status": response.status_code},
                write_protect=context.write_protect,
            )
            break
    elapsed_ms = attempts[-1]["elapsed_ms"] if attempts else 0.0

    ack_body: Any = None
    ack_preview = ""
    status_code: Optional[int] = None
    if response is not None:
        status_code = response.status_code
        try:
            ack_body = response.json()
            ack_preview = json.dumps(ack_body, ensure_ascii=False)[:300]
        except ValueError:
            ack_body = None
            ack_preview = (response.text or "")[:300]
    elif transport_error:
        ack_preview = transport_error[:300]

    ack_ok = response is not None and response.status_code < 400 if response is not None else False

    tracing.log_event(
        component="devexp",
        trace_id=trace_id,
        event="ucnrr_ack",
        meta={
            "status": status_code,
            "ok": ack_ok,
            "transport_error": transport_error,
        },
        write_protect=context.write_protect,
    )

    circuit_info = {
        "open": False,
        "reset_at": None,
        "retry_after_ms": None,
    }
    if isinstance(ack_body, Mapping):
        if ack_body.get("circuit_open"):
            circuit_info["open"] = True
            circuit_info["reset_at"] = ack_body.get("circuit_reset_ts")
            circuit_info["retry_after_ms"] = ack_body.get("retry_after_ms")

    core_changes: Dict[str, Any] = {
        "ok": False,
        "changed": [],
        "counts": {},
        "message": "Core change summary unavailable.",
    }
    if ack_ok and isinstance(ack_body, Mapping):
        change_payload = None
        for key in ("core_changes", "core_change_summary", "changes"):
            value = ack_body.get(key)
            if value:
                change_payload = value
                break
        if isinstance(change_payload, Mapping):
            changed = change_payload.get("changed")
            counts = change_payload.get("counts")
            if isinstance(changed, list):
                core_changes["changed"] = changed[:]
            if isinstance(counts, Mapping):
                core_changes["counts"] = dict(counts)
            core_changes["ok"] = True
            core_changes.pop("message", None)
        elif isinstance(change_payload, list):
            core_changes["changed"] = change_payload[:]
            core_changes["ok"] = True
            core_changes.pop("message", None)

    after_rows: List[Dict[str, Any]] = []
    after_error: Optional[str] = None
    deltas: List[Dict[str, Any]] = []
    curiosity_attempts: List[Dict[str, Any]] = []
    backoff_seconds = max(0.0, float(backoff_ms) / 1000.0)
    auto_snapshot: Optional[Dict[str, Any]] = None

    def _index(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
        indexed: Dict[str, Mapping[str, Any]] = {}
        for row in rows:
            trait_id = str(row.get("trait_id") or "")
            container_id = str(row.get("container_id") or "")
            key = f"{container_id}::{trait_id}" if container_id else trait_id
            if key:
                indexed[key] = row
        return indexed

    def _compute_deltas(
        before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
    ) -> List[Dict[str, Any]]:
        delta_rows: List[Dict[str, Any]] = []
        if not after:
            return delta_rows
        before_index = _index(before)
        after_index = _index(after)
        for key, after_row in after_index.items():
            before_row = before_index.get(key)
            before_val = before_row.get("curiosity") if isinstance(before_row, Mapping) else None
            after_val = after_row.get("curiosity") if isinstance(after_row, Mapping) else None
            delta_val = None
            if isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
                delta_val = float(after_val) - float(before_val)
            elif isinstance(after_val, (int, float)):
                delta_val = float(after_val)
            delta_rows.append(
                {
                    "container_id": after_row.get("container_id"),
                    "trait_id": after_row.get("trait_id"),
                    "curiosity_before": before_val,
                    "curiosity_after": after_val,
                    "delta": delta_val,
                    "ucn_after": after_row.get("ucn"),
                }
            )
        delta_rows.sort(key=lambda row: abs(row.get("delta") or 0.0), reverse=True)
        return delta_rows

    if ack_ok:
        attempts_allowed = retry_limit if use_live_curiosity else 1
        attempts_allowed = max(1, attempts_allowed)
        attempt_index = 0
        schema_doc = None
        while attempt_index < attempts_allowed:
            attempt_index += 1
            fetch_meta = {
                "attempt": attempt_index,
                "mode": curiosity_mode,
            }
            tracing.start_span(
                component="devexp",
                trace_id=trace_id,
                span="curiosity_fetch",
                meta=fetch_meta,
                write_protect=context.write_protect,
            )
            fetch_started = time.perf_counter()
            if use_live_curiosity:
                after_rows, after_error, _ = fetch_live_curiosity_rows(
                    user_id,
                    top_n=top_n,
                    timeout=timeout,
                    core_base=core_base,
                )
            else:
                if schema_doc is None:
                    schema_doc = load_schema(REPO_ROOT)
                after_rows = simulated_curiosity_rows(schema_doc, top_n=top_n)
                after_error = None
            fetch_elapsed = (time.perf_counter() - fetch_started) * 1000.0

            deltas = _compute_deltas(before_rows, after_rows)
            delta_count = sum(1 for row in deltas if row.get("delta"))
            curiosity_attempts.append(
                {
                    "attempt": attempt_index,
                    "delta_count": delta_count,
                    "error": after_error,
                    "elapsed_ms": fetch_elapsed,
                }
            )
            tracing.end_span(
                component="devexp",
                trace_id=trace_id,
                span="curiosity_fetch",
                meta={**fetch_meta, "delta_count": delta_count, "error": after_error},
                write_protect=context.write_protect,
            )

            if not use_live_curiosity:
                break

            should_retry = False
            if after_error:
                should_retry = True
            elif not deltas:
                should_retry = True

            if not should_retry:
                break
            if attempt_index >= attempts_allowed:
                break
            if backoff_seconds > 0:
                time.sleep(backoff_seconds)

    hard_failure = (not ack_ok) or circuit_info.get("open") or bool(transport_error)
    if auto_snapshot_enabled and hard_failure:
        snapshot_note = f"ORS auto snapshot (trace {trace_id or 'n/a'})"
        snapshot_result = snapshot_utils.collect_snapshot(
            context,
            in_memory=context.write_protect,
            note=snapshot_note,
            extra_meta={
                "trace_id": trace_id,
                "status": status_code,
            },
        )
        auto_snapshot = {
            "ok": snapshot_result.get("ok", False),
            "snapshot_id": snapshot_result.get("snapshot_id"),
            "path": snapshot_result.get("path"),
            "note": snapshot_note,
            "error": snapshot_result.get("error"),
        }
        tracing.log_event(
            component="devexp",
            trace_id=trace_id,
            event="auto_snapshot",
            meta={
                "ok": auto_snapshot["ok"],
                "snapshot_id": auto_snapshot.get("snapshot_id"),
            },
            write_protect=context.write_protect,
        )

    log_record: Optional[Dict[str, Any]] = None
    if not write_context.write_protect and ack_ok:
        body_hash = hashlib.sha256((body or "").encode("utf-8")).hexdigest()
        changed_count = len(core_changes.get("changed", [])) if isinstance(core_changes.get("changed"), list) else 0
        top_delta_trait = deltas[0].get("trait_id") if deltas else None
        log_record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_id": user_id,
            "type": payload_type,
            "body_hash": body_hash,
            "ucnrr_http": status_code,
            "changed_count": changed_count,
            "top_delta_trait": top_delta_trait,
        }
        write_guard(write_context, action="append ingest log")
        INGEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INGEST_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(log_record) + "\n")

    health_result: Optional[Dict[str, Any]] = None
    timeout_hint: Optional[str] = None
    if timeout_triggered:
        health_result = ping_endpoint(
            "ucnrr",
            uc_base,
            timeout=min(4.0, max(1.0, timeout / 2.0)),
        )
        if health_result.get("ok"):
            timeout_hint = "Service reachable — likely slow ingest (try a longer timeout)."
        else:
            timeout_hint = "Service unreachable — restart UCNRR."

    tracing.log_event(
        component="devexp",
        trace_id=trace_id,
        event="ingest_complete",
        meta={
            "ok": ack_ok,
            "circuit_open": circuit_info.get("open"),
            "after_error": after_error,
        },
        write_protect=context.write_protect,
    )

    return {
        "payload": payload,
        "ucnrr": {
            "ok": ack_ok,
            "http": status_code,
            "preview": ack_preview,
            "elapsed_ms": elapsed_ms,
            "body": ack_body if isinstance(ack_body, Mapping) else ack_body,
            "error": transport_error,
            "trace_id": trace_id,
            "circuit": circuit_info,
        },
        "endpoint": endpoint,
        "timeout": timeout,
        "trace_id": trace_id,
        "tracing_enabled": tracing_enabled,
        "core_changes": core_changes,
        "curiosity": {
            "mode": curiosity_mode,
            "before": before_rows,
            "after": after_rows,
            "before_error": before_error,
            "after_error": after_error,
            "deltas": deltas,
            "attempts": curiosity_attempts,
            "retry_limit": retry_limit if use_live_curiosity else 1,
            "backoff_ms": backoff_ms,
        },
        "log_record": log_record,
        "log_path": str(INGEST_LOG_PATH) if log_record else None,
        "attempts": attempts,
        "health": health_result,
        "timeout_hint": timeout_hint,
        "auto_snapshot": auto_snapshot,
        "circuit_window_ms": circuit_window_ms,
    }


def ping_endpoint(name: str, base_url: str, *, timeout: float) -> Dict[str, Any]:
    if not base_url:
        return {
            "ok": False,
            "status": None,
            "body": "not configured",
        }
    health_suffix = "/health"
    target = base_url.rstrip("/") + health_suffix
    try:
        response = requests.get(target, timeout=timeout)
        status = response.status_code
        try:
            body = response.json()
            preview = json.dumps(body)[:280]
        except ValueError:
            preview = (response.text or "").strip()[:280]
        return {
            "ok": status < 400,
            "status": status,
            "body": preview or "(empty)",
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": None,
            "body": str(exc),
        }


def tail_log(path: Path, *, max_lines: int = 500) -> List[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            dq = deque(handle, max_lines)
        return [line.rstrip("\n") for line in dq]
    except Exception:
        return []


def log_bytes(path: Path) -> Optional[bytes]:
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        return None


def service_settings_from_env() -> Dict[str, Any]:
    return _sanitize_service_settings({})


def build_loop_config(
    user_id: Optional[str] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    service_defaults = load_service_settings()
    default_user, _ = get_flag_str("DEV_LOOPTEST_USER_ID", "devexp_test")
    default_user = default_user.strip() or "devexp_test"
    config_user = user_id or default_user
    config_user = (config_user or default_user).strip() or default_user

    uc_base = service_defaults.get("ucnrr_base") or ucnrr_base_url()
    core_base = service_defaults.get("core_base") or core_base_url()
    timeout = service_defaults.get("timeout") or _timeout_seconds()
    ingest_path = _path_fragment(os.getenv("UCNRR_INGEST_PATH", "/ingest_text"))
    recompute_path = _path_fragment(os.getenv("CORE_RECOMPUTE_PATH", "/recompute"))
    poll_path = _path_fragment(os.getenv("CORE_RECOMPUTE_POLL_PATH", "/recompute/status"))
    recompute_window_ms = int(os.getenv("DEV_RECOMPUTE_WINDOW_MS", "10000") or 10000)
    skip_recompute = get_flag_bool("DEV_LOOP_SKIP_RECOMPUTE", False)[0]

    config: Dict[str, Any] = {
        "user_id": config_user,
        "uc_base": uc_base,
        "core_base": core_base,
        "timeout": timeout,
        "ingest_path": ingest_path,
        "recompute_path": recompute_path,
        "poll_path": poll_path,
        "recompute_window_ms": recompute_window_ms,
        "skip_recompute": skip_recompute,
    }

    if overrides:
        def _string_override(key: str, *, allow_empty: bool = False) -> None:
            if key in overrides:
                value = overrides.get(key)
                if value is None and not allow_empty:
                    return
                config[key] = str(value).strip() if value is not None else ""

        _string_override("uc_base")
        _string_override("core_base")
        _string_override("ingest_path")
        _string_override("recompute_path")
        _string_override("poll_path")
        _string_override("user_id")

        if "timeout" in overrides:
            try:
                config["timeout"] = float(overrides["timeout"])
            except (TypeError, ValueError):
                pass

        if "recompute_window_ms" in overrides:
            try:
                config["recompute_window_ms"] = int(overrides["recompute_window_ms"])
            except (TypeError, ValueError):
                pass

        if "skip_recompute" in overrides:
            config["skip_recompute"] = bool(overrides["skip_recompute"])

        # Normalize fragments after overrides
        config["ingest_path"] = _path_fragment(config.get("ingest_path", "/"))
        config["recompute_path"] = _path_fragment(config.get("recompute_path", "/recompute"))
        config["poll_path"] = _path_fragment(config.get("poll_path", "/recompute/status"))
        config["uc_base"] = str(config.get("uc_base", "")).rstrip("/") or uc_base
        config["core_base"] = str(config.get("core_base", "")).rstrip("/") or core_base
        user_candidate = str(config.get("user_id", "")).strip()
        if user_candidate:
            config["user_id"] = user_candidate

    return config


def _store_result(result: Dict[str, Any], write_context: WriteProtectContext) -> None:
    if getattr(write_context, "write_protect", False):
        ring: List[Dict[str, Any]] = st.session_state.setdefault("_diag_ring", [])  # type: ignore[assignment]
        ring.append(result)
        if len(ring) > _MAX_RING_SIZE:
            del ring[: len(ring) - _MAX_RING_SIZE]
        return

    write_guard(write_context, action="append diagnostics log entry")
    DIAGNOSTICS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DIAGNOSTICS_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result) + "\n")


def _step_payload(user_id: str, *, use_message: bool = False) -> Dict[str, Any]:
    key = "message" if use_message else "text"
    return {
        "user_id": user_id,
        key: f"devexp_ping={uuid.uuid4()}",
        "provenance": {
            "source": "dev_explorer",
            "kind": "loop_test",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    }


def _run_step(
    step_id: str,
    callable_step,
) -> Tuple[Dict[str, Any], Any]:
    start = time.time()
    http_status = 0
    detail: str | None = None
    ok = False
    warn = False
    context: Any = None
    try:
        result = callable_step()
        if isinstance(result, tuple) and len(result) == 5:
            ok, http_status, detail, warn, context = result
        elif isinstance(result, tuple) and len(result) == 4:
            ok, http_status, detail, context = result
        else:
            ok, http_status, detail, context = result  # type: ignore[assignment]
    except requests.RequestException as exc:
        detail = str(exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        detail = str(exc)
    elapsed_ms = int((time.time() - start) * 1000)
    entry: Dict[str, Any] = {
        "id": step_id,
        "ok": bool(ok),
        "ms": elapsed_ms,
        "detail": (detail or "")[:300],
        "http": int(http_status or 0),
    }
    if warn:
        entry["warn"] = True
    return entry, context


def run_loop_test(
    write_context: WriteProtectContext,
    *,
    user_id: str | None = None,
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the end-to-end data-cycle loop test."""

    loop_config = build_loop_config(user_id, overrides=config)
    uc_base = str(loop_config.get("uc_base", "")).rstrip("/")
    core_base = str(loop_config.get("core_base", "")).rstrip("/")
    timeout = float(loop_config.get("timeout", _timeout_seconds()))
    ingest_path = _path_fragment(str(loop_config.get("ingest_path", "/ingest_text")))
    recompute_path = _path_fragment(str(loop_config.get("recompute_path", "/recompute")))
    poll_path = _path_fragment(str(loop_config.get("poll_path", "/recompute/status")))
    recompute_window_ms = int(loop_config.get("recompute_window_ms", 10000))
    skip_recompute = bool(loop_config.get("skip_recompute", False))
    user_id = str(loop_config.get("user_id", "devexp_test")).strip() or "devexp_test"
    started = datetime.now(timezone.utc)

    steps: List[Dict[str, Any]] = []

    def step_explorer_to_ucnrr() -> Tuple[bool, int, str, bool, None]:
        headers = {"Content-Type": "application/json"}
        status = 0
        detail = ""
        ok = False
        warn = False

        for attempt_idx in range(2):
            use_message = attempt_idx == 1
            try:
                response = requests.post(
                    f"{uc_base}{ingest_path}",
                    json=_step_payload(user_id, use_message=use_message),
                    headers=headers,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                status = 0
                detail = str(exc)[:300]
                break

            status = response.status_code
            try:
                body = response.json()
            except ValueError:
                body = None

            ok = status < 400
            detail = response.text[:300] or f"status {status}"

            if isinstance(body, dict):
                if body.get("ok") is False:
                    core_response = body.get("core_response")
                    if isinstance(core_response, dict) and core_response.get("error"):
                        detail = (
                            "ucnrr ok; core forward error: "
                            + str(core_response.get("error"))[:300]
                        )
                        warn = True
                        ok = True
                    else:
                        message = (
                            core_response.get("error")
                            if isinstance(core_response, dict) and core_response.get("error")
                            else body.get("message")
                            or detail
                        )
                        detail = str(message)[:300]
                        ok = False
                elif body.get("ok") is True:
                    changed = body.get("changed_keys")
                    if isinstance(changed, list) and changed:
                        detail = f"changed {len(changed)} keys"
                    else:
                        detail = str(body.get("message") or f"status {status}")[:300]
                else:
                    detail = str(body.get("message") or detail)[:300]

            if ok or status != 422:
                break

        if not ok:
            try:
                health = requests.get(f"{uc_base}/health", timeout=timeout)
                if health.status_code < 400:
                    warn = True
                    detail = "ingest mismatch; health OK"
                    ok = True
                    status = status or health.status_code
                else:
                    detail = (
                        f"ingest failed; health {health.status_code}: "
                        + health.text[:300]
                    )
            except requests.RequestException:
                detail = detail or "ingest failed; health endpoint unavailable"

        return ok, status, detail[:300], warn, None

    step_result, _ = _run_step("explorer_to_ucnrr", step_explorer_to_ucnrr)
    steps.append(step_result)

    def step_ucnrr_to_core() -> Tuple[bool, int, str, bool, None]:
        try:
            response = requests.get(f"{uc_base}/health", timeout=timeout)
        except requests.RequestException as exc:
            raise exc
        ok = response.status_code < 400
        detail = f"status {response.status_code}"
        return ok, response.status_code, detail, False, None

    step_result, _ = _run_step("ucnrr_to_core", step_ucnrr_to_core)
    steps.append(step_result)

    def step_core_recompute() -> Tuple[bool, int, str, bool, None]:
        if skip_recompute:
            return True, 200, "skipped by config", False, None

        try:
            response = requests.post(
                f"{core_base}{recompute_path}",
                timeout=timeout,
            )
        except requests.RequestException as exc:
            return False, 0, str(exc)[:300], False, None

        status = response.status_code
        detail = response.text[:300] or f"status {status}"

        if status == 404:
            try:
                health = requests.get(f"{core_base}/health", timeout=timeout)
                if health.status_code < 400:
                    return True, status, "recompute endpoint missing; health OK", True, None
                detail = (
                    f"recompute missing; health {health.status_code}: {health.text[:300]}"
                )
                return False, status, detail, False, None
            except requests.RequestException:
                return False, status, "recompute endpoint missing; health unavailable", False, None

        if status >= 400:
            return False, status, detail, False, None

        poll_started = time.time()
        deadline = poll_started + (recompute_window_ms / 1000.0)
        poll_url = f"{core_base}{poll_path}" if poll_path != "/" else f"{core_base}/"
        use_health_poll = False

        while time.time() < deadline:
            try:
                poll_response = requests.get(
                    poll_url if not use_health_poll else f"{core_base}/health",
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                return False, status, str(exc)[:300], False, None

            poll_status = poll_response.status_code
            text_preview = poll_response.text[:300]

            if poll_status == 404 and not use_health_poll:
                use_health_poll = True
                continue

            if use_health_poll:
                if poll_status < 400:
                    return True, status, "health check OK after recompute", False, None
                return False, poll_status, f"health probe {poll_status}: {text_preview}", False, None

            if poll_status >= 400 and poll_status != 404:
                return False, poll_status, text_preview or f"poll status {poll_status}", False, None

            done = poll_status < 300
            if poll_status == 202:
                done = False
            else:
                try:
                    payload = poll_response.json()
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    status_text = str(payload.get("status") or payload.get("state") or "").lower()
                    if status_text in {"pending", "running", "processing", "in_progress"}:
                        done = False
                    elif status_text in {"complete", "completed", "done", "ready", "ok"}:
                        detail = payload.get("message") or status_text
                        done = True
                    elif payload.get("done") is False:
                        done = False
                    elif payload.get("done") is True and not detail:
                        detail = str(payload.get("message") or "recompute complete")
                        done = True
                elif poll_status < 300 and not text_preview:
                    detail = "recompute complete"

            if done:
                elapsed = int((time.time() - poll_started) * 1000)
                if not detail:
                    detail = f"recompute completed in {max(elapsed, 0)} ms"
                return True, status, str(detail)[:300], False, None

            time.sleep(0.25)

        return False, status, f"recompute timeout after {recompute_window_ms}ms", False, None

    step_result, _ = _run_step("core_recompute", step_core_recompute)
    steps.append(step_result)

    def step_ucnrr_to_explorer() -> Tuple[bool, int, str, bool, None]:
        response = requests.get(
            f"{core_base}/resolved/{user_id}",
            timeout=timeout,
        )
        status = response.status_code
        ok = status < 400
        truncated = response.text[:200]
        detail = f"status {status}" if ok else truncated or f"status {status}"
        return ok, status, detail, False, None

    step_result, _ = _run_step("ucnrr_to_explorer", step_ucnrr_to_explorer)
    steps.append(step_result)

    total_ms = sum(step["ms"] for step in steps)
    result_flag = "ok" if all(step.get("ok") for step in steps) else "fail"

    result = {
        "started_at": started.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "total_ms": total_ms,
        "steps": steps,
        "result": result_flag,
        "user_id": user_id,
        "config": loop_config,
    }

    _store_result(result, write_context)
    return result


def run_prompt_source_checks(
    persona_ids: Sequence[str] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Return prompt source summary for canonical personas."""

    persona_ids = persona_ids or [
        "relationship_coach",
        "photo",
        "padna",
    ]

    try:
        registry = registry_helpers.load_persona_registry(mode="warn")
    except Exception:  # pragma: no cover - surface as missing
        registry = registry_helpers.RegistryLoadResult(
            items=[],
            errors=[],
            imported=0,
            failures=0,
            total=0,
            validation_mode="strict",
        )

    index: Dict[str, Dict[str, Any]] = {
        str(item.get("id")): item for item in registry.items if isinstance(item, dict)
    }

    summary: Dict[str, Dict[str, Any]] = {}
    for persona_id in persona_ids:
        entry = index.get(persona_id)
        resolved = (entry or {}).get("resolved_sources")
        system_info = resolved.get("system") if isinstance(resolved, dict) else None
        opening_info = resolved.get("opening") if isinstance(resolved, dict) else None

        def _extract(info: Any) -> Dict[str, Any]:
            if not isinstance(info, dict):
                return {}
            return {
                "used": str(info.get("used") or "missing"),
                "dev_path": info.get("dev_path") or info.get("dev"),
                "live_path": info.get("live_path") or info.get("live"),
            }

        system_meta = _extract(system_info)
        opening_meta = _extract(opening_info)
        used = system_meta.get("used") or opening_meta.get("used") or "missing"

        summary[persona_id] = {
            "used": used,
            "system_path": system_meta.get("dev_path") or system_meta.get("live_path") or "—",
            "opening_path": opening_meta.get("dev_path") or opening_meta.get("live_path") or "—",
        }

    return summary
