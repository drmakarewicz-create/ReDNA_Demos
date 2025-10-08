#!/usr/bin/env python3
"""
DNA Registry Builder - Ontology v1 Baseline
Builds the canonical DNA hierarchy according to the Container Explosion specification.

Generates:
- 14 umbrella namespaces
- Complete sub-DNA and sub-sub-DNA hierarchy (depth ≤3)
- All containers with rr_baseline=null, curiosity_baseline=100
- Sensitive and camouflage flags per specification
- Parent/child relationships with is_a and part_of edges
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# ═══════════════════════════════════════════════════════════════════
# DNA HIERARCHY SPECIFICATION
# ═══════════════════════════════════════════════════════════════════

DNA_HIERARCHY = {
    "PaDNA": {
        "full_name": "Physical Appearance DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "FaceDNA": {
                "description": "Facial features and structure",
                "sub_sub_dnas": [
                    "ForeheadDNA",
                    "EyeRegionDNA",
                    "NoseDNA",
                    "CheekMalarDNA",
                    "LipsMouthDNA",
                    "JawlineMandibleDNA",
                    "ChinMentalDNA",
                    "DentitionOralDNA",
                    "FacialSymmetryDNA",
                    "FacialHairDNA"
                ]
            },
            "HairDNA": {
                "description": "Hair characteristics across the body",
                "sub_sub_dnas": [
                    "ScalpHairDNA",
                    "BodyHairDNA",
                    "HairlineCrownDNA"
                ]
            },
            "EyeDNA": {
                "description": "Eye characteristics and dynamics",
                "sub_sub_dnas": [
                    "IrisDNA",
                    "PupilIrisDynamicsDNA",
                    "ScleraPeriocularDNA"
                ]
            },
            "SkinDNA": {
                "description": "Skin tone, texture, and conditions",
                "sub_sub_dnas": [
                    "TonePigmentDNA",
                    "SurfaceTextureDNA",
                    "MarkingsScarsDNA",
                    "ConditionsDermDNA"
                ]
            },
            "BodyDNA": {
                "description": "Body structure, proportions, and movement",
                "sub_sub_dnas": [
                    "SkeletalProportionDNA",
                    "SoftTissueMorphologyDNA",
                    "PostureSpineDNA",
                    "GaitLocomotionDNA",
                    "HandsFeetExtremitiesDNA"
                ]
            },
            "VoiceOlfactionMotionDNA": {
                "description": "Voice, scent, and kinesthetic presentation",
                "sub_sub_dnas": [
                    "VoiceTimbreProsodyDNA",
                    "OlfactionScentDNA",
                    "GestureKinesicsDNA"
                ]
            }
        }
    },
    "PsyDNA": {
        "full_name": "Psychological DNA",
        "sensitive": True,
        "camouflage": False,
        "sub_dnas": {
            "PersonalityDNA": {
                "description": "Core personality traits and models",
                "sub_sub_dnas": [
                    "FactorModelDNA",
                    "TypeModelDNA",
                    "TemperamentDNA"
                ]
            },
            "MotivationDNA": {
                "description": "Motivational drivers and orientations",
                "sub_sub_dnas": [
                    "GoalOrientationDNA",
                    "NoveltyPersistenceDNA",
                    "ControlSpontaneityDNA"
                ]
            },
            "BeliefValueDNA": {
                "description": "Belief systems and value orientations",
                "sub_sub_dnas": [
                    "PhilosophicalStanceDNA",
                    "SociopoliticalOrientationDNA",
                    "ReligiousSpiritualOrientationDNA",
                    "MoralFoundationDNA"
                ]
            },
            "SelfConceptSchemaDNA": {
                "description": "Self-concept and identity narratives",
                "sub_sub_dnas": [
                    "SelfEsteemSelfEfficacyDNA",
                    "IdentityNarrativeDNA"
                ]
            }
        }
    },
    "EmDNA": {
        "full_name": "Emotional DNA",
        "sensitive": True,
        "camouflage": False,
        "sub_dnas": {
            "AffectBaselineDNA": {
                "description": "Baseline affective state and mood tendencies",
                "sub_sub_dnas": []
            },
            "EmotionRegulationDNA": {
                "description": "Emotion regulation strategies and effectiveness",
                "sub_sub_dnas": []
            },
            "ReactivityArousalDNA": {
                "description": "Emotional reactivity and arousal patterns",
                "sub_sub_dnas": []
            },
            "EmpathyCompassionDNA": {
                "description": "Empathic response and compassionate tendencies",
                "sub_sub_dnas": []
            },
            "AttachmentStyleDNA": {
                "description": "Attachment styles in relationships",
                "sub_sub_dnas": []
            },
            "AngerGuiltShameDNA": {
                "description": "Patterns of anger, guilt, and shame experiences",
                "sub_sub_dnas": []
            },
            "GratitudeForgivenessDNA": {
                "description": "Gratitude expression and forgiveness tendencies",
                "sub_sub_dnas": []
            },
            "ConflictEmotionalStyleDNA": {
                "description": "Emotional responses and styles during conflict",
                "sub_sub_dnas": []
            }
        }
    },
    "CogDNA": {
        "full_name": "Cognitive DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "MemorySystemsDNA": {
                "description": "Memory systems and capacities",
                "sub_sub_dnas": [
                    "WorkingEpisodicSemanticDNA"
                ]
            },
            "ProcessingDynamicsDNA": {
                "description": "Cognitive processing speed, load, and flexibility",
                "sub_sub_dnas": [
                    "SpeedLoadFlexibilityDNA"
                ]
            },
            "ReasoningProblemSolvingDNA": {
                "description": "Reasoning and problem-solving approaches",
                "sub_sub_dnas": [
                    "LogicalAbstractPatternDNA"
                ]
            },
            "CreativityDivergenceDNA": {
                "description": "Creative thinking and divergent thought patterns",
                "sub_sub_dnas": []
            },
            "AttentionControlDNA": {
                "description": "Attentional control and focus patterns",
                "sub_sub_dnas": [
                    "SustainedSelectiveShiftDNA"
                ]
            },
            "MetacognitionInsightDNA": {
                "description": "Metacognitive awareness and insight",
                "sub_sub_dnas": []
            },
            "LearningStyleStrategyDNA": {
                "description": "Learning preferences and strategies",
                "sub_sub_dnas": []
            },
            "LanguageCognitionDNA": {
                "description": "Language processing and linguistic cognition",
                "sub_sub_dnas": []
            }
        }
    },
    "SocDNA": {
        "full_name": "Social/Relational Style DNA",
        "sensitive": True,
        "camouflage": False,
        "sub_dnas": {
            "InteractionStyleDNA": {
                "description": "Social interaction patterns and styles",
                "sub_sub_dnas": [
                    "ConversationalDominanceListeningDNA",
                    "StorytellingHumorInGroupsDNA"
                ]
            },
            "RolePreferenceDNA": {
                "description": "Preferred roles in social contexts",
                "sub_sub_dnas": [
                    "LeadershipFollowershipDNA",
                    "CaregiverSupportDNA"
                ]
            },
            "TrustBoundaryReciprocityDNA": {
                "description": "Trust formation, boundaries, and reciprocity norms",
                "sub_sub_dnas": []
            },
            "NegotiationInfluenceDNA": {
                "description": "Negotiation and influence strategies",
                "sub_sub_dnas": []
            },
            "SocialAdaptabilityNetworkingDNA": {
                "description": "Social adaptability and networking tendencies",
                "sub_sub_dnas": []
            },
            "GroupAlignmentIdentityDNA": {
                "description": "Group alignment and collective identity",
                "sub_sub_dnas": []
            }
        }
    },
    "BehDNA": {
        "full_name": "Behavioral DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "HabitRoutinesDNA": {
                "description": "Habitual behaviors and routines",
                "sub_sub_dnas": [
                    "SleepHabitDNA",
                    "EatingNutritionHabitDNA",
                    "ExerciseActivityHabitDNA"
                ]
            },
            "ProductivityWorkflowDNA": {
                "description": "Productivity patterns and workflow preferences",
                "sub_sub_dnas": []
            },
            "RiskTakingSafetyDNA": {
                "description": "Risk-taking and safety-seeking behaviors",
                "sub_sub_dnas": []
            },
            "AddictivePatternDNA": {
                "description": "Addictive behavior patterns and susceptibilities",
                "sub_sub_dnas": []
            },
            "DailyRhythmChronoDNA": {
                "description": "Daily rhythms and chronotype",
                "sub_sub_dnas": []
            },
            "MicroBehaviorTicksDNA": {
                "description": "Micro-behaviors and behavioral tics",
                "sub_sub_dnas": []
            },
            "ProcrastinationStyleDNA": {
                "description": "Procrastination patterns and styles",
                "sub_sub_dnas": []
            }
        }
    },
    "HistDNA": {
        "full_name": "Historical/Contextual DNA",
        "sensitive": True,
        "camouflage": False,
        "sub_dnas": {
            "DemographicRootDNA": {
                "description": "Demographic roots and origins",
                "sub_sub_dnas": [
                    "BirthplaceNationalityDNA",
                    "CulturalHeritageDNA"
                ]
            },
            "LanguageUseHistoryDNA": {
                "description": "Language use history and multilingual background",
                "sub_sub_dnas": []
            },
            "EducationTrajectoryDNA": {
                "description": "Educational history and trajectory",
                "sub_sub_dnas": []
            },
            "CareerTrajectoryDNA": {
                "description": "Career history and progression",
                "sub_sub_dnas": []
            },
            "SocioeconomicContextDNA": {
                "description": "Socioeconomic background and context",
                "sub_sub_dnas": []
            },
            "FamilyStructureHistoryDNA": {
                "description": "Family structure and relationship history",
                "sub_sub_dnas": []
            },
            "LifeEventsMilestonesDNA": {
                "description": "Major life events and milestones",
                "sub_sub_dnas": [
                    "TraumaAdversityResilienceDNA"
                ]
            },
            "TravelExposureBreadthDNA": {
                "description": "Travel experiences and cultural exposure breadth",
                "sub_sub_dnas": []
            }
        }
    },
    "PrefDNA": {
        "full_name": "Preferences & Taste DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "FoodTasteDietPrefDNA": {
                "description": "Food preferences, taste, and dietary choices",
                "sub_sub_dnas": []
            },
            "EntertainmentPrefDNA": {
                "description": "Entertainment preferences and media consumption",
                "sub_sub_dnas": []
            },
            "LifestyleSettingPrefDNA": {
                "description": "Lifestyle and environmental setting preferences",
                "sub_sub_dnas": []
            },
            "FashionStylePrefDNA": {
                "description": "Fashion and personal style preferences",
                "sub_sub_dnas": []
            },
            "AestheticPalettePrefDNA": {
                "description": "Aesthetic palette and design preferences",
                "sub_sub_dnas": []
            },
            "RelationshipPreferenceDNA": {
                "description": "Relationship and partnership preferences",
                "sub_sub_dnas": []
            },
            "WorkEnvironmentPrefDNA": {
                "description": "Work environment and culture preferences",
                "sub_sub_dnas": []
            },
            "HobbyInterestPrefDNA": {
                "description": "Hobby and interest preferences",
                "sub_sub_dnas": []
            },
            "CollectingAcquisitionPrefDNA": {
                "description": "Collecting behaviors and acquisition preferences",
                "sub_sub_dnas": []
            },
            "TechToolPrefDNA": {
                "description": "Technology and tool preferences",
                "sub_sub_dnas": []
            }
        }
    },
    "SkillDNA": {
        "full_name": "Skills & Competencies DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "TechnicalComputationalSkillDNA": {
                "description": "Technical and computational skills",
                "sub_sub_dnas": []
            },
            "ArtisticCreativeSkillDNA": {
                "description": "Artistic and creative competencies",
                "sub_sub_dnas": []
            },
            "AthleticPhysicalSkillDNA": {
                "description": "Athletic and physical skills",
                "sub_sub_dnas": []
            },
            "InterpersonalSkillDNA": {
                "description": "Interpersonal and communication skills",
                "sub_sub_dnas": []
            },
            "LinguisticSkillDNA": {
                "description": "Language and linguistic competencies",
                "sub_sub_dnas": []
            },
            "ManagerialOrganizationalSkillDNA": {
                "description": "Managerial and organizational skills",
                "sub_sub_dnas": []
            },
            "InnovationProblemMakingDNA": {
                "description": "Innovation and problem-creation skills",
                "sub_sub_dnas": []
            },
            "DomainSpecificSkillDNA": {
                "description": "Domain-specific expertise and skills",
                "sub_sub_dnas": []
            }
        }
    },
    "MetaDNA": {
        "full_name": "Meta/System Interaction DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "SystemTrustSkepticismDNA": {
                "description": "Trust and skepticism toward the ReDNA system",
                "sub_sub_dnas": []
            },
            "GuidanceOpennessAutonomyDNA": {
                "description": "Openness to guidance vs. preference for autonomy",
                "sub_sub_dnas": []
            },
            "TransparencyComfortPrivacyPrefDNA": {
                "description": "Comfort with transparency and privacy preferences",
                "sub_sub_dnas": []
            },
            "ExplanationPreferenceDNA": {
                "description": "Preferences for explanations and rationales",
                "sub_sub_dnas": []
            },
            "FeedbackStyleDNA": {
                "description": "Preferred feedback style and frequency",
                "sub_sub_dnas": []
            },
            "TrainingWillingnessDNA": {
                "description": "Willingness to train and correct the system",
                "sub_sub_dnas": []
            },
            "EngagementPatternDNA": {
                "description": "System engagement patterns and behaviors",
                "sub_sub_dnas": []
            },
            "MetaCuriosityDNA": {
                "description": "Curiosity about the ontology and system design",
                "sub_sub_dnas": []
            }
        }
    },
    "HealthDNA": {
        "full_name": "Health/Bio/Physiology DNA",
        "sensitive": True,
        "camouflage": False,
        "consent_required": True,
        "sub_dnas": {
            "VitalsPhysiologyDNA": {
                "description": "Vital signs and physiological metrics",
                "sub_sub_dnas": []
            },
            "ConditionsDiagnosisDNA": {
                "description": "Health conditions and diagnoses",
                "sub_sub_dnas": []
            },
            "MedicationAllergyDNA": {
                "description": "Medications and allergies",
                "sub_sub_dnas": []
            },
            "SleepPhysiologyDNA": {
                "description": "Sleep physiology and patterns",
                "sub_sub_dnas": []
            },
            "NutritionBiomarkerDNA": {
                "description": "Nutritional biomarkers and status",
                "sub_sub_dnas": []
            },
            "MobilityPainFatigueDNA": {
                "description": "Mobility, pain levels, and fatigue patterns",
                "sub_sub_dnas": []
            }
        }
    },
    "RoDNA": {
        "full_name": "Relational/Intimacy DNA",
        "sensitive": True,
        "camouflage": True,
        "sub_dnas": {
            "PartneringStyleDNA": {
                "description": "Romantic partnering styles and preferences",
                "sub_sub_dnas": []
            },
            "AttractionVectorDNA": {
                "description": "Attraction patterns and vectors",
                "sub_sub_dnas": []
            },
            "BoundaryComfortDNA": {
                "description": "Relationship boundaries and comfort zones",
                "sub_sub_dnas": []
            },
            "AttachmentDyadicDNA": {
                "description": "Dyadic attachment patterns in romantic relationships",
                "sub_sub_dnas": []
            },
            "LoveLanguageExpressionDNA": {
                "description": "Love language expression and reception",
                "sub_sub_dnas": []
            },
            "SexualExpressionDNA": {
                "description": "Sexual expression and intimacy patterns",
                "sub_sub_dnas": []
            },
            "FamilyBondDynamicDNA": {
                "description": "Family bond dynamics and relationship patterns",
                "sub_sub_dnas": []
            }
        }
    },
    "ProfDNA": {
        "full_name": "Professional/Work DNA",
        "sensitive": False,
        "camouflage": False,
        "sub_dnas": {
            "OccupationRoleDNA": {
                "description": "Professional occupation and role",
                "sub_sub_dnas": []
            },
            "SeniorityTenureDNA": {
                "description": "Seniority level and tenure patterns",
                "sub_sub_dnas": []
            },
            "WorkStyleDecisionDNA": {
                "description": "Work style and decision-making approach",
                "sub_sub_dnas": []
            },
            "ComplianceRiskGovernanceDNA": {
                "description": "Compliance orientation and risk governance",
                "sub_sub_dnas": []
            },
            "CollaborationCadenceDNA": {
                "description": "Collaboration patterns and cadence preferences",
                "sub_sub_dnas": []
            },
            "DomainKnowledgeMapDNA": {
                "description": "Domain knowledge and expertise mapping",
                "sub_sub_dnas": []
            },
            "CareerAspirationsMobilityDNA": {
                "description": "Career aspirations and mobility patterns",
                "sub_sub_dnas": []
            }
        }
    },
    "EnvDNA": {
        "full_name": "Environment & Context DNA",
        "sensitive": True,
        "camouflage": False,
        "sub_dnas": {
            "HomeLivingContextDNA": {
                "description": "Home and living environment context",
                "sub_sub_dnas": []
            },
            "DigitalFootprintContextDNA": {
                "description": "Digital footprint and online context",
                "sub_sub_dnas": []
            },
            "MobilityCommuteContextDNA": {
                "description": "Mobility patterns and commute context",
                "sub_sub_dnas": []
            },
            "ClimateLightNoiseContextDNA": {
                "description": "Climate, light, and noise environmental factors",
                "sub_sub_dnas": []
            }
        }
    }
}


def create_container(
    path: str,
    namespace: str,
    description: str,
    sensitive: bool,
    camouflage: bool = False,
    consent_required: bool = False,
    parent_path: Optional[str] = None,
    edge_type: str = "part_of"
) -> Dict[str, Any]:
    """Create a DNA container record."""
    now = datetime.now(timezone.utc).isoformat()

    container = {
        "id": f"{path}.v1",
        "namespace": namespace,
        "path": path,
        "version": 1,
        "status": "stable",
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
            "evidence": "Ontology v1 baseline specification",
            "proposer": "build_registry.py"
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
        "created_by": "ontology_v1_builder",
        "changelog": [
            {
                "version": 1,
                "timestamp": now,
                "changes": "Initial creation via Ontology v1 baseline specification",
                "author": "ontology_v1_builder"
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


def build_registry() -> Dict[str, Any]:
    """Build the complete DNA registry."""
    containers = []
    namespace_counts = {}

    # Build hierarchy
    for umbrella, umbrella_spec in DNA_HIERARCHY.items():
        namespace_counts[umbrella] = 0

        sensitive = umbrella_spec.get("sensitive", False)
        camouflage = umbrella_spec.get("camouflage", False)
        consent_required = umbrella_spec.get("consent_required", False)

        # Create umbrella container
        umbrella_container = create_container(
            path=umbrella,
            namespace=umbrella,
            description=umbrella_spec["full_name"],
            sensitive=sensitive,
            camouflage=camouflage,
            consent_required=consent_required
        )
        containers.append(umbrella_container)
        namespace_counts[umbrella] += 1

        # Create sub-DNA containers
        for sub_dna, sub_spec in umbrella_spec["sub_dnas"].items():
            sub_path = f"{umbrella}.{sub_dna}"
            sub_container = create_container(
                path=sub_path,
                namespace=umbrella,
                description=sub_spec["description"],
                sensitive=sensitive,
                camouflage=camouflage,
                consent_required=consent_required,
                parent_path=umbrella,
                edge_type="part_of"
            )
            containers.append(sub_container)
            namespace_counts[umbrella] += 1

            # Create sub-sub-DNA containers
            for sub_sub_dna in sub_spec.get("sub_sub_dnas", []):
                sub_sub_path = f"{sub_path}.{sub_sub_dna}"
                sub_sub_container = create_container(
                    path=sub_sub_path,
                    namespace=umbrella,
                    description=f"{sub_sub_dna} characteristics",
                    sensitive=sensitive,
                    camouflage=camouflage,
                    consent_required=consent_required,
                    parent_path=sub_path,
                    edge_type="part_of"
                )
                containers.append(sub_sub_container)
                namespace_counts[umbrella] += 1

    # Build registry
    registry = {
        "metadata": {
            "version": "1.0.0",
            "total_containers": len(containers),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "namespace_counts": namespace_counts,
            "generation_method": "ontology_v1_baseline",
            "target_count": 1000,
            "ontology_version": "v1",
            "description": "DNA-only hierarchy (umbrellas, sub-DNAs, sub-sub-DNAs). No traits yet. Ready for container explosion 1k→10k→100k→1M."
        },
        "containers": containers
    }

    return registry


def main():
    """Main entry point."""
    print("Building DNA Registry (Ontology v1 Baseline)...")
    print("=" * 70)

    registry = build_registry()

    # Write to file
    output_path = "dna_registry.json"
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"\n✓ Registry built successfully!")
    print(f"  Total containers: {registry['metadata']['total_containers']}")
    print(f"  Output: {output_path}")
    print(f"\nNamespace breakdown:")
    for ns, count in sorted(registry['metadata']['namespace_counts'].items()):
        print(f"  {ns:12s} {count:3d} containers")

    print(f"\n✓ Ready for linting and validation")


if __name__ == "__main__":
    main()
