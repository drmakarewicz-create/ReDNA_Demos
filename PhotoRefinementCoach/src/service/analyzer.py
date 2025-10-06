from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.io.bundle_schema import validate_bundle
from src.io.export import build_bundle
from src.scoring.merge import aggregate_observations
from src.vision.model import RecencyTag, VisionModel, VisionObservation

LOGGER = logging.getLogger(__name__)


@dataclass
class PhotoPayload:
    """In-memory representation of a photo ready for analysis."""

    image_id: str
    raw_bytes: bytes
    recency: RecencyTag = RecencyTag.RECENT
    timestamp: Optional[str] = None
    filename: Optional[str] = None
    notes: Optional[str] = None


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()


def _ensure_recency(value: Optional[str]) -> RecencyTag:
    if not value:
        return RecencyTag.RECENT
    try:
        return RecencyTag(value)
    except ValueError:
        LOGGER.debug("Unknown recency value %s – defaulting to RECENT", value)
        return RecencyTag.RECENT


def _decode_photo(image: Dict[str, Any], ordinal: int) -> PhotoPayload:
    """Accept Explorer payload {id, b64|path, recency?, ts?} → PhotoPayload."""

    photo_id = image.get("id") or f"photo-{ordinal:02d}"
    recency = _ensure_recency(image.get("recency"))
    ts = image.get("ts")
    filename = image.get("filename") or photo_id
    notes = image.get("notes")

    data: Optional[bytes] = None
    raw_b64 = image.get("b64")
    raw_path = image.get("path")

    if raw_b64:
        try:
            data = base64.b64decode(raw_b64)
        except Exception as exc:  # pragma: no cover - defensive, surfaced via response
            raise ValueError(f"photo {photo_id}: invalid base64 payload ({exc})") from exc
    elif raw_path:
        try:
            with open(raw_path, "rb") as handle:
                data = handle.read()
        except OSError as exc:  # pragma: no cover - relies on environment
            raise ValueError(f"photo {photo_id}: could not read path {raw_path} ({exc})") from exc
    else:
        raise ValueError(f"photo {photo_id}: missing 'b64' or 'path'")

    if not data:
        raise ValueError(f"photo {photo_id}: empty payload")

    return PhotoPayload(
        image_id=photo_id,
        raw_bytes=data,
        recency=recency,
        timestamp=ts,
        filename=filename,
        notes=notes,
    )


def _gather_support(observations: Sequence[VisionObservation]) -> Dict[str, List[Dict[str, Any]]]:
    support: Dict[str, List[Dict[str, Any]]] = {}
    for obs in observations:
        for path, token in obs.tokens.items():
            support.setdefault(path, []).append(
                {
                    "image_id": obs.image_id,
                    "recency": obs.recency.value,
                    "value": token.get("value"),
                    "confidence": float(token.get("confidence", 0.0)),
                }
            )
    return support


def _extract_previous(bundle: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Optional[float], Optional[float]]:
    if not bundle or not isinstance(bundle, dict):
        return {}, None, None
    results = bundle.get("results") or {}
    prev_descriptors = results.get("descriptors") or {}
    ucn_block = results.get("ucn") or {}
    curiosity_block = results.get("curiosity") or {}
    return prev_descriptors, ucn_block.get("overall"), curiosity_block.get("overall")


def _compute_deltas(
    descriptors: Dict[str, Dict[str, Any]],
    prev_descriptors: Dict[str, Any],
    current_ucn: float,
    prev_ucn: Optional[float],
    current_curiosity: float,
    prev_curiosity: Optional[float],
) -> Dict[str, Any]:
    per_trait: List[Dict[str, Any]] = []
    for path, meta in descriptors.items():
        prev_meta = prev_descriptors.get(path) or {}
        prev_ucn_value = prev_meta.get("ucn")
        prev_value = prev_meta.get("value")
        current_ucn_trait = meta.get("ucn")
        per_trait.append(
            {
                "path": path,
                "value": meta.get("value"),
                "previous_value": prev_value,
                "value_changed": (prev_value is not None and prev_value != meta.get("value")),
                "ucn": current_ucn_trait,
                "previous_ucn": prev_ucn_value,
                "ucn_delta": (current_ucn_trait or 0.0) - (prev_ucn_value or 0.0),
            }
        )

    per_trait.sort(key=lambda item: abs(item.get("ucn_delta") or 0.0), reverse=True)

    removed = []
    for path in prev_descriptors.keys() - descriptors.keys():
        meta = prev_descriptors.get(path) or {}
        removed.append(
            {
                "path": path,
                "previous_value": meta.get("value"),
                "previous_ucn": meta.get("ucn"),
            }
        )

    def _delta(current: float, previous: Optional[float]) -> Optional[float]:
        if previous is None:
            return None
        return current - previous

    return {
        "overall_ucn": {
            "current": current_ucn,
            "previous": prev_ucn,
            "delta": _delta(current_ucn, prev_ucn),
        },
        "overall_curiosity": {
            "current": current_curiosity,
            "previous": prev_curiosity,
            "delta": _delta(current_curiosity, prev_curiosity),
        },
        "per_trait": per_trait[:50],
        "removed": removed,
    }


def _metrics(
    photo_count: int,
    descriptors: Dict[str, Dict[str, Any]],
    aggregate: Dict[str, Any],
    deltas: Dict[str, Any],
) -> Dict[str, Any]:
    existing = set(aggregate.get("existing_paths", []))
    return {
        "photo_count": photo_count,
        "descriptor_count": len(descriptors),
        "contradiction_count": len(aggregate.get("contradictions", [])),
        "ucn_overall": aggregate.get("overall_ucn"),
        "curiosity_overall": aggregate.get("curiosity_overall"),
        "ucn_delta_overall": deltas.get("overall_ucn", {}).get("delta"),
        "curiosity_delta_overall": deltas.get("overall_curiosity", {}).get("delta"),
        "new_descriptor_count": len([path for path in descriptors if path not in existing]),
    }


def analyze_photos(
    *,
    user_id: str,
    snapshot_id: str,
    photos: Sequence[PhotoPayload],
    notes: Optional[str] = None,
    previous_bundle: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the vision adapter on photos, aggregate descriptors, and build a bundle."""

    if not user_id:
        raise ValueError("user_id is required")
    if not snapshot_id:
        raise ValueError("snapshot_id is required")
    if not photos:
        raise ValueError("At least one photo is required")

    adapter = VisionModel.from_name(model_name or "mock-vision")

    observations: List[VisionObservation] = []
    image_meta: List[Dict[str, Any]] = []
    observation_meta: List[Dict[str, Any]] = []

    for photo in photos:
        if not photo.raw_bytes:
            raise ValueError(f"photo {photo.image_id} has no data")
        observation = adapter.analyze(photo.raw_bytes, photo.recency)
        observations.append(observation)

        img_hash = _hash_bytes(photo.raw_bytes)
        image_meta.append(
            {
                "image_id": observation.image_id,
                "image_hash": img_hash,
                "recency": observation.recency.value,
                "filename": photo.filename,
                "timestamp": photo.timestamp,
                "notes": photo.notes or notes,
                "model": {
                    "name": observation.model_name,
                    "version": observation.model_version,
                },
            }
        )
        for path, payload in observation.tokens.items():
            observation_meta.append(
                {
                    "image_id": observation.image_id,
                    "path": path,
                    "value": payload.get("value"),
                    "confidence": float(payload.get("confidence", 0.0)),
                }
            )

    if not observations:
        raise ValueError("No usable photos provided")

    aggregate = aggregate_observations(observations, previous_bundle)

    support = _gather_support(observations)
    descriptors = aggregate.get("descriptors", {})
    for path, evidence in support.items():
        if path in descriptors:
            descriptors[path].setdefault("evidence", evidence)
    aggregate["descriptors"] = descriptors

    prev_descriptors, prev_ucn, prev_curiosity = _extract_previous(previous_bundle)
    aggregate["existing_paths"] = sorted(prev_descriptors.keys())

    deltas = _compute_deltas(
        descriptors,
        prev_descriptors,
        aggregate.get("overall_ucn", 0.0),
        prev_ucn,
        aggregate.get("curiosity_overall", 0.0),
        prev_curiosity,
    )
    metrics = _metrics(len(observations), descriptors, aggregate, deltas)

    run_meta = {
        "source": "photo_coach",
        "actor": "PhotoRefinementCoach",
        "method": "visual",
        "model": adapter.name,
        "model_version": getattr(adapter, "version", "n/a"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }

    evidence_meta = {
        "images": image_meta,
        "observations": observation_meta,
        "contradictions": aggregate.get("contradictions", []),
    }

    bundle = build_bundle(
        user_id=user_id,
        snapshot_id=snapshot_id,
        aggregate=aggregate,
        evidence_meta=evidence_meta,
        run_meta=run_meta,
    )

    valid, errors = validate_bundle(bundle)
    if not valid:
        raise ValueError(f"Generated bundle failed validation: {errors}")

    warnings: List[str] = []
    if aggregate.get("contradictions"):
        warnings.append("Conflicting descriptors detected; review contradictions block.")

    return {
        "ok": True,
        "bundle": bundle,
        "aggregate": aggregate,
        "metrics": metrics,
        "deltas": deltas,
        "evidence": evidence_meta,
        "warnings": warnings,
    }


def analyze_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a JSON request (e.g., from FastAPI) and delegate to analyze_photos."""

    images = payload.get("images") or []
    photos: List[PhotoPayload] = []
    for idx, image in enumerate(images):
        photos.append(_decode_photo(image, idx + 1))

    previous_bundle = payload.get("previous_bundle")
    notes = payload.get("notes")
    model_name = payload.get("model")

    return analyze_photos(
        user_id=payload.get("user_id", ""),
        snapshot_id=payload.get("snapshot_id", ""),
        photos=photos,
        notes=notes,
        previous_bundle=previous_bundle,
        model_name=model_name,
    )


__all__ = ["PhotoPayload", "analyze_photos", "analyze_request"]
