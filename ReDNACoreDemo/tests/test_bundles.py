from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from ReDNACoreDemo.core import storage
from ReDNACoreDemo.core.bundles import CURRENT_VERSION


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_id = "bundle_test_user"
        storage.write_user_state(
            self.user_id,
            resolved={"PaDNA.HairDNA.Style": {"resolved_value": "Curly", "ucn": 72, "reasons": ["demo"]}},
            evidence={"items": [{"trait": "PaDNA.HairDNA.Style", "value": "Curly", "ucn": 72}]},
            observations={"items": [], "by_trait": {}},
        )

    def tearDown(self) -> None:
        paths = storage.ensure_dirs_for_user(self.user_id)
        for target in (paths["resolved"], paths["evidence"], paths["observations"], storage.BUNDLES_DIR / f"{self.user_id}_import_v1.json"):
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass

    def test_export_bundle_sets_meta_version(self) -> None:
        path = storage.export_bundle(self.user_id)
        try:
            data = json.loads(Path(path).read_text())
            self.assertEqual(data["meta"]["version"], CURRENT_VERSION)
            self.assertIn("resolved", data)
        finally:
            if Path(path).exists():
                Path(path).unlink()

    def test_import_migrates_v1_bundle(self) -> None:
        payload = {
            "meta": {"version": "1.0", "user_id": self.user_id},
            "resolved": {"PaDNA.HairDNA.Style": {"resolved_value": "Straight"}},
            "evidence": {"items": []},
            "observations": None,
        }
        bundle_path = storage.BUNDLES_DIR / f"{self.user_id}_import_v1.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps(payload))

        migrated = storage.import_bundle(bundle_path, apply=False)
        self.assertEqual(migrated["meta"]["version"], CURRENT_VERSION)
        self.assertEqual(migrated["meta"].get("migrated_from"), "1.0")
        self.assertIn("reasons", migrated["resolved"]["PaDNA.HairDNA.Style"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
