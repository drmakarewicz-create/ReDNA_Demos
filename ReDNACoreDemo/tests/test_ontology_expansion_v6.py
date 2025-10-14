import json
import time
from pathlib import Path

import pytest

from ReDNACoreDemo.core.ontology.expansion_engine_v6 import (
    ExpansionEngineV6,
    run_expansion_v6,
)


@pytest.fixture()
def base_registry(tmp_path: Path) -> Path:
    """Create a minimal v5 registry for tests."""
    containers = [
        {
            "id": "base_psy_1",
            "namespace": "PsyDNA",
            "path": "PsyDNA.personality.empathy",
            "description": "Empathy insight container for testing.",
        },
        {
            "id": "base_skill_1",
            "namespace": "SkillDNA",
            "path": "SkillDNA.communication.storytelling",
            "description": "Storytelling skill container template.",
        },
        {
            "id": "base_belief_1",
            "namespace": "BeliefDNA",
            "path": "BeliefDNA.values.integrity",
            "description": "Integrity belief container template.",
        },
        {
            "id": "base_chat_1",
            "namespace": "ChatDNA",
            "path": "ChatDNA.style.supportive",
            "description": "Supportive chat style definition.",
        },
    ]
    registry = {
        "version": "v5",
        "containers": containers,
        "generated_at": "2025-10-10T00:00:00Z",
    }
    path = tmp_path / "base_registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def build_engine(tmp_path: Path, base_registry: Path) -> ExpansionEngineV6:
    """Helper to create an engine pointed at a temp output directory."""
    output_dir = tmp_path / "registry_v6"
    return ExpansionEngineV6(base_registry_path=base_registry, output_dir=output_dir, num_workers=1)


def test_loads_base_registry(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    assert len(engine.existing_containers) == 4
    assert engine.base_registry_path == base_registry


def test_compute_semantic_hash_stable(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "id": "c1",
        "namespace": "PsyDNA",
        "path": "PsyDNA.personality.curiosity",
        "description": "Curiosity trait container.",
    }
    first = engine.compute_semantic_hash(container)
    second = engine.compute_semantic_hash(container)
    assert first == second
    assert len(first) == 16


def test_compute_semantic_hash_changes_with_path(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container_a = {
        "id": "c1",
        "namespace": "PsyDNA",
        "path": "PsyDNA.personality.curiosity",
        "description": "Curiosity trait container.",
    }
    container_b = {
        **container_a,
        "path": "PsyDNA.personality.tenacity",
    }
    assert engine.compute_semantic_hash(container_a) != engine.compute_semantic_hash(container_b)


def test_persona_weights_namespace_bias(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "id": "c1",
        "namespace": "CareerDNA",
        "path": "CareerDNA.progression.generated",
        "description": "Career progression template.",
    }
    weights = engine.compute_persona_weights(container)
    assert weights["career"] > weights["relationship"]
    assert weights["career"] <= 1.0


def test_persona_weights_trait_keyword_boost(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "id": "c2",
        "namespace": "SkillDNA",
        "path": "SkillDNA.communication.generated",
        "description": "Communication leadership excellence.",
    }
    weights = engine.compute_persona_weights(container)
    assert weights["career"] > 0.9  # leadership keyword boosts


def test_trait_relevance_core_namespace_bonus(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "namespace": "PsyDNA",
        "path": "PsyDNA.personality.focus",
        "description": "Personality insight with behavioral focus.",
    }
    relevance = engine.compute_trait_relevance(container)
    assert relevance >= 0.7


def test_trait_relevance_generic_penalty(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "namespace": "SkillDNA",
        "path": "SkillDNA.general.generic",
        "description": "General basic standard template.",
    }
    relevance = engine.compute_trait_relevance(container)
    assert relevance <= 0.5


def test_curiosity_boost_keywords(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "description": "An unexpected and surprising discovery.",
    }
    boost = engine.compute_curiosity_boost(container)
    assert boost >= 0.6


def test_curiosity_boost_gap_keywords(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "description": "Highlights a conflict and tension gap.",
    }
    boost = engine.compute_curiosity_boost(container)
    assert boost >= 0.5


def test_learning_value_namespace_bonus(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "namespace": "SkillDNA",
        "description": "Skill growth plan.",
    }
    value = engine.compute_learning_value(container)
    assert value >= 0.7


def test_learning_value_keyword_bonus(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "namespace": "BeliefDNA",
        "description": "Helps users adapt and evolve belief structures.",
    }
    value = engine.compute_learning_value(container)
    assert value >= 0.7


def test_tag_container_populates_metadata(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "id": "meta_1",
        "namespace": "PsyDNA",
        "path": "PsyDNA.personality.focus",
        "description": "Personality focus container.",
    }
    tagged = engine.tag_container_with_persona_context(container.copy())
    assert "persona_weights" in tagged
    assert "trait_relevance" in tagged
    assert "curiosity_boost" in tagged
    assert "learning_value" in tagged
    assert "tagged_at" in tagged


def test_generate_expanded_containers_meets_target(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    generated = engine.generate_expanded_containers(target_count=12)
    assert len(generated) == 8  # 12 - 4 base
    assert engine.stats["generated"] == 8
    assert engine.stats["duplicates"] == 0
    assert engine.stats["collisions"] == 0


def test_generated_containers_unique_paths(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    generated = engine.generate_expanded_containers(target_count=20)
    paths = {c["path"] for c in generated}
    assert len(paths) == len(generated)


def test_duplicate_detection_updates_stats(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    container = {
        "id": "dup_test",
        "namespace": "SkillDNA",
        "path": "SkillDNA.technical.generated.0",
        "description": "Technical skill generated container.",
    }
    # First time should not be duplicate
    assert engine.is_duplicate(container) is False
    engine.semantic_hashes.add(engine.compute_semantic_hash(container))
    engine.existing_paths.add(container["path"])
    # Second time should trigger duplicate + collision counters
    assert engine.is_duplicate(container) is True
    assert engine.stats["duplicates"] >= 1 or engine.stats["collisions"] >= 1


def test_build_persona_index_counts(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    engine.generate_expanded_containers(target_count=16)
    engine.build_persona_index()
    assert len(engine.persona_index) > 0
    assert sum(len(v) for v in engine.persona_index.values()) >= len(engine.generated_containers)


def test_get_persona_context_limit(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    engine.generate_expanded_containers(target_count=30)
    engine.build_persona_index()
    top_three = engine.get_persona_context("career", limit=3)
    assert len(top_three) <= 3


def test_save_registry_outputs_files(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    engine.generate_expanded_containers(target_count=15)
    engine.build_persona_index()
    engine.save_registry_v6()
    assert (engine.output_dir / "dna_registry_v6.json").exists()
    assert (engine.output_dir / "persona_context_index.json").exists()


def test_write_validation_report_contents(base_registry: Path, tmp_path: Path) -> None:
    engine = build_engine(tmp_path, base_registry)
    engine.generate_expanded_containers(target_count=18)
    engine.build_persona_index()
    engine.stats["peak_memory_mb"] = 12.5
    engine.stats["duration_sec"] = 0.5
    report_path = engine.write_validation_report()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["total_containers"] == 18
    assert report["duplicates"] == 0
    assert report["collisions"] == 0
    assert report["memory_ok"] is True
    assert report["duration_ok"] is True


def test_run_expansion_v6_respects_target_and_performance(tmp_path: Path) -> None:
    start = time.perf_counter()
    empty_base = tmp_path / "empty_base.json"
    empty_base.write_text(json.dumps({"version": "v5", "containers": []}), encoding="utf-8")
    engine = run_expansion_v6(
        target_count=250,
        base_registry_path=empty_base,
        output_dir=tmp_path / "run_output",
        num_workers=1,
    )
    duration = time.perf_counter() - start
    assert engine.stats["duplicates"] == 0
    assert engine.stats["collisions"] == 0
    assert engine.stats["peak_memory_mb"] < 400
    assert engine.stats["duration_sec"] <= 10
    assert duration <= 10
    validation_path = Path(engine.output_dir) / "validation_report_v6.json"
    assert validation_path.exists()
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["total_containers"] >= 250
