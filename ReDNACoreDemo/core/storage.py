# ReDNACoreDemo/core/storage.py
from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Iterable, Mapping
from uuid import uuid4

from . import curiosity_engine, governance
from .ingest.policy import migrate_trait_record
from .bundles import CURRENT_SCHEMA, CURRENT_VERSION, iso_now, migrate

ROOT = Path(__file__).resolve().parents[1]  # ReDNACoreDemo/
PROJECT_ROOT = ROOT.parent

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", str(PROJECT_ROOT))).expanduser().resolve()
CUSTOM_DATA_ROOT = os.getenv("REDNA_CORE_DATA") or os.getenv("CORE_DATA_DIR")
REDNA_HOME = Path(os.getenv("REDNA_HOME", Path.home() / ".redna")).expanduser()
WHY_CARDS_GLOBAL_PATH = Path(os.getenv("REDNA_WHY_CARDS_LOG", str(REDNA_HOME / "why_cards.jsonl"))).expanduser()

if CUSTOM_DATA_ROOT:
    CORE_DATA_ROOT = Path(CUSTOM_DATA_ROOT).expanduser().resolve()
else:
    CORE_DATA_ROOT = (WORKSPACE_ROOT / "data").resolve()

CORE_DATA_ROOT.mkdir(parents=True, exist_ok=True)

REPO_DATA_DIR = ROOT / "data"
USERS_DIR = CORE_DATA_ROOT / "users"
CHECKPOINTS_DIR = CORE_DATA_ROOT / "checkpoints"
BUNDLES_DIR = CORE_DATA_ROOT / "bundles"
CONFIG_DIR = REPO_DATA_DIR / "config"
ASK_QUEUE_FILENAME = "ask_queue.json"

REPO_USERS_DIR = REPO_DATA_DIR / "users"
REPO_CHECKPOINTS_DIR = REPO_DATA_DIR / "checkpoints"
LEGACY_STORAGE_USERS_DIR = REPO_DATA_DIR / "storage" / "users"

for required_dir in (USERS_DIR, CHECKPOINTS_DIR, BUNDLES_DIR):
    required_dir.mkdir(parents=True, exist_ok=True)

# File names in each user folder we keep stable:
RESOLVED_FILENAME = "resolved.json"       # final merged view (what Explorer shows)
EVIDENCE_FILENAME = "evidence.json"       # all raw “facts” with provenance
OBS_FILENAME = "observations.json"        # intermediate normalized observations
USER_INFO_FILENAME = "user.json"          # metadata about the user
MEDIA_DIR_NAME = "media"
MEDIA_INDEX_FILENAME = "_index.json"
SNAPSHOT_PATTERN = "bundle-"
RENDERS_DIR_NAME = "renders"
RENDER_JOB_FILENAME = "job.json"
DRAFTS_DIR_NAME = "drafts"
WHY_CARDS_FILENAME = "why_cards.json"
CURIOSITY_QUEUE_FILENAME = "curiosity_queue.json"


@dataclass
class UserSummary:
    user_id: str
    label: str
    created_ts: Optional[str]
    last_used_ts: Optional[str] = None
    last_modified_ts: Optional[str] = None

def ensure_dirs_for_user(user_id: str) -> Dict[str, Path]:
    udir = USERS_DIR / user_id
    if not udir.exists():
        seed = REPO_USERS_DIR / user_id
        if seed.exists():
            shutil.copytree(seed, udir)
        else:
            udir.mkdir(parents=True, exist_ok=True)
    else:
        udir.mkdir(parents=True, exist_ok=True)

    user_checkpoint = CHECKPOINTS_DIR / user_id
    if not user_checkpoint.exists():
        seed_checkpoint = REPO_CHECKPOINTS_DIR / user_id
        if seed_checkpoint.exists():
            shutil.copytree(seed_checkpoint, user_checkpoint)
        else:
            user_checkpoint.mkdir(parents=True, exist_ok=True)
    else:
        user_checkpoint.mkdir(parents=True, exist_ok=True)

    (user_checkpoint / "events").mkdir(parents=True, exist_ok=True)
    (udir / MEDIA_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return {
        "udir": udir,
        "resolved": udir / RESOLVED_FILENAME,
        "evidence": udir / EVIDENCE_FILENAME,
        "observations": udir / OBS_FILENAME,
        "info": udir / USER_INFO_FILENAME,
        "events": user_checkpoint / "events",
        "rollback": user_checkpoint / governance.ROLLBACK_FILENAME,
        "media": udir / MEDIA_DIR_NAME,
        "why_cards": udir / WHY_CARDS_FILENAME,
        "curiosity": udir / CURIOSITY_QUEUE_FILENAME,
    }

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False))


def _user_info_path(user_id: str) -> Path:
    return ensure_dirs_for_user(user_id)["info"]


def load_user_info(user_id: str) -> Dict[str, Any]:
    info_path = _user_info_path(user_id)
    info = load_json(info_path, default={})
    if not isinstance(info, dict):
        info = {}
    info.setdefault("id", user_id)
    info.setdefault("label", user_id)
    if "created_ts" not in info:
        info["created_ts"] = iso_now()
    return info


def save_user_info(user_id: str, info: Dict[str, Any]) -> None:
    info_path = _user_info_path(user_id)
    payload = dict(info)
    payload.setdefault("id", user_id)
    payload.setdefault("label", user_id)
    payload.setdefault("created_ts", iso_now())
    save_json(info_path, payload)


def load_why_cards(user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    path = ensure_dirs_for_user(user_id)["why_cards"]
    cards = load_json(path, default=[])
    if not isinstance(cards, list):
        cards = []
    cards = [c for c in cards if isinstance(c, dict)]
    if limit is not None and limit >= 0:
        return cards[-limit:]
    return cards


def append_why_card(user_id: str, card: Dict[str, Any], *, max_items: int = 200) -> None:
    path = ensure_dirs_for_user(user_id)["why_cards"]
    cards = load_why_cards(user_id)
    cards.append(card)
    if len(cards) > max_items:
        cards = cards[-max_items:]
    save_json(path, cards)
    try:
        WHY_CARDS_GLOBAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with WHY_CARDS_GLOBAL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(card, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_curiosity_queue(user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    path = ensure_dirs_for_user(user_id)["curiosity"]
    items = load_json(path, default=[])
    if not isinstance(items, list):
        items = []
    items = [item for item in items if isinstance(item, dict)]
    if limit is not None and limit >= 0:
        return items[-limit:]
    return items


def enqueue_curiosity(user_id: str, item: Dict[str, Any], *, max_items: int = 200) -> None:
    path = ensure_dirs_for_user(user_id)["curiosity"]
    queue = load_curiosity_queue(user_id)
    queue.append(item)
    if len(queue) > max_items:
        queue = queue[-max_items:]
    save_json(path, queue)

def event_checkpoint(user_id: str, name: str, payload: Dict[str, Any]) -> Path:
    # Save an event under checkpoints to help with regressions
    epath = ensure_dirs_for_user(user_id)["events"] / f"{name}.json"
    save_json(epath, payload)
    return epath

def read_user_state(user_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    paths = ensure_dirs_for_user(user_id)
    raw_resolved = load_json(paths["resolved"], default={})
    if isinstance(raw_resolved, dict) and isinstance(raw_resolved.get("resolved"), dict):
        resolved = raw_resolved["resolved"]
    elif isinstance(raw_resolved, dict):
        resolved = raw_resolved
    else:
        resolved = {}

    if isinstance(resolved, dict):
        for trait_id, trait_payload in list(resolved.items()):
            if isinstance(trait_payload, dict):
                migrate_trait_record(trait_payload)
            else:
                resolved.pop(trait_id)

    curiosity_engine.seed_resolved(resolved)

    evidence = load_json(paths["evidence"], default={"items": []})
    observations = load_json(paths["observations"], default={"items": [], "by_trait": {}})
    if not isinstance(observations, dict):
        observations = {"items": [], "by_trait": {}}
    observations.setdefault("items", [])
    observations.setdefault("by_trait", {})
    return resolved, evidence, observations

def write_user_state(
    user_id: str,
    resolved: Dict[str, Any],
    evidence: Dict[str, Any],
    observations: Dict[str, Any],
    *,
    enforce_governance: bool = True,
) -> None:
    paths = ensure_dirs_for_user(user_id)

    if enforce_governance:
        governance.enforce_sensitive_writes(resolved)
        governance.update_dormancy_flags(resolved)

        previous_resolved = load_json(paths["resolved"], default={})
        previous_evidence = load_json(paths["evidence"], default={"items": []})
        previous_observations = load_json(paths["observations"], default={"items": [], "by_trait": {}})
        if governance.has_material_state(previous_resolved, previous_evidence, previous_observations):
            manifest = governance.build_rollback_manifest(
                previous_resolved,
                previous_evidence,
                previous_observations,
            )
            governance.write_rollback_manifest(paths["rollback"], manifest)

    if isinstance(resolved, dict):
        for trait_payload in resolved.values():
            if isinstance(trait_payload, dict):
                migrate_trait_record(trait_payload)
    save_json(paths["resolved"], resolved)
    save_json(paths["evidence"], evidence)
    save_json(paths["observations"], observations)


def export_bundle(user_id: str, *, include_observations: bool = True) -> Path:
    resolved, evidence, observations = read_user_state(user_id)
    meta = {
        "version": CURRENT_VERSION,
        "schema": CURRENT_SCHEMA,
        "generated_at": iso_now(),
        "user_id": user_id,
    }
    bundle: Dict[str, Any] = {
        "meta": meta,
        "resolved": resolved,
        "evidence": evidence,
    }
    if include_observations:
        bundle["observations"] = observations

    BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user_id}_{meta['generated_at'].replace(':', '-')}.json"
    path = BUNDLES_DIR / filename
    save_json(path, bundle)
    return path


def snapshot_bundle(user_id: str) -> Tuple[Path, Dict[str, Any]]:
    resolved, evidence, observations = read_user_state(user_id)
    meta = {
        "version": CURRENT_VERSION,
        "schema": CURRENT_SCHEMA,
        "generated_at": iso_now(),
        "user_id": user_id,
    }
    bundle: Dict[str, Any] = {
        "meta": meta,
        "resolved": resolved,
        "evidence": evidence,
        "observations": observations,
    }

    snapshots_dir = CHECKPOINTS_DIR / user_id
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    filename = f"bundle-{meta['generated_at'].replace(':', '-')}.json"
    path = snapshots_dir / filename
    save_json(path, bundle)
    return path, bundle


def import_bundle(bundle_path: Path, *, apply: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:
    payload = load_json(bundle_path, default={})
    if not isinstance(payload, dict):
        raise ValueError("Bundle payload must be a JSON object")

    payload = migrate(payload)
    meta = payload.setdefault("meta", {})
    if user_id:
        meta["user_id"] = user_id
    resolved = payload.get("resolved") or {}
    evidence = payload.get("evidence") or {"items": []}
    observations = payload.get("observations") or {"items": [], "by_trait": {}}

    if apply:
        apply_user = meta.get("user_id")
        if not apply_user:
            raise ValueError("Bundle meta.user_id required when apply=True")
        write_user_state(apply_user, resolved, evidence, observations)
    return payload


def restore_last_good(user_id: str) -> bool:
    paths = ensure_dirs_for_user(user_id)
    manifest = governance.read_rollback_manifest(paths["rollback"])
    if manifest is None:
        return False
    write_user_state(
        user_id,
        manifest.get("resolved", {}),
        manifest.get("evidence", {"items": []}),
        manifest.get("observations", {"items": [], "by_trait": {}}),
        enforce_governance=False,
    )
    return True


def _compute_last_used_ts(user_id: str) -> Optional[str]:
    events_dir = CHECKPOINTS_DIR / user_id / "events"
    if not events_dir.exists():
        return None
    latest_epoch = None
    for entry in events_dir.iterdir():
        if not entry.is_file():
            continue
        try:
            stat = entry.stat()
            latest_epoch = max(latest_epoch or 0.0, stat.st_mtime)
        except OSError:
            continue
    if latest_epoch is None:
        return None
    return datetime.fromtimestamp(latest_epoch, tz=timezone.utc).isoformat(timespec="milliseconds")


def touch_user_last_used(user_id: str, *, ts_iso: Optional[str] = None) -> None:
    info = load_user_info(user_id)
    info["last_used_ts"] = ts_iso or iso_now()
    save_user_info(user_id, info)


def _stat_to_epoch(stat_value: Optional[float]) -> Optional[float]:
    if stat_value is None:
        return None
    try:
        return float(stat_value)
    except (TypeError, ValueError):
        return None


def _epoch_to_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="milliseconds")


def _iso_to_epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).timestamp()
    except Exception:
        return None


def _latest_mtime(root: Path) -> Optional[float]:
    try:
        latest = root.stat().st_mtime
    except OSError:
        return None

    if not root.is_dir():
        return latest

    max_seen = latest
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                candidate = (Path(dirpath) / name).stat().st_mtime
            except OSError:
                continue
            if candidate > max_seen:
                max_seen = candidate
        for dirname in dirnames:
            child = Path(dirpath) / dirname
            try:
                candidate = child.stat().st_mtime
            except OSError:
                continue
            if candidate > max_seen:
                max_seen = candidate
    return max_seen


def list_users(query: Optional[str] = None) -> List[Dict[str, Any]]:
    query_token = query.strip().lower() if isinstance(query, str) and query.strip() else None
    candidates: Dict[str, Dict[str, Any]] = {}

    def _entry(user_id: str) -> Dict[str, Any]:
        return candidates.setdefault(user_id, {"id": user_id})

    def _skip_name(name: str) -> bool:
        if not name:
            return True
        if name.startswith("."):
            return True
        if name.startswith("__"):
            return True
        if name.startswith("_") and name.lower() in {"_stats"}:
            return True
        return False

    def _consider_label(target: Dict[str, Any], label: Optional[str]) -> None:
        if not label:
            return
        label_str = str(label).strip()
        if not label_str:
            return
        existing = target.get("label")
        if not existing or existing == target["id"]:
            target["label"] = label_str

    def _consider_created(target: Dict[str, Any], created: Optional[str]) -> None:
        if not created:
            return
        created_str = str(created).strip()
        if not created_str:
            return
        if not target.get("created_ts"):
            target["created_ts"] = created_str

    def _consider_last_used(target: Dict[str, Any], value: Optional[str]) -> None:
        if not value:
            return
        value_str = str(value).strip()
        if not value_str:
            return
        current = target.get("last_used_ts")
        if not current:
            target["last_used_ts"] = value_str
            return
        current_epoch = _iso_to_epoch(current)
        candidate_epoch = _iso_to_epoch(value_str)
        if current_epoch is None or (candidate_epoch is not None and candidate_epoch > current_epoch):
            target["last_used_ts"] = value_str

    def _consider_last_modified(target: Dict[str, Any], epoch: Optional[float]) -> None:
        if epoch is None:
            return
        existing = target.get("_last_modified_epoch")
        if existing is None or epoch > existing:
            target["_last_modified_epoch"] = epoch

    def _collect_from_users_dir() -> None:
        if not USERS_DIR.exists():
            return
        for entry in USERS_DIR.iterdir():
            if not entry.is_dir() or _skip_name(entry.name):
                continue
            user_id = entry.name
            target = _entry(user_id)

            info_path = entry / USER_INFO_FILENAME
            info = load_json(info_path, default={}) if info_path.exists() else {}
            label = info.get("label")
            created = info.get("created_ts")
            last_used = info.get("last_used_ts") or _compute_last_used_ts(user_id)

            _consider_label(target, label)
            _consider_created(target, created)
            _consider_last_used(target, last_used)

            stat = entry.stat() if entry.exists() else None
            last_modified_sources: List[Optional[float]] = []
            if stat:
                last_modified_sources.append(_stat_to_epoch(getattr(stat, "st_mtime", None)))
                last_modified_sources.append(_stat_to_epoch(getattr(stat, "st_ctime", None)))
            if info_path.exists():
                try:
                    info_stat = info_path.stat()
                except OSError:
                    info_stat = None
                if info_stat:
                    last_modified_sources.append(_stat_to_epoch(getattr(info_stat, "st_mtime", None)))
            last_modified_sources.append(_latest_mtime(entry))
            _consider_last_modified(target, max((value for value in last_modified_sources if value is not None), default=None))

    def _collect_from_storage_dir() -> None:
        if not LEGACY_STORAGE_USERS_DIR.exists():
            return
        for entry in LEGACY_STORAGE_USERS_DIR.iterdir():
            if not entry.is_dir() or _skip_name(entry.name):
                continue
            user_id = entry.name
            target = _entry(user_id)
            _consider_label(target, target.get("label") or user_id)
            stat = entry.stat() if entry.exists() else None
            if stat:
                _consider_created(target, _epoch_to_iso(stat.st_ctime))
            _consider_last_modified(target, _latest_mtime(entry))

    def _collect_from_checkpoints() -> None:
        if not CHECKPOINTS_DIR.exists():
            return
        for entry in CHECKPOINTS_DIR.iterdir():
            if not entry.is_dir() or _skip_name(entry.name):
                continue
            user_id = entry.name
            target = _entry(user_id)
            _consider_label(target, target.get("label") or user_id)
            stat = entry.stat() if entry.exists() else None
            if stat:
                _consider_created(target, _epoch_to_iso(stat.st_ctime))
            _consider_last_modified(target, _latest_mtime(entry))

    _collect_from_users_dir()
    _collect_from_storage_dir()
    _collect_from_checkpoints()

    results: List[Dict[str, Any]] = []
    for user_id, payload in candidates.items():
        label = payload.get("label") or user_id
        payload["label"] = str(label)
        if not payload.get("created_ts"):
            derived_created = _iso_to_epoch(payload.get("last_used_ts"))
            if derived_created:
                payload["created_ts"] = _epoch_to_iso(derived_created)
        last_used_epoch = _iso_to_epoch(payload.get("last_used_ts"))
        if last_used_epoch is not None:
            _consider_last_modified(payload, last_used_epoch)

        sort_epoch = payload.get("_last_modified_epoch")
        if sort_epoch is None:
            created_epoch = _iso_to_epoch(payload.get("created_ts"))
            sort_epoch = created_epoch
        payload["last_modified_ts"] = _epoch_to_iso(sort_epoch) if sort_epoch is not None else None
        payload["_sort_epoch"] = sort_epoch if sort_epoch is not None else 0.0

        if query_token:
            haystack = f"{user_id}\n{payload['label']}".lower()
            if query_token not in haystack:
                continue

        results.append(payload)

    def _sort_key(item: Dict[str, Any]) -> Tuple[float, str, str]:
        return (-float(item.get("_sort_epoch", 0.0)), item.get("label", item["id"]), item["id"])

    results.sort(key=_sort_key)

    for entry in results:
        entry.pop("_last_modified_epoch", None)
        entry.pop("_sort_epoch", None)

    return results


def _media_index_default() -> Dict[str, Any]:
    return {"items": []}


def _media_index_path(user_id: str) -> Path:
    media_dir = ensure_dirs_for_user(user_id)["media"]
    return media_dir / MEDIA_INDEX_FILENAME


def _slugify_fragment(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    ascii_only = ascii_only.lower()
    ascii_only = re.sub(r'[^a-z0-9]+', '-', ascii_only)
    ascii_only = re.sub(r'-{2,}', '-', ascii_only)
    ascii_only = ascii_only.strip('-')
    return ascii_only or 'upload'


def _sanitize_media_name(name: str) -> str:
    raw = (name or 'upload').strip()
    base, ext = os.path.splitext(raw)
    if not base:
        base = 'upload'
    ext = ext.lower()
    base_slug = _slugify_fragment(base)
    if ext and not re.match(r'^\.[a-z0-9]+$', ext):
        ext = ''
    return f"{base_slug}{ext}" if ext else base_slug


def _media_sort_key(entry: Dict[str, Any]) -> float:
    ts = entry.get("uploaded_ts")
    epoch = _iso_to_epoch(ts) if isinstance(ts, str) else None
    return -(epoch or 0.0)


def save_media_asset(
    user_id: str,
    *,
    original_name: str,
    content_type: Optional[str],
    data: bytes,
    label: Optional[str] = None,
    source_name: Optional[str] = None,
) -> Dict[str, Any]:
    media_dir = ensure_dirs_for_user(user_id)["media"]
    media_dir.mkdir(parents=True, exist_ok=True)

    media_id = uuid4().hex
    base_name = _sanitize_media_name(original_name or "upload")
    stored_name = f"{media_id}_{base_name}"
    target_path = media_dir / stored_name
    target_path.write_bytes(data)

    entry = {
        "id": media_id,
        "filename": stored_name,
        "original_name": original_name or stored_name,
        "content_type": content_type or "application/octet-stream",
        "size": len(data),
        "uploaded_ts": iso_now(),
    }
    if label:
        entry["label"] = label
    if source_name:
        entry["source_name"] = source_name

    index_path = _media_index_path(user_id)
    index_data = load_json(index_path, default=_media_index_default())
    items = index_data.get("items")
    if not isinstance(items, list):
        items = []
    items = [item for item in items if isinstance(item, dict) and item.get("id") != media_id]
    items.append(entry)
    items.sort(key=_media_sort_key)
    index_data["items"] = items
    save_json(index_path, index_data)

    return entry


def list_media_assets(user_id: str) -> List[Dict[str, Any]]:
    index_path = _media_index_path(user_id)
    if not index_path.exists():
        return []
    data = load_json(index_path, default=_media_index_default())
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    media_dir = ensure_dirs_for_user(user_id)["media"]
    existing = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        if not filename:
            continue
        path = media_dir / filename
        if path.exists():
            existing.append(entry)
    return existing


def get_media_asset(user_id: str, media_id: str) -> Optional[Tuple[Dict[str, Any], Path]]:
    entries = list_media_assets(user_id)
    for entry in entries:
        if entry.get("id") == media_id:
            filename = entry.get("filename")
            if filename:
                path = ensure_dirs_for_user(user_id)["media"] / filename
                if path.exists():
                    return entry, path
    return None


def delete_media_asset(user_id: str, media_id: str) -> bool:
    index_path = _media_index_path(user_id)
    if not index_path.exists():
        return False

    index_data = load_json(index_path, default=_media_index_default())
    items = index_data.get("items") if isinstance(index_data, dict) else []
    if not isinstance(items, list):
        items = []

    remaining: List[Dict[str, Any]] = []
    removed_entry: Optional[Dict[str, Any]] = None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") == media_id:
            removed_entry = entry
            continue
        remaining.append(entry)

    if not removed_entry:
        return False

    media_dir = ensure_dirs_for_user(user_id)["media"]
    filename = removed_entry.get("filename")
    if isinstance(filename, str) and filename:
        candidate = media_dir / filename
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass

    index_data["items"] = remaining
    save_json(index_path, index_data)
    return True


def list_snapshot_bundles(user_id: str) -> List[Dict[str, Any]]:
    snapshots_dir = CHECKPOINTS_DIR / user_id
    if not snapshots_dir.exists():
        return []

    bundles: List[Dict[str, Any]] = []
    for path in snapshots_dir.glob("*.json"):
        if not path.is_file():
            continue
        if SNAPSHOT_PATTERN not in path.name:
            continue
        try:
            payload = load_json(path, default={})
        except Exception:
            payload = {}
        meta = payload.get("meta") if isinstance(payload, dict) else {}
        stat = None
        try:
            stat = path.stat()
        except OSError:
            stat = None
        generated = None
        if isinstance(meta, dict):
            generated = meta.get("generated_at") or meta.get("created_ts")
        if not generated and stat:
            generated = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        bundles.append(
            {
                "filename": path.name,
                "path": str(path),
                "size": stat.st_size if stat else None,
                "generated_at": generated,
                "version": meta.get("version") if isinstance(meta, dict) else None,
            }
        )

    bundles.sort(key=lambda item: _iso_to_epoch(item.get("generated_at")) or 0.0, reverse=True)
    return bundles


def _render_jobs_root(user_id: str) -> Path:
    base = ensure_dirs_for_user(user_id)["udir"] / RENDERS_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _render_job_path(user_id: str, job_id: str) -> Path:
    return _render_jobs_root(user_id) / job_id / RENDER_JOB_FILENAME


def _render_job_dir(user_id: str, job_id: str) -> Path:
    return _render_jobs_root(user_id) / job_id


def create_render_job(
    user_id: str,
    *,
    media_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    job_id = uuid4().hex
    job_dir = _render_job_dir(user_id, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    now = iso_now()
    payload: Dict[str, Any] = {
        "id": job_id,
        "user_id": user_id,
        "media_id": media_id,
        "state": "queued",
        "created_at": now,
        "updated_at": now,
        "progress": 0.0,
        "params": params or {},
        "result_id": None,
        "result_filename": None,
        "result_content_type": None,
        "error": None,
    }
    save_json(_render_job_path(user_id, job_id), payload)
    return payload


def load_render_job(user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    job_path = _render_job_path(user_id, job_id)
    if not job_path.exists():
        return None
    data = load_json(job_path, default=None)
    if not isinstance(data, dict):
        return None
    data.setdefault("id", job_id)
    data.setdefault("user_id", user_id)
    data.setdefault("progress", 0.0)
    data.setdefault("state", "queued")
    data.setdefault("params", {})
    data.setdefault("created_at", iso_now())
    data.setdefault("updated_at", data.get("created_at"))
    if "result_id" not in data:
        data["result_id"] = None
    if "result_filename" not in data:
        data["result_filename"] = None
    if "result_content_type" not in data:
        data["result_content_type"] = None
    if "error" not in data:
        data["error"] = None
    return data


def save_render_job(user_id: str, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current = load_render_job(user_id, job_id)
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
    payload["updated_at"] = iso_now()
    save_json(_render_job_path(user_id, job_id), payload)
    return payload


def list_render_jobs(user_id: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    root = _render_jobs_root(user_id)
    if not root.exists():
        return []
    jobs: List[Dict[str, Any]] = []
    for job_path in root.glob("*/" + RENDER_JOB_FILENAME):
        job_dir = job_path.parent
        job_id = job_dir.name
        job = load_render_job(user_id, job_id)
        if job is None:
            continue
        jobs.append(job)
    jobs.sort(key=lambda entry: _iso_to_epoch(entry.get("created_at")) or 0.0, reverse=True)
    if isinstance(limit, int) and limit > 0:
        return jobs[:limit]
    return jobs


def render_job_result_path(user_id: str, job_id: str, *, filename: Optional[str] = None) -> Path:
    job_dir = _render_job_dir(user_id, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        return job_dir / filename
    return job_dir / "result.bin"


def _draft_dirs(user_id: str) -> List[Path]:
    candidates: List[Path] = []
    checkpoint_dir = CHECKPOINTS_DIR / user_id / DRAFTS_DIR_NAME
    user_dir = USERS_DIR / user_id / DRAFTS_DIR_NAME
    draft_chat_checkpoint = CHECKPOINTS_DIR / user_id / "draft_chat"
    draft_chat_user = USERS_DIR / user_id / "draft_chat"
    for path in (checkpoint_dir, user_dir, draft_chat_checkpoint, draft_chat_user):
        if path.exists() and path.is_dir():
            candidates.append(path)
    return candidates


def _coerce_multiline_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for part in value:
            text = _coerce_multiline_text(part)
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    if isinstance(value, dict):
        try:
            return json.dumps(value, indent=2, sort_keys=True)
        except Exception:
            return str(value)
    return str(value)


def list_draft_chat_entries(
    user_id: str,
    *,
    limit: Optional[int] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    since_epoch: Optional[float] = None
    if since:
        since_epoch = _iso_to_epoch(since)
        if since_epoch is None:
            raise ValueError("Invalid since timestamp; use ISO-8601 format (e.g. 2024-09-01T12:00:00Z)")

    entries: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def _append_entry(data: Dict[str, Any], *, path: Path) -> None:
        entry_id = str(data.get("id") or path.stem)
        if entry_id in seen:
            return

        ts_value = data.get("ts") or data.get("timestamp") or data.get("created_at")
        ts_iso: Optional[str] = None
        ts_epoch: Optional[float] = None

        if isinstance(ts_value, (int, float)):
            try:
                ts_epoch = float(ts_value)
                ts_iso = datetime.fromtimestamp(ts_epoch, tz=timezone.utc).isoformat(timespec="seconds")
            except Exception:
                ts_iso = None
                ts_epoch = None
        elif isinstance(ts_value, str) and ts_value.strip():
            ts_iso = ts_value.strip()
            ts_epoch = _iso_to_epoch(ts_iso)
            if ts_epoch is None:
                ts_iso = None

        if ts_epoch is None:
            try:
                stat = path.stat()
                ts_epoch = stat.st_mtime
                ts_iso = datetime.fromtimestamp(ts_epoch, tz=timezone.utc).isoformat(timespec="seconds")
            except OSError:
                ts_epoch = None
                ts_iso = None

        if since_epoch is not None and ts_epoch is not None and ts_epoch < since_epoch:
            return

        title = data.get("title") or data.get("summary") or data.get("label")
        content_source = data.get("content")
        if content_source is None:
            for key in ("body", "text", "notes", "draft", "markdown"):
                if key in data:
                    content_source = data[key]
                    break
        if content_source is None:
            content_source = {k: v for k, v in data.items() if k not in {"id", "title", "summary", "label", "ts", "timestamp", "created_at"}}

        content_text = _coerce_multiline_text(content_source)

        entry = {
            "id": entry_id,
            "ts": ts_iso,
            "title": title if isinstance(title, str) else None,
            "content": content_text,
            "source_path": str(path),
        }

        if ts_epoch is not None:
            entry["_epoch"] = ts_epoch

        entries.append(entry)
        seen.add(entry_id)

    for base in _draft_dirs(user_id):
        for path in sorted(base.glob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix == ".jsonl":
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        for index, raw_line in enumerate(handle):
                            line = raw_line.strip()
                            if not line:
                                continue
                            try:
                                payload = json.loads(line)
                            except Exception:
                                continue
                            if isinstance(payload, dict):
                                entry_payload = dict(payload)
                            else:
                                entry_payload = {"content": payload}
                            entry_payload.setdefault("id", f"{path.stem}-{index}")
                            _append_entry(entry_payload, path=path)
                except OSError:
                    continue
            elif suffix == ".json":
                try:
                    payload = load_json(path, default=None)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    _append_entry(payload, path=path)
                elif isinstance(payload, list):
                    for index, item in enumerate(payload):
                        if isinstance(item, dict):
                            prefixed = dict(item)
                            prefixed.setdefault("id", f"{path.stem}-{index}")
                            _append_entry(prefixed, path=path)
                else:
                    _append_entry({"content": payload}, path=path)

    entries.sort(key=lambda item: float(item.get("_epoch", 0.0)), reverse=True)

    for entry in entries:
        entry.pop("_epoch", None)

    if isinstance(limit, int) and limit > 0:
        return entries[:limit]
    return entries


def append_draft_chat_entries(user_id: str, entries: Iterable[Mapping[str, Any]]) -> int:
    ensure_dirs_for_user(user_id)
    draft_dir = USERS_DIR / user_id / "draft_chat"
    draft_dir.mkdir(parents=True, exist_ok=True)

    day_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = draft_dir / f"imports_{day_stamp}.jsonl"

    def _normalize_ts(value: Any) -> str:
        if isinstance(value, (int, float)):
            try:
                epoch = float(value)
                if epoch > 10_000_000_000:  # likely milliseconds
                    epoch /= 1000.0
                dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                return dt.isoformat(timespec="seconds")
            except Exception:
                pass
        if isinstance(value, str):
            candidate = value.strip()
            if candidate and _iso_to_epoch(candidate) is not None:
                return candidate
        return iso_now()

    count = 0
    with target.open("a", encoding="utf-8") as handle:
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            entry_id = str(entry.get("id") or uuid4().hex)
            title_raw = entry.get("title") or entry.get("summary") or entry.get("label")
            title_text = str(title_raw).strip() if isinstance(title_raw, str) and title_raw.strip() else None
            content_source: Any = entry.get("content")
            if content_source is None:
                for key in ("body", "text", "notes", "draft", "markdown"):
                    if key in entry:
                        content_source = entry[key]
                        break
            content_text = _coerce_multiline_text(content_source)
            if not content_text.strip():
                continue
            ts_value = entry.get("ts") or entry.get("timestamp") or entry.get("created_at")
            record: Dict[str, Any] = {
                "id": entry_id,
                "title": title_text,
                "content": content_text,
                "ts": _normalize_ts(ts_value),
                "imported_at": iso_now(),
            }
            source_path = entry.get("source_path")
            if isinstance(source_path, str) and source_path.strip():
                record["source_path"] = source_path.strip()

            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    return count


def clear_draft_chat_entries(user_id: str) -> int:
    removed = 0
    for base in [USERS_DIR / user_id / "draft_chat", CHECKPOINTS_DIR / user_id / "draft_chat"]:
        if not base.exists() or not base.is_dir():
            continue
        for path in base.glob("*.json*"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        try:
            base.rmdir()
        except OSError:
            pass
    return removed


def create_user(
    user_id: str,
    *,
    label: Optional[str] = None,
    seed: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    user_dir = USERS_DIR / user_id
    if user_dir.exists() and any(user_dir.iterdir()):
        return False, None

    ensure_dirs_for_user(user_id)
    created_ts = iso_now()
    info = {
        "id": user_id,
        "label": label or user_id,
        "created_ts": created_ts,
    }
    save_user_info(user_id, info)

    resolved: Dict[str, Any] = {
        "profile": {
            "label": info["label"],
            "created_ts": created_ts,
        }
    }
    if seed and isinstance(seed, dict):
        big5 = seed.get("Big5") or seed.get("big5")
        if isinstance(big5, dict):
            resolved.setdefault("traits", {})["big5"] = big5

    write_user_state(user_id, resolved, {"items": []}, {"items": [], "by_trait": {}}, enforce_governance=False)

    checkpoint_dir = CHECKPOINTS_DIR / user_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    if seed:
        save_json(
            checkpoint_dir / "seed_bundle.json",
            {
                "meta": {
                    "version": CURRENT_VERSION,
                    "created_ts": created_ts,
                    "user_id": user_id,
                },
                "seed": seed,
            },
        )

    return True, info
