from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

try:  # pragma: no cover - optional dependency
    from llama3_client import chat as llama_chat
except Exception:  # pragma: no cover - best effort assist
    llama_chat = None

from .alias_tables import COMMON_PATH_ALIASES
from .value_normalizer import normalize_confidence, normalize_value_for_path

logger = logging.getLogger(__name__)

DEFAULT_SCALAR_UCN = 80.0
LARGE_IMPORT_THRESHOLD = 500
NUMERIC_FIELDS = ("ucn", "rr", "curiosity")
LIST_FIELDS = ("reasons", "flags")

DEFAULT_SOFT_PROVENANCE = {
    "source": "photo-import",
    "step": "soft-import",
    "adapter": "json",
}

ENABLE_SOFT_IMPORT_ASSIST = os.getenv("ENABLE_SOFT_IMPORT_ASSIST", "true").lower() == "true"
SOFT_IMPORT_ASSIST_TIMEOUT_MS = int(os.getenv("SOFT_IMPORT_ASSIST_TIMEOUT_MS", "1500"))
ASSIST_MAX_ITEMS = int(os.getenv("SOFT_IMPORT_ASSIST_MAX_ITEMS", "12"))

OBSERVATIONS_FORMAT_EXAMPLE = (
    '{ "user_id": "demo_user", "default_provenance": {}, '
    '"observations": [ { "path": "PaDNA.HairDNA.Color", "value": "Brown", "confidence": 0.8 } ] }'
)
MISSING_OBSERVATIONS_MESSAGE = (
    f"No observations found. Expected: {OBSERVATIONS_FORMAT_EXAMPLE}"
)
NON_OBJECT_MESSAGE_PREFIX = "Each `observations` entry must be an object"

FILE_ROOT = Path(__file__).resolve().parents[2]
PATH_MAPPINGS_FILE = FILE_ROOT / "ReDNACoreDemo" / "data" / "config" / "path_mappings.yaml"
TRAITS_REGISTRY_FILE = FILE_ROOT / "ReDNACoreDemo" / "data" / "config" / "traits_registry.yaml"

PREFIX_CANONICAL = {
    "Hair": "PaDNA.HairDNA",
    "Skin": "PaDNA.SkinDNA",
    "Eye": "PaDNA.EyeDNA",
    "Eyes": "PaDNA.EyeDNA",
    "Face": "PaDNA.FaceDNA",
    "Nose": "PaDNA.NoseDNA",
    "Mouth": "PaDNA.MouthDNA",
    "Lips": "PaDNA.LipDNA",
    "Lip": "PaDNA.LipDNA",
    "Brow": "PaDNA.EyebrowDNA",
    "Eyebrow": "PaDNA.EyebrowDNA",
    "Neck": "PaDNA.NeckDNA",
    "Ear": "PaDNA.EarDNA",
    "Accessories": "PaDNA.Accessories",
    "Accessory": "PaDNA.Accessories",
    "Apparel": "PaDNA.ApparelDNA",
    "Clothing": "PaDNA.ApparelDNA",
    "Makeup": "PaDNA.MakeupDNA",
    "Age": "PaDNA.AgeDNA",
}

PREFIX_CANONICAL_LOWER = {key.lower(): value for key, value in PREFIX_CANONICAL.items()}

SPECIAL_PATH_ALIASES = {
    "Hair.Color": "PaDNA.HairDNA.Color",
    "hair.color": "PaDNA.HairDNA.Color",
    "Hair.Style": "PaDNA.HairDNA.Style",
    "Hair.Length": "PaDNA.HairDNA.Length",
    "Hair.Texture": "PaDNA.HairDNA.Texture",
    "Hair.Part": "PaDNA.HairDNA.Part",
    "Skin.Tone": "PaDNA.SkinDNA.Tone",
    "Skin.Undertone": "PaDNA.SkinDNA.Undertone",
    "Eyes.Color": "PaDNA.EyeDNA.Color",
    "Eye.Color": "PaDNA.EyeDNA.Color",
    "Eyes.Shape": "PaDNA.EyeDNA.Shape",
    "Eye.Shape": "PaDNA.EyeDNA.Shape",
    "Face.Shape": "PaDNA.FacialDNA.FaceShape",
    "Nose.Shape": "PaDNA.FacialDNA.Nose.Shape",
    "Mouth.Lips": "PaDNA.FacialDNA.Lips.Shape",
    "Lips.Shape": "PaDNA.FacialDNA.Lips.Shape",
    "Lips.Fullness": "PaDNA.FacialDNA.Lips.Fullness",
    "Eye.EyelidCrease": "PaDNA.EyeDNA.EyelidCrease",
    "Eye.ScleraTint": "PaDNA.EyeDNA.ScleraTint",
    "Eye.Spacing": "PaDNA.EyeDNA.EyeSpacing",
    "Body.HeightCM": "PaDNA.BodyDNA.HeightCM",
    "Body.WeightKG": "PaDNA.BodyDNA.WeightKG",
    "Body.Build": "PaDNA.BodyDNA.Build",
    "Body.Handedness": "PaDNA.BodyDNA.Handedness",
    "Body.HandSize": "PaDNA.BodyDNA.HandSize",
    "Body.FootSize": "PaDNA.BodyDNA.FootSize",
    "Body.ShoulderShape": "PaDNA.BodyDNA.ShoulderShape",
    "Body.NeckLength": "PaDNA.BodyDNA.NeckLength",
    "Clothing.Top.Color": "PaDNA.ApparelDNA.Top.Color",
    "Apparel.Style": "PaDNA.ApparelDNA.Style",
    "Apparel.Fit": "PaDNA.ApparelDNA.Fit",
    "Apparel.Palette": "PaDNA.ApparelDNA.Palette",
    "Apparel.FitPreference": "PaDNA.ApparelDNA.FitPreference",
    "Apparel.PalettePreference": "PaDNA.ApparelDNA.PalettePreference",
    "Apparel.FootwearStyle": "PaDNA.ApparelDNA.FootwearStyle",
    "Apparel.Accessories": "PaDNA.ApparelDNA.Accessories",
    "Movement.Gestures": "PaDNA.MovementDNA.Gestures",
    "Movement.Head": "PaDNA.MovementDNA.HeadMovement",
    "Movement.HandUsage": "PaDNA.MovementDNA.HandUsage",
    "Movement.Tempo": "PaDNA.MovementDNA.Tempo",
    "Movement.Signature": "PaDNA.MovementDNA.SignatureMotion",
    "Accessories.Visible": "PaDNA.Accessories.Visible",
    "Accessories.Earrings": "PaDNA.Accessories.Earrings",
    "Accessories.Glasses": "PaDNA.Accessories.Glasses",
    "Age.Approximation": "PaDNA.AgeDNA.Approximation",
}

_PATH_ALIAS_CACHE: Optional[Dict[str, str]] = None
_PATH_ALIAS_LOWER_CACHE: Optional[Dict[str, str]] = None
_ASSIST_ALLOWED_PATHS_CACHE: Optional[List[str]] = None


@dataclass
class QuarantinedItem:
    raw_path: str
    raw_value: Any
    reasons: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    observations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quarantined: List[QuarantinedItem] = field(default_factory=list)
    assisted: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    default_provenance: Dict[str, Any] = field(default_factory=dict)
    duplicates: List[str] = field(default_factory=list)
    raw_input_count: int = 0


def _load_external_aliases() -> Dict[str, str]:
    if yaml is None or not PATH_MAPPINGS_FILE.exists():
        return {}
    try:
        with PATH_MAPPINGS_FILE.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        aliases = data.get("aliases") if isinstance(data.get("aliases"), dict) else {}
        return {str(key): str(value) for key, value in aliases.items() if isinstance(key, str) and isinstance(value, str)}
    except Exception as exc:  # pragma: no cover - configuration issues should not crash import
        logger.warning("Unable to load path mappings from %s (%s)", PATH_MAPPINGS_FILE, exc)
        return {}


def _ensure_path_alias_cache() -> Tuple[Dict[str, str], Dict[str, str]]:
    global _PATH_ALIAS_CACHE, _PATH_ALIAS_LOWER_CACHE
    if _PATH_ALIAS_CACHE is not None and _PATH_ALIAS_LOWER_CACHE is not None:
        return _PATH_ALIAS_CACHE, _PATH_ALIAS_LOWER_CACHE

    alias_map: Dict[str, str] = dict(SPECIAL_PATH_ALIASES)
    for key, value in COMMON_PATH_ALIASES.items():
        alias_map.setdefault(key, value)
    alias_map.update(_load_external_aliases())

    _PATH_ALIAS_CACHE = alias_map
    _PATH_ALIAS_LOWER_CACHE = {key.lower(): value for key, value in alias_map.items()}
    return _PATH_ALIAS_CACHE, _PATH_ALIAS_LOWER_CACHE


def _get_assist_allowed_paths() -> List[str]:
    global _ASSIST_ALLOWED_PATHS_CACHE
    if _ASSIST_ALLOWED_PATHS_CACHE is not None:
        return _ASSIST_ALLOWED_PATHS_CACHE

    if yaml is None or not TRAITS_REGISTRY_FILE.exists():
        logger.debug("Soft-import assist disabled: traits registry YAML unavailable.")
        _ASSIST_ALLOWED_PATHS_CACHE = []
        return _ASSIST_ALLOWED_PATHS_CACHE

    try:
        with TRAITS_REGISTRY_FILE.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:  # pragma: no cover - configuration shouldn't break import
        logger.warning("Unable to load traits registry from %s (%s)", TRAITS_REGISTRY_FILE, exc)
        _ASSIST_ALLOWED_PATHS_CACHE = []
        return _ASSIST_ALLOWED_PATHS_CACHE

    paths: List[str] = []

    def _walk(node: Any, prefix: str = "") -> None:
        if isinstance(node, dict):
            node_type = node.get("type") if isinstance(node.get("type"), str) else None
            if node_type and prefix:
                paths.append(prefix)
            for key, value in node.items():
                if key in {"type", "choices", "description", "examples", "notes", "example", "display"}:
                    continue
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                _walk(value, next_prefix)
        elif isinstance(node, list):
            for item in node:
                _walk(item, prefix)

    _walk(data, "")
    _ASSIST_ALLOWED_PATHS_CACHE = sorted({path for path in paths if path})
    return _ASSIST_ALLOWED_PATHS_CACHE


def list_known_padna_paths() -> List[str]:
    """Public accessor for canonical PaDNA paths from the registry."""

    return _get_assist_allowed_paths()


def import_padna_soft(payload: Dict[str, Any], *, strict: bool = False) -> ImportResult:
    """Normalize PaDNA observations from lenient payload shapes."""

    if not isinstance(payload, dict):
        return ImportResult(
            errors=["Soft import expects an object payload."],
            default_provenance=dict(DEFAULT_SOFT_PROVENANCE),
        )

    if strict:
        return _run_strict_import(payload)

    return _run_soft_import(payload)


def _run_strict_import(payload: Dict[str, Any]) -> ImportResult:
    try:
        encoded = json.dumps(payload).encode("utf-8")
    except TypeError:
        encoded = json.dumps(_make_json_safe(payload)).encode("utf-8")

    normalized, _, errors = load_and_validate(encoded)

    warnings: List[str] = []
    observations: Dict[str, Dict[str, Any]] = {}
    quarantined: List[QuarantinedItem] = []
    duplicates: List[str] = []

    default_provenance = _build_default_provenance(
        payload,
        normalized.get("default_provenance") if isinstance(normalized, dict) else None,
    )

    user_id: Optional[str] = None
    if isinstance(normalized, dict):
        raw_warnings = normalized.get("warnings")
        if isinstance(raw_warnings, list):
            warnings.extend(str(message) for message in raw_warnings)

        raw_duplicates = normalized.get("duplicates")
        if isinstance(raw_duplicates, list):
            duplicates.extend(str(item) for item in raw_duplicates)

        obs_block = normalized.get("observations")
        if isinstance(obs_block, dict):
            for path, trait in obs_block.items():
                if not isinstance(path, str) or not isinstance(trait, dict):
                    continue
                trait_copy = dict(trait)

                resolved = trait_copy.get("resolved_value")
                if resolved is not None:
                    new_value, value_warnings = normalize_value_for_path(path, resolved)
                    warnings.extend(value_warnings)
                    trait_copy["resolved_value"] = new_value

                if "confidence" in trait_copy:
                    new_conf, conf_warnings = normalize_confidence(trait_copy["confidence"])
                    warnings.extend(conf_warnings)
                    if new_conf is not None:
                        trait_copy["confidence"] = new_conf
                    else:
                        trait_copy.pop("confidence", None)

                provenance = trait_copy.get("provenance")
                merged_prov = {**default_provenance, **provenance} if isinstance(provenance, dict) else dict(default_provenance)
                trait_copy["provenance"] = merged_prov
                observations[path] = trait_copy

        discarded = normalized.get("discarded")
        if isinstance(discarded, list):
            for item in discarded:
                if not isinstance(item, dict):
                    continue
                raw_path = str(item.get("path", "")) if item.get("path") is not None else ""
                reason = str(item.get("reason", "discarded"))
                quarantined.append(
                    QuarantinedItem(
                        raw_path=raw_path,
                        raw_value=_make_json_safe(item.get("raw_value")),
                        reasons=[reason],
                    )
                )

        user = normalized.get("user_id")
        if isinstance(user, str):
            user_id = user.strip() or None

    raw_inputs = 0
    if isinstance(payload.get("observations"), dict):
        raw_inputs = len(payload.get("observations"))
    elif isinstance(payload.get("observations"), list):
        raw_inputs = len(payload.get("observations"))

    return ImportResult(
        observations=observations,
        quarantined=quarantined,
        assisted=[],
        warnings=list(dict.fromkeys(warnings)),
        errors=errors,
        user_id=user_id,
        default_provenance=default_provenance,
        duplicates=list(dict.fromkeys(duplicates)),
        raw_input_count=raw_inputs,
    )


def _run_soft_import(payload: Dict[str, Any]) -> ImportResult:
    warnings: List[str] = []
    errors: List[str] = []
    observations: Dict[str, Dict[str, Any]] = {}
    quarantined: List[QuarantinedItem] = []
    assisted: List[Dict[str, Any]] = []
    duplicates: List[str] = []

    candidates, candidate_warnings, raw_duplicates = _collect_soft_candidates(payload)
    warnings.extend(candidate_warnings)
    duplicates.extend(raw_duplicates)

    raw_inputs = len(candidates)

    default_provenance = _build_default_provenance(payload)
    user_id = _extract_user_id(payload)

    assist_candidates: List[QuarantinedItem] = []

    for raw_path, raw_value in candidates.items():
        canonical_path, path_warnings, reason = normalize_path(raw_path)
        warnings.extend(path_warnings)
        if canonical_path is None:
            quarantined.append(
                QuarantinedItem(
                    raw_path=str(raw_path),
                    raw_value=_make_json_safe(raw_value),
                    reasons=[reason or "unmapped path"],
                )
            )
            if reason != "non-PaDNA path":
                assist_candidates.append(quarantined[-1])
            continue

        value_for_trait = raw_value
        if isinstance(value_for_trait, list):
            value_for_trait = {"resolved_value": value_for_trait}

        trait, trait_warnings, trait_errors = _normalize_trait(canonical_path, value_for_trait)
        warnings.extend(trait_warnings)

        if trait_errors:
            warnings.extend(trait_errors)
            quarantined.append(
                QuarantinedItem(
                    raw_path=str(raw_path),
                    raw_value=_make_json_safe(raw_value),
                    reasons=list(dict.fromkeys(trait_errors)),
                )
            )
            assist_candidates.append(quarantined[-1])
            continue

        resolved = trait.get("resolved_value")
        if resolved is not None:
            new_value, value_warnings = normalize_value_for_path(canonical_path, resolved)
            warnings.extend(value_warnings)
            trait["resolved_value"] = new_value

        if "confidence" in trait:
            new_conf, conf_warnings = normalize_confidence(trait["confidence"])
            warnings.extend(conf_warnings)
            if new_conf is not None:
                trait["confidence"] = new_conf
            else:
                trait.pop("confidence", None)

        if canonical_path in observations:
            duplicates.append(canonical_path)

        provenance = trait.get("provenance")
        merged_prov = {**default_provenance, **provenance} if isinstance(provenance, dict) else dict(default_provenance)
        trait["provenance"] = merged_prov
        observations[canonical_path] = trait

    if ENABLE_SOFT_IMPORT_ASSIST and assist_candidates:
        assist_new, assist_records, handled_items, assist_warnings = _apply_soft_import_assist(
            assist_candidates,
            default_provenance,
        )
        warnings.extend(assist_warnings)
        if assist_records:
            assisted.extend(assist_records)
        for path, trait in assist_new:
            if path in observations:
                duplicates.append(path)
            observations[path] = trait
        if handled_items:
            handled_ids = {id(item) for item in handled_items}
            quarantined = [item for item in quarantined if id(item) not in handled_ids]

    if not observations and not errors:
        errors.append("No PaDNA observations detected in payload.")

    # Track quarantined items for schema evolution
    if quarantined:
        try:
            from .quarantine_tracker import record_quarantine
            quarantine_items = [
                {
                    "raw_path": item.raw_path,
                    "raw_value": item.raw_value,
                    "reasons": item.reasons,
                }
                for item in quarantined
            ]
            source = default_provenance.get("source", "unknown")
            record_quarantine(quarantine_items, user_id=user_id, source=source)
        except Exception as exc:
            logger.debug(f"Failed to record quarantined items: {exc}")

    return ImportResult(
        observations=observations,
        quarantined=quarantined,
        assisted=assisted,
        warnings=list(dict.fromkeys(warnings)),
        errors=list(dict.fromkeys(errors)),
        user_id=user_id,
        default_provenance=default_provenance,
        duplicates=list(dict.fromkeys(duplicates)),
        raw_input_count=raw_inputs,
    )


def _build_default_provenance(
    payload: Dict[str, Any],
    explicit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    provenance = dict(DEFAULT_SOFT_PROVENANCE)
    source = explicit if isinstance(explicit, dict) else payload.get("default_provenance")
    if not isinstance(source, dict):
        source = payload.get("provenance")
    if isinstance(source, dict):
        provenance.update(source)
    return provenance


def _extract_user_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("user_id", "userId", "user", "uid", "id", "subject", "person_id", "name"):
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _collect_soft_candidates(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    flattened, warnings, duplicates = flatten_schema(payload)
    candidates: Dict[str, Any] = dict(flattened)

    extras = _walk_value_tree(payload)
    for path, value in extras.items():
        candidates.setdefault(path, value)

    return candidates, warnings, duplicates


def _apply_soft_import_assist(
    candidates: List[QuarantinedItem],
    default_provenance: Dict[str, Any],
) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Dict[str, Any]], List[QuarantinedItem], List[str]]:
    warnings: List[str] = []
    if not ENABLE_SOFT_IMPORT_ASSIST:
        return [], [], [], warnings

    allowed_paths = _get_assist_allowed_paths()
    if not allowed_paths:
        warnings.append("Soft-import assist unavailable (no traits registry).")
        return [], [], [], warnings

    if llama_chat is None:
        warnings.append("Soft-import assist unavailable (LLM client not configured).")
        return [], [], [], warnings

    trimmed = candidates[:ASSIST_MAX_ITEMS]
    payload_items = [
        {
            "index": idx,
            "raw_path": item.raw_path,
            "raw_value": item.raw_value,
            "reasons": item.reasons,
        }
        for idx, item in enumerate(trimmed)
    ]

    if not payload_items:
        return [], [], [], warnings

    response = _call_assist_model(payload_items, allowed_paths)
    if not response.get("ok"):
        reason = response.get("reason") or "unknown"
        warnings.append(f"Soft-import assist skipped ({reason}).")
        return [], [], [], warnings

    raw_text = response.get("text", "")
    try:
        mappings = json.loads(raw_text)
        if not isinstance(mappings, list):
            raise ValueError("assist response was not a list")
    except Exception as exc:
        warnings.append(f"Soft-import assist response unparseable ({exc}).")
        return [], [], [], warnings

    index_map = {idx: item for idx, item in enumerate(trimmed)}
    handled: List[QuarantinedItem] = []
    new_traits: List[Tuple[str, Dict[str, Any]]] = []
    assisted_records: List[Dict[str, Any]] = []

    for idx, entry in enumerate(mappings):
        if not isinstance(entry, dict):
            continue
        target_index = entry.get("index")
        if isinstance(target_index, int) and target_index in index_map:
            candidate = index_map[target_index]
        else:
            candidate = index_map.get(idx)
        if candidate is None:
            continue

        target_path = entry.get("path")
        if not target_path:
            continue
        if target_path not in allowed_paths:
            warnings.append(f"Assist returned unsupported path {target_path}.")
            continue

        mapped_value = entry.get("value")
        if mapped_value is None:
            continue

        payload_value: Dict[str, Any] = {"resolved_value": mapped_value}
        if "confidence" in entry:
            payload_value["confidence"] = entry.get("confidence")

        trait, trait_warnings, trait_errors = _normalize_trait(target_path, payload_value)
        warnings.extend(trait_warnings)
        if trait_errors:
            warnings.extend(trait_errors)
            continue

        resolved = trait.get("resolved_value")
        if resolved is not None:
            new_value, value_warnings = normalize_value_for_path(target_path, resolved)
            warnings.extend(value_warnings)
            trait["resolved_value"] = new_value

        if "confidence" in trait:
            new_conf, conf_warnings = normalize_confidence(trait["confidence"])
            warnings.extend(conf_warnings)
            if new_conf is not None:
                trait["confidence"] = new_conf
            else:
                trait.pop("confidence", None)

        provenance = trait.get("provenance")
        merged_prov = {**default_provenance, **provenance} if isinstance(provenance, dict) else dict(default_provenance)
        merged_prov.setdefault("assist", "llm")
        trait["provenance"] = merged_prov

        new_traits.append((target_path, trait))
        assisted_records.append(
            {
                "raw_path": candidate.raw_path,
                "path": target_path,
                "value": _make_json_safe(trait.get("resolved_value")),
                "confidence": trait.get("confidence"),
                "reason": entry.get("reason") or "llm-assist",
            }
        )
        handled.append(candidate)

    return new_traits, assisted_records, handled, warnings


ASSIST_SYSTEM_PROMPT = (
    "You normalize traits for the ReDNA Photo Coach. "
    "Given raw key/value observations, map each to the closest canonical PaDNA path."
)


def _call_assist_model(
    observations: List[Dict[str, Any]],
    allowed_paths: List[str],
) -> Dict[str, Any]:
    if not observations:
        return {"ok": False, "reason": "no_observations"}
    if llama_chat is None:
        return {"ok": False, "reason": "client_unavailable"}

    obs_json = json.dumps(observations, ensure_ascii=False)
    paths_json = json.dumps(allowed_paths, ensure_ascii=False)
    user_prompt = (
        "You are provided with:\n"
        "1. A list of allowed PaDNA trait paths.\n"
        "2. A list of raw observations, each with an index, raw_path, raw_value, and reasons.\n"
        "For each observation, choose the PaDNA path that best matches the intent.\n"
        "Return JSON in the form [{\"index\": int, \"path\": string|null, \"value\": any, \"confidence\": float|null, \"reason\": string}].\n"
        "Use null path when no match exists. Confidence must be 0..1 if provided.\n"
        "Only use paths from the allowed list. Keep outputs deterministic.\n"
        f"Allowed paths:{paths_json}\n"
        f"Observations:{obs_json}"
    )

    def _invoke() -> Dict[str, Any]:
        return llama_chat(ASSIST_SYSTEM_PROMPT, user_prompt)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            timeout_s = max(SOFT_IMPORT_ASSIST_TIMEOUT_MS, 250) / 1000.0
            return future.result(timeout=timeout_s)
    except TimeoutError:
        return {"ok": False, "reason": "timeout"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "reason": str(exc)}


_SOFT_SKIP_TOP_LEVEL = {
    "user_id",
    "userid",
    "default_provenance",
    "provenance",
    "images",
    "assisted",
    "quarantined",
    "warnings",
    "errors",
}

_SOFT_SKIP_KEYS = {"observations", "traits"}


def _walk_value_tree(node: Any, prefix: str = "") -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            lower_key = key_str.lower()
            if not prefix and lower_key in _SOFT_SKIP_TOP_LEVEL:
                continue
            if lower_key in _SOFT_SKIP_KEYS:
                continue
            next_prefix = f"{prefix}.{key_str}" if prefix else key_str
            if isinstance(value, dict):
                if _looks_like_observation_dict(value):
                    results[next_prefix] = value
                else:
                    results.update(_walk_value_tree(value, next_prefix))
            elif isinstance(value, list):
                if not value:
                    continue
                if _list_is_scalar(value):
                    results[next_prefix] = value
                else:
                    for item in value:
                        sub_results = _walk_value_tree(item, next_prefix)
                        for sub_path, sub_value in sub_results.items():
                            results.setdefault(sub_path, sub_value)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                results[next_prefix] = value
    elif isinstance(node, list):
        for item in node:
            results.update(_walk_value_tree(item, prefix))
    return results


def _looks_like_observation_dict(value: Dict[str, Any]) -> bool:
    trait_markers = {"value", "resolved_value", "confidence", "ucn", "rr", "curiosity", "notes"}
    return any(marker in value for marker in trait_markers)


def _list_is_scalar(values: Iterable[Any]) -> bool:
    for item in values:
        if isinstance(item, (dict, list)):
            return False
    return True


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _make_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def collect_image_filenames(payload: Dict[str, Any]) -> List[str]:
    """Expose image filename extraction for UI consumption."""

    if not isinstance(payload, dict):
        return []
    return _collect_image_filenames(payload)


def load_and_validate(file_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Parse a PaDNA JSON import, normalise observations, and surface validation details."""

    errors: List[str] = []
    warnings: List[str] = []
    report: Dict[str, Any] = {}
    normalized: Dict[str, Any] = {}

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        errors.append(f"Import must be UTF-8 encoded JSON ({exc}).")
        return {}, {}, errors

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON: {exc}")
        return {}, {}, errors

    if not isinstance(payload, dict):
        errors.append("Top-level JSON must be an object with user_id and observations.")
        return {}, {}, errors

    user_id = payload.get("user_id")
    if isinstance(user_id, str):
        user_id = user_id.strip()
    if not user_id:
        report["user_id"] = {"ok": False, "message": "Missing user_id."}
        errors.append("`user_id` is required.")
    else:
        normalized["user_id"] = user_id
        report["user_id"] = {"ok": True, "message": user_id}

    default_provenance = payload.get("provenance")
    if default_provenance is None:
        normalized["default_provenance"] = {}
        report["provenance"] = {"ok": False, "message": "No default provenance provided."}
    elif isinstance(default_provenance, dict):
        normalized["default_provenance"] = default_provenance
        report["provenance"] = {"ok": True, "message": f"{len(default_provenance)} field(s)"}
    else:
        normalized["default_provenance"] = {}
        warnings.append("Top-level provenance ignored because it is not an object.")
        report["provenance"] = {"ok": False, "message": "Provenance must be an object."}

    observations_raw, flatten_warnings, duplicates = flatten_schema(payload)
    warnings.extend(flatten_warnings)
    for message in flatten_warnings:
        if message.startswith(MISSING_OBSERVATIONS_MESSAGE) and message not in errors:
            errors.append(message)
        if message.startswith(NON_OBJECT_MESSAGE_PREFIX) and message not in errors:
            errors.append(message)
    normalized["duplicates"] = duplicates

    if not observations_raw:
        report["observations"] = {"ok": False, "message": "No traits detected."}
        if MISSING_OBSERVATIONS_MESSAGE not in errors:
            errors.append(MISSING_OBSERVATIONS_MESSAGE)
        normalized["warnings"] = warnings
        report["warnings"] = warnings
        normalized["image_filenames"] = _collect_image_filenames(payload)
        return normalized, report, errors

    normalized_obs: Dict[str, Dict[str, Any]] = {}
    trait_errors: List[str] = []
    discarded: List[Dict[str, Any]] = []
    unmapped: List[Dict[str, Any]] = []

    for path, raw in observations_raw.items():
        canonical_path, path_warnings, reason = normalize_path(path)
        warnings.extend(path_warnings)
        if canonical_path is None:
            detail = {"path": path, "reason": reason or "unmapped path"}
            discarded.append(detail)
            if reason in {"unmapped path", "non-PaDNA path"}:
                unmapped.append(detail)
            logger.warning("Discarding observation %s: %s", path, detail["reason"])
            continue

        trait, trait_warnings, trait_errs = normalize_observation(path, raw)
        if trait_errs:
            trait_errors.extend(trait_errs)
            detail = {"path": canonical_path, "reason": "; ".join(trait_errs)}
            discarded.append(detail)
            logger.warning("Discarding observation %s: %s", canonical_path, detail["reason"])
            continue

        warnings.extend(trait_warnings)
        if canonical_path in normalized_obs:
            warnings.append(
                f"{canonical_path}: duplicate trait detected (last value kept)."
            )
        normalized_obs[canonical_path] = trait

    if trait_errors:
        errors.extend(trait_errors)

    if normalized_obs:
        normalized["observations"] = normalized_obs
        normalized["trait_count"] = len(normalized_obs)
        report["observations"] = {
            "ok": True,
            "count": len(normalized_obs),
            "message": f"{len(normalized_obs)} trait(s) ready",
        }
    else:
        report["observations"] = {"ok": False, "message": "All traits failed validation."}
        if not errors:
            errors.append("No valid observations remain after validation.")

    normalized["discarded"] = discarded
    normalized["unmapped"] = unmapped
    if discarded:
        report["discarded"] = {
            "ok": False,
            "count": len(discarded),
            "message": f"{len(discarded)} observation(s) discarded",
        }
    else:
        report["discarded"] = {"ok": True, "message": "0 discarded"}

    if unmapped:
        report["unmapped"] = {
            "ok": False,
            "count": len(unmapped),
            "message": f"{len(unmapped)} unmapped observation(s)",
        }
    else:
        report["unmapped"] = {"ok": True, "message": "All paths mapped"}

    if duplicates:
        warnings.append(
            "Duplicate trait paths detected (last occurrence kept): "
            + ", ".join(sorted(set(duplicates)))
        )

    image_filenames = _collect_image_filenames(payload)
    normalized["image_filenames"] = image_filenames
    if image_filenames:
        report["images"] = {"ok": True, "message": f"{len(image_filenames)} image reference(s)"}
    elif isinstance(payload.get("images"), list):
        report["images"] = {"ok": False, "message": "Images listed but no filenames detected."}
    else:
        report["images"] = {"ok": False, "message": "No image references provided."}

    needs_confirmation = bool(normalized_obs) and len(normalized_obs) > LARGE_IMPORT_THRESHOLD
    normalized["needs_large_confirmation"] = needs_confirmation
    if needs_confirmation:
        warning_text = (
            f"Import contains {len(normalized_obs)} traits — confirm before ingesting."
        )
        warnings.append(warning_text)
        report["volume"] = {"ok": False, "message": warning_text}
    else:
        report["volume"] = {
            "ok": bool(normalized_obs),
            "message": f"{len(normalized_obs)} traits" if normalized_obs else "0 traits",
        }

    normalized["warnings"] = warnings
    report["warnings"] = warnings

    return normalized, report, errors


def flatten_schema(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Flatten supported observation shapes into a trait-path map."""

    raw = payload.get("observations")
    source_label = "observations"
    if raw is None:
        alt = payload.get("traits")
        if alt is not None:
            raw = alt
            source_label = "traits"
    warnings: List[str] = []
    duplicates: List[str] = []
    flattened: Dict[str, Any] = {}

    if raw is None:
        warnings.append("Missing `observations` block.")
        return {}, warnings, duplicates

    def add_trait(path: Any, value: Any) -> None:
        nonlocal flattened, duplicates
        if not isinstance(path, str):
            warnings.append("Encountered observation without a string path; skipping entry.")
            return
        key = path.strip()
        if not key:
            warnings.append("Encountered observation with empty path; skipping entry.")
            return
        if key in flattened:
            duplicates.append(key)
        flattened[key] = value

    if isinstance(raw, dict):
        if _looks_like_trait_map(raw):
            for path, value in raw.items():
                add_trait(path, value)
        else:
            for group_key, group_value in raw.items():
                _flatten_group(group_value, add_trait, warnings, prefix=group_key)
    elif isinstance(raw, list):
        bad_indexes: List[int] = []
        for index, item in enumerate(raw):
            if isinstance(item, dict) and "observations" in item:
                _flatten_group(item.get("observations"), add_trait, warnings)
            elif isinstance(item, dict):
                path = item.get("path") or item.get("trait") or item.get("name")
                if path is None:
                    warnings.append("List observation missing `path`; skipping entry.")
                    continue
                payload_value = item.get("payload")
                if isinstance(payload_value, dict):
                    add_trait(path, payload_value)
                else:
                    add_trait(path, item)
            else:
                bad_indexes.append(index)
        if bad_indexes:
            index_snippet = ", ".join(str(i) for i in bad_indexes[:10])
            if len(bad_indexes) > 10:
                index_snippet += ", ..."
            warnings.append(
                f"{NON_OBJECT_MESSAGE_PREFIX} with path and value fields. Non-object at indexes: {index_snippet}"
            )
    else:
        warnings.append(f"`{source_label}` must be an object or list.")

    return flattened, warnings, duplicates


def merge_provenance(
    observations: Dict[str, Dict[str, Any]],
    default_provenance: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Apply default provenance to each observation (without mutating inputs)."""

    if not default_provenance:
        return {path: dict(payload) for path, payload in observations.items()}

    merged: Dict[str, Dict[str, Any]] = {}
    for path, payload in observations.items():
        item = dict(payload)
        existing = item.get("provenance")
        if isinstance(existing, dict):
            combined = {**default_provenance, **existing}
        else:
            combined = dict(default_provenance)
        item["provenance"] = combined
        merged[path] = item
    return merged


def preview_rows(observations: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return lightweight preview data for display in Streamlit."""

    rows: List[Dict[str, Any]] = []
    for path in sorted(observations.keys()):
        payload = observations[path]
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        resolved = payload.get("resolved_value")
        if isinstance(resolved, (list, dict)):
            try:
                resolved_display = json.dumps(resolved, ensure_ascii=False)
            except TypeError:
                resolved_display = str(resolved)
        else:
            resolved_display = resolved
        rows.append(
            {
                "path": path,
                "resolved_value": resolved_display,
                "ucn": payload.get("ucn"),
                "rr": payload.get("rr"),
                "curiosity": payload.get("curiosity"),
                "source": provenance.get("source"),
                "status": payload.get("status"),
            }
        )
    return rows


def _flatten_group(group: Any, add_trait: Any, warnings: List[str], prefix: str = "") -> None:
    if isinstance(group, dict):
        # Support nested {"observations": {...}} as well as direct trait maps.
        inner = group.get("observations") if isinstance(group.get("observations"), dict) else None
        if inner is not None:
            for path, value in inner.items():
                full_path = f"{prefix}.{path}" if prefix else path
                add_trait(full_path, value)
            return

        # Check if this dict looks like a trait value (has resolved_value, ucn, etc.)
        if _looks_like_observation_dict(group):
            # This is a trait value, not a container - add it with the current prefix
            if prefix:
                add_trait(prefix, group)
            return

        # Otherwise, recurse into nested structure
        for key, value in group.items():
            full_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                # Check if this value is a trait or needs further recursion
                if _looks_like_observation_dict(value):
                    add_trait(full_path, value)
                else:
                    # Recurse deeper
                    _flatten_group(value, add_trait, warnings, full_path)
            elif isinstance(value, list):
                # Lists might be trait values (arrays) or need flattening
                if _list_is_scalar(value):
                    # This is a scalar list value - wrap it as a trait
                    add_trait(full_path, {"resolved_value": value})
                else:
                    # Recurse into list items
                    _flatten_group(value, add_trait, warnings, full_path)
            else:
                # Scalar value - wrap it as a trait
                add_trait(full_path, value)

    elif isinstance(group, list):
        for item in group:
            if isinstance(item, dict):
                path = item.get("path") or item.get("trait") or item.get("name")
                if path is None:
                    warnings.append("Nested list observation missing `path`; skipping entry.")
                    continue
                full_path = f"{prefix}.{path}" if prefix else path
                payload_value = item.get("payload")
                if isinstance(payload_value, dict):
                    add_trait(full_path, payload_value)
                else:
                    add_trait(full_path, item)
            else:
                warnings.append("Nested list observation entry must be an object; skipping entry.")
    else:
        warnings.append("Unsupported nested observation structure; skipping entry.")


def normalize_path(path: Any) -> Tuple[Optional[str], List[str], Optional[str]]:
    warnings: List[str] = []
    if not isinstance(path, str):
        return None, warnings, "path is not a string"

    key = path.strip()
    if not key:
        return None, warnings, "path is empty"

    alias_map, alias_lower = _ensure_path_alias_cache()
    canonical: Optional[str] = None
    if key in alias_map:
        canonical = alias_map[key]
    else:
        lower_key = key.lower()
        if lower_key in alias_lower:
            canonical = alias_lower[lower_key]
            if canonical != key:
                warnings.append(f"{path}: mapped via case-insensitive alias to {canonical}.")
        else:
            canonical, canonical_warnings = _canonicalize_path(key)
            warnings.extend(canonical_warnings)

    if not canonical:
        return None, warnings, "unmapped path"
    if not canonical.startswith("PaDNA."):
        return None, warnings, "non-PaDNA path"
    return canonical, warnings, None


def normalize_observation(path: str, raw: Any) -> Tuple[Dict[str, Any], List[str], List[str]]:
    return _normalize_trait(path, raw)


def _normalize_trait(path: str, raw: Any) -> Tuple[Dict[str, Any], List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []

    if raw is None:
        errors.append(f"{path}: observation is null.")
        return {}, warnings, errors

    if isinstance(raw, (str, int, float, bool)):
        warnings.append(f"{path}: scalar value wrapped into an observation with default UCN {DEFAULT_SCALAR_UCN}.")
        return {"resolved_value": raw, "ucn": DEFAULT_SCALAR_UCN}, warnings, errors

    if not isinstance(raw, dict):
        errors.append(f"{path}: expected object or scalar, got {type(raw).__name__}.")
        return {}, warnings, errors

    trait: Dict[str, Any] = {
        k: raw[k]
        for k in raw
        if raw[k] is not None and k not in {"path", "trait", "name", "payload"}
    }

    if "resolved_value" not in trait:
        if "value" in raw:
            trait["resolved_value"] = raw["value"]
        elif "resolved" in raw:
            trait["resolved_value"] = raw["resolved"]
        else:
            errors.append(f"{path}: missing `resolved_value`.")
            return {}, warnings, errors

    trait.pop("value", None)
    trait.pop("resolved", None)

    for field in NUMERIC_FIELDS:
        if field in trait:
            coerced, warn = _coerce_number(trait[field], field, path)
            if coerced is None:
                trait.pop(field, None)
                if warn:
                    warnings.append(warn)
            else:
                trait[field] = coerced
                if warn:
                    warnings.append(warn)

    for field in LIST_FIELDS:
        if field in trait:
            value = trait[field]
            if isinstance(value, list):
                trait[field] = [str(item) for item in value]
            elif value is None:
                trait.pop(field, None)
            else:
                trait[field] = [str(value)]
                warnings.append(f"{path}: coerced `{field}` to a list.")

    if "notes" in trait and trait["notes"] is not None and not isinstance(trait["notes"], dict):
        trait["notes"] = {"text": str(trait["notes"]) }
        warnings.append(f"{path}: wrapped notes into an object under 'text'.")

    if "provenance" in trait and trait["provenance"] is not None and not isinstance(trait["provenance"], dict):
        trait["provenance"] = {"value": trait["provenance"]}
        warnings.append(f"{path}: provenance coerced into an object under 'value'.")

    if "status" in trait and trait["status"] is not None and not isinstance(trait["status"], str):
        trait["status"] = str(trait["status"])
        warnings.append(f"{path}: status coerced to string.")

    return trait, warnings, errors


def _looks_like_trait_map(candidate: Dict[str, Any]) -> bool:
    if not candidate:
        return False
    # A trait map has dotted path keys like "PaDNA.HairDNA.Color", not just "PaDNA"
    # Also check that values look like trait objects (have resolved_value, ucn, etc.)
    trait_like_keys = [key for key in candidate.keys() if isinstance(key, str) and "." in key]
    if trait_like_keys and len(trait_like_keys) == len(candidate):
        # Check if at least some values look like trait objects
        trait_value_count = sum(1 for v in candidate.values() if isinstance(v, dict) and _looks_like_observation_dict(v))
        if trait_value_count > 0:
            return True
    if not trait_like_keys:
        return False
    nested = any(isinstance(value, dict) and "observations" in value for value in candidate.values())
    return not nested


def _coerce_number(value: Any, field: str, path: str) -> Tuple[Any, str | None]:
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None, f"{path}: `{field}` was empty and removed."
        try:
            number = float(stripped)
        except ValueError:
            return None, f"{path}: `{field}`='{value}' is not numeric and was dropped."
    else:
        return None, f"{path}: `{field}` of type {type(value).__name__} was dropped."

    warning = None
    if number < 0 or number > 1000:
        warning = f"{path}: `{field}`={number:.2f} outside 0..1000."
    return number, warning


def _collect_image_filenames(payload: Dict[str, Any]) -> List[str]:
    filenames: List[str] = []

    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        images = provenance.get("images")
        filenames.extend(_extract_image_names(images))

    images_block = payload.get("images")
    filenames.extend(_extract_image_names(images_block))

    deduped = sorted({name for name in filenames if name})
    return deduped


def _extract_image_names(images: Any) -> Iterable[str]:
    if images is None:
        return []
    if isinstance(images, list):
        collected: List[str] = []
        for item in images:
            if isinstance(item, str):
                collected.append(item)
            elif isinstance(item, dict):
                name = item.get("filename") or item.get("name") or item.get("id")
                if name:
                    collected.append(str(name))
        return collected
    if isinstance(images, str):
        return [images]
    return []


def _canonicalize_path(path: str) -> Tuple[Optional[str], List[str]]:
    warnings: List[str] = []

    if not isinstance(path, str):
        return None, warnings

    key = path.strip()
    if not key:
        return None, warnings

    if key.startswith("PaDNA."):
        return key, warnings

    alias_map, alias_lower = _ensure_path_alias_cache()
    if key in alias_map:
        return alias_map[key], warnings

    lower_key = key.lower()
    if lower_key in alias_lower:
        canonical = alias_lower[lower_key]
        if canonical != key:
            warnings.append(f"{path}: mapped via case-insensitive alias to {canonical}.")
        return canonical, warnings

    segments = [segment.strip() for segment in key.split(".") if segment.strip()]
    if not segments:
        return None, warnings

    prefix_key = segments[0]
    base = (
        PREFIX_CANONICAL.get(prefix_key)
        or PREFIX_CANONICAL.get(prefix_key.capitalize())
        or PREFIX_CANONICAL_LOWER.get(prefix_key.lower())
    )
    if not base:
        return None, warnings

    canonical_segments = [base] + segments[1:]
    canonical = ".".join(canonical_segments)
    return canonical, warnings
