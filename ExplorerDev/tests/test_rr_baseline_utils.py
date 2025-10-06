"""Unit tests for RR baseline utilities (recalculation, file I/O, validation)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Import RR baseline utilities
import sys
_here = Path(__file__).parent
_explorerdev = _here.parent
sys.path.insert(0, str(_explorerdev.parent))

from ExplorerDev import rr_baseline_utils
from ExplorerDev.write_utils import WriteProtectContext


@pytest.fixture
def temp_repo_root():
    """Create a temporary repo root for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create necessary directory structure
        config_dir = repo_root / "ReDNACoreDemo" / "data" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        dev_config_dir = repo_root / "data" / "dev_config"
        dev_config_dir.mkdir(parents=True, exist_ok=True)

        dev_logs_dir = repo_root / "data" / "dev_logs"
        dev_logs_dir.mkdir(parents=True, exist_ok=True)

        yield repo_root


@pytest.fixture
def sample_canonical_baselines(temp_repo_root):
    """Create sample canonical baselines YAML file."""
    canonical_path = rr_baseline_utils.canonical_baselines_path(temp_repo_root)

    content = """
defaults:
  mean: 450
  std: 100
  sample_size: 50

traits:
  PhotoPreferences.lighting_style:
    mean: 600
    std: 80
    sample_size: 75
  PhotoPreferences.color_palette:
    mean: 400
    std: 120
    sample_size: 60
"""

    canonical_path.write_text(content, encoding="utf-8")
    return canonical_path


class TestLoadCanonicalBaselines:
    """Test loading canonical baselines from Core."""

    def test_load_canonical_baselines_success(self, temp_repo_root, sample_canonical_baselines):
        """Test successfully loading canonical baselines."""
        result = rr_baseline_utils.load_canonical_baselines(temp_repo_root)

        assert "defaults" in result
        assert "traits" in result

        # Check normalized to 0-1 scale
        assert result["defaults"]["mean_ucn"] == 0.45
        assert result["defaults"]["std_ucn"] == 0.10
        assert result["defaults"]["sample_size"] == 50

        # Check trait normalization
        assert "PhotoPreferences.lighting_style" in result["traits"]
        trait = result["traits"]["PhotoPreferences.lighting_style"]
        assert trait["mean_ucn"] == 0.60
        assert trait["std_ucn"] == 0.08

    def test_load_canonical_baselines_missing_file(self, temp_repo_root):
        """Test loading when canonical file doesn't exist."""
        result = rr_baseline_utils.load_canonical_baselines(temp_repo_root)

        # Should return defaults
        assert result["defaults"]["mean_ucn"] == rr_baseline_utils.DEFAULT_BETA_MEAN
        assert result["defaults"]["std_ucn"] == rr_baseline_utils.DEFAULT_BETA_STD
        assert result["traits"] == {}


class TestLoadDemoConfig:
    """Test loading demo configuration."""

    def test_load_demo_config_default(self, temp_repo_root):
        """Test loading demo config when none exists."""
        config = rr_baseline_utils.load_demo_config(temp_repo_root)

        assert config["schemaVersion"] == 1
        assert config["global"]["use_demo_baselines"] is False
        assert config["defaults"]["mean_ucn"] == rr_baseline_utils.DEFAULT_BETA_MEAN

    def test_load_demo_config_from_file(self, temp_repo_root):
        """Test loading demo config from file."""
        demo_path = rr_baseline_utils.demo_baselines_path(temp_repo_root)

        config_data = {
            "schemaVersion": 1,
            "global": {"use_demo_baselines": True},
            "defaults": {
                "mean_ucn": 0.5,
                "std_ucn": 0.12,
                "sample_size": 100,
            },
            "containers": {
                "PhotoPreferences": {
                    "mean_ucn": 0.55,
                    "std_ucn": 0.15,
                    "sample_size": 80,
                }
            },
        }

        # Write YAML
        try:
            import yaml
            with demo_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f)

            loaded = rr_baseline_utils.load_demo_config(temp_repo_root)

            assert loaded["global"]["use_demo_baselines"] is True
            assert loaded["defaults"]["mean_ucn"] == 0.5
            assert "PhotoPreferences" in loaded["containers"]
        except ImportError:
            pytest.skip("PyYAML not available")


class TestValidation:
    """Test validation of demo baselines."""

    def test_validate_valid_config(self, temp_repo_root):
        """Test validation of a valid config."""
        config = {
            "schemaVersion": 1,
            "defaults": {
                "mean_ucn": 0.45,
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {},
        }

        issues = rr_baseline_utils.validate_demo_baselines(config)
        errors = [i for i in issues if i.level == "error"]

        assert len(errors) == 0

    def test_validate_mean_out_of_range(self, temp_repo_root):
        """Test validation catches mean_ucn out of range."""
        config = {
            "schemaVersion": 1,
            "defaults": {
                "mean_ucn": 1.5,  # Invalid: > 1.0
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {},
        }

        issues = rr_baseline_utils.validate_demo_baselines(config)
        errors = [i for i in issues if i.level == "error"]

        assert len(errors) > 0
        assert any("mean_ucn" in i.message.lower() for i in errors)

    def test_validate_std_out_of_range(self, temp_repo_root):
        """Test validation catches std_ucn out of range."""
        config = {
            "schemaVersion": 1,
            "defaults": {
                "mean_ucn": 0.5,
                "std_ucn": -0.1,  # Invalid: < 0
                "sample_size": 50,
            },
            "containers": {},
        }

        issues = rr_baseline_utils.validate_demo_baselines(config)
        errors = [i for i in issues if i.level == "error"]

        assert len(errors) > 0
        assert any("std_ucn" in i.message.lower() for i in errors)

    def test_validate_sample_size_invalid(self, temp_repo_root):
        """Test validation catches invalid sample_size."""
        config = {
            "schemaVersion": 1,
            "defaults": {
                "mean_ucn": 0.5,
                "std_ucn": 0.1,
                "sample_size": 0,  # Invalid: must be >= 1
            },
            "containers": {},
        }

        issues = rr_baseline_utils.validate_demo_baselines(config)
        errors = [i for i in issues if i.level == "error"]

        assert len(errors) > 0
        assert any("sample_size" in i.message.lower() for i in errors)


class TestResolveBaselines:
    """Test baseline resolution with cascade logic."""

    def test_resolve_baselines_defaults_only(self, temp_repo_root):
        """Test resolving when only defaults are specified."""
        config = {
            "defaults": {
                "mean_ucn": 0.45,
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {},
        }

        resolved = rr_baseline_utils.resolve_baselines(config)

        assert resolved["defaults"]["mean_ucn"] == 0.45
        assert resolved["defaults"]["source"] == "explicit"

    def test_resolve_baselines_container_inherits(self, temp_repo_root):
        """Test that containers inherit from defaults."""
        config = {
            "defaults": {
                "mean_ucn": 0.45,
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {
                "PhotoPreferences": {}  # Empty, should inherit
            },
        }

        resolved = rr_baseline_utils.resolve_baselines(config)

        container = resolved["containers"]["PhotoPreferences"]
        assert container["mean_ucn"] == 0.45
        assert container["source"] == "inherited"

    def test_resolve_baselines_container_overrides(self, temp_repo_root):
        """Test that containers can override defaults."""
        config = {
            "defaults": {
                "mean_ucn": 0.45,
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {
                "PhotoPreferences": {
                    "mean_ucn": 0.60,
                }
            },
        }

        resolved = rr_baseline_utils.resolve_baselines(config)

        container = resolved["containers"]["PhotoPreferences"]
        assert container["mean_ucn"] == 0.60
        assert container["std_ucn"] == 0.10  # Inherited
        assert container["source"] == "explicit"

    def test_resolve_baselines_trait_overrides(self, temp_repo_root):
        """Test that traits can override container values."""
        config = {
            "defaults": {
                "mean_ucn": 0.45,
                "std_ucn": 0.10,
                "sample_size": 50,
            },
            "containers": {
                "PhotoPreferences": {
                    "mean_ucn": 0.55,
                    "traits": {
                        "lighting_style": {
                            "mean_ucn": 0.70,
                        }
                    },
                }
            },
        }

        resolved = rr_baseline_utils.resolve_baselines(config)

        trait = resolved["containers"]["PhotoPreferences"]["traits"]["lighting_style"]
        assert trait["mean_ucn"] == 0.70
        assert trait["std_ucn"] == 0.10  # Inherited from defaults
        assert trait["source"] == "explicit"


class TestGetEffectiveBaseline:
    """Test getting effective baseline for a trait."""

    def test_get_effective_baseline_demo_mode(self, temp_repo_root):
        """Test getting effective baseline in demo mode."""
        config = {
            "defaults": {"mean_ucn": 0.45, "std_ucn": 0.10, "sample_size": 50},
            "containers": {
                "PhotoPreferences": {
                    "mean_ucn": 0.60,
                    "traits": {
                        "lighting_style": {"mean_ucn": 0.75}
                    },
                }
            },
        }

        result = rr_baseline_utils.get_effective_baseline(
            temp_repo_root,
            "PhotoPreferences",
            "lighting_style",
            config=config,
            use_demo=True,
        )

        assert result["mean_ucn"] == 0.75
        assert result["source"] == "demo_trait"

    def test_get_effective_baseline_canonical_mode(self, temp_repo_root, sample_canonical_baselines):
        """Test getting effective baseline in canonical mode."""
        canonical = rr_baseline_utils.load_canonical_baselines(temp_repo_root)

        result = rr_baseline_utils.get_effective_baseline(
            temp_repo_root,
            "PhotoPreferences",
            "lighting_style",
            canonical=canonical,
            use_demo=False,
        )

        assert result["mean_ucn"] == 0.60  # From canonical
        assert "canonical" in result["source"]


class TestSaveAndLog:
    """Test saving demo baselines and logging changes."""

    def test_save_demo_baselines(self, temp_repo_root):
        """Test saving demo baselines to file."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")

        config = {
            "schemaVersion": 1,
            "global": {"use_demo_baselines": True},
            "defaults": {"mean_ucn": 0.5, "std_ucn": 0.12, "sample_size": 100},
            "containers": {},
        }

        context = WriteProtectContext(write_protect=False)

        path = rr_baseline_utils.save_demo_baselines(
            temp_repo_root,
            config,
            context,
        )

        assert path.exists()

        # Verify it can be loaded back
        loaded = rr_baseline_utils.load_demo_config(temp_repo_root)
        assert loaded["defaults"]["mean_ucn"] == 0.5

    def test_log_event_creates_entry(self, temp_repo_root):
        """Test that log_event creates a changelog entry."""
        before = {"defaults": {"mean_ucn": 0.45}}
        after = {"defaults": {"mean_ucn": 0.50}}

        rr_baseline_utils.log_event(temp_repo_root, before, after)

        log_path = rr_baseline_utils.change_log_path(temp_repo_root)
        assert log_path.exists()

        # Verify log entry
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert "timestamp" in entry
            assert entry["before"]["defaults"]["mean_ucn"] == 0.45
            assert entry["after"]["defaults"]["mean_ucn"] == 0.50


class TestDisplayHelpers:
    """Test display helper functions."""

    def test_make_rows_for_display(self, temp_repo_root):
        """Test making rows for display."""
        config = {
            "defaults": {"mean_ucn": 0.45, "std_ucn": 0.10, "sample_size": 50},
            "containers": {
                "PhotoPreferences": {
                    "mean_ucn": 0.60,
                    "traits": {
                        "lighting_style": {"mean_ucn": 0.75}
                    },
                }
            },
        }

        rows = rr_baseline_utils.make_rows_for_display(config)

        assert len(rows) >= 3  # defaults + container + trait
        scopes = [row["scope"] for row in rows]
        assert "defaults" in scopes
        assert "PhotoPreferences (container)" in scopes
        assert "PhotoPreferences.lighting_style" in scopes

    def test_export_config_as_csv(self, temp_repo_root):
        """Test exporting config as CSV."""
        config = {
            "defaults": {"mean_ucn": 0.45, "std_ucn": 0.10, "sample_size": 50},
            "containers": {},
        }

        csv_text = rr_baseline_utils.export_config_as_csv(config)

        assert "scope,mean_ucn,std_ucn,sample_size,effective_source" in csv_text
        assert "defaults,0.45,0.1,50" in csv_text


class TestPreflightImport:
    """Test preflight validation for imports."""

    def test_preflight_import_valid(self, temp_repo_root):
        """Test preflight on valid config."""
        new_config = {
            "schemaVersion": 1,
            "defaults": {"mean_ucn": 0.5, "std_ucn": 0.12, "sample_size": 100},
            "containers": {},
        }

        result = rr_baseline_utils.preflight_import(temp_repo_root, new_config)

        assert result["error_count"] == 0
        assert "config" in result
        assert "changes" in result

    def test_preflight_import_with_errors(self, temp_repo_root):
        """Test preflight catches errors."""
        new_config = {
            "schemaVersion": 1,
            "defaults": {"mean_ucn": 1.5, "std_ucn": 0.12, "sample_size": 100},  # Invalid mean
            "containers": {},
        }

        result = rr_baseline_utils.preflight_import(temp_repo_root, new_config)

        assert result["error_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
