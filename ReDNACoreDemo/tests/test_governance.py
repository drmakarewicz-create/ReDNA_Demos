from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
import json

from ReDNACoreDemo.core import governance


class GovernanceTests(unittest.TestCase):
    def test_sensitive_requires_consent(self) -> None:
        resolved = {
            "trait": {"metadata": {"sensitive": True}}
        }
        with self.assertRaises(PermissionError):
            governance.enforce_sensitive_writes(resolved)
        resolved["trait"]["metadata"]["consent_granted"] = True
        governance.enforce_sensitive_writes(resolved)  # should not raise

    def test_dormancy_flag(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        resolved = {
            "trait": {"last_observed": (now - timedelta(days=45)).isoformat(), "metadata": {}}
        }
        governance.update_dormancy_flags(resolved, now=now)
        self.assertTrue(resolved["trait"]["metadata"].get("dormant"))

    def test_rollback_manifest_roundtrip(self) -> None:
        manifest = governance.build_rollback_manifest({"trait": {}}, {"items": []}, {"items": [], "by_trait": {}})
        tmp = Path("/tmp/test_manifest.json")
        governance.write_rollback_manifest(tmp, manifest)
        loaded = governance.read_rollback_manifest(tmp)
        self.assertIsNotNone(loaded)
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
