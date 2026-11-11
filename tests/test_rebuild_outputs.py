"""Rebuild commands must remove stale normalized and analytics artifacts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_analytics
import normalize
from normalization.registry import ParserRegistration
from common import SourceName


class RebuildOutputTests(unittest.TestCase):
    def test_normalize_clears_old_and_unregistered_files_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            normalized_root = project_root / "data" / "normalized"
            raw_file = project_root / "raw.json"
            raw_file.write_text("{}", encoding="utf-8")

            stale_file = normalized_root / "bigquery" / "daily_supply.json"
            stale_file.parent.mkdir(parents=True)
            stale_file.write_text("old", encoding="utf-8")
            orphan_file = normalized_root / "old_provider" / "orphan.json"
            orphan_file.parent.mkdir(parents=True)
            orphan_file.write_text("old", encoding="utf-8")

            registration = ParserRegistration(
                source=SourceName.NEAR_BLOCKS,
                parser=lambda _raw: {"fresh.json": {"value": "new"}},
                normalized_directory=normalized_root / "nearblocks",
            )
            with (
                patch.object(normalize, "PROJECT_ROOT", project_root),
                patch.object(normalize, "NORMALIZED_DATA_DIR", normalized_root),
                patch.object(normalize, "PARSER_REGISTRATIONS", (registration,)),
                patch.object(normalize, "raw_path", return_value=raw_file),
            ):
                self.assertTrue(normalize.normalize_all())

            self.assertFalse(stale_file.exists())
            self.assertFalse(orphan_file.exists())
            self.assertEqual(
                json.loads((normalized_root / "nearblocks" / "fresh.json").read_text()),
                {"value": "new"},
            )

    def test_analytics_build_clears_stale_artifacts_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            analytics_root = project_root / "data" / "analytics"
            stale_file = analytics_root / "tokenomics" / "daily_supply.json"
            stale_file.parent.mkdir(parents=True)
            stale_file.write_text("old", encoding="utf-8")

            def write_output(relative_path):
                def build(**_kwargs):
                    output = analytics_root / relative_path
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text("fresh", encoding="utf-8")
                return build

            with (
                patch.object(build_analytics, "PROJECT_ROOT", project_root),
                patch.object(build_analytics, "ANALYTICS_ROOT", analytics_root),
                patch.object(build_analytics, "build_network_analytics", write_output("network/daily.json")),
                patch.object(build_analytics, "build_tokenomics_analytics", write_output("tokenomics/daily.json")),
                patch.object(build_analytics, "build_near_intents_analytics", write_output("near_intents/daily.json")),
                patch.object(build_analytics, "build_protocol_analytics", write_output("protocols/fees/daily.json")),
                patch.object(build_analytics, "build_dashboard_metadata", write_output("dashboard.json")),
            ):
                build_analytics.build_all_analytics()

            self.assertFalse(stale_file.exists())
            self.assertEqual(
                (analytics_root / "dashboard.json").read_text(encoding="utf-8"),
                "fresh",
            )
            self.assertEqual(
                (analytics_root / "protocols" / "fees" / "daily.json").read_text(encoding="utf-8"),
                "fresh",
            )


if __name__ == "__main__":
    unittest.main()
