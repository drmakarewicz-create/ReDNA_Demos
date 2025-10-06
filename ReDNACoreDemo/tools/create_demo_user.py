"""Generate synthetic demo users at varying refinement stages."""

from __future__ import annotations

import argparse
import json
import random
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ReDNACoreDemo.core.bundles import CURRENT_SCHEMA, CURRENT_VERSION, iso_now

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "demo_users"


@dataclass
class Scenario:
    name: str
    resolved: Dict[str, Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]


def _rand_token(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _base_meta(user_id: str, profile: str) -> Dict[str, Any]:
    return {
        "version": CURRENT_VERSION,
        "schema": CURRENT_SCHEMA,
        "generated_at": iso_now(),
        "user_id": user_id,
        "profile": profile,
    }


def _just_onboarded() -> Scenario:
    resolved = {
        "Onboarding.State": {
            "resolved_value": "just_started",
            "ucn": 45,
            "reasons": ["self_report@45"],
        },
        "PaDNA.HairDNA.Style": {"resolved_value": None, "ucn": 0, "reasons": ["unknown"]},
    }
    evidence = [
        {
            "trait": "Onboarding.State",
            "value": "just_started",
            "ucn": 45,
            "source": "onboarding_form",
        }
    ]
    return Scenario("just_onboarded", resolved, evidence, [])


def _moderately_refined() -> Scenario:
    resolved = {
        "PaDNA.HairDNA.Style": {
            "resolved_value": "Wavy",
            "ucn": 78,
            "reasons": ["photo_ai@78"],
        },
        "PaDNA.SkinDNA.Tone": {
            "resolved_value": "olive",
            "ucn": 65,
            "reasons": ["photo_ai@65"],
        },
        "PsyDNA.PersonalityDNA.Big5.Openness": {
            "resolved_value": "high",
            "ucn": 52,
            "reasons": ["self_report@52"],
        },
    }
    evidence = [
        {"trait": "PaDNA.HairDNA.Style", "value": "Wavy", "ucn": 78, "source": "photo_ai"},
        {"trait": "PaDNA.SkinDNA.Tone", "value": "olive", "ucn": 65, "source": "photo_ai"},
        {
            "trait": "PsyDNA.PersonalityDNA.Big5.Openness",
            "value": "high",
            "ucn": 52,
            "source": "self_report",
        },
    ]
    observations: List[Dict[str, Any]] = []
    return Scenario("moderately_refined", resolved, evidence, observations)


def _highly_refined() -> Scenario:
    resolved = {
        "PaDNA.HairDNA.Style": {
            "resolved_value": "Locs",
            "ucn": 92,
            "reasons": ["expert_review@92"],
        },
        "PaDNA.HairDNA.Length": {
            "resolved_value": "Long",
            "ucn": 90,
            "reasons": ["photo_ai@90"],
        },
        "PaDNA.BodyDNA.Height": {
            "resolved_value": "5'9\"",
            "ucn": 88,
            "reasons": ["self_report@88"],
        },
        "PsyDNA.PersonalityDNA.Big5.Conscientiousness": {
            "resolved_value": "very_high",
            "ucn": 70,
            "reasons": ["coach_inference@70"],
        },
        "BehDNA.Rituals.Morning": {
            "resolved_value": "mindfulness_walk",
            "ucn": 63,
            "reasons": ["coach_inference@63"],
        },
    }
    evidence = [
        {"trait": "PaDNA.HairDNA.Style", "value": "Locs", "ucn": 92, "source": "expert_review"},
        {"trait": "PaDNA.HairDNA.Length", "value": "Long", "ucn": 90, "source": "photo_ai"},
        {"trait": "PaDNA.BodyDNA.Height", "value": "5'9\"", "ucn": 88, "source": "self_report"},
        {
            "trait": "PsyDNA.PersonalityDNA.Big5.Conscientiousness",
            "value": "very_high",
            "ucn": 70,
            "source": "coach_inference",
        },
        {
            "trait": "BehDNA.Rituals.Morning",
            "value": "mindfulness_walk",
            "ucn": 63,
            "source": "coach_inference",
        },
    ]
    observations = [
        {
            "container": "conversational_dynamics",
            "trait": "conversation.cadence",
            "value": "steady",
            "ucn": 35,
        }
    ]
    return Scenario("highly_refined", resolved, evidence, observations)


def _contradiction_overlay() -> Scenario:
    resolved = {
        "PsyDNA.RelationshipDNA.AttachmentStyle": {
            "resolved_value": "anxious",
            "ucn": 42,
            "reasons": ["self_report@42", "partner_report@38"],
        }
    }
    evidence = [
        {"trait": "PsyDNA.RelationshipDNA.AttachmentStyle", "value": "anxious", "ucn": 42, "source": "self_report"},
        {"trait": "PsyDNA.RelationshipDNA.AttachmentStyle", "value": "secure", "ucn": 38, "source": "partner_report"},
    ]
    return Scenario("contradiction", resolved, evidence, [])


def _sarcasm_overlay() -> Scenario:
    observations = [
        {
            "container": "communication_tone",
            "trait": "tone.sarcasm_markers",
            "value": "sarcasm=high",
            "ucn": 40,
        }
    ]
    return Scenario("sarcasm", {}, [], observations)


def _photogenic_overlay() -> Scenario:
    resolved = {
        "PaDNA.PhotoEvaluations.Score": {
            "resolved_value": "high",
            "ucn": 75,
            "reasons": ["photo_ai@75"],
        }
    }
    evidence = [
        {"trait": "PaDNA.PhotoEvaluations.Score", "value": "high", "ucn": 75, "source": "photo_ai"}
    ]
    return Scenario("photogenic", resolved, evidence, [])


PRIMARY_PROFILES = {
    "just_onboarded": _just_onboarded,
    "moderately_refined": _moderately_refined,
    "highly_refined": _highly_refined,
}

OVERLAYS = {
    "contradiction": _contradiction_overlay,
    "sarcasm": _sarcasm_overlay,
    "photogenic": _photogenic_overlay,
}


def build_bundle(user_id: str, profile: str, overlays: List[str]) -> Dict[str, Any]:
    base_scenario = PRIMARY_PROFILES[profile]()
    resolved = dict(base_scenario.resolved)
    evidence = list(base_scenario.evidence)
    observations = list(base_scenario.observations)

    applied_overlays = []
    for overlay_name in overlays:
        builder = OVERLAYS.get(overlay_name)
        if not builder:
            continue
        overlay = builder()
        applied_overlays.append(overlay.name)
        resolved.update(overlay.resolved)
        evidence.extend(overlay.evidence)
        observations.extend(overlay.observations)

    bundle = {
        "meta": _base_meta(user_id, profile),
        "resolved": resolved,
        "evidence": {"items": evidence},
        "observations": {"items": observations, "by_trait": {}},
    }
    if applied_overlays:
        bundle["meta"]["overlays"] = applied_overlays
    return bundle


def write_bundle(bundle: Dict[str, Any]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    user_id = bundle["meta"]["user_id"]
    filename = f"{user_id}.json"
    path = DATA_DIR / filename
    path.write_text(json.dumps(bundle, indent=2))
    return path


def create_users(profile: str, count: int, overlays: List[str], customizable_id: str | None = None) -> List[Path]:
    paths: List[Path] = []
    for idx in range(count):
        suffix = customizable_id or _rand_token()
        user_id = f"demo_{profile}_{suffix}" if count == 1 else f"demo_{profile}_{suffix}_{idx+1}"
        bundle = build_bundle(user_id, profile, overlays)
        paths.append(write_bundle(bundle))
    return paths


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create synthetic demo users")
    parser.add_argument("--profile", choices=list(PRIMARY_PROFILES.keys()), required=True)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument(
        "--overlay",
        action="append",
        choices=list(OVERLAYS.keys()),
        help="Optional overlay scenarios (may be specified multiple times)",
    )
    parser.add_argument("--custom-id", help="Optional base id token to use when generating a single user")

    args = parser.parse_args(argv)

    if args.custom_id and args.count != 1:
        parser.error("--custom-id may only be used when --count=1")

    overlays = args.overlay or []
    paths = create_users(args.profile, max(args.count, 1), overlays, customizable_id=args.custom_id)
    print(f"Generated {len(paths)} bundle(s):")
    for path in paths:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
