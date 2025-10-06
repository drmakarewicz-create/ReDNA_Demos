"""Test coverage for CReDNA ops (import/export, versioning, rollback paths)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Import CReDNA modules
import sys
_here = Path(__file__).parent
_explorerdev = _here.parent
sys.path.insert(0, str(_explorerdev.parent))

from ExplorerDev.credna import credna_ops, credna_store
from ExplorerDev.write_utils import WriteProtectContext


@pytest.fixture
def temp_repo_root():
    """Create a temporary repo root for CReDNA testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create necessary directory structure
        credna_dir = repo_root / "data" / "dev_config" / "credna"
        credna_dir.mkdir(parents=True, exist_ok=True)

        logs_dir = repo_root / "data" / "dev_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        yield repo_root


@pytest.fixture
def sample_coach_registry():
    """Sample coach registry for testing."""
    return {
        "schema_version": 1,
        "coaches": {
            "photo_coach": {
                "label": "Photo Coach",
                "name": "Photo Refinement Coach",
                "containers": [
                    {
                        "id": "PhotoPreferences",
                        "traits": [
                            {
                                "id": "lighting_style",
                                "label": "Lighting Style",
                                "weight": 0.8,
                                "core_trait": "PhotoPreferences.lighting_style",
                                "templates": {
                                    "curious": "What lighting style do you prefer?",
                                    "neutral": "Tell me about lighting preferences",
                                },
                                "provenance": {
                                    "created": "2025-09-01",
                                    "version": "1.0",
                                },
                            }
                        ],
                    }
                ],
            },
            "head_coach": {
                "label": "Head Coach",
                "name": "Head Coach",
                "containers": [],
            },
        },
    }


@pytest.fixture
def write_context():
    """Write context for testing."""
    return WriteProtectContext(write_protect=False)


@pytest.fixture
def write_protect_context():
    """Write-protect context for dry-run testing."""
    return WriteProtectContext(write_protect=True)


class TestCoachListing:
    """Test coach listing and retrieval."""

    def test_list_coaches_from_registry(self, sample_coach_registry):
        """Test listing all coaches from registry."""
        coaches = credna_ops.list_coaches(sample_coach_registry)

        assert "photo_coach" in coaches
        assert "head_coach" in coaches
        assert len(coaches) == 2

    def test_get_coach_success(self, sample_coach_registry):
        """Test retrieving a specific coach."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        assert coach is not None
        assert coach["label"] == "Photo Coach"
        assert len(coach["containers"]) == 1

    def test_get_coach_not_found(self, sample_coach_registry):
        """Test retrieving a non-existent coach."""
        coach = credna_ops.get_coach(sample_coach_registry, "nonexistent_coach")

        assert coach is None


class TestTraitIteration:
    """Test trait iteration within coaches."""

    def test_coach_trait_iterator(self, sample_coach_registry):
        """Test iterating over traits in a coach."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        traits = list(credna_ops.coach_trait_iterator(coach))

        assert len(traits) == 1
        trait_id, trait_data = traits[0]
        assert trait_id == "PhotoPreferences.lighting_style"
        assert trait_data["label"] == "Lighting Style"

    def test_coach_trait_iterator_empty(self, sample_coach_registry):
        """Test iterating over a coach with no traits."""
        coach = credna_ops.get_coach(sample_coach_registry, "head_coach")

        traits = list(credna_ops.coach_trait_iterator(coach))

        assert len(traits) == 0


class TestPersonaResolution:
    """Test resolving persona IDs to coach IDs."""

    def test_resolve_coach_for_persona_exact_match(self, sample_coach_registry):
        """Test resolving with exact persona ID match."""
        coach_id = credna_ops.resolve_coach_for_persona(
            sample_coach_registry,
            "photo_coach",
        )

        assert coach_id == "photo_coach"

    def test_resolve_coach_for_persona_display_name(self, sample_coach_registry):
        """Test resolving with display name match."""
        coach_id = credna_ops.resolve_coach_for_persona(
            sample_coach_registry,
            "unknown_id",
            display_name="Photo Refinement Coach",
        )

        assert coach_id == "photo_coach"

    def test_resolve_coach_for_persona_not_found(self, sample_coach_registry):
        """Test resolving when no match found."""
        coach_id = credna_ops.resolve_coach_for_persona(
            sample_coach_registry,
            "nonexistent_coach",
        )

        assert coach_id is None


class TestTemplateRetrieval:
    """Test template finding for traits."""

    def test_find_trait_template_success(self, sample_coach_registry):
        """Test finding a template for a trait."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        template = credna_ops.find_trait_template(
            coach,
            "PhotoPreferences",
            "lighting_style",
            "curious",
        )

        assert template is not None
        assert template["template"] == "What lighting style do you prefer?"
        assert template["tone_used"] == "curious"

    def test_find_trait_template_fallback_to_neutral(self, sample_coach_registry):
        """Test fallback to neutral template when tone not found."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        template = credna_ops.find_trait_template(
            coach,
            "PhotoPreferences",
            "lighting_style",
            "encouraging",  # Not available, should fallback
        )

        assert template is not None
        assert template["tone_used"] == "neutral"

    def test_find_trait_template_not_found(self, sample_coach_registry):
        """Test when trait doesn't exist."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        template = credna_ops.find_trait_template(
            coach,
            "NonexistentContainer",
            "nonexistent_trait",
            "curious",
        )

        assert template is None


class TestCoverageComputation:
    """Test coverage computation for coaches."""

    def test_build_coach_snapshot_without_user(self, sample_coach_registry):
        """Test building coach snapshot without user context."""
        result = credna_ops.build_coach_snapshot(
            sample_coach_registry,
            "photo_coach",
        )

        assert result["ok"] is True
        snapshot = result["snapshot"]
        assert snapshot["coach_id"] == "photo_coach"
        assert "coverage" in snapshot
        assert "all_curiosity" in snapshot

    def test_build_coach_snapshot_coach_not_found(self, sample_coach_registry):
        """Test building snapshot for non-existent coach."""
        result = credna_ops.build_coach_snapshot(
            sample_coach_registry,
            "nonexistent_coach",
        )

        assert result["ok"] is False
        assert "error" in result


class TestCuriosityComputation:
    """Test curiosity computation for traits."""

    def test_compute_coach_curiosity_with_default(self):
        """Test curiosity computation using default value."""
        trait = {
            "curiosity": {"default": 0.5},
            "weight": 1.0,
        }

        curiosity, core_curiosity = credna_ops.compute_coach_curiosity(
            trait,
            weight=1.0,
            curiosity_lookup={},
            core_trait_key=None,
        )

        assert curiosity == 0.5
        assert core_curiosity is None

    def test_compute_coach_curiosity_with_core_lookup(self):
        """Test curiosity computation with core lookup."""
        trait = {
            "curiosity": {"default": 0.3},
            "weight": 0.8,
        }

        curiosity_lookup = {
            "photopreferenceslightingstyle": {
                "curiosity": 0.9,
                "ucn": 0.2,
            }
        }

        curiosity, core_curiosity = credna_ops.compute_coach_curiosity(
            trait,
            weight=0.8,
            curiosity_lookup=curiosity_lookup,
            core_trait_key="PhotoPreferences.lighting_style",
        )

        # Should blend: max(0.3, 0.9 * 0.8) = max(0.3, 0.72) = 0.72
        assert curiosity == pytest.approx(0.72)
        assert core_curiosity == 0.9


class TestCReDNAStore:
    """Test CReDNA store operations."""

    def test_load_registry_default(self, temp_repo_root, write_context, monkeypatch):
        """Test loading registry when none exists."""
        # Monkey patch the repo root
        monkeypatch.setattr(credna_store, "REPO_ROOT", temp_repo_root)

        registry = credna_store.load_registry(write_context)

        assert "schema_version" in registry
        assert "coaches" in registry

    def test_save_and_load_registry(self, temp_repo_root, write_context, sample_coach_registry, monkeypatch):
        """Test saving and loading a registry."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")

        monkeypatch.setattr(credna_store, "REPO_ROOT", temp_repo_root)

        # Save registry
        path = credna_store.save_registry(sample_coach_registry, write_context)

        assert path.exists()

        # Load it back
        loaded = credna_store.load_registry(write_context)

        assert loaded["schema_version"] == sample_coach_registry["schema_version"]
        assert "photo_coach" in loaded["coaches"]


class TestVersioning:
    """Test versioning and rollback functionality."""

    def test_provenance_tracking(self, sample_coach_registry):
        """Test that provenance is tracked in traits."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        traits = list(credna_ops.coach_trait_iterator(coach))
        _, trait_data = traits[0]

        assert "provenance" in trait_data
        assert trait_data["provenance"]["version"] == "1.0"

    def test_backup_on_save(self, temp_repo_root, write_context, sample_coach_registry, monkeypatch):
        """Test that backup is created on save."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")

        monkeypatch.setattr(credna_store, "REPO_ROOT", temp_repo_root)

        # Save once
        path1 = credna_store.save_registry(sample_coach_registry, write_context)

        # Modify and save again
        modified_registry = {**sample_coach_registry}
        modified_registry["coaches"]["new_coach"] = {"label": "New Coach", "containers": []}

        path2 = credna_store.save_registry(modified_registry, write_context)

        # Check backup exists
        backup_path = path2.with_suffix(path2.suffix + ".bak")
        assert backup_path.exists()


class TestGapDetection:
    """Test gap detection in coach configuration."""

    def test_gaps_missing_template(self):
        """Test gap detection for missing templates."""
        coach = {
            "containers": [
                {
                    "id": "TestContainer",
                    "traits": [
                        {
                            "id": "test_trait",
                            "label": "Test Trait",
                            "core_trait": "TestContainer.test_trait",
                            # No templates
                        }
                    ],
                }
            ]
        }

        result = credna_ops.build_coach_snapshot(
            {"coaches": {"test_coach": coach}},
            "test_coach",
        )

        snapshot = result["snapshot"]
        assert len(snapshot["gaps"]) > 0
        assert any("missing template" in gap["reasons"][0] for gap in snapshot["gaps"])

    def test_gaps_missing_core_mapping(self):
        """Test gap detection for missing core mapping."""
        coach = {
            "containers": [
                {
                    "id": "TestContainer",
                    "traits": [
                        {
                            "id": "test_trait",
                            "label": "Test Trait",
                            "templates": {"neutral": "Test template"},
                            # No core_trait
                        }
                    ],
                }
            ]
        }

        result = credna_ops.build_coach_snapshot(
            {"coaches": {"test_coach": coach}},
            "test_coach",
        )

        snapshot = result["snapshot"]
        assert len(snapshot["gaps"]) > 0
        assert any("missing core mapping" in gap["reasons"][0] for gap in snapshot["gaps"])


class TestWriteProtection:
    """Test write protection mode."""

    def test_write_protect_prevents_save(self, temp_repo_root, write_protect_context, sample_coach_registry, monkeypatch):
        """Test that write_protect prevents registry save."""
        monkeypatch.setattr(credna_store, "REPO_ROOT", temp_repo_root)

        with pytest.raises(PermissionError, match="write-protected"):
            credna_store.save_registry(sample_coach_registry, write_protect_context)


class TestImportExport:
    """Test import/export functionality."""

    def test_export_coach_as_json(self, sample_coach_registry):
        """Test exporting a coach as JSON."""
        coach = credna_ops.get_coach(sample_coach_registry, "photo_coach")

        json_str = json.dumps(coach, indent=2)
        loaded = json.loads(json_str)

        assert loaded["label"] == "Photo Coach"
        assert len(loaded["containers"]) == 1

    def test_import_coach_from_json(self, sample_coach_registry):
        """Test importing a coach from JSON."""
        new_coach = {
            "label": "Imported Coach",
            "name": "Imported Test Coach",
            "containers": [
                {
                    "id": "ImportedContainer",
                    "traits": [
                        {
                            "id": "imported_trait",
                            "label": "Imported Trait",
                            "templates": {"neutral": "Imported template"},
                        }
                    ],
                }
            ],
        }

        # Add to registry
        registry = {**sample_coach_registry}
        registry["coaches"]["imported_coach"] = new_coach

        # Verify it's accessible
        coach = credna_ops.get_coach(registry, "imported_coach")
        assert coach is not None
        assert coach["label"] == "Imported Coach"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
