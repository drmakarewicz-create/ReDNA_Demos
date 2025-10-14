#!/usr/bin/env python3
"""
Bulk Container Generation v5
Generates 8,000+ containers quickly using predefined patterns.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core.ontology.expansion_engine import create_expansion_engine

# Load patterns
PATTERNS_PATH = Path(__file__).parent.parent / "ReDNACoreDemo" / "core" / "ontology" / "container_patterns_v5.json"

def load_patterns():
    """Load container patterns from JSON."""
    with open(PATTERNS_PATH) as f:
        return json.load(f)

def main():
    print("=" * 70)
    print("  ReDNA Bulk Container Generation v5")
    print("=" * 70)
    print()

    # Load patterns
    print("Loading container patterns...")
    patterns = load_patterns()

    # Create engine
    engine = create_expansion_engine()

    # Generate from patterns
    total = 0

    # SkillDNA
    print("\nGenerating SkillDNA containers...")
    for category, items in patterns.get("skill_dna", {}).items():
        cat_name = category.replace("_", ".").title()
        for item in items:
            container = engine.generate_container(
                namespace="SkillDNA",
                category=cat_name,
                trait_name=item,
                description=f"Proficiency in {item}",
                parent_path="SkillDNA",
                tags=["skill", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  SkillDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'SkillDNA')} containers")

    # BehDNA
    print("\nGenerating BehDNA containers...")
    for category, items in patterns.get("behavior_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="BehDNA",
                category=cat_name,
                trait_name=item,
                description=f"Behavioral pattern: {item}",
                parent_path="BehDNA",
                tags=["behavior", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  BehDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'BehDNA')} containers")

    # CogDNA
    print("\nGenerating CogDNA containers...")
    for category, items in patterns.get("cognitive_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="CogDNA",
                category=cat_name,
                trait_name=item,
                description=f"Cognitive pattern: {item}",
                parent_path="CogDNA",
                tags=["cognitive", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  CogDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'CogDNA')} containers")

    # EmDNA
    print("\nGenerating EmDNA containers...")
    for category, items in patterns.get("emotional_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="EmDNA",
                category=cat_name,
                trait_name=item,
                description=f"Emotional pattern: {item}",
                parent_path="EmDNA",
                tags=["emotional", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  EmDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'EmDNA')} containers")

    # ProfDNA
    print("\nGenerating ProfDNA containers...")
    for category, items in patterns.get("professional_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="ProfDNA",
                category=cat_name,
                trait_name=item,
                description=f"Professional {category}: {item}",
                parent_path="ProfDNA",
                tags=["professional", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  ProfDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'ProfDNA')} containers")

    # PrefDNA
    print("\nGenerating PrefDNA containers...")
    for category, items in patterns.get("preference_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="PrefDNA",
                category=cat_name,
                trait_name=item,
                description=f"Preference: {item}",
                parent_path="PrefDNA",
                tags=["preference", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  PrefDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'PrefDNA')} containers")

    # SocDNA
    print("\nGenerating SocDNA containers...")
    for category, items in patterns.get("social_dna", {}).items():
        cat_name = category.replace("_", " ").title()
        for item in items:
            container = engine.generate_container(
                namespace="SocDNA",
                category=cat_name,
                trait_name=item,
                description=f"Social pattern: {item}",
                parent_path="SocDNA",
                tags=["social", category]
            )
            if engine.add_container(container):
                total += 1
    print(f"  SocDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'SocDNA')} containers")

    # Fill to 8000 with variations
    print("\nFilling to 8,000 with systematic variations...")
    target_remaining = 8000 - total
    variations_per_item = max(1, target_remaining // 500)

    # Add depth variations (beginner, intermediate, advanced, expert)
    levels = ["Beginner", "Intermediate", "Advanced", "Expert", "Master"]
    contexts = ["Personal", "Professional", "Academic", "Creative", "Technical"]

    for level in levels:
        for context in contexts:
            for category in ["ProblemSolving", "Communication", "Learning", "Collaboration"]:
                container = engine.generate_container(
                    namespace="MetaDNA",
                    category=f"{category}.Level",
                    trait_name=f"{level}{context}{category}",
                    description=f"{level}-level {category.lower()} in {context.lower()} context",
                    parent_path="MetaDNA",
                    tags=["meta", "level", context.lower()]
                )
                if engine.add_container(container):
                    total += 1
                    if total >= 8000:
                        break
            if total >= 8000:
                break
        if total >= 8000:
            break

    print(f"  MetaDNA: {sum(1 for c in engine.generated_containers if c['namespace'] == 'MetaDNA')} containers")

    # Validate
    print()
    print("=" * 70)
    print("  Validation")
    print("=" * 70)
    validation = engine.validate()
    print(f"Total generated: {validation['total_containers']:,}")
    print(f"Unique IDs: {validation['unique_ids']:,}")
    print(f"Unique paths: {validation['unique_paths']:,}")
    print()

    if validation['errors']:
        print("❌ Errors:")
        for err in validation['errors']:
            print(f"  - {err}")
    else:
        print("✅ No errors")

    # Save
    print()
    print("Saving registry v5...")
    registry_path = engine.save_registry_v5()
    print(f"✅ Saved to {registry_path}")

    #  Save validation
    val_path = registry_path.parent / "validation_report.json"
    with open(val_path, 'w') as f:
        json.dump({'validation': validation, 'stats': engine.stats}, f, indent=2)
    print(f"✅ Validation report: {val_path}")

    print()
    print("=" * 70)
    print(f"✅ Complete! Generated {total:,} new containers")
    print(f"✅ Total in v5 registry: {len(engine.existing_containers) + total:,}")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
