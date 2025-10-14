"""
DNA Container Generator

Deterministic generation rules for creating DNA containers at scale.
Implements the core generation strategies for reaching 1k → 10k → 100k → 1M containers.

Generation Strategies:
1. Family Explosion: Top families × attribute dimensions
2. Cross-Product: Cartesian combinations (Color × Shade, Texture × Pattern)
3. Residual Variance Catchers: Granular leaf containers for edge cases
4. Hierarchical Expansion: Auto-generate intermediate containers

All generation is deterministic and follows namespace rules from namespaces.yaml.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml


class DNAGenerator:
    """Generates DNA containers following deterministic rules."""

    def __init__(
        self,
        namespaces_path: Path,
        output_dir: Path | None = None
    ):
        self.namespaces_path = Path(namespaces_path)
        self.output_dir = Path(output_dir) if output_dir else self.namespaces_path.parent

        # Load namespace definitions
        with open(self.namespaces_path) as f:
            self.namespaces_config = yaml.safe_load(f)

        self.namespaces = self.namespaces_config.get("namespaces", {})
        self.naming_rules = self.namespaces_config.get("naming_rules", {})

        # Container registry
        self.containers: List[Dict[str, Any]] = []
        self.paths_seen: Set[str] = set()

    def generate_seed_registry(
        self,
        target_count: int = 1000,
        include_namespaces: List[str] | None = None
    ) -> Dict[str, Any]:
        """
        Generate seed registry with ~target_count containers.

        Args:
            target_count: Target number of containers (approximate)
            include_namespaces: List of namespaces to include (None = all)

        Returns:
            Complete registry dict ready for JSON serialization
        """
        self.containers = []
        self.paths_seen = set()

        namespaces_to_gen = include_namespaces or list(self.namespaces.keys())

        for namespace in namespaces_to_gen:
            if namespace not in self.namespaces:
                print(f"Warning: Unknown namespace {namespace}, skipping")
                continue

            ns_def = self.namespaces[namespace]
            print(f"Generating containers for {namespace}...")

            # Generate top-level namespace container
            self._generate_container(
                path=namespace,
                namespace=namespace,
                description=ns_def.get("description", ""),
                status="stable",
                sensitive=ns_def.get("sensitive", False)
            )

            # Generate top families
            top_families = ns_def.get("top_families", [])
            for family in top_families:
                family_path = f"{namespace}.{family}"
                self._generate_family_tree(family_path, namespace, depth=1)

        # Build final registry
        registry = {
            "metadata": {
                "version": "1.0.0",
                "total_containers": len(self.containers),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "namespace_counts": self._compute_namespace_counts(),
                "generation_method": "deterministic_seed",
                "target_count": target_count
            },
            "containers": sorted(self.containers, key=lambda c: c["path"])
        }

        return registry

    def _generate_family_tree(
        self,
        family_path: str,
        namespace: str,
        depth: int,
        max_depth: int = 4
    ) -> None:
        """
        Recursively generate family tree for a given family.

        Uses predefined expansion rules for common families.
        """
        if depth > max_depth:
            return

        ns_def = self.namespaces.get(namespace, {})
        ns_max_depth = ns_def.get("max_depth", 6)

        if depth > ns_max_depth:
            return

        # Generate this family container
        family_name = family_path.split(".")[-1]
        description = self._generate_description(family_path)

        self._generate_container(
            path=family_path,
            namespace=namespace,
            description=description,
            status="stable" if depth <= 2 else "candidate",
            sensitive=ns_def.get("sensitive", False),
            parent_path=".".join(family_path.split(".")[:-1]) if depth > 1 else None
        )

        # Apply expansion rules based on family type
        children = self._get_family_children(family_name, depth)

        for child in children:
            child_path = f"{family_path}.{child}"
            self._generate_family_tree(child_path, namespace, depth + 1, max_depth)

    def _get_family_children(self, family_name: str, depth: int) -> List[str]:
        """
        Get child containers for a given family based on expansion rules.

        This is where domain knowledge is encoded.
        """
        # Common attribute dimensions
        common_dimensions = {
            "ColorDNA": ["HueDNA", "SaturationDNA", "BrightnessDNA", "ShadeVariantDNA"],
            "TextureDNA": ["SmoothnessDNA", "RoughnessDNA", "PatternDNA", "FinishDNA"],
            "ShapeDNA": ["GeometryDNA", "ProportionDNA", "SymmetryDNA", "AngularityDNA"],
            "SizeDNA": ["LengthDNA", "WidthDNA", "DepthDNA", "VolumeDNA"],
            "StyleDNA": ["FormalityDNA", "ModernityDNA", "ComplexityDNA", "BoldnessDNA"],
        }

        # Physical appearance expansions
        padna_expansions = {
            "HairDNA": ["ColorDNA", "LengthDNA", "TextureDNA", "VolumeDNA", "StyleDNA", "HealthDNA"],
            "FaceDNA": ["ShapeDNA", "SymmetryDNA", "ProportionDNA", "ComplexionDNA"],
            "FacialDNA": ["FaceShapeDNA", "JawlineDNA", "CheekbonesDNA", "ForeheadDNA", "ChinDNA"],
            "EyeDNA": ["ColorDNA", "ShapeDNA", "SizeDNA", "SettingDNA", "LashesDNA", "BrowsDNA"],
            "EyebrowDNA": ["ShapeDNA", "ThicknessDNA", "ArchDNA", "ColorDNA", "SpacingDNA"],
            "NoseDNA": ["ShapeDNA", "SizeDNA", "BridgeDNA", "TipShapeDNA", "NostrilsDNA"],
            "LipDNA": ["ShapeDNA", "SizeDNA", "ColorDNA", "FullnessDNA", "SymmetryDNA"],
            "SkinDNA": ["ToneDNA", "UndertoneDNA", "TextureDNA", "ClarityDNA", "FrecklesDNA", "MolesDNA"],
            "BodyDNA": ["BuildDNA", "HeightDNA", "ProportionsDNA", "PostureDNA", "FitnessDNA"],
            "StyleDNA": ["AestheticDNA", "ColorPaletteDNA", "FitPreferenceDNA", "AccessoryStyleDNA"],
            "ApparelDNA": ["TopsDNA", "BottomsDNA", "DressesDNA", "OuterwearDNA", "FootwearDNA"],
            "AccessoryDNA": ["JewelryDNA", "BagsDNA", "HatsDNA", "ScarvesDNA", "BeltsDNA"],
            "MakeupDNA": ["FoundationDNA", "EyeMakeupDNA", "LipColorDNA", "BlushDNA", "ContourDNA"],
        }

        # Psychological expansions
        psydna_expansions = {
            "PersonalityDNA": ["OpennessLevelDNA", "ConscientiousnessLevelDNA", "ExtraversionLevelDNA",
                              "AgreeablenessLevelDNA", "NeuroticismLevelDNA"],
            "MotivationDNA": ["IntrinsicDriversDNA", "ExtrinsicDriversDNA", "GoalOrientationDNA", "AchievementNeedDNA"],
            "BeliefDNA": ["CoreBeliefsDNA", "WorldviewDNA", "SelfBeliefsDNA", "MoralFrameworkDNA"],
            "ValuesDNA": ["CoreValuesDNA", "PriorityHierarchyDNA", "EthicalStanceDNA"],
            "FearDNA": ["PhobiasDNA", "AnxietyTriggersDNA", "DeepFearsDNA", "AvoidancePatternsDNA"],
            "DreamDNA": ["AspirationsDNA", "LifeGoalsDNA", "FantasiesDNA", "IdealSelfDNA"],
        }

        # Emotional expansions
        emdna_expansions = {
            "BaselineDNA": ["DefaultMoodDNA", "EmotionalSetPointDNA", "AffectiveToneDNA"],
            "TriggerDNA": ["PositiveTriggersDNA", "NegativeTriggersDNA", "NeutralTriggersDNA"],
            "RegulationDNA": ["CopingStrategiesDNA", "SelfSoothingDNA", "EmotionalControlDNA"],
            "ExpressionDNA": ["DisplayRulesDNA", "ExpressivityDNA", "EmotionalVocabularyDNA"],
            "AttachmentDNA": ["AttachmentStyleDNA", "BondingPatternsDNA", "SecurityNeedsDNA"],
        }

        # Cognitive expansions
        cogdna_expansions = {
            "ThinkingStyleDNA": ["AnalyticalDNA", "IntuitivenessDNA", "CreativityDNA", "AbstractionDNA"],
            "LearningDNA": ["LearningStyleDNA", "InformationProcessingDNA", "MemoryFormationDNA"],
            "MemoryDNA": ["WorkingMemoryDNA", "LongTermMemoryDNA", "EpisodicMemoryDNA"],
            "AttentionDNA": ["FocusDurationDNA", "DistractibilityDNA", "SelectiveAttentionDNA"],
            "ProblemSolvingDNA": ["StrategyPreferenceDNA", "ComplexityHandlingDNA", "NoveltyApproachDNA"],
        }

        # Social DNA expansions
        socdna_expansions = {
            "SocialDNA": ["CommunicationStyleDNA", "GroupDynamicsDNA", "LeadershipDNA", "ConflictStyleDNA"],
            "CommunicationStyleDNA": ["VerbalStyleDNA", "NonVerbalStyleDNA", "ListeningStyleDNA", "AssertivenessDNA"],
            "GroupDynamicsDNA": ["RoleTendencyDNA", "CollaborationStyleDNA", "SocialInfluenceDNA"],
            "LeadershipDNA": ["LeadershipStyleDNA", "DecisionMakingDNA", "InfluenceMethodsDNA"],
        }

        # Relational DNA expansions
        redna_expansions = {
            "RelationshipDNA": ["AttachmentStyleDNA", "IntimacyPatternsDNA", "BoundaryStyleDNA", "ConflictResolutionDNA"],
            "AttachmentStyleDNA": ["SecureAttachmentDNA", "AnxiousAttachmentDNA", "AvoidantAttachmentDNA"],
            "IntimacyPatternsDNA": ["EmotionalIntimacyDNA", "PhysicalIntimacyDNA", "IntellectualIntimacyDNA"],
        }

        # Behavioral DNA expansions
        behdna_expansions = {
            "BehaviorDNA": ["HabitsDNA", "RoutinesDNA", "RiskTakingDNA", "ImpulsivityDNA"],
            "HabitsDNA": ["DailyHabitsDNA", "HealthHabitsDNA", "WorkHabitsDNA", "SocialHabitsDNA"],
            "RoutinesDNA": ["MorningRoutineDNA", "EveningRoutineDNA", "WeekendRoutineDNA"],
        }

        # Skill DNA expansions
        skilldna_expansions = {
            "SkillsDNA": ["TechnicalSkillsDNA", "SoftSkillsDNA", "CreativeSkillsDNA", "PhysicalSkillsDNA"],
            "TechnicalSkillsDNA": ["CodingSkillsDNA", "AnalyticalSkillsDNA", "ToolProficiencyDNA"],
            "SoftSkillsDNA": ["CommunicationSkillsDNA", "EmotionalIntelligenceDNA", "AdaptabilityDNA"],
        }

        # Preference DNA expansions
        prefdna_expansions = {
            "PreferenceDNA": ["ActivityPreferencesDNA", "EnvironmentPreferencesDNA", "SocialPreferencesDNA", "LearningPreferencesDNA"],
            "ActivityPreferencesDNA": ["LeisureActivitiesDNA", "WorkActivitiesDNA", "ExercisePreferencesDNA"],
            "EnvironmentPreferencesDNA": ["NoiseToleranceDNA", "TemperaturePreferenceDNA", "LightingPreferenceDNA"],
            "SocialPreferencesDNA": ["GroupSizePreferenceDNA", "SocialFrequencyDNA", "IntimacyPreferenceDNA"],
        }

        # Goals DNA expansions
        goalsdna_expansions = {
            "GoalsDNA": ["ShortTermGoalsDNA", "LongTermGoalsDNA", "LifeVisionDNA", "AspirationalSelfDNA"],
            "ShortTermGoalsDNA": ["MonthlyGoalsDNA", "QuarterlyGoalsDNA", "YearlyGoalsDNA"],
            "LongTermGoalsDNA": ["FiveYearPlanDNA", "TenYearVisionDNA", "LifetimeAmbitionsDNA"],
        }

        # Heritage DNA expansions
        heritdna_expansions = {
            "HeritageDNA": ["CulturalBackgroundDNA", "LanguageHeritageDNA", "TraditionsDNA", "ValueInheritanceDNA"],
            "CulturalBackgroundDNA": ["EthnicityDNA", "NationalityDNA", "RegionalCultureDNA"],
            "TraditionsDNA": ["FamilyTraditionsDNA", "CulturalRitualsDNA", "HolidayPracticesDNA"],
        }

        # History DNA expansions
        histdna_expansions = {
            "HistoryDNA": ["ChildhoodDNA", "AdolescenceDNA", "AdulthoodDNA", "MajorEventsDNA"],
            "ChildhoodDNA": ["EarlyMemoriesDNA", "FamilyDynamicsDNA", "SchoolExperienceDNA"],
            "MajorEventsDNA": ["LifeTransitionsDNA", "TraumaHistoryDNA", "AchievementsDNA"],
        }

        # Health DNA expansions
        healthdna_expansions = {
            "HealthDNA": ["PhysicalHealthDNA", "MentalHealthDNA", "SleepDNA", "NutritionDNA", "ExerciseDNA"],
            "PhysicalHealthDNA": ["ChronicConditionsDNA", "EnergyLevelsDNA", "MobilityDNA", "PainPatternsDNA"],
            "MentalHealthDNA": ["MoodPatternsDNA", "StressLevelsDNA", "AnxietyPatternsDNA", "ResilienceDNA"],
            "SleepDNA": ["SleepQualityDNA", "SleepDurationDNA", "SleepScheduleDNA", "DreamPatternsDNA"],
        }

        # Bio DNA expansions
        biodna_expansions = {
            "BiologyDNA": ["GeneticMarkersDNA", "BiometricsBaseDNA", "CircadianRhythmDNA", "MetabolicProfileDNA"],
            "BiometricsBaseDNA": ["HeightDNA", "WeightDNA", "BMIRangeDNA", "BodyCompositionDNA"],
            "MetabolicProfileDNA": ["MetabolicRateDNA", "EnergyExpenditureDNA", "NutrientProcessingDNA"],
        }

        # Financial DNA expansions
        findna_expansions = {
            "FinancialDNA": ["SpendingPatternsDNA", "SavingBehaviorDNA", "InvestmentStyleDNA", "FinancialGoalsDNA"],
            "SpendingPatternsDNA": ["CategorySpendingDNA", "ImpulseBuyingDNA", "ValueAssessmentDNA"],
            "SavingBehaviorDNA": ["SavingsRateDNA", "EmergencyFundDNA", "RetirementPlanningDNA"],
        }

        # Family DNA expansions
        familydna_expansions = {
            "FamilyDNA": ["ParentingStyleDNA", "SiblingDynamicsDNA", "FamilyRolesDNA", "IntergenerationalPatternsDNA"],
            "ParentingStyleDNA": ["DisciplineApproachDNA", "EmotionalSupportDNA", "EducationPriorityDNA"],
            "FamilyRolesDNA": ["TraditionalRolesDNA", "ResponsibilityDistributionDNA", "DecisionAuthorityDNA"],
        }

        # Career DNA expansions
        careerdna_expansions = {
            "CareerDNA": ["WorkStyleDNA", "CareerGoalsDNA", "ProfessionalIdentityDNA", "WorkLifeBalanceDNA"],
            "WorkStyleDNA": ["TaskApproachDNA", "CollaborationPreferenceDNA", "AutonomyNeedDNA", "FeedbackStyleDNA"],
            "CareerGoalsDNA": ["AdvancementGoalsDNA", "SkillDevelopmentDNA", "LegacyAspirationsDNA"],
        }

        # Meta DNA expansions
        metadna_expansions = {
            "MetaDNA": ["SelfAwarenessDNA", "PersonalGrowthDNA", "IdentityDNA", "ReflectionStyleDNA"],
            "SelfAwarenessDNA": ["EmotionalAwarenessDNA", "StrengthsAwarenessDNA", "BlindSpotsDNA"],
            "PersonalGrowthDNA": ["GrowthMindsetDNA", "LearningOrientationDNA", "ChangeReadinessDNA"],
        }

        # Combine all expansion rules
        expansion_map = {
            **common_dimensions,
            **padna_expansions,
            **psydna_expansions,
            **emdna_expansions,
            **cogdna_expansions,
            **socdna_expansions,
            **redna_expansions,
            **behdna_expansions,
            **skilldna_expansions,
            **prefdna_expansions,
            **goalsdna_expansions,
            **heritdna_expansions,
            **histdna_expansions,
            **healthdna_expansions,
            **biodna_expansions,
            **findna_expansions,
            **familydna_expansions,
            **careerdna_expansions,
            **metadna_expansions,
        }

        # Return children if defined, otherwise return empty list
        return expansion_map.get(family_name, [])

    def _generate_container(
        self,
        path: str,
        namespace: str,
        description: str,
        status: str = "prototype",
        sensitive: bool = False,
        parent_path: str | None = None,
        ucn_weight_hint: float = 0.01
    ) -> Dict[str, Any]:
        """Generate a single container definition."""
        if path in self.paths_seen:
            return None  # Already generated

        self.paths_seen.add(path)

        now = datetime.now(timezone.utc).isoformat()
        version = 1

        container = {
            "id": f"{path}.v{version}",
            "namespace": namespace,
            "path": path,
            "version": version,
            "status": status,
            "description": description,
            "inputs": [],
            "outputs": [],
            "ucn_weight_hint": ucn_weight_hint,
            "dependencies": [],
            "correlates_with": [],
            "contradicts": [],
            "sensitive": sensitive,
            "consent_required": sensitive,
            "ai_upgradable": True,
            "discovery": {
                "method": "deterministic_generation",
                "confidence": 1.0,
                "evidence": "Generated from ontology expansion rules",
                "proposer": "dna_generator.py"
            },
            "parent_containers": [],
            "tags": self._generate_tags(path),
            "examples": [],
            "validation_rules": self._generate_validation_rules(path),
            "created_at": now,
            "updated_at": now,
            "created_by": "system_generator",
            "changelog": [
                {
                    "version": 1,
                    "timestamp": now,
                    "changes": "Initial creation via deterministic generation",
                    "author": "system_generator"
                }
            ]
        }

        # Add parent relationship if provided
        if parent_path:
            container["parent_containers"].append({
                "path": parent_path,
                "edge_type": "is_a"
            })

        self.containers.append(container)
        return container

    def _generate_description(self, path: str) -> str:
        """Generate human-readable description from path."""
        parts = path.split(".")
        if len(parts) == 1:
            # Top-level namespace
            return self.namespaces.get(path, {}).get("description", "")

        # Generate from last component
        last = parts[-1].replace("DNA", "")

        # Convert camelCase to spaces
        spaced = re.sub(r'([A-Z])', r' \1', last).strip()

        return f"{spaced} characteristics and attributes"

    def _generate_tags(self, path: str) -> List[str]:
        """Generate searchable tags from path."""
        parts = path.split(".")
        tags = []

        # Add namespace as tag
        if parts:
            namespace = parts[0].lower().replace("dna", "")
            tags.append(namespace)

        # Add each level as tag
        for part in parts[1:]:
            tag = part.lower().replace("dna", "").replace("_", "-")
            if tag and tag not in tags:
                tags.append(tag)

        return tags

    def _generate_validation_rules(self, path: str) -> Dict[str, Any]:
        """Generate validation rules based on path."""
        # Default to categorical for most traits
        return {
            "value_type": "categorical",
            "allowed_values": [],  # Will be populated by actual data
        }

    def _compute_namespace_counts(self) -> Dict[str, int]:
        """Compute container counts per namespace."""
        counts = defaultdict(int)
        for container in self.containers:
            namespace = container.get("namespace")
            if namespace:
                counts[namespace] += 1
        return dict(counts)

    def save_registry(self, registry: Dict[str, Any], output_path: Path) -> None:
        """Save registry to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(registry, f, indent=2)

        print(f"✅ Registry saved to {output_path}")
        print(f"   Total containers: {registry['metadata']['total_containers']}")
        print(f"   Namespace breakdown:")
        for ns, count in sorted(registry['metadata']['namespace_counts'].items()):
            print(f"     {ns}: {count}")


def main():
    """CLI entry point for DNA generator."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate DNA container registry")
    parser.add_argument(
        "--namespaces",
        type=Path,
        required=True,
        help="Path to namespaces.yaml"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for dna_registry.json"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=1000,
        help="Target container count (approximate)"
    )
    parser.add_argument(
        "--include",
        nargs="+",
        help="Namespaces to include (default: all)"
    )

    args = parser.parse_args()

    generator = DNAGenerator(
        namespaces_path=args.namespaces,
        output_dir=args.output.parent
    )

    print(f"Generating seed registry with ~{args.target} containers...")
    registry = generator.generate_seed_registry(
        target_count=args.target,
        include_namespaces=args.include
    )

    generator.save_registry(registry, args.output)

    print(f"\n✅ Generation complete!")
    print(f"   Run linter: python3 core/validation/registry_linter.py {args.output}")


if __name__ == "__main__":
    main()
