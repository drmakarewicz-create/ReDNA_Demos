from __future__ import annotations
from typing import Dict, Any, List, Tuple, DefaultDict
from collections import defaultdict
from math import exp

from src.vision.model import VisionObservation, RecencyTag
from src.scoring.ucn_policy import RECENCY_WEIGHTS, confidence_to_ucn
from src.vision.mapping import map_observation_to_descriptors

def aggregate_observations(observations: List[VisionObservation], prior_bundle: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Multi-photo aggregation with:
      - recency-weighted voting (confidence * recency_weight)
      - diminishing returns curve for UCN
      - contradiction flags when runner-up nearly ties winner
      - optional prior bundle ignored in this pass (hook kept for future incremental merges)
    """
    votes: DefaultDict[str, List[Tuple[str, float, float, str]]] = defaultdict(list)
    payloads_per_path: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)

    for obs in observations:
        desc = map_observation_to_descriptors(obs)
        w = RECENCY_WEIGHTS[obs.recency.value if hasattr(obs.recency, "value") else str(obs.recency)]
        for path, payload in desc.items():
            val = payload.get("value")
            if val is None:  # skip empties
                continue
            conf = float(payload.get("conf", payload.get("confidence", 0.6)))
            votes[path].append((val, conf, w, obs.image_id))
            payloads_per_path[path].append(payload)

    descriptors: Dict[str, Dict[str, Any]] = {}
    ucn_per_dna: Dict[str, float] = {}
    contradictions: List[Dict[str, Any]] = []
    agenda = {"top_weighted": [], "raw_curiosity": [], "agenda_items": []}
    curves: List[Dict[str, Any]] = []

    for path, items in votes.items():
        # Recency*confidence weighted evidence per token
        weight_per_token: DefaultDict[str, float] = defaultdict(float)
        recency_weight_sum = 0.0
        for token, conf, w, _ in items:
            weight_per_token[token] += conf * w
            recency_weight_sum += w

        # Determine winner / runner
        sorted_tokens = sorted(weight_per_token.items(), key=lambda kv: kv[1], reverse=True)
        winner, win_score = sorted_tokens[0]
        runner_score = sorted_tokens[1][1] if len(sorted_tokens) > 1 else 0.0
        total = sum(weight_per_token.values()) + 1e-9

        # Contradiction if close competition
        if runner_score / max(1e-6, win_score) > 0.8:
            contradictions.append({
                "dna_path": path,
                "candidates": [{"value": v, "score": s} for v, s in sorted_tokens[:3]],
                "reason": "runner within 80% of winner"
            })

        # Confidence proxy = normalized win mass
        conf_proxy = max(0.1, min(1.0, win_score / total))
        support_n = len(items)

        ucn = confidence_to_ucn(conf_proxy, support_n, recency_weight_sum)
        chosen_payload = next((p for p in payloads_per_path[path] if p.get("value") == winner), None)
        details = (chosen_payload or {}).get("details", {})
        descriptors[path] = {"value": winner, "ucn": ucn, "details": details}
        ucn_per_dna[path] = ucn

        # Simple visual refinement curve (monotonic easing toward final)
        for n in range(1, max(2, support_n) + 1):
            frac = n / max(1, support_n)
            curves.append({"trait": path, "n_photos": n, "ucn": ucn * frac})

        agenda["raw_curiosity"].append([path, 1000.0 - ucn])

    # Gaps (lowest UCN first)
    def gap_weight(u): return (1000.0 - u) * 0.7
    top_paths = sorted(ucn_per_dna, key=lambda k: ucn_per_dna[k])[:5]
    agenda["top_weighted"] = [
        {"dna_path": p, "weighted_score": gap_weight(ucn_per_dna[p]),
         "curiosity": 1000.0 - ucn_per_dna[p], "importance": 0.7, "staleness": 1.0,
         "reason": "low certainty; add diverse photos"}
        for p in top_paths
    ]
    agenda["agenda_items"] = ["Use different lighting/angles; include RECENT photos for top gaps."]

    overall_ucn = sum(ucn_per_dna.values()) / max(1, len(ucn_per_dna))
    return {
        "descriptors": descriptors,
        "ucn_per_dna": ucn_per_dna,
        "overall_ucn": overall_ucn,
        "curiosity_overall": 1000.0 - overall_ucn,
        "contradictions": contradictions,
        "agenda": agenda,
        "ucn_curve": curves
    }
