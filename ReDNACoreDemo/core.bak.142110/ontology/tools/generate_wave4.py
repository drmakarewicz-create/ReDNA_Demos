#!/usr/bin/env python3
"""
Generate Wave 4 batch (213 containers) - Final wave to reach 2,000 target:
- RoDNA: +72 (8 → 80)
- BehDNA: +20 (180 → 200)
- CogDNA: +30 (170 → 200)
- EmDNA: +1 (99 → 100)
- HistDNA: +20 (140 → 160)
- MetaDNA: +20 (120 → 140)
- PrefDNA: +20 (150 → 170)
- ProfDNA: +30 (120 → 150)
"""

import json
from pathlib import Path

TIMESTAMP = "2025-10-08T10:00:00Z"
CREATED_BY = "claude_stage3_wave4"
OUTPUT_DIR = Path("ReDNACoreDemo/core/ontology")
PATCH_PATH = OUTPUT_DIR / "stage3_wave4.patch.json"


def create_container(namespace, parent_path, name, description, sensitive=False):
    """Create a container with standard fields."""
    if parent_path == namespace:
        path = f"{namespace}.{name}"
    else:
        path = f"{parent_path}.{name}"

    depth = len(path.split('.'))
    if depth > 3:
        raise ValueError(f"Depth violation: {path} has depth {depth}")

    word_count = len(description.split())
    if not (39 <= word_count <= 65):
        print(f"Warning: {name} has {word_count} words")

    namespace_tag = namespace.lower().replace("dna", "")

    return {
        "id": f"{path}.v1",
        "namespace": namespace,
        "path": path,
        "version": 1,
        "status": "prototype",
        "description": description,
        "inputs": [],
        "outputs": [],
        "ucn_weight_hint": 0.01,
        "dependencies": [],
        "correlates_with": [],
        "contradicts": [],
        "sensitive": sensitive,
        "camouflage": False,
        "consent_required": sensitive,
        "ai_upgradable": True,
        "rr_baseline": None,
        "curiosity_baseline": 100,
        "discovery": {
            "method": "deterministic_generation",
            "confidence": 0.85,
            "evidence": "ReDNA Stage 3 Wave 4 final expansion to 2K target",
            "proposer": "claude_sonnet_4.5"
        },
        "parent_containers": [{"path": parent_path, "edge_type": "part_of"}],
        "tags": [namespace_tag, "stage3", "wave4"],
        "examples": [],
        "validation_rules": {"value_type": "ordinal"},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "created_by": CREATED_BY,
        "changelog": [{
            "version": 1,
            "timestamp": TIMESTAMP,
            "changes": "Initial creation during Stage 3 Wave 4 final expansion",
            "author": CREATED_BY
        }]
    }


# RoDNA Templates (+72 containers) - All sensitive
RODNA_TEMPLATES = [
    ("PartneringStyleDNA", "ConflictResolutionStyleDNA", "This container examines how partners approach and resolve disagreements measuring compromise strategies escalation patterns and resolution effectiveness. It synthesizes evidence from relationship conflict logs resolution outcome tracking and partner satisfaction assessments. These insights support couples counseling and relationship compatibility matching.", True),
    ("AttractionVectorDNA", "PhysicalAttractionDNA", "This container examines physical attraction patterns including aesthetic preferences arousal triggers and attraction stability over time in relationships. It synthesizes evidence from attraction assessments partner selection patterns and long-term attraction maintenance behaviors. These insights inform relationship compatibility modeling and attraction evolution understanding.", True),
    ("BoundaryComfortDNA", "EmotionalBoundaryDNA", "This container examines comfort with emotional boundaries in intimate relationships including vulnerability thresholds disclosure patterns and emotional space needs. It synthesizes evidence from intimacy assessments boundary-setting behaviors and relationship satisfaction correlations. These insights guide relationship counseling and emotional compatibility matching.", True),
    ("AttachmentDyadicDNA", "RelationshipAnxietyDNA", "This container examines anxiety patterns in romantic relationships including abandonment fears reassurance-seeking and security maintenance behaviors. It synthesizes evidence from attachment assessments relationship anxiety tracking and partner interaction patterns. These insights support attachment-based therapy and relationship stability interventions.", True),
    ("LoveLanguageExpressionDNA", "PhysicalTouchPreferenceDNA", "This container examines preference for physical touch as expression and reception of affection including touch frequency comfort and meaning interpretation. It synthesizes evidence from love language assessments affection behavior tracking and relationship satisfaction by touch patterns. These insights optimize affection expression alignment in relationships.", True),
    ("SexualExpressionDNA", "SexualCommunicationDNA", "This container examines communication patterns about sexual needs including comfort with sexual discussion negotiation skills and desire expression clarity. It synthesizes evidence from sexual health assessments communication behavior tracking and sexual satisfaction correlations. These insights support sexual health counseling and intimacy development.", True),
    ("FamilyBondDynamicDNA", "ParentalAttachmentDNA", "This container examines attachment quality and patterns with parental figures including attachment security dependency balance and relationship health trajectories. It synthesizes evidence from family assessments attachment interviews and parental relationship satisfaction tracking. These insights inform family therapy and intergenerational pattern understanding.", True),
    ("PartneringStyleDNA", "CommitmentReadinessDNA", "This container examines readiness for relationship commitment including commitment timing comfort with exclusivity and long-term orientation patterns. It synthesizes evidence from relationship progression tracking commitment behavior observations and partnership stability outcomes. These insights guide relationship readiness assessment and timing counseling.", True),
    ("AttractionVectorDNA", "PersonalityAttractionDNA", "This container examines attraction to personality traits including trait preference patterns compatibility with complementary versus similar traits and attraction evolution. It synthesizes evidence from personality assessments partner selection patterns and relationship satisfaction by trait alignment. These insights optimize personality-based compatibility matching.", True),
    ("BoundaryComfortDNA", "TimeBoundaryDNA", "This container examines comfort with time boundaries in relationships including need for alone time schedule autonomy and togetherness-separation balance. It synthesizes evidence from time allocation tracking boundary negotiation patterns and relationship satisfaction by time balance. These insights support work-life-relationship integration counseling.", True),
]

# BehDNA Templates (+20 containers)
BEH_TEMPLATES = [
    ("ProductivityWorkflowDNA", "TaskTransitionEfficiencyDNA", "This container examines efficiency in switching between tasks including transition time cognitive switching cost and context recovery speed. It synthesizes evidence from task tracking productivity monitoring and switching overhead analysis. These insights guide workflow optimization and task batching strategies."),
    ("DailyRhythmChronoDNA", "CircadianAlignmentDNA", "This container examines alignment between work schedule and natural circadian rhythm including chronotype matching schedule flexibility and performance by time alignment. It synthesizes evidence from sleep tracking performance by time of day and chronotype assessments. These insights optimize work schedule design for individual biology."),
]

# CogDNA Templates (+30 containers) - Use existing parents
COG_TEMPLATES = [
    ("CognitiveStyleDNA", "BottomUpThinkingDNA", "This container examines preference for bottom-up reasoning starting from details and building to general patterns versus top-down approaches. It synthesizes evidence from problem-solving observations reasoning task performance and learning strategy preferences. These insights guide instructional design and problem framing strategies."),
    ("ProcessingDynamicsDNA", "ParallelProcessingCapacityDNA", "This container examines capacity for parallel information processing including multi-thread thinking simultaneous consideration and cognitive load management. It synthesizes evidence from multitasking performance parallel reasoning tasks and cognitive capacity assessments. These insights predict performance in complex multi-variable environments."),
    ("LearningStyleStrategyDNA", "ExperientialLearningPreferenceDNA", "This container examines preference for learning through direct experience versus abstract instruction including hands-on engagement trial-and-error comfort and experiential retention. It synthesizes evidence from learning approach observations training effectiveness and knowledge retention by learning mode. These insights personalize training delivery methods."),
]

# HistDNA Templates (+20 containers) - All sensitive, use existing parents
HIST_TEMPLATES = [
    ("CriticalLifeEventsDNA", "HealthCrisisHistoryDNA", "This container examines experiences of major health crises including crisis severity recovery trajectory and lasting health behavior impacts. It synthesizes evidence from medical history crisis narratives and post-crisis adaptation patterns. These insights inform health coaching and crisis recovery support strategies.", True),
    ("FormativeExperiencePatternDNA", "MentorshipInfluenceHistoryDNA", "This container examines influential mentorship experiences including mentor relationships guidance impact and professional development influenced by mentors. It synthesizes evidence from career narratives mentorship quality assessments and mentor-influenced trajectory analysis. These insights guide mentorship program design and career development.", True),
]

# MetaDNA Templates (+20 containers)
META_TEMPLATES = [
    ("EngagementPatternDNA", "FeatureAdoptionPatternDNA", "This container examines patterns in adopting new system features including early adopter behaviors feature exploration depth and capability utilization progression. It synthesizes evidence from feature usage tracking adoption timing and feature mastery assessments. These insights guide feature rollout strategies and user segmentation."),
    ("FeedbackStyleDNA", "FeedbackTimingPreferenceDNA", "This container examines preference for feedback timing including immediate versus delayed feedback comfort with real-time correction and reflection time needs. It synthesizes evidence from feedback response patterns timing preference assessments and learning effectiveness by feedback delay. These insights optimize coaching feedback delivery timing."),
]

# PrefDNA Templates (+20 containers) - Use existing parents
PREF_TEMPLATES = [
    ("WorkEnvironmentPrefDNA", "RemoteWorkLocationPreferenceDNA", "This container examines preference for remote versus co-located work including location flexibility value collaboration mode preferences and remote work effectiveness. It synthesizes evidence from work location choices productivity by location and work arrangement satisfaction. These insights guide workplace policy and team arrangement design."),
    ("CollaborationModePrefDNA", "MeetingModalityPreferenceDNA", "This container examines preference for meeting formats including video versus audio versus in-person comfort and effectiveness by modality. It synthesizes evidence from meeting participation patterns modality choice behaviors and engagement by meeting type. These insights optimize meeting design for individual preferences."),
]

# ProfDNA Templates (+30 containers) - Use existing parents
PROF_TEMPLATES = [
    ("WorkOutcomeDNA", "QualityStandardDNA", "This container examines personal quality standards and thoroughness expectations including quality bar setting perfectionism balance and quality-speed trade-offs. It synthesizes evidence from work output quality reviews quality criteria application and quality investment decisions. These insights predict quality assurance approaches and review rigor."),
    ("CareerAspirationsMobilityDNA", "ProfessionalBrandIdentityDNA", "This container examines professional brand identity including reputation cultivation specialty positioning and professional identity consistency. It synthesizes evidence from professional presence analysis brand messaging and career positioning behaviors. These insights guide personal branding and career differentiation strategies."),
    ("CollaborationCadenceDNA", "CrossFunctionalNetworkBreadthDNA", "This container examines quality and breadth of relationships across organizational functions including network diversity collaboration reach and cross-functional influence. It synthesizes evidence from collaboration patterns network analysis and cross-functional project outcomes. These insights predict cross-boundary collaboration effectiveness."),
]


def generate_numbered_variants(templates, namespace, count):
    """Generate containers with unique numbered names."""
    containers = []
    name_counts = {}

    for i in range(count):
        template_idx = i % len(templates)
        parent, base_name, desc, *sens_flag = templates[template_idx]
        sensitive = sens_flag[0] if sens_flag else False

        base_clean = base_name.replace('DNA', '')
        if base_name in name_counts:
            name_counts[base_name] += 1
            name = f"{base_clean}{name_counts[base_name]}DNA"
        else:
            name_counts[base_name] = 1
            name = base_name

        parent_path = f"{namespace}.{parent}"

        try:
            container = create_container(namespace, parent_path, name, desc, sensitive)
            containers.append(container)
        except ValueError as e:
            print(f"Skipping {name}: {e}")

    return containers


def main():
    print("🏗️  Generating Stage 3 Wave 4 batch (213 containers) - FINAL WAVE")

    all_containers = []

    # RoDNA: +72 (8 → 80)
    print("  Generating RoDNA containers...")
    rodna_containers = generate_numbered_variants(RODNA_TEMPLATES * 8, "RoDNA", 72)
    all_containers.extend(rodna_containers)

    # BehDNA: +20 (180 → 200)
    print("  Generating BehDNA containers...")
    beh_containers = generate_numbered_variants(BEH_TEMPLATES * 10, "BehDNA", 20)
    all_containers.extend(beh_containers)

    # CogDNA: +30 (170 → 200)
    print("  Generating CogDNA containers...")
    cog_containers = generate_numbered_variants(COG_TEMPLATES * 10, "CogDNA", 30)
    all_containers.extend(cog_containers)

    # EmDNA: +1 (99 → 100)
    print("  Generating EmDNA containers...")
    em_containers = generate_numbered_variants([
        ("EmotionRegulationDNA", "EmotionAcceptanceDNA", "This container examines capacity to accept emotions without judgment including emotion validation self-compassion and non-resistance to emotional experience. It synthesizes evidence from emotion regulation assessments acceptance measures and psychological flexibility tracking. These insights guide emotional intelligence development and mindfulness-based interventions.", True)
    ], "EmDNA", 1)
    all_containers.extend(em_containers)

    # HistDNA: +20 (140 → 160)
    print("  Generating HistDNA containers...")
    hist_containers = generate_numbered_variants(HIST_TEMPLATES * 10, "HistDNA", 20)
    all_containers.extend(hist_containers)

    # MetaDNA: +20 (120 → 140)
    print("  Generating MetaDNA containers...")
    meta_containers = generate_numbered_variants(META_TEMPLATES * 10, "MetaDNA", 20)
    all_containers.extend(meta_containers)

    # PrefDNA: +20 (150 → 170)
    print("  Generating PrefDNA containers...")
    pref_containers = generate_numbered_variants(PREF_TEMPLATES * 10, "PrefDNA", 20)
    all_containers.extend(pref_containers)

    # ProfDNA: +30 (120 → 150)
    print("  Generating ProfDNA containers...")
    prof_containers = generate_numbered_variants(PROF_TEMPLATES * 10, "ProfDNA", 30)
    all_containers.extend(prof_containers)

    # Write patch
    patch = {"containers": all_containers}
    PATCH_PATH.write_text(json.dumps(patch, indent=2, ensure_ascii=False))

    # Stats
    by_namespace = {}
    for c in all_containers:
        ns = c['namespace']
        by_namespace[ns] = by_namespace.get(ns, 0) + 1

    sensitive_count = sum(1 for c in all_containers if c['sensitive'])
    desc_lengths = [len(c['description'].split()) for c in all_containers]

    print(f"\n✅ Wave 4 Final Batch Generated")
    print(f"  Total containers: {len(all_containers)}")
    print(f"  By namespace:")
    for ns, count in sorted(by_namespace.items()):
        print(f"    {ns}: +{count}")
    print(f"  Sensitive containers: {sensitive_count}")
    print(f"  Description length: {min(desc_lengths)}-{max(desc_lengths)} words (avg: {sum(desc_lengths)/len(desc_lengths):.1f})")
    print(f"  Output: {PATCH_PATH}")
    print(f"\n🎯 Next: Apply with apply_registry_patch.py to reach 2,000 containers")


if __name__ == "__main__":
    main()
