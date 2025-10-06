"""Persona orchestration helpers for specialized coaches."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests
import streamlit as st
import pandas as pd

from pathlib import Path

from ui.coach_api import apply_canonical_lines
from ui.persona_router import get_persona
from ui.session import UCNRR_BASE, core_get_resolved, core_get_resolved_flat, set_user_id

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

root_str = str(_PROJECT_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

for package_dir in ("PhotoRefinementCoach", "PaDNAOutboundDemo"):
    root_path = _PROJECT_ROOT / package_dir
    src_path = root_path / "src"
    for candidate in (root_path, src_path):
        if candidate.exists():
            path_str = str(candidate)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)

_photo_analyze = None
_photo_import_error: Optional[Exception] = None
_render_svg_local = None
_padna_import_error: Optional[Exception] = None

try:
    from PhotoRefinementCoach.src.importer import (
        load_and_validate as _padna_load_and_validate,
        merge_provenance as _padna_merge_provenance,
        preview_rows as _padna_preview_rows,
    )
    _padna_importer_error: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - defensive fallback
    _padna_load_and_validate = None
    _padna_merge_provenance = None
    _padna_preview_rows = None
    _padna_importer_error = exc


def _load_photo_module() -> None:
    global _photo_analyze, _photo_import_error
    if _photo_analyze or _photo_import_error:
        return
    try:
        pkg = importlib.import_module("PhotoRefinementCoach.src")
        sys.modules.setdefault("src", pkg)
        module = importlib.import_module("PhotoRefinementCoach.src.service.analyzer")
        _photo_analyze = getattr(module, "analyze_request")
    except Exception as exc:  # pragma: no cover - defensive capture
        _photo_import_error = exc


def _load_padna_module() -> None:
    global _render_svg_local, _padna_import_error
    if _render_svg_local or _padna_import_error:
        return
    try:
        module = importlib.import_module("PaDNAOutboundDemo.src.vision.renderer_v2")
        _render_svg_local = getattr(module, "render_svg")
    except Exception as exc:  # pragma: no cover - defensive capture
        _padna_import_error = exc


def _ensure_user_ready_in_services(user_id: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    try:
        resp = requests.post(
            f"{UCNRR_BASE}/users/init",
            json={"username": user_id},
            timeout=8,
        )
        body: Any
        if resp.headers.get("content-type", "").startswith("application/json"):
            body = resp.json()
        else:
            body = resp.text
        summary["ucnrr"] = {
            "ok": resp.ok,
            "status_code": resp.status_code,
            "body": body,
        }
    except Exception as exc:  # pragma: no cover - surfaced in UI diagnostics
        summary["ucnrr"] = {"ok": False, "error": str(exc)}

    try:
        resp = requests.post(
            f"{CORE_BASE}/user/{user_id}/ensure",
            timeout=8,
        )
        if resp.headers.get("content-type", "").startswith("application/json"):
            body = resp.json()
        else:
            body = resp.text
        summary["core"] = {
            "ok": resp.ok,
            "status_code": resp.status_code,
            "body": body,
        }
    except Exception as exc:  # pragma: no cover - surfaced in UI diagnostics
        summary["core"] = {"ok": False, "error": str(exc)}

    return summary


def _build_core_payload_from_import(
    payload: Dict[str, Any],
    target_user: str,
    *,
    compute_rr: bool,
    use_inbound_rr: bool,
) -> Dict[str, Any]:
    base_prov = dict(payload.get("default_provenance") or {})
    base_prov.setdefault("actor", "photo-import")
    base_prov.setdefault("source", "explorer")
    base_prov["via"] = base_prov.get("via", "json")
    base_prov.setdefault("mode", "photo-import")
    base_prov["ts"] = _iso_now()

    filenames = payload.get("image_filenames") or []
    if filenames:
        merged_images = {str(name) for name in filenames if name}
        existing_images = base_prov.get("images")
        if isinstance(existing_images, list):
            merged_images.update(str(name) for name in existing_images)
        base_prov["images"] = sorted(merged_images)

    observations = payload.get("observations") or {}
    merged_observations = _padna_merge_provenance(observations, base_prov)

    if not use_inbound_rr:
        for trait in merged_observations.values():
            trait.pop("rr", None)
            trait.pop("curiosity", None)

    body: Dict[str, Any] = {
        "user_id": target_user,
        "observations": merged_observations,
    }

    options: Dict[str, Any] = {}
    if not compute_rr:
        options["compute_rr_curiosity"] = False
    if options:
        body["options"] = options

    metadata: Dict[str, Any] = {}
    for key in ("warnings", "discarded", "unmapped"):
        value = payload.get(key)
        if value:
            metadata[key] = value
    if metadata:
        body["metadata"] = metadata

    return body


def _recent_padna_rows(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    flat = core_get_resolved_flat(user_id)
    rows = flat.get("rows", []) if isinstance(flat, dict) else []
    padna_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path_value = row.get("canonical_path") or row.get("path") or row.get("trait_path")
        if isinstance(path_value, str) and path_value.startswith("PaDNA."):
            padna_rows.append(row)
    if len(padna_rows) <= limit:
        return padna_rows
    return padna_rows[-limit:]

PHOTO_COACH_BASE = os.getenv("PHOTO_COACH_BASE", "http://127.0.0.1:8051").rstrip("/")
PADNA_RENDER_BASE = os.getenv("PADNA_RENDER_BASE", "http://127.0.0.1:8055").rstrip("/")
PHOTO_VISION_BASE_URL = os.getenv("PHOTO_VISION_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
CORE_BASE = os.getenv("CORE_BASE", os.getenv("CORE_URL", "http://127.0.0.1:8015")).rstrip("/")


def _vision_endpoint_available() -> bool:
    try:
        resp = requests.get(f"{PHOTO_VISION_BASE_URL}/api/version", timeout=2)
        return resp.status_code < 300
    except Exception:
        return False

PERSONA_SKINS = {
    "head_coach": {"label": "Head Coach", "icon": "🧠", "color": "#1F2933"},
    "photo_coach": {"label": "PhotoRefinementCoach", "icon": "📸", "color": "#0F766E"},
    "padna_coach": {"label": "PaDNA Outbound Coach", "icon": "🎨", "color": "#7C3AED"},
}

SHARED_PHOTO_BUNDLES_KEY = "photo_coach_bundles"

RECENCY_OPTIONS = [
    ("RECENT", "Recent (last 6 months)"),
    ("OLD", "Older (6–24 months)"),
    ("RETRO", "Legacy / archival"),
]

PADNA_LINE_ALIASES: Dict[str, List[str]] = {
    "PaDNA.HairDNA.Color": ["HairDNA.Color"],
    "PaDNA.HairDNA.Length": ["HairDNA.Length"],
    "PaDNA.HairDNA.Texture": ["HairDNA.Texture"],
    "PaDNA.HairDNA.Style": ["HairDNA.Style"],
    "PaDNA.HairDNA.Part": ["HairDNA.Part"],
    "PaDNA.EyeDNA.Color": ["EyeDNA.Color"],
    "PaDNA.EyeDNA.Shape": ["EyeDNA.Shape"],
    "PaDNA.EyeDNA.Lashes.Length": ["EyeDNA.Lashes.Length"],
    "PaDNA.SkinDNA.Tone": ["SkinDNA.Tone"],
    "PaDNA.SkinDNA.Undertone": ["SkinDNA.Undertone"],
    "PaDNA.FaceDNA.Shape": ["FaceDNA.Shape"],
    "PaDNA.LipDNA.Fullness": ["LipDNA.Fullness"],
    "PaDNA.DistinguishingMarksDNA.Tattoos": ["DistinguishingMarksDNA.Tattoos"],
    "PaDNA.DistinguishingMarksDNA.Tattoos.Location": ["DistinguishingMarksDNA.Tattoos.Location"],
    "PaDNA.DistinguishingMarksDNA.Piercings": ["DistinguishingMarksDNA.Piercings"],
    "PaDNA.Accessories.Earrings": ["Accessories.Earrings"],
    "PaDNA.GlassesDNA": ["GlassesDNA"],
    "PaDNA.PostureDNA": ["PostureDNA"],
    "PaDNA.ApparelDNA.Style": ["ApparelDNA.Style"],
    "PaDNA.ApparelDNA.Fit": ["ApparelDNA.Fit"],
    "PaDNA.ApparelDNA.Palette": ["ApparelDNA.Palette"],
}

PADNA_ALIAS_MAP: Dict[str, str] = {
    alias: canonical
    for canonical, aliases in PADNA_LINE_ALIASES.items()
    for alias in aliases
}


_DEFAULT_PALETTE_SPEC = {
    "palette": {
        "skin": {
            "fill": "#EBD3C5",
            "shadow": "#D1B1A0",
            "highlight": "#F6E4DA",
            "line": "#B28C7C",
            "blush": "#E6B4A0",
            "freckles": {
                "color": "#8E634F",
                "density": "none",
                "size": "small",
                "spread": "nose_cheeks",
            },
        },
        "hair": {
            "base": "#D9C896",
            "low": "#B79F5A",
            "hi": "#F1E6B5",
            "line": "#8A7344",
            "part": "center",
            "overlay": "none",
        },
        "eyes": {
            "iris": "#7A5235",
            "ring": "#3F2C1D",
            "inner": "#9B6A44",
            "pupil": "#141414",
            "sclera": "#F4F6F8",
            "size": "m",
            "shape": "almond",
        },
        "lips": {
            "fill": "#D98E8C",
            "line": "#A56564",
            "highlight": "#E7A9A7",
            "fullness": "medium",
            "style": "bow",
        },
        "brows": {
            "color": "#614731",
            "thickness": "medium",
            "arch": "soft",
        },
        "accent": {"primary": "#ADB5BD", "secondary": "#C2C8CE"},
    },
    "apparel": {"style": "classic", "fit": "regular", "palette": "neutral"},
    "posture": "upright",
    "tattoos": "none",
}


def _merge_specs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_specs(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _spec_signature(spec: Dict[str, Any]) -> str:
    try:
        return hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    except Exception:
        return str(hash(str(spec)))


def _spec_from_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = copy.deepcopy(_DEFAULT_PALETTE_SPEC)
    if not result:
        return base

    palette = result.get("palette", {}) or {}
    geometry = result.get("geometry", {}) or {}

    skin_spec = base["palette"]["skin"]
    skin_values = palette.get("skin", {})
    for key in ("fill", "shadow", "highlight", "line", "blush"):
        if skin_values.get(key):
            skin_spec[key] = skin_values[key]
    freckles_value = skin_values.get("freckles")
    if isinstance(freckles_value, dict):
        skin_spec["freckles"].update(freckles_value)
    elif isinstance(freckles_value, str):
        skin_spec["freckles"]["color"] = freckles_value
        skin_spec["freckles"]["density"] = "medium"

    hair_spec = base["palette"]["hair"]
    hair_values = palette.get("hair", {})
    for key in ("base", "low", "hi", "line"):
        if hair_values.get(key):
            hair_spec[key] = hair_values[key]
    hair_geometry = geometry.get("hair", {}) if isinstance(geometry.get("hair"), dict) else {}
    for key in ("part", "overlay"):
        if hair_geometry.get(key):
            hair_spec[key] = hair_geometry[key]

    eyes_spec = base["palette"]["eyes"]
    eye_values = palette.get("eyes", {})
    for key in ("iris", "ring", "inner", "pupil", "sclera"):
        if eye_values.get(key):
            eyes_spec[key] = eye_values[key]
    eye_geometry = geometry.get("eyes", {}) if isinstance(geometry.get("eyes"), dict) else {}
    for key in ("shape", "size"):
        if eye_geometry.get(key):
            eyes_spec[key] = eye_geometry[key]

    lips_spec = base["palette"]["lips"]
    lip_values = palette.get("lips", {})
    for key in ("fill", "line", "highlight"):
        if lip_values.get(key):
            lips_spec[key] = lip_values[key]
    lip_geometry = geometry.get("lips", {}) if isinstance(geometry.get("lips"), dict) else {}
    for key in ("fullness", "style"):
        if lip_geometry.get(key):
            lips_spec[key] = lip_geometry[key]

    brow_spec = base["palette"]["brows"]
    brow_color = palette.get("brows")
    if isinstance(brow_color, str) and brow_color:
        brow_spec["color"] = brow_color
    brow_geometry = geometry.get("brows", {}) if isinstance(geometry.get("brows"), dict) else {}
    for key in ("thickness", "arch"):
        if brow_geometry.get(key):
            brow_spec[key] = brow_geometry[key]

    accent_spec = base["palette"]["accent"]
    accent_values = palette.get("accent", {})
    for key in ("primary", "secondary"):
        if accent_values.get(key):
            accent_spec[key] = accent_values[key]

    apparel_values = result.get("apparel", {}) or {}
    base["apparel"].update(apparel_values)

    if result.get("posture"):
        base["posture"] = result["posture"]

    tattoos_value = result.get("tattoos")
    if tattoos_value is not None:
        base["tattoos"] = tattoos_value

    return base


def _prepare_bundle_for_render(bundle: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(bundle)
    renderer_cfg = dict(bundle.get("renderer", {}))
    renderer_cfg["palette_spec"] = spec
    payload["renderer"] = renderer_cfg
    return payload

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_key(prefix: str, suffix: str) -> str:
    return f"{prefix}_{suffix}"


def _ensure_state(prefix: str) -> Dict[str, Any]:
    keys_defaults = {
        "active_persona": "head_coach",
        "handoff_log": [],
        "photo_files": [],
        "photo_notes": "",
        "photo_snapshot_id": "",
        "photo_result": None,
        "photo_ingest_status": None,
        "padna_result": None,
        "padna_last_source": None,
        "padna_palette_spec": {},
        "padna_palette_spec_hash": None,
        "padna_show_traits": False,
        "photo_adapter": None,
        "import_payload": None,
        "import_report": {},
        "import_errors": [],
        "import_warnings": [],
        "import_preview": [],
        "import_filename": None,
        "import_status": None,
        "import_compute_rr": True,
        "import_use_inbound_rr": False,
        "import_large_confirmed": False,
        "import_unmapped": [],
        "import_discarded": [],
        "import_dry_run": True,
        "import_core_payload": None,
        "import_init_status": None,
        "import_digest": None,
    }
    for suffix, default in keys_defaults.items():
        st.session_state.setdefault(_state_key(prefix, suffix), default)
    return {suffix: st.session_state[_state_key(prefix, suffix)] for suffix in keys_defaults}


def _update_state(prefix: str, **updates: Any) -> None:
    for suffix, value in updates.items():
        st.session_state[_state_key(prefix, suffix)] = value


def _set_streamlit_state(key: str, value: Any) -> None:
    st.session_state[key] = value


def _persona_skin(persona_id: str) -> Dict[str, str]:
    return PERSONA_SKINS.get(persona_id, PERSONA_SKINS["head_coach"])


def _log_handoff(prefix: str, persona_id: str, trigger: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    key = _state_key(prefix, "handoff_log")
    entry = {
        "ts": _iso_now(),
        "persona": persona_id,
        "trigger": trigger,
        "meta": metadata or {},
    }
    st.session_state[key].append(entry)


def _set_active_persona(prefix: str, persona_id: str, trigger: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    _update_state(prefix, active_persona=persona_id)
    _log_handoff(prefix, persona_id, trigger, metadata)


def _append_assistant_message(prefix: str, user_id: str, content: str, *, persona_id: str, badges: Optional[List[Dict[str, str]]] = None) -> None:
    msgs_key = _state_key(prefix, "msgs")
    history = st.session_state.setdefault(msgs_key, {}).setdefault(user_id, [])
    persona_meta = get_persona(persona_id) or {}
    entry = {
        "role": "assistant",
        "content": content,
        "meta": {
            "ts": _iso_now(),
            "persona_id": persona_id,
            "persona_title": persona_meta.get("title", PERSONA_SKINS.get(persona_id, {}).get("label", persona_id)),
            "badge_details": badges or [],
        },
    }
    history.append(entry)
    st.session_state[msgs_key][user_id] = history


def _trigger_rerun() -> None:
    for name in ("rerun", "experimental_rerun"):
        fn = getattr(st, name, None)
        if callable(fn):
            fn()
            break


def _call_photo_service(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(f"{PHOTO_COACH_BASE}/analyze", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        _load_photo_module()
        if _photo_analyze:
            return _photo_analyze(payload)
        message = "Photo coach service unreachable and local fallback import failed"
        if _photo_import_error:
            message += f": {_photo_import_error}"
        raise RuntimeError(message)


def _call_padna_service(bundle: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(
            f"{PADNA_RENDER_BASE}/render",
            json={"bundle": bundle},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        _load_padna_module()
        if _render_svg_local:
            return _render_svg_local(bundle)
        message = "PaDNA renderer service unreachable and local fallback import failed"
        if _padna_import_error:
            message += f": {_padna_import_error}"
        raise RuntimeError(message)


def _dedupe_files(existing: List[Dict[str, Any]], new_files: List[Any]) -> List[Dict[str, Any]]:
    hashes = {item["hash"] for item in existing}
    for uploaded in new_files:
        try:
            raw = uploaded.getvalue()
        except AttributeError:
            raw = uploaded.read()
        if not raw:
            continue
        hsh = hashlib.sha1(raw).hexdigest()
        if hsh in hashes:
            continue
        existing.append(
            {
                "name": getattr(uploaded, "name", f"photo-{len(existing)+1}"),
                "hash": hsh,
                "bytes": raw,
                "recency": "RECENT",
            }
        )
        hashes.add(hsh)
    return existing


def _render_persona_banner(persona_id: str, *, hint: Optional[str] = None) -> None:
    skin = _persona_skin(persona_id)
    label = skin["label"]
    icon = skin["icon"]
    color = skin["color"]
    text = hint or icon + " " + label
    st.markdown(
        f"""
        <div style="background:{color};color:white;padding:0.75rem 1rem;border-radius:0.75rem;margin-bottom:1rem;">
            <strong>{icon} {label}</strong><br />{text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _photo_payload(user_id: str, snapshot_id: str, files: List[Dict[str, Any]], notes: Optional[str]) -> Dict[str, Any]:
    images: List[Dict[str, Any]] = []
    for item in files:
        images.append(
            {
                "id": item["hash"],
                "filename": item["name"],
                "b64": base64.b64encode(item["bytes"]).decode("utf-8"),
                "recency": item.get("recency", "RECENT"),
                "notes": notes,
            }
        )
    return {
        "user_id": user_id,
        "snapshot_id": snapshot_id or f"{user_id}-photo-bundle",
        "images": images,
        "notes": notes,
    }


def _render_dev_log(prefix: str) -> None:
    log = st.session_state.get(_state_key(prefix, "handoff_log"), [])
    if not log:
        st.caption("No handoffs yet.")
        return
    for entry in reversed(log[-8:]):
        st.write(f"{entry['ts']}: {entry['persona']} ← {entry['trigger']}")
        if entry.get("meta"):
            st.code(entry["meta"], language="json")


def _ingest_photo_descriptors(prefix: str, user_id: str) -> None:
    result = st.session_state.get(_state_key(prefix, "photo_result")) or {}
    bundle = result.get("bundle") or {}
    descriptors = (bundle.get("results", {}).get("descriptors") or {})
    if not descriptors:
        st.warning("No descriptors found to ingest.")
        return

    lines: List[str] = []
    for path, meta in descriptors.items():
        value = meta.get("value")
        if value is None:
            continue
        lines.append(f"{path} = {value}")
        for alias in PADNA_LINE_ALIASES.get(path, []):
            lines.append(f"{alias} = {value}")
    if not lines:
        st.warning("Descriptors are missing values; skipping ingestion.")
        return

    response = apply_canonical_lines(
        user_id,
        lines,
        persona_id="head_coach",
        actor="assistant",
        source="photo_coach",
    )
    status = {
        "ok": response.get("ok", False),
        "status": response.get("status"),
        "reason": response.get("reason"),
    }
    _update_state(prefix, photo_ingest_status=status)
    if response.get("ok"):
        st.success("Canonical lines submitted to UCN/RR.")
    else:
        st.error(f"Failed to apply canonical lines: {response.get('reason')}")


def _collect_padna_descriptors(user_id: str) -> Dict[str, Dict[str, Any]]:
    descriptors: Dict[str, Dict[str, Any]] = {}

    resolved_doc = core_get_resolved(user_id)
    resolved_map = (resolved_doc or {}).get("resolved") or {}

    for path, meta in resolved_map.items():
        if not isinstance(meta, dict):
            continue
        canonical_path: Optional[str] = None
        if isinstance(path, str) and path.startswith("PaDNA."):
            canonical_path = path
        elif isinstance(path, str) and path in PADNA_ALIAS_MAP:
            canonical_path = PADNA_ALIAS_MAP[path]
        if not canonical_path:
            continue
        value = meta.get("resolved_value", meta.get("value"))
        if value is None:
            continue
        descriptors.setdefault(
            canonical_path,
            {"value": value, "ucn": meta.get("ucn")},
        )

    if descriptors:
        return descriptors

    flat_doc = core_get_resolved_flat(user_id)
    rows = flat_doc.get("rows", [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = (
            row.get("canonical_path")
            or row.get("path")
            or row.get("trait_path")
        )
        canonical_path: Optional[str] = None
        if isinstance(path, str) and path.startswith("PaDNA."):
            canonical_path = path
        elif isinstance(path, str) and path in PADNA_ALIAS_MAP:
            canonical_path = PADNA_ALIAS_MAP[path]
        if not canonical_path:
            continue
        value = row.get("value") or row.get("resolved_value")
        if value is None:
            continue
        descriptors.setdefault(
            canonical_path,
            {"value": value, "ucn": row.get("ucn")},
        )

    return descriptors


def build_photo_body_renderer(page_prefix: str) -> Callable[[str], None]:
    def _render(active_user: str) -> None:
        state = _ensure_state(page_prefix)
        dev_mode = st.session_state.get(_state_key(page_prefix, "dev"), False)

        if not active_user:
            st.info("Select an active user to begin photo refinement.")
            return

        files_key = _state_key(page_prefix, "photo_files")
        current_files: List[Dict[str, Any]] = st.session_state[files_key]

        persona = st.session_state[_state_key(page_prefix, "active_persona")]

        st.subheader("Import JSON")
        if _padna_load_and_validate is None or _padna_merge_provenance is None:
            if _padna_importer_error:
                st.warning(
                    "PaDNA importer unavailable — install PhotoRefinementCoach dependencies or check logs."
                )
            else:
                st.info("Importer helpers not available in this build.")
        else:
            import_upload = st.file_uploader(
                "Upload PaDNA JSON",
                type=["json"],
                accept_multiple_files=False,
                key=f"{page_prefix}_padna_import_json",
                help="Provide PaDNA observation bundles produced offline to ingest directly into Core.",
            )

            if import_upload is not None:
                data = import_upload.getvalue()
                digest = hashlib.sha1(data).hexdigest()
                if digest != state.get("import_digest"):
                    normalized, report, errors = _padna_load_and_validate(data)
                    warnings = []
                    preview: List[Dict[str, Any]] = []
                    if isinstance(normalized, dict):
                        warnings = normalized.get("warnings", []) or []
                        observations = normalized.get("observations") or {}
                        default_prov = normalized.get("default_provenance") or {}
                        if observations:
                            merged_preview = _padna_merge_provenance(observations, default_prov)
                            preview = _padna_preview_rows(merged_preview)
                    else:
                        normalized = {}

                    needs_confirmation = bool(
                        isinstance(normalized, dict) and normalized.get("needs_large_confirmation")
                    )

                    _update_state(
                        page_prefix,
                        import_digest=digest,
                        import_filename=import_upload.name,
                        import_payload=normalized if not errors else None,
                        import_report=report,
                        import_errors=errors,
                        import_warnings=warnings,
                        import_preview=preview,
                        import_status=None,
                        import_large_confirmed=not needs_confirmation,
                        import_compute_rr=True,
                        import_use_inbound_rr=False,
                        import_unmapped=(normalized.get("unmapped") if isinstance(normalized, dict) else []),
                        import_discarded=(normalized.get("discarded") if isinstance(normalized, dict) else []),
                        import_dry_run=True,
                        import_core_payload=None,
                        import_init_status=None,
                    )
                    state.update(
                        {
                            "import_digest": digest,
                            "import_filename": import_upload.name,
                            "import_payload": normalized if not errors else None,
                            "import_report": report,
                            "import_errors": errors,
                            "import_warnings": warnings,
                            "import_preview": preview,
                            "import_status": None,
                            "import_large_confirmed": not needs_confirmation,
                            "import_compute_rr": True,
                            "import_use_inbound_rr": False,
                            "import_unmapped": normalized.get("unmapped") if isinstance(normalized, dict) else [],
                            "import_discarded": normalized.get("discarded") if isinstance(normalized, dict) else [],
                            "import_dry_run": True,
                            "import_core_payload": None,
                            "import_init_status": None,
                        }
                    )

                    st.session_state[f"{page_prefix}_import_compute_rr_widget"] = True
                    st.session_state[f"{page_prefix}_import_use_inbound_rr_widget"] = False
                    st.session_state[f"{page_prefix}_import_large_confirm_widget"] = not needs_confirmation

                    payload_user = normalized.get("user_id") if isinstance(normalized, dict) else None
                    if payload_user and payload_user != active_user and not active_user:
                        set_user_id(payload_user)
                        _trigger_rerun()
                        return

            if state.get("import_filename"):
                trait_count = None
                payload = state.get("import_payload")
                report = state.get("import_report") or {}
                if isinstance(payload, dict):
                    trait_count = payload.get("trait_count")
                elif isinstance(report, dict):
                    trait_count = (report.get("observations") or {}).get("count")
                suffix = f" — {trait_count} trait(s) detected" if trait_count else ""
                st.caption(f"Loaded {state['import_filename']}{suffix}")

            report_block = state.get("import_report") or {}

            def _status_line(label: str, block: Dict[str, Any]) -> None:
                if not block:
                    return
                ok = bool(block.get("ok"))
                icon = "✅" if ok else "❌"
                message = block.get("message") or ""
                st.markdown(f"{icon} **{label}:** {message}")

            if isinstance(report_block, dict) and report_block:
                _status_line("User", report_block.get("user_id", {}))
                _status_line("Observations", report_block.get("observations", {}))
                _status_line("Provenance", report_block.get("provenance", {}))
                _status_line("Images", report_block.get("images", {}))
                _status_line("Volume", report_block.get("volume", {}))

            for err in state.get("import_errors", []) or []:
                st.error(err)

            for warn in state.get("import_warnings", []) or []:
                st.warning(warn)

            payload = state.get("import_payload") if isinstance(state.get("import_payload"), dict) else None
            requires_confirmation = bool(payload and payload.get("needs_large_confirmation"))
            if requires_confirmation:
                st.session_state.setdefault(
                    f"{page_prefix}_import_large_confirm_widget", state.get("import_large_confirmed", False)
                )
                confirmed = st.checkbox(
                    f"Confirm import of {payload.get('trait_count', 0)} traits",
                    key=f"{page_prefix}_import_large_confirm_widget",
                )
                _update_state(page_prefix, import_large_confirmed=bool(confirmed))
                state["import_large_confirmed"] = bool(confirmed)
            else:
                _update_state(page_prefix, import_large_confirmed=True)
                state["import_large_confirmed"] = True

            st.session_state.setdefault(
                f"{page_prefix}_import_compute_rr_widget", state.get("import_compute_rr", True)
            )
            compute_rr_val = st.checkbox(
                "Compute RR/Curiosity in Core",
                key=f"{page_prefix}_import_compute_rr_widget",
                help="When enabled, Core recomputes RR/Curiosity after ingest.",
            )
            _update_state(page_prefix, import_compute_rr=bool(compute_rr_val))
            state["import_compute_rr"] = bool(compute_rr_val)

            inbound_rr_available = any(
                isinstance(row, dict)
                and (row.get("rr") is not None or row.get("curiosity") is not None)
                for row in state.get("import_preview", [])
            )
            st.session_state.setdefault(
                f"{page_prefix}_import_use_inbound_rr_widget",
                state.get("import_use_inbound_rr", False) and inbound_rr_available,
            )
            use_inbound_rr_val = st.checkbox(
                "Use inbound RR/Curiosity values",
                key=f"{page_prefix}_import_use_inbound_rr_widget",
                help="Preserve RR/Curiosity supplied in the JSON instead of recomputing in Core.",
                disabled=not inbound_rr_available,
            )
            use_inbound_rr = bool(use_inbound_rr_val) and inbound_rr_available
            _update_state(page_prefix, import_use_inbound_rr=use_inbound_rr)
            state["import_use_inbound_rr"] = use_inbound_rr

            if payload and payload.get("user_id") and payload.get("user_id") != active_user:
                st.warning(
                    "Bundle user_id differs from the active user; ingest will use the active user instead."
                )

            preview_rows_data = state.get("import_preview", []) or []
            if preview_rows_data:
                df = pd.DataFrame(preview_rows_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

            target_user = active_user or (payload.get("user_id") if payload else None)

            dry_run_key = f"{page_prefix}_import_dry_run_widget"
            st.session_state.setdefault(dry_run_key, state.get("import_dry_run", True))
            dry_run_val = st.checkbox(
                "Dry run (review payload without posting)",
                key=dry_run_key,
                help="When enabled, the normalized payload is shown but not sent to Core.",
            )
            dry_run = bool(dry_run_val)
            _update_state(page_prefix, import_dry_run=dry_run)
            state["import_dry_run"] = dry_run

            core_payload: Optional[Dict[str, Any]] = None
            if payload and target_user:
                core_payload = _build_core_payload_from_import(
                    payload,
                    target_user,
                    compute_rr=state.get("import_compute_rr", True),
                    use_inbound_rr=state.get("import_use_inbound_rr", False),
                )
            _update_state(page_prefix, import_core_payload=core_payload)
            state["import_core_payload"] = core_payload
            if core_payload is None:
                _update_state(page_prefix, import_init_status=None)
                state["import_init_status"] = None

            if core_payload:
                with st.expander("Core payload preview", expanded=dry_run):
                    st.json(core_payload, expanded=False)
            elif payload:
                st.info("Provide an active user to build the Core ingest payload.")

            unmapped_rows = state.get("import_unmapped") or []
            if unmapped_rows:
                with st.expander("Unmapped PaDNA keys", expanded=False):
                    copy_store_key = f"{page_prefix}_copied_key"
                    for idx, entry in enumerate(unmapped_rows):
                        path_value = entry.get("path") or entry.get("canonical_path") or ""
                        reason_value = entry.get("reason") or ""
                        cols = st.columns([5, 1])
                        with cols[0]:
                            st.code(path_value or "(missing path)")
                            if reason_value:
                                st.caption(reason_value)
                        with cols[1]:
                            st.button(
                                "Copy key",
                                key=f"{page_prefix}_copy_btn_{idx}",
                                on_click=_set_streamlit_state,
                                args=(copy_store_key, path_value),
                                use_container_width=True,
                            )
                    copied_value = st.session_state.get(copy_store_key)
                    if copied_value:
                        st.caption(f"Stored `{copied_value}` in the session clipboard — paste where needed.")
                    st.caption("Add these keys to the mapping registry if they should resolve to PaDNA.* traits.")

            discarded_rows = state.get("import_discarded") or []
            if discarded_rows:
                with st.expander("Discarded observations", expanded=False):
                    df_discarded = pd.DataFrame(discarded_rows)
                    st.dataframe(df_discarded, use_container_width=True, hide_index=True)

            if dry_run:
                st.info("Dry run enabled — uncheck to post the payload to Core.")

            ingest_ready = bool(core_payload and (payload and payload.get("observations")))
            if requires_confirmation:
                ingest_ready = ingest_ready and state.get("import_large_confirmed", False)
            if payload is None or state.get("import_errors"):
                ingest_ready = False

            post_disabled = (not ingest_ready) or dry_run or core_payload is None

            st.caption(f"Core ingest endpoint: `{CORE_BASE}/ingest_from_ucnrr`")

            if st.button(
                "Post to Core",
                type="primary",
                use_container_width=True,
                disabled=post_disabled,
                key=f"{page_prefix}_import_ingest",
            ):
                if not payload or not core_payload or not target_user:
                    st.error("No validated payload available for ingest.")
                else:
                    try:
                        init_summary = _ensure_user_ready_in_services(target_user)
                        _update_state(page_prefix, import_init_status=init_summary)
                        state["import_init_status"] = init_summary

                        with st.spinner("Ingesting PaDNA traits into Core…"):
                            resp = requests.post(
                                f"{CORE_BASE}/ingest_from_ucnrr",
                                json=core_payload,
                                timeout=30,
                            )

                        if resp.headers.get("content-type", "").startswith("application/json"):
                            resp_body: Any = resp.json()
                        else:
                            resp_body = resp.text

                        status = {
                            "ok": resp.ok,
                            "status_code": resp.status_code,
                            "body": resp_body,
                            "user_id": target_user,
                        }
                        _update_state(page_prefix, import_status=status)
                        state["import_status"] = status
                    except Exception as exc:  # pragma: no cover - surfaced to user
                        status = {"ok": False, "error": str(exc)}
                        _update_state(page_prefix, import_status=status)
                        state["import_status"] = status

            status_block = state.get("import_status") or {}
            if status_block:
                if status_block.get("ok"):
                    body = status_block.get("body") if isinstance(status_block.get("body"), dict) else {}
                    changed = len(body.get("changed", [])) if isinstance(body, dict) else "?"
                    st.success(f"Core ingest succeeded — {changed} key(s) changed.")
                else:
                    detail = status_block.get("error") or status_block.get("status_code") or "unknown error"
                    st.error(f"Core ingest failed: {detail}")
                if isinstance(status_block.get("body"), (dict, list)):
                    st.json(status_block.get("body"), expanded=False)
                elif status_block.get("body"):
                    st.code(str(status_block.get("body")))

            init_block = state.get("import_init_status") or {}
            if init_block:
                with st.expander("Initialization results", expanded=False):
                    st.json(init_block, expanded=False)

            if active_user:
                recent_rows = _recent_padna_rows(active_user)
                with st.expander("Recent PaDNA resolved traits", expanded=False):
                    if recent_rows:
                        df_recent = pd.DataFrame(recent_rows)
                        st.dataframe(df_recent, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No PaDNA traits resolved yet.")

        uploader = st.file_uploader(
            "Drop 1..N photos for refinement",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"{page_prefix}_photo_upload",
        )
        if uploader:
            current_files = _dedupe_files(current_files, uploader)
            st.session_state[files_key] = current_files
            if persona != "photo_coach" and current_files:
                _set_active_persona(page_prefix, "photo_coach", "photo_upload", {"count": len(current_files)})
                _trigger_rerun()
                return

        if persona != "photo_coach":
            st.caption("Head Coach will offer a handoff once photos are uploaded.")
            if dev_mode:
                with st.expander("Handoff log", expanded=False):
                    _render_dev_log(page_prefix)
            return

        # Persona view
        _render_persona_banner(
            "photo_coach",
            hint="Analyzing photos (traits flow back through Head Coach ingest)",
        )

        col_left, col_right = st.columns([0.55, 0.45])
        with col_left:
            adapter_state = st.session_state.get(_state_key(page_prefix, "photo_adapter"))
            if adapter_state is None:
                adapter_state = "llama3-vision" if _vision_endpoint_available() else "mock-vision"
                _update_state(page_prefix, photo_adapter=adapter_state)

            adapter_options = ["mock-vision", "llama3-vision"]
            adapter_choice = st.selectbox(
                "Vision adapter",
                options=adapter_options,
                index=adapter_options.index(adapter_state) if adapter_state in adapter_options else 0,
                help="Switch to llama3-vision when the vision service is running.",
            )
            if adapter_choice != adapter_state:
                _update_state(page_prefix, photo_adapter=adapter_choice)

            snapshot_id = st.text_input(
                "Snapshot ID",
                value=st.session_state.get(_state_key(page_prefix, "photo_snapshot_id")) or f"{active_user}-photo-bundle",
                help="Used for provenance when Explorer ingests the bundle.",
            )
            notes = st.text_area(
                "Session notes",
                value=st.session_state.get(_state_key(page_prefix, "photo_notes")),
                placeholder="e.g., Lighting mix: studio + outdoor",
            )
            _update_state(page_prefix, photo_snapshot_id=snapshot_id, photo_notes=notes)

            if not current_files:
                st.warning("Add at least one photo to continue.")
            else:
                for idx, file_meta in enumerate(current_files):
                    cols = st.columns([0.6, 0.4])
                    with cols[0]:
                        st.image(
                            file_meta["bytes"],
                            caption=file_meta["name"],
                            use_container_width=True,
                        )
                    with cols[1]:
                        recency = st.selectbox(
                            "Recency",
                            options=[opt[0] for opt in RECENCY_OPTIONS],
                            format_func=lambda val: dict(RECENCY_OPTIONS)[val],
                            index=[opt[0] for opt in RECENCY_OPTIONS].index(file_meta.get("recency", "RECENT")),
                            key=f"{page_prefix}_recency_{file_meta['hash']}",
                        )
                        file_meta["recency"] = recency
                        if st.button("Remove", key=f"{page_prefix}_remove_{idx}"):
                            current_files.pop(idx)
                            st.session_state[files_key] = current_files
                            _trigger_rerun()
                            return

                if st.button("Run refinement", type="primary"):
                    payload = _photo_payload(active_user, snapshot_id, current_files, notes)
                    payload["model"] = st.session_state.get(_state_key(page_prefix, "photo_adapter"))
                    try:
                        result = _call_photo_service(payload)
                        st.session_state[_state_key(page_prefix, "photo_result")] = result
                        st.session_state.setdefault(SHARED_PHOTO_BUNDLES_KEY, {})[active_user] = result.get("bundle")
                        _set_active_persona(page_prefix, "photo_coach", "analysis_completed", {"descriptors": len(result.get("aggregate", {}).get("descriptors", {}))})
                        st.success("Refinement completed.")
                    except Exception as exc:  # pragma: no cover - service fallback
                        st.error(f"Photo refinement failed: {exc}")

        with col_right:
            result = st.session_state.get(_state_key(page_prefix, "photo_result")) or {}
            if not result:
                st.info("Run refinement to see descriptors and bundle output.")
            else:
                metrics = result.get("metrics", {})
                deltas = result.get("deltas", {})
                bundle = result.get("bundle", {})

                st.metric("Overall UCN", f"{metrics.get('ucn_overall', 0.0):.1f}")
                if metrics.get("ucn_delta_overall") is not None:
                    st.metric("Δ UCN", f"{metrics['ucn_delta_overall']:+.1f}")
                st.metric("Photos", metrics.get("photo_count", 0))

                descriptors = result.get("aggregate", {}).get("descriptors", {})
                if descriptors:
                    fallback_meta = descriptors.get("PaDNA.Debug.ModelFallback")
                    if fallback_meta:
                        err_detail = fallback_meta.get("details", {}).get("error")
                        st.error(
                            "Vision adapter failed – "
                            + (err_detail or fallback_meta.get("value", "see logs"))
                        )
                    display_pairs = [
                        (path, meta)
                        for path, meta in descriptors.items()
                        if path != "PaDNA.Debug.ModelFallback"
                    ]
                    if display_pairs:
                        st.markdown("**Top descriptors**")
                        for idx, (path, meta) in enumerate(display_pairs[:8]):
                            st.write(
                                f"{idx+1}. {path} → {meta.get('value')} (UCN {meta.get('ucn'):.1f})"
                            )
                if bundle:
                    st.download_button(
                        "Download bundle",
                        data=json.dumps(bundle, indent=2).encode("utf-8"),
                        file_name="explorer_bundle.json",
                        mime="application/json",
                    )

                if st.button("Ingest descriptors to UCN/RR"):
                    _ingest_photo_descriptors(page_prefix, active_user)

                ingest_status = st.session_state.get(_state_key(page_prefix, "photo_ingest_status"))
                if ingest_status:
                    tone = st.success if ingest_status.get("ok") else st.error
                    tone(f"Ingest status: {ingest_status}")

        return_col = st.columns([0.7, 0.3])[1]
        with return_col:
            if st.button("Return to Head Coach", type="secondary"):
                result = st.session_state.get(_state_key(page_prefix, "photo_result")) or {}
                deltas = result.get("deltas", {})
                bundle = result.get("bundle")
                summary_lines: List[str] = []
                overall = deltas.get("overall_ucn", {})
                if overall.get("delta") is not None:
                    summary_lines.append(
                        f"Overall UCN changed by {overall['delta']:+.1f} to {overall['current']:.1f}."
                    )
                top_traits = deltas.get("per_trait", [])[:3]
                for item in top_traits:
                    if item.get("value") is None:
                        continue
                    summary_lines.append(
                        f"{item['path']} → {item['value']} ({item.get('ucn_delta', 0.0):+0.1f} UCN)."
                    )
                recap = "\n".join(summary_lines) or "Refinement complete; no descriptor deltas detected."
                _append_assistant_message(
                    page_prefix,
                    active_user,
                    f"Photo coach recap:\n{recap}",
                    persona_id="head_coach",
                    badges=[{"text": "Photo coach recap", "tone": "info"}],
                )
                if bundle:
                    st.session_state.setdefault(SHARED_PHOTO_BUNDLES_KEY, {})[active_user] = bundle
                _set_active_persona(page_prefix, "head_coach", "return", {"recap": True})
                _trigger_rerun()

        if dev_mode:
            with st.expander("Handoff log", expanded=False):
                _render_dev_log(page_prefix)

    return _render


def build_padna_body_renderer(page_prefix: str) -> Callable[[str], None]:
    def _render(active_user: str) -> None:
        state = _ensure_state(page_prefix)
        dev_mode = st.session_state.get(_state_key(page_prefix, "dev"), False)

        if not active_user:
            st.info("Select an active user to render the PaDNA avatar.")
            return

        persona = st.session_state[_state_key(page_prefix, "active_persona")]
        if persona != "padna_coach":
            st.button(
                "Render my avatar",
                key=f"{page_prefix}_start",
                on_click=lambda: _set_active_persona(page_prefix, "padna_coach", "cta_click", None),
                use_container_width=True,
            )
            if dev_mode:
                with st.expander("Handoff log", expanded=False):
                    _render_dev_log(page_prefix)
            return

        _render_persona_banner("padna_coach", hint="Rendering outbound avatar from PaDNA descriptors")

        result: Optional[Dict[str, Any]] = state["padna_result"]
        stored_spec: Dict[str, Any] = copy.deepcopy(state["padna_palette_spec"]) if state["padna_palette_spec"] else {}
        stored_hash: Optional[str] = state["padna_palette_spec_hash"]
        show_traits: bool = state["padna_show_traits"]

        descriptors = _collect_padna_descriptors(active_user)
        descriptor_count = len(descriptors or {})
        bundle: Dict[str, Any] = {"results": {"descriptors": descriptors or {}}}

        base_spec = _spec_from_result(result) if result else copy.deepcopy(_DEFAULT_PALETTE_SPEC)
        palette_spec = _merge_specs(base_spec, stored_spec) if stored_spec else base_spec

        palette = palette_spec.setdefault("palette", {})
        skin_spec = palette.setdefault("skin", {})
        freckles_entry = skin_spec.get("freckles")
        if not isinstance(freckles_entry, dict):
            skin_spec["freckles"] = {
                "color": freckles_entry if isinstance(freckles_entry, str) and freckles_entry else skin_spec.get("line", "#8E634F"),
                "density": "medium",
                "size": "small",
                "spread": "nose_cheeks",
            }
        hair_spec = palette.setdefault("hair", {})
        hair_spec.setdefault("part", "center")
        hair_spec.setdefault("overlay", "none")
        eyes_spec = palette.setdefault("eyes", {})
        eyes_spec.setdefault("shape", "almond")
        eyes_spec.setdefault("size", "m")
        lips_spec = palette.setdefault("lips", {})
        lips_spec.setdefault("fullness", "medium")
        lips_spec.setdefault("style", "bow")
        brows_spec = palette.setdefault("brows", {})
        brows_spec.setdefault("color", "#614731")
        brows_spec.setdefault("thickness", "medium")
        brows_spec.setdefault("arch", "soft")
        palette.setdefault("accent", {}).setdefault("primary", "#ADB5BD")
        palette["accent"].setdefault("secondary", "#C2C8CE")

        apparel_spec = palette_spec.setdefault("apparel", {})
        apparel_spec.setdefault("style", "classic")
        apparel_spec.setdefault("fit", "regular")
        apparel_spec.setdefault("palette", "neutral")
        palette_spec.setdefault("posture", "upright")
        palette_spec.setdefault("tattoos", "none")

        col_left, col_right = st.columns([0.52, 0.48])

        with col_right:
            st.subheader("Palette & Posture Editor")
            skin_tab, hair_tab, eyes_tab, lips_tab, brows_tab, apparel_tab, posture_tab = st.tabs(
                ["Skin", "Hair", "Eyes", "Lips", "Brows", "Apparel & Accent", "Posture"]
            )

            with skin_tab:
                skin_cols = st.columns(3)
                skin_spec["fill"] = skin_cols[0].color_picker(
                    "Fill",
                    skin_spec.get("fill", "#EBD3C5"),
                    key=f"{page_prefix}_skin_fill",
                ).upper()
                skin_spec["shadow"] = skin_cols[1].color_picker(
                    "Shadow",
                    skin_spec.get("shadow", "#D1B1A0"),
                    key=f"{page_prefix}_skin_shadow",
                ).upper()
                skin_spec["highlight"] = skin_cols[2].color_picker(
                    "Highlight",
                    skin_spec.get("highlight", "#F6E4DA"),
                    key=f"{page_prefix}_skin_highlight",
                ).upper()
                skin_cols_line = st.columns(2)
                skin_spec["line"] = skin_cols_line[0].color_picker(
                    "Line",
                    skin_spec.get("line", "#B28C7C"),
                    key=f"{page_prefix}_skin_line",
                ).upper()
                skin_spec["blush"] = skin_cols_line[1].color_picker(
                    "Blush",
                    skin_spec.get("blush", "#E6B4A0"),
                    key=f"{page_prefix}_skin_blush",
                ).upper()

                freckles_spec = skin_spec.get("freckles", {})
                freckles_spec["color"] = st.color_picker(
                    "Freckles color",
                    freckles_spec.get("color", "#8E634F"),
                    key=f"{page_prefix}_freckles_color",
                ).upper()
                density_options = {"None": "none", "Light": "light", "Medium": "medium", "Dense": "dense"}
                density_values = list(density_options.values())
                density_current = freckles_spec.get("density", "none")
                density_index = density_values.index(density_current) if density_current in density_values else 0
                density_choice = st.selectbox(
                    "Freckles density",
                    list(density_options.keys()),
                    index=density_index,
                    key=f"{page_prefix}_freckles_density",
                )
                freckles_spec["density"] = density_options[density_choice]

                size_options = {"Small": "small", "Medium": "medium", "Large": "large"}
                size_values = list(size_options.values())
                size_current = freckles_spec.get("size", "small")
                size_index = size_values.index(size_current) if size_current in size_values else 0
                size_choice = st.selectbox(
                    "Freckles size",
                    list(size_options.keys()),
                    index=size_index,
                    key=f"{page_prefix}_freckles_size",
                )
                freckles_spec["size"] = size_options[size_choice]

                spread_options = {"Nose & cheeks": "nose_cheeks", "Full": "full", "Cheeks only": "cheeks"}
                spread_values = list(spread_options.values())
                spread_current = freckles_spec.get("spread", "nose_cheeks")
                spread_index = spread_values.index(spread_current) if spread_current in spread_values else 0
                spread_choice = st.selectbox(
                    "Freckles spread",
                    list(spread_options.keys()),
                    index=spread_index,
                    key=f"{page_prefix}_freckles_spread",
                )
                freckles_spec["spread"] = spread_options[spread_choice]

            with hair_tab:
                hair_cols = st.columns(2)
                hair_spec["base"] = hair_cols[0].color_picker(
                    "Base",
                    hair_spec.get("base", "#D9C896"),
                    key=f"{page_prefix}_hair_base",
                ).upper()
                hair_spec["low"] = hair_cols[1].color_picker(
                    "Low",
                    hair_spec.get("low", "#B79F5A"),
                    key=f"{page_prefix}_hair_low",
                ).upper()
                hair_cols_hi = st.columns(2)
                hair_spec["hi"] = hair_cols_hi[0].color_picker(
                    "Highlight",
                    hair_spec.get("hi", "#F1E6B5"),
                    key=f"{page_prefix}_hair_hi",
                ).upper()
                hair_spec["line"] = hair_cols_hi[1].color_picker(
                    "Line",
                    hair_spec.get("line", "#8A7344"),
                    key=f"{page_prefix}_hair_line",
                ).upper()

                part_options = {"Left": "left", "Center": "center", "Right": "right"}
                part_values = list(part_options.values())
                part_current = hair_spec.get("part", "center")
                part_index = part_values.index(part_current) if part_current in part_values else 1
                part_choice = st.selectbox(
                    "Part",
                    list(part_options.keys()),
                    index=part_index,
                    key=f"{page_prefix}_hair_part",
                )
                hair_spec["part"] = part_options[part_choice]

                overlay_options = {"None": "none", "Side sweep": "side_sweep"}
                overlay_values = list(overlay_options.values())
                overlay_current = hair_spec.get("overlay", "none")
                overlay_index = overlay_values.index(overlay_current) if overlay_current in overlay_values else 0
                overlay_choice = st.selectbox(
                    "Overlay",
                    list(overlay_options.keys()),
                    index=overlay_index,
                    key=f"{page_prefix}_hair_overlay",
                )
                hair_spec["overlay"] = overlay_options[overlay_choice]

            with eyes_tab:
                eyes_cols = st.columns(3)
                eyes_spec["iris"] = eyes_cols[0].color_picker(
                    "Iris",
                    eyes_spec.get("iris", "#7A5235"),
                    key=f"{page_prefix}_eyes_iris",
                ).upper()
                eyes_spec["ring"] = eyes_cols[1].color_picker(
                    "Ring",
                    eyes_spec.get("ring", "#3F2C1D"),
                    key=f"{page_prefix}_eyes_ring",
                ).upper()
                eyes_spec["inner"] = eyes_cols[2].color_picker(
                    "Inner",
                    eyes_spec.get("inner", "#9B6A44"),
                    key=f"{page_prefix}_eyes_inner",
                ).upper()
                eyes_cols_more = st.columns(2)
                eyes_spec["pupil"] = eyes_cols_more[0].color_picker(
                    "Pupil",
                    eyes_spec.get("pupil", "#141414"),
                    key=f"{page_prefix}_eyes_pupil",
                ).upper()
                eyes_spec["sclera"] = eyes_cols_more[1].color_picker(
                    "Sclera",
                    eyes_spec.get("sclera", "#F4F6F8"),
                    key=f"{page_prefix}_eyes_sclera",
                ).upper()

                eye_shape_options = {"Almond": "almond", "Round": "round"}
                eye_shape_values = list(eye_shape_options.values())
                shape_current = eyes_spec.get("shape", "almond")
                shape_index = eye_shape_values.index(shape_current) if shape_current in eye_shape_values else 0
                shape_choice = st.selectbox(
                    "Shape",
                    list(eye_shape_options.keys()),
                    index=shape_index,
                    key=f"{page_prefix}_eyes_shape",
                )
                eyes_spec["shape"] = eye_shape_options[shape_choice]

                eye_size_options = {"Small": "s", "Medium": "m", "Large": "l"}
                eye_size_values = list(eye_size_options.values())
                size_current = eyes_spec.get("size", "m")
                size_index = eye_size_values.index(size_current) if size_current in eye_size_values else 1
                size_choice = st.selectbox(
                    "Size",
                    list(eye_size_options.keys()),
                    index=size_index,
                    key=f"{page_prefix}_eyes_size",
                )
                eyes_spec["size"] = eye_size_options[size_choice]

            with lips_tab:
                lips_cols = st.columns(3)
                lips_spec["fill"] = lips_cols[0].color_picker(
                    "Fill",
                    lips_spec.get("fill", "#D98E8C"),
                    key=f"{page_prefix}_lips_fill",
                ).upper()
                lips_spec["line"] = lips_cols[1].color_picker(
                    "Line",
                    lips_spec.get("line", "#A56564"),
                    key=f"{page_prefix}_lips_line",
                ).upper()
                lips_spec["highlight"] = lips_cols[2].color_picker(
                    "Highlight",
                    lips_spec.get("highlight", "#E7A9A7"),
                    key=f"{page_prefix}_lips_highlight",
                ).upper()

                lip_fullness_options = {"Thin": "thin", "Medium": "medium", "Full": "full"}
                lip_fullness_values = list(lip_fullness_options.values())
                fullness_current = lips_spec.get("fullness", "medium")
                fullness_index = lip_fullness_values.index(fullness_current) if fullness_current in lip_fullness_values else 1
                fullness_choice = st.selectbox(
                    "Fullness",
                    list(lip_fullness_options.keys()),
                    index=fullness_index,
                    key=f"{page_prefix}_lips_fullness",
                )
                lips_spec["fullness"] = lip_fullness_options[fullness_choice]

                lip_style_options = {"Cupid bow": "bow", "Straight": "straight"}
                lip_style_values = list(lip_style_options.values())
                style_current = lips_spec.get("style", "bow")
                style_index = lip_style_values.index(style_current) if style_current in lip_style_values else 0
                style_choice = st.selectbox(
                    "Style",
                    list(lip_style_options.keys()),
                    index=style_index,
                    key=f"{page_prefix}_lips_style",
                )
                lips_spec["style"] = lip_style_options[style_choice]

            with brows_tab:
                brow_cols = st.columns(2)
                brows_spec["color"] = brow_cols[0].color_picker(
                    "Color",
                    brows_spec.get("color", "#614731"),
                    key=f"{page_prefix}_brow_color",
                ).upper()

                brow_thickness_options = {"Thin": "thin", "Medium": "medium", "Thick": "thick"}
                thickness_values = list(brow_thickness_options.values())
                thickness_current = brows_spec.get("thickness", "medium")
                thickness_index = thickness_values.index(thickness_current) if thickness_current in thickness_values else 1
                thickness_choice = st.selectbox(
                    "Thickness",
                    list(brow_thickness_options.keys()),
                    index=thickness_index,
                    key=f"{page_prefix}_brow_thickness",
                )
                brows_spec["thickness"] = brow_thickness_options[thickness_choice]

                brow_arch_options = {"Flat": "flat", "Soft": "soft", "High": "high"}
                arch_values = list(brow_arch_options.values())
                arch_current = brows_spec.get("arch", "soft")
                arch_index = arch_values.index(arch_current) if arch_current in arch_values else 1
                arch_choice = st.selectbox(
                    "Arch",
                    list(brow_arch_options.keys()),
                    index=arch_index,
                    key=f"{page_prefix}_brow_arch",
                )
                brows_spec["arch"] = brow_arch_options[arch_choice]

            with apparel_tab:
                style_options = {"Classic": "classic", "Hooded": "hooded", "Scarf": "scarf", "Jacket": "jacket"}
                style_values = list(style_options.values())
                style_current = apparel_spec.get("style", "classic")
                style_index = style_values.index(style_current) if style_current in style_values else 0
                style_choice = st.selectbox(
                    "Style",
                    list(style_options.keys()),
                    index=style_index,
                    key=f"{page_prefix}_apparel_style",
                )
                apparel_spec["style"] = style_options[style_choice]

                fit_options = {"Relaxed": "relaxed", "Regular": "regular", "Tailored": "tailored", "Fitted": "fitted"}
                fit_values = list(fit_options.values())
                fit_current = apparel_spec.get("fit", "regular")
                fit_index = fit_values.index(fit_current) if fit_current in fit_values else 1
                fit_choice = st.selectbox(
                    "Fit",
                    list(fit_options.keys()),
                    index=fit_index,
                    key=f"{page_prefix}_apparel_fit",
                )
                apparel_spec["fit"] = fit_options[fit_choice]

                palette_choice = st.selectbox(
                    "Palette",
                    ["neutral", "cool", "warm"],
                    index=["neutral", "cool", "warm"].index(apparel_spec.get("palette", "neutral")) if apparel_spec.get("palette") in {"neutral", "cool", "warm"} else 0,
                    key=f"{page_prefix}_apparel_palette",
                )
                apparel_spec["palette"] = palette_choice

                accent_spec = palette.setdefault("accent", {})
                accent_cols = st.columns(2)
                accent_spec["primary"] = accent_cols[0].color_picker(
                    "Accent primary",
                    accent_spec.get("primary", "#ADB5BD"),
                    key=f"{page_prefix}_accent_primary",
                ).upper()
                accent_spec["secondary"] = accent_cols[1].color_picker(
                    "Accent secondary",
                    accent_spec.get("secondary", "#C2C8CE"),
                    key=f"{page_prefix}_accent_secondary",
                ).upper()

            with posture_tab:
                posture_options = {"Upright": "upright", "Relaxed": "neutral", "Tilted": "slight-tilt-left"}
                posture_values = list(posture_options.values())
                posture_current = palette_spec.get("posture", "upright")
                posture_index = posture_values.index(posture_current) if posture_current in posture_values else 0
                posture_choice = st.selectbox(
                    "Posture",
                    list(posture_options.keys()),
                    index=posture_index,
                    key=f"{page_prefix}_posture",
                )
                palette_spec["posture"] = posture_options[posture_choice]

                tattoo_options = {"None": "none", "Visible (forearm)": "forearm"}
                tattoo_values = list(tattoo_options.values())
                tattoo_current = palette_spec.get("tattoos", "none")
                tattoo_index = tattoo_values.index(tattoo_current) if tattoo_current in tattoo_values else 0
                tattoo_choice = st.selectbox(
                    "Tattoos",
                    list(tattoo_options.keys()),
                    index=tattoo_index,
                    key=f"{page_prefix}_tattoos",
                )
                palette_spec["tattoos"] = tattoo_options[tattoo_choice]

        current_spec_hash = _spec_signature(palette_spec)
        auto_ready = descriptor_count > 0

        with col_left:
            st.subheader("Inputs & Render")
            if not descriptors:
                st.warning("No PaDNA descriptors available in Core yet. Run refinement and ingest traits first.")
            else:
                st.info(f"Using {descriptor_count} PaDNA traits resolved by Core/UCN/RR.")

            traits_button = st.button(
                "Show raw PaDNA traits",
                key=f"{page_prefix}_toggle_traits",
                use_container_width=True,
                disabled=descriptor_count == 0,
            )
            if traits_button:
                show_traits = not show_traits
            st.session_state[_state_key(page_prefix, "padna_show_traits")] = show_traits
            if show_traits and descriptors:
                st.json(descriptors)

            if st.button(
                "Render avatar",
                type="primary",
                use_container_width=True,
                key=f"{page_prefix}_render_avatar",
                disabled=not auto_ready,
            ):
                try:
                    rendered = _call_padna_service(_prepare_bundle_for_render(bundle, palette_spec))
                    result = rendered
                    stored_hash = current_spec_hash
                    st.session_state[_state_key(page_prefix, "padna_result")] = rendered
                    st.session_state[_state_key(page_prefix, "padna_palette_spec_hash")] = stored_hash
                    st.session_state[_state_key(page_prefix, "padna_palette_spec")] = copy.deepcopy(palette_spec)
                    st.success("Avatar rendered.")
                except Exception as exc:
                    st.error(f"Renderer failed: {exc}")

        if result and auto_ready:
            desired_hash = current_spec_hash
            if stored_hash != desired_hash:
                try:
                    rendered = _call_padna_service(_prepare_bundle_for_render(bundle, palette_spec))
                    result = rendered
                    stored_hash = desired_hash
                    st.session_state[_state_key(page_prefix, "padna_result")] = rendered
                except Exception as exc:
                    st.warning(f"Auto re-render failed: {exc}")

        st.session_state[_state_key(page_prefix, "padna_palette_spec")] = copy.deepcopy(palette_spec)
        if stored_hash is not None:
            st.session_state[_state_key(page_prefix, "padna_palette_spec_hash")] = stored_hash

        with col_right:
            st.markdown("### Avatar Preview")
            if not result:
                st.info("Click render to preview the outbound avatar.")
            else:
                data_url = result.get("data_url")
                if data_url:
                    st.markdown(
                        f"<div style='text-align:center;'><img src='{data_url}' alt='PaDNA avatar' width='340' /></div>",
                        unsafe_allow_html=True,
                    )
                st.download_button(
                    "Download SVG",
                    data=result.get("svg", ""),
                    file_name="padna_avatar.svg",
                    mime="image/svg+xml",
                    key=f"{page_prefix}_download_svg",
                )
                unmapped_rows = state.get("import_unmapped") or []
                if unmapped_rows:
                    with st.expander("Unmapped PaDNA keys", expanded=False):
                        copy_store_key = f"{page_prefix}_padna_copy_key"
                        for idx, entry in enumerate(unmapped_rows):
                            path_value = entry.get("path") or entry.get("canonical_path") or ""
                            reason_value = entry.get("reason") or ""
                            cols = st.columns([5, 1])
                            with cols[0]:
                                st.code(path_value or "(missing path)")
                                if reason_value:
                                    st.caption(reason_value)
                            with cols[1]:
                                st.button(
                                    "Copy key",
                                    key=f"{page_prefix}_padna_copy_btn_{idx}",
                                    on_click=_set_streamlit_state,
                                    args=(copy_store_key, path_value),
                                    use_container_width=True,
                                )
                        copied_value = st.session_state.get(copy_store_key)
                        if copied_value:
                            st.caption(f"Stored `{copied_value}` in the session clipboard — paste where needed.")
                st.markdown("#### Palette & Posture JSON")
                st.code(json.dumps(palette_spec, indent=2), language="json")

                debug_payload = result.get("debug", {}) if isinstance(result.get("debug"), dict) else {}
                with st.expander("Renderer debug", expanded=False):
                    st.json(
                        {
                            "traits_used": debug_payload.get("traits_used", {}),
                            "palette": result.get("palette", {}),
                            "geometry": result.get("geometry", {}),
                            "fallbacks": debug_payload.get("fallbacks", []),
                        }
                    )

        return_col = st.columns([0.7, 0.3])[1]
        with return_col:
            if st.button("Return to Head Coach", type="secondary"):
                final_result = st.session_state.get(_state_key(page_prefix, "padna_result")) or {}
                palette_summary = final_result.get("palette") or {}
                summary = "Avatar refreshed." if palette_summary else "Avatar rendering complete."
                if palette_summary:
                    summary += f" Palette skin {palette_summary.get('skin', {}).get('fill')}, hair {palette_summary.get('hair', {}).get('base')}."
                _append_assistant_message(
                    page_prefix,
                    active_user,
                    summary,
                    persona_id="head_coach",
                    badges=[{"text": "Avatar ready", "tone": "info"}],
                )
                _set_active_persona(page_prefix, "head_coach", "return", {"avatar": True})
                _trigger_rerun()

        if dev_mode:
            with st.expander("Handoff log", expanded=False):
                _render_dev_log(page_prefix)

    return _render


__all__ = ["build_photo_body_renderer", "build_padna_body_renderer"]
