# ReDNACoreDemo/core/redna_core.py
from __future__ import annotations
import math
from typing import Any, Dict, List, Tuple
from .schemas import EvidenceItem, ObservationItem, ResolveOut
from . import hierarchy
from .arbitration import choose_best
from .priority import priority_score, trait_importance_for


def _normalize_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return str(value)


def _normalize_ucn_value(ucn: float) -> float:
    if ucn > 1.0:
        return max(0.0, min(ucn / 100.0, 1.0))
    return max(0.0, min(ucn, 1.0))


def _denormalize_ucn_value(norm: float, reference: float) -> float:
    if reference > 1.0:
        return max(0.0, min(norm * 100.0, 100.0))
    return max(0.0, min(norm, 1.0))


def _extract_trust(provenance: Dict[str, Any]) -> float:
    if not isinstance(provenance, dict):
        return 0.6
    candidates = []
    for key in ("trust", "source_trust", "trust_score", "confidence", "confidence_weight"):
        if key in provenance:
            candidates.append(provenance.get(key))
    meta = provenance.get("meta")
    if isinstance(meta, dict):
        for key in ("trust", "source_trust", "trust_score", "confidence", "confidence_weight"):
            if key in meta:
                candidates.append(meta.get(key))
    for candidate in candidates:
        try:
            trust = float(candidate)
        except (TypeError, ValueError):
            continue
        if math.isfinite(trust):
            return max(0.0, min(trust, 1.0))
    return 0.6


def _safe_source(provenance: Dict[str, Any]) -> str:
    if not isinstance(provenance, dict):
        return "unknown"
    source = provenance.get("source") or provenance.get("channel")
    if isinstance(source, str) and source.strip():
        return source.strip()
    meta = provenance.get("meta")
    if isinstance(meta, dict):
        channel = meta.get("source") or meta.get("channel")
        if isinstance(channel, str) and channel.strip():
            return channel.strip()
    return "unknown"


def _conflict_severity(trust: float, conflicting_ucn: float, existing_ucn: float) -> Tuple[str, float]:
    conflicting_norm = _normalize_ucn_value(conflicting_ucn)
    existing_norm = _normalize_ucn_value(existing_ucn)
    if conflicting_norm >= max(existing_norm, 0.75):
        return "critical", 0.3
    if conflicting_norm >= 0.5:
        return "moderate", 0.2
    return "minor", 0.1


def _evidence_type_from_source(source: str) -> str:
    token = source.strip().lower()
    if not token:
        return "self"
    if "partner" in token or "spouse" in token:
        return "partner"
    if "device" in token or "sensor" in token:
        return "device"
    if "app" in token or "import" in token or "bundle" in token:
        return "app"
    if "coach" in token:
        return "app"
    return "self"

def build_observations(bundle_items: List[EvidenceItem]) -> List[ObservationItem]:
    obs: List[ObservationItem] = []
    for ev in bundle_items:
        # only accept traits the Core knows about (or umbrella placeholders)
        t = ev.get("trait")
        if not t:
            continue
        if t not in hierarchy.all_trait_keys() and not any(t.startswith(fam + ".") for fam in hierarchy.REGISTRY):
            continue
        try:
            confidence = float(ev.get("ucn", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if not math.isfinite(confidence) or confidence < 0.0:
            confidence = 0.0
        provenance: EvidenceItem = dict(ev)
        provenance.setdefault("kind", "observation")
        provenance.setdefault("meta", {})
        obs.append(
            {
                "trait": t,
                "value": ev.get("value"),
                "ucn": confidence,
                "provenance": provenance,
            }
        )
    return obs

def resolve_traits(
    prior_resolved: Dict[str, Any],
    prior_evidence: Dict[str, Any],
    prior_obs: Dict[str, Any],
    new_obs: List[ObservationItem],
) -> ResolveOut:
    # merge new evidence/observations
    evidence_items = list(prior_evidence.get("items", [])) + [o["provenance"] for o in new_obs]
    prior_obs_items = list(prior_obs.get("items", [])) if isinstance(prior_obs.get("items"), list) else []
    obs_items = prior_obs_items + new_obs

    prior_obs_log = prior_obs.get("by_trait") if isinstance(prior_obs.get("by_trait"), dict) else {}
    obs_log: Dict[str, List[Dict[str, Any]]] = {
        trait: list(entries) if isinstance(entries, list) else []
        for trait, entries in prior_obs_log.items()
    }

    # group observations by trait
    by_trait: Dict[str, List[ObservationItem]] = {}
    for o in obs_items:
        trait = o.get("trait")
        if not trait:
            continue
        by_trait.setdefault(trait, []).append(o)

    # append new observations to log (keep last 25 per trait)
    for obs in new_obs:
        trait = obs.get("trait")
        if not trait:
            continue
        provenance = obs.get("provenance", {}) or {}
        meta = provenance.get("meta") or {}
        entry = {
            "value": obs.get("value"),
            "ucn": obs.get("ucn"),
            "ts": provenance.get("when") or meta.get("ts"),
            "source": provenance.get("source"),
            "meta": meta,
        }
        bucket = obs_log.setdefault(trait, [])
        bucket.append(entry)
        if len(bucket) > 25:
            obs_log[trait] = bucket[-25:]

    # arbitrate each trait
    resolved: Dict[str, Any] = {}
    priorities: Dict[str, float] = {}
    conflicts: Dict[str, Dict[str, Any]] = {}
    ucn_changes: Dict[str, Dict[str, Any]] = {}
    for trait, group in by_trait.items():
        val, ucn, reasons = choose_best([g["provenance"] for g in group])
        if val is None:
            continue
        resolved_entry = {
            "resolved_value": val if isinstance(val, (str, int, float, bool)) else val,
            "ucn": ucn,
            "reasons": reasons,
        }
        recent_log = obs_log.get(trait, [])
        if recent_log:
            resolved_entry["observations"] = recent_log[-5:]
            resolved_entry["last_observed"] = recent_log[-1].get("ts")
        prior_entry = prior_resolved.get(trait) if isinstance(prior_resolved.get(trait), dict) else {}
        resolved[trait] = resolved_entry
        # curiosity/system-need heuristic: lower UCN ⇒ higher priority
        rr = ucn / 100.0 if ucn > 1.0 else ucn
        rr = max(0.0, min(1.0, rr))
        contradiction = "conflict_detected" in reasons
        importance = trait_importance_for(trait)
        priorities[trait] = priority_score(rr, importance, contradiction)

        existing_value = prior_entry.get("resolved_value") if isinstance(prior_entry, dict) else None
        if existing_value is not None:
            conflicting_candidates = []
            for obs in group:
                obs_value = obs.get("value")
                if obs_value is None:
                    continue
                if _normalize_value(obs_value) != _normalize_value(existing_value):
                    conflicting_candidates.append(obs)

            if conflicting_candidates:
                top_conflict = max(
                    conflicting_candidates,
                    key=lambda item: _normalize_ucn_value(float(item.get("ucn", 0.0)))
                )
                provenance = top_conflict.get("provenance") if isinstance(top_conflict.get("provenance"), dict) else {}
                trust = _extract_trust(provenance)
                source = _safe_source(provenance)
                conflicting_ucn = float(top_conflict.get("ucn", 0.0))
                severity_label, severity_factor = _conflict_severity(trust, conflicting_ucn, ucn)
                reduction = severity_factor * (1.0 - trust)

                before_ucn = resolved_entry.get("ucn", 0.0)
                before_norm = _normalize_ucn_value(before_ucn)
                after_norm = max(0.0, before_norm * (1.0 - reduction))
                resolved_entry["ucn"] = _denormalize_ucn_value(after_norm, before_ucn)
                resolved_entry["needs_validation"] = True
                resolved_entry.setdefault("validation_notes", []).append("contradiction")
                resolved_entry["conflict"] = {
                    "severity": severity_label,
                    "severity_factor": round(severity_factor, 4),
                    "source_trust": round(trust, 4),
                    "incoming_value": top_conflict.get("value"),
                    "existing_value": existing_value,
                    "source": source,
                    "reduction": round(reduction, 4),
                    "ucn_before": before_ucn,
                    "ucn_after": resolved_entry["ucn"],
                }
                conflicts[trait] = {
                    "severity": severity_label,
                    "severity_factor": round(severity_factor, 4),
                    "source_trust": round(trust, 4),
                    "incoming_value": top_conflict.get("value"),
                    "existing_value": existing_value,
                    "source": source,
                    "reduction": round(reduction, 4),
                    "ucn_before": before_ucn,
                    "ucn_after": resolved_entry["ucn"],
                }

        before_ucn = float(prior_entry.get("ucn", 0.0)) if isinstance(prior_entry, dict) else 0.0
        after_ucn = float(resolved_entry.get("ucn", 0.0))
        if abs(after_ucn - before_ucn) > 1e-6 or trait in conflicts or not prior_entry:
            winning_obs = None
            best_ucn = -1.0
            for obs in group:
                if _normalize_value(obs.get("value")) == _normalize_value(val):
                    try:
                        obs_ucn = float(obs.get("ucn", 0.0))
                    except (TypeError, ValueError):
                        obs_ucn = 0.0
                    if obs_ucn > best_ucn:
                        best_ucn = obs_ucn
                        winning_obs = obs
            provenance = winning_obs.get("provenance") if isinstance(winning_obs, dict) else {}
            source = _safe_source(provenance) if isinstance(provenance, dict) else "unknown"
            trust = _extract_trust(provenance) if isinstance(provenance, dict) else 0.6
            ucn_changes[trait] = {
                "before_ucn": before_ucn,
                "after_ucn": after_ucn,
                "source": source,
                "source_trust": trust,
                "evidence_type": _evidence_type_from_source(source),
                "provenance": provenance,
            }

    # make sure every known trait appears at least with null (for “wide table”)
    for key in hierarchy.all_trait_keys():
        resolved.setdefault(key, {"resolved_value": None, "ucn": 0, "reasons": ["unknown"]})
        bucket = obs_log.get(key, [])
        if key in resolved and bucket:
            if "observations" not in resolved[key]:
                resolved[key]["observations"] = bucket[-5:]
            resolved[key]["last_observed"] = bucket[-1].get("ts")
        priorities.setdefault(key, 0.0)

    observations_payload = {"items": obs_items, "by_trait": obs_log}

    return {
        "resolved": resolved,
        "priorities": priorities,
        "conflicts": conflicts,
        "ucn_changes": ucn_changes,
    }, {"items": evidence_items}, observations_payload
