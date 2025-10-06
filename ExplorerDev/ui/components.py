"""Shared UI helpers for Dev Explorer provenance tooling."""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import streamlit as st


@dataclass(frozen=True)
class BundleCandidate:
    label: str
    path: Path
    mtime: float


@dataclass(frozen=True)
class UserCandidate:
    user_id: str
    label: str
    source: str


@dataclass(frozen=True)
class UserBundleSet:
    user_id: str
    label: str
    bundles: List[BundleCandidate]
    most_recent_mtime: float


_CACHE: Dict[str, tuple[float, object]] = {}


def _from_cache(key: str, max_age: float) -> object | None:
    payload = _CACHE.get(key)
    if not payload:
        return None
    timestamp, value = payload
    if (time.time() - timestamp) > max_age:
        return None
    return value


def _store_cache(key: str, value: object) -> object:
    _CACHE[key] = (time.time(), value)
    return value


def list_recent_bundles(
    repo_root: Path,
    *,
    limit: int = 100,
    max_age: float = 6.0,
) -> List[BundleCandidate]:
    """Return bundle-style checkpoint files sorted by most recent mtime."""

    cache_key = f"bundles::{limit}"
    cached = _from_cache(cache_key, max_age)
    if cached is not None:
        return cached  # type: ignore[return-value]

    candidates: List[BundleCandidate] = []
    try:
        checkpoints_root = repo_root / "ReDNACoreDemo" / "data" / "checkpoints"
        for path in checkpoints_root.glob("*/bundle-*.json"):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            label = f"{path.parent.name}/{path.name}"
            candidates.append(BundleCandidate(label=label, path=path, mtime=stat.st_mtime))
    except Exception:
        # swallow discovery errors; downstream UI will handle empty states
        pass

    try:
        demo_root = repo_root / "ReDNACoreDemo" / "data" / "demo_users"
        for path in demo_root.glob("*.json"):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            label = f"demo_users/{path.name}"
            candidates.append(BundleCandidate(label=label, path=path, mtime=stat.st_mtime))
    except Exception:
        pass

    candidates.sort(key=lambda item: item.mtime, reverse=True)
    if limit:
        candidates = candidates[:limit]

    return _store_cache(cache_key, candidates)  # type: ignore[return-value]


def list_recent_user_bundles(
    repo_root: Path,
    *,
    per_user: int = 2,
    limit_users: int = 8,
    max_age: float = 6.0,
) -> List[UserBundleSet]:
    """Return per-user bundle snapshots grouped by most recent activity."""

    cache_key = f"user_bundles::{per_user}::{limit_users}"
    cached = _from_cache(cache_key, max_age)
    if cached is not None:
        return cached  # type: ignore[return-value]

    grouped: Dict[str, List[BundleCandidate]] = {}
    recency: Dict[str, float] = {}

    candidates = list_recent_bundles(repo_root, limit=0)  # grab all, rely on caching inside
    for candidate in candidates:
        try:
            path = candidate.path
            user_id: str
            if path.match("*/ReDNACoreDemo/data/checkpoints/*/bundle-*.json"):
                user_id = path.parent.name
            elif path.match("*/ReDNACoreDemo/data/demo_users/*.json"):
                user_id = path.stem
            else:
                # Fallback to parent folder name when structure differs
                user_id = path.stem
        except Exception:
            continue

        grouped.setdefault(user_id, []).append(candidate)
        recency[user_id] = max(recency.get(user_id, 0.0), candidate.mtime)

    user_sets: List[UserBundleSet] = []
    for user_id, bundle_list in grouped.items():
        bundle_list.sort(key=lambda item: item.mtime, reverse=True)
        limited = bundle_list[:per_user] if per_user else bundle_list
        if not limited:
            continue
        label = f"{user_id} ({len(limited)} bundle{'s' if len(limited) != 1 else ''})"
        user_sets.append(
            UserBundleSet(
                user_id=user_id,
                label=label,
                bundles=limited,
                most_recent_mtime=recency.get(user_id, limited[0].mtime),
            )
        )

    user_sets.sort(key=lambda item: item.most_recent_mtime, reverse=True)
    if limit_users:
        user_sets = user_sets[:limit_users]

    return _store_cache(cache_key, user_sets)  # type: ignore[return-value]


def list_known_users(
    repo_root: Path,
    *,
    max_age: float = 10.0,
) -> List[UserCandidate]:
    """Discover user identifiers with checkpoints or storage directories."""

    cache_key = "users"
    cached = _from_cache(cache_key, max_age)
    if cached is not None:
        return cached  # type: ignore[return-value]

    seen: Dict[str, UserCandidate] = {}

    checkpoints_root = repo_root / "ReDNACoreDemo" / "data" / "checkpoints"
    try:
        if checkpoints_root.exists():
            for path in checkpoints_root.iterdir():
                if not path.is_dir():
                    continue
                events_dir = path / "events"
                if events_dir.exists() and any(events_dir.glob("*.json")):
                    user_id = path.name
                    seen.setdefault(
                        user_id,
                        UserCandidate(user_id=user_id, label=f"{user_id} (events)", source="events"),
                    )
    except Exception:
        pass

    storage_root = repo_root / "ReDNACoreDemo" / "data" / "storage" / "users"
    try:
        if storage_root.exists():
            for path in storage_root.iterdir():
                if not path.is_dir():
                    continue
                user_id = path.name
                seen.setdefault(
                    user_id,
                    UserCandidate(user_id=user_id, label=f"{user_id} (storage)", source="storage"),
                )
    except Exception:
        pass

    ordered = sorted(seen.values(), key=lambda item: item.user_id.lower())
    return _store_cache(cache_key, ordered)  # type: ignore[return-value]


def download_buttons(
    rows: Sequence[Mapping[str, object]],
    *,
    filename_prefix: str,
    csv_columns: Sequence[str] | None,
    key: str,
) -> None:
    """Render JSON/CSV export buttons for the provided table rows."""

    safe_rows: List[Mapping[str, object]] = list(rows)
    if not safe_rows:
        st.caption("No rows to export.")
        return

    json_bytes = json.dumps(safe_rows, indent=2, default=str).encode("utf-8")
    st.download_button(
        "Export JSON",
        json_bytes,
        file_name=f"{filename_prefix}.json",
        mime="application/json",
        key=f"{key}_json",
    )

    fieldnames: List[str]
    if csv_columns:
        fieldnames = list(csv_columns)
    else:
        fieldnames = sorted({str(k) for row in safe_rows for k in row.keys()})

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in safe_rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})

    st.download_button(
        "Export CSV",
        csv_buffer.getvalue().encode("utf-8"),
        file_name=f"{filename_prefix}.csv",
        mime="text/csv",
        key=f"{key}_csv",
    )
