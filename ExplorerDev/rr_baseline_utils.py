"""Helpers for managing demo RR baseline overrides in Dev Explorer."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path  # type: ignore

ensure_explorerdev_on_path()

import copy
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # optional dependency in some deployment targets
    import yaml  # type: ignore
except Exception:  # pragma: no cover - keep utilities usable without PyYAML
    yaml = None

try:  # Streamlit is only available when running the Dev Explorer UI
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - allow CLI/tests to import utilities
    st = None  # type: ignore

try:
    from ExplorerDev import schema_utils as _schema_utils
except Exception:  # pragma: no cover - schema utils optional for CLI usage
    _schema_utils = None  # type: ignore

from ExplorerDev.write_utils import WriteProtectContext, write_guard


DEFAULT_BETA_MEAN = 0.45
DEFAULT_BETA_STD = 0.10
DEFAULT_SAMPLE_SIZE = 50

SESSION_KEY_DEMO_ENABLED = "_rr_demo_baselines_toggle"
SESSION_KEY_DRAFT = "_rr_demo_baselines_draft"


@dataclass(slots=True)
class ValidationIssue:
    level: str
    scope: str
    message: str


def canonical_baselines_path(repo_root: Path) -> Path:
    return repo_root / "ReDNACoreDemo" / "data" / "config" / "rr_baselines.yaml"


def demo_baselines_path(repo_root: Path) -> Path:
    return repo_root / "data" / "dev_config" / "rr_demo_baselines.yaml"


def change_log_path(repo_root: Path) -> Path:
    return repo_root / "data" / "dev_logs" / "rr_baselines_changes.log"


def load_canonical_baselines(repo_root: Path) -> Dict[str, Any]:
    """Load Core's canonical baselines and normalise to 0–1 scale where possible."""

    path = canonical_baselines_path(repo_root)
    defaults = {
        "mean_ucn": DEFAULT_BETA_MEAN,
        "std_ucn": DEFAULT_BETA_STD,
        "sample_size": DEFAULT_SAMPLE_SIZE,
    }
    traits: Dict[str, Dict[str, Any]] = {}

    if yaml is None or not path.exists():
        return {"defaults": defaults, "traits": traits, "path": str(path)}

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except Exception:
        return {"defaults": defaults, "traits": traits, "path": str(path)}

    raw_defaults = raw.get("defaults") if isinstance(raw.get("defaults"), dict) else {}
    defaults.update(_convert_canonical_block(raw_defaults))

    raw_traits = raw.get("traits") if isinstance(raw.get("traits"), dict) else {}
    for key, payload in raw_traits.items():
        if not isinstance(payload, dict):
            continue
        traits[str(key)] = _convert_canonical_block(payload)

    return {
        "defaults": defaults,
        "traits": traits,
        "path": str(path),
    }


def _convert_canonical_block(block: Dict[str, Any]) -> Dict[str, Any]:
    converted: Dict[str, Any] = {}
    mean = block.get("mean")
    std = block.get("std")
    n = block.get("sample_size") or block.get("n")
    if isinstance(mean, (int, float)):
        converted["mean_ucn"] = max(0.0, min(float(mean) / 1000.0, 1.0))
    if isinstance(std, (int, float)):
        converted["std_ucn"] = max(0.0, min(float(std) / 1000.0, 1.0))
    if isinstance(n, (int, float)):
        converted["sample_size"] = max(int(n), 1)
    return converted


def load_demo_config(repo_root: Path) -> Dict[str, Any]:
    """Load the demo config from disk or return a default stub."""

    path = demo_baselines_path(repo_root)
    if path.exists() and yaml is not None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            if isinstance(data, dict):
                return _normalise_demo_config(data)
        except Exception:
            pass

    return {
        "schemaVersion": 1,
        "global": {"use_demo_baselines": False},
        "note": "",
        "defaults": {
            "mean_ucn": DEFAULT_BETA_MEAN,
            "std_ucn": DEFAULT_BETA_STD,
            "sample_size": DEFAULT_SAMPLE_SIZE,
        },
        "containers": {},
    }


def _normalise_demo_config(config: Dict[str, Any]) -> Dict[str, Any]:
    data = copy.deepcopy(config)
    data.setdefault("schemaVersion", 1)
    global_conf = data.get("global") if isinstance(data.get("global"), dict) else {}
    data["global"] = {"use_demo_baselines": bool(global_conf.get("use_demo_baselines"))}
    data["note"] = str(config.get("note") or "")
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    data["defaults"] = _coerce_baseline_block(defaults, fallback=None)

    containers_raw = data.get("containers") if isinstance(data.get("containers"), dict) else {}
    containers: Dict[str, Any] = {}
    for name, payload in containers_raw.items():
        if not isinstance(payload, dict):
            continue
        entry: Dict[str, Any] = _coerce_baseline_block(payload, fallback=data["defaults"])
        traits_raw = payload.get("traits") if isinstance(payload.get("traits"), dict) else {}
        traits: Dict[str, Any] = {}
        for trait_name, trait_payload in traits_raw.items():
            if not isinstance(trait_payload, dict):
                continue
            traits[str(trait_name)] = _coerce_baseline_block(trait_payload, fallback=entry)
        if traits:
            entry["traits"] = traits
        containers[str(name)] = entry
    data["containers"] = containers
    return data


def _coerce_baseline_block(block: Dict[str, Any], fallback: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = copy.deepcopy(fallback) if fallback else {
        "mean_ucn": DEFAULT_BETA_MEAN,
        "std_ucn": DEFAULT_BETA_STD,
        "sample_size": DEFAULT_SAMPLE_SIZE,
    }
    if isinstance(block, dict):
        if isinstance(block.get("mean_ucn"), (int, float)):
            base["mean_ucn"] = float(block["mean_ucn"])
        if isinstance(block.get("std_ucn"), (int, float)):
            base["std_ucn"] = float(block["std_ucn"])
        if isinstance(block.get("sample_size"), (int, float)):
            base["sample_size"] = int(block["sample_size"]) or DEFAULT_SAMPLE_SIZE
    return base


def validate_demo_baselines(config: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if int(config.get("schemaVersion", 1)) != 1:
        issues.append(
            ValidationIssue("error", "schemaVersion", "Only schemaVersion=1 is supported.")
        )

    defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    issues.extend(_validate_block("defaults", defaults))

    containers = config.get("containers") if isinstance(config.get("containers"), dict) else {}
    for container_name, payload in containers.items():
        if not isinstance(payload, dict):
            issues.append(ValidationIssue("error", container_name, "Container entry must be a mapping."))
            continue
        issues.extend(_validate_block(f"container:{container_name}", payload))
        traits = payload.get("traits") if isinstance(payload.get("traits"), dict) else {}
        for trait_name, trait_block in traits.items():
            if not isinstance(trait_block, dict):
                issues.append(
                    ValidationIssue(
                        "error",
                        f"trait:{container_name}.{trait_name}",
                        "Trait entry must be a mapping.",
                    )
                )
                continue
            issues.extend(
                _validate_block(
                    f"trait:{container_name}.{trait_name}",
                    trait_block,
                )
            )

    return issues


def _validate_block(scope: str, block: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    mean = block.get("mean_ucn")
    std = block.get("std_ucn")
    n = block.get("sample_size")

    if mean is not None:
        if not isinstance(mean, (int, float)):
            issues.append(ValidationIssue("error", scope, "mean_ucn must be numeric."))
        elif not (0.0 <= float(mean) <= 1.0):
            issues.append(ValidationIssue("error", scope, "mean_ucn must be between 0 and 1."))

    if std is not None:
        if not isinstance(std, (int, float)):
            issues.append(ValidationIssue("error", scope, "std_ucn must be numeric."))
        elif not (0.0 <= float(std) <= 1.0):
            issues.append(ValidationIssue("error", scope, "std_ucn must be between 0 and 1."))

    if n is not None:
        if not isinstance(n, (int, float)):
            issues.append(ValidationIssue("error", scope, "sample_size must be numeric."))
        elif int(n) < 1:
            issues.append(ValidationIssue("error", scope, "sample_size must be ≥ 1."))

    return issues


def resolve_baselines(config: Dict[str, Any], canonical: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Produce cascade-resolved baselines for quick lookup and display."""

    defaults = _coerce_baseline_block(config.get("defaults", {}), fallback=None)
    containers = {}

    raw_containers = config.get("containers") if isinstance(config.get("containers"), dict) else {}
    for container_name, payload in raw_containers.items():
        if not isinstance(payload, dict):
            continue
        container_block = _coerce_baseline_block(payload, fallback=defaults)
        explicit_fields = {
            field
            for field in ("mean_ucn", "std_ucn", "sample_size")
            if isinstance(payload.get(field), (int, float))
        }
        container_entry = {
            "mean_ucn": container_block.get("mean_ucn", defaults["mean_ucn"]),
            "std_ucn": container_block.get("std_ucn", defaults["std_ucn"]),
            "sample_size": int(container_block.get("sample_size", defaults["sample_size"])),
            "source": "explicit" if explicit_fields else "inherited",
            "traits": {},
        }
        trait_entries = payload.get("traits") if isinstance(payload.get("traits"), dict) else {}
        for trait_name, trait_payload in trait_entries.items():
            if not isinstance(trait_payload, dict):
                continue
            trait_block = _coerce_baseline_block(trait_payload, fallback=container_block)
            trait_explicit = {
                field
                for field in ("mean_ucn", "std_ucn", "sample_size")
                if isinstance(trait_payload.get(field), (int, float))
            }
            container_entry["traits"][str(trait_name)] = {
                "mean_ucn": trait_block.get("mean_ucn", container_entry["mean_ucn"]),
                "std_ucn": trait_block.get("std_ucn", container_entry["std_ucn"]),
                "sample_size": int(trait_block.get("sample_size", container_entry["sample_size"])),
                "source": "explicit" if trait_explicit else "inherited",
            }
        containers[str(container_name)] = container_entry

    explicit_defaults = any(
        isinstance(config.get("defaults", {}).get(field), (int, float))
        for field in ("mean_ucn", "std_ucn", "sample_size")
    )

    resolved = {
        "defaults": {
            "mean_ucn": defaults.get("mean_ucn", DEFAULT_BETA_MEAN),
            "std_ucn": defaults.get("std_ucn", DEFAULT_BETA_STD),
            "sample_size": int(defaults.get("sample_size", DEFAULT_SAMPLE_SIZE)),
            "source": "explicit" if explicit_defaults else "default",
        },
        "containers": containers,
    }

    if canonical:
        resolved["canonical_defaults"] = canonical.get("defaults", {})
        resolved["canonical_traits"] = canonical.get("traits", {})

    return resolved


def load_demo_baselines(repo_root: Path) -> Dict[str, Any]:
    config = load_demo_config(repo_root)
    canonical = load_canonical_baselines(repo_root)
    resolved = resolve_baselines(config, canonical=canonical)
    return {
        "config": config,
        "resolved": resolved,
        "canonical": canonical,
        "path": str(demo_baselines_path(repo_root)),
    }


def get_effective_baseline(
    repo_root: Path,
    container: str,
    trait: Optional[str] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
    canonical: Optional[Dict[str, Any]] = None,
    use_demo: Optional[bool] = None,
) -> Dict[str, Any]:
    data = config if config else load_demo_config(repo_root)
    canonical = canonical if canonical else load_canonical_baselines(repo_root)
    if use_demo is None:
        use_demo = is_demo_enabled(repo_root)

    resolved = resolve_baselines(data, canonical=canonical)
    defaults = resolved["defaults"]
    container_entry = resolved["containers"].get(container) if isinstance(resolved["containers"], dict) else None

    if use_demo:
        if trait and container_entry and trait in container_entry.get("traits", {}):
            trait_entry = container_entry["traits"][trait]
            return {**trait_entry, "source": "demo_trait"}
        if container_entry:
            return {**container_entry, "source": "demo_container"}
        return {**defaults, "source": "demo_default"}

    # live baselines path
    canonical_trait = canonical.get("traits", {}).get(trait or "") if trait else None
    canonical_defaults = canonical.get("defaults", {})
    mean = canonical_trait.get("mean_ucn") if isinstance(canonical_trait, dict) else None
    std = canonical_trait.get("std_ucn") if isinstance(canonical_trait, dict) else None
    n = canonical_trait.get("sample_size") if isinstance(canonical_trait, dict) else None
    return {
        "mean_ucn": mean if isinstance(mean, (int, float)) else canonical_defaults.get("mean_ucn", DEFAULT_BETA_MEAN),
        "std_ucn": std if isinstance(std, (int, float)) else canonical_defaults.get("std_ucn", DEFAULT_BETA_STD),
        "sample_size": int(n) if isinstance(n, (int, float)) else canonical_defaults.get("sample_size", DEFAULT_SAMPLE_SIZE),
        "source": "canonical_trait" if canonical_trait else "canonical_default",
    }


def save_demo_baselines(
    repo_root: Path,
    data: Dict[str, Any],
    context: WriteProtectContext,
    *,
    previous: Optional[Dict[str, Any]] = None,
) -> Path:
    write_guard(context, action="write RR demo baselines")
    path = demo_baselines_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        raise RuntimeError("PyYAML is required to persist RR demo baselines.")
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, backup_path)
        except Exception:
            try:
                backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
    serializable = copy.deepcopy(data)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(serializable, handle, sort_keys=False)

    log_event(repo_root, previous or {}, data)
    return path


def log_event(repo_root: Path, before: Dict[str, Any], after: Dict[str, Any]) -> None:
    path = change_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    diff = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "before": before,
        "after": after,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(diff) + "\n")


def is_demo_enabled(repo_root: Path, *, with_source: bool = False) -> Any:
    session_value = None
    if st is not None:
        session_value = st.session_state.get(SESSION_KEY_DEMO_ENABLED)
    if session_value is not None:
        result = bool(session_value)
        return (result, "session") if with_source else result

    config = load_demo_config(repo_root)
    global_conf = config.get("global") if isinstance(config.get("global"), dict) else {}
    default_value = bool(global_conf.get("use_demo_baselines"))

    if _schema_utils is not None:
        value, source = _schema_utils.get_flag_bool("DEMO_BASELINES_ENABLED", default_value)
    else:
        env_value = os.getenv("DEMO_BASELINES_ENABLED")
        if env_value and str(env_value).strip().lower() in {"1", "true", "yes", "on"}:
            value, source = True, "env"
        else:
            value, source = default_value, "default"

    if with_source:
        return value, source
    return value


def current_baselines_path(repo_root: Path) -> str:
    return (
        str(demo_baselines_path(repo_root))
        if is_demo_enabled(repo_root)
        else str(canonical_baselines_path(repo_root))
    )


def make_rows_for_display(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved = resolve_baselines(config)
    rows: List[Dict[str, Any]] = []
    rows.append(
        {
            "scope": "defaults",
            "mean_ucn": resolved["defaults"]["mean_ucn"],
            "std_ucn": resolved["defaults"]["std_ucn"],
            "sample_size": resolved["defaults"]["sample_size"],
            "effective_source": resolved["defaults"].get("source", "defaults"),
            "sparkline": _sparkline(
                resolved["defaults"].get("mean_ucn"),
                resolved["defaults"].get("std_ucn"),
            ),
            "source_chip": _format_source_chip(resolved["defaults"].get("source")),
        }
    )
    for container_name, container in resolved["containers"].items():
        rows.append(
            {
                "scope": f"{container_name} (container)",
                "mean_ucn": container["mean_ucn"],
                "std_ucn": container["std_ucn"],
                "sample_size": container["sample_size"],
                "effective_source": container.get("source", "container"),
                "sparkline": _sparkline(container.get("mean_ucn"), container.get("std_ucn")),
                "source_chip": _format_source_chip(container.get("source")),
            }
        )
        traits = container.get("traits") if isinstance(container.get("traits"), dict) else {}
        for trait_name, trait in traits.items():
            rows.append(
                {
                    "scope": f"{container_name}.{trait_name}",
                    "mean_ucn": trait["mean_ucn"],
                    "std_ucn": trait["std_ucn"],
                    "sample_size": trait["sample_size"],
                    "effective_source": trait.get("source", "trait"),
                    "sparkline": _sparkline(trait.get("mean_ucn"), trait.get("std_ucn")),
                    "source_chip": _format_source_chip(trait.get("source")),
                }
            )
    return rows


def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _sparkline(mean: Any, std: Any) -> str:
    if mean is None:
        return "—"
    mean_val = _safe_float(mean, None)
    if mean_val is None:
        return "—"
    mean_val = max(0.0, min(mean_val, 1.0))
    std_val = max(0.0, min(_safe_float(std, 0.0) or 0.0, 1.0))
    lower = max(0.0, mean_val - std_val)
    upper = min(1.0, mean_val + std_val)
    width = 18
    cells: List[str] = []
    for idx in range(width):
        position = (idx + 0.5) / width
        if abs(position - mean_val) <= 0.5 / width:
            cells.append("█")
        elif lower <= position <= upper:
            cells.append("▒")
        else:
            cells.append("░")
    return "".join(cells)


def _format_source_chip(source: Any) -> str:
    token = str(source or "").lower()
    if "trait" in token:
        label = "trait"
    elif "container" in token:
        label = "container"
    elif "canonical" in token or "live" in token:
        label = "live"
    elif "demo" in token:
        label = "demo"
    elif "default" in token:
        label = "default"
    else:
        label = token or "default"
    return label.upper()


def _known_schema_entities(repo_root: Path) -> Tuple[set[str], set[str]]:
    if _schema_utils is None:
        return set(), set()
    try:
        schema = _schema_utils.load_schema(repo_root)
    except Exception:
        return set(), set()

    containers: set[str] = set()
    traits: set[str] = set()
    schema_containers = schema.get("containers", []) if isinstance(schema.get("containers"), list) else []
    for container in schema_containers:
        if not isinstance(container, dict):
            continue
        container_id = str(container.get("id") or "").strip()
        if not container_id:
            continue
        containers.add(container_id)
        trait_list = container.get("traits") if isinstance(container.get("traits"), list) else []
        for trait in trait_list:
            if not isinstance(trait, dict):
                continue
            trait_id = str(trait.get("id") or "").strip()
            if trait_id:
                traits.add(f"{container_id}.{trait_id}")
    return containers, traits


def _summarize_changes(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    base_rows = {row["scope"]: row for row in make_rows_for_display(before)}
    new_rows = {row["scope"]: row for row in make_rows_for_display(after)}

    base_scopes = set(base_rows.keys())
    new_scopes = set(new_rows.keys())

    added = sorted(new_scopes - base_scopes)
    removed = sorted(base_scopes - new_scopes)
    changed: List[str] = []
    for scope in sorted(base_scopes & new_scopes):
        base_row = base_rows.get(scope, {})
        new_row = new_rows.get(scope, {})
        if any(
            _safe_float(base_row.get(field)) != _safe_float(new_row.get(field))
            for field in ("mean_ucn", "std_ucn", "sample_size")
        ):
            changed.append(scope)

    note_changed = str(before.get("note") or "") != str(after.get("note") or "")

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "note_changed": note_changed,
    }


def preflight_import(
    repo_root: Path,
    new_config: Dict[str, Any],
    *,
    canonical: Optional[Dict[str, Any]] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    canonical = canonical or load_canonical_baselines(repo_root)
    existing = existing or load_demo_config(repo_root)
    normalized = _normalise_demo_config(new_config)
    issues = validate_demo_baselines(normalized)
    error_issues = [issue for issue in issues if issue.level == "error"]
    warning_issues = [issue for issue in issues if issue.level != "error"]

    containers_map = (
        normalized.get("containers") if isinstance(normalized.get("containers"), dict) else {}
    )
    container_count = len(containers_map)
    trait_count = 0
    for payload in containers_map.values():
        if isinstance(payload, dict):
            trait_map = payload.get("traits") if isinstance(payload.get("traits"), dict) else {}
            trait_count += len(trait_map)

    known_containers, known_traits = _known_schema_entities(repo_root)
    unknown_containers = sorted(
        container_name
        for container_name in containers_map.keys()
        if known_containers and container_name not in known_containers
    )

    unknown_traits: List[str] = []
    for container_name, payload in containers_map.items():
        trait_map = payload.get("traits") if isinstance(payload, dict) and isinstance(payload.get("traits"), dict) else {}
        for trait_name in trait_map.keys():
            scope = f"{container_name}.{trait_name}"
            if known_traits and scope not in known_traits:
                unknown_traits.append(scope)

    changes = _summarize_changes(existing, normalized)

    return {
        "config": normalized,
        "issues": issues,
        "error_count": len(error_issues),
        "warning_count": len(warning_issues),
        "counts": {
            "containers": container_count,
            "traits": trait_count,
        },
        "unknown": {
            "containers": unknown_containers,
            "traits": sorted(unknown_traits),
        },
        "changes": changes,
        "canonical": canonical,
    }


def export_config_as_csv(config: Dict[str, Any]) -> str:
    rows = make_rows_for_display(config)
    header = ["scope", "mean_ucn", "std_ucn", "sample_size", "effective_source"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(
            ",".join(
                [
                    str(row.get("scope", "")),
                    f"{row.get('mean_ucn', '')}",
                    f"{row.get('std_ucn', '')}",
                    f"{row.get('sample_size', '')}",
                    str(row.get("effective_source", "")),
                ]
            )
        )
    return "\n".join(lines)


def load_change_log(repo_root: Path, limit: int = 10) -> List[Dict[str, Any]]:
    path = change_log_path(repo_root)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                entries.append(payload)
        except json.JSONDecodeError:
            continue
    return entries


def set_session_toggle(value: bool) -> None:
    if st is None:
        return
    st.session_state[SESSION_KEY_DEMO_ENABLED] = bool(value)


def get_session_draft(default: Dict[str, Any]) -> Dict[str, Any]:
    if st is None:
        return copy.deepcopy(default)
    draft = st.session_state.get(SESSION_KEY_DRAFT)
    if isinstance(draft, dict):
        return copy.deepcopy(draft)
    st.session_state[SESSION_KEY_DRAFT] = copy.deepcopy(default)
    return copy.deepcopy(default)


def set_session_draft(data: Dict[str, Any]) -> None:
    if st is None:
        return
    st.session_state[SESSION_KEY_DRAFT] = copy.deepcopy(data)


def clear_session_toggle() -> None:
    if st is None:
        return
    if SESSION_KEY_DEMO_ENABLED in st.session_state:
        del st.session_state[SESSION_KEY_DEMO_ENABLED]
