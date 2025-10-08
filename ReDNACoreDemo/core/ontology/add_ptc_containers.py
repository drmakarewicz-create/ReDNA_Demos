#!/usr/bin/env python3
"""
Add Personality Test Coach (PTC) DNA containers to the ontology registry.
Follows strict governance rules for depth ≤3, status=prototype, ai_upgradable=true.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# ═══════════════════════════════════════════════════════════════════
# PERSONALITY TEST COACH DNA HIERARCHY SPECIFICATION
# ═══════════════════════════════════════════════════════════════════

PTC_DNA = {
    "PsyDNA": {
        # PersonalityDNA umbrella (32 containers)
        "PersonalityDNA": {
            "description": "Core personality traits and individual differences",
            "sub_dnas": {
                # BigFiveDNA structure (6 containers)
                "BigFiveDNA": {
                    "description": "Big Five personality model (OCEAN)",
                    "sub_sub_dnas": [
                        {"name": "OpennessDNA", "description": "Openness to experience and intellectual curiosity"},
                        {"name": "ConscientiousnessDNA", "description": "Conscientiousness, organization, and self-discipline"},
                        {"name": "ExtraversionDNA", "description": "Extraversion, social energy, and assertiveness"},
                        {"name": "AgreeablenessDNA", "description": "Agreeableness, compassion, and cooperative tendencies"},
                        {"name": "EmotionalStabilityDNA", "description": "Emotional stability, resilience, and stress tolerance"}
                    ]
                },
                # Openness Facets (4 containers)
                "OpennessFacetsDNA": {
                    "description": "Facets of Openness to experience",
                    "sub_sub_dnas": [
                        {"name": "ImaginationCreativityDNA", "description": "Imagination, creativity, and fantasy proneness"},
                        {"name": "IntellectCuriosityDNA", "description": "Intellectual curiosity and love of learning"},
                        {"name": "AestheticSensitivityDNA", "description": "Aesthetic sensitivity and appreciation for beauty"}
                    ]
                },
                # Conscientiousness Facets (4 containers)
                "ConscientiousnessFacetsDNA": {
                    "description": "Facets of Conscientiousness",
                    "sub_sub_dnas": [
                        {"name": "OrderlinessDNA", "description": "Orderliness, organization, and preference for structure"},
                        {"name": "IndustriousnessDNA", "description": "Industriousness, work ethic, and achievement striving"},
                        {"name": "SelfDisciplineDNA", "description": "Self-discipline, self-control, and impulse regulation"}
                    ]
                },
                # Extraversion Facets (4 containers)
                "ExtraversionFacetsDNA": {
                    "description": "Facets of Extraversion",
                    "sub_sub_dnas": [
                        {"name": "AssertivenessDNA", "description": "Assertiveness, dominance, and social confidence"},
                        {"name": "EnergySociabilityDNA", "description": "Social energy, gregariousness, and sociability"},
                        {"name": "PositiveAffectivityDNA", "description": "Positive affectivity, enthusiasm, and cheerfulness"}
                    ]
                },
                # Agreeableness Facets (4 containers)
                "AgreeablenessFacetsDNA": {
                    "description": "Facets of Agreeableness",
                    "sub_sub_dnas": [
                        {"name": "CompassionDNA", "description": "Compassion, empathy, and concern for others"},
                        {"name": "PolitenessDNA", "description": "Politeness, respect, and deference to social norms"},
                        {"name": "TrustDNA", "description": "Trust in others and belief in human goodness"}
                    ]
                },
                # Emotional Stability Facets (4 containers)
                "EmotionalStabilityFacetsDNA": {
                    "description": "Facets of Emotional Stability",
                    "sub_sub_dnas": [
                        {"name": "StressToleranceDNA", "description": "Stress tolerance and ability to remain calm under pressure"},
                        {"name": "EmotionVolatilityDNA", "description": "Emotion volatility and mood fluctuation patterns"},
                        {"name": "SelfSoothingDNA", "description": "Self-soothing capacity and emotional recovery"}
                    ]
                },
                # HEXACO Additions (2 containers)
                "HexacoAdditionsDNA": {
                    "description": "Additional dimensions from HEXACO model",
                    "sub_sub_dnas": [
                        {"name": "HonestyHumilityDNA", "description": "Honesty-humility and ethical orientation"}
                    ]
                },
                # Type Model (2 containers)
                "TypeModelDNA": {
                    "description": "Type-based personality models (e.g., MBTI-style)",
                    "sub_sub_dnas": [
                        {"name": "CognitivePreferenceDNA", "description": "Cognitive preference patterns and information processing styles"}
                    ]
                },
                # Dark Traits (4 containers - SENSITIVE)
                "DarkTraitsDNA": {
                    "description": "Dark triad personality traits",
                    "sensitive": True,
                    "consent_required": True,
                    "sub_sub_dnas": [
                        {"name": "MachiavellianismDNA", "description": "Machiavellian tendencies and manipulative traits", "sensitive": True, "consent_required": True},
                        {"name": "NarcissismDNA", "description": "Narcissistic traits and grandiosity patterns", "sensitive": True, "consent_required": True},
                        {"name": "PsychopathyDNA", "description": "Psychopathic traits and callousness", "sensitive": True, "consent_required": True}
                    ]
                }
            }
        },
        # MotivationDNA (7 containers)
        "MotivationDNA": {
            "description": "Motivational drivers and goal orientations",
            "sub_sub_dnas": [
                {"name": "IntrinsicExtrinsicBalanceDNA", "description": "Balance between intrinsic and extrinsic motivation"},
                {"name": "AchievementDriveDNA", "description": "Achievement motivation and drive for excellence"},
                {"name": "AutonomyNeedDNA", "description": "Need for autonomy and self-direction"},
                {"name": "MasteryGrowthMotivationDNA", "description": "Mastery orientation and growth motivation"},
                {"name": "PurposeMeaningOrientationDNA", "description": "Purpose-driven orientation and meaning-making"},
                {"name": "NoveltySeekingVsRoutineDNA", "description": "Novelty seeking vs. routine preference"},
                {"name": "RewardSensitivityDNA", "description": "Sensitivity to rewards and reinforcement"}
            ]
        },
        # SelfConceptSchemaDNA (9 containers)
        "SelfConceptSchemaDNA": {
            "description": "Self-concept, self-schemas, and identity patterns",
            "sub_sub_dnas": [
                {"name": "SelfEsteemDNA", "description": "Self-esteem level and self-worth beliefs"},
                {"name": "SelfEfficacyDNA", "description": "Self-efficacy and belief in own capabilities"},
                {"name": "LocusOfControlDNA", "description": "Locus of control (internal vs external)"},
                {"name": "GrowthMindsetDNA", "description": "Growth mindset vs fixed mindset orientation"},
                {"name": "GritPersistenceDNA", "description": "Grit, persistence, and long-term goal pursuit"},
                {"name": "PerfectionismDNA", "description": "Perfectionism tendencies and standards"},
                {"name": "OptimismPessimismDNA", "description": "Optimism vs pessimism orientation"},
                {"name": "RiskToleranceDNA", "description": "Risk tolerance and uncertainty navigation"}
            ]
        },
        # BeliefValueDNA (5 containers)
        "BeliefValueDNA": {
            "description": "Beliefs, values, and worldview orientations",
            "sub_sub_dnas": [
                {"name": "MoralFoundationDNA", "description": "Moral foundations and ethical principles"},
                {"name": "LifePhilosophyDNA", "description": "Life philosophy and existential beliefs"},
                {"name": "ReligiousSpiritualOrientationDNA", "description": "Religious and spiritual orientation", "sensitive": True, "consent_required": True},
                {"name": "SociopoliticalOrientationDNA", "description": "Sociopolitical beliefs and orientations", "sensitive": True, "consent_required": True}
            ]
        }
    },
    "EmDNA": {
        # AffectBaselineDNA (3 containers)
        "AffectBaselineDNA": {
            "description": "Baseline affective states and emotional set points",
            "sub_sub_dnas": [
                {"name": "PositiveAffectDNA", "description": "Baseline positive affect and happiness set point"},
                {"name": "NegativeAffectDNA", "description": "Baseline negative affect and anxiety/depression tendencies"}
            ]
        },
        # EmotionRegulationDNA (3 containers)
        "EmotionRegulationDNA": {
            "description": "Emotion regulation strategies and patterns",
            "sub_sub_dnas": [
                {"name": "CognitiveReappraisalDNA", "description": "Cognitive reappraisal strategy use and effectiveness"},
                {"name": "SuppressionDNA", "description": "Emotional suppression patterns and tendencies"}
            ]
        },
        # ImpulsivityDNA (5 containers)
        "ImpulsivityDNA": {
            "description": "Impulsivity traits and self-control patterns",
            "sub_sub_dnas": [
                {"name": "UrgencyDNA", "description": "Urgency and tendency to act rashly under emotion"},
                {"name": "PremeditationDNA", "description": "Premeditation and planning before action"},
                {"name": "PerseveranceDNA", "description": "Perseverance and ability to stay on task"},
                {"name": "SensationSeekingDNA", "description": "Sensation seeking and thrill-seeking tendencies"}
            ]
        },
        # AttachmentStyleDNA (1 container)
        "AttachmentStyleDNA": {
            "description": "Attachment style and relational patterns",
            "sub_sub_dnas": []
        }
    },
    "CogDNA": {
        # CognitiveStyleDNA (5 containers)
        "CognitiveStyleDNA": {
            "description": "Cognitive styles and thinking preferences",
            "sub_sub_dnas": [
                {"name": "AnalyticalVsIntuitiveDNA", "description": "Analytical vs intuitive thinking preference"},
                {"name": "NeedForCognitionDNA", "description": "Need for cognition and enjoyment of thinking"},
                {"name": "ToleranceForAmbiguityDNA", "description": "Tolerance for ambiguity and uncertainty"},
                {"name": "NeedForClosureDNA", "description": "Need for closure and decisiveness"}
            ]
        },
        # AttentionControlDNA (3 containers)
        "AttentionControlDNA": {
            "description": "Attentional control and focus patterns",
            "sub_sub_dnas": [
                {"name": "SustainedAttentionDNA", "description": "Sustained attention and concentration ability"},
                {"name": "TaskSwitchingDNA", "description": "Task switching and cognitive flexibility"}
            ]
        },
        # WorkingMemoryDNA (1 container)
        "WorkingMemoryDNA": {
            "description": "Working memory capacity and utilization",
            "sub_sub_dnas": []
        },
        # CreativityDivergenceDNA (1 container)
        "CreativityDivergenceDNA": {
            "description": "Creativity and divergent thinking capacity",
            "sub_sub_dnas": []
        }
    },
    "SocDNA": {
        # SocialEnergyAssertivenessDNA (1 container)
        "SocialEnergyAssertivenessDNA": {
            "description": "Social energy levels and assertiveness in interactions",
            "sub_sub_dnas": []
        },
        # EmpathyPerspectiveDNA (3 containers)
        "EmpathyPerspectiveDNA": {
            "description": "Empathy and perspective-taking abilities",
            "sub_sub_dnas": [
                {"name": "CognitiveEmpathyDNA", "description": "Cognitive empathy and perspective-taking"},
                {"name": "AffectiveEmpathyDNA", "description": "Affective empathy and emotional resonance"}
            ]
        },
        # BoundarySettingDNA (1 container)
        "BoundarySettingDNA": {
            "description": "Boundary setting and interpersonal limits",
            "sub_sub_dnas": []
        },
        # SocialAnxietyShynessDNA (1 container - SENSITIVE)
        "SocialAnxietyShynessDNA": {
            "description": "Social anxiety and shyness tendencies",
            "sensitive": True,
            "consent_required": True,
            "sub_sub_dnas": []
        },
        # InfluenceCollaborationDNA (3 containers)
        "InfluenceCollaborationDNA": {
            "description": "Influence and collaboration dynamics",
            "sub_sub_dnas": [
                {"name": "AssertivenessDNA", "description": "Assertiveness and directiveness in groups"},
                {"name": "DiplomacyDNA", "description": "Diplomatic skill and tactful communication"}
            ]
        }
    },
    "BehDNA": {
        # HabitualReflectionDNA (1 container)
        "HabitualReflectionDNA": {
            "description": "Habitual reflection and self-examination patterns",
            "sub_sub_dnas": []
        },
        # MicroBehaviorConsistencyDNA (1 container)
        "MicroBehaviorConsistencyDNA": {
            "description": "Micro-behavior consistency and predictability",
            "sub_sub_dnas": []
        },
        # ProcrastinationStyleDNA (1 container)
        "ProcrastinationStyleDNA": {
            "description": "Procrastination patterns and delay behaviors",
            "sub_sub_dnas": []
        },
        # SleepChronoIndicatorDNA (1 container)
        "SleepChronoIndicatorDNA": {
            "description": "Sleep chronotype and circadian rhythm indicators",
            "sub_sub_dnas": []
        }
    },
    "PrefDNA": {
        # SocialContextPreferenceDNA (3 containers)
        "SocialContextPreferenceDNA": {
            "description": "Social context preferences and comfort zones",
            "sub_sub_dnas": [
                {"name": "SmallGroupVsLargeGroupDNA", "description": "Small group vs large group preference"},
                {"name": "StructuredVsSpontaneousDNA", "description": "Structured vs spontaneous interaction preference"}
            ]
        },
        # StimulationPreferenceDNA (3 containers)
        "StimulationPreferenceDNA": {
            "description": "Stimulation level preferences and optimal arousal",
            "sub_sub_dnas": [
                {"name": "HighStimulationSeekingDNA", "description": "High stimulation seeking and novelty preference"},
                {"name": "LowStimulationPreferenceDNA", "description": "Low stimulation preference and quiet environments"}
            ]
        },
        # ReflectionModePreferenceDNA (3 containers)
        "ReflectionModePreferenceDNA": {
            "description": "Reflection mode preferences and thinking styles",
            "sub_sub_dnas": [
                {"name": "SolitaryReflectionDNA", "description": "Solitary reflection and introspective thinking"},
                {"name": "DialogicReflectionDNA", "description": "Dialogic reflection and thinking-through-talking"}
            ]
        }
    },
    "MetaDNA": {
        # ResponseStyleValidityDNA (5 containers)
        "ResponseStyleValidityDNA": {
            "description": "Response style and validity indicators for assessments",
            "sub_sub_dnas": [
                {"name": "ImpressionManagementDNA", "description": "Impression management and self-presentation bias"},
                {"name": "SocialDesirabilityBiasDNA", "description": "Social desirability bias in responses"},
                {"name": "ExtremeResponseBiasDNA", "description": "Extreme response bias tendencies"},
                {"name": "AcquiescenceBiasDNA", "description": "Acquiescence bias and yea-saying tendencies"}
            ]
        },
        # TestInteractionDNA (4 containers)
        "TestInteractionDNA": {
            "description": "Test interaction patterns and assessment engagement",
            "sub_sub_dnas": [
                {"name": "AttentionChecksPassDNA", "description": "Attention check passage and engagement quality"},
                {"name": "ResponseConsistencyDNA", "description": "Response consistency across similar items"},
                {"name": "LatencyPatternDNA", "description": "Response latency patterns and speed"}
            ]
        }
    },
    "HistDNA": {
        # FormativeExperiencePatternDNA (3 containers)
        "FormativeExperiencePatternDNA": {
            "description": "Formative experiences shaping personality development",
            "sub_sub_dnas": [
                {"name": "CaretakingRolesHistoryDNA", "description": "History of caretaking roles and responsibilities"},
                {"name": "LeadershipRolesHistoryDNA", "description": "History of leadership roles and experiences"}
            ]
        },
        # CriticalLifeEventsDNA (2 containers)
        "CriticalLifeEventsDNA": {
            "description": "Critical life events and turning points",
            "sub_sub_dnas": [
                {"name": "IdentityShiftMomentsDNA", "description": "Identity shift moments and transformative experiences"}
            ]
        }
    }
}

# Cross-links to add (correlates_with edges with evidence_score: 0.5)
CROSS_LINKS = [
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.OpennessDNA",
        "to": "CogDNA.CreativityDivergenceDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.ConscientiousnessDNA",
        "to": "BehDNA.HabitualReflectionDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.ConscientiousnessDNA",
        "to": "CogDNA.CognitiveStyleDNA.NeedForClosureDNA",
        "evidence_score": 0.5,
        "is_negative": True  # Negative correlation
    },
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.ExtraversionDNA",
        "to": "SocDNA.SocialEnergyAssertivenessDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.AgreeablenessDNA",
        "to": "SocDNA.EmpathyPerspectiveDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "PsyDNA.PersonalityDNA.BigFiveDNA.EmotionalStabilityDNA",
        "to": "EmDNA.AffectBaselineDNA.NegativeAffectDNA",
        "evidence_score": 0.5,
        "is_negative": True  # Negative correlation
    },
    {
        "from": "PsyDNA.SelfConceptSchemaDNA.GritPersistenceDNA",
        "to": "PsyDNA.MotivationDNA.MasteryGrowthMotivationDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "EmDNA.EmotionRegulationDNA.CognitiveReappraisalDNA",
        "to": "CogDNA.CognitiveStyleDNA.AnalyticalVsIntuitiveDNA",
        "evidence_score": 0.5,
        "is_negative": False
    },
    {
        "from": "MetaDNA.ResponseStyleValidityDNA.SocialDesirabilityBiasDNA",
        "to": "MetaDNA.TestInteractionDNA.ResponseConsistencyDNA",
        "evidence_score": 0.5,
        "is_negative": False
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
        "status": "prototype",  # PTC containers are prototype
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
            "evidence": "Personality Test Coach DNA expansion - Ontology v1",
            "proposer": "ptc_builder"
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
        "created_by": "ptc_builder",
        "changelog": [
            {
                "version": 1,
                "timestamp": now,
                "changes": "Initial creation via Personality Test Coach DNA expansion",
                "author": "ptc_builder"
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


def add_ptc_containers(registry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, int], List[str]]:
    """Add PTC DNA containers to the registry."""
    containers = registry["containers"]
    namespace_counts = registry["metadata"]["namespace_counts"]
    added_counts = {}
    sensitive_containers = []

    # Track containers to add (we'll add them all at once at the end)
    new_containers = []

    for umbrella, sub_dnas in PTC_DNA.items():
        if umbrella not in added_counts:
            added_counts[umbrella] = 0

        # Get umbrella-level sensitivity settings
        umbrella_container = find_container_by_path(containers, umbrella)
        umbrella_sensitive = umbrella_container["sensitive"] if umbrella_container else False
        umbrella_camouflage = umbrella_container["camouflage"] if umbrella_container else False
        umbrella_consent = umbrella_container.get("consent_required", False) if umbrella_container else False

        for sub_dna_name, sub_spec in sub_dnas.items():
            # Handle nested PersonalityDNA structure
            if "sub_dnas" in sub_spec:
                # This is PersonalityDNA with nested structure
                parent_path = f"{umbrella}.{sub_dna_name}"

                # Check if parent exists
                existing_parent = find_container_by_path(containers, parent_path)
                if not existing_parent:
                    parent_container = create_container(
                        path=parent_path,
                        namespace=umbrella,
                        description=sub_spec["description"],
                        sensitive=umbrella_sensitive,
                        camouflage=umbrella_camouflage,
                        consent_required=umbrella_consent,
                        parent_path=umbrella,
                        edge_type="part_of"
                    )
                    new_containers.append(parent_container)
                    added_counts[umbrella] += 1
                    print(f"  + {parent_path}")
                else:
                    print(f"  ✓ {parent_path} (already exists)")

                # Add sub-DNAs under PersonalityDNA
                for nested_sub_name, nested_spec in sub_spec["sub_dnas"].items():
                    nested_path = f"{parent_path}.{nested_sub_name}"

                    existing_nested = find_container_by_path(containers, nested_path)
                    if not existing_nested:
                        # Check for sensitivity flags
                        sensitive = nested_spec.get("sensitive", umbrella_sensitive)
                        consent_required = nested_spec.get("consent_required", umbrella_consent)

                        if sensitive:
                            sensitive_containers.append(nested_path)

                        nested_container = create_container(
                            path=nested_path,
                            namespace=umbrella,
                            description=nested_spec["description"],
                            sensitive=sensitive,
                            camouflage=umbrella_camouflage,
                            consent_required=consent_required,
                            parent_path=parent_path,
                            edge_type="part_of"
                        )
                        new_containers.append(nested_container)
                        added_counts[umbrella] += 1
                        print(f"    + {nested_path}")
                    else:
                        print(f"    ✓ {nested_path} (already exists)")

                    # Add sub-sub-DNAs
                    for sub_sub_spec in nested_spec.get("sub_sub_dnas", []):
                        if isinstance(sub_sub_spec, dict):
                            sub_sub_name = sub_sub_spec["name"]
                            sub_sub_desc = sub_sub_spec["description"]
                            sub_sub_sensitive = sub_sub_spec.get("sensitive", sensitive)
                            sub_sub_consent = sub_sub_spec.get("consent_required", consent_required)
                        else:
                            sub_sub_name = sub_sub_spec
                            sub_sub_desc = f"{sub_sub_spec} characteristics"
                            sub_sub_sensitive = sensitive
                            sub_sub_consent = consent_required

                        sub_sub_path = f"{nested_path}.{sub_sub_name}"

                        existing_sub_sub = find_container_by_path(containers, sub_sub_path)
                        if not existing_sub_sub:
                            if sub_sub_sensitive:
                                sensitive_containers.append(sub_sub_path)

                            sub_sub_container = create_container(
                                path=sub_sub_path,
                                namespace=umbrella,
                                description=sub_sub_desc,
                                sensitive=sub_sub_sensitive,
                                camouflage=umbrella_camouflage,
                                consent_required=sub_sub_consent,
                                parent_path=nested_path,
                                edge_type="part_of"
                            )
                            new_containers.append(sub_sub_container)
                            added_counts[umbrella] += 1
                            print(f"      + {sub_sub_path}")
                        else:
                            print(f"      ✓ {sub_sub_path} (already exists)")
            else:
                # Regular structure (not PersonalityDNA)
                sub_path = f"{umbrella}.{sub_dna_name}"

                # Check if sub-DNA already exists
                existing_sub = find_container_by_path(containers, sub_path)
                if not existing_sub:
                    # Use container-specific sensitivity if provided, otherwise inherit from umbrella
                    sensitive = sub_spec.get("sensitive", umbrella_sensitive)
                    consent_required = sub_spec.get("consent_required", umbrella_consent)

                    if sensitive:
                        sensitive_containers.append(sub_path)

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
                        sub_sub_sensitive = sub_sub_spec.get("sensitive", sensitive)
                        sub_sub_consent = sub_sub_spec.get("consent_required", consent_required)
                    else:
                        sub_sub_name = sub_sub_spec
                        sub_sub_desc = f"{sub_sub_spec} characteristics"
                        sub_sub_sensitive = sensitive
                        sub_sub_consent = consent_required

                    sub_sub_path = f"{sub_path}.{sub_sub_name}"

                    # Check if sub-sub-DNA already exists
                    existing_sub_sub = find_container_by_path(containers, sub_sub_path)
                    if not existing_sub_sub:
                        if sub_sub_sensitive:
                            sensitive_containers.append(sub_sub_path)

                        sub_sub_container = create_container(
                            path=sub_sub_path,
                            namespace=umbrella,
                            description=sub_sub_desc,
                            sensitive=sub_sub_sensitive,
                            camouflage=umbrella_camouflage,
                            consent_required=sub_sub_consent,
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

    return registry, added_counts, sensitive_containers


def add_cross_links(registry: Dict[str, Any]) -> tuple[int, List[str]]:
    """Add correlates_with cross-links between containers."""
    containers = registry["containers"]
    links_added = 0
    issues = []

    for link_spec in CROSS_LINKS:
        from_path = link_spec["from"]
        to_path = link_spec["to"]
        evidence_score = link_spec["evidence_score"]
        is_negative = link_spec.get("is_negative", False)

        from_container = find_container_by_path(containers, from_path)
        to_container = find_container_by_path(containers, to_path)

        if from_container and to_container:
            # Check if link already exists
            existing_links = [c["path"] for c in from_container.get("correlates_with", [])]
            if to_path not in existing_links:
                correlation = {
                    "path": to_path,
                    "strength": evidence_score
                }
                if is_negative:
                    correlation["evidence"] = "Negative correlation (research-backed)"

                from_container["correlates_with"].append(correlation)
                links_added += 1

                correlation_type = "↔ (negative)" if is_negative else "↔"
                print(f"  ✓ {from_path} {correlation_type} {to_path}")
            else:
                print(f"  - {from_path} ↔ {to_path} (already exists)")
        else:
            if not from_container:
                issues.append(f"Missing source container: {from_path}")
            if not to_container:
                issues.append(f"Missing target container: {to_path}")

    return links_added, issues


def generate_report(added_counts: Dict[str, int], sensitive_containers: List[str],
                   links_added: int, initial_count: int, final_count: int,
                   issues: List[str]) -> str:
    """Generate a comprehensive addition report."""
    report = []
    report.append("=" * 80)
    report.append("PTC DNA CONTAINERS ADDITION REPORT")
    report.append("=" * 80)
    report.append("")

    report.append("CONTAINERS ADDED BY UMBRELLA DNA:")
    report.append("-" * 80)
    total_added = 0
    for umbrella in sorted(added_counts.keys()):
        count = added_counts[umbrella]
        total_added += count
        report.append(f"  {umbrella:20s} : +{count:3d} containers")
    report.append("-" * 80)
    report.append(f"  {'TOTAL ADDED':20s} : +{total_added:3d} containers")
    report.append("")

    report.append("REGISTRY TOTALS:")
    report.append("-" * 80)
    report.append(f"  Initial container count : {initial_count}")
    report.append(f"  Containers added        : {total_added}")
    report.append(f"  Final container count   : {final_count}")
    report.append("")

    report.append("SENSITIVE CONTAINERS:")
    report.append("-" * 80)
    report.append(f"  Total sensitive: {len(sensitive_containers)}")
    for path in sorted(sensitive_containers):
        report.append(f"    - {path}")
    report.append("")

    report.append("CROSS-LINKS:")
    report.append("-" * 80)
    report.append(f"  Total cross-links added: {links_added}")
    report.append("")

    if issues:
        report.append("ISSUES ENCOUNTERED:")
        report.append("-" * 80)
        for issue in issues:
            report.append(f"  ! {issue}")
        report.append("")
    else:
        report.append("No issues encountered.")
        report.append("")

    report.append("=" * 80)

    return "\n".join(report)


def main():
    """Main execution function."""
    registry_path = "/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/ontology/dna_registry.json"

    print("Loading DNA registry...")
    registry = load_registry(registry_path)
    initial_count = registry["metadata"]["total_containers"]

    print(f"\nInitial container count: {initial_count}")
    print("\nAdding PTC DNA containers...")
    print("=" * 80)

    registry, added_counts, sensitive_containers = add_ptc_containers(registry)

    print("\n" + "=" * 80)
    print("Adding cross-links...")
    print("=" * 80)

    links_added, issues = add_cross_links(registry)

    final_count = registry["metadata"]["total_containers"]

    print("\nSaving updated registry...")
    save_registry(registry, registry_path)

    # Generate and print report
    print("\n")
    report = generate_report(added_counts, sensitive_containers, links_added,
                           initial_count, final_count, issues)
    print(report)

    # Save report to file
    report_path = "/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/ontology/ptc_addition_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
