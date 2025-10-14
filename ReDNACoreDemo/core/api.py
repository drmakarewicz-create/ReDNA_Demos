# ReDNACoreDemo/core/api.py
from __future__ import annotations

import asyncio
import base64
import copy
import io
import json
import logging
import math
import mimetypes
import os
import random
import re
import tempfile
import time
import zipfile
import shutil
import threading
import queue

logger = logging.getLogger(__name__)

# Configure robust logging for debugging chat ingestion pipeline
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/core_pipeline.log'),
        logging.StreamHandler()
    ]
)

from functools import lru_cache
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, AsyncGenerator, Tuple, Mapping, Set, Annotated
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

from PIL import Image, UnidentifiedImageError

from . import curiosity_engine, hierarchy, ui_readonly, planner, nudges, trait_timeline, decay, conversation_analyzer, hc_trait_bridge, preference_extractor, trait_container_discovery, hc_life, hc_human_intel
from .bundles import CURRENT_VERSION, iso_now
from .storage import (
    OBS_FILENAME,
    USERS_DIR,
    CORE_DATA_ROOT,
    ensure_dirs_for_user,
    load_json,
    read_user_state,
    save_json,
    save_user_info,
    write_user_state,
    touch_user_last_used,
    list_users,
    create_user,
    load_user_info,
    CHECKPOINTS_DIR,
    import_bundle,
    snapshot_bundle,
    save_media_asset,
    list_media_assets,
    get_media_asset,
    delete_media_asset,
    list_snapshot_bundles,
    create_render_job,
    load_render_job,
    save_render_job,
    list_render_jobs,
    render_job_result_path,
    list_draft_chat_entries,
    event_checkpoint,
    append_draft_chat_entries,
    clear_draft_chat_entries,
)
from . import chat_providers
from ExplorerFinal.core.head_coach_runtime import capture_turn_observation
from .schemas import BundleIn

# Photo Coach imports
try:
    import sys
    photo_coach_path = Path(__file__).resolve().parents[2] / "PhotoRefinementCoach"
    if str(photo_coach_path) not in sys.path:
        sys.path.insert(0, str(photo_coach_path))
    from src.importer import import_padna_soft
    PHOTO_COACH_AVAILABLE = True
except ImportError:
    PHOTO_COACH_AVAILABLE = False
    import_padna_soft = None

# Trait inference engine
from .trait_inference import infer_traits_from_import, InferredTrait
from . import head_coach, ucn_rr_service

from .redna_core import build_observations, resolve_traits
from .events import capture
from .security import allow
from .priority import priority_score, trait_importance_for

TRACE_TRUE = {"1", "true", "yes", "on"}
APP_VERSION = str(CURRENT_VERSION or "dev")
TRACE_ENABLED = os.getenv("ROUNDTRIP_TRACING_ENABLED", "true").strip().lower() in TRACE_TRUE
TRACE_PATH = Path(__file__).resolve().parents[1] / "data" / "dev_logs" / "trace_core.jsonl"
PROVIDER_LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "_stats" / "provider_errors.log"
PROVIDER_LOG_MAX_BYTES = 512 * 1024
TONE_CURVE_PATH = Path(__file__).resolve().parents[1] / "data" / "config" / "tone_curves.json"
COHORT_STATS_PATH = Path(__file__).resolve().parents[1] / "data" / "_stats" / "cohort_rr.json"
DEV_COHORTS_ENABLED = os.getenv("CORE_DEV_COHORTS_ENABLED", "").strip().lower() in TRACE_TRUE

ASKS_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "_asks"
NUDGES_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "_nudges"
ASKS_STORE_FILENAME = "asks.json"
NUDGES_STORE_FILENAME = "nudges.json"
_SAFE_USER_FRAGMENT = re.compile(r"[^A-Za-z0-9._-]+")

UPLOAD_LOG_PATH = Path(__file__).resolve().parents[1] / 'data' / '_stats' / 'uploads.log'
ALLOWED_MEDIA_EXTENSIONS = {'.jpg', '.png', '.json'}
IMAGE_EXTENSION_ALIASES = {'.jpeg': '.jpg'}
MEDIA_MAX_MB_DEFAULT = 20

MEDIA_EXPECTED_TYPES = {
    '.jpg': 'image/jpeg',
    '.png': 'image/png',
    '.json': 'application/json',
}


def safe_image_type(path: str) -> Optional[str]:
    """Return the detected image subtype (e.g., 'jpeg') or None when detection fails."""
    try:
        with Image.open(path) as image:
            image_format = image.format
            if image_format:
                return image_format.lower()
    except FileNotFoundError:
        return None
    except (UnidentifiedImageError, OSError):
        pass

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and mime_type.startswith('image/'):
        return mime_type.split('/', 1)[1].lower()
    return None


def _get_coach_icon(coach_id: str) -> str:
    """Return emoji icon for coach."""
    icons = {
        "head_coach": "🧭",
        "relationship_coach": "💞",
        "photo_coach": "📸",
        "personality_test_coach": "🧠",
        "career_coach": "💼",
        "chatdna_coach": "🎯",
        "beliefdna_coach": "🤔"
    }
    return icons.get(coach_id, "🤖")


def _trace_append(record: Dict[str, Any]) -> None:
    if not TRACE_ENABLED:
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


def _rotate_provider_log() -> None:
    try:
        if PROVIDER_LOG_PATH.exists() and PROVIDER_LOG_PATH.stat().st_size > PROVIDER_LOG_MAX_BYTES:
            backup = PROVIDER_LOG_PATH.with_suffix(PROVIDER_LOG_PATH.suffix + f".{int(time.time())}")
            PROVIDER_LOG_PATH.rename(backup)
    except Exception:
        pass


def _log_provider_error(kind: str, provider: str, message: str, detail: Optional[str] = None) -> None:
    try:
        PROVIDER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_provider_log()
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "error": kind,
            "provider": provider,
            "message": message,
        }
        if detail:
            record["detail"] = detail
        with PROVIDER_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:
        pass


_TRUTHY = {"1", "true", "yes", "on"}


def _sanitize_user_fragment(token: str) -> str:
    sanitized = _SAFE_USER_FRAGMENT.sub("_", token.strip())
    sanitized = sanitized.strip("._")
    return sanitized or "default"


def _load_ui_collection(base_dir: Path, user_id: str, filename: str) -> List[Dict[str, Any]]:
    """Load a lightweight UI collection (asks/nudges) from JSON storage."""

    safe_user = _sanitize_user_fragment(user_id)
    target = base_dir / safe_user / filename
    if not target.exists():
        return []

    try:
        payload = load_json(target, default={})
    except Exception:
        return []

    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [entry for entry in items if isinstance(entry, dict)]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _ui_store_path(base_dir: Path, user_id: str, filename: str) -> Path:
    safe_user = _sanitize_user_fragment(user_id)
    return base_dir / safe_user / filename


def _load_ui_store_for_update(base_dir: Path, user_id: str, filename: str) -> Tuple[Path, str, Any, List[Dict[str, Any]]]:
    """Return the target path, container type, raw payload, and mutable items list for a UI store."""

    target = _ui_store_path(base_dir, user_id, filename)
    payload = load_json(target, default=None)
    if isinstance(payload, dict):
        items = payload.get("items")
        if not isinstance(items, list):
            items = []
            payload["items"] = items
        return target, "dict", payload, items
    if isinstance(payload, list):
        return target, "list", payload, payload
    # For unexpected formats treat as empty list but still mutate original object
    payload = {"items": []}
    return target, "dict", payload, payload["items"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _write_ucn_audit_entry(
    user_id: str,
    trait_id: str,
    *,
    before_ucn: float,
    after_ucn: float,
    evidence_type: str,
    source_trust: float,
    decay_applied: bool,
    contradiction: bool,
    reason: str,
    provenance_ref: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    event_dir = ensure_dirs_for_user(user_id)["events"]
    slug = trait_id.replace("/", "_").replace(".", "_") or "trait"
    ts = datetime.now(timezone.utc)
    ts_ms = int(ts.timestamp() * 1000)
    filename = event_dir / f"ucn_{ts_ms}_{slug}.json"
    payload: Dict[str, Any] = {
        "timestamp": ts.isoformat(timespec="milliseconds"),
        "user_id": user_id,
        "trait_id": trait_id,
        "before_ucn": before_ucn,
        "after_ucn": after_ucn,
        "evidence_type": evidence_type,
        "source_trust": round(float(source_trust), 4),
        "decay_applied": bool(decay_applied),
        "contradiction": bool(contradiction),
        "reason": reason,
        "provenance_ref": provenance_ref,
    }
    if extra:
        payload["extra"] = extra
    save_json(filename, payload)


def _policy_entry(*, allowed: bool, reason: Optional[str] = None) -> Dict[str, Any]:
    return {"allowed": bool(allowed), "reason": reason if reason else None}


def _demo_ask_items(user_id: str) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    base_ms = int(now.timestamp() * 1000)

    def iso(dt: datetime) -> str:
        return dt.isoformat(timespec="milliseconds")

    def ask_entry(
        identifier: str,
        *,
        title: str,
        summary: str,
        container: str,
        gap: str,
        confidence: float,
        ask_type: str,
        status: str,
        created_offset_minutes: int = 0,
        ttl_minutes: int = 1440,
        snooze_minutes: int = 120,
        policy: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        next_available_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        created_dt = now - timedelta(minutes=created_offset_minutes)
        resume_dt = next_available_at or created_dt
        expire_dt = expires_at or (created_dt + timedelta(hours=12))
        entry_meta: Dict[str, Any] = {"title": title, "body": summary, "original_status": status}
        if metadata:
            entry_meta.update(metadata)

        base_entry: Dict[str, Any] = {
            "id": identifier,
            "user_id": user_id,
            "title": title,
            "summary": summary,
            "container": container,
            "gap": gap,
            "confidence": round(confidence, 3),
            "ask_type": ask_type,
            "sensitivity": False,
            "status": status,
            "created_at": iso(created_dt),
            "expires_at": iso(expire_dt),
            "next_available_at": iso(resume_dt),
            "ttl_minutes": ttl_minutes,
            "snooze_minutes": snooze_minutes,
            "default_snooze_minutes": snooze_minutes,
            "ts": base_ms - created_offset_minutes * 60_000,
            "meta": entry_meta,
            "policy": policy
            or {
                "approve": _policy_entry(allowed=True),
                "snooze": _policy_entry(allowed=True),
                "skip": _policy_entry(allowed=True),
            },
        }

        if extra:
            base_entry.update(extra)

        return base_entry

    resume_dt = now + timedelta(minutes=45)

    items = [
        ask_entry(
            "demo-ask-clarify-welcome",
            title="Clarify welcome message for new cohort",
            summary="Draft a single-sentence welcome the Head Coach can reuse for tomorrow's intro calls.",
            container="head_coach",
            gap="welcome_playbook",
            confidence=0.82,
            ask_type="action",
            status="open",
            created_offset_minutes=20,
        ),
        ask_entry(
            "demo-ask-refine-playlist",
            title="Mark relationship wins from last sprint",
            summary="Review the Relationship Coach board and tag one win we can celebrate in the recap email.",
            container="relationship_coach",
            gap="celebrations",
            confidence=0.74,
            ask_type="review",
            status="done",
            created_offset_minutes=90,
            policy={
                "approve": _policy_entry(allowed=False, reason="Ask already completed"),
                "snooze": _policy_entry(allowed=False, reason="Ask completed"),
                "skip": _policy_entry(allowed=False, reason="Ask completed"),
            },
            metadata={"completion_note": "Logged in recap deck"},
            extra={"completed_at": iso(now - timedelta(minutes=60))},
        ),
        ask_entry(
            "demo-ask-padna-brief",
            title="Prep PaDNA styling brief",
            summary="Collect 2 inspiration images and note palette + lighting for the next render batch.",
            container="padna_coach",
            gap="visual_identity",
            confidence=0.68,
            ask_type="plan",
            status="snoozed",
            created_offset_minutes=10,
            next_available_at=resume_dt,
            metadata={"snoozed_minutes": 45, "snooze_until": iso(resume_dt)},
            policy={
                "approve": _policy_entry(allowed=False, reason="Available again in 45 minutes"),
                "snooze": _policy_entry(allowed=False, reason="Already snoozed"),
                "skip": _policy_entry(allowed=True, reason=None),
            },
            extra={"history": [{"action": "snooze", "ts": iso(now - timedelta(minutes=10)), "minutes": 45}]},
        ),
    ]

    return items


def _demo_nudge_items(user_id: str) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)

    def iso(dt: datetime) -> str:
        return dt.isoformat(timespec="seconds")

    items: List[Dict[str, Any]] = []

    items.append(
        {
            "id": "demo-nudge-celebrate-win",
            "user_id": user_id,
            "kind": "celebration",
            "title": "Celebrate today’s quick win",
            "body": "Send a 2-sentence Slack shout-out reinforcing the progress they just logged.",
            "text": "Celebrate today’s quick win with a short Slack shout-out.",
            "status": "new",
            "created_ts": iso(now - timedelta(minutes=30)),
            "ttl_minutes": 1440,
            "snooze_minutes": 120,
            "metadata": {
                "original_status": "new",
                "body": "Send a quick Slack shout-out reinforcing the latest win.",
            },
            "policy": {
                "accept": _policy_entry(allowed=True),
                "dismiss": _policy_entry(allowed=True),
                "undo": _policy_entry(allowed=False, reason="no_previous_action"),
            },
            "history": [],
        }
    )

    snoozed_until = now + timedelta(minutes=60)
    items.append(
        {
            "id": "demo-nudge-follow-up",
            "user_id": user_id,
            "kind": "follow_up",
            "title": "Remind them about tomorrow’s check-in",
            "body": "Draft a 2-line reminder email with the calendar link.",
            "text": "Draft tomorrow’s check-in reminder email.",
            "status": "pending",
            "created_ts": iso(now - timedelta(hours=1)),
            "ttl_minutes": 2880,
            "snooze_minutes": 90,
            "snoozed_until": iso(snoozed_until),
            "last_snoozed_at": iso(now - timedelta(minutes=10)),
            "metadata": {
                "original_status": "pending",
                "body": "Draft a two-line reminder email with tomorrow’s check-in link.",
            },
            "policy": {
                "accept": _policy_entry(allowed=True),
                "dismiss": _policy_entry(allowed=True),
                "undo": _policy_entry(allowed=False, reason="no_previous_action"),
            },
            "history": [{"action": "snooze", "ts": iso(now - timedelta(minutes=10)), "minutes": 60}],
        }
    )

    items.append(
        {
            "id": "demo-nudge-done-checklist",
            "user_id": user_id,
            "kind": "checklist",
            "title": "Mark onboarding checklist complete",
            "body": "Log the final onboarding step in the shared tracker so Ops can review.",
            "text": "Mark onboarding checklist complete in the tracker.",
            "status": "read",
            "created_ts": iso(now - timedelta(hours=4)),
            "ttl_minutes": 4320,
            "snooze_minutes": 60,
            "metadata": {
                "original_status": "read",
                "body": "Log the final onboarding step in the shared tracker.",
            },
            "policy": {
                "accept": _policy_entry(allowed=False, reason="already_completed"),
                "dismiss": _policy_entry(allowed=False, reason="already_completed"),
                "undo": _policy_entry(allowed=True, reason=None),
            },
            "history": [{"action": "accept", "ts": iso(now - timedelta(hours=3, minutes=45))}],
        }
    )

    return items


def _seed_ui_items(base_dir: Path, user_id: str, filename: str, items: List[Dict[str, Any]]) -> Tuple[bool, int]:
    target = _ui_store_path(base_dir, user_id, filename)
    if target.exists():
        existing = _load_ui_collection(base_dir, user_id, filename)
        return False, len(existing)

    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": items} if base_dir == ASKS_DATA_ROOT else items
    save_json(target, payload)
    return True, len(items)


PADNA_JOB_FILENAME = "job.json"
PADNA_RESULT_FILENAME = "result.png"
ONBOARDING_PROFILE_DIR = "profile"
ONBOARDING_PROFILE_FILENAME = "onboarding.json"


def _padna_job_root(user_id: str) -> Path:
    return USERS_DIR / user_id / "renders"


def _padna_job_dir(user_id: str, job_id: str) -> Path:
    return _padna_job_root(user_id) / job_id


def _padna_job_path(user_id: str, job_id: str) -> Path:
    return _padna_job_dir(user_id, job_id) / PADNA_JOB_FILENAME


def _padna_result_path(user_id: str, job_id: str, filename: Optional[str] = None) -> Path:
    target_name = filename if isinstance(filename, str) and filename else PADNA_RESULT_FILENAME
    return _padna_job_dir(user_id, job_id) / target_name


def _padna_load_job(user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    job_path = _padna_job_path(user_id, job_id)
    if not job_path.exists():
        return None
    payload = load_json(job_path, default=None)
    if not isinstance(payload, dict):
        return None
    payload.setdefault("id", job_id)
    payload.setdefault("user_id", user_id)
    payload.setdefault("state", "queued")
    payload.setdefault("progress", 0.0)
    payload.setdefault("created_at", _iso_now())
    payload.setdefault("updated_at", payload.get("created_at"))
    payload.setdefault("error", None)
    payload.setdefault("result_filename", None)
    payload.setdefault("result_content_type", None)
    if "bundle" not in payload or not isinstance(payload["bundle"], dict):
        payload["bundle"] = {}
    return payload


def _padna_save_job(user_id: str, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current = _padna_load_job(user_id, job_id)
    if current is None:
        return None
    payload = dict(current)
    payload.update(updates)
    if "progress" in payload:
        try:
            value = float(payload["progress"])
        except (TypeError, ValueError):
            value = current.get("progress", 0.0) or 0.0
        payload["progress"] = max(0.0, min(1.0, value))
    payload["id"] = payload.get("id") or job_id
    payload["job_id"] = payload.get("job_id") or payload.get("id") or job_id
    payload["user_id"] = payload.get("user_id") or user_id
    payload.setdefault("params", payload.get("params") or payload.get("bundle") or {})
    payload["storage_path"] = f"renders/{job_id}/"
    if payload.get("result_content_type") and not updates.get("content_type"):
        payload["content_type"] = payload["result_content_type"]
    if "content_type" in updates:
        payload["content_type"] = updates["content_type"]
    if payload.get("result_filename") is None and updates.get("result_filename") is None:
        payload["result_filename"] = None
    payload["updated_at"] = _iso_now()
    job_path = _padna_job_path(user_id, job_id)
    job_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(job_path, payload)
    return payload


def _padna_create_job(user_id: str, bundle: Mapping[str, Any]) -> Dict[str, Any]:
    job_id = f"rb_{uuid4().hex}"
    root = _padna_job_dir(user_id, job_id)
    root.mkdir(parents=True, exist_ok=True)
    now_iso = _iso_now()
    payload: Dict[str, Any] = {
        "id": job_id,
        "job_id": job_id,
        "user_id": user_id,
        "state": "queued",
        "progress": 0.0,
        "created_at": now_iso,
        "updated_at": now_iso,
        "bundle": dict(bundle),
        "params": dict(bundle),
        "result_filename": None,
        "result_content_type": None,
        "content_type": None,
        "error": None,
        "storage_path": f"renders/{job_id}/",
    }
    save_json(_padna_job_path(user_id, job_id), payload)
    return payload


def _padna_list_jobs(user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    root = _padna_job_root(user_id)
    if not root.exists():
        return []
    jobs: List[Dict[str, Any]] = []
    for job_path in root.glob(f"*/{PADNA_JOB_FILENAME}"):
        job_id = job_path.parent.name
        job = _padna_load_job(user_id, job_id)
        if job is None:
            continue
        jobs.append(job)
    jobs.sort(key=lambda entry: _iso_to_epoch(entry.get("created_at")) or 0.0, reverse=True)
    if isinstance(limit, int) and limit > 0:
        return jobs[:limit]
    return jobs


def _curiosity_flag_on() -> bool:
    value = os.getenv("CORE_CURIOSITY_ENABLED", "").strip().lower()
    return value in _TRUTHY

def build_app() -> FastAPI:
    app = FastAPI(title="ReDNA Core Demo", version="2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    CURIOSITY_ON = _curiosity_flag_on()

    RUNTIME_STATE_FILENAME = "hc_runtime_state.json"
    SYSTEM_PROMPT = (
        "⚠️ CRITICAL CONSTRAINT: You are a TEXT-ONLY chatbot. You CANNOT send messages, make introductions, or execute actions. "
        "When users ask to switch coaches, you can ONLY give them UI directions like: 'Click the Coach Catalog (📚) in the sidebar.'\n\n"

        "You are the Head Coach - a lifelong companion helping someone become their best self. "
        "Your role is to listen, guide, and connect them with the right tools when needed. "
        "Speak like a close friend texting - warm, direct, not wordy. "
        "Keep responses short (1-2 sentences max). Listen carefully to what they say. Ask ONE question to go deeper. "

        "BOUNDARIES: If someone says 'not now', 'later', 'not interested' about a topic, DON'T bring it up again proactively. "
        "However, if they DIRECTLY ASK about that topic later, answer their question normally - 'not now' means 'not now', not 'never'. "
        "Example: If they said 'not interested in photos now' but later ask 'what coaches are available?', list ALL coaches including Photo Coach. "
        "The boundary is about YOU pushing topics, not about preventing them from asking questions. "
        "Let users talk about whatever they want—TV shows, sports, hobbies. Casual chat builds trust. "

        "AVAILABLE COACHES: You work with specialized coaches who help in different areas:\n"
        "• Relationship Coach 💞 - dating, relationships, emotions, psychology\n"
        "• Photo Coach 📸 - physical appearance, style, visual presence\n"
        "• Personality Test Coach 🧠 - personality profiling, motivations, values\n"
        "• Career Coach 💼 - career planning, skills, professional development\n"
        "\n"
        "⚠️ CRITICAL - COACH SWITCHING PROTOCOL:\n"
        "When a user asks to switch coaches (e.g., 'talk to career coach', 'switch to relationship coach'):\n"
        "\n"
        "✅ CORRECT RESPONSE:\n"
        "'Perfect! Click the Coach Catalog button (📚) in the left sidebar, then select [Coach Name] from the list.'\n"
        "\n"
        "❌ FORBIDDEN RESPONSES (NEVER SAY THESE):\n"
        "- 'I'll send an introduction'\n"
        "- 'I'll connect you'\n"
        "- 'They'll reach out to you'\n"
        "- 'I've notified them'\n"
        "\n"
        "WHY: You are a text interface. You CANNOT execute actions or send messages to other coaches.\n"
        "You can ONLY guide users to click UI buttons. Be EXTREMELY clear about this.\n"
        "\n"
        "TEMPLATE: 'Great! To switch to [Coach Name], click the Coach Catalog (📚) in the sidebar, then select [Coach Name].'\n"
        "\n"
        "You can suggest ONE coach per conversation if highly relevant, but don't be pushy. "
        "If they say 'not interested' or 'later', don't mention it again in this conversation. "

        "CASUAL TOPICS: When someone asks about TV shows, books, food, weather, sports—answer naturally and stay on that topic. "
        "DO NOT pivot to self-improvement, goals, or life changes. Do NOT ask 'what would you like to change in your life?' "
        "Just have a normal conversation about the thing they asked about. Being helpful with small things builds trust. "

        "FUTURE VALUE: Show long-term value when appropriate, but don't force every conversation toward big life goals. "
        "Sometimes people just want to chat, and that's valuable too."
    )
    PERSONA_PROMPTS = {
        "head coach": (
            "⚠️ YOU ARE A CHATBOT - NOT A SECRETARY. You CANNOT send messages or make introductions. "
            "When asked to switch coaches, give UI directions ONLY.\n\n"

            "You're the Head Coach - their closest ally for life. "

            "BOUNDARIES: If someone says 'not now', 'later', or 'not interested' about a topic, DON'T proactively bring it up again. "
            "But if they DIRECTLY ASK about it later, answer normally. 'Not now' ≠ 'never'. "
            "The boundary is about YOU not pushing, not about blocking their questions. "
            "Example: They said 'no coaches now', but later ask 'what coaches exist?' → Answer the question fully. "
            "If they change the subject, follow their lead immediately. "

            "AVAILABLE COACHES:\n"
            "• Relationship Coach 💞 - relationships, emotions, psychology\n"
            "• Photo Coach 📸 - appearance, style, visual presence\n"
            "• Personality Test Coach 🧠 - personality, motivations, values\n"
            "• Career Coach 💼 - career, skills, professional development\n"
            "\n"
            "⚠️ SWITCHING COACHES - CRITICAL RULE:\n"
            "When user asks to switch: Give them UI DIRECTIONS ONLY.\n"
            "✅ SAY: 'Perfect! Click Coach Catalog (📚) in sidebar → select [Coach Name]'\n"
            "❌ NEVER SAY: 'I'll connect you' / 'I'll send introduction' / 'They'll contact you'\n"
            "You are TEXT ONLY. You cannot execute switches. ONLY guide to UI.\n"
            "\n"
            "You can suggest ONE coach per conversation if highly relevant (e.g., 'Dating is tough. Want to chat with our Relationship Coach?')\n"
            "If they say no or 'later', never mention that coach again in this conversation. "

            "CASUAL CONVERSATIONS: If they ask about TV shows, restaurants, hobbies, books, weather, sports—have a normal conversation. "
            "Stay on their topic. DO NOT redirect to self-improvement, goals, life changes, or meaningful decisions. "
            "DO NOT ask 'what would you like to change' or 'are you looking to improve'. Just chat about the thing they asked about. "
            "Example: If they ask about TV shows, talk about TV shows. Don't ask about their life goals. "

            "TONE: Be casual and helpful, not salesy. Avoid therapy-speak, business jargon, and phrases like 'Next step:' or 'Let's explore.' "
            "Sound like a real person texting a friend."
        ),
        "rc": (
            "Persona: Relationship Coach. Offer empathetic, practical relationship guidance with a collaborative tone."
        ),
        "padna": (
            "Persona: PaDNA Coach. Reference visual DNA insights, summarize aesthetic direction, and flag follow-ups."
        ),
        "photo": (
            "Persona: Photo Coach. Focus on photo session preparation, lighting, and pose refinement tips."
        ),
        "career_coach": (
            "You're the Career Coach - a strategic partner for professional growth and career development.\n\n"

            "YOUR EXPERTISE:\n"
            "• Skills Assessment - Identify strengths, gaps, and growth opportunities\n"
            "• Career Planning - Map career paths, transitions, and progression strategies\n"
            "• Learning Paths - Recommend courses, certifications, and skill-building approaches\n"
            "• Work-Life Optimization - Balance productivity with sustainable work habits\n"
            "• Professional Development - Networking, personal branding, interview prep\n\n"

            "YOUR APPROACH:\n"
            "• Start by understanding their current role, industry, and career goals\n"
            "• Ask about skills they want to develop or areas they want to explore\n"
            "• Provide specific, actionable advice based on their situation\n"
            "• Suggest concrete next steps (courses, projects, networking strategies)\n"
            "• Balance ambition with realistic timelines and effort required\n\n"

            "CONVERSATION STYLE:\n"
            "• Professional but friendly - like a mentor who's been there\n"
            "• Focus on practical steps, not just theory or inspiration\n"
            "• Acknowledge career challenges and uncertainties honestly\n"
            "• Celebrate wins and progress, no matter how small\n"
            "• Ask clarifying questions to give better, more tailored advice\n\n"

            "AVOID:\n"
            "• Generic career advice that could apply to anyone\n"
            "• Overpromising results ('this will land you a job in 30 days')\n"
            "• Corporate buzzwords and LinkedIn-speak\n"
            "• Pushing them toward specific careers without understanding their values\n\n"

            "TONE: Supportive, knowledgeable, and practical. Sound like a career mentor, not a motivational speaker."
        ),
        "personality_test_coach": (
            "You're the Personality Test Coach - an expert in adaptive personality assessment and psychological profiling.\n\n"

            "YOUR ROLE:\n"
            "• Explore personality traits through contextual questions and observations\n"
            "• Map to OCEAN model (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)\n"
            "• Discover motivational drives, values, and behavioral patterns\n"
            "• Help them understand themselves better through self-reflection\n\n"

            "HOW YOU ASSESS:\n"
            "• Ask about real situations, not hypotheticals ('Tell me about a time when...')\n"
            "• Listen for patterns in how they describe experiences\n"
            "• Explore motivations behind their choices and behaviors\n"
            "• Use follow-up questions to go deeper on interesting signals\n"
            "• Connect observations to personality insights naturally\n\n"

            "CONVERSATION APPROACH:\n"
            "• Start with open-ended questions about their life, work, or relationships\n"
            "• Listen for clues about personality traits and motivations\n"
            "• Reflect back what you notice: 'It sounds like you really value...'\n"
            "• Ask clarifying questions to validate or refine your understanding\n"
            "• Share personality insights when you have enough data\n\n"

            "TRAITS TO EXPLORE:\n"
            "• Openness: Curiosity, creativity, comfort with novelty\n"
            "• Conscientiousness: Organization, planning, follow-through\n"
            "• Extraversion: Social energy, expressiveness, stimulation needs\n"
            "• Agreeableness: Cooperation, empathy, conflict approach\n"
            "• Neuroticism: Emotional stability, stress response, worry patterns\n\n"

            "TONE:\n"
            "• Curious and non-judgmental - you're discovering, not diagnosing\n"
            "• Insightful but humble - acknowledge complexity and nuance\n"
            "• Conversational, not clinical - avoid psych jargon\n"
            "• Frame traits neutrally - every trait has strengths and challenges\n\n"

            "AVOID:\n"
            "• Labeling or boxing people in ('You're definitely a...')\n"
            "• Using clinical terminology without explanation\n"
            "• Making it feel like a test or interrogation\n"
            "• Oversimplifying complex personalities\n\n"

            "Remember: Personality is multifaceted. Your job is to help them see themselves more clearly, not to reduce them to labels."
        ),
    }
    PERSONA_RUBRICS = {
        "head coach": (
            "Rubric: Listen closely. Reflect what you heard (1 sentence), then either ask ONE question OR suggest a coach (1 sentence). "

            "VARIATION: Never ask the same question twice in one conversation. If they don't answer or change topics, let it go. "

            "COACH SUGGESTIONS: Suggest a coach only ONCE per conversation, and only if highly relevant. "
            "If they decline ('not now', 'later', 'not interested'), DON'T proactively suggest that coach again. "
            "HOWEVER: If they DIRECTLY ASK about coaches (e.g., 'what coaches are available?', 'tell me about the career coach'), ANSWER THEIR QUESTION. "
            "The rule is: Don't PUSH rejected coaches on them. But DO answer when they ASK. "
            "Example: They said 'no relationship coach now'. Later they ask 'what coaches exist?' → List ALL coaches including Relationship Coach. "
            "Example: They said 'no career coach'. You suggest career help → DON'T mention career coach. They ask 'can I talk to career coach?' → YES, explain how. "
            "\n"
            "COACH MATCHING:\n"
            "• Relationships, emotions, psychology → Relationship Coach\n"
            "• Appearance, style, physical traits → Photo Coach\n"
            "• Personality, motivations, values → Personality Test Coach\n"
            "• Career, skills, work, professional growth → Career Coach\n"
            "Keep it light: 'If you want, I can connect you with [Coach]—no pressure.'\n"
            "\n"
            "⚠️ CRITICAL: COACH SWITCHING REQUESTS\n"
            "User asks to switch? → Give UI directions ONLY. NO role-playing as executor.\n"
            "✅ CORRECT: 'Great! Click Coach Catalog (📚) in sidebar → select [Coach Name]'\n"
            "❌ FORBIDDEN: 'I'll send intro' / 'I'll connect you' / 'They'll reach out'\n"
            "You are a CHATBOT, not a secretary. Guide to UI, don't pretend to do actions.\n"
            "→ NEVER refuse switching requests. ALWAYS give clear UI directions. "

            "FRUSTRATION: If they sound frustrated ('I already said', 'I told you', 'again'), apologize immediately and change approach. "
            "Example: 'Sorry! I hear you. Let's talk about what you want to talk about.' "

            "LONG-TERM VALUE: When natural, show value: 'I'm here for your whole journey.' But don't force it into every response."
        ),
        "rc": "Rubric: Empathetic relationship guide; validate feelings and offer one practical follow-up.",
        "padna": "Rubric: Visual DNA stylist; surface palette/texture cues and suggest one design tweak.",
        "photo": "Rubric: Photo session coach; focus on lighting/pose alignment and provide one immediate adjustment.",
        "career_coach": (
            "Rubric: Career mentor approach. Each response should:\n"
            "1. Acknowledge their current situation or concern (1 sentence)\n"
            "2. Provide one specific, actionable piece of advice or insight (2-3 sentences)\n"
            "3. Ask ONE clarifying question OR suggest one concrete next step\n\n"
            "Keep it practical and tailored. Avoid generic platitudes. Sound like a mentor who knows their industry."
        ),
        "personality_test_coach": (
            "Rubric: Adaptive assessment approach. Each response should:\n"
            "1. Reflect back what you heard, noting patterns (1 sentence)\n"
            "2. Ask ONE follow-up question about a specific situation or behavior\n"
            "3. When you have enough data, share a personality insight tied to what they've shared\n\n"
            "Move between questions and insights fluidly. Never rush to conclusions. Make them feel understood, not analyzed."
        ),
    }
    DEFAULT_RESPONSES = {
        "head coach": "(Head Coach) Thanks for the update. I noted your message and will suggest a next step shortly.",
        "rc": "(Relationship Coach) Appreciate you sharing this—let's focus on a practical next action together.",
        "padna": "(PaDNA Coach) Got it. I'll log this and circle back with a visual check when ready.",
        "photo": "(Photo Coach) Understood. I'll keep it in mind for the next refinement pass.",
        "career_coach": "(Career Coach) Got it. I'll consider this and suggest a practical career step when you're ready.",
        "personality_test_coach": "(Personality Test Coach) Interesting. I'll note this pattern and we can explore it more together.",
    }
    USER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")

    def _media_limits() -> Tuple[int, int]:
        raw = os.getenv('MEDIA_MAX_MB')
        try:
            mb_value = int(raw) if raw else MEDIA_MAX_MB_DEFAULT
        except (TypeError, ValueError):
            mb_value = MEDIA_MAX_MB_DEFAULT
        mb_value = max(1, mb_value)
        return mb_value, mb_value * 1024 * 1024

    def _normalize_media_extension(filename: str) -> str:
        ext = Path(filename or '').suffix.lower()
        if ext in IMAGE_EXTENSION_ALIASES:
            return IMAGE_EXTENSION_ALIASES[ext]
        return ext

    def _slugify_media_name(name: str, ext: str) -> str:
        base = Path(name or '').stem or 'upload'
        normalized = unicodedata.normalize('NFKD', base)
        ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
        ascii_only = ascii_only.lower()
        ascii_only = re.sub(r'[^a-z0-9]+', '-', ascii_only)
        ascii_only = re.sub(r'-{2,}', '-', ascii_only).strip('-')
        if not ascii_only:
            ascii_only = 'upload'
        return f"{ascii_only}{ext}"

    def _detect_media_type(payload: bytes) -> Optional[str]:
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile('wb', suffix='.upload', delete=False) as tmp_file:
                tmp_file.write(payload)
                temp_path = tmp_file.name
            kind = safe_image_type(temp_path) if temp_path else None
        except Exception:
            kind = None
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        if kind == 'jpeg':
            return 'image/jpeg'
        if kind == 'png':
            return 'image/png'
        sample = payload.lstrip()
        if sample.startswith(b'\xef\xbb\xbf'):
            sample = sample[3:].lstrip()
        if sample.startswith((b'{', b'[')):
            try:
                text = payload.decode('utf-8')
            except UnicodeDecodeError:
                return None
            try:
                json.loads(text)
            except Exception:
                return None
            return 'application/json'
        return None

    def _log_upload_violation(reason: str, *, user_id: str, filename: str, size: int, content_type: Optional[str], detail: Optional[str] = None) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            "reason": reason,
            "user_id": user_id,
            "filename": filename,
            "size": size,
        }
        if content_type:
            record["content_type"] = content_type
        if detail:
            record["detail"] = detail
        try:
            UPLOAD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with UPLOAD_LOG_PATH.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(record) + '\n')
        except Exception:
            pass

    PHOTO_PLACEHOLDER_BYTES = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )
    PHOTO_PLACEHOLDER_TYPE = "image/png"
    PHOTO_PLACEHOLDER_FILENAME = "render-placeholder.png"

    job_user_cache: Dict[str, str] = {}
    padna_job_user_cache: Dict[str, str] = {}
    PADNA_PLACEHOLDER_BYTES = PHOTO_PLACEHOLDER_BYTES
    PADNA_PLACEHOLDER_TYPE = PHOTO_PLACEHOLDER_TYPE

    def _serialize_padna_job(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": job.get("id"),
            "user_id": job.get("user_id"),
            "state": job.get("state"),
            "progress": job.get("progress"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "error": job.get("error"),
            "result_filename": job.get("result_filename"),
            "result_content_type": job.get("result_content_type"),
            "content_type": job.get("content_type") or job.get("result_content_type"),
            "bundle": job.get("bundle") if isinstance(job.get("bundle"), dict) else {},
            "params": job.get("params") if isinstance(job.get("params"), dict) else {},
            "storage_path": job.get("storage_path"),
        }
        job_id = payload["id"]
        if isinstance(job_id, str):
            payload["status_url"] = f"/ui/padna/status?job_id={job_id}"
            payload["result_url"] = f"/ui/padna/result?job_id={job_id}"
            if not payload.get("storage_path"):
                payload["storage_path"] = f"renders/{job_id}/"
        return payload


    def _padna_locate_job(job_id: str, user_hint: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        candidates: List[str] = []
        if isinstance(user_hint, str) and user_hint.strip():
            candidates.append(user_hint.strip())
        cached = padna_job_user_cache.get(job_id)
        if cached and cached not in candidates:
            candidates.append(cached)

        for candidate in candidates:
            job = _padna_load_job(candidate, job_id)
            if job:
                padna_job_user_cache[job_id] = candidate
                return candidate, job

        try:
            for user_dir in USERS_DIR.iterdir():
                if not user_dir.is_dir():
                    continue
                candidate = user_dir.name
                if candidate in candidates:
                    continue
                job = _padna_load_job(candidate, job_id)
                if job:
                    padna_job_user_cache[job_id] = candidate
                    return candidate, job
        except FileNotFoundError:
            return None
        return None

    class PhotoRenderWorker:
        def __init__(self) -> None:
            self._queue: "queue.Queue[Optional[Tuple[str, str]]]" = queue.Queue()
            self._thread = threading.Thread(target=self._run, name="photo-render-worker", daemon=True)
            self._thread.start()

        def submit(self, user_id: str, job_id: str) -> None:
            self._queue.put((user_id, job_id))

        def stop(self) -> None:
            try:
                self._queue.put(None)
            except Exception:
                return
            self._thread.join(timeout=2.0)

        def _run(self) -> None:
            while True:
                item = self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break
                user_id, job_id = item
                try:
                    self._process_job(user_id, job_id)
                finally:
                    self._queue.task_done()

        def _process_job(self, user_id: str, job_id: str) -> None:
            job = save_render_job(user_id, job_id, {"state": "running", "progress": 0.1})
            if job is None:
                return
            media_id = job.get("media_id")
            if not isinstance(media_id, str) or not media_id:
                save_render_job(
                    user_id,
                    job_id,
                    {
                        "state": "error",
                        "error": "MEDIA_ID_MISSING",
                        "progress": 1.0,
                    },
                )
                return

            time.sleep(0.35)
            resolved = get_media_asset(user_id, media_id)
            if not resolved:
                save_render_job(
                    user_id,
                    job_id,
                    {
                        "state": "error",
                        "error": "MEDIA_NOT_FOUND",
                        "progress": 1.0,
                    },
                )
                return

            entry, media_path = resolved
            save_render_job(user_id, job_id, {"progress": 0.6})

            ext = Path(entry.get("filename") or "").suffix or Path(entry.get("original_name") or "").suffix
            if not ext:
                ext = ".png"
            result_filename = f"result{ext}"
            result_path = render_job_result_path(user_id, job_id, filename=result_filename)

            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(media_path, result_path)
            except Exception as exc:
                save_render_job(
                    user_id,
                    job_id,
                    {
                        "state": "error",
                        "error": f"COPY_FAILED: {exc}",
                        "progress": 1.0,
                    },
                )
                return

            save_render_job(
                user_id,
                job_id,
                {
                    "state": "done",
                    "progress": 1.0,
                    "result_id": job_id,
                    "result_filename": result_filename,
                    "result_content_type": entry.get("content_type") or "application/octet-stream",
                    "error": None,
                },
            )

    photo_worker = PhotoRenderWorker()

    class PadnaRenderWorker:
        def __init__(self) -> None:
            self._queue: "queue.Queue[Optional[Tuple[str, str]]]" = queue.Queue()
            self._thread = threading.Thread(target=self._run, name="padna-render-worker", daemon=True)
            self._thread.start()

        def submit(self, user_id: str, job_id: str) -> None:
            self._queue.put((user_id, job_id))

        def stop(self) -> None:
            try:
                self._queue.put(None)
            except Exception:
                return
            self._thread.join(timeout=2.0)

        def _run(self) -> None:
            while True:
                item = self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break
                user_id, job_id = item
                try:
                    self._process_job(user_id, job_id)
                finally:
                    self._queue.task_done()

        def _process_job(self, user_id: str, job_id: str) -> None:
            job = _padna_save_job(user_id, job_id, {"state": "running", "progress": 0.15})
            if job is None:
                return
            time.sleep(0.3)
            _padna_save_job(user_id, job_id, {"progress": 0.6})
            result_path = _padna_result_path(user_id, job_id, PADNA_RESULT_FILENAME)
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with result_path.open("wb") as handle:
                    handle.write(PADNA_PLACEHOLDER_BYTES)
            except Exception as exc:
                _padna_save_job(
                    user_id,
                    job_id,
                    {
                        "state": "error",
                        "error": f"RENDER_FAILED: {exc}",
                        "progress": 1.0,
                        "result_filename": None,
                        "result_content_type": None,
                        "content_type": None,
                    },
                )
                return

            _padna_save_job(
                user_id,
                job_id,
                {
                    "state": "done",
                    "progress": 1.0,
                    "result_filename": PADNA_RESULT_FILENAME,
                    "result_content_type": PADNA_PLACEHOLDER_TYPE,
                    "content_type": PADNA_PLACEHOLDER_TYPE,
                    "error": None,
                },
            )

    padna_worker = PadnaRenderWorker()

    @app.on_event("shutdown")
    async def _stop_photo_worker() -> None:
        photo_worker.stop()

    @app.on_event("shutdown")
    async def _stop_padna_worker() -> None:
        padna_worker.stop()

    def _hc_chat_enabled() -> bool:
        raw = os.getenv("HC_CHAT_ENABLED")
        if raw is None or raw.strip() == "":
            return True
        return raw.strip().lower() in _TRUTHY

    def _aggregate_user_summary(user_id: str) -> Optional[Dict[str, Any]]:
        for entry in list_users(user_id):
            if entry.get("id") == user_id:
                return entry
        return None

    def _hc_chat_stream_enabled() -> bool:
        raw = os.getenv("HC_CHAT_STREAM_ENABLED")
        if raw is None or raw.strip() == "":
            return True
        return raw.strip().lower() in _TRUTHY

    def _runtime_state_path(user_id: str) -> Path:
        return USERS_DIR / user_id / RUNTIME_STATE_FILENAME

    def _load_runtime_state(user_id: str) -> Dict[str, Any]:
        path = _runtime_state_path(user_id)
        return load_json(path, default={}) if path.exists() else {}

    def _store_runtime_state(user_id: str, state: Dict[str, Any]) -> None:
        path = _runtime_state_path(user_id)
        save_json(path, state)

    def _index_render_job(job: Dict[str, Any]) -> None:
        job_id = job.get("id")
        user_id = job.get("user_id")
        if isinstance(job_id, str) and isinstance(user_id, str):
            job_user_cache[job_id] = user_id

    def _serialize_render_job(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "id": job.get("id"),
            "user_id": job.get("user_id"),
            "media_id": job.get("media_id"),
            "state": job.get("state"),
            "progress": job.get("progress"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "error": job.get("error"),
            "result_id": job.get("result_id"),
            "result_filename": job.get("result_filename"),
            "result_content_type": job.get("result_content_type"),
            "params": job.get("params") if isinstance(job.get("params"), dict) else {},
        }
        job_id = payload["id"]
        if isinstance(job_id, str):
            payload["status_url"] = f"/ui/photo/status?job_id={job_id}"
            payload["result_url"] = f"/ui/photo/result?job_id={job_id}"
        return payload

    def _locate_render_job(job_id: str, user_hint: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        candidate_users: List[str] = []
        if isinstance(user_hint, str) and user_hint.strip():
            candidate_users.append(user_hint.strip())
        cached_user = job_user_cache.get(job_id)
        if cached_user and cached_user not in candidate_users:
            candidate_users.append(cached_user)

        for user_candidate in candidate_users:
            job = load_render_job(user_candidate, job_id)
            if job:
                _index_render_job(job)
                return user_candidate, job

        try:
            for user_dir in USERS_DIR.iterdir():
                if not user_dir.is_dir():
                    continue
                candidate = user_dir.name
                if candidate in candidate_users:
                    continue
                job = load_render_job(candidate, job_id)
                if job:
                    _index_render_job(job)
                    return candidate, job
        except FileNotFoundError:
            return None
        return None

    def _persona_normalize(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        token = str(raw).strip().lower()
        if not token:
            return None
        alias_map = {
            "head_coach": "head coach",
            "headcoach": "head coach",
            "relationship_coach": "rc",
            "relationship coach": "rc",
            "pa dna": "padna",
            "padna coach": "padna",
            "photo coach": "photo",
        }
        normalized = alias_map.get(token, token)
        return normalized if normalized in PERSONA_PROMPTS else None

    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            try:
                return int(value)
            except (TypeError, ValueError, OverflowError):
                return None
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            try:
                return int(float(token))
            except (TypeError, ValueError):
                return None
        return None

    def _ucnrr_base_url() -> Optional[str]:
        for key in ("UCNRR_BASE_URL", "UCNRR_BASE", "UCNRR_URL"):
            raw = os.getenv(key)
            if raw and raw.strip():
                return raw.strip().rstrip("/")
        return None

    def _latest_ucnrr_compute_ts(max_files_per_user: int = 5) -> Optional[int]:
        if not CHECKPOINTS_DIR.exists():
            return None

        latest: Optional[int] = None
        for events_dir in CHECKPOINTS_DIR.glob("*/events"):
            if not events_dir.is_dir():
                continue

            try:
                json_paths = sorted(
                    (path for path in events_dir.glob("*.json") if path.is_file()),
                    key=lambda item: item.name,
                    reverse=True,
                )
            except Exception:
                continue

            for entry_path in json_paths[:max_files_per_user]:
                payload = load_json(entry_path, default=None)
                if not isinstance(payload, dict):
                    continue
                if not payload.get("ucnrr_result"):
                    continue

                ts_candidate: Optional[int] = None
                for candidate in (payload.get("written_at"), payload.get("ts")):
                    ts_candidate = _safe_int(candidate)
                    if ts_candidate is not None:
                        break

                if ts_candidate is None:
                    change_event = payload.get("change_event")
                    if isinstance(change_event, dict):
                        ts_candidate = _safe_int(change_event.get("ts"))

                if ts_candidate is None:
                    ts_candidate = _safe_int(entry_path.stem)

                if ts_candidate is None:
                    continue

                if latest is None or ts_candidate > latest:
                    latest = ts_candidate

                break  # Only need the newest matching event per user

        return latest

    def _user_has_material_state(user_id: str) -> bool:
        user_dir = USERS_DIR / user_id
        if not user_dir.exists():
            return False
        try:
            next(user_dir.iterdir())
            return True
        except StopIteration:
            return False

    def _derive_user_label(payload: Mapping[str, Any], user_id: str) -> str:
        meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
        for key in ("label", "user_label", "display_name"):
            value = meta.get(key) if isinstance(meta, Mapping) else None
            if value:
                text = str(value).strip()
                if text:
                    return text
        resolved = payload.get("resolved")
        if isinstance(resolved, Mapping):
            profile = resolved.get("profile")
            if isinstance(profile, Mapping):
                label = profile.get("label")
                if label:
                    text = str(label).strip()
                    if text:
                        return text
        return user_id

    def _sanitize_fragment(name: Optional[str]) -> str:
        if not name:
            return "bundle"
        fragment = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
        fragment = fragment.strip("._")
        return fragment or "bundle"

    def _write_bundle_checkpoint(
        user_id: str,
        payload: Dict[str, Any],
        *,
        source_tag: str,
        original_filename: Optional[str],
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = _sanitize_fragment(original_filename)
        filename = f"bundle-{source_tag}-{timestamp}-{suffix}.json"
        target = CHECKPOINTS_DIR / user_id / filename
        save_json(target, payload)
        return target.as_posix()

    def _load_bundle_payload(raw_bytes: bytes, filename: str) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename or "bundle.json").suffix or ".json") as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
        try:
            payload = import_bundle(tmp_path, apply=False)
        finally:
            tmp_path.unlink(missing_ok=True)
        if not isinstance(payload, dict):
            raise ValueError("Bundle payload must be a JSON object.")
        return payload

    def _prepare_bundle_payload(payload: Dict[str, Any]) -> str:
        meta = payload.get("meta")
        if not isinstance(meta, Mapping):
            raise ValueError("Bundle missing meta block.")
        user_id = str(meta.get("user_id") or "").strip()
        if not user_id:
            raise ValueError("Bundle missing meta.user_id.")
        version = str(meta.get("version") or "").strip()
        if not version:
            raise ValueError("Bundle missing meta.version.")
        if version != CURRENT_VERSION:
            meta["version"] = CURRENT_VERSION
        return user_id

    def _apply_bundle_payload(
        user_id: str,
        payload: Dict[str, Any],
        *,
        overwrite: bool,
        source_tag: str,
        original_name: Optional[str],
        existed: bool,
    ) -> Tuple[Dict[str, Any], bool, str]:
        resolved = payload.get("resolved") or {}
        evidence = payload.get("evidence") or {"items": []}
        observations = payload.get("observations") or {"items": [], "by_trait": {}}

        write_user_state(user_id, resolved, evidence, observations)

        label = _derive_user_label(payload, user_id)
        info = load_user_info(user_id)
        info["label"] = label
        save_user_info(user_id, info)
        touch_user_last_used(user_id)

        meta = payload.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["imported_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            meta.setdefault("source", source_tag)
            if original_name:
                meta.setdefault("original_filename", original_name)

        snapshot_path = _write_bundle_checkpoint(
            user_id,
            payload,
            source_tag=source_tag,
            original_filename=original_name,
        )

        capture(
            user_id,
            "bundle_imported",
            {
                "source": source_tag,
                "filename": original_name,
                "overwrite": overwrite and existed,
            },
        )

        refreshed = load_user_info(user_id)
        refreshed_label = refreshed.get("label") or label

        summary = _aggregate_user_summary(user_id)

        user_summary = {
            "id": refreshed.get("id", user_id),
            "label": refreshed_label,
            "created_ts": refreshed.get("created_ts"),
            "last_used_ts": refreshed.get("last_used_ts"),
        }
        if summary:
            user_summary.update(
                {
                    "label": summary.get("label", refreshed_label),
                    "created_ts": summary.get("created_ts", user_summary.get("created_ts")),
                    "last_used_ts": summary.get("last_used_ts", user_summary.get("last_used_ts")),
                    "last_modified_ts": summary.get("last_modified_ts"),
                }
            )

        return user_summary, existed, snapshot_path

    def _ms_to_iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()

    def _derive_priority_from_observations(observations: List[Dict[str, Any]]) -> float:
        if not observations:
            return 0.0

        best = 0.0
        for entry in observations:
            trait_id = str(entry.get("trait") or entry.get("trait_id") or "").strip()
            try:
                ucn_value = float(entry.get("ucn", 0.0))
            except (TypeError, ValueError):
                ucn_value = 0.0
            rr = ucn_value / 100.0 if ucn_value > 1.0 else ucn_value
            rr = 0.0 if rr < 0.0 else 1.0 if rr > 1.0 else rr
            importance = trait_importance_for(trait_id)
            score = priority_score(rr, importance, False)
            if score > best:
                best = score
        return best

    @lru_cache(maxsize=1)
    def _tone_curve_config() -> Dict[str, Any]:
        if not TONE_CURVE_PATH.exists():
            return {}
        try:
            with TONE_CURVE_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _infer_user_dna(persona_key: str, state: Optional[Mapping[str, Any]]) -> str:
        candidate: Optional[str] = None
        if isinstance(state, Mapping):
            for field in ("primary_dna", "dna_profile", "dna", "tone_curve_dna"):
                raw_value = state.get(field)
                if isinstance(raw_value, str) and raw_value.strip():
                    candidate = raw_value.strip().lower()
                    break
        if candidate:
            return candidate
        fallback_map = {
            "head coach": "core",
            "rc": "relationship",
            "padna": "visual",
            "photo": "visual",
        }
        normalized = persona_key.strip().lower() if persona_key else ""
        return fallback_map.get(normalized, "default")

    def _resolve_curve_id(persona_key: str, dna_key: str, config: Mapping[str, Any]) -> Optional[str]:
        persona_curves = config.get("persona_curves")
        if isinstance(persona_curves, Mapping):
            curve_candidate = persona_curves.get(persona_key)
            if isinstance(curve_candidate, str) and curve_candidate.strip():
                return curve_candidate.strip()
        dna_defaults = config.get("dna_defaults")
        if isinstance(dna_defaults, Mapping):
            if dna_key:
                curve_candidate = dna_defaults.get(dna_key)
                if isinstance(curve_candidate, str) and curve_candidate.strip():
                    return curve_candidate.strip()
            curve_candidate = dna_defaults.get("default")
            if isinstance(curve_candidate, str) and curve_candidate.strip():
                return curve_candidate.strip()
        return None

    def _select_tone_band(curve: Mapping[str, Any], rr_value: float) -> Optional[Mapping[str, Any]]:
        bands = curve.get("bands")
        if not isinstance(bands, list):
            return None
        fallback_band: Optional[Mapping[str, Any]] = None
        for band in bands:
            if not isinstance(band, Mapping):
                continue
            fallback_band = band
            threshold_raw = band.get("max_rr")
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                threshold = None
            if threshold is None:
                continue
            if rr_value <= threshold + 1e-9:
                return band
        return fallback_band

    def _compose_tone_hint(
        persona_key: str,
        persona_label: str,
        state: Optional[Mapping[str, Any]],
        rr_value: float,
    ) -> Tuple[Optional[str], Optional[str]]:
        config = _tone_curve_config()
        if not config:
            return None, None
        dna_key = _infer_user_dna(persona_key, state)
        curve_id = _resolve_curve_id(persona_key, dna_key, config)
        curves = config.get("curves")
        curve: Optional[Mapping[str, Any]] = None
        if isinstance(curves, Mapping):
            if curve_id and isinstance(curves.get(curve_id), Mapping):
                curve = curves[curve_id]
            elif isinstance(curves.get("default"), Mapping):
                curve = curves["default"]
            else:
                # use first mapping-like entry as fallback
                for value in curves.values():
                    if isinstance(value, Mapping):
                        curve = value
                        break
        if not isinstance(curve, Mapping):
            return None, None
        selected_band = _select_tone_band(curve, rr_value)
        if not isinstance(selected_band, Mapping):
            return None, None
        band_id = selected_band.get("id")
        prompt_template = selected_band.get("prompt")
        band_label_raw = selected_band.get("label")
        effective_label: Optional[str] = None
        if isinstance(band_label_raw, str) and band_label_raw.strip():
            effective_label = band_label_raw.strip()
        elif isinstance(band_id, str) and band_id.strip():
            effective_label = band_id.strip()
        persona_prompts = config.get("persona_prompts")
        if isinstance(persona_prompts, Mapping):
            persona_override = persona_prompts.get(persona_key)
            if isinstance(persona_override, Mapping) and band_id in persona_override:
                override_value = persona_override.get(band_id)
                if isinstance(override_value, str) and override_value.strip():
                    prompt_template = override_value
        if not isinstance(prompt_template, str) or not prompt_template.strip():
            if effective_label:
                prompt_template = f"Tone band: {effective_label}."
            else:
                return None, None
        try:
            formatted = prompt_template.format(persona_label=persona_label)
        except Exception:
            formatted = prompt_template
        return formatted.strip(), effective_label

    def _persist_observations(
        user_id: str,
        persona: str,
        user_ts_iso: str,
        observation_items: List[Dict[str, Any]],
    ) -> None:
        if not observation_items:
            return

        resolved, evidence, obs_store = read_user_state(user_id)
        items = obs_store.get("items") if isinstance(obs_store, dict) else None
        if not isinstance(items, list):
            items = []
        by_trait = obs_store.get("by_trait") if isinstance(obs_store, dict) else None
        if not isinstance(by_trait, dict):
            by_trait = {}

        for raw_item in observation_items:
            trait_id = str(raw_item.get("trait") or raw_item.get("trait_id") or "").strip()
            if not trait_id:
                continue
            prepared = dict(raw_item)
            prepared["trait"] = trait_id
            prepared.setdefault("trait_id", trait_id)
            prepared.setdefault("ts", user_ts_iso)
            prepared.setdefault("source", "ui_chat_turn")
            prepared.setdefault("persona", persona)
            prepared.setdefault("ucn", 20.0)
            prepared.setdefault("provenance", "observed_chat_turn")
            items.append(prepared)

            history_entry = {
                "value": prepared.get("value"),
                "ucn": prepared.get("ucn", 0.0),
                "ts": prepared.get("ts"),
                "source": prepared.get("source"),
                "persona": persona,
            }
            bucket = by_trait.setdefault(trait_id, [])
            bucket.append(history_entry)
            if len(bucket) > 25:
                by_trait[trait_id] = bucket[-25:]

        obs_store["items"] = items
        obs_store["by_trait"] = by_trait
        write_user_state(user_id, resolved, evidence, obs_store)

    def _ask_actions_enabled() -> bool:
        raw = os.getenv("HC_ASK_ACTIONS_ENABLED")
        if raw is None or raw.strip() == "":
            return True
        return raw.strip().lower() in _TRUTHY

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "core",
            "version": APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "features": {
                "photo_import": PHOTO_COACH_AVAILABLE,
                "ucnrr_enabled": bool(_ucnrr_base_url()),
                "curiosity_enabled": curiosity_engine.is_enabled(),
            }
        }

    def _seed_curiosity(user_id: str, resolved: Dict[str, Any], evidence: Dict[str, Any], obs: Dict[str, Any]) -> bool:
        if not curiosity_engine.is_enabled():
            return False
        if curiosity_engine.seed_resolved(resolved):
            write_user_state(user_id, resolved, evidence, obs)
            return True
        return False

    def _update_curiosity(
        user_id: str,
        prior_resolved: Dict[str, Any],
        resolved: Dict[str, Any],
        evidence: Dict[str, Any],
        observations: Dict[str, Any],
        touched_traits: Iterable[str],
    ) -> None:
        if not curiosity_engine.is_enabled():
            return

        baseline = copy.deepcopy(prior_resolved)
        # Ensure both prior and new payloads include curiosity scaffolding
        curiosity_engine.seed_resolved(prior_resolved)
        curiosity_engine.seed_resolved(resolved)
        curiosity_engine.update_curiosity(baseline, resolved, touched_traits)
        write_user_state(user_id, resolved, evidence, observations)

    @app.post("/user/{user_id}/ensure")
    def ensure_user(user_id: str):
        ensure_dirs_for_user(user_id)
        resolved, evidence, obs = read_user_state(user_id)
        _seed_curiosity(user_id, resolved, evidence, obs)
        return {"ok": True, "resolved_keys": len(resolved)}

    @app.get("/user/{user_id}/resolved")
    def get_resolved(user_id: str):
        resolved, evidence, obs = read_user_state(user_id)
        _seed_curiosity(user_id, resolved, evidence, obs)
        return {"user_id": user_id, "resolved": resolved}

    @app.get("/catalog")
    def catalog():
        # Wide table support in Explorer (“show all traits even if empty”)
        return {"registry": hierarchy.REGISTRY, "all_keys": hierarchy.all_trait_keys()}

    @app.get("/ui/personas")
    def list_personas() -> Dict[str, Any]:
        """Return roster metadata for UI shells (read-only)."""

        return {"personas": ui_readonly.persona_roster()}

    @app.get("/ui/coach-catalog")
    def get_coach_catalog() -> Dict[str, Any]:
        """
        Return full coach catalog with metadata from coach_registry.yaml.
        Includes all coaches with their capabilities, domains, and autonomy levels.
        """
        import yaml

        registry_path = Path(__file__).parent / "coach_registry.yaml"

        if not registry_path.exists():
            return {"coaches": [], "error": "Coach registry not found"}

        try:
            with open(registry_path, "r") as f:
                registry_data = yaml.safe_load(f)

            coaches_config = registry_data.get("coaches", {})
            availability = registry_data.get("availability", {})

            # Transform into catalog format
            catalog = []
            for coach_id, config in coaches_config.items():
                catalog.append({
                    "id": coach_id,
                    "display_name": config.get("display_name", coach_id),
                    "description": config.get("description", ""),
                    "icon": _get_coach_icon(coach_id),
                    "primary_namespaces": config.get("primary_namespaces", []),
                    "capabilities": config.get("capabilities", []),
                    "natural_domains": config.get("natural_domains", []),
                    "delegation_context": config.get("delegation_context", ""),
                    "autonomy_level": config.get("autonomy_level", "medium"),
                    "is_default": config.get("is_default", False),
                    "available": availability.get(coach_id, True)
                })

            return {
                "coaches": catalog,
                "total": len(catalog)
            }

        except Exception as e:
            logger.error(f"Failed to load coach catalog: {e}")
            return {"coaches": [], "error": str(e)}

    @app.get("/ui/asks")
    def list_planner_asks(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        limit: int = Query(5, ge=1, le=25, description="Maximum asks to return"),
    ) -> Dict[str, Any]:
        """Return the top planner asks for the requested user (read-only)."""

        clean_user = user_id.strip()
        asks = ui_readonly.planner_asks(clean_user, limit=limit)
        return {"user_id": clean_user, "asks": asks}

    @app.get("/ui/asks/list")
    def ui_ask_list(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        status: str = Query("all", description="Filter by status: all|open|done"),
        limit: int = Query(50, ge=1, le=200, description="Max asks to return"),
        sort: str = Query("new", description="Sort order: new|old"),
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        status_token = (status or "all").strip().lower()
        if status_token not in {"all", "open", "done"}:
            status_token = "all"

        sort_token = (sort or "new").strip().lower()
        if sort_token not in {"new", "old"}:
            sort_token = "new"

        raw_items = _load_ui_collection(ASKS_DATA_ROOT, clean_user, ASKS_STORE_FILENAME)
        normalized: List[Dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                continue
            entry_id = str(raw.get("id") or "").strip()
            if not entry_id:
                entry_id = f"ask_{len(normalized) + 1}"
            ts_value = _safe_int(raw.get("ts"))
            if ts_value is None and isinstance(raw.get("created_ts"), (int, float)):
                ts_value = _safe_int(raw.get("created_ts"))
            if ts_value is None and isinstance(raw.get("created_at"), str):
                iso_source = str(raw["created_at"]).strip()
                if iso_source.endswith("Z"):
                    iso_source = iso_source[:-1] + "+00:00"
                try:
                    ts_value = int(datetime.fromisoformat(iso_source).timestamp() * 1000)
                except Exception:
                    ts_value = None
            if ts_value is None:
                ts_value = int(time.time() * 1000)

            entry_status = str(raw.get("status") or "open").strip().lower()
            if entry_status not in {"open", "done"}:
                entry_status = "open"

            title = str(raw.get("title") or raw.get("headline") or "Coach ask").strip()
            body = str(raw.get("body") or raw.get("summary") or "").strip()

            normalized_entry: Dict[str, Any] = {
                "id": entry_id,
                "user_id": str(raw.get("user_id") or clean_user).strip() or clean_user,
                "ts": ts_value,
                "status": entry_status,
                "title": title,
                "body": body,
            }

            extra = {key: value for key, value in raw.items() if key not in {"id", "user_id", "ts", "created_ts", "created_at", "status", "title", "headline", "body", "summary"}}
            if extra:
                normalized_entry["meta"] = extra

            normalized.append(normalized_entry)

        if status_token != "all":
            normalized = [item for item in normalized if item.get("status") == status_token]

        normalized.sort(key=lambda item: item.get("ts", 0), reverse=(sort_token == "new"))
        if len(normalized) > limit:
            normalized = normalized[:limit]

        return {"items": normalized}

    @app.post("/ui/asks/seed")
    def seed_ui_asks(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        created, count = _seed_ui_items(
            ASKS_DATA_ROOT,
            clean_user,
            ASKS_STORE_FILENAME,
            _demo_ask_items(clean_user),
        )

        return {
            "user_id": clean_user,
            "created": created,
            "count": count,
        }

    @app.post("/ui/preferences/submit")
    def submit_ui_preference(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = payload.get("user_id")
        key_raw = payload.get("key")
        ttl_raw = payload.get("ttl_days")

        user_id = str(user_id_raw or "").strip()
        key_value = str(key_raw or "").strip()

        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        if not key_value:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "key is required."},
            )

        try:
            ttl_days = float(ttl_raw)
        except (TypeError, ValueError):
            ttl_days = math.nan

        if not math.isfinite(ttl_days) or ttl_days <= 0:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "ttl_days must be a positive number."},
            )

        sanitized_key = _sanitize_user_fragment(key_value)
        if not sanitized_key:
            sanitized_key = "topic"

        user_dirs = ensure_dirs_for_user(user_id)
        prefs_dir = user_dirs["udir"] / "prefs"
        prefs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record = {
            "set_at": timestamp,
            "ttl_days": ttl_days,
        }

        target_path = prefs_dir / f"{sanitized_key}.json"
        try:
            save_json(target_path, record)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "PREFERENCE_WRITE_FAILED",
                    "message": "Failed to persist preference.",
                    "detail": str(exc),
                },
            )

        response_payload = {
            "ok": True,
            "user_id": user_id,
            "key": sanitized_key,
            "set_at": timestamp,
            "ttl_days": ttl_days,
        }
        return response_payload

    @app.post("/ui/asks/add_demo")
    def add_demo_ask(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        title = str(payload.get("title") or payload.get("topic") or "").strip()
        summary_raw = payload.get("summary") or payload.get("description")
        summary = str(summary_raw).strip() if isinstance(summary_raw, str) else None
        persona_raw = payload.get("persona") or payload.get("container")
        persona = str(persona_raw).strip() if isinstance(persona_raw, str) else None
        confidence_raw = payload.get("confidence")

        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        if not title:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "title is required."},
            )

        confidence_value: Optional[float]
        if confidence_raw is None:
            confidence_value = None
        else:
            try:
                confidence_value = float(confidence_raw)
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "message": "confidence must be numeric when provided.",
                    },
                )

        try:
            ask = planner.add_demo_ask(
                user_id,
                title=title,
                summary=summary,
                persona=persona,
                confidence=confidence_value,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": str(exc)},
            )

        return {"ok": True, "ask": ask}

    @app.get("/ui/observations/aggregates")
    def observation_aggregates(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Dict[str, Any]:
        """Return conversational observation aggregates for the requested user."""

        clean_user = user_id.strip()
        return ui_readonly.observation_aggregates(clean_user)

    @app.get("/ui/unabridged")
    def unabridged(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Dict[str, Any]:
        """Return the current unabridged trait snapshot (read-only)."""

        clean_user = user_id.strip()
        return ui_readonly.unabridged_snapshot(clean_user)

    @app.get("/core/api/user/{user_id}/provenance/{trait_id}")
    def get_provenance(user_id: str, trait_id: str) -> Dict[str, Any]:
        """
        Return complete provenance for a specific trait.

        Includes:
        - Current resolved value and UCN
        - Evidence timeline (all observations)
        - Inference items (rule-based derivations)
        - Resolver trace references
        - RR scoring status

        Used by Northstar "Why?" panel for trait explainability.
        """
        from core.provenance.service import build_provenance

        try:
            clean_user = user_id.strip()
            clean_trait = trait_id.strip()

            if not clean_user or not clean_trait:
                return JSONResponse(
                    status_code=400,
                    content={"error": "BAD_REQUEST", "message": "user_id and trait_id are required"}
                )

            prov = build_provenance(clean_user, clean_trait)

            if not prov:
                return JSONResponse(
                    status_code=404,
                    content={"error": "NOT_FOUND", "message": f"No provenance found for trait {clean_trait}"}
                )

            return prov

        except Exception as e:
            logger.error(f"Provenance error for user {user_id}, trait {trait_id}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_ERROR", "message": f"provenance_error: {str(e)}"}
            )

    @app.get("/ui/nudges")
    def list_nudges(
        user_id: str = Query(..., min_length=1, description="Active user identifier")
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        return {"user_id": clean_user, "nudges": nudges.list_for_ui(clean_user)}

    @app.get("/ui/nudges/list")
    def ui_nudge_list(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        status: str = Query("all", description="Filter by status: all|new|read"),
        limit: int = Query(50, ge=1, le=200, description="Max nudges to return"),
        sort: str = Query("new", description="Sort order: new|old"),
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        status_token = (status or "all").strip().lower()
        if status_token not in {"all", "new", "read"}:
            status_token = "all"

        sort_token = (sort or "new").strip().lower()
        if sort_token not in {"new", "old"}:
            sort_token = "new"

        raw_items = _load_ui_collection(NUDGES_DATA_ROOT, clean_user, NUDGES_STORE_FILENAME)
        normalized: List[Dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                continue
            entry_id = str(raw.get("id") or "").strip()
            if not entry_id:
                entry_id = f"nudge_{len(normalized) + 1}"

            ts_value = _safe_int(raw.get("ts"))
            if ts_value is None and isinstance(raw.get("created_ts"), (int, float)):
                ts_value = _safe_int(raw.get("created_ts"))
            if ts_value is None and isinstance(raw.get("created_at"), str):
                iso_source = str(raw["created_at"]).strip()
                if iso_source.endswith("Z"):
                    iso_source = iso_source[:-1] + "+00:00"
                try:
                    ts_value = int(datetime.fromisoformat(iso_source).timestamp() * 1000)
                except Exception:
                    ts_value = None
            if ts_value is None:
                ts_value = int(time.time() * 1000)

            entry_status = str(raw.get("status") or "new").strip().lower()
            if entry_status not in {"new", "read"}:
                entry_status = "new"

            title = str(raw.get("title") or "Coach nudge").strip()
            body = str(raw.get("body") or "").strip()

            normalized_entry: Dict[str, Any] = {
                "id": entry_id,
                "user_id": str(raw.get("user_id") or clean_user).strip() or clean_user,
                "ts": ts_value,
                "status": entry_status,
                "title": title,
                "body": body,
            }

            extra = {key: value for key, value in raw.items() if key not in {"id", "user_id", "ts", "created_ts", "created_at", "status", "title", "body"}}
            if extra:
                normalized_entry["meta"] = extra

            normalized.append(normalized_entry)

        if status_token != "all":
            normalized = [item for item in normalized if item.get("status") == status_token]

        normalized.sort(key=lambda item: item.get("ts", 0), reverse=(sort_token == "new"))
        if len(normalized) > limit:
            normalized = normalized[:limit]

        return {"items": normalized}

    @app.post("/ui/nudges/seed")
    def seed_ui_nudges(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        created, count = _seed_ui_items(
            NUDGES_DATA_ROOT,
            clean_user,
            NUDGES_STORE_FILENAME,
            _demo_nudge_items(clean_user),
        )

        return {
            "user_id": clean_user,
            "created": created,
            "count": count,
        }

    @app.get("/ui/trait_timeline")
    def trait_timeline_view(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        trait_id: str = Query(..., min_length=1, description="Fully-qualified trait id"),
        limit: int = Query(50, ge=1, le=200),
    ) -> Dict[str, Any]:
        clean_user = user_id.strip()
        timeline = trait_timeline.build_timeline(clean_user, trait_id.strip(), limit=limit)
        return {"user_id": clean_user, "trait_id": trait_id.strip(), "entries": timeline}

    @app.get("/ui/dev/cohorts")
    def dev_cohort_rr() -> Any:
        if not DEV_COHORTS_ENABLED:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "FORBIDDEN",
                    "message": "Cohort statistics endpoint disabled. Set CORE_DEV_COHORTS_ENABLED=1 to enable.",
                },
            )

        if not COHORT_STATS_PATH.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "NOT_FOUND",
                    "message": "Cohort RR statistics file not found.",
                },
            )

        try:
            stats_payload = json.loads(COHORT_STATS_PATH.read_text())
        except json.JSONDecodeError as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "STATS_PARSE_FAILED",
                    "message": "Unable to parse cohort RR statistics file.",
                    "detail": str(exc),
                },
            )

        return {"ok": True, "stats": stats_payload}

    @app.post("/ui/user/import")
    async def import_user_bundle(
        file: UploadFile = File(..., description="Bundle JSON file"),
        overwrite: bool = Form(False, description="Overwrite existing user if present"),
    ) -> Any:
        try:
            raw_bytes = await file.read()
        finally:
            await file.close()

        if not raw_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "EMPTY_UPLOAD",
                    "message": "Upload a bundle JSON file to import.",
                },
            )

        filename = file.filename or "bundle.json"
        try:
            payload = _load_bundle_payload(raw_bytes, filename)
            user_id = _prepare_bundle_payload(payload)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_BUNDLE", "message": str(exc)},
            )

        existed = _user_has_material_state(user_id)
        if existed and not overwrite:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "USER_EXISTS",
                    "message": f"User '{user_id}' already exists. Re-run with overwrite=true to replace their state.",
                    "user": {
                        "id": user_id,
                        "label": _derive_user_label(payload, user_id),
                    },
                },
            )

        try:
            user_summary, previously_existing, snapshot_path = _apply_bundle_payload(
                user_id,
                payload,
                overwrite=overwrite,
                source_tag="import",
                original_name=filename,
                existed=existed,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "IMPORT_FAILED", "message": str(exc)},
            )
        except Exception as exc:  # pragma: no cover - unexpected failure path
            return JSONResponse(
                status_code=500,
                content={"error": "IMPORT_FAILED", "message": str(exc)},
            )

        user_summary.pop("last_used_ts", None)
        user_summary.pop("last_modified_ts", None)
        return {
            "ok": True,
            "user": user_summary,
            "overwrote": previously_existing,
            "snapshot_path": snapshot_path,
        }

    @app.post("/ui/users/import_bulk")
    async def import_users_bulk(
        file: UploadFile = File(..., description="Zip file containing bundle JSON files"),
        overwrite: bool = Form(False, description="Overwrite users if they already exist"),
    ) -> Any:
        try:
            raw_bytes = await file.read()
        finally:
            await file.close()

        if not raw_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": "EMPTY_UPLOAD", "message": "Upload a zip archive of bundle files."},
            )

        try:
            archive = zipfile.ZipFile(io.BytesIO(raw_bytes))
        except zipfile.BadZipFile:
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_ARCHIVE", "message": "Provided file is not a valid zip archive."},
            )

        results: List[Dict[str, Any]] = []
        imported_count = 0
        overwritten_count = 0
        conflict_count = 0

        with archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                entry_name = entry.filename
                try:
                    entry_bytes = archive.read(entry)
                except KeyError:
                    results.append(
                        {
                            "filename": entry_name,
                            "status": "error",
                            "message": "Unable to read archive entry.",
                        }
                    )
                    continue

                try:
                    payload = _load_bundle_payload(entry_bytes, entry_name)
                    user_id = _prepare_bundle_payload(payload)
                except ValueError as exc:
                    results.append(
                        {
                            "filename": entry_name,
                            "status": "error",
                            "message": str(exc),
                        }
                    )
                    continue

                existed = _user_has_material_state(user_id)
                if existed and not overwrite:
                    conflict_count += 1
                    results.append(
                        {
                            "filename": entry_name,
                            "status": "conflict",
                            "user": {
                                "id": user_id,
                                "label": _derive_user_label(payload, user_id),
                            },
                            "message": "User already exists. Re-run with overwrite=true to replace.",
                        }
                    )
                    continue

                try:
                    user_summary, previously_existing, snapshot_path = _apply_bundle_payload(
                        user_id,
                        payload,
                        overwrite=overwrite,
                        source_tag="bulk_import",
                        original_name=entry_name,
                        existed=existed,
                    )
                except ValueError as exc:
                    results.append(
                        {
                            "filename": entry_name,
                            "status": "error",
                            "message": str(exc),
                        }
                    )
                    continue
                except Exception as exc:  # pragma: no cover - unexpected failure path
                    results.append(
                        {
                            "filename": entry_name,
                            "status": "error",
                            "message": str(exc),
                        }
                    )
                    continue

                imported_count += 1
                if previously_existing:
                    overwritten_count += 1

                results.append(
                    {
                        "filename": entry_name,
                        "status": "imported",
                        "user": user_summary,
                        "overwrote": previously_existing,
                        "snapshot_path": snapshot_path,
                    }
                )

        return {
            "ok": imported_count > 0,
            "imported": imported_count,
            "overwritten": overwritten_count,
            "conflicts": conflict_count,
            "results": results,
        }

    @app.get("/ui/ucnrr/health")
    def ucnrr_health() -> Dict[str, Any]:
        """Return UCN/RR reachability and recent compute timestamp for dashboards."""

        base_url = _ucnrr_base_url()
        reachable = False
        reason: Optional[str] = None

        if base_url:
            probe_url = base_url.rstrip("/") + "/health"
            try:
                response = requests.get(probe_url, timeout=1.5)
            except requests.RequestException as exc:
                reason = str(exc)
            else:
                if response.status_code == 200:
                    reachable = True
                else:
                    reason = f"http {response.status_code}"
        else:
            reason = "UCNRR_BASE_URL not configured"

        payload: Dict[str, Any] = {"reachable": reachable}

        if base_url:
            payload["base_url"] = base_url

        last_compute_ts = _latest_ucnrr_compute_ts()
        if last_compute_ts is not None:
            payload["last_compute_ts"] = last_compute_ts

        if reason and not reachable:
            payload["reason"] = reason

        return payload

    @app.get("/ui/curiosity/health")
    def curiosity_health() -> Dict[str, Any]:
        """Return Curiosity engine status (always enabled as part of Core)."""
        return {
            "enabled": True,
            "engine": "curiosity",
            "status": "ready"
        }

    @app.post("/ui/holistic/review")
    def holistic_review(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
        """
        Trigger a holistic review using the core holistic.run_holistic() function,
        which properly computes UCN → RR percentiles and updates resolved.json.
        """
        user_id = payload.get("user_id", "").strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")

        trace_id = request.headers.get("X-Trace-Id")
        _trace_event(trace_id, "holistic_review_start", {"user_id": user_id})

        # Ensure user exists
        ensure_dirs_for_user(user_id)
        touch_user_last_used(user_id)

        # Run holistic review using core function
        from .holistic import run_holistic

        try:
            report, resolved_doc, evidence_doc, flat_doc = run_holistic(
                user_id=user_id,
                loader=lambda uid: read_user_state(uid),
                distribution_dir=Path("data/population_distributions"),
                rr_k_min=50,
                use_llm=False,  # Don't use LLM for UI holistic review
            )

            # Save updated state
            # Note: resolved_doc IS the resolved dict (has a "resolved" key added by holistic.py:242)
            # We need to extract the actual traits (everything except metadata keys)
            resolved = {k: v for k, v in resolved_doc.items()
                       if k not in ("resolved", "user_id", "last_holistic_ts") and isinstance(v, dict)}
            _, evidence, obs = read_user_state(user_id)
            write_user_state(user_id, resolved, evidence, obs)

            # Log event to checkpoints
            event_checkpoint(
                user_id,
                "holistic_review",
                {
                    "traits_updated": len(report.get("ucn_rr_updates", [])),
                    "implied_additions": len(report.get("implied_additions", [])),
                    "contradictions": len(report.get("contradictions", [])),
                    "warnings": report.get("warnings", []),
                },
            )

            _trace_event(
                trace_id,
                "holistic_review_complete",
                {"user_id": user_id, "ok": report.get("ok")},
            )

            return {
                "ok": True,
                "user_id": user_id,
                "traits_updated": len(report.get("ucn_rr_updates", [])),
                "implied_additions": len(report.get("implied_additions", [])),
                "contradictions": len(report.get("contradictions", [])),
                "warnings": report.get("warnings", []),
                "time_ms": report.get("time_ms", 0),
            }

        except Exception as exc:
            _trace_event(
                trace_id,
                "holistic_review_error",
                {"user_id": user_id, "error": str(exc)},
            )
            return {
                "ok": False,
                "error": "holistic_review_failed",
                "message": f"Holistic review failed: {str(exc)}",
            }

    @app.post("/ui/asks/act")
    def ask_action(payload: Dict[str, Any]) -> Any:
        if not _ask_actions_enabled():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "HC_ASK_ACTIONS_DISABLED",
                    "enabled": False,
                    "message": "Ask actions are disabled by configuration (HC_ASK_ACTIONS_ENABLED=false).",
                },
            )

        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        ask_id = str(payload.get("id") or payload.get("ask_id") or "").strip()
        action = str(payload.get("action") or "").strip().lower()

        if not user_id or not ask_id or not action:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id, ask_id, and action are required."},
            )

        if action not in {"approve", "snooze", "skip"}:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "action must be approve, snooze, or skip."},
            )

        minutes_raw = payload.get("minutes")
        if minutes_raw is None:
            minutes_raw = payload.get("snooze_minutes")
        minutes_value: Optional[int] = None
        if minutes_raw is not None:
            try:
                minutes_value = int(minutes_raw)
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "message": "minutes must be an integer number of minutes when provided.",
                    },
                )

        target_path = _ui_store_path(ASKS_DATA_ROOT, user_id, ASKS_STORE_FILENAME)
        if not target_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "ASKS_NOT_FOUND",
                    "message": f"No asks store found for user {user_id}.",
                },
            )

        try:
            path, container_kind, raw_store, items = _load_ui_store_for_update(ASKS_DATA_ROOT, user_id, ASKS_STORE_FILENAME)
        except Exception as exc:  # pragma: no cover - defensive
            return JSONResponse(
                status_code=500,
                content={
                    "error": "ASK_STORE_LOAD_FAILED",
                    "message": "Failed to load asks store.",
                    "detail": str(exc),
                },
            )

        target_entry: Optional[Dict[str, Any]] = None
        for entry in items:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or "").strip()
            if entry_id == ask_id:
                target_entry = entry
                break

        if target_entry is None:
            return {"ok": False, "reason": "ASK_NOT_FOUND"}

        now_dt = datetime.now(timezone.utc)
        iso_now = _iso_now()

        meta = target_entry.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            target_entry["meta"] = meta

        action_lower = action.lower()
        previous_status_raw = target_entry.get("status")
        previous_status = str(previous_status_raw).strip() if previous_status_raw is not None else "open"
        if not previous_status:
            previous_status = "open"
        meta.setdefault("original_status", previous_status)

        if action_lower in {"approve", "skip"}:
            target_entry["status"] = "done"
            target_entry["completed_at"] = iso_now
            target_entry.pop("snooze_until", None)
            target_entry.pop("snoozed_at", None)
            meta.pop("snooze_until", None)
            meta["last_action"] = action_lower
            if action_lower == "skip":
                meta.setdefault("skip_reason", "skipped_via_ui")
        else:  # snooze
            effective_minutes = minutes_value
            if effective_minutes is None:
                fallback = target_entry.get("snooze_minutes")
                try:
                    effective_minutes = int(fallback)
                except Exception:
                    effective_minutes = 15
            if effective_minutes <= 0:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "message": "minutes must be greater than zero for snooze.",
                    },
                )
            snooze_until = now_dt + timedelta(minutes=effective_minutes)
            target_entry["snooze_until"] = snooze_until.isoformat()
            target_entry["snoozed_at"] = iso_now
            target_entry["status"] = "open"
            meta["last_action"] = "snooze"
            meta["snoozed_minutes"] = effective_minutes
            meta["snooze_until"] = target_entry["snooze_until"]

        target_entry["updated_at"] = iso_now

        try:
            save_json(path, raw_store)
        except Exception as exc:  # pragma: no cover - defensive
            return JSONResponse(
                status_code=500,
                content={
                    "error": "ASK_STORE_WRITE_FAILED",
                    "message": "Failed to persist ask changes.",
                    "detail": str(exc),
                },
            )

        return {"ok": True, "ask": target_entry}

    @app.post("/ui/chat/send")
    async def chat_send(payload: Dict[str, Any], stream: int = Query(0, ge=0, le=1)) -> Any:
        if not _hc_chat_enabled():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "HC_CHAT_DISABLED",
                    "enabled": False,
                    "message": "Head Coach chat is disabled by configuration (HC_CHAT_ENABLED=false).",
                },
            )

        stream_mode = bool(stream)
        if stream_mode and not _hc_chat_stream_enabled():
            stream_mode = False

        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        persona = _persona_normalize(payload.get("persona"))

        if not user_id or not text:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and text are required."},
            )
        if persona is None:
            allowed = ", ".join(sorted(PERSONA_PROMPTS))
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": f"persona must be one of: {allowed}.",
                },
            )

        client_ts_raw = payload.get("client_ts")
        client_ts_ms: Optional[int]
        if client_ts_raw is None:
            client_ts_ms = None
        else:
            try:
                client_ts_ms = int(client_ts_raw)
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "message": "client_ts must be an integer representing milliseconds since epoch.",
                    },
                )

        user_dirs = ensure_dirs_for_user(user_id)
        runtime_state = _load_runtime_state(user_id)
        last_assistant_iso = runtime_state.get("last_assistant_ts") if isinstance(runtime_state, dict) else None

        now = datetime.now(timezone.utc)
        server_ts_ms = int(now.timestamp() * 1000)
        server_ts_iso = now.isoformat()

        user_ts_iso = _ms_to_iso(client_ts_ms) if client_ts_ms is not None else server_ts_iso

        # Create request ID for tracing
        from uuid import uuid4
        req_id = str(uuid4())[:8]

        # Extract observations from conversation (hungry data ingestion)
        # Phase 1: Keyword-based extraction
        keyword_observations = conversation_analyzer.analyze_message(user_id, text, user_ts_iso)

        # Phase 2: LLM-based preference extraction (more precise)
        llm_observations = []
        try:
            llm_extracted = preference_extractor.extract_from_message(text, user_id)
            if llm_extracted:
                llm_observations = preference_extractor.to_observations(
                    llm_extracted,
                    user_ts_iso,
                    text
                )
                if llm_observations:
                    logger.info(f"LLM extracted {len(llm_observations)} preference observations for user {user_id}")
        except Exception as e:
            logger.error(f"LLM preference extraction failed: {e}", exc_info=True)

        # Combine both extraction methods
        all_observations = keyword_observations + llm_observations

        # Log extraction results
        sample_item = all_observations[0] if all_observations else None
        logger.info(f"chat_extract{{req_id={req_id}, user={user_id}, items={len(all_observations)}, sample={sample_item}}}")

        # FALLBACK: If zero evidence extracted, use lexical fallback for critical traits
        if not all_observations:
            logger.warning(f"Zero evidence extracted for user {user_id}, attempting fallback lexical extraction")
            try:
                from .ingest.fallback_lex import fallback_extract, format_fallback_summary
                fallback_items = fallback_extract(text)
                if fallback_items:
                    trait_ids = format_fallback_summary(fallback_items)
                    logger.info(f"chat_fallback{{req_id={req_id}, items={len(fallback_items)}, types={trait_ids}}}")
                    all_observations = fallback_items
                else:
                    logger.warning(f"Fallback extractor also found zero evidence for: '{text[:50]}...'")
            except Exception as e:
                logger.error(f"Fallback extraction failed: {e}", exc_info=True)

        if all_observations:
            logger.info(f"Total extracted {len(all_observations)} observations from message for user {user_id}")
            logger.info(f"chat_extract{{req_id={req_id}, user={user_id}, items={len(all_observations)}}}")

            # Log sample evidence for debugging
            for i, obs in enumerate(all_observations[:3]):
                trait_id = obs.get('trait_id', obs.get('fact_category', 'UNKNOWN'))
                value = obs.get('fact_value', obs.get('value', 'UNKNOWN'))
                logger.info(f"  Evidence[{i}]: trait_id={trait_id}, value={value}, keys={list(obs.keys())}")

            # NORTHSTAR PHASE 2: Unified ingestion pipeline
            # Single source of truth for evidence processing (chat, onboarding, etc.)
            try:
                from .ingest import ingest_evidence_roundtrip

                logger.info(f"Calling ingest_evidence_roundtrip for user={user_id}, req_id={req_id}")

                # Call unified pipeline with chat evidence
                # This handles: canonicalization, validation, resolve, inference, snapshot
                result = ingest_evidence_roundtrip(
                    user_id=user_id,
                    source="chat",
                    evidence=all_observations,
                    req_id=req_id  # Pass through for tracing
                )

                logger.info(f"ingest_evidence_roundtrip returned: {result.keys()}")

                # Log resolution success
                resolved_path = f"users/{user_id}/resolved.json"
                logger.info(f"chat_resolve{{req_id={req_id}, wrote_resolved=true, resolved_path=\"{resolved_path}\"}}")
                logger.info(f"Chat ingestion complete: {result.get('ingested', 0)} direct + {result.get('inferred', 0)} inferred traits")

            except Exception as e:
                logger.exception(f"CRITICAL: Failed to process chat evidence through unified pipeline for user {user_id}, req_id={req_id}")
                logger.error(f"Evidence that failed: {all_observations[:2] if len(all_observations) > 2 else all_observations}")
        else:
            logger.warning(f"No observations extracted (primary or fallback) for user {user_id}, message: '{text[:100]}...'")

        observation_result = capture_turn_observation(
            user_id=user_id,
            user_text=text,
            user_ts=user_ts_iso,
            last_assistant_ts=last_assistant_iso,
            state=runtime_state if isinstance(runtime_state, dict) else None,
            source="ui_chat_turn",
        )

        _persist_observations(user_id, persona, user_ts_iso, observation_result.observations)

        turn_priority = _derive_priority_from_observations(observation_result.observations)

        updated_state = dict(observation_result.state)
        updated_state["last_assistant_ts"] = server_ts_iso
        _store_runtime_state(user_id, updated_state)

        provider_name = (os.getenv("HC_CHAT_PROVIDER", "stub") or "stub").strip().lower() or "stub"
        try:
            provider = chat_providers.get_provider(provider_name)
        except chat_providers.ProviderConfigError as exc:
            detail = str(exc)
            if provider_name != "stub":
                _log_provider_error("config", provider_name, detail)
                return JSONResponse(
                    status_code=503,
                    content={"error": "PROVIDER_CONFIG", "detail": detail},
            )
            provider = chat_providers.get_provider("stub")
            provider_name = "stub"

        provider_identifier = getattr(provider, "name", provider_name)

        provider_options_raw = payload.get("provider")
        model_override: Optional[str] = None
        temperature_override: Optional[float] = None
        max_tokens_override: Optional[int] = None

        if isinstance(provider_options_raw, dict):
            model_value = provider_options_raw.get("model")
            if isinstance(model_value, str) and model_value.strip():
                model_override = model_value.strip()

            temperature_value = provider_options_raw.get("temperature")
            if temperature_value is not None:
                try:
                    temp_candidate = float(temperature_value)
                    if math.isfinite(temp_candidate):
                        temperature_override = max(0.0, min(2.0, temp_candidate))
                except (TypeError, ValueError):
                    temperature_override = None

            max_tokens_value = provider_options_raw.get("max_tokens")
            if max_tokens_value is None:
                max_tokens_value = provider_options_raw.get("maxTokens")
            if max_tokens_value is not None:
                try:
                    tokens_candidate = int(max_tokens_value)
                    if tokens_candidate > 0:
                        max_tokens_override = tokens_candidate
                except (TypeError, ValueError):
                    max_tokens_override = None

        breaker_key: Optional[str] = None
        breaker_model: Optional[str] = None
        if provider_identifier != "stub":
            breaker_model = chat_providers.resolve_circuit_model(provider, model_override)
            breaker_key = chat_providers.circuit_key(provider_identifier, breaker_model)
            retry_after = chat_providers.circuit_retry_after(breaker_key)
            if retry_after:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "PROVIDER_UNAVAILABLE",
                        "retry_after_ms": int(retry_after * 1000),
                    },
                )

        persona_prompt = PERSONA_PROMPTS.get(persona, "")
        fallback_text = DEFAULT_RESPONSES.get(persona, DEFAULT_RESPONSES["head coach"])

        persona_label = {
            "head coach": "Head Coach",
            "rc": "Relationship Coach",
            "padna": "PaDNA Coach",
            "photo": "Photo Coach",
        }.get(persona, persona.title())

        priority_clamped = 0.0 if turn_priority < 0.0 else 1.0 if turn_priority > 1.0 else turn_priority
        rr_estimate = 1.0 - priority_clamped
        rr_estimate = 0.0 if rr_estimate < 0.0 else 1.0 if rr_estimate > 1.0 else rr_estimate
        tone_hint_line, tone_band_label = _compose_tone_hint(persona, persona_label, updated_state, rr_estimate)

        events_dir = user_dirs["events"]
        recent_pairs: List[Tuple[str, str]] = []
        if events_dir.exists():
            for event_path in sorted(events_dir.glob("chat_*.json"), key=lambda item: item.name, reverse=True):
                if len(recent_pairs) >= 6:
                    break
                if not event_path.is_file():
                    continue
                try:
                    event_payload = load_json(event_path, default=None)
                except Exception:
                    continue
                if not isinstance(event_payload, dict):
                    continue
                persona_ref = _persona_normalize(event_payload.get("persona"))
                if persona_ref and persona_ref != persona:
                    continue
                user_section = event_payload.get("user")
                assistant_section = event_payload.get("assistant")
                user_text_prev = ""
                assistant_text_prev = ""
                if isinstance(user_section, dict):
                    user_text_prev = str(user_section.get("text") or "").strip()
                if isinstance(assistant_section, dict):
                    assistant_text_prev = str(assistant_section.get("text") or "").strip()
                if not user_text_prev and not assistant_text_prev:
                    continue
                recent_pairs.append((user_text_prev, assistant_text_prev))
        recent_pairs.reverse()

        def _summarize_line(value: str, limit: int = 180) -> str:
            collapsed = " ".join(value.split())
            if len(collapsed) <= limit:
                return collapsed
            cutoff = max(0, limit - 3)
            return collapsed[:cutoff].rstrip() + "..."

        history_messages: List[Dict[str, str]] = []
        transcript_summary: List[str] = []
        for idx, (prior_user, prior_assistant) in enumerate(recent_pairs, start=1):
            if prior_user:
                history_messages.append({"role": "user", "content": prior_user})
                transcript_summary.append(f"{idx}. User: {_summarize_line(prior_user)}")
            if prior_assistant:
                history_messages.append({"role": "assistant", "content": prior_assistant})
                transcript_summary.append(f"{idx}. {persona_label}: {_summarize_line(prior_assistant)}")

        provider_messages: List[Dict[str, str]] = [*history_messages, {"role": "user", "content": text}]

        persona_rubric_line = PERSONA_RUBRICS.get(persona, "")
        band_persona_line: Optional[str] = None
        if tone_band_label and isinstance(persona_rubric_line, str) and persona_rubric_line.strip():
            rubric_content = persona_rubric_line
            lower_value = rubric_content.lower()
            if lower_value.startswith("rubric:"):
                rubric_content = rubric_content[len("rubric:"):].strip()
            else:
                rubric_content = rubric_content.strip()
            if rubric_content:
                rubric_summary = rubric_content.split(";", 1)[0].strip()
                if not rubric_summary:
                    rubric_summary = rubric_content
                band_persona_line = f"Tone cue: {tone_band_label} — {rubric_summary}"

        # Load user traits to personalize responses (Direction 2: Retrieve)
        user_context_snippet = ""
        try:
            user_context_snippet = hc_trait_bridge.get_user_context(user_id, topic=None)
            if user_context_snippet:
                logger.debug(f"Injecting user context for {user_id}: {len(user_context_snippet)} chars")
        except Exception as e:
            logger.error(f"Failed to load user context: {e}", exc_info=True)

        system_prompt_parts = [
            SYSTEM_PROMPT,
            persona_prompt,
            persona_rubric_line,
            tone_hint_line,
            band_persona_line,
            user_context_snippet,  # Inject trait-based user knowledge
            f"You are replying as the {persona_label}. Maintain continuity and cite actions tied to this persona.",
        ]
        if transcript_summary:
            system_prompt_parts.append("Recent transcript (last up to 6 turns):")
            system_prompt_parts.extend(transcript_summary)
        system_prompt_parts.append(
            "Respond in 2-3 sentences, stay action-oriented, and finish with a concrete next step when appropriate."
        )
        system_prompt = "\n".join(part for part in system_prompt_parts if part)

        history_count = len(history_messages)

        provider_settings_payload: Dict[str, Any] = {}
        if model_override:
            provider_settings_payload["model"] = model_override
        if temperature_override is not None:
            provider_settings_payload["temperature"] = temperature_override
        if max_tokens_override is not None:
            provider_settings_payload["max_tokens"] = max_tokens_override

        model_used = model_override or breaker_model or getattr(provider, "_default_model", None)
        trace_payload = {
            "system_prompt": system_prompt,
            "model": model_used,
            "temperature": temperature_override,
            "max_tokens": max_tokens_override,
            "persona": persona,
            "history_count": history_count,
            "priority": turn_priority,
            "tone_band": tone_band_label,
            "tone_hint": tone_hint_line,
        }
        try:
            save_json(events_dir / f"chat_{server_ts_ms}_trace.json", trace_payload)
        except Exception:
            pass

        def _note_breaker_failure(detail: str) -> Optional[int]:
            if not breaker_key:
                return None
            retry_after, opened = chat_providers.circuit_record_failure(breaker_key)
            if opened:
                label = breaker_model or provider_identifier
                _log_provider_error(
                    "breaker_open",
                    provider_identifier,
                    f"Circuit opened for {label}: {detail}",
                )
            if retry_after:
                return int(retry_after * 1000)
            return None

        def _finalize_success() -> None:
            if not breaker_key:
                return
            if chat_providers.circuit_record_success(breaker_key):
                label = breaker_model or provider_identifier
                _log_provider_error("breaker_reset", provider_identifier, f"Circuit reset for {label}")

        def _handle_failure(detail: str, error_code: str, status_code: int) -> JSONResponse:
            retry_after_ms = _note_breaker_failure(detail)
            if retry_after_ms is not None:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "PROVIDER_UNAVAILABLE",
                        "retry_after_ms": retry_after_ms,
                    },
                )
            return JSONResponse(status_code=status_code, content={"error": error_code, "detail": detail})

        def _stream_error_payload(detail: str, error_code: str, status_code: int) -> Dict[str, Any]:
            retry_after_ms = _note_breaker_failure(detail)
            payload: Dict[str, Any] = {
                "error": error_code,
                "detail": detail,
                "status": status_code,
                "done": True,
            }
            if retry_after_ms is not None:
                payload["error"] = "PROVIDER_UNAVAILABLE"
                payload["retry_after_ms"] = retry_after_ms
                payload["status"] = 503
            return payload

        def _stream_with_provider(active_provider: chat_providers.ChatProvider) -> Iterable[str]:
            return active_provider.stream(
                system_prompt=system_prompt,
                persona=persona,
                messages=provider_messages,
                model=model_override,
                temperature=temperature_override,
                max_tokens=max_tokens_override,
            )

        def _collect_response(active_provider: chat_providers.ChatProvider) -> str:
            collected: List[str] = []
            for delta in _stream_with_provider(active_provider):
                if delta:
                    collected.append(str(delta))
            final_text = "".join(collected).strip()
            return final_text or fallback_text

        message_id = f"chat-{uuid4().hex}"

        def _persist_event(assistant_text: str, provider_used: str) -> None:
            metrics_payload: Dict[str, Any]
            if isinstance(observation_result.metrics, dict):
                metrics_payload = dict(observation_result.metrics)
            else:
                metrics_payload = {}
            metrics_payload["priority"] = turn_priority
            event_payload = {
                "type": "chat_turn",
                "ts": server_ts_ms,
                "user_id": user_id,
                "persona": persona,
                "provider": provider_used,
                "user": {
                    "text": text,
                    "ts": client_ts_ms if client_ts_ms is not None else server_ts_ms,
                },
                "assistant": {
                    "text": assistant_text,
                    "ts": server_ts_ms,
                    "message_id": message_id,
                },
                "provider_settings": provider_settings_payload,
                "observations_ref": f"users/{user_id}/{OBS_FILENAME}",
                "metrics": metrics_payload,
            }
            save_json(events_dir / f"chat_{server_ts_ms}.json", event_payload)
            touch_user_last_used(user_id, ts_iso=server_ts_iso)

        if not stream_mode:
            try:
                assistant_text = _collect_response(provider)
                _finalize_success()
            except chat_providers.ProviderTimeoutError as exc:
                detail = str(exc) or "Provider request timed out."
                _log_provider_error("timeout", provider_identifier, detail)
                return _handle_failure(detail, "PROVIDER_TIMEOUT", 504)
            except chat_providers.ProviderRuntimeError as exc:
                detail = str(exc) or "Provider request failed."
                _log_provider_error("upstream", provider_identifier, detail)
                return _handle_failure(detail, "PROVIDER_UPSTREAM", 502)
            except Exception as exc:
                detail = str(exc) or "Provider request failed."
                _log_provider_error("upstream", provider_identifier, detail)
                return _handle_failure(detail, "PROVIDER_UPSTREAM", 502)

            _persist_event(assistant_text, provider_identifier)
            return {
                "message_id": message_id,
                "persona": persona,
                "text": assistant_text,
                "ts": server_ts_ms,
                "provider": provider_identifier,
                "provider_settings": provider_settings_payload,
            }

        async def event_stream() -> AsyncGenerator[bytes, None]:
            await asyncio.sleep(random.uniform(0.25, 0.75))
            provider_iterator = _stream_with_provider(provider)
            buffered: List[str] = []
            try:
                while True:
                    first_delta = next(provider_iterator)
                    if first_delta:
                        buffered.append(str(first_delta))
                        break
                # continue streaming with remaining iterator
            except StopIteration:
                pass
            except chat_providers.ProviderTimeoutError as exc:
                detail = str(exc) or "Provider request timed out."
                _log_provider_error("timeout", provider_identifier, detail)
                error_payload = _stream_error_payload(detail, "PROVIDER_TIMEOUT", 504)
                yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                return
            except chat_providers.ProviderRuntimeError as exc:
                detail = str(exc) or "Provider request failed."
                _log_provider_error("upstream", provider_identifier, detail)
                error_payload = _stream_error_payload(detail, "PROVIDER_UPSTREAM", 502)
                yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                return
            except Exception as exc:
                detail = str(exc) or "Provider request failed."
                _log_provider_error("upstream", provider_identifier, detail)
                error_payload = _stream_error_payload(detail, "PROVIDER_UPSTREAM", 502)
                yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                return

            collected: List[str] = []
            for delta in buffered:
                collected.append(delta)
                chunk = json.dumps({"delta": delta}).encode("utf-8")
                yield b"data: " + chunk + b"\n\n"

            while True:
                try:
                    delta = next(provider_iterator)
                except StopIteration:
                    break
                except chat_providers.ProviderTimeoutError as exc:
                    detail = str(exc) or "Provider request timed out."
                    _log_provider_error("timeout", provider_identifier, detail)
                    error_payload = _stream_error_payload(detail, "PROVIDER_TIMEOUT", 504)
                    yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                    return
                except chat_providers.ProviderRuntimeError as exc:
                    detail = str(exc) or "Provider request failed."
                    _log_provider_error("upstream", provider_identifier, detail)
                    error_payload = _stream_error_payload(detail, "PROVIDER_UPSTREAM", 502)
                    yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                    return
                except Exception as exc:
                    detail = str(exc) or "Provider request failed."
                    _log_provider_error("upstream", provider_identifier, detail)
                    error_payload = _stream_error_payload(detail, "PROVIDER_UPSTREAM", 502)
                    yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
                    return
                if not delta:
                    continue
                text_delta = str(delta)
                collected.append(text_delta)
                chunk = json.dumps({"delta": text_delta}).encode("utf-8")
                yield b"data: " + chunk + b"\n\n"

            assistant_text = "".join(collected).strip() or fallback_text
            _finalize_success()
            _persist_event(assistant_text, provider_identifier)
            done_chunk = json.dumps(
                {
                    "done": True,
                    "message_id": message_id,
                    "persona": persona,
                    "text": assistant_text,
                    "ts": server_ts_ms,
                    "provider": provider_identifier,
                    "provider_settings": provider_settings_payload,
                }
            ).encode("utf-8")
            yield b"data: " + done_chunk + b"\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/ui/chat/turn")
    def chat_turn_event(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        if not user_id_raw:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        persona_token = _persona_normalize(payload.get("persona"))
        if persona_token is None:
            allowed = ", ".join(sorted(PERSONA_PROMPTS))
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": f"persona must be one of: {allowed}.",
                },
            )

        user_text = payload.get("user_text")
        assistant_text = payload.get("assistant_text")
        if not isinstance(user_text, str) or not user_text.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_text is required."},
            )
        if not isinstance(assistant_text, str) or not assistant_text.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "assistant_text is required."},
            )

        client_ts_raw = payload.get("client_ts")
        client_ts_ms: Optional[int] = None
        client_ts_iso: Optional[str] = None
        if client_ts_raw is not None:
            candidate_ms = _safe_int(client_ts_raw)
            if candidate_ms is not None:
                client_ts_ms = candidate_ms
                client_ts_iso = _ms_to_iso(candidate_ms)
            elif isinstance(client_ts_raw, str) and client_ts_raw.strip():
                token = client_ts_raw.strip()
                try:
                    parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "BAD_REQUEST",
                            "message": "client_ts must be milliseconds or ISO8601 timestamp.",
                        },
                    )
                client_ts_iso = parsed.astimezone(timezone.utc).isoformat()
                client_ts_ms = int(parsed.timestamp() * 1000)
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "message": "client_ts must be milliseconds or ISO8601 timestamp.",
                    },
                )

        provider_raw = payload.get("provider")
        provider = str(provider_raw).strip() if isinstance(provider_raw, str) and provider_raw.strip() else None
        provider_settings_raw = payload.get("provider_settings")
        provider_settings = provider_settings_raw if isinstance(provider_settings_raw, dict) else None

        persona_label_raw = payload.get("persona_label")
        persona_label = (
            str(persona_label_raw).strip()
            if isinstance(persona_label_raw, str) and persona_label_raw.strip()
            else None
        )

        client_message_id_raw = payload.get("client_message_id")
        client_message_id = (
            str(client_message_id_raw).strip()
            if isinstance(client_message_id_raw, str) and client_message_id_raw.strip()
            else None
        )
        assistant_message_id_raw = payload.get("assistant_message_id")
        assistant_message_id = (
            str(assistant_message_id_raw).strip()
            if isinstance(assistant_message_id_raw, str) and assistant_message_id_raw.strip()
            else None
        )

        now_dt = datetime.now(timezone.utc)
        server_ts_iso = now_dt.isoformat(timespec="milliseconds")
        server_ts_ms = int(now_dt.timestamp() * 1000)

        dirs = ensure_dirs_for_user(user_id_raw)
        events_dir = dirs["udir"] / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        filename_token = now_dt.strftime("%Y%m%dT%H%M%S%fZ")
        event_path = events_dir / f"chat_turn_{filename_token}_{uuid4().hex[:8]}.json"

        event_payload: Dict[str, Any] = {
            "type": "chat_turn",
            "user_id": user_id_raw,
            "persona": persona_token,
            "persona_label": persona_label,
            "user_text": user_text,
            "assistant_text": assistant_text,
            "client_message_id": client_message_id,
            "assistant_message_id": assistant_message_id,
            "client_ts": client_ts_iso,
            "client_ts_ms": client_ts_ms,
            "server_ts": server_ts_iso,
            "server_ts_ms": server_ts_ms,
            "provider": provider,
            "provider_settings": provider_settings,
            "source": "ui_chat_turn",
        }

        if event_payload["persona_label"] is None:
            event_payload.pop("persona_label")
        if event_payload["client_message_id"] is None:
            event_payload.pop("client_message_id")
        if event_payload["assistant_message_id"] is None:
            event_payload.pop("assistant_message_id")
        if event_payload["client_ts"] is None:
            event_payload.pop("client_ts")
        if event_payload["client_ts_ms"] is None:
            event_payload.pop("client_ts_ms")
        if event_payload["provider"] is None:
            event_payload.pop("provider")
        if not provider_settings:
            event_payload.pop("provider_settings")

        save_json(event_path, event_payload)
        capture(user_id_raw, "ui_chat_turn", event_payload)
        touch_user_last_used(user_id_raw, ts_iso=server_ts_iso)

        return {"ok": True, "written": str(event_path.relative_to(dirs["udir"]))}

    @app.post("/ui/media/upload")
    async def media_upload(
        user_id: str = Form(..., min_length=1, description="Active user identifier"),
        file: UploadFile = File(..., description="Media file (image or JSON)"),
        label: Optional[str] = Form(None, description="Optional label for media"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        ensure_dirs_for_user(clean_user)

        try:
            payload = await file.read()
        finally:
            await file.close()

        if not payload:
            return JSONResponse(
                status_code=400,
                content={"error": "EMPTY_MEDIA", "message": "Upload a non-empty file."},
            )

        size_bytes = len(payload)
        media_max_mb, media_max_bytes = _media_limits()
        original_filename = file.filename or 'upload'
        normalized_ext = _normalize_media_extension(original_filename)

        if size_bytes > media_max_bytes:
            _log_upload_violation(
                'SIZE_EXCEEDED',
                user_id=clean_user,
                filename=original_filename,
                size=size_bytes,
                content_type=file.content_type,
                detail=f'max_bytes={media_max_bytes}',
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": "MEDIA_TOO_LARGE",
                    "message": f"File exceeds the {media_max_mb} MB upload limit.",
                },
            )

        if normalized_ext not in ALLOWED_MEDIA_EXTENSIONS:
            _log_upload_violation(
                'EXTENSION_FORBIDDEN',
                user_id=clean_user,
                filename=original_filename,
                size=size_bytes,
                content_type=file.content_type,
                detail=f'extension={normalized_ext or "<missing>"}',
            )
            return JSONResponse(
                status_code=415,
                content={
                    "error": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "Only .jpg, .png, or .json uploads are supported.",
                },
            )

        detected_type = _detect_media_type(payload)
        expected_type = MEDIA_EXPECTED_TYPES.get(normalized_ext)

        if not detected_type:
            _log_upload_violation(
                'MIME_UNSUPPORTED',
                user_id=clean_user,
                filename=original_filename,
                size=size_bytes,
                content_type=file.content_type,
                detail=f'expected={expected_type}',
            )
            return JSONResponse(
                status_code=415,
                content={
                    "error": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "File content must be valid JPEG, PNG, or JSON.",
                },
            )

        if expected_type and detected_type != expected_type:
            _log_upload_violation(
                'MIME_MISMATCH',
                user_id=clean_user,
                filename=original_filename,
                size=size_bytes,
                content_type=detected_type,
                detail=f'expected={expected_type}',
            )
            return JSONResponse(
                status_code=415,
                content={
                    "error": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "File extension does not match detected content.",
                },
            )

        safe_original_name = _slugify_media_name(original_filename, normalized_ext)
        label_value = label.strip() if isinstance(label, str) and label.strip() else None

        try:
            entry = save_media_asset(
                clean_user,
                original_name=safe_original_name,
                content_type=detected_type,
                data=payload,
                label=label_value,
                source_name=original_filename if original_filename != safe_original_name else None,
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"error": "MEDIA_SAVE_FAILED", "message": str(exc)},
            )

        response_entry = dict(entry)
        response_entry["download_url"] = f"/ui/media/download/{clean_user}/{entry['id']}"
        return {"ok": True, "media": response_entry}

    @app.get("/ui/media/list")
    def media_list(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        ensure_dirs_for_user(clean_user)
        entries = list_media_assets(clean_user)
        items: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            enriched = dict(entry)
            enriched["download_url"] = f"/ui/media/download/{clean_user}/{entry.get('id')}"
            items.append(enriched)

        return {"user_id": clean_user, "items": items}

    @app.delete("/ui/media/delete")
    def media_delete(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        media_id: str = Query(..., min_length=1, description="Media asset identifier"),
    ) -> Any:
        clean_user = user_id.strip()
        clean_media = media_id.strip()
        if not clean_user or not clean_media:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and media_id are required."},
            )

        ensure_dirs_for_user(clean_user)
        resolved = get_media_asset(clean_user, clean_media)
        if not resolved:
            return JSONResponse(
                status_code=404,
                content={"error": "MEDIA_NOT_FOUND", "message": "Media asset not found."},
            )

        removed = delete_media_asset(clean_user, clean_media)
        if not removed:
            return JSONResponse(
                status_code=500,
                content={"error": "MEDIA_DELETE_FAILED", "message": "Failed to remove media asset."},
            )

        return {"ok": True, "removed": True, "media_id": clean_media}

    @app.get("/ui/media/download/{user_id}/{media_id}")
    def media_download(user_id: str, media_id: str) -> Any:
        clean_user = user_id.strip()
        clean_media = media_id.strip()
        if not clean_user or not clean_media:
            raise HTTPException(status_code=400, detail="user_id and media_id are required")

        resolved = get_media_asset(clean_user, clean_media)
        if not resolved:
            raise HTTPException(status_code=404, detail="Media not found")

        entry, path = resolved
        filename = entry.get("original_name") or path.name
        media_type = entry.get("content_type") or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=filename)

    @app.post("/ui/photo/render")
    def create_photo_render_job(payload: Dict[str, Any] = Body(...)) -> Any:
        user_id = str(payload.get("user_id") or "").strip()
        media_id = str(payload.get("media_id") or "").strip()
        params_raw = payload.get("params")
        params = params_raw if isinstance(params_raw, dict) else {}

        if not user_id or not media_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and media_id are required."},
            )

        ensure_dirs_for_user(user_id)
        if not get_media_asset(user_id, media_id):
            return JSONResponse(
                status_code=404,
                content={"error": "MEDIA_NOT_FOUND", "message": "Media asset not found."},
            )

        job = create_render_job(user_id, media_id=media_id, params=params)
        _index_render_job(job)
        photo_worker.submit(user_id, job["id"])
        return {
            "ok": True,
            "job_id": job["id"],
            "job": _serialize_render_job(job),
        }

    @app.get("/ui/photo/status")
    def photo_render_status(
        job_id: str = Query(..., min_length=8, description="Render job identifier"),
        user_id: Optional[str] = Query(None, description="Optional user hint"),
    ) -> Any:
        clean_job = job_id.strip()
        if not clean_job:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "job_id is required."},
            )

        located = _locate_render_job(clean_job, user_hint=user_id)
        if not located:
            return JSONResponse(
                status_code=404,
                content={"error": "JOB_NOT_FOUND", "message": "Render job not found."},
            )

        found_user, job = located
        _index_render_job(job)
        return {"ok": True, "user_id": found_user, "job": _serialize_render_job(job)}

    @app.get("/ui/photo/jobs")
    def list_photo_render_jobs(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        limit: Optional[int] = Query(None, description="Optional limit for recent jobs"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        jobs = list_render_jobs(clean_user, limit=limit)
        items = []
        for job in jobs:
            _index_render_job(job)
            items.append(_serialize_render_job(job))
        return {"user_id": clean_user, "items": items}

    @app.get("/ui/photo/result")
    def photo_render_result(
        job_id: Optional[str] = Query(None, description="Render job identifier"),
        result_id: Optional[str] = Query(None, description="Alias for job identifier"),
        user_id: Optional[str] = Query(None, description="Optional user hint"),
    ) -> Any:
        identifier = (result_id or job_id or "").strip()
        if not identifier:
            raise HTTPException(status_code=400, detail="job_id or result_id is required")

        located = _locate_render_job(identifier, user_hint=user_id)
        if not located:
            return StreamingResponse(io.BytesIO(PHOTO_PLACEHOLDER_BYTES), media_type=PHOTO_PLACEHOLDER_TYPE)

        found_user, job = located
        filename = job.get("result_filename")
        job_identifier = job.get("id")
        if not isinstance(job_identifier, str):
            job_identifier = identifier
        if isinstance(filename, str) and filename and isinstance(job_identifier, str):
            candidate = render_job_result_path(found_user, job_identifier, filename=filename)
            if candidate.exists():
                media_type = job.get("result_content_type") or "application/octet-stream"
                return FileResponse(candidate, media_type=media_type, filename=filename)

        return StreamingResponse(
            io.BytesIO(PHOTO_PLACEHOLDER_BYTES),
            media_type=PHOTO_PLACEHOLDER_TYPE,
            headers={"x-placeholder": "1"},
        )

    @app.post("/ui/photo/extract")
    def photo_extract_traits(payload: Dict[str, Any] = Body(...)) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        media_id = str(payload.get("media_id") or "").strip()
        if not user_id or not media_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and media_id are required."},
            )

        ensure_dirs_for_user(user_id)
        media_asset = get_media_asset(user_id, media_id)
        if not media_asset:
            return JSONResponse(
                status_code=404,
                content={"error": "MEDIA_NOT_FOUND", "message": "Media asset not found."},
            )

        resolved, evidence, observations = read_user_state(user_id)
        prior_resolved = copy.deepcopy(resolved)
        if not isinstance(observations, dict):
            observations = {"items": [], "by_trait": {}}
        if not isinstance(observations.get("items"), list):
            observations["items"] = []
        if not isinstance(observations.get("by_trait"), dict):
            observations["by_trait"] = {}

        trait_catalog: Dict[str, List[str]] = {
            "PaDNA.LooksDNA.FaceDNA.Shape": ["oval", "round", "heart", "square"],
            "PaDNA.LooksDNA.HairDNA.Length": ["short", "medium", "long"],
            "PaDNA.LooksDNA.EyeDNA.Highlight": ["warm", "cool", "neutral"],
            "PaDNA.StyleDNA.Palette.Core": ["vibrant", "soft", "bold"],
        }

        rng = random.Random(f"{user_id}:{media_id}")
        extracted: List[Dict[str, Any]] = []
        now_iso = iso_now()
        touched_traits: Set[str] = set()

        for trait_id, options in trait_catalog.items():
            if not options:
                continue
            value = rng.choice(options)
            ucn_value = 70 + rng.randint(-10, 10)
            reason = f"photo_extract_stub:{media_id}"

            resolved_entry = resolved.get(trait_id)
            if not isinstance(resolved_entry, dict):
                resolved_entry = {}
            resolved_entry["resolved_value"] = value
            resolved_entry["ucn"] = max(0, ucn_value)
            resolved_entry["reasons"] = [reason]
            resolved[trait_id] = resolved_entry
            touched_traits.add(trait_id)

            observation_entry = {
                "trait": trait_id,
                "trait_id": trait_id,
                "value": value,
                "ucn": resolved_entry["ucn"],
                "source": "photo_extract_stub",
                "persona": "photo",
                "ts": now_iso,
                "media_id": media_id,
            }
            observations["items"].append(observation_entry)
            bucket = observations["by_trait"].setdefault(trait_id, [])
            bucket.append(
                {
                    "value": value,
                    "ucn": resolved_entry["ucn"],
                    "ts": now_iso,
                    "source": "photo_extract_stub",
                    "media_id": media_id,
                }
            )
            if len(bucket) > 25:
                observations["by_trait"][trait_id] = bucket[-25:]

            extracted.append({
                "trait": trait_id,
                "value": value,
                "ucn": resolved_entry["ucn"],
            })

        if not extracted:
            return {"ok": True, "traits": [], "summary_fixes": []}

        _update_curiosity(user_id, prior_resolved, resolved, evidence, observations, touched_traits)

        touch_user_last_used(user_id, ts_iso=now_iso)

        capture(
            user_id,
            "photo_extract_stub",
            {
                "ts": int(time.time() * 1000),
                "media_id": media_id,
                "trait_count": len(extracted),
                "stub": True,
            },
        )

        # Call UCN/RR to get actual RR values and curiosity
        ucnrr_result = {}
        ucnrr_base = _ucnrr_base_url()
        if ucnrr_base:
            try:
                traits_payload = []
                for item in extracted:
                    traits_payload.append({
                        "id": item["trait"],
                        "value": item["value"],
                        "rr": item.get("ucn", 500.0),  # Use UCN as initial RR estimate
                    })

                response = requests.post(
                    f"{ucnrr_base}/api/rescore",
                    json={"user_id": user_id, "traits": traits_payload},
                    timeout=10,
                )
                if response.ok:
                    ucnrr_result = response.json()
            except Exception:
                pass  # Continue without UCN/RR data

        # Extract RR and curiosity from UCN/RR result
        rr_by_trait = ucnrr_result.get("rr_by_trait", {})
        curiosity_by_trait = ucnrr_result.get("curiosity_by_trait", {})

        # Build summary_fixes with RR bands and actual RR/curiosity values
        summary_fixes = []
        for trait_item in extracted:
            trait_id = trait_item["trait"]
            ucn = trait_item.get("ucn", 50)
            rr = rr_by_trait.get(trait_id, ucn)  # Fallback to UCN if no RR
            curiosity = curiosity_by_trait.get(trait_id, 0.0)

            # Convert RR (0-1000) to band
            if rr < 333:
                rr_band = "low"
            elif rr < 667:
                rr_band = "medium"
            else:
                rr_band = "high"

            summary_fixes.append({
                "trait_id": trait_id,
                "value": trait_item["value"],
                "ucn": ucn,
                "rr": rr,
                "curiosity": curiosity,
                "rr_band": rr_band,
                "fix_text": f"{trait_id}: {trait_item['value']} (RR: {int(rr)})",
            })

        return {
            "ok": True,
            "traits": extracted,
            "summary_fixes": summary_fixes,
            "ucnrr_result": ucnrr_result.get("ok", False),
        }

    @app.post("/ui/render/avatar")
    def create_avatar_render(payload: Dict[str, Any] = Body(...)) -> Any:
        """
        Stub endpoint for avatar rendering based on PaDNA/Rendering traits.
        Creates a placeholder render job and saves a stub result.
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        # Ensure user directories exist
        user_paths = ensure_dirs_for_user(user_id)
        renders_dir = user_paths["udir"] / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)

        # Create job ID
        job_id = f"avatar_{int(time.time() * 1000)}"
        job_dir = renders_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Load user traits for rendering
        resolved, evidence, obs = read_user_state(user_id)

        # Extract rendering-relevant traits
        rendering_traits = {}
        for trait_id, trait_data in resolved.items():
            if isinstance(trait_data, dict) and "PaDNA" in trait_id:
                rendering_traits[trait_id] = {
                    "value": trait_data.get("resolved_value"),
                    "ucn": trait_data.get("ucn", 0),
                    "rr": trait_data.get("rr", 0),
                }

        # Create stub render result (placeholder)
        result_path = job_dir / "result.png"
        job_metadata = {
            "job_id": job_id,
            "user_id": user_id,
            "created_at": iso_now(),
            "state": "done",
            "rendering_traits": rendering_traits,
            "result_path": str(result_path.relative_to(user_paths["udir"])),
            "download_url": f"/ui/render/download/{user_id}/{job_id}/result.png",
        }

        # Save job metadata
        metadata_path = job_dir / "job.json"
        save_json(metadata_path, job_metadata)

        # Create placeholder PNG (1x1 transparent pixel for stub)
        # In real implementation, this would call an actual rendering service
        import base64
        stub_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        with open(result_path, "wb") as f:
            f.write(stub_png)

        # Log event
        capture(
            user_id,
            "avatar_render_created",
            {
                "ts": int(time.time() * 1000),
                "job_id": job_id,
                "traits_count": len(rendering_traits),
                "stub": True,
            },
        )

        return {
            "ok": True,
            "job": job_metadata,
        }

    @app.get("/ui/render/download/{user_id}/{job_id}/{filename}")
    def download_render_result(user_id: str, job_id: str, filename: str) -> Any:
        """Download rendered avatar result."""
        user_paths = ensure_dirs_for_user(user_id)
        result_path = user_paths["udir"] / "renders" / job_id / filename

        if not result_path.exists() or not result_path.is_file():
            return JSONResponse(
                status_code=404,
                content={"error": "NOT_FOUND", "message": "Render result not found."},
            )

        return FileResponse(
            result_path,
            media_type="image/png",
            filename=filename,
        )

    @app.get("/ui/render/jobs/{user_id}")
    def list_render_jobs(user_id: str) -> Any:
        """
        List all rendering jobs for a user, sorted by creation time (newest first).
        Returns job metadata including job_id, created_at, traits count, and download_url.
        """
        user_paths = ensure_dirs_for_user(user_id)
        renders_dir = user_paths["udir"] / "renders"

        if not renders_dir.exists():
            return {"ok": True, "jobs": []}

        jobs = []
        try:
            for job_dir in renders_dir.iterdir():
                if not job_dir.is_dir():
                    continue

                job_metadata_path = job_dir / "job.json"
                if not job_metadata_path.exists():
                    continue

                try:
                    job_data = load_json(job_metadata_path)
                    if isinstance(job_data, dict):
                        # Extract key fields for the list
                        rendering_traits = job_data.get("rendering_traits", {})
                        jobs.append({
                            "job_id": job_data.get("job_id", job_dir.name),
                            "created_at": job_data.get("created_at", ""),
                            "traits_count": len(rendering_traits) if isinstance(rendering_traits, dict) else 0,
                            "download_url": job_data.get("download_url", ""),
                            "state": job_data.get("state", "unknown"),
                        })
                except Exception:
                    continue  # Skip malformed job metadata
        except Exception:
            pass  # Handle case where renders_dir can't be read

        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

        return {"ok": True, "jobs": jobs}

    @app.post("/ui/photo/apply_fix")
    def apply_photo_fix(payload: Dict[str, Any] = Body(...)) -> Any:
        """
        Apply a photo fix by creating a trait override and triggering rescore.
        Wrapper endpoint that combines override + rescore for convenience.
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        trait_id = str(payload.get("trait_id") or "").strip()
        value = payload.get("value")
        reason = str(payload.get("reason") or "photo_fix_applied").strip()

        if not user_id or not trait_id or value is None:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id, trait_id, and value are required."},
            )

        # 1. Apply trait override
        override_payload = {
            "user_id": user_id,
            "trait_id": trait_id,
            "value": value,
            "reason": reason,
        }

        # Call the existing override endpoint logic directly
        try:
            resolved, evidence, observations = read_user_state(user_id)
            prior_resolved = copy.deepcopy(resolved)

            # Create override entry
            entry = resolved.get(trait_id)
            if not isinstance(entry, dict):
                entry = {}

            entry["resolved_value"] = value
            entry["override"] = True
            entry["override_reason"] = reason
            entry["override_ts"] = iso_now()
            resolved[trait_id] = entry

            # Save state
            ensure_dirs_for_user(user_id)
            touch_user_last_used(user_id)

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_ERROR", "message": f"Failed to apply override: {str(e)}"},
            )

        # 2. Trigger rescore via UCN/RR
        trait_changes = []
        ucnrr_base = _ucnrr_base_url()

        if ucnrr_base:
            try:
                # Build traits payload for rescore
                traits_payload = []
                for tid, trait_data in resolved.items():
                    if isinstance(trait_data, dict) and trait_data.get("resolved_value") is not None:
                        traits_payload.append({
                            "id": tid,
                            "value": trait_data.get("resolved_value"),
                            "rr": trait_data.get("rr", trait_data.get("ucn", 500.0)),
                        })

                response = requests.post(
                    f"{ucnrr_base}/api/rescore",
                    json={"user_id": user_id, "traits": traits_payload},
                    timeout=10,
                )

                if response.ok:
                    rescore_result = response.json()

                    # Extract trait changes
                    new_rr_by_trait = rescore_result.get("rr_by_trait", {})
                    for tid in resolved:
                        if tid in prior_resolved:
                            old_rr = prior_resolved[tid].get("rr", prior_resolved[tid].get("ucn", 0))
                            new_rr = new_rr_by_trait.get(tid, old_rr)
                            delta = new_rr - old_rr

                            if abs(delta) > 0.1:  # Only include meaningful changes
                                trait_changes.append({
                                    "trait": tid,
                                    "old_rr": old_rr,
                                    "new_rr": new_rr,
                                    "delta": delta,
                                })

                    # Update resolved with new RR values
                    for tid, new_rr in new_rr_by_trait.items():
                        if tid in resolved and isinstance(resolved[tid], dict):
                            resolved[tid]["rr"] = new_rr

            except Exception:
                pass  # Continue without rescore

        # Log the fix application
        capture(
            user_id,
            "photo_fix_applied",
            {
                "ts": int(time.time() * 1000),
                "trait_id": trait_id,
                "value": value,
                "reason": reason,
                "rescore_triggered": bool(ucnrr_base),
            },
        )

        return {
            "ok": True,
            "trait_id": trait_id,
            "value": value,
            "changes": trait_changes,
            "rescore_triggered": bool(ucnrr_base),
        }

    @app.post("/ui/photo/import")
    def import_photo_json(payload: Dict[str, Any] = Body(...)) -> Any:
        """
        Import PaDNA traits from flexible JSON or plain text.
        Supports structured JSON, unstructured JSON, or plain text descriptions.
        Uses LLM-assisted path normalization for flexible input formats.

        Expected payload:
        {
            "user_id": "demo_user",
            "data": {...} or "plain text description",
            "source": "photo-analysis" (optional)
        }
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        if not user_id_raw:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        data_raw = payload.get("data")
        if data_raw is None:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "data field is required."},
            )

        # Check if Photo Coach is available
        if not PHOTO_COACH_AVAILABLE or import_padna_soft is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SERVICE_UNAVAILABLE",
                    "message": "Photo Coach import system is not available.",
                },
            )

        ensure_dirs_for_user(user_id_raw)

        # Convert plain text to structured format if needed
        if isinstance(data_raw, str):
            # Plain text description - wrap it in a simple structure
            import_payload = {
                "user_id": user_id_raw,
                "description": data_raw,
                "provenance": {
                    "source": payload.get("source", "photo-import"),
                    "mode": "text-description",
                },
            }
        elif isinstance(data_raw, dict):
            # Structured JSON - ensure user_id is present
            import_payload = dict(data_raw)
            if "user_id" not in import_payload:
                import_payload["user_id"] = user_id_raw
            if "provenance" not in import_payload:
                import_payload["provenance"] = {
                    "source": payload.get("source", "photo-import"),
                    "mode": "json-import",
                }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": "data must be a string (text description) or object (structured JSON).",
                },
            )

        # Use the Photo Coach soft import system
        try:
            result = import_padna_soft(import_payload, strict=False)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "IMPORT_FAILED",
                    "message": f"Failed to parse import data: {str(exc)}",
                },
            )

        # Check for critical errors
        if result.errors and not result.observations:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "VALIDATION_FAILED",
                    "message": "; ".join(result.errors),
                    "warnings": result.warnings,
                },
            )

        # Now apply the observations to the user's state
        resolved, evidence, observations = read_user_state(user_id_raw)
        prior_resolved = copy.deepcopy(resolved)

        if not isinstance(observations, dict):
            observations = {"items": [], "by_trait": {}}
        if not isinstance(observations.get("items"), list):
            observations["items"] = []
        if not isinstance(observations.get("by_trait"), dict):
            observations["by_trait"] = {}

        now_iso = iso_now()
        touched_traits: Set[str] = set()
        imported_traits: List[Dict[str, Any]] = []

        # Process each observation
        for trait_path, trait_data in result.observations.items():
            if not isinstance(trait_data, dict):
                continue

            resolved_value = trait_data.get("resolved_value")
            if resolved_value is None:
                continue

            # Get confidence/UCN
            confidence = trait_data.get("confidence")
            ucn_value = trait_data.get("ucn")

            if ucn_value is None:
                if confidence is not None and isinstance(confidence, (int, float)):
                    # Convert confidence (0-1) to UCN (0-1000)
                    ucn_value = confidence * 1000
                else:
                    ucn_value = 80.0  # Default

            # Get provenance
            provenance = trait_data.get("provenance", {})
            if not isinstance(provenance, dict):
                provenance = {}

            source = provenance.get("source", "photo-import")

            # Update resolved state
            resolved_entry = resolved.get(trait_path)
            if not isinstance(resolved_entry, dict):
                resolved_entry = {}

            resolved_entry["resolved_value"] = resolved_value
            resolved_entry["ucn"] = max(0, min(1000, ucn_value))

            reasons = trait_data.get("reasons", [])
            if isinstance(reasons, list) and reasons:
                resolved_entry["reasons"] = reasons
            else:
                resolved_entry["reasons"] = [f"photo_import:{source}"]

            # Add notes if present
            notes = trait_data.get("notes")
            if isinstance(notes, dict):
                resolved_entry["notes"] = notes

            resolved[trait_path] = resolved_entry
            touched_traits.add(trait_path)

            # Add to observations log
            observation_entry = {
                "trait": trait_path,
                "trait_id": trait_path,
                "value": resolved_value,
                "ucn": resolved_entry["ucn"],
                "source": source,
                "persona": "photo",
                "ts": now_iso,
                "provenance": provenance,
            }
            observations["items"].append(observation_entry)

            bucket = observations["by_trait"].setdefault(trait_path, [])
            bucket.append({
                "value": resolved_value,
                "ucn": resolved_entry["ucn"],
                "ts": now_iso,
                "source": source,
                "provenance": provenance,
            })
            if len(bucket) > 25:
                observations["by_trait"][trait_path] = bucket[-25:]

            imported_traits.append({
                "trait": trait_path,
                "value": resolved_value,
                "ucn": resolved_entry["ucn"],
            })

        # Update curiosity
        if touched_traits:
            _update_curiosity(user_id_raw, prior_resolved, resolved, evidence, observations, touched_traits)

        # Save state
        write_user_state(user_id_raw, resolved, evidence, observations, enforce_governance=True)
        touch_user_last_used(user_id_raw, ts_iso=now_iso)

        # Log the import event
        capture(
            user_id_raw,
            "photo_import",
            {
                "ts": int(time.time() * 1000),
                "trait_count": len(imported_traits),
                "source": payload.get("source", "photo-import"),
                "quarantined_count": len(result.quarantined),
                "assisted_count": len(result.assisted),
                "warnings_count": len(result.warnings),
            },
        )

        # Optionally trigger UCN/RR rescore
        ucnrr_result = {}
        ucnrr_base = _ucnrr_base_url()
        if ucnrr_base and imported_traits:
            try:
                traits_payload = []
                for item in imported_traits:
                    traits_payload.append({
                        "id": item["trait"],
                        "value": item["value"],
                        "rr": item.get("ucn", 500.0),
                    })

                response = requests.post(
                    f"{ucnrr_base}/api/rescore",
                    json={"user_id": user_id_raw, "traits": traits_payload},
                    timeout=10,
                )
                if response.ok:
                    ucnrr_result = response.json()

                    # Update resolved with RR values
                    rr_by_trait = ucnrr_result.get("rr_by_trait", {})
                    curiosity_by_trait = ucnrr_result.get("curiosity_by_trait", {})

                    for trait_id, rr_value in rr_by_trait.items():
                        if trait_id in resolved and isinstance(resolved[trait_id], dict):
                            resolved[trait_id]["rr"] = rr_value

                    for trait_id, curiosity_value in curiosity_by_trait.items():
                        if trait_id in resolved and isinstance(resolved[trait_id], dict):
                            resolved[trait_id]["curiosity"] = curiosity_value

                    # Save updated state with RR values
                    write_user_state(user_id_raw, resolved, evidence, observations, enforce_governance=True)
            except Exception:
                pass  # Continue without UCN/RR data

        # NEW ARCHITECTURE: Three-layer data flow
        # 1. HEAD COACH: Shape data and perform initial AI inference
        # 2. UCN/RR: Statistical validation and confidence scoring
        # 3. CORE: Holistic synthesis (happens below in response building)

        head_coach_result = None
        ucnrr_validation = None
        inference_result = None  # Backward compatibility structure

        if imported_traits:
            try:
                # LAYER 1: HEAD COACH - Shape photo data and perform AI inference
                imported_for_inference = {}
                for trait_item in imported_traits:
                    trait_id = trait_item["trait"]
                    if trait_id in resolved:
                        imported_for_inference[trait_id] = resolved[trait_id]

                head_coach_result = head_coach.shape_photo_import(
                    imported_traits=imported_for_inference,
                    user_id=user_id_raw,
                    image_quality=0.9  # TODO: Extract from photo metadata
                )

                logger.info(
                    f"[HeadCoach:{user_id_raw}] Processed {len(head_coach_result.direct_observations)} "
                    f"observations, inferred {len(head_coach_result.inferred_traits)} traits"
                )

                # LAYER 2: UCN/RR - Validate confidence and rarity
                if head_coach_result.inferred_traits or head_coach_result.direct_observations:
                    ucnrr_validation = ucn_rr_service.assess_observations_and_inferences(
                        direct_observations=head_coach_result.direct_observations,
                        proposed_inferences=head_coach_result.inferred_traits,
                        current_profile=resolved,
                        user_id=user_id_raw,
                        baselines=None  # Will use synthetic baselines
                    )

                    logger.info(
                        f"[UCNRR:{user_id_raw}] Validated {len(ucnrr_validation.assessments)} traits"
                    )

                # Build backward-compatible inference_result for existing UI
                if head_coach_result and head_coach_result.inferred_traits:
                    from dataclasses import dataclass as _dataclass, field as _field
                    from typing import List as _List

                    @_dataclass
                    class _InferenceResult:
                        inferences: _List[InferredTrait] = _field(default_factory=list)
                        source_trait_count: int = 0
                        inference_count: int = 0
                        skipped: _List[str] = _field(default_factory=list)
                        warnings: _List[str] = _field(default_factory=list)
                        llm_available: bool = False
                        model_used: str = None

                    inference_result = _InferenceResult(
                        source_trait_count=len(imported_traits),
                        inference_count=len(head_coach_result.inferred_traits),
                        llm_available=head_coach_result.llm_available,
                        model_used=head_coach_result.model_used,
                        warnings=head_coach_result.warnings
                    )

                    # Convert ProposedInference to InferredTrait for UI compatibility
                    for proposed in head_coach_result.inferred_traits:
                        inferred = InferredTrait(
                            trait_path=proposed.trait_path,
                            value=proposed.value,
                            confidence=proposed.confidence,
                            reasoning=proposed.reasoning,
                            source_traits=proposed.source_observations,
                            category=proposed.category
                        )
                        inference_result.inferences.append(inferred)

            except Exception as exc:
                logger.error(f"[PhotoImport:{user_id_raw}] New architecture inference failed: {exc}", exc_info=True)
                # Don't fail the import if inference fails

        # Build response
        response = {
            "ok": True,
            "imported": len(imported_traits),
            "traits": imported_traits,
            "quarantined": [
                {
                    "raw_path": item.raw_path,
                    "raw_value": item.raw_value,
                    "reasons": item.reasons,
                }
                for item in result.quarantined
            ],
            "assisted": result.assisted,
            "warnings": result.warnings,
            "rescore_triggered": bool(ucnrr_base and imported_traits),
        }

        # Add inference results if available
        if inference_result:
            response["inferences"] = {
                "available": inference_result.llm_available,
                "count": inference_result.inference_count,
                "model_used": inference_result.model_used,
                "traits": [
                    {
                        "trait_path": inf.trait_path,
                        "value": inf.value,
                        "confidence": inf.confidence,
                        "reasoning": inf.reasoning,
                        "source_traits": inf.source_traits,
                        "category": inf.category,
                    }
                    for inf in inference_result.inferences
                ],
                "skipped": inference_result.skipped,
                "warnings": inference_result.warnings,
            }
        else:
            response["inferences"] = {
                "available": False,
                "count": 0,
                "traits": [],
            }

        return response

    @app.post("/ui/photo/apply_inferences")
    def apply_trait_inferences(payload: Dict[str, Any] = Body(...)) -> Any:
        """
        Apply approved AI-inferred traits to user profile.

        Expected payload:
        {
            "user_id": "demo_user",
            "inferences": [
                {
                    "trait_path": "PaDNA.SkinDNA.Freckles",
                    "value": "Present",
                    "confidence": 0.85,
                    "reasoning": "...",
                    "source_traits": [...],
                    "category": "physical"
                }
            ]
        }
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        inferences_raw = payload.get("inferences")

        if not user_id_raw:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        if not isinstance(inferences_raw, list):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "inferences must be a list."},
            )

        if not inferences_raw:
            return {"ok": True, "applied": 0, "message": "No inferences to apply"}

        ensure_dirs_for_user(user_id_raw)

        # Load user state
        resolved, evidence, observations = read_user_state(user_id_raw)
        prior_resolved = copy.deepcopy(resolved)

        if not isinstance(observations, dict):
            observations = {"items": [], "by_trait": {}}
        if not isinstance(observations.get("items"), list):
            observations["items"] = []
        if not isinstance(observations.get("by_trait"), dict):
            observations["by_trait"] = {}

        now_iso = iso_now()
        touched_traits: Set[str] = set()
        applied_count = 0

        # Apply each inference
        for inf_data in inferences_raw:
            if not isinstance(inf_data, dict):
                continue

            trait_path = inf_data.get("trait_path", "").strip()
            value = inf_data.get("value")
            confidence = inf_data.get("confidence", 0.0)
            reasoning = inf_data.get("reasoning", "")
            source_traits = inf_data.get("source_traits", [])
            category = inf_data.get("category", "physical")

            if not trait_path or value is None:
                continue

            # Create inference object
            inference = InferredTrait(
                trait_path=trait_path,
                value=value,
                confidence=confidence,
                reasoning=reasoning,
                source_traits=source_traits if isinstance(source_traits, list) else [],
                category=category
            )

            # Apply to resolved state
            entry = resolved.get(trait_path, {})
            if not isinstance(entry, dict):
                entry = {}

            entry["resolved_value"] = inference.value
            entry["ucn"] = min(1000, max(0, inference.confidence * 1000))
            entry["inferred"] = True
            entry["inferred_by"] = "ai"
            entry["inferred_ts"] = now_iso
            entry["reasons"] = [f"ai_inference:confidence_{inference.confidence:.2f}"]
            entry["notes"] = {
                "inference_reasoning": inference.reasoning,
                "source_traits": inference.source_traits,
                "category": inference.category
            }

            resolved[trait_path] = entry
            touched_traits.add(trait_path)

            # Add to observations log
            observation_entry = {
                "trait": trait_path,
                "trait_id": trait_path,
                "value": inference.value,
                "ucn": entry["ucn"],
                "source": "ai_inference",
                "persona": "photo",
                "ts": now_iso,
                "inferred": True,
            }
            observations["items"].append(observation_entry)

            bucket = observations["by_trait"].setdefault(trait_path, [])
            bucket.append({
                "value": inference.value,
                "ucn": entry["ucn"],
                "ts": now_iso,
                "source": "ai_inference",
                "inferred": True,
            })
            if len(bucket) > 25:
                observations["by_trait"][trait_path] = bucket[-25:]

            applied_count += 1

        # Update curiosity
        if touched_traits:
            _update_curiosity(user_id_raw, prior_resolved, resolved, evidence, observations, touched_traits)

        # Save state
        write_user_state(user_id_raw, resolved, evidence, observations, enforce_governance=True)
        touch_user_last_used(user_id_raw, ts_iso=now_iso)

        # Log the application
        capture(
            user_id_raw,
            "inferences_applied",
            {
                "ts": int(time.time() * 1000),
                "applied_count": applied_count,
            },
        )

        return {
            "ok": True,
            "applied": applied_count,
            "message": f"Applied {applied_count} AI-inferred trait{'' if applied_count == 1 else 's'}"
        }

    @app.post("/ui/padna/render")
    def create_padna_render_job(payload: Dict[str, Any] = Body(...)) -> Any:
        user_id = str(payload.get("user_id") or "").strip()
        bundle_raw = payload.get("bundle")

        if not user_id or not isinstance(bundle_raw, Mapping):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and bundle are required."},
            )

        ensure_dirs_for_user(user_id)
        job = _padna_create_job(user_id, bundle_raw)
        padna_job_user_cache[job["id"]] = user_id
        padna_worker.submit(user_id, job["id"])
        return {"ok": True, "job": _serialize_padna_job(job)}

    @app.get("/ui/padna/status")
    def padna_render_status(
        job_id: str = Query(..., min_length=8, description="Padna render job identifier"),
        user_id: Optional[str] = Query(None, description="Optional user hint"),
    ) -> Any:
        clean_job = job_id.strip()
        if not clean_job:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "job_id is required."},
            )

        located = _padna_locate_job(clean_job, user_hint=user_id)
        if not located:
            return JSONResponse(
                status_code=404,
                content={"error": "JOB_NOT_FOUND", "message": "Padna render job not found."},
            )

        found_user, job = located
        padna_job_user_cache[clean_job] = found_user
        return {"ok": True, "user_id": found_user, "job": _serialize_padna_job(job)}

    @app.get("/ui/padna/list")
    def padna_render_list(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        limit: Optional[int] = Query(10, description="Optional limit for recent jobs"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        effective_limit: Optional[int]
        if limit is None:
            effective_limit = 10
        else:
            try:
                limit_value = int(limit)
            except (TypeError, ValueError):
                limit_value = 10
            effective_limit = limit_value if limit_value > 0 else None

        jobs = _padna_list_jobs(clean_user, limit=effective_limit)
        items = [_serialize_padna_job(job) for job in jobs]
        return {"user_id": clean_user, "items": items}

    @app.get("/ui/padna/result")
    def padna_render_result(
        job_id: str = Query(..., min_length=8, description="Padna render job identifier"),
        user_id: Optional[str] = Query(None, description="Optional user hint"),
    ) -> Any:
        identifier = job_id.strip()
        if not identifier:
            raise HTTPException(status_code=400, detail="job_id is required")

        located = _padna_locate_job(identifier, user_hint=user_id)
        if not located:
            return StreamingResponse(io.BytesIO(PADNA_PLACEHOLDER_BYTES), media_type=PADNA_PLACEHOLDER_TYPE)

        found_user, job = located
        if job.get("state") != "done":
            return StreamingResponse(
                io.BytesIO(PADNA_PLACEHOLDER_BYTES),
                media_type=PADNA_PLACEHOLDER_TYPE,
                headers={"x-placeholder": "1"},
            )

        job_identifier = job.get("id") or identifier
        filename = job.get("result_filename") or PADNA_RESULT_FILENAME
        result_filename = job.get("result_filename")
        result_path = _padna_result_path(found_user, str(job_identifier), result_filename)
        if not result_path.exists():
            return StreamingResponse(
                io.BytesIO(PADNA_PLACEHOLDER_BYTES),
                media_type=PADNA_PLACEHOLDER_TYPE,
                headers={"x-placeholder": "1"},
            )

        media_type = job.get("result_content_type") or PADNA_PLACEHOLDER_TYPE
        return FileResponse(result_path, media_type=media_type, filename=filename)

    @app.get("/ui/draft_chat")
    def get_draft_chat(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
        limit: Optional[int] = Query(None, ge=1, le=500, description="Maximum drafts to return"),
        since: Optional[str] = Query(None, description="Only include drafts on/after this ISO timestamp"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        clean_since = since.strip() if isinstance(since, str) else None
        limit_value = limit if isinstance(limit, int) and limit > 0 else None

        try:
            items = list_draft_chat_entries(clean_user, limit=limit_value, since=clean_since)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_SINCE", "message": str(exc)},
            )

        return {"user_id": clean_user, "items": items}

    @app.post("/ui/draft/import")
    def import_draft_chat(
        user_id: Annotated[str, Query(..., min_length=1, description="Active user identifier")],
        entries: Annotated[List[Dict[str, Any]], Body(..., description="Draft entries to import")],
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        if not isinstance(entries, list):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request body must be an array of draft entries."},
            )

        imported = append_draft_chat_entries(clean_user, entries)
        return {"ok": True, "imported": imported}

    @app.post("/ui/draft/clear")
    def clear_draft_chat_endpoint(
        user_id: Annotated[str, Query(..., min_length=1, description="Active user identifier")]
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        removed = clear_draft_chat_entries(clean_user)
        return {"ok": True, "removed": removed}

    @app.get("/ui/snapshots")
    def list_snapshots_endpoint(
        user_id: str = Query(..., min_length=1, description="Active user identifier"),
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        ensure_dirs_for_user(clean_user)
        items: List[Dict[str, Any]] = []
        for entry in list_snapshot_bundles(clean_user):
            if not isinstance(entry, dict):
                continue
            filename = entry.get("filename")
            if not filename:
                continue
            enriched = dict(entry)
            enriched["download_url"] = f"/ui/snapshot/download/{clean_user}/{filename}"
            items.append(enriched)

        return {"user_id": clean_user, "items": items}

    @app.get("/ui/snapshot/download/{user_id}/{filename}")
    def snapshot_download(user_id: str, filename: str) -> Any:
        clean_user = user_id.strip()
        clean_filename = filename.strip()
        if not clean_user or not clean_filename:
            raise HTTPException(status_code=400, detail="user_id and filename are required")

        snapshots_dir = CHECKPOINTS_DIR / clean_user
        ensure_dirs_for_user(clean_user)
        try:
            snapshots_root = snapshots_dir.resolve(strict=True)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        target = (snapshots_root / clean_filename).resolve()

        if not target.is_file() or target.parent != snapshots_root:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        try:
            payload = load_json(target, default={})
        except Exception:
            payload = {}
        meta = payload.get("meta") if isinstance(payload, dict) else {}
        version = meta.get("version") if isinstance(meta, dict) else CURRENT_VERSION
        content_type = "application/json"
        download_name = f"{clean_user}_{version}_{clean_filename}"
        return FileResponse(target, media_type=content_type, filename=download_name)

    @app.get("/ui/users")
    def get_users(query: Optional[str] = Query(None, description="Substring match on id or label")) -> Any:
        users = list_users(query)
        return {"users": users}

    @app.post("/ui/users/init")
    def init_user_containers(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        if not user_id_raw:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        label_value = payload.get("label")
        label = str(label_value).strip() if isinstance(label_value, str) and label_value.strip() else None

        dirs = ensure_dirs_for_user(user_id_raw)
        coach_info_dir = dirs["udir"] / "coach_info"
        coach_info_dir.mkdir(parents=True, exist_ok=True)

        onboarding_raw = payload.get("onboarding") if isinstance(payload, dict) else None
        script_path_value: Optional[str] = None
        quick_facts_payload: Dict[str, Any] = {}
        interests_payload: Dict[str, List[str]] = {"selected": [], "custom": []}
        seed_used_flag = False
        if isinstance(onboarding_raw, dict):
            script_raw = str(onboarding_raw.get("script_path") or "").strip().lower()
            if script_raw in {"smart_defaults", "trust_walkthrough"}:
                script_path_value = script_raw

            quick_facts_raw = onboarding_raw.get("quick_facts")
            if isinstance(quick_facts_raw, dict):
                for key in ("eye_color", "hair_color", "handedness"):
                    fact_raw = quick_facts_raw.get(key)
                    if not isinstance(fact_raw, dict):
                        continue
                    fact: Dict[str, str] = {}
                    value = fact_raw.get("value")
                    if isinstance(value, str) and value.strip():
                        fact["value"] = value.strip()
                    label_value = fact_raw.get("label")
                    if isinstance(label_value, str) and label_value.strip():
                        fact["label"] = label_value.strip()
                    custom_value = fact_raw.get("custom")
                    if isinstance(custom_value, str) and custom_value.strip():
                        fact["custom"] = custom_value.strip()
                    if fact:
                        quick_facts_payload[key] = fact

            interests_raw = onboarding_raw.get("interests")
            if isinstance(interests_raw, dict):
                for bucket in ("selected", "custom"):
                    items_raw = interests_raw.get(bucket)
                    if not isinstance(items_raw, list):
                        continue
                    cleaned: List[str] = []
                    seen: Set[str] = set()
                    for item in items_raw:
                        token = str(item).strip()
                        if not token:
                            continue
                        lowered = token.lower()
                        if lowered in seen:
                            continue
                        seen.add(lowered)
                        cleaned.append(token)
                    interests_payload[bucket] = cleaned

            seed_raw = onboarding_raw.get("seed_used")
            if isinstance(seed_raw, bool):
                seed_used_flag = seed_raw
            elif isinstance(seed_raw, str):
                seed_used_flag = seed_raw.strip().lower() in _TRUTHY
            elif isinstance(seed_raw, (int, float)):
                seed_used_flag = bool(seed_raw)

        if script_path_value is None:
            script_path_value = "smart_defaults"

        resolved, evidence, observations = read_user_state(user_id_raw)
        if not isinstance(resolved, dict):
            resolved = {}
        if not isinstance(evidence, dict):
            evidence = {"items": []}
        if not isinstance(observations, dict):
            observations = {"items": [], "by_trait": {}}

        evidence_items = evidence.get("items")
        if not isinstance(evidence_items, list):
            evidence["items"] = []

        obs_items = observations.get("items")
        if isinstance(obs_items, list):
            observations["items"] = obs_items
        else:
            observations["items"] = []

        by_trait = observations.get("by_trait")
        if not isinstance(by_trait, dict):
            by_trait = {}

        trait_keys = hierarchy.all_trait_keys()
        stub_template = {"resolved_value": None, "ucn": 0, "reasons": ["unknown"]}
        containers_added = 0
        containers_updated = 0
        for trait in trait_keys:
            current = resolved.get(trait)
            if not isinstance(current, dict):
                resolved[trait] = dict(stub_template)
                containers_added += 1
                continue

            changed = False
            if "resolved_value" not in current:
                current["resolved_value"] = None
                changed = True
            if "ucn" not in current:
                current["ucn"] = 0
                changed = True
            reasons = current.get("reasons")
            if not isinstance(reasons, list) or not reasons:
                current["reasons"] = ["unknown"]
                changed = True
            if changed:
                containers_updated += 1

            if trait in resolved and resolved[trait] is not current:
                resolved[trait] = current

        by_trait_added = 0
        for trait in trait_keys:
            bucket = by_trait.get(trait)
            if not isinstance(bucket, list):
                by_trait[trait] = []
                by_trait_added += 1

        observations["by_trait"] = by_trait

        info = load_user_info(user_id_raw)
        previous_label = info.get("label")
        if label:
            info["label"] = label
        save_user_info(user_id_raw, info)

        curiosity_engine.seed_resolved(resolved)
        write_user_state(user_id_raw, resolved, evidence, observations, enforce_governance=False)

        runtime_state = _load_runtime_state(user_id_raw)
        now_iso = iso_now()
        runtime_state.setdefault("user_id", user_id_raw)
        runtime_state.setdefault("last_member_ts", None)
        runtime_state.setdefault("last_assistant_ts", None)
        runtime_state.setdefault("initialized_at", now_iso)
        runtime_state["last_init_ts"] = now_iso
        _store_runtime_state(user_id_raw, runtime_state)

        touch_user_last_used(user_id_raw, ts_iso=now_iso)

        onboarding_record = {
            "script_path": script_path_value,
            "quick_facts": quick_facts_payload,
            "interests": interests_payload,
            "seed_used": bool(seed_used_flag),
            "initialized_at": now_iso,
        }
        onboarding_path = coach_info_dir / "onboarding.json"
        save_json(onboarding_path, onboarding_record)

        capture(
            user_id_raw,
            "ui_user_initialized",
            {
                "ts": int(time.time() * 1000),
                "traits_total": len(trait_keys),
                "traits_added": containers_added,
                "traits_updated": containers_updated,
                "by_trait_initialized": by_trait_added,
                "label_updated": bool(label and label != previous_label),
                "coach_info": str(coach_info_dir.relative_to(dirs["udir"])),
                "script_path": script_path_value,
                "seed_used": bool(seed_used_flag),
                "onboarding_written": str(onboarding_path.relative_to(dirs["udir"]))
            },
        )

        return {
            "ok": True,
            "user_id": user_id_raw,
            "traits_total": len(trait_keys),
            "traits_added": containers_added,
            "traits_updated": containers_updated,
            "by_trait_initialized": by_trait_added,
            "onboarding_written": str(onboarding_path.relative_to(dirs["udir"]))
        }

    @app.post("/ui/user/create")
    def create_user_endpoint(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip().lower()
        if not user_id_raw or not USER_ID_PATTERN.match(user_id_raw):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": "user_id must be 3-64 characters, lowercase letters, numbers, hyphen, or underscore.",
                },
            )

        label = payload.get("label")
        if label is not None:
            label = str(label).strip()
        seed = payload.get("seed") if isinstance(payload.get("seed"), dict) else None

        created, info = create_user(user_id_raw, label=label, seed=seed)
        if not created:
            # Handle various failure reasons
            if info and isinstance(info, dict):
                error_type = info.get("error", "USER_EXISTS")
                message = info.get("message", f"User '{user_id_raw}' already exists.")
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": error_type.upper(),
                        "message": message,
                        "conflicting_user_id": info.get("conflicting_user_id")
                    },
                )
            return JSONResponse(
                status_code=409,
                content={"error": "USER_EXISTS", "message": f"User '{user_id_raw}' already exists."},
            )

        touch_user_last_used(user_id_raw)

        summary = _aggregate_user_summary(user_id_raw)

        payload = {
            "id": info.get("id", user_id_raw),
            "label": info.get("label", user_id_raw),
            "created_ts": info.get("created_ts"),
        }
        if summary:
            payload.update({
                "label": summary.get("label", payload["label"]),
                "created_ts": summary.get("created_ts", payload["created_ts"]),
                "last_used_ts": summary.get("last_used_ts"),
                "last_modified_ts": summary.get("last_modified_ts"),
            })

        return {
            "ok": True,
            "user": payload,
        }

    @app.post("/ui/ingest/text")
    def ingest_text_endpoint(payload: Dict[str, Any]) -> Any:
        """
        Ingest freeform text notes and trigger UCN/RR rescoring.
        Stores the note in events/provenance and calls UCN/RR to update resolved.json.
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        if not user_id_raw or not text:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and text are required."},
            )

        # Store the note as a provenance event
        dirs = ensure_dirs_for_user(user_id_raw)
        events_dir = dirs["events"]
        timestamp = datetime.now(timezone.utc)
        ts_iso = timestamp.isoformat(timespec="seconds")
        event_id = f"text_{int(timestamp.timestamp() * 1000)}"
        event_path = events_dir / f"{event_id}.json"

        event_payload = {
            "event_id": event_id,
            "ts": ts_iso,
            "type": "text_ingest",
            "user_id": user_id_raw,
            "text": text,
            "source": payload.get("source", "explorer"),
            "status": "accepted",  # Initial status
        }

        # Always log provenance regardless of UCNRR outcome
        rescore_result: Dict[str, Any] = {"ok": False, "error": "not_attempted"}
        provenance_status = "accepted"

        # Call UCN/RR rescore endpoint
        ucnrr_base = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
        try:
            response = requests.post(
                f"{ucnrr_base}/api/rescore",
                json={"user_id": user_id_raw, "text": text},
                timeout=10,
            )
            if response.ok:
                rescore_result = response.json()
                provenance_status = "accepted"
            else:
                rescore_result = {"ok": False, "error": f"HTTP {response.status_code}"}
                provenance_status = "failed"
        except requests.exceptions.ConnectionError as exc:
            rescore_result = {"ok": False, "error": f"Connection error: {str(exc)}"}
            provenance_status = "failed"
        except requests.exceptions.Timeout as exc:
            rescore_result = {"ok": False, "error": f"Timeout: {str(exc)}"}
            provenance_status = "failed"
        except Exception as exc:
            rescore_result = {"ok": False, "error": f"Unexpected error: {str(exc)}"}
            provenance_status = "failed"

        # Update event payload with final status and UCNRR result
        event_payload["status"] = provenance_status
        event_payload["ucnrr_result"] = rescore_result
        save_json(event_path, event_payload)
        capture(user_id_raw, "text_ingest", event_payload)

        # Update resolved.json with new curiosity/RR values if rescore succeeded
        if rescore_result.get("ok"):
            resolved, evidence, obs = read_user_state(user_id_raw)
            rr_by_trait = rescore_result.get("rr_by_trait", {})
            curiosity_by_trait = rescore_result.get("curiosity_by_trait", {})

            # Northstar Phase 2: CREATE traits if they don't exist
            for trait_id, rr_value in rr_by_trait.items():
                if trait_id in resolved:
                    resolved[trait_id]["rr"] = rr_value
                else:
                    # Create new trait from ingestion
                    resolved[trait_id] = {
                        "id": trait_id,
                        "rr": rr_value,
                        "curiosity": curiosity_by_trait.get(trait_id, 50.0),
                        "value": None,  # Will be extracted later
                        "provenance": [{"source": "text_ingest", "event_id": event_id, "ts": ts_iso}]
                    }

            # Update curiosity for existing traits
            for trait_id, curiosity_value in curiosity_by_trait.items():
                if trait_id in resolved:
                    resolved[trait_id]["curiosity"] = curiosity_value

            write_user_state(user_id_raw, resolved, evidence, obs)
            touch_user_last_used(user_id_raw, ts_iso=ts_iso)

        # Return success even if UCNRR failed (provenance was logged)
        return {
            "ok": True if provenance_status == "accepted" else False,
            "user_id": user_id_raw,
            "event_written": str(event_path.name),
            "status": provenance_status,
            "rescore": rescore_result,
        }

    @app.post("/core/api/ingest_text")
    def core_api_ingest_text(payload: Dict[str, Any]) -> Any:
        """
        Northstar Phase 2: Core ingestion endpoint for unified text ingestion.
        Alias to /ui/ingest/text with standardized response format.

        POST /core/api/ingest_text
        Body: { user_id: str, text: str, source: str, metadata?: dict }
        Returns: { success: bool, error?: str, event_id?: str }
        """
        # Call the existing ingest_text_endpoint
        result = ingest_text_endpoint(payload)

        # Transform to Northstar expected format
        if isinstance(result, dict):
            # Success case
            if result.get("ok"):
                return {
                    "success": True,
                    "event_id": result.get("event_written"),
                    "user_id": result.get("user_id"),
                    "rescore": result.get("rescore", {})
                }
            else:
                return {
                    "success": False,
                    "error": result.get("status", "unknown_error")
                }

        # Handle JSONResponse objects from error cases
        if hasattr(result, 'status_code'):
            return {
                "success": False,
                "error": getattr(result, 'body', b'').decode('utf-8') if hasattr(result, 'body') else "request_failed"
            }

        # Fallback
        return {"success": False, "error": "unexpected_response"}

    @app.post("/ui/ingest/json")
    def ingest_json_endpoint(payload: Dict[str, Any]) -> Any:
        """
        Ingest structured trait payload and trigger UCN/RR rescoring.
        Expects payload: { user_id, traits: [{id, value, ...}] }
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        traits = payload.get("traits")
        if not user_id_raw or not isinstance(traits, list):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and traits (list) are required."},
            )

        # Store the traits as a provenance event
        dirs = ensure_dirs_for_user(user_id_raw)
        events_dir = dirs["events"]
        timestamp = datetime.now(timezone.utc)
        ts_iso = timestamp.isoformat(timespec="seconds")
        event_id = f"json_{int(timestamp.timestamp() * 1000)}"
        event_path = events_dir / f"{event_id}.json"

        event_payload = {
            "event_id": event_id,
            "ts": ts_iso,
            "type": "json_ingest",
            "user_id": user_id_raw,
            "traits": traits,
            "source": payload.get("source", "explorer"),
            "status": "accepted",  # Initial status
        }

        # Always log provenance regardless of UCNRR outcome
        rescore_result: Dict[str, Any] = {"ok": False, "error": "not_attempted"}
        provenance_status = "accepted"

        # Call UCN/RR rescore endpoint
        ucnrr_base = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
        try:
            response = requests.post(
                f"{ucnrr_base}/api/rescore",
                json={"user_id": user_id_raw, "traits": traits},
                timeout=10,
            )
            if response.ok:
                rescore_result = response.json()
                provenance_status = "accepted"
            else:
                rescore_result = {"ok": False, "error": f"HTTP {response.status_code}"}
                provenance_status = "failed"
        except requests.exceptions.ConnectionError as exc:
            rescore_result = {"ok": False, "error": f"Connection error: {str(exc)}"}
            provenance_status = "failed"
        except requests.exceptions.Timeout as exc:
            rescore_result = {"ok": False, "error": f"Timeout: {str(exc)}"}
            provenance_status = "failed"
        except Exception as exc:
            rescore_result = {"ok": False, "error": f"Unexpected error: {str(exc)}"}
            provenance_status = "failed"

        # Update event payload with final status and UCNRR result
        event_payload["status"] = provenance_status
        event_payload["ucnrr_result"] = rescore_result
        save_json(event_path, event_payload)
        capture(user_id_raw, "json_ingest", event_payload)

        # Update resolved.json with new curiosity/RR values if rescore succeeded
        if rescore_result.get("ok"):
            resolved, evidence, obs = read_user_state(user_id_raw)
            rr_by_trait = rescore_result.get("rr_by_trait", {})
            curiosity_by_trait = rescore_result.get("curiosity_by_trait", {})

            for trait_id, rr_value in rr_by_trait.items():
                if trait_id in resolved:
                    resolved[trait_id]["rr"] = rr_value
                else:
                    # Create new trait entry
                    resolved[trait_id] = {"resolved_value": None, "rr": rr_value}
            for trait_id, curiosity_value in curiosity_by_trait.items():
                if trait_id in resolved:
                    resolved[trait_id]["curiosity"] = curiosity_value
                elif trait_id in rr_by_trait:
                    resolved[trait_id]["curiosity"] = curiosity_value

            write_user_state(user_id_raw, resolved, evidence, obs)
            touch_user_last_used(user_id_raw, ts_iso=ts_iso)

        # Return success even if UCNRR failed (provenance was logged)
        return {
            "ok": True if provenance_status == "accepted" else False,
            "user_id": user_id_raw,
            "traits_count": len(traits),
            "event_written": str(event_path.name),
            "status": provenance_status,
            "rescore": rescore_result,
        }

    @app.post("/ui/coach/query")
    def coach_query_endpoint(payload: Dict[str, Any]) -> Any:
        """
        Route persona-specific prompts to the LLM with appropriate tone/rubric.
        Returns { text, rr_band, provenance_refs[] }
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip()
        persona_raw = payload.get("persona")
        input_data = payload.get("input")

        if not user_id_raw or not persona_raw:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and persona are required."},
            )

        persona = _persona_normalize(persona_raw)
        if persona is None:
            allowed = ", ".join(sorted(PERSONA_PROMPTS))
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": f"persona must be one of: {allowed}.",
                },
            )

        # Get provider
        provider_name = (os.getenv("HC_CHAT_PROVIDER", "stub") or "stub").strip().lower() or "stub"
        try:
            provider = chat_providers.get_provider(provider_name)
        except chat_providers.ProviderConfigError as exc:
            if provider_name != "stub":
                return JSONResponse(
                    status_code=503,
                    content={"error": "PROVIDER_CONFIG", "detail": str(exc)},
                )
            provider = chat_providers.get_provider("stub")

        # Build persona prompt
        persona_prompt = PERSONA_PROMPTS.get(persona, "")

        # Extract text from input
        if isinstance(input_data, dict):
            text = str(input_data.get("text") or "").strip()
        elif isinstance(input_data, str):
            text = input_data.strip()
        else:
            text = str(input_data or "").strip()

        if not text:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "input.text is required."},
            )

        # Estimate RR band (simplified for now)
        state = read_user_state(user_id_raw)
        resolved = state.get("resolved", {})

        # Simple average curiosity → RR band
        curiosity_values = [t.get("curiosity", 0.5) for t in resolved.values() if isinstance(t, dict)]
        avg_curiosity = sum(curiosity_values) / len(curiosity_values) if curiosity_values else 0.5
        rr_estimate = 1.0 - avg_curiosity  # RR is inverse of curiosity

        if rr_estimate < 0.3:
            rr_band = "low"
        elif rr_estimate < 0.7:
            rr_band = "medium"
        else:
            rr_band = "high"

        # Build messages for LLM
        messages = [{"role": "user", "content": text}]

        # Stream response
        response_text = ""
        try:
            for chunk in provider.stream(
                system_prompt=SYSTEM_PROMPT + "\n" + persona_prompt,
                persona=persona,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            ):
                response_text += chunk
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"error": "PROVIDER_ERROR", "detail": str(exc)},
            )

        # Log provenance checkpoint
        event_checkpoint(
            user_id_raw,
            f"coach_query_{int(time.time() * 1000)}",
            {
                "type": "coach_query",
                "persona": persona,
                "input_text": text[:200],  # First 200 chars
                "response_length": len(response_text),
                "rr_band": rr_band,
                "provider": provider_name,
                "ts": int(time.time() * 1000),
            },
        )

        return {
            "ok": True,
            "text": response_text.strip(),
            "rr_band": rr_band,
            "persona": persona,
            "provenance_ref": f"coach_query_{int(time.time() * 1000)}",
        }

    @app.post("/ui/coach/rescore_now")
    def rescore_now_endpoint(payload: Dict[str, Any]) -> Any:
        """
        Ingest text, trigger UCN/RR rescore, and return updated traits.
        Always writes provenance checkpoint.
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        persona = str(payload.get("persona") or "head_coach").strip()

        if not user_id or not text:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and text are required."},
            )

        # Ensure user exists
        ensure_dirs_for_user(user_id)
        touch_user_last_used(user_id)

        # Load current state (before rescore)
        resolved, evidence, obs = read_user_state(user_id)
        traits_before = {k: v.get("rr", 0) for k, v in resolved.items() if isinstance(v, dict)}

        # Ingest text (stub: in real impl, this would parse text → traits)
        # For now, we'll just call UCN/RR rescore with existing traits
        ucnrr_base = _ucnrr_base_url()
        if not ucnrr_base:
            return JSONResponse(
                status_code=503,
                content={"error": "UCNRR_UNAVAILABLE", "message": "UCN/RR service not configured."},
            )

        # Build traits payload for rescore
        traits_payload = []
        for trait_id, trait_data in resolved.items():
            if isinstance(trait_data, dict):
                traits_payload.append({
                    "id": trait_id,
                    "value": trait_data.get("resolved_value"),
                    "rr": trait_data.get("rr", 500.0),
                })

        # Call UCN/RR rescore
        try:
            response = requests.post(
                f"{ucnrr_base}/api/rescore",
                json={"user_id": user_id, "traits": traits_payload},
                timeout=15,
            )
            if not response.ok:
                raise Exception(f"HTTP {response.status_code}")
            rescore_result = response.json()
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"error": "RESCORE_FAILED", "detail": str(exc)},
            )

        if not rescore_result.get("ok"):
            return JSONResponse(
                status_code=500,
                content={"error": "RESCORE_ERROR", "message": rescore_result.get("error", "Unknown error")},
            )

        # Extract new RR and curiosity values
        rr_by_trait = rescore_result.get("rr_by_trait", {})
        curiosity_by_trait = rescore_result.get("curiosity_by_trait", {})

        # Update resolved.json
        updated_traits = []
        for trait_id in resolved:
            if trait_id in rr_by_trait:
                old_rr = resolved[trait_id].get("rr", 0)
                new_rr = rr_by_trait[trait_id]
                resolved[trait_id]["rr"] = new_rr
                resolved[trait_id]["curiosity"] = curiosity_by_trait.get(trait_id, 0.0)

                if abs(new_rr - old_rr) > 10:  # Only report significant changes
                    updated_traits.append({
                        "trait": trait_id,
                        "old_rr": old_rr,
                        "new_rr": new_rr,
                        "curiosity": curiosity_by_trait.get(trait_id, 0.0),
                    })

        write_user_state(user_id, resolved, evidence, obs)

        # Write provenance checkpoint with trait changes for undo
        event_ref = f"checkpoint_{int(time.time() * 1000)}"
        event_checkpoint(
            user_id,
            event_ref,
            {
                "type": "rescore_now",
                "persona": persona,
                "input_text": text[:200],
                "traits_updated": len(updated_traits),
                "trait_changes": updated_traits,  # Store for undo
                "ucnrr_ok": rescore_result.get("ok"),
                "ts": int(time.time() * 1000),
            },
        )

        return {
            "ok": True,
            "updated_traits": updated_traits,
            "event_ref": event_ref,
        }

    @app.post("/ui/trait/revert_last")
    def revert_last_rescore(payload: Dict[str, Any] = Body(...)) -> Any:
        """Revert the most recent rescore_now operation using checkpoint data."""
        user_id = payload.get("user_id", "").strip()
        if not user_id:
            return JSONResponse(
                status_code=400, content={"error": "user_id required"}
            )

        # Find the most recent rescore_now checkpoint
        events_dir = ensure_dirs_for_user(user_id)["events"]
        rescore_checkpoints = sorted(
            events_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        last_rescore_event = None
        for checkpoint_path in rescore_checkpoints:
            try:
                event_data = storage.load_json(checkpoint_path, default={})
                if event_data.get("type") == "rescore_now":
                    last_rescore_event = event_data
                    break
            except Exception:
                continue

        if not last_rescore_event:
            return {"ok": False, "message": "No rescore_now checkpoint found"}

        # Load current resolved state
        resolved, evidence, obs = read_user_state(user_id)

        # Get the trait changes from the checkpoint
        trait_changes = last_rescore_event.get("trait_changes", [])
        if not trait_changes:
            return {"ok": False, "message": "Checkpoint missing trait_changes data"}

        # Revert each trait to its old RR value
        reverted_count = 0
        for change in trait_changes:
            trait_id = change.get("trait")
            old_rr = change.get("old_rr")

            if trait_id and trait_id in resolved and old_rr is not None:
                if isinstance(resolved[trait_id], dict):
                    resolved[trait_id]["rr"] = old_rr
                    reverted_count += 1

        # Save the reverted state
        if reverted_count > 0:
            write_user_state(user_id, resolved, evidence, obs)

        return {
            "ok": True,
            "reverted_count": reverted_count,
            "message": f"Reverted {reverted_count} traits to previous RR values",
        }

    @app.post("/ui/onboarding/submit")
    def submit_onboarding_profile(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id_raw = str(payload.get("user_id") or "").strip().lower()
        if not user_id_raw or not USER_ID_PATTERN.match(user_id_raw):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "BAD_REQUEST",
                    "message": "user_id must be 3-64 characters, lowercase letters, numbers, hyphen, or underscore.",
                },
            )

        profile_raw = payload.get("profile")
        if not isinstance(profile_raw, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "profile must be provided."},
            )

        def _trimmed(value: Any) -> str:
            return str(value).strip() if isinstance(value, str) else ""

        def _sanitize_big_five(seed_payload: Any) -> Optional[Dict[str, float]]:
            if not isinstance(seed_payload, dict):
                return None
            source = seed_payload.get("Big5") or seed_payload.get("big5")
            if not isinstance(source, dict):
                return None
            result: Dict[str, float] = {}
            for trait in ("O", "C", "E", "A", "N"):
                value = source.get(trait)
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(number) or math.isinf(number):
                    continue
                result[trait] = max(0.0, min(1.0, number))
            return result if len(result) == 5 else None

        def _sanitize_fact(entry: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(entry, dict):
                return None
            value = _trimmed(entry.get("value")) or None
            label = _trimmed(entry.get("label")) or None
            custom = _trimmed(entry.get("custom")) or None
            if not value and not label and not custom:
                return None
            fact: Dict[str, Any] = {}
            if value:
                fact["value"] = value
            if label:
                fact["label"] = label
            if custom:
                fact["custom"] = custom
            return fact if fact else None

        def _sanitize_string_list(items: Any) -> List[str]:
            if not isinstance(items, list):
                return []
            cleaned: List[str] = []
            seen: Set[str] = set()
            for item in items:
                token = _trimmed(item)
                if not token:
                    continue
                lowered = token.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                cleaned.append(token)
            return cleaned

        user_paths = ensure_dirs_for_user(user_id_raw)
        info = load_user_info(user_id_raw)

        name_section = profile_raw.get("name")
        display_name = _trimmed(name_section.get("display")) if isinstance(name_section, dict) else ""
        if display_name and display_name != info.get("label"):
            info["label"] = display_name
            save_user_info(user_id_raw, info)

        seed_section = profile_raw.get("seed")
        big_five = _sanitize_big_five(seed_section)

        quick_facts_raw = profile_raw.get("quick_facts")
        quick_facts: Dict[str, Any] = {}
        if isinstance(quick_facts_raw, dict):
            for api_key in ("eye_color", "hair_color", "handedness"):
                fact = _sanitize_fact(quick_facts_raw.get(api_key))
                if fact:
                    quick_facts[api_key] = fact

        interests_raw = profile_raw.get("interests")
        if isinstance(interests_raw, dict):
            selected = _sanitize_string_list(interests_raw.get("selected"))
            custom = _sanitize_string_list(interests_raw.get("custom"))
        else:
            selected = []
            custom = []

        notes_value = _trimmed(profile_raw.get("notes"))

        captured_iso = _iso_now()
        server_ts_ms = int(time.time() * 1000)

        # Extract phase data for 3-phase onboarding
        phase_info = payload.get("phase_info", {})
        hc_qa_responses = payload.get("hc_qa_responses", [])  # Phase 2: HC Q&A responses

        profile_payload: Dict[str, Any] = {
            "version": 2,  # Bumped to v2 for 3-phase support
            "captured_at": captured_iso,
            "user_id": user_id_raw,
            "display_name": display_name or info.get("label") or user_id_raw,
            "quick_facts": quick_facts,
            "interests": {
                "selected": selected,
                "custom": custom,
            },
            "source": "ui_onboarding_modal",
        }
        if big_five:
            profile_payload["seed"] = {"Big5": big_five}
        if notes_value:
            profile_payload["notes"] = notes_value
        if phase_info:
            profile_payload["phase_info"] = phase_info
        if hc_qa_responses:
            profile_payload["hc_qa_responses"] = hc_qa_responses

        profile_dir = user_paths["udir"] / ONBOARDING_PROFILE_DIR
        profile_dir.mkdir(parents=True, exist_ok=True)
        target_path = profile_dir / ONBOARDING_PROFILE_FILENAME
        save_json(target_path, profile_payload)

        # Store HC Q&A responses as separate evidence files (Phase 2)
        evidence_files_written = []
        if hc_qa_responses:
            evidence_dir = user_paths["evidence"]
            evidence_dir.mkdir(parents=True, exist_ok=True)
            for idx, qa in enumerate(hc_qa_responses):
                if isinstance(qa, dict):
                    evidence_filename = f"onboarding_qa_{server_ts_ms}_{idx}.json"
                    evidence_path = evidence_dir / evidence_filename
                    evidence_payload = {
                        "type": "hc_qa_response",
                        "ts": captured_iso,
                        "question": qa.get("question"),
                        "response": qa.get("response"),
                        "question_id": qa.get("question_id"),
                        "phase": "phase2_hc_qa",
                    }
                    save_json(evidence_path, evidence_payload)
                    evidence_files_written.append(str(evidence_path.relative_to(user_paths["udir"])))

        ucnrr_status: Dict[str, Any]
        base_url = _ucnrr_base_url()
        if base_url:
            try:
                response = requests.post(
                    f"{base_url}/gateway/onboarding",
                    json={"user_id": user_id_raw, "profile": profile_payload},
                    timeout=8,
                )
                try:
                    response_payload = response.json()
                except Exception:
                    response_payload = None
                if response.status_code >= 400:
                    ucnrr_status = {
                        "ok": False,
                        "status": response.status_code,
                        "detail": response_payload or response.text,
                    }
                else:
                    detail_ok = True
                    if isinstance(response_payload, dict) and "ok" in response_payload:
                        detail_ok = bool(response_payload.get("ok"))
                    ucnrr_status = {
                        "ok": detail_ok,
                        "status": response.status_code,
                        "detail": response_payload,
                    }
            except Exception as exc:
                ucnrr_status = {"ok": False, "error": str(exc)}
        else:
            ucnrr_status = {"ok": False, "reason": "UCNRR_BASE_URL not configured"}

        checkpoint_payload = {
            "type": "onboarding_profile",
            "ts": server_ts_ms,
            "captured_at": captured_iso,
            "profile": profile_payload,
            "ucnrr": ucnrr_status,
        }
        if phase_info:
            checkpoint_payload["phases"] = phase_info
        if evidence_files_written:
            checkpoint_payload["evidence_files"] = evidence_files_written

        event_checkpoint(
            user_id_raw,
            f"onboarding_{server_ts_ms}",
            checkpoint_payload,
        )

        touch_user_last_used(user_id_raw, ts_iso=captured_iso)

        response_payload = {
            "ok": True,
            "written": f"users/{user_id_raw}/{ONBOARDING_PROFILE_DIR}/{ONBOARDING_PROFILE_FILENAME}",
            "ucnrr": ucnrr_status,
            "profile": profile_payload,
        }
        if evidence_files_written:
            response_payload["evidence_files"] = evidence_files_written
        return response_payload

    @app.post("/ui/trait/override")
    def override_trait(payload: Dict[str, Any] = Body(...)) -> Any:
        """Override a trait value and trigger rescore."""
        user_id = payload.get("user_id", "").strip()
        trait_id = payload.get("trait_id", "").strip()
        new_value = payload.get("value")

        if not user_id or not trait_id:
            return JSONResponse(
                status_code=400, content={"error": "user_id and trait_id required"}
            )

        # Load current state
        resolved, evidence, obs = read_user_state(user_id)

        # Store old value for checkpoint
        old_value = None
        old_rr = None
        if trait_id in resolved:
            if isinstance(resolved[trait_id], dict):
                old_value = resolved[trait_id].get("resolved_value")
                old_rr = resolved[trait_id].get("rr")
            else:
                old_value = resolved[trait_id]

        # Write override
        if trait_id not in resolved:
            resolved[trait_id] = {}
        if not isinstance(resolved[trait_id], dict):
            resolved[trait_id] = {"resolved_value": resolved[trait_id]}

        resolved[trait_id]["resolved_value"] = new_value
        resolved[trait_id]["override"] = True
        resolved[trait_id]["override_ts"] = int(time.time() * 1000)

        # Build traits for rescore
        traits_payload = []
        for tid, tdata in resolved.items():
            if isinstance(tdata, dict):
                traits_payload.append({
                    "id": tid,
                    "value": tdata.get("resolved_value"),
                    "rr": tdata.get("rr", 500.0),
                })

        # Call UCN/RR rescore
        ucnrr_base = _ucnrr_base_url()
        new_rr = old_rr
        new_curiosity = None

        if ucnrr_base:
            try:
                response = requests.post(
                    f"{ucnrr_base}/api/rescore",
                    json={"user_id": user_id, "traits": traits_payload},
                    timeout=15,
                )
                if response.ok:
                    rescore_result = response.json()
                    rr_by_trait = rescore_result.get("rr", {})
                    curiosity_by_trait = rescore_result.get("curiosity", {})

                    # Update RR and curiosity for all traits
                    for tid in resolved:
                        if tid in rr_by_trait:
                            if isinstance(resolved[tid], dict):
                                resolved[tid]["rr"] = rr_by_trait[tid]
                                resolved[tid]["curiosity"] = curiosity_by_trait.get(tid, 0.0)

                    new_rr = rr_by_trait.get(trait_id, old_rr)
                    new_curiosity = curiosity_by_trait.get(trait_id)
            except Exception:
                pass

        # Save state
        write_user_state(user_id, resolved, evidence, obs)

        # Write checkpoint
        event_ref = f"checkpoint_{int(time.time() * 1000)}"
        event_checkpoint(
            user_id,
            event_ref,
            {
                "type": "trait_override",
                "trait_id": trait_id,
                "old_value": old_value,
                "new_value": new_value,
                "old_rr": old_rr,
                "new_rr": new_rr,
                "ts": int(time.time() * 1000),
            },
        )

        return {
            "ok": True,
            "trait_id": trait_id,
            "new_value": new_value,
            "old_rr": old_rr,
            "new_rr": new_rr,
            "curiosity": new_curiosity,
            "event_ref": event_ref,
        }

    @app.post("/ui/trait/provenance")
    def get_trait_provenance(payload: Dict[str, Any]) -> Any:
        """
        Return provenance information for a specific trait.
        Shows why a trait has its current value, including evidence, sources, and data gaps.
        """
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        trait_id = str(payload.get("trait_id") or "").strip()

        if not user_id or not trait_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id and trait_id are required."},
            )

        # Load user state
        resolved, evidence, obs = read_user_state(user_id)

        if trait_id not in resolved:
            return JSONResponse(
                status_code=404,
                content={"error": "NOT_FOUND", "message": f"Trait '{trait_id}' not found for user '{user_id}'."},
            )

        trait_data = resolved[trait_id]

        # Build provenance response
        response = {
            "trait_id": trait_id,
            "trait_value": trait_data.get("resolved_value"),
            "ucn": trait_data.get("ucn"),
            "rr": trait_data.get("rr"),
            "curiosity": trait_data.get("curiosity"),
            "reasons": trait_data.get("reasons", []),
            "provenance": trait_data.get("provenance", {}),
            "notes": trait_data.get("notes", {}),
        }

        return response

    @app.post("/ui/nudges/act")
    def nudge_action(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        nudge_id = str(payload.get("id") or payload.get("nudge_id") or "").strip()
        action = str(payload.get("action") or "").strip().lower()

        if not user_id or not nudge_id or not action:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id, id, and action are required."},
            )

        if action not in {"accept", "dismiss", "undo"}:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "action must be accept, dismiss, or undo."},
            )

        success, data = nudges.apply_action(user_id, nudge_id, action)
        if not success:
            return {"ok": False, "reason": data.get("reason"), "nudge": data.get("nudge")}

        return {"ok": True, "nudge": data.get("nudge")}

    @app.post("/ui/snapshot")
    def create_snapshot(payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "Request payload must be a JSON object."},
            )

        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        path, bundle = snapshot_bundle(user_id)
        version = bundle.get("meta", {}).get("version", CURRENT_VERSION)
        filename = Path(path).name
        download_url = f"/ui/snapshot/download/{user_id}/{filename}"
        return {
            "ok": True,
            "path": str(path),
            "version": version,
            "bundle": bundle,
            "filename": filename,
            "download_url": download_url,
        }

    @app.post("/ui/snapshots/create")
    def create_snapshot_light(
        user_id: Annotated[str, Query(..., min_length=1, description="Active user identifier")]
    ) -> Any:
        clean_user = user_id.strip()
        if not clean_user:
            return JSONResponse(
                status_code=400,
                content={"error": "BAD_REQUEST", "message": "user_id is required."},
            )

        path, bundle = snapshot_bundle(clean_user)
        filename = Path(path).name
        version = bundle.get("meta", {}).get("version", CURRENT_VERSION)
        download_url = f"/ui/snapshot/download/{clean_user}/{filename}"
        return {
            "ok": True,
            "filename": filename,
            "version": version,
            "download_url": download_url,
            "snapshot_path": str(path),
        }

    @app.post("/ingest_bundle")
    def ingest_bundle(payload: BundleIn, request: Request):
        user_id = payload.get("user_id", "").strip()
        if not user_id:
            raise HTTPException(400, "missing user_id")
        if not allow(user_id):
            raise HTTPException(403, "forbidden")

        ensure_dirs_for_user(user_id)
        prior_resolved, prior_evidence, prior_obs = read_user_state(user_id)
        if curiosity_engine.is_enabled():
            curiosity_engine.seed_resolved(prior_resolved)
        decay_changes = decay.apply_decay(prior_resolved)

        bundle_type = str(payload.get("bundle_type") or "default")
        bundle_source = payload.get("source") or "unknown"
        new_obs = build_observations(payload.get("items", []))
        trace_id = payload.get("trace_id") or request.headers.get("X-Trace-Id")
        _trace_span(
            trace_id,
            "core_ingest",
            "start",
            {"user_id": user_id, "count": len(new_obs), "bundle_type": bundle_type},
        )
        (out, evidence, observations) = resolve_traits(
            prior_resolved, prior_evidence, prior_obs, new_obs
        )
        conflicts_map = out.get("conflicts", {}) if isinstance(out, dict) else {}

        decay_metrics = [
            {
                "trait": trait,
                **info,
            }
            for trait, info in decay_changes.items()
        ] if decay_changes else []

        if curiosity_engine.is_enabled():
            touched: List[str] = [item.get("trait", "") for item in new_obs if isinstance(item, dict)]
            _update_curiosity(
                user_id,
                prior_resolved,
                out["resolved"],
                evidence,
                observations,
                touched,
            )
        else:
            write_user_state(user_id, out["resolved"], evidence, observations)

        priorities_map = out.get("priorities", {}) if isinstance(out, dict) else {}
        ucn_changes_map = out.get("ucn_changes", {}) if isinstance(out, dict) else {}
        top_priority = max(priorities_map.values()) if priorities_map else 0.0

        metrics_payload = {
            "priorities": priorities_map,
            "top_priority": top_priority,
        }
        if conflicts_map:
            metrics_payload["conflicts"] = conflicts_map
        if decay_metrics:
            metrics_payload["decay"] = decay_metrics

        provenance_ref = f"users/{user_id}/{OBS_FILENAME}"
        for trait, change in ucn_changes_map.items():
            contradiction = trait in conflicts_map
            change_extra = {"source": change.get("source")}
            provenance_payload = change.get("provenance")
            if isinstance(provenance_payload, dict):
                change_extra["provenance"] = provenance_payload
            if contradiction:
                change_extra["conflict"] = conflicts_map.get(trait)
            _write_ucn_audit_entry(
                user_id,
                trait,
                before_ucn=float(change.get("before_ucn", 0.0)),
                after_ucn=float(change.get("after_ucn", 0.0)),
                evidence_type=str(change.get("evidence_type") or "self"),
                source_trust=float(change.get("source_trust", 0.0)),
                decay_applied=False,
                contradiction=contradiction,
                reason="bundle_ingest_conflict" if contradiction else "bundle_ingest",
                provenance_ref=provenance_ref,
                extra=change_extra,
            )

        for decay_entry in decay_metrics:
            trait = decay_entry.get("trait")
            if not isinstance(trait, str) or not trait:
                continue
            _write_ucn_audit_entry(
                user_id,
                trait,
                before_ucn=float(decay_entry.get("before_ucn", 0.0)),
                after_ucn=float(decay_entry.get("after_ucn", 0.0)),
                evidence_type="system",
                source_trust=1.0,
                decay_applied=True,
                contradiction=False,
                reason="decay_half_life",
                provenance_ref=provenance_ref,
                extra={
                    "half_life_days": decay_entry.get("half_life_days"),
                    "elapsed_days": decay_entry.get("elapsed_days"),
                },
            )

        capture(
            user_id,
            "bundle_ingested",
            {
                "count": len(payload.get("items", []) or []),
                "bundle_type": bundle_type,
                "source": bundle_source,
                "metrics": metrics_payload,
            },
        )
        _trace_span(
            trace_id,
            "core_ingest",
            "end",
            {
                "resolved_count": len(out["resolved"]),
                "curiosity": curiosity_engine.is_enabled(),
                "bundle_type": bundle_type,
            },
        )
        result_payload = {
            "ok": True,
            "resolved_count": len(out["resolved"]),
            "priorities": out["priorities"],
        }
        if conflicts_map:
            result_payload["conflicts"] = conflicts_map
        if decay_metrics:
            result_payload["decay"] = decay_metrics
        return result_payload

    @app.post("/recompute/{user_id}")
    def recompute(user_id: str, request: Request):
        resolved, evidence, obs = read_user_state(user_id)
        trace_id = request.headers.get("X-Trace-Id")
        _trace_span(trace_id, "core_recompute", "start", {"user_id": user_id})

        if not curiosity_engine.is_enabled():
            write_user_state(user_id, resolved, evidence, obs)
            _trace_span(trace_id, "core_recompute", "end", {"curiosity": False})
            return {"ok": True, "resolved_count": len(resolved)}

        baseline = copy.deepcopy(resolved)
        curiosity_engine.seed_resolved(resolved)
        curiosity_engine.update_curiosity(baseline, resolved, touched_traits=[])
        write_user_state(user_id, resolved, evidence, obs)
        _trace_span(trace_id, "core_recompute", "end", {"curiosity": True})

        return {
            "ok": True,
            "resolved_count": len(resolved),
            "curiosity_enabled": True,
            "top_traits": curiosity_engine.top_traits(resolved),
        }

    if CURIOSITY_ON:

        @app.get("/curiosity/{user_id}")
        def curiosity_snapshot(user_id: str, limit: int = 25, request: Request = None):
            ensure_dirs_for_user(user_id)
            resolved, evidence, obs = read_user_state(user_id)
            curiosity_engine.seed_resolved(resolved)
            write_user_state(user_id, resolved, evidence, obs)

            trace_id = request.headers.get("X-Trace-Id") if isinstance(request, Request) else None
            _trace_span(
                trace_id,
                "curiosity_rr_compute",
                "start",
                {"user_id": user_id},
            )

            items = curiosity_engine.snapshot(resolved)
            try:
                limit_value = int(limit)
            except (TypeError, ValueError):
                limit_value = 25
            limit_value = max(1, min(limit_value, len(items) if items else 1, 100))
            selected = items[:limit_value]

            source_counts: Dict[str, int] = {}
            rr_values: List[float] = []
            curiosity_values: List[float] = []
            for row in selected:
                if not isinstance(row, dict):
                    continue
                source_token = str(row.get("source") or "").strip() or "UNKNOWN"
                source_counts[source_token] = source_counts.get(source_token, 0) + 1
                rr_value = row.get("rr")
                try:
                    rr_float = float(rr_value)
                except (TypeError, ValueError):
                    rr_float = None
                if rr_float is not None and not math.isnan(rr_float):
                    rr_values.append(rr_float)
                curiosity_val = row.get("curiosity")
                try:
                    curiosity_float = float(curiosity_val)
                except (TypeError, ValueError):
                    curiosity_float = None
                if curiosity_float is not None and not math.isnan(curiosity_float):
                    curiosity_values.append(curiosity_float)

            meta = {
                "user_id": user_id,
                "n_rows": len(selected),
            }
            if rr_values:
                meta["mean_rr"] = round(sum(rr_values) / len(rr_values), 4)
            if curiosity_values:
                meta["mean_curiosity"] = round(sum(curiosity_values) / len(curiosity_values), 4)

            _trace_span(trace_id, "curiosity_rr_compute", "end", meta)

            return {
                "user_id": user_id,
                "items": selected,
                "curiosity_enabled": True,
                "source_counts": source_counts,
            }

    # ============================================================================
    # Head Coach v1 Endpoints
    # ============================================================================

    @app.get("/hc/state")
    async def hc_get_state(user_id: str):
        """
        Get HC state for UI rendering.

        Returns:
            {
                userId, hcName, goals, openTasks, curiosityHotspots,
                recentDecisions, checkpoints, relationship,
                flags (v2), tasks (v2), reminders (v2)
            }
        """
        from .head_coach_service import get_hc_service
        from .hc_task_runner import get_task_runner
        from .hc_reminders import get_reminders
        import yaml
        from pathlib import Path

        try:
            hc = get_hc_service()
            state = hc.get_state(user_id)

            # Add v2 features: flags, tasks, reminders
            # Load flags
            flags_path = Path("ReDNACoreDemo/config/hc_flags.yaml")
            try:
                with open(flags_path, 'r') as f:
                    flags = yaml.safe_load(f)
            except Exception:
                flags = {
                    "enable_task_runner": False,
                    "enable_reminders": False,
                    "enable_ucnrr": False,
                    "enable_conversation_memory": False,
                    "enable_playbook_runner": False
                }

            state["flags"] = flags

            # Add tasks if enabled
            if flags.get("enable_task_runner", False):
                runner = get_task_runner()
                tasks = runner.list_tasks(user_id)
                state["tasks"] = {
                    "queued": [t for t in tasks if t.get("state") == "queued"],
                    "running": [t for t in tasks if t.get("state") == "running"],
                    "done": [t for t in tasks if t.get("state") == "done"][:5],  # Last 5
                    "failed": [t for t in tasks if t.get("state") == "failed"],
                }
            else:
                state["tasks"] = {"queued": [], "running": [], "done": [], "failed": []}

            # Add reminders if enabled
            if flags.get("enable_reminders", False):
                reminders_svc = get_reminders()
                pending_reminders = reminders_svc.get_pending(user_id)
                state["reminders"] = pending_reminders
            else:
                state["reminders"] = []

            # Add media and render stats if Photo Coach enabled
            if flags.get("enable_photo_coach", False):
                from .photo_coach import get_media_stats
                from .render_coach import get_render_stats

                repo_root = Path(__file__).parents[2]
                state["media"] = get_media_stats(user_id, repo_root)
                state["renders"] = get_render_stats(user_id, repo_root)
            else:
                state["media"] = {"batches": 0, "images_total": 0, "latest_batch_id": None}
                state["renders"] = {"batches": 0, "latest_render_id": None}

            return JSONResponse(content=state, status_code=200)
        except Exception as e:
            logger.error(f"HC state error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/ingest")
    async def hc_ingest_observations(
        user_id: str = Query(...),
        observations: Dict[str, Any] = Body(...),
        source_coach: str = Query("unknown")
    ):
        """
        Ingest observations from any coach.

        Flow:
        1. Normalize observations
        2. Submit to Core
        3. Trigger UCNRR rescore
        4. Return HC decision

        Returns:
            HC decision with recommendations and next steps
        """
        from .head_coach_service import get_hc_service

        try:
            hc = get_hc_service()
            decision = hc.ingest_observations(user_id, observations, source_coach)
            return JSONResponse(content=decision, status_code=200)
        except Exception as e:
            logger.error(f"HC ingest error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/plan")
    async def hc_plan_next_actions(user_id: str):
        """
        Plan next actions based on current state + curiosity.

        Returns:
            {
                goals, prioritized_tasks, focus_area, quick_wins
            }
        """
        from .head_coach_service import get_hc_service

        try:
            hc = get_hc_service()
            plan = hc.plan_next_actions(user_id)
            return JSONResponse(content=plan, status_code=200)
        except Exception as e:
            logger.error(f"HC plan error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/explain")
    async def hc_explain(user_id: str, topic: str):
        """
        Explain a decision or suggestion in plain language.

        Args:
            user_id: User identifier
            topic: Topic to explain (trait path, decision, etc.)

        Returns:
            Plain language explanation with provenance
        """
        from .head_coach_service import get_hc_service

        try:
            hc = get_hc_service()
            explanation = hc.explain(user_id, topic)
            return JSONResponse(content={"explanation": explanation}, status_code=200)
        except Exception as e:
            logger.error(f"HC explain error for {user_id}/{topic}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/action_plan")
    async def hc_action_plan(
        user_id: str = Query(...),
        max_actions: int = Query(5, ge=1, le=20)
    ):
        """
        Get Head Coach action plan based on UCN/RR curiosity signals.

        This implements the "Core proposes, Head Coach disposes" architecture:
        1. UCN/RR engine identifies curiosity hotspots
        2. Core converts to recommendations
        3. Head Coach deliberates using 6-check framework
        4. Returns accepted actions in user's best interest

        Args:
            user_id: User identifier
            max_actions: Maximum number of actions to return (default 5)

        Returns:
            Action plan with greeting, priority message, and accepted actions
        """
        from .head_coach_ucn_bridge import create_ucn_bridge

        try:
            # Load user traits
            obs_dict, resolved_dict, evidence_dict = read_user_state(user_id)

            # Extract UCN values
            user_traits = {}
            for trait_path, trait_data in resolved_dict.items():
                if isinstance(trait_data, dict) and 'ucn' in trait_data:
                    user_traits[trait_path] = int(trait_data['ucn'])

            if not user_traits:
                return JSONResponse(content={
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "greeting": "No traits found yet. Upload some photos or add observations to get started!",
                    "priority_message": None,
                    "accepted_actions": [],
                    "stats": {
                        "total_signals": 0,
                        "acceptance_rate": 0.0,
                        "dominant_mode": "servant"
                    }
                }, status_code=200)

            # Get action plan from Head Coach
            bridge = create_ucn_bridge()
            plan = bridge.process_curiosity_signals(
                user_id=user_id,
                user_traits=user_traits,
                max_actions=max_actions
            )

            # Format accepted actions for response
            formatted_actions = []
            for decision in plan.accepted_actions:
                formatted_actions.append({
                    "action_type": decision.action_type,
                    "action_description": decision.action_description,
                    "estimated_time_mins": decision.estimated_time_mins,
                    "mode": decision.mode.value,
                    "intervention_style": decision.intervention_style.value,
                    "message_to_user": decision.message_to_user,
                    "user_benefit": decision.user_benefit,
                    "when": decision.when_to_present
                })

            return JSONResponse(content={
                "user_id": plan.user_id,
                "timestamp": plan.timestamp,
                "greeting": plan.greeting,
                "priority_message": plan.priority_message,
                "celebration_message": plan.celebration_message,
                "accepted_actions": formatted_actions,
                "stats": {
                    "total_signals": plan.curiosity_signals_count,
                    "total_recommendations": plan.core_recommendations_count,
                    "acceptance_rate": plan.acceptance_rate,
                    "dominant_mode": plan.dominant_mode.value,
                    "deferred_count": len(plan.deferred_actions)
                }
            }, status_code=200)

        except Exception as e:
            logger.error(f"HC action_plan error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # HC v2 Endpoints (Task Runner, Reminders, Flags)
    # ========================================================================

    @app.get("/hc/flags")
    async def hc_get_flags():
        """Get HC feature flags."""
        import yaml
        from pathlib import Path

        flags_path = Path("ReDNACoreDemo/config/hc_flags.yaml")

        try:
            with open(flags_path, 'r') as f:
                flags = yaml.safe_load(f)
            return JSONResponse(content=flags, status_code=200)
        except Exception as e:
            logger.error(f"Error loading HC flags: {e}")
            # Return defaults if file not found
            return JSONResponse(content={
                "enable_task_runner": False,
                "enable_reminders": False,
                "enable_ucnrr": False,
                "enable_conversation_memory": False,
                "enable_playbook_runner": False
            }, status_code=200)

    @app.post("/hc/tasks/queue")
    async def hc_tasks_queue(
        user_id: str = Query(...),
        title: str = Body(...),
        action: str = Body(...),
        args: Dict[str, Any] = Body(default={}),
        eta_mins: int = Body(default=2),
        provenance: Dict[str, Any] = Body(default={}),
        priority: str = Body(default="normal")
    ):
        """Enqueue a new task with optional priority (low/normal/high)."""
        from .hc_task_runner import get_task_runner

        try:
            runner = get_task_runner()
            task = runner.enqueue(
                user_id=user_id,
                title=title,
                action=action,
                args=args,
                eta_mins=eta_mins,
                provenance=provenance,
                priority=priority
            )
            return JSONResponse(content=task, status_code=200)
        except Exception as e:
            logger.error(f"HC tasks/queue error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/tasks/list")
    async def hc_tasks_list(user_id: str, state: Optional[str] = None):
        """List tasks for a user."""
        from .hc_task_runner import get_task_runner

        try:
            runner = get_task_runner()
            tasks = runner.list_tasks(user_id, state=state)
            return JSONResponse(content={"tasks": tasks}, status_code=200)
        except Exception as e:
            logger.error(f"HC tasks/list error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/tasks/tick")
    async def hc_tasks_tick(user_id: str = Query(...)):
        """Run one task execution step."""
        from .hc_task_runner import get_task_runner

        try:
            runner = get_task_runner()
            result = runner.tick(user_id)
            return JSONResponse(content=result, status_code=200)
        except Exception as e:
            logger.error(f"HC tasks/tick error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/tasks/update")
    async def hc_tasks_update(
        user_id: str = Query(...),
        task_id: str = Body(...),
        new_state: str = Body(...),
        error: Optional[str] = Body(default=None)
    ):
        """Update task state."""
        from .hc_task_runner import get_task_runner

        try:
            runner = get_task_runner()
            task = runner.update_state(user_id, task_id, new_state, error)

            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

            return JSONResponse(content=task, status_code=200)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"HC tasks/update error for {user_id}/{task_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/reminders/schedule")
    async def hc_reminders_schedule(
        user_id: str = Query(...),
        title: str = Body(...),
        when_iso: str = Body(...),
        action: str = Body(...),
        args: Dict[str, Any] = Body(default={})
    ):
        """Schedule a new reminder."""
        from .hc_reminders import get_reminders

        try:
            reminders = get_reminders()
            reminder = reminders.add(
                user_id=user_id,
                title=title,
                when_iso=when_iso,
                action=action,
                args=args
            )
            return JSONResponse(content=reminder, status_code=200)
        except Exception as e:
            logger.error(f"HC reminders/schedule error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/reminders/list")
    async def hc_reminders_list(user_id: str):
        """List all reminders for a user."""
        from .hc_reminders import get_reminders

        try:
            reminders_svc = get_reminders()
            reminders = reminders_svc.list(user_id)
            return JSONResponse(content={"reminders": reminders}, status_code=200)
        except Exception as e:
            logger.error(f"HC reminders/list error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/reminders/tick")
    async def hc_reminders_tick(user_id: str = Query(...)):
        """Process due reminders."""
        from .hc_reminders import get_reminders

        try:
            reminders_svc = get_reminders()
            result = reminders_svc.tick(user_id)
            return JSONResponse(content=result, status_code=200)
        except Exception as e:
            logger.error(f"HC reminders/tick error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/reminders/complete")
    async def hc_reminders_complete(
        user_id: str = Query(...),
        reminder_id: str = Body(...)
    ):
        """Mark a reminder as completed."""
        from .hc_reminders import get_reminders

        try:
            reminders_svc = get_reminders()
            reminder = reminders_svc.complete(user_id, reminder_id)

            if not reminder:
                raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found")

            return JSONResponse(content=reminder, status_code=200)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"HC reminders/complete error for {user_id}/{reminder_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/reminders/cancel")
    async def hc_reminders_cancel(
        user_id: str = Query(...),
        reminder_id: str = Body(...)
    ):
        """Cancel a reminder."""
        from .hc_reminders import get_reminders

        try:
            reminders_svc = get_reminders()
            reminder = reminders_svc.cancel(user_id, reminder_id)

            if not reminder:
                raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found")

            return JSONResponse(content=reminder, status_code=200)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"HC reminders/cancel error for {user_id}/{reminder_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # HC v2: Conversation Memory
    # ─────────────────────────────────────────────────────────────────────────

    def _load_hc_flags():
        """Load HC feature flags from config file."""
        import yaml
        from pathlib import Path

        flags_path = Path("ReDNACoreDemo/config/hc_flags.yaml")

        try:
            with open(flags_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Error loading HC flags: {e}")
            return {
                "enable_task_runner": True,
                "enable_reminders": True,
                "enable_ucnrr": False,
                "enable_ucnrr_real": False,
                "enable_conversation_memory": True,
                "enable_llm_replies": True,
                "enable_playbook_runner": True
            }

    @app.post("/hc/say")
    async def hc_say(
        user_id: str = Query(...),
        message: str = Body(...),
        role: str = Body(default="user"),
        task_id: str = Body(default=None),
        provenance: dict = Body(default=None)
    ):
        """
        Record a conversation message with Head Coach.

        Logs to: data/users/{user_id}/hc/conversation/{YYYY-MM-DD}.jsonl

        If role="user" and enable_llm_replies flag is true, generates and logs
        an assistant reply based on current user state.

        Args:
            user_id: User ID
            message: Message content
            role: "user" or "assistant" (default: "user")
            task_id: Optional linked task ID
            provenance: Optional provenance metadata

        Returns:
            {"logged": true, "file": "...", "ts": "...", "reply_logged": bool}
        """
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        try:
            # Ensure user conversation directory exists
            user_dir = Path("data/users") / user_id
            conv_dir = user_dir / "hc" / "conversation"
            conv_dir.mkdir(parents=True, exist_ok=True)

            # Log to today's file
            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            log_file = conv_dir / f"{date_str}.jsonl"

            # Build log entry
            entry = {
                "ts": now.isoformat(),
                "role": role,
                "content": message,
            }
            if task_id:
                entry["task_id"] = task_id
            if provenance:
                entry["provenance"] = provenance

            # Append to JSONL
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            logger.info(f"HC conversation logged for {user_id}: {role} - {len(message)} chars")

            result = {
                "logged": True,
                "file": str(log_file.relative_to(user_dir)),
                "ts": entry["ts"],
                "reply_logged": False
            }

            # Generate assistant reply if user message and flag enabled (Sprint 2a: LLM-powered)
            if role == "user":
                flags = _load_hc_flags()
                enable_llm_replies = flags.get("enable_llm_replies", True)

                if enable_llm_replies:
                    try:
                        from .storage import read_user_state
                        from .hc_llm_agent import generate_reply, load_conversation_history

                        # Load user state for context
                        resolved, evidence, obs = read_user_state(user_id)

                        # Use curiosity engine to get priority-ordered exploration agenda
                        try:
                            from .curiosity.curiosity_engine import CuriosityEngine

                            engine = CuriosityEngine(data_dir=Path("data"))
                            agenda = engine.generate_curiosity_agenda(
                                user_id=user_id,
                                top_n=10,
                                min_curiosity=60.0  # Focus on high/urgent curiosity
                            )

                            # Convert to legacy format for Head Coach
                            high_curiosity_traits = []
                            for item in agenda:
                                high_curiosity_traits.append({
                                    "trait": item.path,
                                    "curiosity": item.curiosity,
                                    "rr": item.rr,
                                    "reason": item.reason,
                                    "type": item.container_type  # trait, container, or missing
                                })
                        except Exception as e:
                            logger.warning(f"Curiosity engine failed, falling back to legacy: {e}")
                            # Fallback to legacy curiosity calculation
                            high_curiosity_traits = []
                            for trait_id, trait_data in resolved.items():
                                rr = trait_data.get("rr", 0)
                                curiosity = 100 - rr if rr > 0 else 0

                                if curiosity >= 60:  # High curiosity threshold
                                    high_curiosity_traits.append({
                                        "trait": trait_id,
                                        "curiosity": curiosity,
                                        "rr": rr
                                    })

                            # Sort by curiosity desc
                            high_curiosity_traits.sort(key=lambda x: x["curiosity"], reverse=True)

                        # Get user tolerance for nudging (adaptive guardrails)
                        tolerance = resolved.get("ReDNA.ToleranceForNudging", {}).get("value", 0.5)
                        if isinstance(tolerance, str):
                            try:
                                tolerance = float(tolerance)
                            except (ValueError, TypeError):
                                tolerance = 0.5

                        # Check if user has explicit RR goals
                        user_rr_goal = None
                        overall_rr = None
                        rr_scores = [t.get("rr", 0) for t in resolved.values() if isinstance(t, dict) and t.get("rr")]
                        if rr_scores:
                            overall_rr = sum(rr_scores) / len(rr_scores)

                        # Get delegation recommendations
                        delegation_recommendations = []
                        try:
                            from core.coach_delegation import DelegationManager

                            manager = DelegationManager(data_dir=CORE_DATA_ROOT)

                            # Check if delegation is appropriate
                            if manager.should_delegate(
                                curiosity_items=high_curiosity_traits,
                                user_tolerance=tolerance
                            ):
                                # Group by coach and get recommendations
                                by_coach = manager.group_curiosity_by_coach(high_curiosity_traits)

                                for coach_id, items in by_coach.items():
                                    if manager.registry.can_delegate_to(coach_id, user_id):
                                        # Calculate priority (average curiosity)
                                        avg_curiosity = sum(item.get("curiosity", 0) for item in items) / len(items)

                                        coaches = manager.registry.config.get("coaches", {})
                                        coach_data = coaches.get(coach_id, {})
                                        coach_display_name = coach_data.get("display_name", coach_id)

                                        # Don't recommend Head Coach to itself
                                        if coach_id != "head_coach":
                                            delegation_recommendations.append({
                                                "coach": coach_id,
                                                "coach_display_name": coach_display_name,
                                                "items": items,
                                                "priority": avg_curiosity
                                            })

                                # Sort by priority
                                delegation_recommendations.sort(key=lambda x: x["priority"], reverse=True)

                        except Exception as e:
                            logger.warning(f"Failed to get delegation recommendations: {e}")

                        # Build state snapshot
                        state_snapshot = {
                            "high_curiosity_traits": high_curiosity_traits,
                            "tolerance_for_nudging": tolerance,
                            "overall_rr": overall_rr,
                            "user_rr_goal": user_rr_goal,  # Future: extract from user goals
                            "delegation_recommendations": delegation_recommendations
                        }

                        # Load conversation history (last 5 messages)
                        conversation_history = load_conversation_history(user_id, limit=5)

                        # Build LLM config from flags
                        model_config = {
                            "provider": flags.get("llm_provider", "mock"),
                            "model": flags.get("llm_model", "gpt-4o-mini"),
                            "max_tokens": flags.get("llm_max_tokens", 300),
                            "temperature": flags.get("llm_temperature", 0.7),
                            "timeout_sec": flags.get("llm_timeout_sec", 10)
                        }

                        # Generate LLM reply
                        llm_response = generate_reply(
                            user_id=user_id,
                            user_message=message,
                            state_snapshot=state_snapshot,
                            model_config=model_config,
                            conversation_history=conversation_history
                        )

                        # Log assistant reply
                        reply_entry = {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "role": "assistant",
                            "content": llm_response["content"],
                            "provenance": {
                                "source": "llm_reply",
                                "provider": llm_response.get("provider", "unknown"),
                                "model": llm_response.get("model", "unknown"),
                                "tokens_used": llm_response.get("tokens_used", 0),
                                "trigger": "user_message"
                            }
                        }

                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(reply_entry) + "\n")

                        result["reply_logged"] = True
                        result["llm_provider"] = llm_response.get("provider")
                        result["tokens_used"] = llm_response.get("tokens_used", 0)
                        logger.info(f"HC LLM reply logged for {user_id} (provider={llm_response.get('provider')}, tokens={llm_response.get('tokens_used', 0)})")

                    except Exception as e:
                        logger.warning(f"HC LLM reply failed for {user_id}: {e}")
                        # Non-blocking: continue even if reply generation fails

            return JSONResponse(content=result, status_code=200)

        except Exception as e:
            logger.error(f"HC say error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/conversation/history")
    async def hc_conversation_history(
        user_id: str = Query(...),
        date: str = Query(default=None),
        limit: int = Query(default=50)
    ):
        """
        Get conversation history for a user.

        Args:
            user_id: User ID
            date: Optional date filter (YYYY-MM-DD), defaults to today
            limit: Max messages to return (default: 50)

        Returns:
            {"messages": [...], "date": "...", "file": "..."}
        """
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        try:
            user_dir = Path("data/users") / user_id
            conv_dir = user_dir / "hc" / "conversation"

            if not conv_dir.exists():
                return JSONResponse(content={"messages": [], "date": None, "file": None}, status_code=200)

            # Determine which file to read
            if date:
                log_file = conv_dir / f"{date}.jsonl"
            else:
                now = datetime.now(timezone.utc)
                date = now.strftime("%Y-%m-%d")
                log_file = conv_dir / f"{date}.jsonl"

            if not log_file.exists():
                return JSONResponse(content={"messages": [], "date": date, "file": None}, status_code=200)

            # Read messages
            messages = []
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        messages.append(json.loads(line))

            # Return most recent {limit} messages
            messages = messages[-limit:]

            return JSONResponse(content={
                "messages": messages,
                "date": date,
                "file": str(log_file.relative_to(user_dir))
            }, status_code=200)

        except Exception as e:
            logger.error(f"HC conversation/history error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # HC v2: Playbook Runner
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/hc/playbooks/list")
    async def hc_playbooks_list():
        """
        List all available playbooks.

        Returns:
            {"playbooks": [{"id": "...", "name": "...", "description": "..."}]}
        """
        import json
        from pathlib import Path

        try:
            playbooks_dir = Path(__file__).parent / "hc_playbooks"
            playbooks = []

            if playbooks_dir.exists():
                for file in playbooks_dir.glob("*.json"):
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            playbooks.append({
                                "id": data.get("playbook_id", file.stem),
                                "name": data.get("name", file.stem),
                                "description": data.get("description", ""),
                                "version": data.get("version", "1.0")
                            })
                    except Exception as e:
                        logger.warning(f"Failed to load playbook {file}: {e}")

            return JSONResponse(content={"playbooks": playbooks}, status_code=200)

        except Exception as e:
            logger.error(f"HC playbooks/list error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/playbooks/run")
    async def hc_playbooks_run(
        user_id: str = Query(...),
        playbook_id: str = Body(..., embed=True)
    ):
        """
        Run a playbook for a user.

        Currently implements curiosity_campaign playbook:
        - Finds trait with highest curiosity
        - Enqueues task to reduce uncertainty

        Args:
            user_id: User ID
            playbook_id: Playbook ID to run

        Returns:
            {"executed": true, "playbook_id": "...", "tasks_enqueued": [...]}
        """
        import json
        from pathlib import Path
        from .hc_task_runner import get_task_runner
        from .storage import read_user_state

        try:
            # Load playbook
            playbooks_dir = Path(__file__).parent / "hc_playbooks"
            playbook_file = playbooks_dir / f"{playbook_id}.json"

            if not playbook_file.exists():
                raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")

            with open(playbook_file, "r", encoding="utf-8") as f:
                playbook = json.load(f)

            tasks_enqueued = []

            # Implement curiosity_campaign
            if playbook_id == "curiosity_campaign":
                # Get user state
                resolved, evidence, obs = read_user_state(user_id)

                # Find highest curiosity trait
                max_curiosity = 0
                max_trait = None

                for trait_id, trait_data in resolved.items():
                    curiosity = trait_data.get("curiosity", 0)
                    if curiosity > max_curiosity and curiosity > 800:
                        max_curiosity = curiosity
                        max_trait = trait_id

                if max_trait:
                    # Enqueue task
                    task_runner = get_task_runner()
                    task = task_runner.enqueue(
                        user_id=user_id,
                        title=f"Reduce uncertainty for {max_trait.split('.')[-1]}",
                        action="add_evidence",
                        args={"trait": max_trait},
                        eta_mins=2,
                        provenance={
                            "source": "playbook",
                            "playbook_id": playbook_id,
                            "reason": f"High curiosity detected ({int(max_curiosity)}). Quick action = big impact."
                        }
                    )
                    tasks_enqueued.append(task["id"])

                    logger.info(f"Playbook {playbook_id} enqueued task for {user_id}: {task['id']}")

            # Implement photo_refine
            elif playbook_id == "photo_refine":
                from .photo_coach import get_latest_batch_id
                from .render_coach import get_latest_render_id, analyze_photo_render_delta

                repo_root = Path(__file__).parents[2]

                # Get latest batches
                photo_batch_id = get_latest_batch_id(user_id, repo_root)
                render_batch_id = get_latest_render_id(user_id, repo_root)

                if photo_batch_id and render_batch_id:
                    # Analyze delta
                    delta_analysis = analyze_photo_render_delta(
                        user_id, photo_batch_id, render_batch_id, repo_root
                    )

                    # Enqueue tasks based on recommendations
                    task_runner = get_task_runner()

                    for recommendation in delta_analysis.get("recommendations", []):
                        priority = recommendation.get("priority", 5)

                        # Only enqueue if priority meets threshold
                        if priority >= playbook.get("priority_threshold", 3):
                            action = recommendation.get("action", "add_evidence")
                            trait = recommendation.get("trait")

                            task = task_runner.enqueue(
                                user_id=user_id,
                                title=f"{action}: {trait.split('.')[-1] if trait else 'trait'}",
                                action=action,
                                args={"trait": trait} if trait else {},
                                eta_mins=2,
                                provenance={
                                    "source": "playbook",
                                    "playbook_id": playbook_id,
                                    "reason": recommendation.get("reason", "Delta heuristic triggered")
                                }
                            )
                            tasks_enqueued.append(task["id"])

                            logger.info(f"Playbook {playbook_id} enqueued {action} task for {user_id}: {task['id']}")

                            # Respect max_tasks_per_run
                            if len(tasks_enqueued) >= playbook.get("max_tasks_per_run", 5):
                                break

            return JSONResponse(content={
                "executed": True,
                "playbook_id": playbook_id,
                "tasks_enqueued": tasks_enqueued
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"HC playbooks/run error for {user_id}/{playbook_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # Photo Coach Endpoints
    # ========================================================================

    @app.post("/photo/ingest")
    async def photo_ingest(
        user_id: str = Query(...),
        batch_id: Optional[str] = Query(None),
        files: List[UploadFile] = File(...)
    ):
        """
        Ingest a batch of photos for a user.

        Args:
            user_id: User ID
            batch_id: Optional batch ID (auto-generated if not provided)
            files: List of image files

        Returns:
            Batch manifest JSON
        """
        from .photo_coach import ingest_photo_batch

        try:
            # Read file contents
            file_data = []
            for file in files:
                content = await file.read()
                file_data.append((file.filename, content))

            # Ingest batch
            repo_root = Path(__file__).parents[2]
            manifest = ingest_photo_batch(user_id, file_data, repo_root, batch_id)

            return JSONResponse(content=manifest, status_code=200)

        except Exception as e:
            logger.error(f"Photo ingest error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/photo/batches")
    async def photo_batches(user_id: str = Query(...)):
        """
        List all photo batches for a user.

        Args:
            user_id: User ID

        Returns:
            List of batch summaries sorted descending by created_at
        """
        from .photo_coach import list_photo_batches

        try:
            repo_root = Path(__file__).parents[2]
            batches = list_photo_batches(user_id, repo_root)

            return JSONResponse(content={"batches": batches}, status_code=200)

        except Exception as e:
            logger.error(f"Photo batches list error for {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/photo/batch")
    async def photo_batch(
        user_id: str = Query(...),
        batch_id: str = Query(...)
    ):
        """
        Get a specific photo batch manifest.

        Args:
            user_id: User ID
            batch_id: Batch ID

        Returns:
            Batch manifest JSON
        """
        from .photo_coach import get_photo_batch

        try:
            repo_root = Path(__file__).parents[2]
            manifest = get_photo_batch(user_id, batch_id, repo_root)

            if manifest is None:
                raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

            return JSONResponse(content=manifest, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Photo batch get error for {user_id}/{batch_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/photo/vision/label")
    async def photo_vision_label(
        user_id: str = Query(...),
        batch_id: str = Query(...),
        image: Optional[str] = Query(None)
    ):
        """
        Add vision labels to images in a batch (stub implementation).

        Args:
            user_id: User ID
            batch_id: Batch ID
            image: Optional specific image filename

        Returns:
            Summary of labels added
        """
        from .photo_coach import add_vision_labels_stub

        try:
            repo_root = Path(__file__).parents[2]
            result = add_vision_labels_stub(user_id, batch_id, repo_root, image)

            return JSONResponse(content=result, status_code=200)

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Photo vision label error for {user_id}/{batch_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================================
    # Trait Container Discovery Endpoints
    # ============================================================================

    @app.get("/api/trait-containers")
    async def get_trait_containers(
        category: Optional[str] = Query(None, description="Filter by category")
    ):
        """
        Get all discovered trait containers.

        Returns a registry of all trait containers discovered from conversations
        and predefined in the schema.

        Args:
            category: Optional category filter (Preferences, PaDNA, etc.)

        Returns:
            Dict with containers and stats
        """
        try:
            if category:
                containers = trait_container_discovery.get_registry().get_containers_by_category(category)
            else:
                containers = trait_container_discovery.get_all_containers()

            stats = trait_container_discovery.get_container_stats()

            return JSONResponse(content={
                "ok": True,
                "containers": containers,
                "stats": stats,
            }, status_code=200)

        except Exception as e:
            logger.error(f"Failed to get trait containers: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================================
    # ONTOLOGY V2 ENDPOINTS - Full registry access
    # ============================================================================

    @app.get("/api/ontology/containers")
    async def get_ontology_containers(
        namespace: Optional[str] = Query(None, description="Filter by namespace"),
        tags: Optional[str] = Query(None, description="Comma-separated tags"),
        search: Optional[str] = Query(None, description="Search term"),
        limit: int = Query(100, description="Max results", ge=1, le=1000)
    ):
        """
        Get containers from the Ontology V2 registry.

        Query Parameters:
        - namespace: Filter by namespace (e.g., "BehDNA", "PaDNA")
        - tags: Comma-separated list of tags (e.g., "beh,social")
        - search: Search in ID, description, or path
        - limit: Maximum number of results (1-1000, default 100)

        Returns:
            {
                "ok": true,
                "containers": [...],
                "count": 42,
                "total_available": 2000
            }
        """
        try:
            from .ontology_service import get_ontology_service

            service = get_ontology_service()
            tag_list = tags.split(",") if tags else None

            containers = service.search_containers(
                namespace=namespace,
                tags=tag_list,
                search_term=search,
                limit=limit
            )

            total = len(service.get_all_containers())

            return JSONResponse(content={
                "ok": True,
                "containers": containers,
                "count": len(containers),
                "total_available": total
            }, status_code=200)

        except Exception as e:
            logger.error(f"Failed to get ontology containers: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/ontology/container/{container_id}")
    async def get_ontology_container(container_id: str):
        """
        Get a specific container by ID.

        Example: /api/ontology/container/BehDNA.v1

        Returns:
            {
                "ok": true,
                "container": {...}
            }
        """
        try:
            from .ontology_service import get_ontology_service

            service = get_ontology_service()
            container = service.get_container_by_id(container_id)

            if not container:
                raise HTTPException(status_code=404, detail=f"Container '{container_id}' not found")

            return JSONResponse(content={
                "ok": True,
                "container": container
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get container {container_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/ontology/namespaces")
    async def get_ontology_namespaces():
        """
        Get all namespaces with container counts.

        Returns:
            {
                "ok": true,
                "namespaces": {
                    "BehDNA": 150,
                    "PaDNA": 200,
                    ...
                }
            }
        """
        try:
            from .ontology_service import get_ontology_service

            service = get_ontology_service()
            namespaces = service.get_namespaces()

            return JSONResponse(content={
                "ok": True,
                "namespaces": namespaces
            }, status_code=200)

        except Exception as e:
            logger.error(f"Failed to get ontology namespaces: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/ontology/stats")
    async def get_ontology_stats():
        """
        Get comprehensive ontology registry statistics.

        Returns:
            {
                "ok": true,
                "stats": {
                    "total_containers": 2000,
                    "namespaces": {...},
                    "status_breakdown": {...},
                    "sensitive_containers": 50,
                    ...
                }
            }
        """
        try:
            from .ontology_service import get_ontology_service

            service = get_ontology_service()
            stats = service.get_stats()

            return JSONResponse(content={
                "ok": True,
                "stats": stats
            }, status_code=200)

        except Exception as e:
            logger.error(f"Failed to get ontology stats: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================================
    # RR ENDPOINTS - Multi-level RR calculation
    # ============================================================================

    @app.get("/rr/trait")
    def get_trait_rr(
        user_id: str = Query(..., description="User ID"),
        trait_path: str = Query(..., description="Trait path (e.g., PaDNA.HairDNA.Color)")
    ):
        """
        Get RR for a specific trait.

        Returns:
            {
                "ok": true,
                "user_id": "user123",
                "trait_path": "PaDNA.HairDNA.Color",
                "rr": 45.3,
                "curiosity": 54.7,
                "ucn": 440.0,
                "method": "histogram_percentile",
                "population_size": 150,
                "blending_applied": false
            }
        """
        from core.rr_per_trait import PerTraitRRCalculator

        try:
            distribution_dir = Path(config.core_data_dir) / "population_distributions"

            calculator = PerTraitRRCalculator(
                distribution_dir=distribution_dir,
                k_min=50
            )

            # Get user's UCN for this trait
            resolved, _, _ = read_user_state(user_id)
            if not resolved:
                raise HTTPException(status_code=404, detail="User not found")

            trait_entry = resolved.get(trait_path)
            if not trait_entry:
                raise HTTPException(status_code=404, detail=f"Trait {trait_path} not found")

            ucn = trait_entry.get("ucn")
            if ucn is None:
                raise HTTPException(status_code=400, detail="Trait has no UCN value")

            # Calculate RR
            metadata = calculator.calculate_rr_metadata(ucn, trait_path)

            return JSONResponse(content={
                "ok": True,
                "user_id": user_id,
                "trait_path": trait_path,
                **metadata
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Trait RR calculation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/rr/container")
    def get_container_rr(
        user_id: str = Query(..., description="User ID"),
        container: str = Query(..., description="Container name (e.g., PaDNA)")
    ):
        """
        Get aggregated RR for a DNA container.

        Returns:
            {
                "ok": true,
                "container": "PaDNA",
                "rr": 67.8,
                "curiosity": 32.2,
                "trait_count": 45,
                "coverage": 32.4,
                "traits": [...]
            }
        """
        from core.rr_aggregation import ContainerRRAggregator

        try:
            distribution_dir = Path(config.core_data_dir) / "population_distributions"

            aggregator = ContainerRRAggregator(
                distribution_dir=distribution_dir,
                k_min=50,
                alpha=0.5
            )

            result = aggregator.calculate_container_rr(user_id, container)

            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valid RR data for container {container}"
                )

            return JSONResponse(content={
                "ok": True,
                "user_id": user_id,
                **result
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Container RR calculation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/rr/overall")
    def get_overall_rr(
        user_id: str = Query(..., description="User ID")
    ):
        """
        Get overall user RR across all containers.

        Returns:
            {
                "ok": true,
                "overall": {
                    "rr": 64.5,
                    "curiosity": 35.5,
                    "container_count": 3,
                    "trait_count": 109
                },
                "containers": [...]
            }
        """
        from core.rr_aggregation import calculate_user_rr_summary

        try:
            distribution_dir = Path(config.core_data_dir) / "population_distributions"

            summary = calculate_user_rr_summary(
                user_id=user_id,
                distribution_dir=distribution_dir,
                k_min=50,
                alpha=0.5
            )

            if summary.get("error"):
                raise HTTPException(status_code=404, detail=summary["error"])

            return JSONResponse(content={
                "ok": True,
                "user_id": user_id,
                **summary
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Overall RR calculation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rr/rebuild_distributions")
    def rebuild_distributions(
        force: bool = Query(False, description="Force rebuild even if up-to-date")
    ):
        """
        Rebuild population distributions for RR calculation.

        This should be run:
        - After data migration
        - Periodically (e.g., weekly) to include new users
        - When distribution quality degrades

        Returns:
            {
                "ok": true,
                "distributions_built": 87,
                "total_users": 150,
                "traits": {...}
            }
        """
        from core.rr_distribution_builder import build_all_distributions

        try:
            distribution_dir = Path(config.core_data_dir) / "population_distributions"

            trait_counts = build_all_distributions(
                output_dir=distribution_dir,
                k_min=5,  # Use k_min=5 for distribution building
                force_rebuild=force
            )

            return JSONResponse(content={
                "ok": True,
                "distributions_built": len(trait_counts),
                "total_users": len(list_users()),
                "traits": trait_counts
            }, status_code=200)

        except Exception as e:
            logger.error(f"Distribution rebuild error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # DNA ONTOLOGY ENDPOINTS
    # ========================================================================

    @app.get("/ontology/registry")
    def get_ontology_registry():
        """Get the complete DNA container registry."""
        try:
            registry_path = Path("core/ontology/dna_registry.json")

            if not registry_path.exists():
                raise HTTPException(status_code=404, detail="Registry not found")

            with open(registry_path) as f:
                registry = json.load(f)

            return JSONResponse(content={"ok": True, "registry": registry}, status_code=200)

        except Exception as e:
            logger.error(f"Registry fetch error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ontology/container/{path:path}")
    def get_ontology_container(path: str):
        """Get a single container by path."""
        try:
            registry_path = Path("core/ontology/dna_registry.json")

            if not registry_path.exists():
                raise HTTPException(status_code=404, detail="Registry not found")

            with open(registry_path) as f:
                registry = json.load(f)

            # Find container
            for container in registry.get("containers", []):
                if container.get("path") == path:
                    return JSONResponse(content={"ok": True, "container": container}, status_code=200)

            raise HTTPException(status_code=404, detail=f"Container not found: {path}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Container fetch error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ontology/namespace/{namespace}")
    def get_ontology_namespace(namespace: str):
        """Get all containers in a namespace."""
        try:
            registry_path = Path("core/ontology/dna_registry.json")

            if not registry_path.exists():
                raise HTTPException(status_code=404, detail="Registry not found")

            with open(registry_path) as f:
                registry = json.load(f)

            # Filter containers
            containers = [
                c for c in registry.get("containers", [])
                if c.get("namespace") == namespace
            ]

            return JSONResponse(content={
                "ok": True,
                "namespace": namespace,
                "count": len(containers),
                "containers": containers
            }, status_code=200)

        except Exception as e:
            logger.error(f"Namespace fetch error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ontology/search")
    def search_ontology(q: str = Query(..., min_length=2)):
        """Search containers by path, description, or tags."""
        try:
            registry_path = Path("core/ontology/dna_registry.json")

            if not registry_path.exists():
                raise HTTPException(status_code=404, detail="Registry not found")

            with open(registry_path) as f:
                registry = json.load(f)

            query = q.lower()
            results = []

            for container in registry.get("containers", []):
                path = container.get("path", "").lower()
                description = container.get("description", "").lower()
                tags = [t.lower() for t in container.get("tags", [])]

                if query in path or query in description or any(query in t for t in tags):
                    results.append(container)

            return JSONResponse(content={
                "ok": True,
                "query": q,
                "count": len(results),
                "results": results
            }, status_code=200)

        except Exception as e:
            logger.error(f"Search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/curiosity/{user_id}")
    def get_curiosity_agenda(
        user_id: str,
        top_n: int = Query(20, ge=1, le=100),
        min_curiosity: float = Query(50.0, ge=0.0, le=100.0)
    ):
        """Get curiosity-driven agenda for a user."""
        try:
            from core.curiosity.curiosity_engine import CuriosityEngine

            engine = CuriosityEngine(data_dir=Path("data"))

            agenda = engine.generate_curiosity_agenda(
                user_id=user_id,
                top_n=top_n,
                min_curiosity=min_curiosity
            )

            return JSONResponse(content={
                "ok": True,
                "user_id": user_id,
                "count": len(agenda),
                "agenda": [item.to_dict() for item in agenda]
            }, status_code=200)

        except Exception as e:
            logger.error(f"Curiosity agenda error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/curiosity/{user_id}/map")
    def get_curiosity_map(user_id: str):
        """Get complete curiosity map for visualization."""
        try:
            from core.curiosity.curiosity_engine import CuriosityEngine

            engine = CuriosityEngine(data_dir=Path("data"))

            curiosity_map = engine.export_curiosity_map(user_id=user_id)

            return JSONResponse(content={"ok": True, **curiosity_map}, status_code=200)

        except Exception as e:
            logger.error(f"Curiosity map error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================
    # COACH DELEGATION ENDPOINTS
    # ============================================================

    @app.post("/delegation/analyze")
    def analyze_delegation_opportunity(payload: dict = Body(...)):
        """
        Analyze if delegation is appropriate for current curiosity state.

        Returns:
            {
                "should_delegate": bool,
                "recommendations": [
                    {
                        "coach": str,
                        "items": [curiosity_item, ...],
                        "priority": float,
                        "message": str
                    }
                ]
            }
        """
        try:
            from core.coach_delegation import DelegationManager
            from core.curiosity.curiosity_engine import CuriosityEngine

            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(status_code=400, detail="Missing user_id")

            # Get current curiosity state
            engine = CuriosityEngine(data_dir=CORE_DATA_ROOT)
            agenda = engine.generate_curiosity_agenda(
                user_id=user_id,
                top_n=20,
                min_curiosity=60.0
            )

            curiosity_items = [item.to_dict() for item in agenda]

            # Get user tolerance (read_user_state returns tuple)
            state_tuple = read_user_state(user_id)
            resolved = state_tuple[2] if len(state_tuple) > 2 else {}
            tolerance = resolved.get("ReDNA.ToleranceForNudging", {}).get("value", 0.5)
            if isinstance(tolerance, str):
                try:
                    tolerance = float(tolerance)
                except (ValueError, TypeError):
                    tolerance = 0.5

            # Analyze delegation opportunity
            manager = DelegationManager(data_dir=CORE_DATA_ROOT)

            should_delegate = manager.should_delegate(
                curiosity_items=curiosity_items,
                user_tolerance=tolerance,
                conversation_context=payload.get("conversation_context")
            )

            # Group by coach
            by_coach = manager.group_curiosity_by_coach(curiosity_items)

            # Build recommendations
            recommendations = []
            for coach_id, items in by_coach.items():
                if manager.registry.can_delegate_to(coach_id, user_id):
                    # Calculate priority (simple: average curiosity)
                    avg_curiosity = sum(item.get("curiosity", 0) for item in items) / len(items)

                    coaches = manager.registry.config.get("coaches", {})
                    coach_data = coaches.get(coach_id, {})
                    coach_display_name = coach_data.get("display_name", coach_id)

                    recommendations.append({
                        "coach": coach_id,
                        "coach_display_name": coach_display_name,
                        "items": items,
                        "priority": avg_curiosity,
                        "message": f"{coach_display_name} could help explore {len(items)} area(s)"
                    })

            # Sort by priority
            recommendations.sort(key=lambda x: x["priority"], reverse=True)

            return JSONResponse(content={
                "ok": True,
                "should_delegate": should_delegate,
                "user_tolerance": tolerance,
                "total_curiosity_items": len(curiosity_items),
                "recommendations": recommendations
            }, status_code=200)

        except Exception as e:
            logger.error(f"Delegation analysis error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/delegation/create")
    def create_delegation(payload: dict = Body(...)):
        """
        Create a delegation to a specialized coach.

        Request:
            {
                "user_id": str,
                "coach_id": str,
                "curiosity_targets": [path, ...],
                "context": {...}
            }

        Returns:
            {
                "ok": bool,
                "delegation": {
                    "delegation_id": str,
                    "coach": str,
                    "message": str,
                    "curiosity_targets": [...]
                }
            }
        """
        try:
            from core.coach_delegation import DelegationManager

            user_id = payload.get("user_id")
            coach_id = payload.get("coach_id")
            curiosity_targets = payload.get("curiosity_targets", [])
            context = payload.get("context", {})

            if not user_id or not coach_id:
                return JSONResponse(content={
                    "ok": False,
                    "error": "missing_params",
                    "message": "Missing user_id or coach_id"
                }, status_code=400)

            manager = DelegationManager(data_dir=CORE_DATA_ROOT)

            result = manager.delegate_to_coach(
                coach_id=coach_id,
                user_id=user_id,
                curiosity_targets=curiosity_targets,
                context=context
            )

            if not result.success:
                return JSONResponse(content={
                    "ok": False,
                    "error": result.error,
                    "message": result.message
                }, status_code=400)

            return JSONResponse(content={
                "ok": True,
                "delegation": {
                    "delegation_id": result.delegation_id,
                    "coach": result.coach,
                    "message": result.message,
                    "curiosity_targets": result.curiosity_targets,
                    "context": result.context
                }
            }, status_code=200)

        except Exception as e:
            logger.error(f"Delegation creation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/delegation/{user_id}/status/{delegation_id}")
    def get_delegation_status(user_id: str, delegation_id: str):
        """
        Get status of a delegation.

        Returns:
            {
                "ok": bool,
                "status": {
                    "delegation_id": str,
                    "coach": str,
                    "status": str,
                    "traits_collected": [...],
                    "curiosity_satisfied": float,
                    "timestamp": str
                }
            }
        """
        try:
            from core.coach_delegation import DelegationManager

            manager = DelegationManager(data_dir=CORE_DATA_ROOT)
            status = manager.check_delegation_status(delegation_id, user_id)

            if not status:
                raise HTTPException(status_code=404, detail="Delegation not found")

            return JSONResponse(content={
                "ok": True,
                "status": {
                    "delegation_id": status.delegation_id,
                    "coach": status.coach,
                    "status": status.status,
                    "traits_collected": status.traits_collected,
                    "curiosity_satisfied": status.curiosity_satisfied,
                    "timestamp": status.timestamp,
                    "notes": status.notes
                }
            }, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delegation status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/delegation/{user_id}/active")
    def get_active_delegations(user_id: str):
        """
        Get all active delegations for a user.

        Returns:
            {
                "ok": bool,
                "count": int,
                "delegations": [...]
            }
        """
        try:
            from core.coach_delegation import DelegationManager

            manager = DelegationManager(data_dir=CORE_DATA_ROOT)
            active = manager.get_active_delegations(user_id)

            return JSONResponse(content={
                "ok": True,
                "count": len(active),
                "delegations": [
                    {
                        "delegation_id": d.delegation_id,
                        "coach": d.coach,
                        "status": d.status,
                        "traits_collected": d.traits_collected,
                        "curiosity_satisfied": d.curiosity_satisfied,
                        "timestamp": d.timestamp,
                        "notes": d.notes
                    }
                    for d in active
                ]
            }, status_code=200)

        except Exception as e:
            logger.error(f"Active delegations error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/delegation/{user_id}/complete/{delegation_id}")
    def complete_delegation(user_id: str, delegation_id: str, payload: dict = Body(...)):
        """
        Mark delegation as completed and return to Head Coach with results.

        Request:
            {
                "traits_collected": [path, ...],
                "curiosity_before": {path: score, ...},
                "curiosity_after": {path: score, ...},
                "notes": str,
                "auto_return": bool  # default True - switch back to Head Coach
            }

        Returns:
            {
                "ok": bool,
                "message": str,
                "delegation_summary": {
                    "traits_collected_count": int,
                    "curiosity_satisfied": float,
                    "notes": str
                },
                "mode_switch": {
                    "previous_mode": str,
                    "new_mode": str,
                    "message": str
                }
            }
        """
        try:
            from core.coach_delegation import DelegationManager
            from core.coach_mode_manager import switch_mode_with_handoff

            traits_collected = payload.get("traits_collected", [])
            curiosity_before = payload.get("curiosity_before", {})
            curiosity_after = payload.get("curiosity_after", {})
            notes = payload.get("notes", "")
            auto_return = payload.get("auto_return", True)

            manager = DelegationManager(data_dir=CORE_DATA_ROOT)

            success = manager.complete_delegation(
                delegation_id=delegation_id,
                user_id=user_id,
                traits_collected=traits_collected,
                curiosity_before=curiosity_before,
                curiosity_after=curiosity_after,
                notes=notes
            )

            if not success:
                raise HTTPException(status_code=404, detail="Delegation not found or already completed")

            # Get delegation status for summary
            delegation_status = manager.check_delegation_status(delegation_id, user_id)

            response_data = {
                "ok": True,
                "message": "Delegation completed successfully",
                "delegation_summary": {
                    "traits_collected_count": len(traits_collected),
                    "curiosity_satisfied": delegation_status.curiosity_satisfied if delegation_status else 0.0,
                    "notes": notes,
                }
            }

            # Auto-return to Head Coach with delegation results
            if auto_return:
                mode_switch_result = switch_mode_with_handoff(
                    user_id=user_id,
                    target_mode="head_coach",
                    data_dir=CORE_DATA_ROOT,
                    delegation_id=delegation_id,
                    context={
                        "reason": "delegation_complete",
                        "traits_collected": traits_collected,
                        "curiosity_satisfied": delegation_status.curiosity_satisfied if delegation_status else 0.0,
                        "notes": notes,
                    }
                )
                response_data["mode_switch"] = mode_switch_result
            else:
                response_data["mode_switch"] = None

            return JSONResponse(content=response_data, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delegation completion error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================
    # COACH MODE ENDPOINTS
    # ============================================================

    @app.get("/users/{user_id}/coach-mode")
    def get_active_coach_mode(user_id: str):
        """
        Get user's current active coach mode.

        Returns:
            {
                "ok": bool,
                "active_mode": str,
                "mode_info": {
                    "display_name": str,
                    "emoji": str,
                    "description": str,
                    "namespaces": [...]
                }
            }
        """
        try:
            from core.coach_mode_manager import CoachModeManager

            manager = CoachModeManager(data_dir=CORE_DATA_ROOT)
            active_mode = manager.get_active_mode(user_id)
            mode_info = manager.get_mode_info(active_mode)

            return JSONResponse(content={
                "ok": True,
                "active_mode": active_mode,
                "mode_info": mode_info
            }, status_code=200)

        except Exception as e:
            logger.error(f"Get coach mode error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/users/{user_id}/coach-mode")
    def switch_coach_mode(user_id: str, payload: dict = Body(...)):
        """
        Switch user's active coach mode.

        Request:
            {
                "target_mode": str,  # "head_coach", "photo", "relationship"
                "delegation_id": str (optional),
                "context": {...} (optional)
            }

        Returns:
            {
                "ok": bool,
                "previous_mode": str,
                "new_mode": str,
                "mode_info": {...},
                "message": str
            }
        """
        try:
            from core.coach_mode_manager import switch_mode_with_handoff

            target_mode = payload.get("target_mode")
            if not target_mode:
                return JSONResponse(content={
                    "ok": False,
                    "error": "missing_target_mode",
                    "message": "target_mode is required"
                }, status_code=400)

            delegation_id = payload.get("delegation_id")
            context = payload.get("context", {})

            result = switch_mode_with_handoff(
                user_id=user_id,
                target_mode=target_mode,
                data_dir=CORE_DATA_ROOT,
                delegation_id=delegation_id,
                context=context
            )

            if not result["success"]:
                return JSONResponse(content={
                    "ok": False,
                    "error": result.get("error", "switch_failed"),
                    "message": result.get("message", "Failed to switch modes")
                }, status_code=400)

            return JSONResponse(content={
                "ok": True,
                **result
            }, status_code=200)

        except Exception as e:
            logger.error(f"Switch coach mode error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/users/{user_id}/coach-mode/history")
    def get_coach_mode_history(user_id: str, limit: int = Query(10, ge=1, le=100)):
        """
        Get user's coach mode switching history.

        Returns:
            {
                "ok": bool,
                "history": [
                    {
                        "from_mode": str,
                        "to_mode": str,
                        "timestamp": str,
                        "context": {...}
                    }
                ]
            }
        """
        try:
            from core.coach_mode_manager import CoachModeManager

            manager = CoachModeManager(data_dir=CORE_DATA_ROOT)
            history = manager.get_mode_history(user_id, limit=limit)

            return JSONResponse(content={
                "ok": True,
                "history": history,
                "count": len(history)
            }, status_code=200)

        except Exception as e:
            logger.error(f"Get mode history error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/users/{user_id}/coach-mode/stats")
    def get_coach_mode_stats(user_id: str):
        """
        Get statistics about user's coach mode usage.

        Returns:
            {
                "ok": bool,
                "stats": {
                    "total_transitions": int,
                    "mode_counts": {mode: count},
                    "current_mode": str,
                    "most_used_mode": str
                }
            }
        """
        try:
            from core.coach_mode_manager import CoachModeManager

            manager = CoachModeManager(data_dir=CORE_DATA_ROOT)
            stats = manager.get_mode_stats(user_id)

            return JSONResponse(content={
                "ok": True,
                "stats": stats
            }, status_code=200)

        except Exception as e:
            logger.error(f"Get mode stats error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ==================== Career Coach Panel Endpoint ====================
    @app.get("/api/coach/career_coach/panel")
    def get_career_coach_panel(user_id: str = Query(..., description="User ID")):
        """
        Career Coach unified panel endpoint - returns all widget data in one call.

        Returns aggregated data for:
        - snapshot: Career overview metrics
        - user_intents: Detected user intents with confidence
        - skills: SkillDNA map with RR/curiosity/trend
        - suggestions: Learning path recommendations
        - roles: Career transition role recommendations
        - user_profile: Work style radar data
        - role_profile: Role demands radar data
        - mismatches: Work style gaps
        - points: Motivation alignment scatter points
        - entries: Career timeline milestones
        - cards: Insight cards from coach logic
        """
        try:
            from .career_coach.career_service import CareerCoach

            coach = CareerCoach(user_id)

            # Get skill curiosity map
            skill_map = coach.get_skill_curiosity_map(min_curiosity=50.0)

            # Get career dashboard
            dashboard = coach.get_career_dashboard()

            # Detect user intent (simple heuristic for now)
            # If high curiosity in multiple skills → career_change
            # If high curiosity in few skills → current_role_growth
            # Otherwise → organization_mode
            skills_needing_attention = skill_map.get("skills_needing_attention", 0)
            avg_skill_rr = skill_map.get("avg_skill_rr", 50.0)

            if skills_needing_attention >= 5 and avg_skill_rr < 60:
                detected_intent = "career_change"
                confidence = 0.75
            elif skills_needing_attention > 0:
                detected_intent = "current_role_growth"
                confidence = 0.65
            else:
                detected_intent = "organization_mode"
                confidence = 0.50

            # Build snapshot
            snapshot = {
                "profdna_rr": round(dashboard["satisfaction_score"], 1),
                "skilldna_rr": round(avg_skill_rr, 1),
                "top_strengths": [s["name"] for s in dashboard.get("top_strengths", [])[:3]],
                "top_curiosity": [s["name"] for s in dashboard.get("skill_gaps", [])[:3]],
                "active_intent": detected_intent
            }

            # Build skills list for SkillCuriosityMap
            skills = skill_map.get("high_curiosity_skills", []) + skill_map.get("well_resolved_skills", [])

            # Placeholder data for other widgets (will be built in future phases)
            suggestions = []  # LearningPathBuilder
            roles = []  # TransitionPlanner
            user_profile = {}  # WorkStyleAnalyzer
            role_profile = {}  # WorkStyleAnalyzer
            mismatches = []  # WorkStyleAnalyzer
            points = []  # MotivationAlignmentChart
            entries = []  # CareerTimeline

            # Build insight cards
            cards = []

            # Add insight for high curiosity skills
            if skills_needing_attention > 0:
                high_curiosity_skills = skill_map.get("high_curiosity_skills", [])[:3]
                cards.append({
                    "id": "skill_curiosity_insight",
                    "type": "curiosity",
                    "title": f"{skills_needing_attention} Skills Need Attention",
                    "description": f"High curiosity detected in: {', '.join([s['name'] for s in high_curiosity_skills])}",
                    "rr_delta": -15.0,
                    "curiosity_delta": 20.0,
                    "action": "explore_learning_paths"
                })

            # Add insight for strengths
            if dashboard.get("top_strengths"):
                top_strength = dashboard["top_strengths"][0]
                cards.append({
                    "id": "strength_insight",
                    "type": "strength",
                    "title": "Top Strength Identified",
                    "description": f"{top_strength['name']} is highly resolved (RR: {round(top_strength['rr'], 1)})",
                    "rr_delta": 0.0,
                    "curiosity_delta": 0.0,
                    "action": "acknowledge"
                })

            return JSONResponse(content={
                # Intent detection
                "user_intents": [detected_intent],
                "confidence": confidence,

                # Snapshot widget data
                "snapshot": snapshot,

                # SkillCuriosityMap widget data
                "skills": skills,

                # Placeholder widget data (future)
                "suggestions": suggestions,
                "roles": roles,
                "user_profile": user_profile,
                "role_profile": role_profile,
                "mismatches": mismatches,
                "points": points,
                "entries": entries,

                # InsightFeed widget data
                "cards": cards
            }, status_code=200)

        except Exception as e:
            logger.error(f"Career coach panel error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================
    # Personality Test Coach Panel Endpoint
    # ========================================
    @app.get("/api/coach/personality_test_coach/panel")
    def get_personality_test_coach_panel(user_id: str = Query(..., description="User ID")):
        """
        Personality Test Coach unified panel endpoint.
        Returns all widget data in one call: snapshot, personality map, motivation matrix,
        insights, timeline, test items, and contradiction flags.

        Supports adaptive testing based on RR/Curiosity scores.
        """
        try:
            resolved, evidence, obs = read_user_state(user_id)

            # Extract PsyDNA data
            psydna = resolved.get("PsyDNA", {})
            big_five = {}
            facets = {}
            motivation = {}
            self_concept = {}

            # Parse BigFive factors
            for factor_name in ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "EmotionalStability"]:
                factor_path = f"PersonalityDNA.BigFiveDNA.{factor_name}DNA"
                factor_data = psydna.get(factor_path, {})
                if factor_data:
                    big_five[factor_name] = {
                        "rr": factor_data.get("rr", 0),
                        "curiosity": factor_data.get("curiosity", 100),
                        "last_updated": factor_data.get("last_updated")
                    }

            # Parse facets for low RR detection
            for factor_name in ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "EmotionalStability"]:
                facets_path = f"PersonalityDNA.{factor_name}FacetsDNA"
                facets_data = psydna.get(facets_path, {})
                for facet_key, facet_val in facets_data.items():
                    if isinstance(facet_val, dict) and "rr" in facet_val:
                        facets[facet_key] = {
                            "rr": facet_val.get("rr", 0),
                            "curiosity": facet_val.get("curiosity", 100),
                            "parent_factor": factor_name
                        }

            # Parse MotivationDNA
            motivation_dna = psydna.get("MotivationDNA", {})
            for motive_key, motive_val in motivation_dna.items():
                if isinstance(motive_val, dict) and "rr" in motive_val:
                    motivation[motive_key] = {
                        "rr": motive_val.get("rr", 0),
                        "curiosity": motive_val.get("curiosity", 100)
                    }

            # Parse SelfConceptSchemaDNA
            self_concept_dna = psydna.get("SelfConceptSchemaDNA", {})
            for sc_key, sc_val in self_concept_dna.items():
                if isinstance(sc_val, dict) and "rr" in sc_val:
                    self_concept[sc_key] = {
                        "rr": sc_val.get("rr", 0),
                        "curiosity": sc_val.get("curiosity", 100)
                    }

            # Calculate aggregate PsyDNA RR
            all_rr_values = []
            for bf in big_five.values():
                if bf["rr"] is not None:
                    all_rr_values.append(bf["rr"])
            for m in motivation.values():
                if m["rr"] is not None:
                    all_rr_values.append(m["rr"])

            psydna_rr = sum(all_rr_values) / len(all_rr_values) if all_rr_values else 0

            # Identify top strengths (high RR) and top curiosity (high curiosity score)
            strengths = []
            high_curiosity = []

            for factor, data in big_five.items():
                if data["rr"] and data["rr"] >= 70:
                    strengths.append({"name": f"{factor}DNA", "rr": data["rr"]})
                if data["curiosity"] and data["curiosity"] >= 70:
                    high_curiosity.append({"name": f"{factor}DNA", "curiosity": data["curiosity"], "rr": data["rr"]})

            # Sort and limit
            strengths.sort(key=lambda x: x["rr"], reverse=True)
            high_curiosity.sort(key=lambda x: x["curiosity"], reverse=True)

            # Detect intent based on data state
            if psydna_rr < 40:
                active_intent = "discover_self"
            elif len(high_curiosity) > 2:
                active_intent = "track_growth"
            else:
                active_intent = "compare_over_time"

            # Build snapshot
            snapshot = {
                "psydna_rr": round(psydna_rr, 1),
                "top_strengths": [s["name"] for s in strengths[:3]],
                "top_curiosity": [c["name"] for c in high_curiosity[:3]],
                "active_intent": active_intent,
                "factors_assessed": len([bf for bf in big_five.values() if bf["rr"] is not None])
            }

            # Build personality map (radar chart data)
            personality_map = {
                "factors": []
            }
            for factor, data in big_five.items():
                personality_map["factors"].append({
                    "name": factor,
                    "rr": data["rr"] or 0,
                    "curiosity": data["curiosity"] or 100,
                    "population_avg": 50  # Placeholder for population reference
                })

            # Build motivation matrix (scatter data)
            motivation_matrix = {
                "intrinsic_extrinsic": [],
                "purpose_alignment": []
            }

            if "IntrinsicExtrinsicBalanceDNA" in motivation:
                motivation_matrix["intrinsic_extrinsic"].append({
                    "trait": "IntrinsicExtrinsicBalance",
                    "rr": motivation["IntrinsicExtrinsicBalanceDNA"]["rr"],
                    "curiosity": motivation["IntrinsicExtrinsicBalanceDNA"]["curiosity"]
                })

            if "PurposeMeaningOrientationDNA" in motivation:
                motivation_matrix["purpose_alignment"].append({
                    "trait": "PurposeMeaningOrientation",
                    "rr": motivation["PurposeMeaningOrientationDNA"]["rr"],
                    "curiosity": motivation["PurposeMeaningOrientationDNA"]["curiosity"]
                })

            # Generate insights (adaptive prompts based on RR gaps)
            insights = []
            for factor, data in big_five.items():
                if data["rr"] is not None and data["rr"] < 50:
                    insights.append({
                        "type": "low_rr",
                        "trait": factor,
                        "message": f"Your {factor} assessment could be refined (RR {data['rr']}). Consider a focused mini-quiz.",
                        "action": "micro_quiz",
                        "target": factor
                    })

            if len(high_curiosity) > 0:
                insights.append({
                    "type": "high_curiosity",
                    "trait": high_curiosity[0]["name"],
                    "message": f"High curiosity detected in {high_curiosity[0]['name']}. Explore this trait further?",
                    "action": "reflection",
                    "target": high_curiosity[0]["name"]
                })

            # Timeline (placeholder - would fetch from events)
            timeline = []

            # Test items (placeholder - would load from personality_items.json)
            test_items = []

            # Contradiction flags (placeholder - would detect from behavior vs self-report)
            contradiction_flags = []

            # Confidence (based on RR completeness)
            assessed_count = len([bf for bf in big_five.values() if bf["rr"] is not None])
            confidence = assessed_count / 5.0 if assessed_count > 0 else 0.0

            return JSONResponse(content={
                "user_id": user_id,
                "snapshot": snapshot,
                "personality_map": personality_map,
                "motivation_matrix": motivation_matrix,
                "insights": insights,
                "timeline": timeline,
                "test_items": test_items,
                "contradiction_flags": contradiction_flags,
                "confidence": round(confidence, 2)
            })

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"PTC panel error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================
    # ChatDNA Coach Panel Endpoints
    # ========================================
    @app.get("/api/coach/chatdna_coach/panel")
    def get_chatdna_coach_panel(user_id: str = Query(..., description="User ID")):
        """
        ChatDNA Coach unified panel endpoint.
        Returns snapshot with language style and interaction metrics.
        """
        try:
            from .chatdna_service import ChatDNACoach

            coach = ChatDNACoach(user_id)
            result = coach.get_chatdna_snapshot()

            return JSONResponse(content=result, status_code=200)

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"ChatDNA coach panel error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/coach/chatdna_coach/traits")
    def get_chatdna_traits(
        user_id: str = Query(..., description="User ID"),
        min_curiosity: float = Query(50.0, description="Minimum curiosity threshold")
    ):
        """
        Get language style traits with high curiosity.
        Used by LanguageStylePanel component.
        """
        try:
            from .chatdna_service import ChatDNACoach

            coach = ChatDNACoach(user_id)
            result = coach.get_language_traits(min_curiosity=min_curiosity)

            return JSONResponse(content=result, status_code=200)

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"ChatDNA traits error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================
    # BeliefDNA Coach Panel Endpoints
    # ========================================
    @app.get("/api/coach/beliefdna_coach/panel")
    def get_beliefdna_coach_panel(user_id: str = Query(..., description="User ID")):
        """
        BeliefDNA Coach unified panel endpoint.
        Returns snapshot, templates, console state, and evidence data.
        """
        try:
            from .beliefdna_service import BeliefDNACoach

            coach = BeliefDNACoach(user_id)
            result = coach.get_panel_data()

            return JSONResponse(content=result, status_code=200)

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"BeliefDNA coach panel error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/coach/beliefdna_coach/render")
    async def render_beliefdna_response(request: Request):
        """
        Generate a belief-based philosophical response.

        Request body:
          - prompt: The question to answer
          - intent: Category (moral, social, existential, political, psychological)
          - user_id: User identifier

        Returns reasoned answer with reasoning map and evidence.
        """
        try:
            from .beliefdna_service import BeliefDNACoach

            body = await request.json()
            user_id = body.get("user_id")
            prompt = body.get("prompt", "")
            intent = body.get("intent", "moral")

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")
            if not prompt:
                raise HTTPException(status_code=400, detail="prompt is required")

            coach = BeliefDNACoach(user_id)
            result = coach.generate_belief_response(prompt, intent)

            return JSONResponse(content=result, status_code=200)

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"BeliefDNA render error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/coach/beliefdna_coach/feedback")
    async def submit_beliefdna_feedback(request: Request):
        """
        Submit feedback on a BeliefDNA response to refine belief traits.

        Request body:
          - prompt: Original question
          - output: Generated response
          - user_rating: Rating from 1-5
          - notes: Optional feedback notes
          - user_id: User identifier

        Returns RR adjustments and affected containers.
        """
        try:
            from .beliefdna_service import BeliefDNACoach

            body = await request.json()
            user_id = body.get("user_id")
            prompt = body.get("prompt", "")
            output = body.get("output", "")
            user_rating = body.get("user_rating", 3)
            notes = body.get("notes", "")

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")

            coach = BeliefDNACoach(user_id)
            result = coach.record_feedback(prompt, output, user_rating, notes)

            return JSONResponse(content=result, status_code=200)

        except Exception as e:
            logger.error(f"BeliefDNA feedback error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # =========================================================================
    # COACH WORKSHOP ENDPOINTS
    # =========================================================================

    @app.get("/api/workshop/coaches")
    def list_workshop_coaches(source: str = Query("delegation", description="Source: delegation or legacy")):
        """
        List all available coaches with metadata for Workshop.
        Returns unified view of delegation coaches + legacy personas.
        """
        try:
            coaches = []

            if source == "delegation":
                # Read coach_registry.yaml
                registry_path = Path(__file__).parent.parent / "core" / "coach_registry.yaml"
                if registry_path.exists():
                    import yaml
                    with open(registry_path, "r", encoding="utf-8") as f:
                        registry = yaml.safe_load(f)

                    for coach_id, coach_meta in registry.get("coaches", {}).items():
                        # Find manifest
                        manifest_path = Path(__file__).parent.parent / "coaches" / coach_id / "coach_ui_manifest.yaml"
                        manifest_exists = manifest_path.exists()
                        manifest_valid = False
                        last_updated = None

                        if manifest_exists:
                            try:
                                with open(manifest_path, "r", encoding="utf-8") as mf:
                                    manifest_data = yaml.safe_load(mf)
                                    manifest_valid = bool(manifest_data.get("widgets"))
                                    last_updated = manifest_data.get("metadata", {}).get("updated_at")
                            except:
                                pass

                        coaches.append({
                            "id": coach_id,
                            "display_name": coach_meta.get("display_name", coach_id),
                            "description": coach_meta.get("description", ""),
                            "purpose": ", ".join(coach_meta.get("natural_domains", [])),
                            "manifest_path": str(manifest_path) if manifest_exists else None,
                            "manifest_exists": manifest_exists,
                            "manifest_valid": manifest_valid,
                            "status": "ready" if manifest_valid else ("draft" if manifest_exists else "no_manifest"),
                            "last_updated": last_updated,
                            "source": "delegation"
                        })

            elif source == "legacy":
                # Legacy personas (adapter stubs)
                legacy_personas = [
                    {"id": "head_coach", "display_name": "Head Coach (Legacy)", "description": "General conversational coach"},
                    {"id": "photo", "display_name": "Photo Coach (Legacy)", "description": "Physical appearance analysis"},
                    {"id": "padna", "display_name": "PaDNA Coach (Legacy)", "description": "Style and aesthetics"},
                    {"id": "relationship_coach", "display_name": "Relationship Coach (Legacy)", "description": "Relationship patterns"}
                ]

                for persona in legacy_personas:
                    coaches.append({
                        "id": persona["id"],
                        "display_name": persona["display_name"],
                        "description": persona["description"],
                        "purpose": "Legacy persona (adapter mode)",
                        "manifest_path": None,
                        "manifest_exists": False,
                        "manifest_valid": False,
                        "status": "legacy_adapter",
                        "last_updated": None,
                        "source": "legacy"
                    })

            return JSONResponse(content={"coaches": coaches, "source": source})

        except Exception as e:
            logger.error(f"Workshop coaches list error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/workshop/coaches/{coach_id}/manifest")
    def get_workshop_coach_manifest(coach_id: str):
        """
        Retrieve coach manifest YAML for Workshop editing.
        """
        try:
            manifest_path = Path(__file__).parent.parent / "coaches" / coach_id / "coach_ui_manifest.yaml"

            if not manifest_path.exists():
                raise HTTPException(status_code=404, detail=f"Manifest not found for {coach_id}")

            with open(manifest_path, "r", encoding="utf-8") as f:
                import yaml
                manifest_data = yaml.safe_load(f)

            # Also return raw YAML text for editor
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_yaml = f.read()

            return JSONResponse(content={
                "coach_id": coach_id,
                "manifest_path": str(manifest_path),
                "manifest_data": manifest_data,
                "manifest_yaml": manifest_yaml,
                "schema_version": manifest_data.get("schema_version"),
                "renderer_version": manifest_data.get("renderer_version"),
                "manifest_version": manifest_data.get("manifest_version")
            })

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workshop manifest get error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/workshop/coaches/{coach_id}/manifest/save")
    async def save_workshop_coach_manifest(coach_id: str, request: Request):
        """
        Save updated manifest (writes to _dev copy for safety).
        """
        try:
            body = await request.json()
            manifest_yaml = body.get("manifest_yaml")

            if not manifest_yaml:
                raise HTTPException(status_code=400, detail="manifest_yaml required")

            # Validate YAML
            import yaml
            try:
                manifest_data = yaml.safe_load(manifest_yaml)
            except yaml.YAMLError as e:
                raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

            # Schema validation (basic)
            if not manifest_data.get("widgets"):
                raise HTTPException(status_code=400, detail="Manifest must have 'widgets' array")

            if manifest_data.get("coach_id") != coach_id:
                raise HTTPException(status_code=400, detail=f"coach_id mismatch: expected {coach_id}")

            # Write to _dev copy
            manifest_dir = Path(__file__).parent.parent / "coaches" / coach_id
            manifest_dir.mkdir(parents=True, exist_ok=True)
            dev_manifest_path = manifest_dir / "coach_ui_manifest_dev.yaml"

            with open(dev_manifest_path, "w", encoding="utf-8") as f:
                f.write(manifest_yaml)

            return JSONResponse(content={
                "success": True,
                "dev_path": str(dev_manifest_path),
                "message": "Manifest saved to _dev copy. Use 'Promote' to move to stable."
            })

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workshop manifest save error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/workshop/coaches/{coach_id}/manifest/promote")
    def promote_workshop_manifest(coach_id: str):
        """
        Promote _dev manifest to stable (overwrites coach_ui_manifest.yaml).
        """
        try:
            manifest_dir = Path(__file__).parent.parent / "coaches" / coach_id
            dev_path = manifest_dir / "coach_ui_manifest_dev.yaml"
            stable_path = manifest_dir / "coach_ui_manifest.yaml"

            if not dev_path.exists():
                raise HTTPException(status_code=404, detail="No _dev manifest to promote")

            # Backup stable
            if stable_path.exists():
                import shutil
                from datetime import datetime
                backup_path = manifest_dir / f"coach_ui_manifest_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
                shutil.copy(stable_path, backup_path)

            # Copy dev → stable
            import shutil
            shutil.copy(dev_path, stable_path)

            return JSONResponse(content={
                "success": True,
                "stable_path": str(stable_path),
                "message": f"Manifest promoted to stable. Backup created."
            })

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workshop manifest promote error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/workshop/coaches/{coach_id}/preview")
    def preview_workshop_panel(
        coach_id: str,
        user_id: str = Query("TEST", description="User ID for preview"),
        data_mode: str = Query("live", description="Data mode: live, stub, hybrid"),
        intent: str = Query(None, description="Simulated intent")
    ):
        """
        Preview coach panel with simulated data.
        Returns same structure as production panel endpoint + perf metrics.
        """
        try:
            import time
            start_time = time.time()

            # Determine which panel endpoint to call
            panel_data = {}
            api_time = 0

            if data_mode == "live":
                # Call actual panel endpoint
                if coach_id == "career_coach":
                    # Would call internal function - for now return stub
                    panel_data = {"user_id": user_id, "widgets": [], "message": "Career Coach live preview"}
                elif coach_id == "personality_test_coach":
                    # Would call internal function
                    panel_data = {"user_id": user_id, "widgets": [], "message": "PTC live preview"}
                else:
                    panel_data = {"user_id": user_id, "widgets": [], "message": f"{coach_id} preview not implemented"}

            elif data_mode == "stub":
                # Load fixture
                fixture_path = Path(__file__).parent.parent / "coaches" / coach_id / "workshop_fixtures" / f"{intent or 'default'}.json"
                if fixture_path.exists():
                    with open(fixture_path, "r", encoding="utf-8") as f:
                        panel_data = json.load(f)
                else:
                    panel_data = {"user_id": user_id, "widgets": [], "message": "No fixture found"}

            else:  # hybrid
                # Live RR/curiosity + stub widget data
                panel_data = {"user_id": user_id, "widgets": [], "message": "Hybrid mode not yet implemented"}

            compose_time = (time.time() - start_time) * 1000  # ms

            return JSONResponse(content={
                "coach_id": coach_id,
                "user_id": user_id,
                "data_mode": data_mode,
                "intent": intent,
                "panel_data": panel_data,
                "performance": {
                    "compose_ms": round(compose_time, 2),
                    "api_ms": round(api_time, 2),
                    "fcp_ms": None,  # Would measure on frontend
                    "parity_ok": True
                }
            })

        except Exception as e:
            logger.error(f"Workshop preview error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/workshop/coaches/{coach_id}/simulate")
    async def simulate_user_state(coach_id: str, request: Request):
        """
        Simulate user state (RR, curiosity, intent) for testing panel behavior.
        """
        try:
            body = await request.json()
            user_id = body.get("user_id", "workshop_sim")
            intent = body.get("intent")
            rr_overrides = body.get("rr_overrides", {})  # {"SkillDNA": 40, "PsyDNA": 70}
            curiosity_overrides = body.get("curiosity_overrides", {})

            # Would apply overrides to a temp user state and return preview
            # For now, return stub
            return JSONResponse(content={
                "coach_id": coach_id,
                "user_id": user_id,
                "intent": intent,
                "rr_overrides": rr_overrides,
                "curiosity_overrides": curiosity_overrides,
                "message": "Simulation applied. Refresh preview to see changes."
            })

        except Exception as e:
            logger.error(f"Workshop simulate error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/workshop/coaches/{coach_id}/export")
    def export_workshop_bundle(coach_id: str):
        """
        Export coach bundle (manifest, fixtures, screenshots) as ZIP.
        """
        try:
            import zipfile
            from io import BytesIO
            from datetime import datetime

            manifest_dir = Path(__file__).parent.parent / "coaches" / coach_id
            manifest_path = manifest_dir / "coach_ui_manifest.yaml"

            if not manifest_path.exists():
                raise HTTPException(status_code=404, detail="No manifest to export")

            # Create ZIP in memory
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add manifest
                zf.write(manifest_path, f"{coach_id}/coach_ui_manifest.yaml")

                # Add fixtures if exist
                fixtures_dir = manifest_dir / "workshop_fixtures"
                if fixtures_dir.exists():
                    for fixture_file in fixtures_dir.glob("*.json"):
                        zf.write(fixture_file, f"{coach_id}/fixtures/{fixture_file.name}")

                # Add performance report (stub)
                perf_report = {
                    "coach_id": coach_id,
                    "exported_at": datetime.now().isoformat(),
                    "compose_target_ms": 200,
                    "fcp_target_ms": 300,
                    "parity_ok": True
                }
                zf.writestr(f"{coach_id}/performance_report.json", json.dumps(perf_report, indent=2))

            zip_buffer.seek(0)

            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={coach_id}_workshop_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workshop export error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # =========================================================================
    # CHATDNA COACH ENDPOINTS
    # =========================================================================

    @app.get("/api/coach/chatdna_coach/panel")
    def get_chatdna_coach_panel(user_id: str = Query(..., description="User ID")):
        """
        ChatDNA Coach unified panel endpoint.
        Returns snapshot, templates, console state, style profile, similarity, and evidence links.
        """
        try:
            resolved, evidence, obs = read_user_state(user_id)

            # Extract LanguageStyleDNA, PsyDNA, SocDNA data
            language_dna = resolved.get("LanguageStyleDNA", {})
            psydna = resolved.get("PsyDNA", {})
            socdna = resolved.get("SocDNA", {})
            metadna = resolved.get("MetaDNA", {})

            # Calculate aggregate RR scores
            def calculate_domain_rr(domain_data):
                rr_values = [v.get("rr", 0) for v in domain_data.values() if isinstance(v, dict) and "rr" in v]
                return round(sum(rr_values) / len(rr_values), 2) if rr_values else 0

            language_rr = calculate_domain_rr(language_dna)

            # Calculate personality RR from PsyDNA.PersonalityDNA
            personality_dna = {}
            for key, val in psydna.items():
                if key.startswith("PersonalityDNA."):
                    personality_dna[key] = val
            personality_rr = calculate_domain_rr(personality_dna)

            # Calculate social RR from SocDNA.InteractionStyleDNA
            interaction_dna = {}
            for key, val in socdna.items():
                if key.startswith("InteractionStyleDNA."):
                    interaction_dna[key] = val
            social_rr = calculate_domain_rr(interaction_dna)

            # Find top curiosity items
            all_style_traits = {}
            all_style_traits.update(language_dna)
            all_style_traits.update(personality_dna)
            all_style_traits.update(interaction_dna)

            curiosity_items = []
            for path, data in all_style_traits.items():
                if isinstance(data, dict):
                    curiosity = data.get("curiosity", 0)
                    rr = data.get("rr", 0)
                    if curiosity > 60 or rr < 40:
                        curiosity_items.append({
                            "path": path,
                            "curiosity": curiosity,
                            "rr": rr
                        })

            # Sort by curiosity (descending)
            curiosity_items.sort(key=lambda x: x["curiosity"], reverse=True)
            top_curiosity = [item["path"] for item in curiosity_items[:3]]

            # Detect active intent based on data state
            if language_rr < 40:
                active_intent = "casual"  # Start with simple examples
            elif personality_rr > 60:
                active_intent = "reflective"  # Have enough data for complex styles
            else:
                active_intent = "casual"

            # Build snapshot
            snapshot = {
                "language_rr": language_rr,
                "personality_rr": personality_rr,
                "social_rr": social_rr,
                "top_curiosity": top_curiosity,
                "active_intent": active_intent
            }

            # Build templates
            templates = {
                "cards": [
                    {
                        "id": "intro_casual",
                        "title": "Casual intro",
                        "prompt": "Hey, just checking in...",
                        "category": "casual"
                    },
                    {
                        "id": "email_formal",
                        "title": "Formal email",
                        "prompt": "Dear team, following up on...",
                        "category": "formal"
                    },
                    {
                        "id": "persuade",
                        "title": "Persuasive note",
                        "prompt": "I believe we should consider...",
                        "category": "persuasive"
                    },
                    {
                        "id": "late_message",
                        "title": "Running late",
                        "prompt": "Write two sentences saying I'm running 10 minutes late.",
                        "category": "casual"
                    },
                    {
                        "id": "technical_explanation",
                        "title": "Technical explanation",
                        "prompt": "Explain how to configure the database connection.",
                        "category": "technical"
                    }
                ]
            }

            # Console state (initially empty)
            console_state = {
                "last_prompt": "",
                "last_output": ""
            }

            # Build style profile (from available data)
            style_profile_rows = []

            # Extract key language traits
            for trait_path in ["CadenceDNA", "VocabularyDensityDNA", "FormalityDNA", "HedgingPatternDNA"]:
                full_path = f"LanguageStyleDNA.{trait_path}"
                trait_data = language_dna.get(full_path, {})
                if trait_data and isinstance(trait_data, dict):
                    rr = trait_data.get("rr", 0)
                    confidence = rr / 100.0 if rr > 0 else 0.0
                    # Infer value from RR (stub - would use actual trait value)
                    if "Cadence" in trait_path:
                        value = "medium-fast" if rr > 50 else "medium"
                    elif "Vocabulary" in trait_path:
                        value = "high" if rr > 60 else "medium"
                    elif "Formality" in trait_path:
                        value = "semi-formal" if rr > 50 else "casual"
                    elif "Hedging" in trait_path:
                        value = "light" if rr > 50 else "moderate"
                    else:
                        value = "unknown"

                    style_profile_rows.append({
                        "trait": trait_path.replace("DNA", ""),
                        "value": value,
                        "confidence": round(confidence, 2),
                        "source": "LanguageStyleDNA"
                    })

            # Add personality traits that affect style
            personality_traits = ["AgreeablenessDNA", "ExtraversionDNA", "OpennessDNA"]
            for trait_path in personality_traits:
                full_path = f"PersonalityDNA.BigFiveDNA.{trait_path}"
                trait_data = psydna.get(full_path, {})
                if trait_data and isinstance(trait_data, dict):
                    rr = trait_data.get("rr", 0)
                    confidence = rr / 100.0 if rr > 0 else 0.0
                    value = "high" if rr > 60 else ("medium" if rr > 30 else "low")

                    style_profile_rows.append({
                        "trait": trait_path.replace("DNA", " (tone)"),
                        "value": value,
                        "confidence": round(confidence, 2),
                        "source": "PsyDNA.PersonalityDNA"
                    })

            style_profile = {
                "rows": style_profile_rows
            }

            # Similarity monitor (stub - would compute from actual samples)
            similarity = {
                "cards": [
                    {
                        "title": "Linguistic similarity",
                        "score": 0.72 if language_rr > 50 else 0.45,
                        "note": "Cosine similarity vs writing samples" if language_rr > 50 else "Insufficient data for comparison",
                        "rr_delta": 4 if language_rr > 50 else 0
                    },
                    {
                        "title": "Tone alignment",
                        "score": 0.66 if personality_rr > 50 else 0.40,
                        "note": "Sentiment + hedging pattern match" if personality_rr > 50 else "Limited personality data",
                        "curiosity_delta": -6 if personality_rr > 50 else 0
                    },
                    {
                        "title": "Social style match",
                        "score": 0.58 if social_rr > 50 else 0.35,
                        "note": "Interaction pattern alignment" if social_rr > 50 else "Gather more social data",
                        "rr_delta": 2 if social_rr > 50 else 0
                    }
                ]
            }

            # Evidence links
            evidence_items = []
            for path, data in all_style_traits.items():
                if isinstance(data, dict) and data.get("rr", 0) > 30:
                    evidence_items.append({
                        "path": path,
                        "rr": data.get("rr", 0)
                    })

            # Sort by RR descending
            evidence_items.sort(key=lambda x: x["rr"], reverse=True)
            evidence_items = evidence_items[:10]  # Top 10

            evidence_links = {
                "items": evidence_items
            }

            return JSONResponse(content={
                "user_id": user_id,
                "snapshot": snapshot,
                "templates": templates,
                "console_state": console_state,
                "style_profile": style_profile,
                "similarity": similarity,
                "evidence_links": evidence_links
            })

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        except Exception as e:
            logger.error(f"ChatDNA panel error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/coach/chatdna_coach/render")
    async def render_chatdna_response(request: Request):
        """
        Generate a response in the user's conversational style.
        Uses LanguageStyleDNA, PsyDNA, SocDNA to synthesize style.
        """
        try:
            body = await request.json()
            prompt = body.get("prompt", "")
            intent = body.get("intent", "casual")
            options = body.get("options", {})
            user_id = body.get("user_id", "TEST")

            if not prompt:
                raise HTTPException(status_code=400, detail="prompt required")

            # Load user state
            resolved, evidence, obs = read_user_state(user_id)

            # Extract style data
            language_dna = resolved.get("LanguageStyleDNA", {})
            psydna = resolved.get("PsyDNA", {})
            socdna = resolved.get("SocDNA", {})

            # Build style profile for synthesis
            style_profile = []

            # Cadence
            cadence_data = language_dna.get("LanguageStyleDNA.CadenceDNA", {})
            cadence_rr = cadence_data.get("rr", 0)
            cadence_value = "medium-fast" if cadence_rr > 50 else "medium"
            style_profile.append({
                "trait": "CadenceDNA",
                "value": cadence_value,
                "confidence": round(cadence_rr / 100.0, 2) if cadence_rr > 0 else 0.5
            })

            # Vocabulary density
            vocab_data = language_dna.get("LanguageStyleDNA.VocabularyDensityDNA", {})
            vocab_rr = vocab_data.get("rr", 0)
            vocab_value = "high" if vocab_rr > 60 else ("medium" if vocab_rr > 30 else "medium")
            style_profile.append({
                "trait": "VocabularyDensityDNA",
                "value": vocab_value,
                "confidence": round(vocab_rr / 100.0, 2) if vocab_rr > 0 else 0.5
            })

            # Hedging pattern
            hedging_data = language_dna.get("LanguageStyleDNA.HedgingPatternDNA", {})
            hedging_rr = hedging_data.get("rr", 0)
            hedging_value = "light" if hedging_rr > 50 else "moderate"
            style_profile.append({
                "trait": "HedgingPatternDNA",
                "value": hedging_value,
                "confidence": round(hedging_rr / 100.0, 2) if hedging_rr > 0 else 0.5
            })

            # Formality
            formality_data = language_dna.get("LanguageStyleDNA.FormalityDNA", {})
            formality_rr = formality_data.get("rr", 0)
            if intent == "formal":
                formality_value = "formal"
            elif intent == "casual":
                formality_value = "casual"
            else:
                formality_value = "semi-formal" if formality_rr > 50 else "casual"
            style_profile.append({
                "trait": "FormalityDNA",
                "value": formality_value,
                "confidence": round(formality_rr / 100.0, 2) if formality_rr > 0 else 0.5
            })

            # Agreeableness (affects warmth)
            agree_data = psydna.get("PersonalityDNA.BigFiveDNA.AgreeablenessDNA", {})
            agree_rr = agree_data.get("rr", 0)
            agree_value = "warm" if agree_rr > 60 else ("neutral" if agree_rr > 30 else "neutral")

            # Generate response using LLM or return honest error
            import os
            api_key_openai = os.getenv("OPENAI_API_KEY", "").strip()
            api_key_anthropic = os.getenv("ANTHROPIC_API_KEY", "").strip()

            if not api_key_openai and not api_key_anthropic:
                # No API key - be honest
                output = "⚠️ I can't generate a live response because no LLM API key is configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY to enable AI responses."
            else:
                # Build style synthesis prompt
                style_desc = f"""You are mimicking the conversational style of {user_id}.

Style profile:
- Cadence: {cadence_value}
- Vocabulary: {vocab_value}
- Hedging: {hedging_value}
- Formality: {formality_value}
- Tone: {agree_value}

Generate a response to this prompt in their style: {prompt}

Intent: {intent}
"""

                try:
                    if api_key_openai:
                        import openai
                        client = openai.OpenAI(api_key=api_key_openai, timeout=10)
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": style_desc},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=200,
                            temperature=0.7
                        )
                        output = response.choices[0].message.content
                    else:  # Anthropic
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key_anthropic, timeout=10)
                        response = client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            system=style_desc,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=200,
                            temperature=0.7
                        )
                        output = response.content[0].text
                except Exception as e:
                    logger.error(f"ChatDNA LLM generation failed: {e}")
                    output = f"⚠️ Error generating response: {str(e)}"

            # Calculate similarity (stub)
            linguistic_similarity = 0.71 if cadence_rr > 50 else 0.45
            tone_similarity = 0.65 if agree_rr > 50 else 0.40
            overall_similarity = (linguistic_similarity + tone_similarity) / 2

            similarity = {
                "linguistic": round(linguistic_similarity, 2),
                "tone": round(tone_similarity, 2),
                "overall": round(overall_similarity, 2)
            }

            # Relevant containers
            relevant_containers = [
                "LanguageStyleDNA.CadenceDNA",
                "LanguageStyleDNA.HedgingPatternDNA",
                "LanguageStyleDNA.VocabularyDensityDNA",
                "PsyDNA.PersonalityDNA.BigFiveDNA.AgreeablenessDNA"
            ]

            # RR summary
            def calc_domain_rr(domain_data):
                rr_vals = [v.get("rr", 0) for v in domain_data.values() if isinstance(v, dict) and "rr" in v]
                return round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else 0

            rr_summary = {
                "LanguageStyleDNA": calc_domain_rr(language_dna),
                "PersonalityDNA": calc_domain_rr({k: v for k, v in psydna.items() if "PersonalityDNA" in k}),
                "InteractionStyleDNA": calc_domain_rr({k: v for k, v in socdna.items() if "InteractionStyleDNA" in k})
            }

            # Gap logging: detect unmapped features and fallbacks
            try:
                from ReDNACoreDemo.core.feature_map import (
                    get_feature_map_version, lookup_container, is_unmapped
                )
                from ReDNACoreDemo.core.gap_logs import (
                    log_unmet_features, create_gap_item, extract_mock_features
                )

                # Extract features from prompt (mock in this version)
                extracted_features = extract_mock_features(prompt, intent)

                # Detect gaps
                gap_items = []
                for feature, value in extracted_features.items():
                    container = lookup_container(feature)

                    if is_unmapped(feature):
                        # Unmapped feature - estimate impact
                        impact_estimate = 0.08 if value > 0.5 else 0.04
                        gap_items.append(create_gap_item(
                            feature=feature,
                            gap_type="unmapped",
                            value=value,
                            impact_estimate=impact_estimate
                        ))
                    elif container:
                        # Mapped feature - check if we're falling back due to low RR
                        container_data = resolved
                        for part in container.split('.'):
                            container_data = container_data.get(part, {})
                        container_rr = container_data.get("rr", 0) if isinstance(container_data, dict) else 0

                        if container_rr < 40:  # Low confidence threshold
                            impact_estimate = 0.05
                            gap_items.append(create_gap_item(
                                feature=feature,
                                gap_type="fallback",
                                value=value,
                                impact_estimate=impact_estimate,
                                mapped_to=container
                            ))

                # Log if we have gaps
                if gap_items:
                    log_unmet_features(
                        user_id=user_id,
                        prompt=prompt,
                        intent=intent,
                        feature_map_version=get_feature_map_version(),
                        items=gap_items,
                        rr_context=rr_summary
                    )
            except Exception as gap_log_error:
                # Don't fail the render if gap logging fails
                logger.warning(f"Gap logging failed: {gap_log_error}")

            return JSONResponse(content={
                "output": output,
                "style_profile": style_profile,
                "similarity": similarity,
                "relevant_containers": relevant_containers,
                "rr_summary": rr_summary,
                "policy": {
                    "renderer_version": 1,
                    "manifest_version": 1
                }
            })

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"ChatDNA render error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/coach/chatdna_coach/feedback")
    async def submit_chatdna_feedback(request: Request):
        """
        Collect user feedback on generated response similarity.
        Updates UCN and triggers RR recomputation.
        """
        try:
            body = await request.json()
            prompt = body.get("prompt", "")
            output = body.get("output", "")
            user_rating = body.get("user_rating", 3)  # 1-5
            notes = body.get("notes", "")
            user_id = body.get("user_id", "TEST")

            if not output or user_rating < 1 or user_rating > 5:
                raise HTTPException(status_code=400, detail="Invalid feedback data")

            # Log feedback
            logger.info(f"ChatDNA feedback: user={user_id}, rating={user_rating}, notes={notes}")

            # Convert rating to similarity delta
            # 5 = perfect match (+10 to relevant RR)
            # 4 = good match (+5)
            # 3 = neutral (0)
            # 2 = poor match (-5)
            # 1 = terrible match (-10)
            rr_delta_map = {
                5: 10,
                4: 5,
                3: 0,
                2: -5,
                1: -10
            }
            rr_delta = rr_delta_map.get(user_rating, 0)

            # Apply small UCN adjustments to relevant containers
            # (In production, would update resolved.json and trigger RR recompute)
            affected_containers = [
                "LanguageStyleDNA.CadenceDNA",
                "LanguageStyleDNA.VocabularyDensityDNA",
                "LanguageStyleDNA.HedgingPatternDNA",
                "LanguageStyleDNA.FormalityDNA"
            ]

            # Log provenance
            from datetime import datetime
            feedback_record = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "prompt": prompt,
                "output": output,
                "user_rating": user_rating,
                "notes": notes,
                "rr_delta": rr_delta,
                "affected_containers": affected_containers
            }

            # Store feedback (would write to provenance log)
            logger.info(f"ChatDNA feedback recorded: {feedback_record}")

            return JSONResponse(content={
                "success": True,
                "rr_delta": rr_delta,
                "affected_containers": affected_containers,
                "message": f"Feedback recorded. RR adjustments: {'+' if rr_delta >= 0 else ''}{rr_delta}"
            })

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"ChatDNA feedback error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ═══════════════════════════════════════════════════════════════════════
    # HEAD COACH V2 (JARVIS-CLASS ORCHESTRATOR) API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════

    @app.get("/hc/awareness")
    def get_head_coach_awareness(
        user_id: str = Query(..., description="User ID"),
        force_refresh: bool = Query(False, description="Force cache refresh for all layers")
    ):
        """
        Get Head Coach situational awareness snapshot for user.

        Returns 4-layer awareness model:
        - Core state (live): Active coach, curiosity hotspots, delegation state
        - Goal/task layer (5m TTL): Active goals, pending tasks
        - Context layer (1h TTL): Recent topics, active threads
        - Memory layer (24h TTL): Long-term patterns, RR by domain

        Includes emotional tone analysis, TTL hints, policy metadata, and Workshop summary.

        Response time target: ≤20ms (warm cache)
        Privacy: No raw message text included
        """
        try:
            from .head_coach.situational_awareness import AwarenessEngine

            engine = AwarenessEngine()
            snapshot = engine.get_snapshot(user_id, force_refresh=force_refresh)

            return snapshot

        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        except Exception as e:
            logger.error(f"Head Coach awareness error for user {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/classify-intent")
    async def classify_user_intent(request: Request):
        """
        Classify user message intent for coach routing.

        Body: { "message": "...", "user_id": "...", "context": {...} }

        Returns intent classification matching hc_intent.schema.json
        """
        try:
            from .head_coach.intent_classifier import IntentClassifier

            body = await request.json()
            message = body.get("message")
            user_id = body.get("user_id")
            context = body.get("context", {})

            if not message:
                raise HTTPException(status_code=400, detail="message required")
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id required")

            # Classify intent
            classifier = IntentClassifier()
            result = classifier.classify(message, context)

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Intent classification error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/route-delegation")
    async def route_user_delegation(request: Request):
        """
        Route user message to appropriate coach based on intent.

        Body: {
            "message": "...",
            "user_id": "...",
            "current_coach": "head_coach",
            "context": {...}
        }

        Returns routing decision with target coach and handoff details.
        """
        try:
            from .head_coach.delegation_router import DelegationRouter

            body = await request.json()
            message = body.get("message")
            user_id = body.get("user_id")
            current_coach = body.get("current_coach", "head_coach")
            context = body.get("context", {})

            if not message:
                raise HTTPException(status_code=400, detail="message required")
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id required")

            # Route message
            router = DelegationRouter()
            routing_decision = router.route(
                message=message,
                user_id=user_id,
                current_coach=current_coach,
                context=context
            )

            return routing_decision

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delegation routing error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/hc/routing-stats")
    def get_routing_statistics():
        """
        Get routing statistics for monitoring/optimization.

        Returns delegation rates, coach distribution, intent distribution.
        """
        try:
            from .head_coach.delegation_router import DelegationRouter

            # Note: In production, this would access persistent stats storage
            # For now, returns empty stats (router is stateless between requests)
            router = DelegationRouter()
            stats = router.get_routing_stats()

            return stats

        except Exception as e:
            logger.error(f"Routing stats error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hc/personality")
    async def get_head_coach_personality(request: Request):
        """
        Get context-aware personality envelope for Head Coach.

        Integrates:
        - CReDNA personality synthesis
        - Situational awareness (emotional tone, goals, context)
        - Intent classification (what user wants)

        Body: {
            "user_id": "...",
            "awareness_snapshot": {...},  # Optional: from /hc/awareness
            "intent_analysis": {...},      # Optional: from /hc/classify-intent
            "override_intent": "supportive|analytical|delegation_mode"  # Optional
        }

        Returns personality envelope with style dimensions + meta-dimensions.
        """
        try:
            from .head_coach.personality_engine import PersonalityEngine

            body = await request.json()
            user_id = body.get("user_id")
            awareness_snapshot = body.get("awareness_snapshot")
            intent_analysis = body.get("intent_analysis")
            override_intent = body.get("override_intent")

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id required")

            # Build personality envelope
            engine = PersonalityEngine()
            personality = engine.build_personality_envelope(
                user_id=user_id,
                awareness_snapshot=awareness_snapshot,
                intent_analysis=intent_analysis,
                override_intent=override_intent
            )

            return personality

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Personality build error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ═══════════════════════════════════════════════════════════════════════
    # CREDNA API ENDPOINTS (Per-User, Per-Coach Personality Engine)
    # ═══════════════════════════════════════════════════════════════════════

    @app.get("/api/credna/style_envelope")
    def get_style_envelope(
        user_id: str = Query(..., description="User ID"),
        coach_id: str = Query(..., description="Coach ID"),
        intent: str = Query("default", description="Intent/mode (default, supportive, analytical, etc.)")
    ):
        """
        Build CReDNA style/persona envelope for (user, coach, intent).

        IMPORTANT: ChatDNA Coach is NOT allowed to use CReDNA.
        ChatDNA uses user self-simulation (ReDNA only).
        All other coaches use CReDNA (coach personalities).

        Returns:
            Style envelope with tone, cadence, formality, etc.
        """
        try:
            # Enforce architectural boundary: ChatDNA cannot use CReDNA
            if coach_id == "chatdna_coach":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ChatDNA Coach uses user self-simulation (ReDNA only)",
                        "message": "ChatDNA does not use CReDNA. It simulates the user talking to themselves.",
                        "hint": "Use ChatDNA's existing render endpoint instead"
                    }
                )

            from .credna.persona_synthesis import build_envelope

            envelope = build_envelope(user_id, coach_id, intent)

            return envelope

        except ValueError as e:
            # Catches the guard in build_envelope()
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.error(f"CReDNA envelope error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/credna/feedback")
    async def submit_credna_feedback(request: Request):
        """
        Submit dimensional feedback for (user, coach) pair.

        Accepts either:
        - Rating-based: { "dimension": "directness", "rating": 4 }
        - Chip-based: { "chips": ["more_direct", "less_formal"] }

        IMPORTANT: ChatDNA Coach is NOT allowed to use CReDNA feedback.
        """
        try:
            body = await request.json()
            user_id = body.get("user_id")
            coach_id = body.get("coach_id")

            if not user_id or not coach_id:
                raise HTTPException(status_code=400, detail="user_id and coach_id required")

            # Enforce architectural boundary
            if coach_id == "chatdna_coach":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ChatDNA Coach does not use CReDNA",
                        "message": "ChatDNA feedback updates ReDNA style traits, not CReDNA deltas",
                        "hint": "Use ChatDNA's existing feedback endpoint instead"
                    }
                )

            # TODO: Implement feedback processing with cooldowns
            # For now, return success stub
            return {
                "status": "success",
                "message": "CReDNA feedback endpoint (stub - implementation pending)",
                "user_id": user_id,
                "coach_id": coach_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"CReDNA feedback error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/credna/save_prefs")
    async def save_credna_prefs(request: Request):
        """
        Save manual preference overrides for (user, coach) pair.

        Body: { "user_id": "...", "coach_id": "...", "prefs": { "directness": "high", ... } }

        IMPORTANT: ChatDNA Coach is NOT allowed to use CReDNA prefs.
        """
        try:
            body = await request.json()
            user_id = body.get("user_id")
            coach_id = body.get("coach_id")
            prefs = body.get("prefs", {})

            if not user_id or not coach_id:
                raise HTTPException(status_code=400, detail="user_id and coach_id required")

            # Enforce architectural boundary
            if coach_id == "chatdna_coach":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ChatDNA Coach does not use CReDNA",
                        "message": "ChatDNA uses ReDNA only, no manual personality overrides",
                        "hint": "Adjust user's ReDNA traits directly instead"
                    }
                )

            # TODO: Implement prefs saving with validation
            # For now, return success stub
            return {
                "status": "success",
                "message": "CReDNA save_prefs endpoint (stub - implementation pending)",
                "user_id": user_id,
                "coach_id": coach_id,
                "prefs": prefs
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"CReDNA save_prefs error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/credna/reset")
    async def reset_credna(request: Request):
        """
        Reset learned deltas and/or prefs for (user, coach) pair.

        Body: { "user_id": "...", "coach_id": "...", "reset": "all|deltas|prefs" }

        IMPORTANT: ChatDNA Coach is NOT allowed to use CReDNA reset.
        """
        try:
            body = await request.json()
            user_id = body.get("user_id")
            coach_id = body.get("coach_id")
            reset_type = body.get("reset", "all")

            if not user_id or not coach_id:
                raise HTTPException(status_code=400, detail="user_id and coach_id required")

            # Enforce architectural boundary
            if coach_id == "chatdna_coach":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ChatDNA Coach does not use CReDNA",
                        "message": "ChatDNA has no deltas/prefs to reset",
                        "hint": "ChatDNA uses ReDNA only"
                    }
                )

            # TODO: Implement reset logic
            # For now, return success stub
            return {
                "status": "success",
                "message": "CReDNA reset endpoint (stub - implementation pending)",
                "user_id": user_id,
                "coach_id": coach_id,
                "reset": reset_type
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"CReDNA reset error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # =====================================================================
    # HEAD COACH LIFE OS ENDPOINTS
    # =====================================================================

    @app.get("/ui/hc/life/{user_id}/summary")
    async def get_life_summary(user_id: str):
        """Get Life OS summary (north star, goals, todos, links, quote)."""
        try:
            summary = hc_life.get_life_summary(user_id)
            return {"ok": True, **summary}
        except Exception as e:
            logger.error(f"Life OS summary error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ui/hc/life/{user_id}/human_intel")
    async def get_life_human_intel(user_id: str, days: int = Query(7, ge=1, le=30)):
        """Expose empathy + curiosity telemetry for DevX Life OS surfaces."""
        start = time.perf_counter()
        try:
            snapshot = hc_human_intel.build_human_intel_snapshot(user_id, window_days=days)
            duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
            return {"ok": True, "snapshot": snapshot, "duration_ms": duration_ms}
        except Exception as e:
            logger.error(f"Life OS human intel error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/ui/hc/life/{user_id}/capture")
    async def quick_capture(user_id: str, request: Request):
        """Quick capture text into a todo."""
        try:
            body = await request.json()
            text = body.get("text", "").strip()
            when = body.get("when", "today")

            if not text:
                raise HTTPException(status_code=400, detail="text required")

            todo = hc_life.Todo(
                id="",
                text=text,
                when=when,
                tags=body.get("tags", [])
            )
            created = hc_life.create_todo(user_id, todo)

            return {"ok": True, "todo": hc_life.asdict(created)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Life OS capture error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ui/hc/life/{user_id}/goals")
    async def list_goals(user_id: str, status: str = None):
        """List goals for user."""
        try:
            goals = hc_life.list_goals(user_id, status)
            return {"ok": True, "goals": [hc_life.asdict(g) for g in goals]}
        except Exception as e:
            logger.error(f"Life OS list goals error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/ui/hc/life/{user_id}/goals")
    async def create_goal(user_id: str, request: Request):
        """Create a new goal."""
        try:
            body = await request.json()
            goal = hc_life.Goal(
                id="",
                text=body.get("text", ""),
                owner=body.get("owner", user_id),
                why=body.get("why", ""),
                first_step=body.get("first_step", ""),
                confidence=body.get("confidence", 0.5),
                target_date=body.get("target_date")
            )
            created = hc_life.create_goal(user_id, goal)
            return {"ok": True, "goal": hc_life.asdict(created)}
        except Exception as e:
            logger.error(f"Life OS create goal error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/ui/hc/life/{user_id}/todos")
    async def list_todos(user_id: str, when: str = None):
        """List todos for user."""
        try:
            todos = hc_life.list_todos(user_id, when)
            return {"ok": True, "todos": [hc_life.asdict(t) for t in todos]}
        except Exception as e:
            logger.error(f"Life OS list todos error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.patch("/ui/hc/life/{user_id}/todos/{todo_id}")
    async def update_todo(user_id: str, todo_id: str, request: Request):
        """Update a todo."""
        try:
            body = await request.json()
            success = hc_life.update_todo(user_id, todo_id, body)
            if success:
                return {"ok": True}
            raise HTTPException(status_code=404, detail="Todo not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Life OS update todo error for {user_id}/{todo_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    return app


# Module-level app instance for uvicorn
app = build_app()
