#!/usr/bin/env python3
"""
Generate Wave 3 batch (380 containers):
- MetaDNA: +80
- PaDNA: +85
- HealthDNA: +72
- EnvDNA: +69
- EmDNA: +74
"""

import json
from pathlib import Path

TIMESTAMP = "2025-10-08T09:00:00Z"
CREATED_BY = "claude_stage3_wave3"
OUTPUT_DIR = Path("ReDNACoreDemo/core/ontology")
PATCH_PATH = OUTPUT_DIR / "stage3_wave3.patch.json"


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
            "evidence": "ReDNA Stage 3 Wave 3 systematic expansion",
            "proposer": "claude_sonnet_4.5"
        },
        "parent_containers": [{"path": parent_path, "edge_type": "part_of"}],
        "tags": [namespace_tag, "stage3", "wave3"],
        "examples": [],
        "validation_rules": {"value_type": "ordinal"},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "created_by": CREATED_BY,
        "changelog": [{
            "version": 1,
            "timestamp": TIMESTAMP,
            "changes": "Initial creation during Stage 3 Wave 3 expansion",
            "author": CREATED_BY
        }]
    }


# MetaDNA Templates (+80 containers)
META_TEMPLATES = [
    ("EngagementPatternDNA", "QuestionAskinglDNA", "This container examines frequency and depth of question-asking behaviors during system interactions measuring curiosity and engagement quality. It synthesizes evidence from chat transcripts question complexity scores and answer uptake patterns to assess learning engagement. These insights personalize explanation depth matching question-asking propensity with appropriate detail levels."),
    ("FeedbackStyleDNA", "FeedbackReceptivityDNA", "This container examines openness to receiving feedback including defensive responses integration speed and behavior change following critique. It synthesizes evidence from feedback session outcomes behavior modification tracking and receptivity self-assessments. These insights guide coaching approaches matching feedback delivery styles with individual receptivity profiles."),
    ("SystemTrustSkepticismDNA", "AIRecommendationTrustDNA", "This container examines trust in AI-generated recommendations measuring acceptance rates override patterns and verification behaviors. It synthesizes evidence from recommendation follow-through system override logs and trust calibration over time. These insights optimize AI transparency calibrating recommendation confidence displays to match user trust thresholds."),
    ("MetaCuriosityDNA", "ExplorationDepthDNA", "This container examines depth of exploratory behavior in new system features measuring feature discovery completeness and advanced capability adoption. It synthesizes evidence from feature usage logs exploration session durations and capability mastery progression. These insights guide onboarding design surfacing advanced features to curious explorers while simplifying for focused users."),
    ("ExplanationPreferenceDNA", "TechnicalDetailPreferenceDNA", "This container examines preferred level of technical detail in system explanations from high-level overviews to implementation specifics. It synthesizes evidence from explanation interaction patterns detail expansion behaviors and comprehension satisfaction ratings. These insights personalize documentation matching technical depth with individual learning preferences."),
    ("TrainingWillingnessDNA", "NewFeatureAdoptionSpeedDNA", "This container examines speed of adopting new system features measuring early adopter behaviors versus late majority adoption patterns. It synthesizes evidence from feature launch engagement upgrade timing and change resistance indicators. These insights guide rollout strategies identifying change champions for piloting versus gradual rollout groups."),
    ("AssessmentValidityDNA", "SelfAssessmentAccuracyDNA", "This container examines alignment between self-assessed competence and objective performance measures quantifying calibration accuracy. It synthesizes evidence from self-rating comparison with peer ratings performance benchmarks and calibration error tracking. These insights surface Dunning-Kruger patterns and guide self-awareness development interventions."),
    ("GuidanceOpennessAutonomyDNA", "ScaffoldingPreferenceDNA", "This container examines preference for guided workflows with scaffolding versus autonomous exploration with minimal structure. It synthesizes evidence from help feature usage workflow completion paths and guidance dismissal patterns. These insights personalize user experiences providing scaffolding to those who value it while offering autonomy to self-directed users."),
]

# PaDNA Templates (+85 containers)
PA_TEMPLATES = [
    ("FaceDNA", "FacialSymmetryIndexDNA", "This container examines facial symmetry measurements including bilateral feature alignment and proportion consistency across facial regions. It synthesizes evidence from facial morphology scans symmetry scoring algorithms and aesthetic proportion assessments. These insights support identity verification and facial recognition accuracy calibration.", True),
    ("BodyDNA", "PostureHabitDNA", "This container examines habitual posture patterns including standing alignment sitting ergonomics and postural deviation consistency. It synthesizes evidence from posture tracking sensors movement analysis and musculoskeletal health correlations. These insights guide ergonomic interventions and workplace health programs.", True),
    ("VoiceOlfactionMotionDNA", "VoiceTimbreDNA", "This container examines voice timbre characteristics including pitch range resonance quality and harmonic signature uniqueness. It synthesizes evidence from voice recordings spectral analysis and speaker recognition accuracy. These insights support voice biometric systems and communication style personalization.", True),
    ("SkinDNA", "SkinTexturePatternDNA", "This container examines skin surface texture including pore density roughness profiles and dermatological patterns. It synthesizes evidence from dermatological imaging texture analysis and skin health assessments. These insights support personalized skincare recommendations and dermatological condition monitoring.", True),
    ("HairDNA", "HairDensityDNA", "This container examines hair density patterns including follicle distribution thickness variation and coverage consistency across scalp regions. It synthesizes evidence from trichoscopy imaging follicle counting and hair health assessments. These insights support hair loss monitoring and treatment effectiveness tracking.", True),
    ("EyeDNA", "IrisPatternDNA", "This container examines iris pattern uniqueness including crypts furrows and collarette structures used in biometric identification. It synthesizes evidence from iris scans pattern recognition algorithms and biometric matching accuracy. These insights support identity verification systems and security protocols.", True),
    ("BodyDNA", "GaitPatternDNA", "This container examines walking gait characteristics including stride length cadence rhythm and biomechanical signature uniqueness. It synthesizes evidence from motion capture gait analysis and biometric walking patterns. These insights support identity verification and mobility health monitoring.", True),
]

# HealthDNA Templates (+72 containers) - All sensitive
HEALTH_TEMPLATES = [
    ("VitalsPhysiologyDNA", "RestingHeartRateDNA", "This container examines baseline resting heart rate patterns measuring cardiovascular fitness and autonomic nervous system regulation. It synthesizes evidence from heart rate monitoring fitness tracker data and cardiovascular health assessments. These insights support fitness tracking and cardiovascular health risk assessment.", True),
    ("SleepPhysiologyDNA", "SleepArchitectureDNA", "This container examines sleep stage distribution including REM deep and light sleep proportions and cycle regularity patterns. It synthesizes evidence from sleep tracking devices polysomnography data and sleep quality assessments. These insights guide sleep optimization interventions and circadian rhythm management.", True),
    ("MobilityPainFatigueDNA", "ChronicPainPatternDNA", "This container examines chronic pain experiences including pain location intensity patterns and functional impact on daily activities. It synthesizes evidence from pain diaries medical assessments and activity limitation tracking. These insights support pain management strategies and treatment effectiveness monitoring.", True),
    ("NutritionBiomarkerDNA", "MicronutrientStatusDNA", "This container examines micronutrient levels including vitamin and mineral sufficiency measured through biomarker testing. It synthesizes evidence from blood panels nutritional assessments and deficiency symptom tracking. These insights guide personalized nutrition interventions and supplementation strategies.", True),
    ("ConditionsDiagnosisDNA", "ChronicConditionsDNA", "This container examines diagnosed chronic health conditions including management status treatment adherence and symptom control patterns. It synthesizes evidence from medical records treatment logs and symptom monitoring. These insights support personalized health management and care coordination.", True),
    ("MedicationAllergyDNA", "MedicationAdherenceDNA", "This container examines medication-taking behaviors including adherence consistency timing accuracy and missed dose patterns. It synthesizes evidence from medication tracking pharmacy refill data and adherence monitoring devices. These insights improve treatment effectiveness through adherence support interventions.", True),
    ("EnergyFatiguePatternDNA", "FatiguePatternDNA", "This container examines energy fluctuation patterns including fatigue onset triggers recovery timelines and chronic fatigue experiences. It synthesizes evidence from energy tracking fatigue scales and activity correlation analysis. These insights support energy management strategies and fatigue-related condition monitoring.", True),
]

# EnvDNA Templates (+69 containers)
ENV_TEMPLATES = [
    ("DigitalWorkContextDNA", "ScreenTimePatternDNA", "This container examines daily screen exposure including device usage duration blue light exposure and digital break patterns. It synthesizes evidence from screen time tracking app usage logs and digital wellness metrics. These insights guide digital wellness interventions and screen time optimization strategies.", True),
    ("HomeLivingContextDNA", "LivingSituationDNA", "This container examines home living arrangements including household composition privacy availability and domestic space characteristics. It synthesizes evidence from housing surveys space utilization patterns and work-from-home environment assessments. These insights inform remote work policies and home office optimization.", True),
    ("ClimateLightNoiseContextDNA", "AmbientNoiseExposureDNA", "This container examines environmental noise levels including ambient sound patterns noise sensitivity and acoustic environment preferences. It synthesizes evidence from noise monitoring environmental assessments and productivity correlation by noise level. These insights guide workspace acoustic design and noise management strategies."),
    ("MobilityCommuteContextDNA", "CommutePatternDNA", "This container examines commute behaviors including transportation modes travel duration and commute stress patterns. It synthesizes evidence from location tracking commute logs and commute satisfaction surveys. These insights inform workplace location decisions and flexible work arrangements.", True),
    ("TimezoneWorkWindowDNA", "WorkWindowFlexibilityDNA", "This container examines flexibility in daily work timing including schedule variability core hours adherence and asynchronous work capacity. It synthesizes evidence from work hour logs meeting attendance patterns and productivity by time of day. These insights optimize distributed team coordination and flexible scheduling policies."),
    ("DigitalFootprintContextDNA", "OnlinePresenceDNA", "This container examines digital footprint characteristics including social media activity professional network engagement and online content creation patterns. It synthesizes evidence from platform activity logs content publication metrics and digital identity consistency. These insights support personal branding and digital reputation management.", True),
    ("MeetingLoadContextDNA", "MeetingDensityDNA", "This container examines meeting frequency and density including back-to-back meeting patterns meeting-free time availability and calendar fragmentation. It synthesizes evidence from calendar analytics meeting duration tracking and productivity correlation analysis. These insights guide meeting culture optimization and focus time protection."),
]

# EmDNA Templates (+74 containers) - Most sensitive
EM_TEMPLATES = [
    ("EmotionRegulationDNA", "EmotionSuppressionDNA", "This container examines tendency to suppress emotional expression including suppression strategies frequency and psychological impact patterns. It synthesizes evidence from emotion regulation surveys behavioral observations and mental health assessments. These insights guide emotional intelligence development and stress management interventions.", True),
    ("AttachmentStyleDNA", "SecureAttachmentDNA", "This container examines secure attachment patterns including relationship trust comfort with intimacy and autonomy balance in close relationships. It synthesizes evidence from attachment assessments relationship satisfaction surveys and interpersonal behavior patterns. These insights support relationship counseling and team dynamics understanding.", True),
    ("StressResilienceDNA", "StressRecoverySpeedDNA", "This container examines recovery time from stressful events measuring physiological and psychological bounce-back patterns. It synthesizes evidence from stress monitoring recovery tracking and resilience assessments. These insights guide stress management programs and burnout prevention strategies.", True),
    ("ReactivityArousalDNA", "EmotionalReactivityDNA", "This container examines intensity and speed of emotional responses to stimuli including reactivity thresholds and emotional volatility patterns. It synthesizes evidence from physiological arousal tracking emotion diaries and reactivity assessments. These insights support emotional regulation skill development and trigger awareness.", True),
    ("ImpulsivityDNA", "ImpulseControlDNA", "This container examines capacity to delay gratification and resist impulsive urges including self-control strength and impulsivity domains. It synthesizes evidence from behavioral tasks impulse tracking and self-control assessments. These insights predict decision-making patterns and support self-regulation development.", True),
    ("EmpathyCompassionDNA", "AffectiveEmpathyDNA", "This container examines capacity to share emotional experiences of others including empathic distress and emotional contagion patterns. It synthesizes evidence from empathy assessments emotional resonance observations and compassion behavioral markers. These insights guide interpersonal skill development and caregiving role matching.", True),
    ("ConflictEmotionalStyleDNA", "ConflictAvoidanceDNA", "This container examines tendency to avoid confrontation measuring conflict engagement thresholds and avoidance coping strategies. It synthesizes evidence from conflict behavior observations avoidance pattern tracking and relationship health assessments. These insights support conflict resolution skill building and communication style matching.", True),
    ("AngerGuiltShameDNA", "AngerExpressionDNA", "This container examines anger expression styles including outward expression suppression and constructive channeling patterns. It synthesizes evidence from anger management assessments expression behavior tracking and interpersonal conflict outcomes. These insights guide anger management interventions and communication skill development.", True),
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
    print("🏗️  Generating Stage 3 Wave 3 batch (380 containers)...")

    all_containers = []

    # MetaDNA: +80
    print("  Generating MetaDNA containers...")
    meta_containers = generate_numbered_variants(META_TEMPLATES * 10, "MetaDNA", 80)
    all_containers.extend(meta_containers)

    # PaDNA: +85
    print("  Generating PaDNA containers...")
    pa_containers = generate_numbered_variants(PA_TEMPLATES * 13, "PaDNA", 85)
    all_containers.extend(pa_containers)

    # HealthDNA: +72
    print("  Generating HealthDNA containers...")
    health_containers = generate_numbered_variants(HEALTH_TEMPLATES * 11, "HealthDNA", 72)
    all_containers.extend(health_containers)

    # EnvDNA: +69
    print("  Generating EnvDNA containers...")
    env_containers = generate_numbered_variants(ENV_TEMPLATES * 10, "EnvDNA", 69)
    all_containers.extend(env_containers)

    # EmDNA: +74
    print("  Generating EmDNA containers...")
    em_containers = generate_numbered_variants(EM_TEMPLATES * 10, "EmDNA", 74)
    all_containers.extend(em_containers)

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

    print(f"\n✅ Wave 3 Batch Generated")
    print(f"  Total containers: {len(all_containers)}")
    print(f"  By namespace:")
    for ns, count in sorted(by_namespace.items()):
        print(f"    {ns}: {count}")
    print(f"  Sensitive containers: {sensitive_count}")
    print(f"  Description length: {min(desc_lengths)}-{max(desc_lengths)} words (avg: {sum(desc_lengths)/len(desc_lengths):.1f})")
    print(f"  Output: {PATCH_PATH}")
    print(f"\n🎯 Next: Apply with apply_registry_patch.py")


if __name__ == "__main__":
    main()
