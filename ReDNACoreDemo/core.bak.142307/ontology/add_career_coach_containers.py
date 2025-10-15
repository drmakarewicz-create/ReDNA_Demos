#!/usr/bin/env python3
"""
Add Career Coach DNA containers to the ontology registry.
Follows strict governance rules for depth ≤3, status=prototype, ai_upgradable=true.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# ═══════════════════════════════════════════════════════════════════
# CAREER COACH DNA HIERARCHY SPECIFICATION
# ═══════════════════════════════════════════════════════════════════

CAREER_COACH_DNA = {
    "SkillDNA": {
        "CommunicationSkillDNA": {
            "description": "Communication skills across modalities and contexts",
            "sub_sub_dnas": [
                {"name": "WrittenCommunicationDNA", "description": "Written communication clarity and effectiveness"},
                {"name": "VerbalCommunicationDNA", "description": "Verbal communication and articulation skills"},
                {"name": "PresentationDeliveryDNA", "description": "Presentation delivery and public speaking skills"},
                {"name": "ActiveListeningDNA", "description": "Active listening and comprehension skills"},
                {"name": "StakeholderCommunicationDNA", "description": "Stakeholder communication and alignment skills"}
            ]
        },
        "AnalyticalSkillDNA": {
            "description": "Analytical and data-driven reasoning skills",
            "sub_sub_dnas": [
                {"name": "DataAnalysisDNA", "description": "Data analysis and interpretation capabilities"},
                {"name": "QuantitativeReasoningDNA", "description": "Quantitative reasoning and numerical analysis"},
                {"name": "ResearchSynthesisDNA", "description": "Research synthesis and insight extraction"}
            ]
        },
        "ProjectDeliverySkillDNA": {
            "description": "Project delivery and execution skills",
            "sub_sub_dnas": [
                {"name": "PlanningDNA", "description": "Project planning and roadmapping capabilities"},
                {"name": "EstimationDNA", "description": "Effort estimation and scoping accuracy"},
                {"name": "RiskManagementDNA", "description": "Risk identification and mitigation skills"},
                {"name": "DependencyManagementDNA", "description": "Dependency tracking and management skills"}
            ]
        },
        "LeadershipSkillDNA": {
            "description": "Leadership and people management skills",
            "sub_sub_dnas": [
                {"name": "PeopleManagementDNA", "description": "People management and team leadership"},
                {"name": "MentoringCoachingDNA", "description": "Mentoring and coaching capabilities"},
                {"name": "DecisionMakingDNA", "description": "Strategic decision-making skills"}
            ]
        },
        "CollaborationSkillDNA": {
            "description": "Collaboration and teamwork skills",
            "sub_sub_dnas": [
                {"name": "CrossFunctionalDNA", "description": "Cross-functional collaboration effectiveness"},
                {"name": "ConflictMediationDNA", "description": "Conflict resolution and mediation skills"}
            ]
        },
        "WritingSkillDNA": {
            "description": "Writing skills across contexts",
            "sub_sub_dnas": [
                {"name": "TechnicalWritingDNA", "description": "Technical writing and documentation skills"},
                {"name": "BusinessWritingDNA", "description": "Business writing and executive communication"}
            ]
        },
        "CreativityInnovationSkillDNA": {
            "description": "Creativity and innovation capabilities",
            "sub_sub_dnas": [
                {"name": "IdeationDivergenceDNA", "description": "Ideation and divergent thinking skills"},
                {"name": "ProblemFramingDNA", "description": "Problem framing and reframing capabilities"}
            ]
        },
        "LearningAdaptationSkillDNA": {
            "description": "Learning and adaptation capabilities",
            "sub_sub_dnas": [
                {"name": "MetaLearningDNA", "description": "Meta-learning and learning-to-learn skills"},
                {"name": "ToolAdoptionDNA", "description": "Tool adoption and technology learning speed"}
            ]
        }
    },
    "ProfDNA": {
        "OccupationRoleDNA": {
            "description": "Professional occupation and role",
            "sub_sub_dnas": [
                {"name": "RoleArchetypeDNA", "description": "Role archetype and functional classification"},
                {"name": "FunctionFamilyDNA", "description": "Function family and domain specialization"}
            ]
        },
        "SeniorityTenureDNA": {
            "description": "Seniority level and tenure patterns",
            "sub_sub_dnas": [
                {"name": "LevelDNA", "description": "Organizational level and career stage"},
                {"name": "YearsInFunctionDNA", "description": "Years of experience in current function"}
            ]
        },
        "DomainKnowledgeMapDNA": {
            "description": "Domain knowledge and expertise mapping",
            "sub_sub_dnas": [
                {"name": "IndustryGenericDNA", "description": "Industry-specific knowledge and context"},
                {"name": "RegulatoryGenericDNA", "description": "Regulatory and compliance knowledge"}
            ]
        },
        "CollaborationCadenceDNA": {
            "description": "Collaboration patterns and cadence preferences",
            "sub_sub_dnas": [
                {"name": "MeetingLoadDNA", "description": "Meeting load and calendar density"},
                {"name": "AsyncSyncBalanceDNA", "description": "Async vs sync communication balance"}
            ]
        },
        "ComplianceRiskGovernanceDNA": {
            "description": "Compliance orientation and risk governance",
            "sub_sub_dnas": [
                {"name": "PolicyAdherenceDNA", "description": "Policy adherence and process compliance"},
                {"name": "RiskAwarenessDNA", "description": "Risk awareness and mitigation orientation"}
            ]
        },
        "WorkOutcomeDNA": {
            "description": "Work outcomes and performance metrics",
            "sub_sub_dnas": [
                {"name": "OKRAlignmentDNA", "description": "OKR alignment and goal achievement"},
                {"name": "KPIFulfillmentDNA", "description": "KPI fulfillment and metric performance"}
            ]
        },
        "WorkContractContextDNA": {
            "description": "Work contract and employment context",
            "sub_sub_dnas": [
                {"name": "EmploymentTypeDNA", "description": "Employment type and contract structure"},
                {"name": "WorkModeDNA", "description": "Work mode and location preferences"}
            ]
        }
    },
    "BehDNA": {
        "ProductivityWorkflowDNA": {
            "description": "Productivity patterns and workflow preferences",
            "sub_sub_dnas": [
                {"name": "FocusBlocksDNA", "description": "Deep focus blocks and concentration patterns"},
                {"name": "TaskManagementDNA", "description": "Task management and prioritization approach"},
                {"name": "ContextSwitchingDNA", "description": "Context switching patterns and tolerance"}
            ]
        },
        "MeetingBehaviorDNA": {
            "description": "Meeting behavior and participation patterns",
            "sub_sub_dnas": [
                {"name": "PunctualityDNA", "description": "Meeting punctuality and time respect"},
                {"name": "ParticipationDNA", "description": "Meeting participation and engagement level"}
            ]
        },
        "DailyRhythmChronoDNA": {
            "description": "Daily rhythms and chronotype",
            "sub_sub_dnas": [
                {"name": "WorkWindowPreferenceDNA", "description": "Preferred work windows and energy peaks"}
            ]
        },
        "WorkBreakHabitDNA": {
            "description": "Work break patterns and recovery habits",
            "sub_sub_dnas": [
                {"name": "RecoveryMicrobreaksDNA", "description": "Recovery microbreaks and rest patterns"}
            ]
        },
        "ProcrastinationStyleDNA": {
            "description": "Procrastination patterns and styles",
            "sub_sub_dnas": []
        }
    },
    "SocDNA": {
        "TeamCommunicationDNA": {
            "description": "Team communication patterns and effectiveness",
            "sub_sub_dnas": [
                {"name": "StatusUpdatesDNA", "description": "Status update frequency and clarity"},
                {"name": "FeedbackExchangeDNA", "description": "Feedback exchange patterns and receptivity"}
            ]
        },
        "StakeholderManagementDNA": {
            "description": "Stakeholder management and relationship building",
            "sub_sub_dnas": [
                {"name": "ExpectationSettingDNA", "description": "Expectation setting and alignment skills"},
                {"name": "DiplomacyDNA", "description": "Diplomatic communication and tact"}
            ]
        },
        "NegotiationInfluenceDNA": {
            "description": "Negotiation and influence strategies",
            "sub_sub_dnas": []
        },
        "LeadershipFollowershipDNA": {
            "description": "Leadership and followership dynamics",
            "sub_sub_dnas": []
        }
    },
    "PsyDNA": {
        "MotivationDNA": {
            "description": "Motivational drivers and orientations",
            "sub_sub_dnas": [
                {"name": "AchievementDriveDNA", "description": "Achievement motivation and drive"},
                {"name": "AutonomyNeedDNA", "description": "Autonomy need and self-direction preference"},
                {"name": "PurposeAlignmentDNA", "description": "Purpose alignment and meaning-making"}
            ]
        },
        "PersonalityDNA": {
            "description": "Core personality traits and models",
            "sub_sub_dnas": [
                {"name": "ConscientiousnessDNA", "description": "Conscientiousness and organizational tendencies"},
                {"name": "OpennessDNA", "description": "Openness to experience and novelty seeking"},
                {"name": "ExtraversionDNA", "description": "Extraversion and social energy patterns"},
                {"name": "AgreeablenessDNA", "description": "Agreeableness and cooperative tendencies"},
                {"name": "EmotionalStabilityDNA", "description": "Emotional stability and resilience"}
            ]
        },
        "GritPersistenceDNA": {
            "description": "Grit, persistence, and long-term goal pursuit",
            "sub_sub_dnas": []
        },
        "RiskToleranceDNA": {
            "description": "Risk tolerance and uncertainty navigation",
            "sub_sub_dnas": []
        }
    },
    "EmDNA": {
        "StressResilienceDNA": {
            "description": "Stress response and resilience patterns",
            "sub_sub_dnas": [
                {"name": "RecoveryCapacityDNA", "description": "Recovery capacity and bounce-back speed"},
                {"name": "TriggerSensitivityDNA", "description": "Stress trigger sensitivity and thresholds"}
            ]
        },
        "EmotionRegulationAtWorkDNA": {
            "description": "Emotion regulation in professional contexts",
            "sub_sub_dnas": []
        }
    },
    "CogDNA": {
        "ProblemSolvingStrategyDNA": {
            "description": "Problem-solving strategies and approaches",
            "sub_sub_dnas": [
                {"name": "SystematicApproachDNA", "description": "Systematic problem-solving methodology"},
                {"name": "HeuristicApproachDNA", "description": "Heuristic-based problem-solving patterns"}
            ]
        },
        "SystemsThinkingDNA": {
            "description": "Systems thinking and holistic reasoning",
            "sub_sub_dnas": []
        },
        "AttentionControlDNA": {
            "description": "Attentional control and focus patterns",
            "sub_sub_dnas": [
                {"name": "SustainedAttentionDNA", "description": "Sustained attention and focus duration"},
                {"name": "TaskSwitchingDNA", "description": "Task switching speed and cognitive flexibility"}
            ]
        },
        "WorkingMemoryDNA": {
            "description": "Working memory capacity and utilization",
            "sub_sub_dnas": []
        },
        "LearningStyleStrategyDNA": {
            "description": "Learning preferences and strategies",
            "sub_sub_dnas": []
        }
    },
    "HistDNA": {
        "CareerTrajectoryDNA": {
            "description": "Career history and progression",
            "sub_sub_dnas": [
                {"name": "RoleHistoryDNA", "description": "Role progression and career transitions"},
                {"name": "ProjectPortfolioHistoryDNA", "description": "Project portfolio and accomplishments history"}
            ]
        },
        "CertificationCredentialDNA": {
            "description": "Certifications, credentials, and formal training",
            "sub_sub_dnas": [
                {"name": "ProfessionalCertsDNA", "description": "Professional certifications and licenses"},
                {"name": "TrainingCoursesDNA", "description": "Training courses and professional development"}
            ]
        }
    },
    "PrefDNA": {
        "WorkEnvironmentPrefDNA": {
            "description": "Work environment and culture preferences",
            "sub_sub_dnas": [
                {"name": "RemoteHybridOnsiteDNA", "description": "Remote vs hybrid vs onsite preference"},
                {"name": "OpenOfficePreferenceDNA", "description": "Open office vs private space preference"}
            ]
        },
        "CollaborationModePrefDNA": {
            "description": "Collaboration mode preferences and styles",
            "sub_sub_dnas": [
                {"name": "AsyncPreferenceDNA", "description": "Async communication preference strength"},
                {"name": "MeetingToleranceDNA", "description": "Meeting tolerance and optimal frequency"}
            ]
        },
        "ManagementStylePrefDNA": {
            "description": "Management style preferences and expectations",
            "sub_sub_dnas": [
                {"name": "CoachingVsDirectingDNA", "description": "Coaching vs directing management preference"}
            ]
        },
        "ToolingPrefDNA": {
            "description": "Tooling and software preferences",
            "sub_sub_dnas": [
                {"name": "PMToolPreferenceDNA", "description": "Project management tool preferences"},
                {"name": "DocumentationToolPreferenceDNA", "description": "Documentation tool preferences"}
            ]
        },
        "IndustryPreferenceDNA": {
            "description": "Industry sector and domain preferences",
            "sub_sub_dnas": []
        }
    },
    "EnvDNA": {
        "DigitalWorkContextDNA": {
            "description": "Digital work environment and toolchain context",
            "sub_sub_dnas": [
                {"name": "PrimaryToolchainDNA", "description": "Primary toolchain and software stack"},
                {"name": "CommunicationStackDNA", "description": "Communication stack and platform usage"}
            ]
        },
        "TimezoneWorkWindowDNA": {
            "description": "Timezone and work window context",
            "sub_sub_dnas": [
                {"name": "CoreHoursDNA", "description": "Core working hours and availability windows"}
            ]
        },
        "MeetingLoadContextDNA": {
            "description": "Current meeting load and calendar context",
            "sub_sub_dnas": []
        }
    },
    "MetaDNA": {
        "TrainingWillingnessDNA": {
            "description": "Willingness to train and correct the system",
            "sub_sub_dnas": []
        },
        "GuidanceOpennessAutonomyDNA": {
            "description": "Openness to guidance vs. preference for autonomy",
            "sub_sub_dnas": []
        }
    },
    "HealthDNA": {
        "SleepPhysiologyDNA": {
            "description": "Sleep physiology and patterns",
            "sub_sub_dnas": []
        },
        "MobilityPainFatigueDNA": {
            "description": "Mobility, pain levels, and fatigue patterns",
            "sub_sub_dnas": []
        },
        "EnergyFatiguePatternDNA": {
            "description": "Energy and fatigue patterns throughout the day",
            "sub_sub_dnas": [],
            "sensitive": True,
            "consent_required": True
        }
    }
}

# Cross-links to add (correlates_with edges)
CROSS_LINKS = [
    {
        "from": "SkillDNA.CommunicationSkillDNA.PresentationDeliveryDNA",
        "to": "SocDNA.TeamCommunicationDNA",
        "evidence_score": 0.5
    },
    {
        "from": "SkillDNA.ProjectDeliverySkillDNA.PlanningDNA",
        "to": "BehDNA.ProductivityWorkflowDNA.FocusBlocksDNA",
        "evidence_score": 0.5
    },
    {
        "from": "PsyDNA.MotivationDNA.PurposeAlignmentDNA",
        "to": "ProfDNA.WorkOutcomeDNA.OKRAlignmentDNA",
        "evidence_score": 0.5
    },
    {
        "from": "PrefDNA.WorkEnvironmentPrefDNA.RemoteHybridOnsiteDNA",
        "to": "ProfDNA.WorkContractContextDNA.WorkModeDNA",
        "evidence_score": 0.5
    },
    {
        "from": "CogDNA.AttentionControlDNA.TaskSwitchingDNA",
        "to": "BehDNA.ProductivityWorkflowDNA.ContextSwitchingDNA",
        "evidence_score": 0.5
    },
    {
        "from": "EmDNA.StressResilienceDNA.RecoveryCapacityDNA",
        "to": "BehDNA.WorkBreakHabitDNA.RecoveryMicrobreaksDNA",
        "evidence_score": 0.5
    }
]


def create_container(
    path: str,
    namespace: str,
    description: str,
    sensitive: bool = False,
    camouflage: bool = False,
    consent_required: bool = False,
    parent_path: Optional[str] = None,
    edge_type: str = "part_of"
) -> Dict[str, Any]:
    """Create a DNA container record following governance rules."""
    now = datetime.now(timezone.utc).isoformat()

    container = {
        "id": f"{path}.v1",
        "namespace": namespace,
        "path": path,
        "version": 1,
        "status": "prototype",  # Career Coach containers are prototype
        "description": description,
        "inputs": [],
        "outputs": [],
        "ucn_weight_hint": 0.01,
        "dependencies": [],
        "correlates_with": [],
        "contradicts": [],
        "sensitive": sensitive,
        "camouflage": camouflage,
        "consent_required": consent_required,
        "ai_upgradable": True,
        "rr_baseline": None,
        "curiosity_baseline": 100,
        "discovery": {
            "method": "manual",
            "confidence": 1.0,
            "evidence": "Career Coach DNA expansion - Ontology v1",
            "proposer": "career_coach_builder"
        },
        "parent_containers": [],
        "tags": [namespace.lower().replace("dna", "")],
        "examples": [],
        "validation_rules": {
            "value_type": "categorical",
            "allowed_values": []
        },
        "created_at": now,
        "updated_at": now,
        "created_by": "career_coach_builder",
        "changelog": [
            {
                "version": 1,
                "timestamp": now,
                "changes": "Initial creation via Career Coach DNA expansion",
                "author": "career_coach_builder"
            }
        ]
    }

    # Add parent relationship if provided
    if parent_path:
        container["parent_containers"].append({
            "path": parent_path,
            "edge_type": edge_type
        })

    return container


def load_registry(filepath: str) -> Dict[str, Any]:
    """Load the existing DNA registry."""
    with open(filepath, 'r') as f:
        return json.load(f)


def save_registry(registry: Dict[str, Any], filepath: str):
    """Save the updated DNA registry."""
    with open(filepath, 'w') as f:
        json.dump(registry, f, indent=2)


def find_container_by_path(containers: List[Dict], path: str) -> Optional[Dict]:
    """Find a container by its path."""
    for container in containers:
        if container["path"] == path:
            return container
    return None


def add_career_coach_containers(registry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, int]]:
    """Add Career Coach DNA containers to the registry."""
    containers = registry["containers"]
    namespace_counts = registry["metadata"]["namespace_counts"]
    added_counts = {}

    # Track containers to add (we'll add them all at once at the end)
    new_containers = []

    for umbrella, sub_dnas in CAREER_COACH_DNA.items():
        if umbrella not in added_counts:
            added_counts[umbrella] = 0

        # Get umbrella-level sensitivity settings
        umbrella_container = find_container_by_path(containers, umbrella)
        umbrella_sensitive = umbrella_container["sensitive"] if umbrella_container else False
        umbrella_camouflage = umbrella_container["camouflage"] if umbrella_container else False
        umbrella_consent = umbrella_container.get("consent_required", False) if umbrella_container else False

        for sub_dna, sub_spec in sub_dnas.items():
            sub_path = f"{umbrella}.{sub_dna}"

            # Check if sub-DNA already exists
            existing_sub = find_container_by_path(containers, sub_path)
            if not existing_sub:
                # Use container-specific sensitivity if provided, otherwise inherit from umbrella
                sensitive = sub_spec.get("sensitive", umbrella_sensitive)
                consent_required = sub_spec.get("consent_required", umbrella_consent)

                sub_container = create_container(
                    path=sub_path,
                    namespace=umbrella,
                    description=sub_spec["description"],
                    sensitive=sensitive,
                    camouflage=umbrella_camouflage,
                    consent_required=consent_required,
                    parent_path=umbrella,
                    edge_type="part_of"
                )
                new_containers.append(sub_container)
                added_counts[umbrella] += 1
                print(f"  + {sub_path}")
            else:
                print(f"  ✓ {sub_path} (already exists)")

            # Add sub-sub-DNAs
            for sub_sub_spec in sub_spec.get("sub_sub_dnas", []):
                if isinstance(sub_sub_spec, dict):
                    sub_sub_name = sub_sub_spec["name"]
                    sub_sub_desc = sub_sub_spec["description"]
                else:
                    sub_sub_name = sub_sub_spec
                    sub_sub_desc = f"{sub_sub_spec} characteristics"

                sub_sub_path = f"{sub_path}.{sub_sub_name}"

                # Check if sub-sub-DNA already exists
                existing_sub_sub = find_container_by_path(containers, sub_sub_path)
                if not existing_sub_sub:
                    # Use container-specific sensitivity if provided, otherwise inherit
                    sensitive = sub_spec.get("sensitive", umbrella_sensitive)
                    consent_required = sub_spec.get("consent_required", umbrella_consent)

                    sub_sub_container = create_container(
                        path=sub_sub_path,
                        namespace=umbrella,
                        description=sub_sub_desc,
                        sensitive=sensitive,
                        camouflage=umbrella_camouflage,
                        consent_required=consent_required,
                        parent_path=sub_path,
                        edge_type="part_of"
                    )
                    new_containers.append(sub_sub_container)
                    added_counts[umbrella] += 1
                    print(f"    + {sub_sub_path}")
                else:
                    print(f"    ✓ {sub_sub_path} (already exists)")

    # Add all new containers to the registry
    containers.extend(new_containers)

    # Update namespace counts
    for umbrella, count in added_counts.items():
        if umbrella in namespace_counts:
            namespace_counts[umbrella] += count
        else:
            namespace_counts[umbrella] = count

    # Update metadata
    registry["metadata"]["total_containers"] = len(containers)
    registry["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    return registry, added_counts


def add_cross_links(registry: Dict[str, Any]) -> int:
    """Add correlates_with cross-links between containers."""
    containers = registry["containers"]
    links_added = 0

    for link_spec in CROSS_LINKS:
        from_path = link_spec["from"]
        to_path = link_spec["to"]
        evidence_score = link_spec["evidence_score"]

        from_container = find_container_by_path(containers, from_path)
        to_container = find_container_by_path(containers, to_path)

        if from_container and to_container:
            # Check if link already exists
            existing_links = [c["path"] for c in from_container.get("correlates_with", [])]
            if to_path not in existing_links:
                from_container["correlates_with"].append({
                    "path": to_path,
                    "evidence_score": evidence_score
                })
                links_added += 1
                print(f"  ✓ {from_path} ↔ {to_path}")
            else:
                print(f"  - {from_path} ↔ {to_path} (already exists)")
        else:
            if not from_container:
                print(f"  ✗ Missing container: {from_path}")
            if not to_container:
                print(f"  ✗ Missing container: {to_path}")

    return links_added


def validate_depth(containers: List[Dict]) -> Dict[str, int]:
    """Validate that all containers have depth ≤3 and return depth histogram."""
    depth_histogram = {1: 0, 2: 0, 3: 0}

    for container in containers:
        path = container["path"]
        depth = path.count(".") + 1
        if depth <= 3:
            depth_histogram[depth] = depth_histogram.get(depth, 0) + 1
        else:
            print(f"  ✗ DEPTH VIOLATION: {path} (depth={depth})")

    return depth_histogram


def main():
    """Main entry point."""
    print("Adding Career Coach DNA Containers to Ontology Registry")
    print("=" * 70)

    # Load existing registry
    registry_path = "/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/ontology/dna_registry.json"
    print(f"\n📖 Loading registry from: {registry_path}")
    registry = load_registry(registry_path)

    print(f"   Current total: {registry['metadata']['total_containers']} containers")

    # Add Career Coach containers
    print(f"\n📦 Adding Career Coach containers...")
    registry, added_counts = add_career_coach_containers(registry)

    # Add cross-links
    print(f"\n🔗 Adding cross-links...")
    links_added = add_cross_links(registry)

    # Validate depth
    print(f"\n✅ Validating depth constraints...")
    depth_histogram = validate_depth(registry["containers"])

    # Save updated registry
    print(f"\n💾 Saving updated registry...")
    save_registry(registry, registry_path)

    # Print summary
    print(f"\n" + "=" * 70)
    print(f"✓ COMPLETE - Career Coach DNA Containers Added")
    print(f"=" * 70)
    print(f"\n📊 Summary:")
    print(f"   Total containers: {registry['metadata']['total_containers']}")
    print(f"   Containers added: {sum(added_counts.values())}")
    print(f"   Cross-links added: {links_added}")

    print(f"\n📊 Containers added by umbrella:")
    for umbrella in sorted(added_counts.keys()):
        count = added_counts[umbrella]
        if count > 0:
            total = registry['metadata']['namespace_counts'][umbrella]
            print(f"   {umbrella:12s} +{count:2d} (total: {total})")

    print(f"\n📊 Depth histogram:")
    for depth, count in sorted(depth_histogram.items()):
        print(f"   Depth {depth}: {count:4d} containers")

    print(f"\n✓ Registry saved to: {registry_path}")
    print(f"\n🔍 Next step: Run the linter to validate the registry")
    print(f"   python ReDNACoreDemo/core/ontology/ontology_linter.py")


if __name__ == "__main__":
    main()
