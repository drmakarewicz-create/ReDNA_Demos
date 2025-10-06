# UCN_RR_Demo/ucn_rr.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

# --------------------------------------------------------------------
# Deterministic scoring & helpers (kept intentionally simple + robust)
# --------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def summarize_paths_present(core_snapshot: Dict[str, Any]) -> List[List[str]]:
    """
    Extract list of dna_path components from the Core snapshot.
    Expected Core snapshot to contain evidence or traits keyed by dna_path.
    This is tolerant to different shapes: either a top-level 'evidence' list
    or a dict of 'traits' with dna_path keys.
    """
    paths: List[List[str]] = []
    ev = (core_snapshot.get("evidence") or [])
    if isinstance(ev, list):
        for row in ev:
            p = (row or {}).get("dna_path")
            if isinstance(p, str):
                paths.append(p.split("."))
    traits = (core_snapshot.get("traits") or {})
    if isinstance(traits, dict):
        for k in traits.keys():
            if isinstance(k, str):
                paths.append(k.split("."))
    # de-duplicate
    uniq = []
    seen = set()
    for p in paths:
        k = tuple(p)
        if k not in seen:
            uniq.append(p)
            seen.add(k)
    return uniq

def _aggregate_ucn(core_snapshot: Dict[str, Any]) -> Dict[str, float]:
    """
    Build a per_dna UCN map deterministically:
    - Start from any 'traits' with explicit scores if present.
    - Otherwise, derive from evidence confidence*weight (clipped and scaled).
    """
    per: Dict[str, float] = {}

    traits = (core_snapshot.get("traits") or {})
    if isinstance(traits, dict):
        for path, obj in traits.items():
            if isinstance(obj, dict) and "ucn" in obj:
                try:
                    per[path] = float(obj["ucn"])
                except Exception:
                    pass

    ev = (core_snapshot.get("evidence") or [])
    for row in ev if isinstance(ev, list) else []:
        path = (row or {}).get("dna_path")
        if not isinstance(path, str):
            continue
        conf = float((row or {}).get("confidence", 0.5))
        w = float((row or {}).get("weight", 1.0))
        # crude deterministic mapping to UCN contribution
        contrib = max(0.0, min(1.0, conf)) * max(0.1, min(2.0, w)) * 400.0  # 0..800
        per[path] = max(per.get(path, 200.0), min(1000.0, contrib + 200.0))  # floor ~200

    # ensure 0..1000
    for k, v in list(per.items()):
        per[k] = max(0.0, min(1000.0, float(v)))

    return per

def _top_level_aggregate(per: Dict[str, float]) -> Dict[str, float]:
    agg: Dict[str, List[float]] = {}
    for path, u in per.items():
        top = path.split(".")[0]
        agg.setdefault(top, []).append(float(u))
    return {k: sum(v)/len(v) for k, v in agg.items()}

def _overall_ucn(per: Dict[str, float]) -> float:
    if not per:
        return 0.0
    return sum(per.values()) / len(per)

def _rr_percentile(overall_ucn: float, preset: str = "Normal") -> float:
    k_map = {"Easy": 12.0, "Normal": 14.0, "Hard": 16.0}
    x0_map = {"Easy": 0.35, "Normal": 0.50, "Hard": 0.60}
    k = k_map.get(preset, 14.0)
    x0 = x0_map.get(preset, 0.50)
    x = overall_ucn / 1000.0
    import math
    return 100.0 / (1.0 + math.e ** (-k * (x - x0)))

def _gaps(per: Dict[str, float]) -> Dict[str, Any]:
    # raw curiosity = 1000 - UCN
    raw = sorted([(k, 1000.0 - v) for k, v in per.items()], key=lambda x: x[1], reverse=True)[:8]
    # weighted minimal stub: importance defaults to 0.7, staleness 1.0
    weighted = []
    for k, cur in raw:
        weighted.append({
            "dna_path": k,
            "weighted_score": cur * 0.7 * 1.0,
            "curiosity": cur,
            "importance": 0.7,
            "staleness": 1.0,
            "reason": "stale or low certainty"
        })
    return {
        "raw_curiosity": raw,
        "top_weighted": weighted[:5],
        "agenda_items": ["Collect one fresh, high-cred signal on top gaps."]
    }

def _contradictions(core_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Look for contradictory evidence on the same dna_path (values near 0 and near 1).
    """
    out: List[Dict[str, Any]] = []
    by_path: Dict[str, List[float]] = {}
    for row in (core_snapshot.get("evidence") or []):
        if not isinstance(row, dict):
            continue
        p = row.get("dna_path")
        v = row.get("value")
        if isinstance(p, str) and isinstance(v, (int, float)):
            by_path.setdefault(p, []).append(float(v))
    for p, vals in by_path.items():
        if not vals:
            continue
        lo = min(vals)
        hi = max(vals)
        if hi - lo >= 0.6:
            out.append({"dna_path": p, "values": [lo, hi], "agenda": "Resolve spread with targeted check."})
    return out

def _evidence_meta_from_core(core_snapshot: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build results.evidence_meta: { dna_path: [ {observed_at, provenance{credibility_tier, source, method}}, ... ] }
    """
    by_path: Dict[str, List[Dict[str, Any]]] = {}
    for row in (core_snapshot.get("evidence") or []):
        if not isinstance(row, dict):
            continue
        p = row.get("dna_path")
        if not isinstance(p, str):
            continue
        prov = (row.get("provenance") or {}) if isinstance(row.get("provenance"), dict) else {}
        entry = {
            "observed_at": row.get("observed_at") or row.get("timestamp") or None,
            "provenance": {
                "credibility_tier": prov.get("credibility_tier") or prov.get("tier") or "unverified",
                "source": prov.get("source") or "Core",
                "method": prov.get("method") or "import",
            }
        }
        by_path.setdefault(p, []).append(entry)
    return by_path

# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------
def compute_all(core_snapshot: Dict[str, Any], rr_preset: str = "Normal") -> Dict[str, Any]:
    per = _aggregate_ucn(core_snapshot)
    top = _top_level_aggregate(per)
    overall = _overall_ucn(per)
    rr = _rr_percentile(overall, preset=rr_preset)
    gaps = _gaps(per)
    contr = _contradictions(core_snapshot)
    return {
        "schema_version": "ucnrr.demo/1.4",
        "ucn": {
            "per_dna": per,
            "top_level": top,
            "overall": overall,
        },
        "curiosity": {"overall": max(0.0, 1000.0 - overall)},
        "rr": {"overall": rr},
        "gaps": gaps,
        "contradictions": contr,
        "meta": {"difficulty": rr_preset, "calculated_at": _now_iso()},
    }

def make_explorer_bundle(
    core_snapshot: Dict[str, Any],
    results: Dict[str, Any],
    difficulty: str,
    calculated_at: str,
    include_evidence_meta: bool = True,
) -> Dict[str, Any]:
    paths = summarize_paths_present(core_snapshot)
    bundle = {
        "schema_version": "explorer.bundle/1.0",
        "source": {"core_schema": core_snapshot.get("schema_version", "core/3.1"),
                   "ucnrr_schema": results.get("schema_version", "ucnrr.demo/1.4")},
        "identity": core_snapshot.get("identity", {}),
        "paths_present": paths,
        "results": dict(results),
        "notes": f"Exported at {calculated_at}",
    }
    if include_evidence_meta:
        bundle["results"]["evidence_meta"] = _evidence_meta_from_core(core_snapshot)
    # ensure meta.difficulty
    bundle["results"]["meta"] = bundle["results"].get("meta", {})
    bundle["results"]["meta"]["difficulty"] = difficulty
    bundle["results"]["meta"]["calculated_at"] = calculated_at
    return bundle

def recompute_with_delta(core_snapshot: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply an Explorer delta:
      { schema_version: "explorer.delta/1.0", suggested_evidence: [ {dna_path, value, confidence, weight, provenance, observed_at?}, ... ] }
    Deterministic effect:
      - Append evidence rows to Core snapshot.
      - No mutation of past evidence (append-only).
    """
    if not isinstance(core_snapshot, dict):
        raise ValueError("core_snapshot must be an object")
    ev_list = core_snapshot.setdefault("evidence", [])
    if not isinstance(ev_list, list):
        core_snapshot["evidence"] = ev_list = []

    sug = (delta or {}).get("suggested_evidence") or []
    for row in sug:
        if not isinstance(row, dict):
            continue
        p = row.get("dna_path")
        if not isinstance(p, str):
            continue
        ev_list.append({
            "dna_path": p,
            "value": float(row.get("value", 0.5)) if isinstance(row.get("value"), (int, float)) else 0.5,
            "confidence": float(row.get("confidence", 0.6)),
            "weight": float(row.get("weight", 1.0)),
            "observed_at": row.get("observed_at"),
            "provenance": (row.get("provenance") or {}),
            "notes": row.get("notes", "explorer_delta"),
        })
    # Update an updated_at marker
    core_snapshot["updated_at"] = _now_iso()
    return core_snapshot