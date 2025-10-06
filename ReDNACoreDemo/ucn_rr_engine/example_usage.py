"""
UCN/RR Engine Example Usage

Demonstrates how to use the UCN/RR calculation engine with the abtest user data.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from pprint import pprint

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ucn_rr_engine import (
    UCNCalculator,
    RRCalculator,
    CuriosityEngine,
    EvidenceSource,
    SourceType,
    ProvenanceLogger,
    AttemptType,
    AttemptStatus,
    update_evidence
)


def example_1_basic_ucn_calculation():
    """Example 1: Calculate UCN for hair color with multiple evidence sources."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic UCN Calculation for Hair Color")
    print("="*80)

    # Create evidence sources
    evidence_list = [
        # Self-report (text)
        EvidenceSource(
            source_type=SourceType.SELF_REPORT_TEXT,
            value="Dark Brown",
            timestamp=datetime.now() - timedelta(days=5),
            source_id="self-report-001",
            quality_metadata={}
        ),
        # Photo series (high quality)
        EvidenceSource(
            source_type=SourceType.PHOTO_SERIES,
            value="Dark Brown",
            timestamp=datetime.now() - timedelta(days=2),
            source_id="photo-series-001",
            quality_metadata={
                'resolution': 'high',
                'lighting': 'good',
                'angle': 'multiple'
            }
        ),
        # Third-party attestation
        EvidenceSource(
            source_type=SourceType.THIRD_PARTY_ATTESTATION,
            value="Dark Brown",
            timestamp=datetime.now() - timedelta(days=1),
            source_id="third-party-001",
            quality_metadata={
                'relationship': 'friend'
            }
        )
    ]

    # Calculate UCN
    calculator = UCNCalculator()
    result = calculator.calculate(
        trait_path="PaDNA.HairDNA.Color",
        evidence_list=evidence_list,
        user_metadata={'age': 30}
    )

    print("\nResult:")
    pprint(result)

    print(f"\n✓ UCN: {result['ucn']} ({result['confidence_level']})")
    print(f"✓ Consensus Value: {result['value']}")
    print(f"✓ Evidence Count: {result['evidence_count']}")
    print(f"✓ Decay Half-Life: {result['decay_half_life_days']} days")


def example_2_contradiction_handling():
    """Example 2: Handle contradictory evidence (hair color changed)."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Contradiction Handling")
    print("="*80)

    # Create contradictory evidence
    evidence_list = [
        # Old photo (6 months ago) - blonde
        EvidenceSource(
            source_type=SourceType.PHOTO_SERIES,
            value="Blonde",
            timestamp=datetime.now() - timedelta(days=180),
            source_id="photo-old-001",
            quality_metadata={'resolution': 'high'}
        ),
        # Recent photo (1 week ago) - dark brown
        EvidenceSource(
            source_type=SourceType.PHOTO_SERIES,
            value="Dark Brown",
            timestamp=datetime.now() - timedelta(days=7),
            source_id="photo-recent-001",
            quality_metadata={'resolution': 'high'}
        ),
        # Self-report confirms dark brown
        EvidenceSource(
            source_type=SourceType.SELF_REPORT_TEXT,
            value="Dark Brown",
            timestamp=datetime.now() - timedelta(days=1),
            source_id="self-report-002"
        )
    ]

    calculator = UCNCalculator()
    result = calculator.calculate(
        trait_path="PaDNA.HairDNA.Color",
        evidence_list=evidence_list
    )

    print("\nResult:")
    pprint(result)

    print(f"\n✓ UCN: {result['ucn']} (reduced due to contradiction)")
    print(f"✓ Contradictions Detected: {len(result['contradictions'])}")
    if result['contradictions']:
        for c in result['contradictions']:
            print(f"  - {c['severity']}: {c['values']} (penalty: {c['penalty']})")


def example_3_rr_calculation():
    """Example 3: Calculate Refinement Rank (RR) for a user."""
    print("\n" + "="*80)
    print("EXAMPLE 3: RR Calculation")
    print("="*80)

    # Simulate user traits with various UCN scores
    user_traits = {
        "PaDNA.HairDNA.Color": 850,
        "PaDNA.HairDNA.Length": 720,
        "PaDNA.EyeDNA.Color": 950,
        "PaDNA.EyeDNA.Shape": 800,
        "PaDNA.SkinDNA.Tone": 680,
        "PaDNA.FacialDNA.FaceShape": 900,
        "PaDNA.FacialDNA.Cheekbones": 750,
        "PsyDNA.Personality.Openness": 450,
        "PsyDNA.Opinions.PoliticalViews": 320,
        "StyleDNA.ColorPreference": 600,
    }

    calculator = RRCalculator()
    rr_info = calculator.get_rr_info(user_id="abtest", user_traits=user_traits)

    print("\nRR Info:")
    pprint(rr_info)

    print(f"\n✓ RR: {rr_info['rr']} percentile")
    print(f"✓ Average UCN: {rr_info['average_ucn']}")
    print(f"✓ Trait Count: {rr_info['trait_count']}")
    print(f"✓ Gates Passed: {', '.join(rr_info['gates_passed'])}")
    print(f"✓ Milestones: {', '.join(rr_info['milestones_achieved'])}")


def example_4_curiosity_signals():
    """Example 4: Generate Curiosity signals for refinement."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Curiosity Signals")
    print("="*80)

    # Simulate user traits (mix of high and low UCN)
    user_traits = {
        "PaDNA.HairDNA.Color": 850,  # High confidence
        "PaDNA.EyeDNA.Color": 950,   # Very high confidence
        "PaDNA.SkinDNA.Tone": 280,   # Low confidence - needs refinement
        "PaDNA.FacialDNA.FaceShape": 150,  # Very low - critical
        "PsyDNA.Personality.Openness": 450,  # Moderate
        "PsyDNA.Opinions.Politics": 180,     # Very low - critical
        "StyleDNA.ColorPreference": 600,     # Moderate-high
    }

    # Calculate RR
    rr_calculator = RRCalculator()
    rr = rr_calculator.calculate_rr(user_id="test", user_traits=user_traits)

    # Generate curiosity signals
    curiosity_engine = CuriosityEngine()
    curiosity_summary = curiosity_engine.get_curiosity_summary(rr, user_traits)

    print("\nCuriosity Summary:")
    print(f"✓ Overall Curiosity: {curiosity_summary['overall_curiosity']}")
    print(f"✓ Curiosity Level: {curiosity_summary['curiosity_level']}")
    print(f"✓ RR: {curiosity_summary['rr']}")
    print(f"✓ Average UCN: {curiosity_summary['avg_ucn']:.2f}")

    print("\nBudget Allocation:")
    budget = curiosity_summary['budget_allocation']
    print(f"✓ Strategy: {budget['strategy']}")
    print(f"✓ Focus: {budget['focus']}")
    print(f"✓ Max Concurrent Actions: {budget['max_concurrent_actions']}")
    print(f"✓ Trait Breakdown:")
    for priority, count in budget['trait_breakdown'].items():
        print(f"  - {priority}: {count}")

    print("\nTop Priority Traits for Refinement:")
    for i, signal in enumerate(curiosity_summary['trait_signals'][:5], 1):
        print(f"\n{i}. {signal['trait_path']}")
        print(f"   UCN: {signal['ucn']} | Priority: {signal['priority']}")
        print(f"   Reason: {signal['reason']}")
        print(f"   Action: {signal['suggested_action']}")


def example_5_provenance_logging():
    """Example 5: Log evidence attempts and analyze user behavior."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Provenance Logging")
    print("="*80)

    logger = ProvenanceLogger()

    # Log successful photo upload
    logger.log_attempt(
        user_id="abtest",
        trait_path="PaDNA.HairDNA.Color",
        attempt_type=AttemptType.PHOTO_UPLOAD,
        attempt_status=AttemptStatus.SUCCESS,
        source_type="photo_series",
        source_id="photo-001",
        evidence_quality=0.9,
        extracted_value="Dark Brown",
        ucn_before=300,
        ucn_after=850
    )

    # Log failed photo upload
    logger.log_attempt(
        user_id="abtest",
        trait_path="PaDNA.EyeDNA.Color",
        attempt_type=AttemptType.PHOTO_UPLOAD,
        attempt_status=AttemptStatus.FAILURE,
        source_type="photo",
        source_id="photo-002",
        failure_reason="file_too_large",
        user_behavior_indicators={'technical_ability': 'low'}
    )

    # Log another successful upload
    logger.log_attempt(
        user_id="abtest",
        trait_path="PaDNA.EyeDNA.Color",
        attempt_type=AttemptType.PHOTO_UPLOAD,
        attempt_status=AttemptStatus.SUCCESS,
        source_type="photo",
        source_id="photo-003",
        evidence_quality=0.85,
        extracted_value="Blue-Green"
    )

    # Retrieve provenance log
    provenance = logger.get_provenance(user_id="abtest", lookback_days=90)

    print(f"\n✓ Total Provenance Entries: {len(provenance)}")
    print("\nRecent Attempts:")
    for i, entry in enumerate(provenance[:5], 1):
        print(f"\n{i}. {entry.attempt_type.value} - {entry.attempt_status.value}")
        print(f"   Trait: {entry.trait_path}")
        print(f"   Timestamp: {entry.timestamp}")
        if entry.extracted_value:
            print(f"   Value: {entry.extracted_value}")
        if entry.failure_reason:
            print(f"   Failure: {entry.failure_reason}")

    # Analyze user behavior patterns
    behavior = logger.get_user_behavior_patterns(user_id="abtest", lookback_days=90)

    print("\nUser Behavior Analysis:")
    pprint(behavior)

    print(f"\n✓ Success Rate: {behavior['success_rate']*100:.1f}%")
    print(f"✓ Technical Ability: {behavior['technical_ability']}")
    print(f"✓ Engagement: {behavior['engagement']}")


def example_6_end_to_end():
    """Example 6: Complete end-to-end workflow."""
    print("\n" + "="*80)
    print("EXAMPLE 6: End-to-End Workflow")
    print("="*80)
    print("Simulating complete refinement workflow for user 'abtest'\n")

    # Initialize components
    ucn_calc = UCNCalculator()
    rr_calc = RRCalculator()
    curiosity_engine = CuriosityEngine()
    logger = ProvenanceLogger()

    # Step 1: Gather evidence for multiple traits
    print("Step 1: Gathering evidence...")

    trait_evidence = {
        "PaDNA.HairDNA.Color": [
            EvidenceSource(
                SourceType.SELF_REPORT_TEXT,
                "Dark Brown",
                datetime.now() - timedelta(days=10),
                "self-001"
            ),
            EvidenceSource(
                SourceType.PHOTO_SERIES,
                "Dark Brown",
                datetime.now() - timedelta(days=3),
                "photo-001",
                quality_metadata={'resolution': 'high', 'lighting': 'good'}
            )
        ],
        "PaDNA.EyeDNA.Color": [
            EvidenceSource(
                SourceType.PHOTO_SERIES,
                "Blue-Green",
                datetime.now() - timedelta(days=1),
                "photo-002",
                quality_metadata={'resolution': 'high'}
            )
        ],
        "PaDNA.SkinDNA.Tone": [
            EvidenceSource(
                SourceType.SELF_REPORT_STRUCTURED,
                "Fair",
                datetime.now() - timedelta(days=30),
                "form-001"
            )
        ]
    }

    # Step 2: Calculate UCN for each trait
    print("Step 2: Calculating UCN scores...")
    user_traits = {}

    for trait_path, evidence_list in trait_evidence.items():
        result = ucn_calc.calculate(trait_path, evidence_list)
        user_traits[trait_path] = result['ucn']

        # Log to provenance
        for evidence in evidence_list:
            logger.log_attempt(
                user_id="abtest",
                trait_path=trait_path,
                attempt_type=AttemptType.PHOTO_UPLOAD if 'photo' in evidence.source_id else AttemptType.FORM_SUBMISSION,
                attempt_status=AttemptStatus.SUCCESS,
                source_type=evidence.source_type.value,
                source_id=evidence.source_id,
                extracted_value=evidence.value,
                ucn_after=result['ucn']
            )

        print(f"  {trait_path}: UCN {result['ucn']}")

    # Step 3: Calculate RR
    print("\nStep 3: Calculating Refinement Rank...")
    rr_info = rr_calc.get_rr_info(user_id="abtest", user_traits=user_traits)
    print(f"  RR: {rr_info['rr']} percentile")
    print(f"  Average UCN: {rr_info['average_ucn']}")

    # Step 4: Generate Curiosity signals
    print("\nStep 4: Generating Curiosity signals...")
    curiosity_summary = curiosity_engine.get_curiosity_summary(
        rr_info['rr'],
        user_traits
    )
    print(f"  Overall Curiosity: {curiosity_summary['overall_curiosity']}")
    print(f"  Curiosity Level: {curiosity_summary['curiosity_level']}")

    # Step 5: Head Coach planning (simulated)
    print("\nStep 5: Head Coach Planning (simulated)...")
    budget = curiosity_summary['budget_allocation']
    print(f"  Strategy: {budget['strategy']}")
    print(f"  Max Concurrent Actions: {budget['max_concurrent_actions']}")

    print("\n  Top actions to take:")
    for i, signal in enumerate(budget['top_priority_traits'][:3], 1):
        print(f"    {i}. {signal['trait_path']}")
        print(f"       → {signal['suggested_action']}")

    print("\n✓ End-to-end workflow complete!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("UCN/RR CALCULATION ENGINE - EXAMPLE USAGE")
    print("="*80)

    # Run all examples
    example_1_basic_ucn_calculation()
    example_2_contradiction_handling()
    example_3_rr_calculation()
    example_4_curiosity_signals()
    example_5_provenance_logging()
    example_6_end_to_end()

    print("\n" + "="*80)
    print("ALL EXAMPLES COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Integrate UCN/RR engine with Core evidence loading")
    print("2. Wire provenance logging to all evidence attempts")
    print("3. Expose UCN/RR/Curiosity signals to Explorer → Head Coach")
    print("4. Implement Head Coach planning layer")
    print("5. Test with real user data (abtest, mrscoachtest)")
    print()
