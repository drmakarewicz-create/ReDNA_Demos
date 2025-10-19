#!/usr/bin/env python3
"""
Expanded bulk generation script for Ontology V5.
Generates containers with skill levels, contexts, and modalities for 8,000+ containers.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core.ontology.expansion_engine import create_expansion_engine


# Skill levels for multiplication
SKILL_LEVELS = ["Beginner", "Intermediate", "Advanced", "Expert", "Master"]

# Contexts for multiplication
CONTEXTS = ["Personal", "Professional", "Academic", "Creative"]

# Modalities for multiplication
MODALITIES = ["Solo", "Collaborative", "Remote", "InPerson"]


def load_patterns(pattern_file="ReDNACoreDemo/core/ontology/container_patterns_v5_expanded.json"):
    """Load pattern definitions."""
    with open(pattern_file) as f:
        return json.load(f)


def generate_skill_variations(engine, patterns):
    """Generate SkillDNA containers with level variations."""
    print("\n=== Generating SkillDNA containers (with level variations) ===")
    total = 0

    for category, items in patterns.get("skill_dna", {}).items():
        print(f"\nCategory: {category}")

        for item in items:
            # Generate base container
            container = engine.generate_container(
                namespace="SkillDNA",
                category=category.replace("_", " ").title(),
                trait_name=item,
                description=f"Skill in {item}",
                parent_path="SkillDNA",
                tags=["skill", category, item.lower()]
            )

            if engine.add_container(container):
                total += 1

            # Generate level variations for certain categories
            if category in ["programming_languages", "web_frameworks", "databases", "ml_frameworks"]:
                for level in SKILL_LEVELS:
                    container = engine.generate_container(
                        namespace="SkillDNA",
                        category=category.replace("_", " ").title(),
                        trait_name=f"{item}_{level}",
                        description=f"{level} level skill in {item}",
                        parent_path=f"SkillDNA.{category.replace('_', ' ').title()}",
                        tags=["skill", category, item.lower(), level.lower()]
                    )

                    if engine.add_container(container):
                        total += 1

        print(f"  Generated {total} containers so far")

    print(f"\n✓ SkillDNA total: {total} containers")
    return total


def generate_behavior_variations(engine, patterns):
    """Generate BehDNA containers with context variations."""
    print("\n=== Generating BehDNA containers (with context variations) ===")
    total = 0

    for category, items in patterns.get("behavior_dna", {}).items():
        print(f"\nCategory: {category}")

        for item in items:
            # Generate base container
            container = engine.generate_container(
                namespace="BehDNA",
                category=category.replace("_", " ").title(),
                trait_name=item,
                description=f"Behavioral pattern: {item}",
                parent_path="BehDNA",
                tags=["behavior", category, item.lower()]
            )

            if engine.add_container(container):
                total += 1

            # Generate context variations for key categories
            if category in ["communication", "work_habits", "collaboration"]:
                for context in CONTEXTS:
                    container = engine.generate_container(
                        namespace="BehDNA",
                        category=category.replace("_", " ").title(),
                        trait_name=f"{item}_{context}",
                        description=f"{item} in {context} context",
                        parent_path=f"BehDNA.{category.replace('_', ' ').title()}",
                        tags=["behavior", category, item.lower(), context.lower()]
                    )

                    if engine.add_container(container):
                        total += 1

        print(f"  Generated {total} containers so far")

    print(f"\n✓ BehDNA total: {total} containers")
    return total


def generate_cognitive_variations(engine, patterns):
    """Generate CogDNA containers with modality variations."""
    print("\n=== Generating CogDNA containers (with modality variations) ===")
    total = 0

    for category, items in patterns.get("cognitive_dna", {}).items():
        print(f"\nCategory: {category}")

        for item in items:
            # Generate base container
            container = engine.generate_container(
                namespace="CogDNA",
                category=category.replace("_", " ").title(),
                trait_name=item,
                description=f"Cognitive trait: {item}",
                parent_path="CogDNA",
                tags=["cognitive", category, item.lower()]
            )

            if engine.add_container(container):
                total += 1

            # Generate modality variations for problem solving
            if category in ["problem_solving", "decision_making"]:
                for modality in MODALITIES[:2]:  # Just Solo and Collaborative
                    container = engine.generate_container(
                        namespace="CogDNA",
                        category=category.replace("_", " ").title(),
                        trait_name=f"{item}_{modality}",
                        description=f"{item} in {modality} mode",
                        parent_path=f"CogDNA.{category.replace('_', ' ').title()}",
                        tags=["cognitive", category, item.lower(), modality.lower()]
                    )

                    if engine.add_container(container):
                        total += 1

        print(f"  Generated {total} containers so far")

    print(f"\n✓ CogDNA total: {total} containers")
    return total


def generate_standard_containers(engine, patterns, namespace, namespace_key):
    """Generate containers without variations."""
    print(f"\n=== Generating {namespace} containers ===")
    total = 0

    for category, items in patterns.get(namespace_key, {}).items():
        print(f"\nCategory: {category}")

        for item in items:
            container = engine.generate_container(
                namespace=namespace,
                category=category.replace("_", " ").title(),
                trait_name=item,
                description=f"{namespace} trait: {item}",
                parent_path=namespace,
                tags=[namespace.lower(), category, item.lower()]
            )

            if engine.add_container(container):
                total += 1

        print(f"  Generated {total} containers so far")

    print(f"\n✓ {namespace} total: {total} containers")
    return total


def main():
    """Main generation function."""
    print("=" * 70)
    print(" EXPANDED ONTOLOGY V5 GENERATION")
    print(" Target: 8,000+ containers with variations")
    print("=" * 70)

    # Create expansion engine
    print("\nInitializing expansion engine...")
    engine = create_expansion_engine()
    print(f"✓ Engine initialized with {len(engine.existing_containers)} base containers")

    # Load patterns
    print("\nLoading expanded patterns...")
    patterns = load_patterns()
    print("✓ Patterns loaded")

    # Generate containers with variations
    grand_total = 0

    # SkillDNA with level variations (491 * ~3 avg = ~1,473)
    grand_total += generate_skill_variations(engine, patterns)

    # BehDNA with context variations (214 * ~2 avg = ~428)
    grand_total += generate_behavior_variations(engine, patterns)

    # CogDNA with modality variations (139 * ~1.5 avg = ~209)
    grand_total += generate_cognitive_variations(engine, patterns)

    # EmDNA (143, no variations)
    grand_total += generate_standard_containers(engine, patterns, "EmDNA", "emotional_dna")

    # ProfDNA (185, no variations)
    grand_total += generate_standard_containers(engine, patterns, "ProfDNA", "professional_dna")

    # PrefDNA (120, no variations)
    grand_total += generate_standard_containers(engine, patterns, "PrefDNA", "preference_dna")

    # SocDNA (87, no variations)
    grand_total += generate_standard_containers(engine, patterns, "SocDNA", "social_dna")

    # MetaDNA (76, no variations)
    grand_total += generate_standard_containers(engine, patterns, "MetaDNA", "meta_dna")

    # Summary
    print("\n" + "=" * 70)
    print(" GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nNew containers generated: {grand_total}")
    print(f"Total containers: {len(engine.existing_containers) + len(engine.generated_containers)}")
    print(f"Total generated (new): {len(engine.generated_containers)}")

    # Validate
    print("\nValidating...")
    validation = engine.validate()

    if validation['valid']:
        print("✓ Validation passed!")
        print(f"  - Unique IDs: {validation['unique_ids']}")
        print(f"  - Unique paths: {validation['unique_paths']}")
        print(f"  - Unique hashes: {validation['unique_semantic_hashes']}")
    else:
        print("✗ Validation failed!")
        for error in validation['errors'][:10]:
            print(f"  - {error}")
        return 1

    # Save
    print("\nSaving registry...")
    registry_path = engine.save_registry_v5()
    print(f"✓ Saved to {registry_path}")

    # Namespace distribution
    print("\nNamespace Distribution:")
    all_containers = list(engine.existing_containers.values()) + engine.generated_containers
    by_ns = {}
    for container in all_containers:
        ns = container['namespace']
        by_ns[ns] = by_ns.get(ns, 0) + 1

    for ns, count in sorted(by_ns.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(all_containers)) * 100
        print(f"  {ns:15} {count:5} ({pct:5.1f}%)")

    print("\n✅ SUCCESS! Expanded ontology generated.")
    print(f"   Run correlation generation next to create edges.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
