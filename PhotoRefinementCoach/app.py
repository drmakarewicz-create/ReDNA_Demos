#!/usr/bin/env python3
"""Streamlit UI for the PhotoRefinementCoach specialist."""

from __future__ import annotations

import copy
import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

try:
    from ExplorerFinal.ui.nav import side_nav, top_tabs
    from ExplorerFinal.ui.session import get_user_id, user_picker
except Exception:  # pragma: no cover - keeps local dev working if Explorer imports move
    def side_nav(active: str = "photo") -> None:  # type: ignore[override]
        st.sidebar.title("Navigation")

    def top_tabs(active: str = "explorer") -> None:  # type: ignore[override]
        st.markdown("### Explorer shell")

    def user_picker(label: str = "Active user") -> None:  # type: ignore[override]
        st.text_input(label, key="user_id", placeholder="e.g., 918NIGHT")

    def get_user_id() -> str:  # type: ignore[override]
        return st.session_state.get("user_id", "")

PHOTO_VISION_BASE_URL = os.getenv("PHOTO_VISION_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
CORE_BASE = os.getenv("CORE_BASE", os.getenv("CORE_URL", "http://127.0.0.1:8015")).rstrip("/")


def _vision_endpoint_available() -> bool:
    try:
        resp = requests.get(f"{PHOTO_VISION_BASE_URL}/api/version", timeout=2)
        return resp.status_code < 300
    except Exception:
        return False


from src.importer import (
    LARGE_IMPORT_THRESHOLD,
    collect_image_filenames,
    import_padna_soft,
    list_known_padna_paths,
    merge_provenance,
    preview_rows,
)
from src.service.analyzer import PhotoPayload, analyze_photos
from src.ui.session import CoachState, get_state
from src.ui.widgets import download_buttons, photos_uploader, show_refinement_plots


PREVIEW_LIMIT = 25


def _serialize_quarantine(items: List[Any]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for entry in items:
        if isinstance(entry, dict):
            serialized.append(
                {
                    "raw_path": str(entry.get("raw_path", "")),
                    "raw_value": entry.get("raw_value"),
                    "reasons": list(entry.get("reasons", [])),
                }
            )
            continue

        serialized.append(
            {
                "raw_path": getattr(entry, "raw_path", ""),
                "raw_value": getattr(entry, "raw_value", None),
                "reasons": list(getattr(entry, "reasons", [])),
            }
        )
    return serialized

st.set_page_config(page_title="Photo Refinement Coach", page_icon="📸", layout="wide")

# Shared Explorer chrome
top_tabs(active="explorer")
side_nav(active="photo")

st.title("📸 Photo Refinement Coach")

state: CoachState = get_state()

# --- Layout -----------------------------------------------------------------
left, right = st.columns([0.45, 0.55])

with left:
    st.subheader("Session setup")
    user_picker("Active user")
    active_user = get_user_id() or state.user_id
    state.user_id = st.text_input("User ID", value=active_user, placeholder="e.g., 918NIGHT").strip()
    state.snapshot_id = st.text_input(
        "Snapshot ID",
        value=state.snapshot_id,
        help="Use the Core snapshot identifier you plan to reconcile against.",
    ).strip()
    state.notes = st.text_area(
        "Coach notes (optional)",
        value=state.notes,
        placeholder="e.g., Head Coach suggested focusing on tattoos and posture.",
        height=90,
    )

    adapters = ["mock-vision", "llama3-vision"]
    default_index = adapters.index("llama3-vision") if _vision_endpoint_available() else 0
    adapter_choice = st.selectbox(
        "Vision adapter",
        options=adapters,
        index=default_index,
        help="Switch to llama3-vision when the local Ollama service is running.",
    )

    photos_uploader(state)

    st.subheader("Import JSON")
    soft_toggle = st.toggle(
        "Soft import (auto-normalize)",
        value=state.import_soft_enabled,
        help="Accept loose JSON structures and coerce them into PaDNA where possible.",
        key="soft_import_toggle",
    )
    state.import_soft_enabled = soft_toggle

    with st.container():
        upload = st.file_uploader(
            "Upload PaDNA JSON",
            type=["json"],
            key="padna_import_json",
            help="Use bundles authored offline (e.g., ChatGPT) to ingest traits directly into Core.",
        )

        if upload is not None:
            uploaded_bytes = upload.getvalue()
            digest = hashlib.sha1(uploaded_bytes).hexdigest()
            is_new_upload = digest != state.import_digest

            errors: List[str] = []
            warnings: List[str] = []
            counts: Dict[str, int] = {"imported": 0, "assisted": 0, "quarantined": 0}
            normalized_payload: Optional[Dict[str, Any]] = None
            result_observations: Dict[str, Dict[str, Any]] = {}
            default_provenance: Dict[str, Any] = {}
            preview_data: List[Dict[str, Any]] = []
            report: Dict[str, Any] = {}
            needs_confirmation = False

            state.import_assisted = []
            state.import_quarantined = []
            state.import_raw_payload = None
            state.import_raw_text = None

            payload_dict: Optional[Dict[str, Any]] = None

            try:
                text = uploaded_bytes.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                errors.append(f"Import must be UTF-8 encoded JSON ({exc}).")
            else:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    errors.append(f"Invalid JSON: {exc}")
                else:
                    if not isinstance(parsed, dict):
                        errors.append("Top-level JSON must be an object with PaDNA content.")
                    else:
                        payload_dict = parsed
                        state.import_raw_text = text
                        state.import_raw_payload = copy.deepcopy(parsed)

            if payload_dict is not None:
                result = import_padna_soft(payload_dict, strict=not state.import_soft_enabled)
                result_observations = result.observations
                default_provenance = result.default_provenance
                counts = {
                    "raw": result.raw_input_count,
                    "imported": len(result_observations),
                    "assisted": len(result.assisted),
                    "quarantined": len(result.quarantined),
                }

                state.import_assisted = [dict(item) for item in result.assisted] if result.assisted else []
                state.import_quarantined = _serialize_quarantine(result.quarantined)

                warnings.extend(result.warnings)
                duplicate_paths = list(dict.fromkeys(result.duplicates))
                if duplicate_paths:
                    warnings.append(
                        "Duplicate trait paths detected (last value kept): "
                        + ", ".join(sorted(duplicate_paths))
                    )

                user_id_value = result.user_id or payload_dict.get("user_id")
                fallback_applied = False
                if isinstance(user_id_value, str):
                    user_id_value = user_id_value.strip() or None
                else:
                    user_id_value = None

                if not user_id_value and state.user_id:
                    user_id_value = state.user_id
                    fallback_applied = True

                if not user_id_value:
                    errors.append("`user_id` is required.")

                needs_confirmation = len(result_observations) > LARGE_IMPORT_THRESHOLD
                image_filenames = collect_image_filenames(payload_dict)

                normalized_payload = {
                    "user_id": user_id_value,
                    "observations": result_observations,
                    "trait_count": len(result_observations),
                    "default_provenance": default_provenance,
                    "needs_large_confirmation": needs_confirmation,
                    "duplicates": result.duplicates,
                    "image_filenames": image_filenames,
                }

                preview_source = merge_provenance(result_observations, default_provenance)
                preview_data = preview_rows(preview_source) if result_observations else []

                report = {
                    "user_id": {
                        "ok": bool(user_id_value),
                        "message": user_id_value or "Missing user_id.",
                    },
                    "observations": {
                        "ok": bool(result_observations),
                        "count": len(result_observations),
                        "message": f"{len(result_observations)} trait(s) ready"
                        if result_observations
                        else "No traits detected.",
                    },
                    "provenance": {
                        "ok": bool(default_provenance),
                        "message": f"{len(default_provenance)} field(s)"
                        if default_provenance
                        else "No default provenance provided.",
                    },
                    "images": {
                        "ok": bool(image_filenames),
                        "message": f"{len(image_filenames)} image reference(s)"
                        if image_filenames
                        else "No image references provided.",
                    },
                    "volume": {
                        "ok": not needs_confirmation,
                        "message": f"{len(result_observations)} traits",
                    },
                }
                if state.import_quarantined:
                    report["discarded"] = {
                        "ok": False,
                        "count": len(state.import_quarantined),
                        "message": f"{len(state.import_quarantined)} item(s) quarantined",
                    }
                else:
                    report["discarded"] = {"ok": True, "message": "0 quarantined"}

                if state.import_quarantined:
                    warnings.append(
                        f"{len(state.import_quarantined)} observation(s) placed in quarantine; review below."
                    )

                if fallback_applied:
                    warnings.append("No user_id in JSON; defaulted to the active user above.")

                if state.import_raw_payload is not None and user_id_value:
                    state.import_raw_payload.setdefault("user_id", user_id_value)

            warnings = list(dict.fromkeys(warnings))
            errors = list(dict.fromkeys(errors))

            state.import_digest = digest
            state.import_filename = upload.name
            state.import_report = report
            state.import_errors = errors
            state.import_warnings = warnings
            state.import_counts = counts
            state.import_preview = preview_data if not errors else []
            state.import_payload = normalized_payload if not errors else None

            state.import_raw_payload = state.import_raw_payload if not errors else state.import_raw_payload

            if is_new_upload:
                state.import_status = None
                state.import_compute_rr = True
                state.import_use_inbound_rr = False
                st.session_state["import_compute_rr_checkbox"] = True
                st.session_state["import_use_inbound_rr_checkbox"] = False
                if state.import_payload:
                    state.import_large_confirmed = not needs_confirmation
                    st.session_state["import_large_confirm"] = state.import_large_confirmed
                    payload_user = state.import_payload.get("user_id")
                    if payload_user:
                        state.user_id = payload_user
                else:
                    state.import_large_confirmed = False
                    st.session_state["import_large_confirm"] = False

        if state.import_filename:
            trait_count = (
                state.import_payload.get("trait_count")
                if state.import_payload
                else (state.import_report or {}).get("observations", {}).get("count")
            )
            suffix = f" — {trait_count} trait(s) detected" if trait_count else ""
            st.caption(f"Loaded {state.import_filename}{suffix}")

        report = state.import_report or {}

        def _status_line(label: str, block: Dict[str, Any]) -> None:
            if not block:
                return
            ok = bool(block.get("ok"))
            icon = "✅" if ok else "❌"
            message = block.get("message") or ""
            st.markdown(f"{icon} **{label}:** {message}")

        if report:
            _status_line("User", report.get("user_id", {}))
            _status_line("Observations", report.get("observations", {}))
            _status_line("Provenance", report.get("provenance", {}))
            _status_line("Images", report.get("images", {}))
            _status_line("Volume", report.get("volume", {}))
            if "discarded" in report:
                _status_line("Quarantined", report.get("discarded", {}))

        if state.import_errors:
            for error_msg in state.import_errors:
                st.error(error_msg)

        if state.import_warnings:
            for warning_msg in state.import_warnings:
                st.warning(warning_msg)

        metrics = state.import_counts or {}
        metric_cols = st.columns(4)
        metric_cols[0].metric("Raw inputs", metrics.get("raw", 0))
        metric_cols[1].metric("Imported", metrics.get("imported", 0))
        metric_cols[2].metric("Assisted", metrics.get("assisted", 0))
        metric_cols[3].metric("Quarantined", metrics.get("quarantined", 0))

        requires_confirmation = bool(state.import_payload and state.import_payload.get("needs_large_confirmation"))
        if requires_confirmation:
            confirm_label = (
                f"Confirm import of {state.import_payload.get('trait_count', 0)} traits"
            )
            confirmed = st.checkbox(
                confirm_label,
                value=state.import_large_confirmed,
                key="import_large_confirm",
            )
            state.import_large_confirmed = confirmed
        else:
            state.import_large_confirmed = True

        compute_rr = st.checkbox(
            "Compute RR/Curiosity in Core",
            value=state.import_compute_rr,
            key="import_compute_rr_checkbox",
            help="When enabled, Core recomputes RR/Curiosity using its baselines.",
        )
        state.import_compute_rr = compute_rr

        inbound_rr_available = any(
            isinstance(row, dict) and (row.get("rr") is not None or row.get("curiosity") is not None)
            for row in (state.import_preview or [])
        )
        use_inbound_rr = st.checkbox(
            "Use inbound RR/Curiosity values",
            value=state.import_use_inbound_rr,
            key="import_use_inbound_rr_checkbox",
            help="Preserve RR/Curiosity provided in the JSON instead of Core recomputing them.",
            disabled=not inbound_rr_available,
        )
        state.import_use_inbound_rr = use_inbound_rr and inbound_rr_available

        if state.import_payload and state.import_payload.get("user_id") != state.user_id:
            st.warning(
                "Imported bundle user_id differs from the active user field above; the import will use the bundle's user_id."
            )

        if state.import_preview:
            st.markdown("**Imported observations**")
            preview_subset = state.import_preview[:PREVIEW_LIMIT]
            preview_df = pd.DataFrame(preview_subset)
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
            if len(state.import_preview) > PREVIEW_LIMIT:
                st.caption(f"Showing first {PREVIEW_LIMIT} of {len(state.import_preview)} observations.")

        if state.import_assisted:
            st.markdown("**Assisted mappings**")
            st.json(state.import_assisted)

        if state.import_quarantined:
            st.markdown("**Quarantined observations**")
            known_paths = list_known_padna_paths()
            if not known_paths:
                known_paths = sorted(state.import_payload.get("observations", {}).keys()) if state.import_payload else []
            for idx, item in enumerate(state.import_quarantined):
                label = item.get("raw_path") or f"Entry {idx + 1}"
                reasons = ", ".join(item.get("reasons") or []) or "Review"
                with st.expander(f"{label} — {reasons}", expanded=False):
                    st.json({"raw_value": item.get("raw_value"), "reasons": item.get("reasons", [])})
                    with st.form(f"quarantine_form_{idx}"):
                        default_path = item.get("raw_path") or ""
                        try:
                            default_index = known_paths.index(default_path)
                        except ValueError:
                            default_index = 0 if known_paths else -1
                        canonical_path = st.selectbox(
                            "Canonical path",
                            options=known_paths,
                            index=default_index if default_index >= 0 else 0,
                            key=f"canonical_path_{idx}",
                        ) if known_paths else st.text_input("Canonical path", value=default_path, key=f"canonical_path_free_{idx}")

                        value_input = st.text_area(
                            "Resolved value",
                            value=_stringify(item.get("raw_value")),
                            key=f"value_input_{idx}",
                        )
                        confidence_input = st.text_input(
                            "Confidence (0-1, optional)",
                            value="",
                            key=f"confidence_input_{idx}",
                        )
                        submit = st.form_submit_button("Map & apply")
                        if submit:
                            parsed_conf, conf_error = _parse_confidence(confidence_input)
                            if conf_error:
                                st.error(conf_error)
                            else:
                                mapped_value = _parse_input_value(value_input)
                                target_path = canonical_path if isinstance(canonical_path, str) else str(canonical_path)
                                success, warnings = _apply_manual_mapping(
                                    state,
                                    idx,
                                    target_path,
                                    mapped_value,
                                    parsed_conf,
                                )
                                if success:
                                    for warning in warnings:
                                        st.warning(warning)
                                    st.success("Mapping applied. Entry moved to assisted list.")
                                    st.experimental_rerun()
                                else:
                                    for warning in warnings:
                                        st.error(warning)

        ingest_ready = bool(state.import_payload and state.import_payload.get("observations"))
        if requires_confirmation:
            ingest_ready = ingest_ready and state.import_large_confirmed
        ingest_disabled = (
            not ingest_ready
            or bool(state.import_errors)
            or state.import_payload is None
        )

        st.caption(f"Core ingest endpoint: `{CORE_BASE}/ingest_from_ucnrr`")

        if st.button(
            "Ingest to Core",
            type="primary",
            use_container_width=True,
            disabled=ingest_disabled,
        ):
            if not state.import_payload:
                st.error("No validated PaDNA observations to ingest.")
            else:
                try:
                    normalized = state.import_payload
                    base_provenance = dict(normalized.get("default_provenance") or {})
                    base_provenance.setdefault("mode", "manual-import")
                    base_provenance["source"] = "photo-coach"
                    base_provenance["from"] = "manual-import"
                    base_provenance["ts"] = datetime.now(timezone.utc).isoformat()

                    filenames = normalized.get("image_filenames") or []
                    if filenames:
                        existing = base_provenance.get("images")
                        merged_images = set(filenames)
                        if isinstance(existing, list):
                            merged_images.update(str(name) for name in existing)
                        base_provenance["images"] = sorted(merged_images)

                    merged_observations = merge_provenance(
                        normalized.get("observations") or {},
                        base_provenance,
                    )

                    if not state.import_use_inbound_rr:
                        for payload_entry in merged_observations.values():
                            payload_entry.pop("rr", None)
                            payload_entry.pop("curiosity", None)

                    payload: Dict[str, Any] = {
                        "user_id": normalized.get("user_id"),
                        "observations": merged_observations,
                    }

                    compute_flag = bool(state.import_compute_rr and not state.import_use_inbound_rr)
                    if not compute_flag:
                        payload["options"] = {"compute_rr_curiosity": False}

                    if state.import_raw_payload is not None:
                        payload["raw_payload"] = state.import_raw_payload
                    elif state.import_payload is not None:
                        payload["raw_payload"] = state.import_payload

                    if state.import_counts:
                        payload["raw_counts"] = state.import_counts

                    if state.import_warnings:
                        payload["raw_notes"] = state.import_warnings

                    with st.spinner("Ingesting into Core..."):
                        resp = requests.post(
                            f"{CORE_BASE}/ingest_from_ucnrr",
                            json=payload,
                            timeout=30,
                        )

                    if resp.headers.get("content-type", "").startswith("application/json"):
                        body: Any = resp.json()
                    else:
                        body = resp.text

                    state.import_status = {
                        "ok": resp.ok,
                        "status_code": resp.status_code,
                        "body": body,
                    }
                except Exception as exc:  # pragma: no cover - surfaced to user
                    state.import_status = {"ok": False, "error": str(exc)}

        if state.import_status:
            status = state.import_status
            if status.get("ok"):
                body = status.get("body") if isinstance(status.get("body"), dict) else {}
                changed = len(body.get("changed", [])) if isinstance(body, dict) else "?"
                st.success(f"Core ingest succeeded — {changed} key(s) changed.")
            else:
                err_detail = status.get("error") or status.get("status_code")
                st.error(f"Core ingest failed: {err_detail}")
            if isinstance(status.get("body"), (dict, list)):
                st.json(status.get("body"), expanded=False)
            elif status.get("body"):
                st.code(str(status.get("body")))

    run_disabled = not state.user_id or not state.snapshot_id or not state.photos
    if st.button("Run refinement on all photos", type="primary", use_container_width=True, disabled=run_disabled):
        try:
            payloads: List[PhotoPayload] = []
            for idx, photo in enumerate(state.photos):
                payloads.append(
                    PhotoPayload(
                        image_id=getattr(photo, "hash", f"photo-{idx:02d}"),
                        raw_bytes=photo.data or b"",
                        recency=photo.recency,
                        timestamp=photo.timestamp_iso,
                        filename=photo.name,
                        notes=photo.notes,
                    )
                )

            result = analyze_photos(
                user_id=state.user_id,
                snapshot_id=state.snapshot_id,
                photos=payloads,
                notes=state.notes,
                previous_bundle=state.previous_bundle,
                model_name=adapter_choice,
            )
            state.last_result = result
            state.last_bundle = result.get("bundle")
            state.last_aggregate = result.get("aggregate")
            st.success("Refinement completed — bundle ready for Explorer ingestion.")
            if result.get("warnings"):
                for warning in result["warnings"]:
                    st.warning(warning)
        except Exception as exc:  # pragma: no cover - surfaced to user
            st.error(f"Refinement failed: {exc}")

with right:
    st.subheader("Results")
    if not state.last_result:
        st.info("Upload photos and run a refinement to view descriptors and metrics.")
    else:
        result = state.last_result
        metrics = result.get("metrics", {})
        aggregate = result.get("aggregate", {})
        bundle = result.get("bundle", {})
        deltas = result.get("deltas", {})

        met_cols = st.columns(3)
        met_cols[0].metric("Overall UCN", f"{metrics.get('ucn_overall', 0.0):.1f}")
        delta_ucn = metrics.get("ucn_delta_overall")
        met_cols[1].metric(
            "UCN Δ",
            "—" if delta_ucn is None else f"{delta_ucn:+.1f}",
        )
        met_cols[2].metric("Photos analyzed", int(metrics.get("photo_count", 0)))

        if aggregate.get("contradictions"):
            with st.expander("Contradictions detected", expanded=False):
                st.json(aggregate["contradictions"], expanded=False)

        descriptors = (aggregate.get("descriptors") or {})
        if descriptors:
            table: List[Dict[str, Any]] = []
            for path, payload in descriptors.items():
                evidence = payload.get("evidence") or []
                table.append(
                    {
                        "dna_path": path,
                        "value": payload.get("value"),
                        "ucn": round(float(payload.get("ucn", 0.0)), 2),
                        "support_photos": ", ".join(sorted({ev.get("image_id") for ev in evidence})) or "—",
                    }
                )
            df = pd.DataFrame(table)
            st.dataframe(df, use_container_width=True, hide_index=True)

        if aggregate:
            show_refinement_plots(aggregate)

        if deltas:
            with st.expander("Trait deltas", expanded=False):
                st.json(deltas, expanded=False)

        st.markdown("---")
        download_buttons(bundle)
        with st.expander("Bundle JSON", expanded=False):
            st.code(json.dumps(bundle, indent=2), language="json")

        if result.get("evidence"):
            with st.expander("Evidence metadata", expanded=False):
                st.json(result["evidence"], expanded=False)

st.markdown("---")
with st.expander("Developer diagnostics", expanded=False):
    st.write("State snapshot")
    st.json(
        {
            "photos": [
                {
                    "name": p.name,
                    "recency": p.recency.value,
                    "hash": getattr(p, "hash", ""),
                    "timestamp": p.timestamp_iso,
                }
                for p in state.photos
            ],
            "previous_bundle_loaded": bool(state.previous_bundle),
        },
        expanded=False,
    )
def _stringify(value: Any) -> str:
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _parse_input_value(text: str) -> Any:
    raw = text.strip()
    if not raw:
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _parse_confidence(text: str) -> tuple[Optional[float], Optional[str]]:
    raw = text.strip()
    if not raw:
        return None, None
    try:
        value = float(raw)
    except ValueError:
        return None, "Confidence must be numeric between 0 and 1."
    if value > 1:
        value /= 100.0
    value = max(0.0, min(1.0, value))
    return value, None


def _apply_manual_mapping(
    state: CoachState,
    index: int,
    canonical_path: str,
    resolved_value: Any,
    confidence: Optional[float],
) -> tuple[bool, List[str]]:
    payload = state.import_payload or {}
    user_id = payload.get("user_id") or state.user_id
    if not user_id:
        return False, ["User ID missing; cannot apply mapping."]

    observation_entry: Dict[str, Any] = {"path": canonical_path, "value": resolved_value}
    if confidence is not None:
        observation_entry["confidence"] = confidence

    manual_payload: Dict[str, Any] = {
        "user_id": user_id,
        "default_provenance": payload.get("default_provenance") or {},
        "observations": [observation_entry],
    }

    result = import_padna_soft(manual_payload, strict=False)
    if result.errors:
        return False, result.errors
    if not result.observations:
        return False, ["Manual mapping did not yield a valid observation."]
    if result.quarantined:
        return False, ["Manual mapping still ambiguous; adjust value or path."]

    trait_path, trait_payload = next(iter(result.observations.items()))

    payload.setdefault("observations", {})
    payload["observations"][trait_path] = trait_payload
    payload["trait_count"] = len(payload["observations"])
    if result.default_provenance:
        payload.setdefault("default_provenance", {}).update(result.default_provenance)

    removed_item = state.import_quarantined[index]
    assisted_entry = {
        "raw_path": removed_item.get("raw_path"),
        "path": trait_path,
        "value": trait_payload.get("resolved_value") if isinstance(trait_payload, dict) else trait_payload,
        "confidence": trait_payload.get("confidence") if isinstance(trait_payload, dict) else None,
        "reason": "manual-remap",
    }
    state.import_assisted.append(assisted_entry)

    del state.import_quarantined[index]

    merged = merge_provenance(payload["observations"], payload.get("default_provenance") or {})
    state.import_preview = preview_rows(merged)

    counts = dict(state.import_counts or {})
    counts["imported"] = len(payload["observations"])
    counts["assisted"] = len(state.import_assisted)
    counts["quarantined"] = len(state.import_quarantined)
    state.import_counts = counts

    state.import_payload = payload
    return True, result.warnings
