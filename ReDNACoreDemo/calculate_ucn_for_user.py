"""
Calculate UCN/RR for a user from their observations.

This script integrates the UCN/RR engine with existing user data:
1. Load observations from observations.json
2. Convert to EvidenceSource objects
3. Calculate UCN for all traits
4. Calculate RR for the user
5. Generate Curiosity signals
6. Save results to UCN report
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from pprint import pprint

# Add ucn_rr_engine to path
sys.path.insert(0, str(Path(__file__).parent))

from ucn_rr_engine import (
    UCNCalculator,
    RRCalculator,
    CuriosityEngine,
    EvidenceSource,
    SourceType,
    ProvenanceLogger,
    AttemptType,
    AttemptStatus
)


def load_observations(user_id: str, data_dir: Path = None) -> dict:
    """Load observations for a user."""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data" / "users"

    user_dir = data_dir / user_id
    obs_file = user_dir / f"{user_id}_observations.json"

    if not obs_file.exists():
        raise FileNotFoundError(f"Observations file not found: {obs_file}")

    with open(obs_file, 'r') as f:
        return json.load(f)


def convert_observation_to_evidence(
    obs: dict,
    default_provenance: dict,
    user_id: str
) -> EvidenceSource:
    """
    Convert an observation to an EvidenceSource.

    Observations have:
    - path: trait path
    - value: observed value
    - confidence: 0.0-1.0
    - notes: observation notes

    Default provenance has:
    - source: type (e.g., "reference_photo_analysis")
    - timestamp: date
    - photo_count: number of photos
    - analyst: who made observation
    """
    trait_path = obs['path']
    value = obs['value']
    confidence = obs.get('confidence', 0.8)
    notes = obs.get('notes', '')

    # Determine source type based on provenance
    source = default_provenance.get('source', 'manual_observation')
    photo_count = default_provenance.get('photo_count', 0)

    if 'photo' in source.lower() and photo_count >= 3:
        source_type = SourceType.PHOTO_SERIES
    elif 'photo' in source.lower():
        source_type = SourceType.PHOTO_SINGLE
    elif 'manual' in source.lower() or 'analyst' in source.lower():
        source_type = SourceType.AI_ANALYSIS  # Manual analysis by analyst
    else:
        source_type = SourceType.SELF_REPORT_STRUCTURED

    # Parse timestamp
    timestamp_str = default_provenance.get('timestamp', datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except:
        timestamp = datetime.now()

    # Quality metadata based on confidence and photo analysis
    quality_metadata = {
        'resolution': 'high' if confidence >= 0.9 else 'medium' if confidence >= 0.7 else 'low',
        'lighting': 'good' if confidence >= 0.85 else 'fair',
        'angle': 'multiple' if photo_count >= 5 else 'frontal',
        'analyst_confidence': confidence,
        'notes': notes
    }

    # Generate source ID
    source_id = f"{user_id}_{source}_{trait_path.replace('.', '_')}"

    return EvidenceSource(
        source_type=source_type,
        value=value,
        timestamp=timestamp,
        source_id=source_id,
        quality_metadata=quality_metadata
    )


def calculate_ucn_for_user(
    user_id: str,
    data_dir: Path = None,
    verbose: bool = True
) -> dict:
    """
    Calculate UCN/RR for a user.

    Returns:
        Dictionary with ucn_results, rr_info, curiosity_summary
    """
    # Load observations
    obs_data = load_observations(user_id, data_dir)
    observations = obs_data['observations']
    default_provenance = obs_data.get('default_provenance', {})

    if verbose:
        print(f"\n{'='*80}")
        print(f"CALCULATING UCN/RR FOR USER: {user_id}")
        print(f"{'='*80}")
        print(f"Loaded {len(observations)} observations")
        print(f"Provenance: {default_provenance.get('source', 'unknown')}")
        print(f"Photos: {default_provenance.get('photo_count', 0)}")

    # Group observations by trait path
    trait_evidence = {}
    for obs in observations:
        trait_path = obs['path']
        if trait_path not in trait_evidence:
            trait_evidence[trait_path] = []

        evidence = convert_observation_to_evidence(obs, default_provenance, user_id)
        trait_evidence[trait_path].append(evidence)

    # Calculate UCN for each trait
    ucn_calc = UCNCalculator()
    provenance_logger = ProvenanceLogger()

    ucn_results = {}
    user_traits = {}  # {trait_path: ucn}

    if verbose:
        print(f"\n{'='*80}")
        print("CALCULATING UCN FOR EACH TRAIT")
        print(f"{'='*80}")

    for trait_path, evidence_list in trait_evidence.items():
        # Calculate UCN
        result = ucn_calc.calculate(
            trait_path=trait_path,
            evidence_list=evidence_list,
            user_metadata={'age': 30}  # TODO: Get from user profile
        )

        ucn_results[trait_path] = result
        user_traits[trait_path] = result['ucn']

        # Log to provenance
        for evidence in evidence_list:
            provenance_logger.log_attempt(
                user_id=user_id,
                trait_path=trait_path,
                attempt_type=AttemptType.PHOTO_UPLOAD if evidence.source_type in [SourceType.PHOTO_SINGLE, SourceType.PHOTO_SERIES] else AttemptType.AI_ANALYSIS,
                attempt_status=AttemptStatus.SUCCESS,
                source_type=evidence.source_type.value,
                source_id=evidence.source_id,
                evidence_quality=evidence.quality_metadata.get('analyst_confidence', 0.8),
                extracted_value=evidence.value,
                ucn_after=result['ucn']
            )

        if verbose:
            print(f"\n{trait_path}")
            print(f"  Value: {result['value']}")
            print(f"  UCN: {result['ucn']} ({result['confidence_level']})")
            print(f"  Evidence: {result['evidence_count']} sources")
            if result['contradictions']:
                print(f"  ⚠️  Contradictions: {len(result['contradictions'])}")

    # Calculate RR
    rr_calc = RRCalculator()
    rr_info = rr_calc.get_rr_info(user_id=user_id, user_traits=user_traits)

    if verbose:
        print(f"\n{'='*80}")
        print("REFINEMENT RANK (RR)")
        print(f"{'='*80}")
        print(f"RR: {rr_info['rr']} percentile")
        print(f"Average UCN: {rr_info['average_ucn']}")
        print(f"Trait Count: {rr_info['trait_count']}")
        print(f"Gates Passed: {', '.join(rr_info['gates_passed'])}")
        if rr_info['milestones_achieved']:
            print(f"Milestones: {', '.join(rr_info['milestones_achieved'])}")

    # Generate Curiosity signals
    curiosity_engine = CuriosityEngine()
    curiosity_summary = curiosity_engine.get_curiosity_summary(
        rr=rr_info['rr'],
        user_traits=user_traits
    )

    if verbose:
        print(f"\n{'='*80}")
        print("CURIOSITY SIGNALS")
        print(f"{'='*80}")
        print(f"Overall Curiosity: {curiosity_summary['overall_curiosity']}")
        print(f"Curiosity Level: {curiosity_summary['curiosity_level']}")

        budget = curiosity_summary['budget_allocation']
        print(f"\nStrategy: {budget['strategy']}")
        print(f"Focus: {budget['focus']}")
        print(f"Max Concurrent Actions: {budget['max_concurrent_actions']}")

        print(f"\nTrait Priority Breakdown:")
        for priority, count in budget['trait_breakdown'].items():
            if count > 0:
                print(f"  {priority}: {count}")

        print(f"\nTop 5 Priority Traits for Refinement:")
        for i, signal in enumerate(curiosity_summary['trait_signals'][:5], 1):
            print(f"\n{i}. {signal['trait_path']}")
            print(f"   UCN: {signal['ucn']} | Priority: {signal['priority']}")
            print(f"   → {signal['suggested_action']}")

    # Analyze user behavior from provenance
    behavior = provenance_logger.get_user_behavior_patterns(user_id=user_id)

    if verbose:
        print(f"\n{'='*80}")
        print("USER BEHAVIOR ANALYSIS")
        print(f"{'='*80}")
        print(f"Total Attempts: {behavior['total_attempts']}")
        print(f"Success Rate: {behavior['success_rate']*100:.1f}%")
        print(f"Engagement: {behavior['engagement']}")
        print(f"Average Quality: {behavior['avg_evidence_quality']:.3f}")

    return {
        'user_id': user_id,
        'ucn_results': ucn_results,
        'rr_info': rr_info,
        'curiosity_summary': curiosity_summary,
        'user_behavior': behavior,
        'timestamp': datetime.now().isoformat()
    }


def save_ucn_report(report: dict, output_dir: Path = None) -> Path:
    """Save UCN report to file."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "users" / report['user_id']

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{report['user_id']}_ucn_report.json"

    # Convert to JSON-serializable format
    json_report = {
        'user_id': report['user_id'],
        'timestamp': report['timestamp'],
        'rr': report['rr_info']['rr'],
        'average_ucn': report['rr_info']['average_ucn'],
        'trait_count': report['rr_info']['trait_count'],
        'gates_passed': report['rr_info']['gates_passed'],
        'milestones_achieved': report['rr_info']['milestones_achieved'],
        'overall_curiosity': report['curiosity_summary']['overall_curiosity'],
        'curiosity_level': report['curiosity_summary']['curiosity_level'],
        'traits': {}
    }

    # Add per-trait UCN data
    for trait_path, result in report['ucn_results'].items():
        json_report['traits'][trait_path] = {
            'value': result['value'],
            'ucn': result['ucn'],
            'confidence_level': result['confidence_level'],
            'evidence_count': result['evidence_count'],
            'decay_half_life_days': result['decay_half_life_days'],
            'contradictions': result['contradictions']
        }

    # Add top curiosity signals
    json_report['top_refinement_priorities'] = [
        {
            'trait_path': s['trait_path'],
            'ucn': s['ucn'],
            'priority': s['priority'],
            'suggested_action': s['suggested_action']
        }
        for s in report['curiosity_summary']['trait_signals'][:10]
    ]

    # Add user behavior
    json_report['user_behavior'] = report['user_behavior']

    with open(output_file, 'w') as f:
        json.dump(json_report, f, indent=2)

    return output_file


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate UCN/RR for a user')
    parser.add_argument('user_id', help='User ID (e.g., abtest, mrscoachtest)')
    parser.add_argument('--data-dir', type=Path, help='Data directory (default: ../data/users)')
    parser.add_argument('--quiet', action='store_true', help='Suppress verbose output')
    parser.add_argument('--save', action='store_true', help='Save report to JSON file')

    args = parser.parse_args()

    # Calculate UCN/RR
    report = calculate_ucn_for_user(
        user_id=args.user_id,
        data_dir=args.data_dir,
        verbose=not args.quiet
    )

    # Save report
    if args.save:
        output_file = save_ucn_report(report)
        print(f"\n✓ Report saved to: {output_file}")

    print(f"\n{'='*80}")
    print("CALCULATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
