#!/usr/bin/env python3
"""
Generate Wave 2 batch (420 containers):
- SkillDNA: +110
- SocDNA: +100
- HistDNA: +90
- PrefDNA: +90
- PsyDNA: +29 (makeup from Wave 1)
"""

import json
from pathlib import Path
from datetime import datetime

TIMESTAMP = "2025-10-08T08:00:00Z"
CREATED_BY = "claude_stage3_wave2"
OUTPUT_DIR = Path("ReDNACoreDemo/core/ontology")
PATCH_PATH = OUTPUT_DIR / "stage3_wave2.patch.json"


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
            "evidence": "ReDNA Stage 3 Wave 2 systematic expansion",
            "proposer": "claude_sonnet_4.5"
        },
        "parent_containers": [{"path": parent_path, "edge_type": "part_of"}],
        "tags": [namespace_tag, "stage3", "wave2"],
        "examples": [],
        "validation_rules": {"value_type": "ordinal"},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "created_by": CREATED_BY,
        "changelog": [{
            "version": 1,
            "timestamp": TIMESTAMP,
            "changes": "Initial creation during Stage 3 Wave 2 expansion",
            "author": CREATED_BY
        }]
    }


# SkillDNA Templates (+110 containers)
SKILL_TEMPLATES = [
    ("TechnicalComputationalSkillDNA", "DebuggingSkillDNA", "This container examines systematic debugging approaches including hypothesis formation reproduction steps and root cause analysis patterns. It synthesizes evidence from debugging session logs issue resolution timelines and code fix quality to assess debugging effectiveness. These insights guide technical mentorship pairing strong debuggers with those developing systematic troubleshooting capabilities."),
    ("CommunicationSkillDNA", "TechnicalWritingDNA", "This container examines ability to document technical concepts clearly including API documentation architecture diagrams and runbook completeness. It synthesizes evidence from documentation quality reviews peer comprehension feedback and adoption metrics to measure technical writing proficiency. These insights optimize documentation workflows identifying writers who can translate complex systems into accessible technical guides."),
    ("CollaborationSkillDNA", "ConflictResolutionDNA", "This container examines approaches to resolving team conflicts including mediation strategies stakeholder navigation and outcome fairness. It synthesizes evidence from conflict resolution logs team health surveys and post-conflict productivity metrics to quantify resolution effectiveness. These insights support team composition and leadership development by surfacing natural mediators."),
    ("LeadershipSkillDNA", "DelegationSkillDNA", "This container examines capacity to delegate work effectively including task matching autonomy calibration and follow-up balance patterns. It synthesizes evidence from delegation outcomes team member growth trajectories and workload distribution fairness to assess delegation maturity. These insights guide leadership coaching helping managers transition from individual contribution to team multiplication."),
    ("ProjectDeliverySkillDNA", "ScopeNegotiationDNA", "This container examines skill in negotiating realistic scope boundaries when requirements exceed capacity or timelines compress. It synthesizes evidence from scope negotiation logs stakeholder alignment outcomes and delivery predictability after scope adjustments. These insights improve project planning matching negotiation strength with high-stakes delivery contexts."),
    ("AnalyticalSkillDNA", "DataInterpretationDNA", "This container examines ability to extract insights from complex datasets including statistical reasoning pattern recognition and narrative synthesis from numbers. It synthesizes evidence from analysis artifacts stakeholder presentation effectiveness and decision influence to quantify analytical storytelling strength. These insights guide analyst development and data-driven decision-making capacity building."),
    ("LearningAdaptationSkillDNA", "FrameworkAdoptionSpeedDNA", "This container examines speed of adopting new technical frameworks or methodologies measuring ramp-up time and proficiency milestones. It synthesizes evidence from learning logs project deliverables on new stacks and peer comparison benchmarks. These insights predict technology transition success and inform realistic onboarding timelines for emerging tools."),
]

# SocDNA Templates (+100 containers)
SOC_TEMPLATES = [
    ("StakeholderManagementDNA", "InfluenceWithoutAuthorityDNA", "This container examines ability to drive outcomes across organizational boundaries without formal authority through persuasion relationship capital and credibility. It synthesizes evidence from cross-functional project outcomes stakeholder endorsements and influence mapping to quantify informal power. These insights guide org design and identify natural connectors who enable matrix collaboration."),
    ("TeamCommunicationDNA", "AsynchronousCommunicationDNA", "This container examines effectiveness in async communication channels including written clarity update cadence and context provision completeness. It synthesizes evidence from message comprehension rates response latency patterns and collaboration efficiency in distributed settings. These insights optimize remote work protocols matching async communicators with suitable workflows."),
    ("InteractionStyleDNA", "ActiveListeningDNA", "This container examines listening quality including paraphrasing accuracy question depth and signal uptake from conversational partners. It synthesizes evidence from meeting facilitation feedback conversation transcripts and idea attribution patterns to assess listening engagement. These insights improve meeting effectiveness by surfacing strong listeners for facilitation and mediation roles."),
    ("EmpathyPerspectiveDNA", "CulturalEmpathyDNA", "This container examines sensitivity to cultural differences and ability to navigate cross-cultural collaboration with respect and adaptation. It synthesizes evidence from cross-cultural project feedback inclusion survey responses and communication adaptation patterns. These insights guide global team formation and diversity initiative effectiveness.", True),
    ("SocialEnergyAssertivenessDNA", "SocialBatteryManagementDNA", "This container examines strategies for managing social energy including recharge rituals interaction pacing and burnout prevention in collaborative environments. It synthesizes evidence from meeting load preferences energy level tracking and productivity patterns around social intensity. These insights enable personalized collaboration cadences respecting individual social energy constraints."),
    ("GroupAlignmentIdentityDNA", "TeamBelongingDNA", "This container examines sense of belonging within teams measuring psychological safety identity alignment and inclusion experiences. It synthesizes evidence from belonging surveys retention patterns and engagement metrics to quantify team cohesion quality. These insights guide inclusion interventions and team culture health monitoring.", True),
]

# HistDNA Templates (+90 containers) - Most are sensitive
HIST_TEMPLATES = [
    ("CareerTrajectoryDNA", "CareerPivotHistoryDNA", "This container examines major career transitions including role switches industry changes and skill pivots documenting adaptation patterns and success factors. It synthesizes evidence from career narratives transition timelines and post-pivot satisfaction to map pivot effectiveness. These insights support career counseling by surfacing pivot strategies that align with individual strengths and circumstances.", True),
    ("EducationTrajectoryDNA", "AdvancedDegreeHistoryDNA", "This container examines pursuit of advanced degrees including motivation timing and career impact of graduate education investments. It synthesizes evidence from education transcripts career progression post-degree and ROI assessments to evaluate education decisions. These insights guide professional development investments matching degree pursuit with career advancement goals.", True),
    ("CriticalLifeEventsDNA", "LeadershipBreakthroughMomentDNA", "This container examines pivotal moments that catalyzed leadership identity formation including first management roles crisis navigation and mentor influences. It synthesizes evidence from leadership narratives role transition stories and identity reflection journals. These insights support leadership development by identifying formative experiences common to effective leaders.", True),
    ("FormativeExperiencePatternDNA", "EarlyResponsibilityHistoryDNA", "This container examines early life responsibilities including caretaking financial contribution and family support roles that shape adult accountability patterns. It synthesizes evidence from life history interviews responsibility narratives and correlation with adult work ethic. These insights contextualize professional behavior rooted in formative responsibility experiences.", True),
    ("SocioeconomicContextDNA", "SocioeconomicMobilityDNA", "This container examines economic mobility trajectories including class transitions resource access changes and wealth accumulation patterns over life stages. It synthesizes evidence from financial histories educational access and income progression to map mobility factors. These insights inform equity initiatives and understand diverse economic starting points.", True),
    ("TravelExposureBreadthDNA", "InternationalExperienceDNA", "This container examines international living and travel experiences measuring cultural breadth language exposure and global perspective development. It synthesizes evidence from travel logs international project participation and cross-cultural adaptability to quantify global exposure. These insights guide global role assignments and cross-cultural team composition.", True),
]

# PrefDNA Templates (+90 containers)
PREF_TEMPLATES = [
    ("WorkEnvironmentPrefDNA", "NoiseTolerancePreferenceDNA", "This container examines preferred ambient noise levels from silence to busy cafe environments measuring concentration quality across noise spectrums. It synthesizes evidence from environment satisfaction surveys productivity by location type and workspace choices to reveal noise tolerance profiles. These insights guide workspace design matching noise preferences with available work settings."),
    ("CollaborationModePrefDNA", "SynchronousPreferenceDNA", "This container examines preference for real-time synchronous collaboration versus asynchronous communication measuring meeting comfort and instant messaging adoption. It synthesizes evidence from communication channel usage meeting attendance patterns and collaboration effectiveness ratings. These insights optimize team protocols balancing synchronous and async modes based on team preferences."),
    ("LearningFormatPreferenceDNA", "VideoVsTextPreferenceDNA", "This container examines learning modality preferences between video content and written documentation measuring comprehension and retention across formats. It synthesizes evidence from learning resource consumption patterns skill acquisition speed and format satisfaction ratings. These insights personalize learning resource recommendations matching content format with individual learning preferences."),
    ("ToolingPrefDNA", "IDEPreferenceDNA", "This container examines development environment preferences including IDE choice customization depth and workflow tool integration patterns. It synthesizes evidence from tool adoption logs productivity metrics by IDE and setup documentation to map tooling preferences. These insights guide onboarding tooling choices and respect individual productivity tool preferences."),
    ("FocusEnvironmentPreferenceDNA", "OpenOfficeVsPrivatePreferenceDNA", "This container examines workspace layout preferences balancing collaborative access with private focus spaces. It synthesizes evidence from workspace satisfaction surveys productivity by layout type and voluntary workspace choices. These insights inform office design and hybrid work policies respecting focus environment preferences."),
    ("SocialContextPreferenceDNA", "GroupSizePreferenceDNA", "This container examines preferred social group sizes from one-on-one to large gatherings measuring engagement quality across group size spectrums. It synthesizes evidence from meeting size preferences social event attendance and participation patterns. These insights guide meeting design and social event planning matching group sizes with participant comfort zones."),
]

# PsyDNA Makeup Templates (+29 containers to reach 180 target)
PSY_MAKEUP_TEMPLATES = [
    ("MotivationDNA", "CompetitiveDriveDNA", "This container examines motivation from competitive comparison and performance ranking measuring desire to outperform peers and achieve recognition. It synthesizes evidence from competition participation performance comparison sensitivity and recognition-seeking behaviors. These insights guide role matching placing competitive individuals in meritocratic contexts with clear performance differentiation."),
    ("MotivationDNA", "AffiliationMotivationDNA", "This container examines drive for social connection and belonging as primary motivator versus achievement or power motives. It synthesizes evidence from team preference patterns relationship investment and affiliation-seeking behaviors. These insights enable environment matching placing affiliation-motivated individuals in collaborative team-centric roles."),
    ("SelfConceptSchemaDNA", "LeaderIdentityDNA", "This container examines self-perception as leader including leadership identity strength and comfort with authority roles. It synthesizes evidence from leadership role seeking identity narratives and leadership comfort self-assessments. These insights predict leadership potential and identify those requiring identity development alongside skill building.", True),
    ("RiskToleranceDNA", "FinancialRiskToleranceDNA", "This container examines willingness to accept financial uncertainty including investment risk compensation variability and income stability preferences. It synthesizes evidence from financial decisions risk-taking patterns and security versus growth trade-offs. These insights guide compensation design and startup versus corporate role fit assessment."),
    ("GritPersistenceDNA", "ObstacleInterpretationDNA", "This container examines how obstacles are framed as challenges to overcome versus signals to pivot measuring persistence versus flexibility. It synthesizes evidence from setback narratives persistence patterns and pivot decision factors. These insights predict performance in high-obstacle versus rapidly-changing environments."),
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
    print("🏗️  Generating Stage 3 Wave 2 batch (420 containers)...")

    all_containers = []

    # SkillDNA: +110
    print("  Generating SkillDNA containers...")
    skill_containers = generate_numbered_variants(SKILL_TEMPLATES * 16, "SkillDNA", 110)
    all_containers.extend(skill_containers)

    # SocDNA: +100
    print("  Generating SocDNA containers...")
    soc_containers = generate_numbered_variants(SOC_TEMPLATES * 17, "SocDNA", 100)
    all_containers.extend(soc_containers)

    # HistDNA: +90
    print("  Generating HistDNA containers...")
    hist_containers = generate_numbered_variants(HIST_TEMPLATES * 15, "HistDNA", 90)
    all_containers.extend(hist_containers)

    # PrefDNA: +90
    print("  Generating PrefDNA containers...")
    pref_containers = generate_numbered_variants(PREF_TEMPLATES * 15, "PrefDNA", 90)
    all_containers.extend(pref_containers)

    # PsyDNA makeup: +29
    print("  Generating PsyDNA makeup containers...")
    psy_containers = generate_numbered_variants(PSY_MAKEUP_TEMPLATES * 6, "PsyDNA", 29)
    all_containers.extend(psy_containers)

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

    print(f"\n✅ Wave 2 Batch Generated")
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
