import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_analytics
import normalize
from analytics.validators import build_validator_analytics
from sources import SourceName
from normalization.registry import ParserRegistration


class PartialPipelineTests(unittest.TestCase):
    def test_normalization_skips_missing_or_bad_sources_and_keeps_good_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            raw_root.mkdir()
            good_raw = raw_root / "good.json"
            good_raw.write_text('{"ok": true}', encoding="utf-8")
            bad_raw = raw_root / "bad.json"
            bad_raw.write_text("{invalid", encoding="utf-8")
            normalized_root = root / "data" / "normalized"

            def raw_for(source):
                return raw_root / {
                    SourceName.NEAR_BLOCKS_NETWORK_STATS: "good.json",
                    SourceName.NEAR_BLOCKS_VALIDATORS_INFO: "bad.json",
                    SourceName.NEAR_BLOCKS_VALIDATORS: "missing.json",
                }[source.name]

            def parser(raw):
                if not raw["ok"]:
                    raise ValueError("bad source")
                return {"summary.json": {"available": True}}

            registrations = (
                ParserRegistration(SourceName.NEAR_BLOCKS_NETWORK_STATS, parser,
                                   normalized_root / "good"),
                ParserRegistration(SourceName.NEAR_BLOCKS_VALIDATORS_INFO, parser,
                                   normalized_root / "bad"),
                ParserRegistration(SourceName.NEAR_BLOCKS_VALIDATORS, parser,
                                   normalized_root / "missing"),
            )
            with (
                patch.object(normalize, "DATA_ROOT", root / "data"),
                patch.object(normalize, "NORMALIZED_DATA_DIR", normalized_root),
                patch.object(normalize, "PARSER_REGISTRATIONS", registrations),
                patch.object(normalize, "raw_path", raw_for),
            ):
                self.assertTrue(normalize.normalize_all())

            self.assertTrue((normalized_root / "good" / "summary.json").exists())
            self.assertFalse((normalized_root / "bad" / "summary.json").exists())
            self.assertFalse((normalized_root / "missing" / "summary.json").exists())

    def test_section_build_failures_write_empty_snapshots_and_continue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analytics_root = root / "data" / "analytics"

            def metadata():
                analytics_root.mkdir(parents=True, exist_ok=True)
                (analytics_root / "dashboard.json").write_text("{}", encoding="utf-8")

            with (
                patch.object(build_analytics, "DATA_ROOT", root / "data"),
                patch.object(build_analytics, "ANALYTICS_ROOT", analytics_root),
                patch.object(build_analytics, "build_network_analytics", side_effect=RuntimeError("offline")),
                patch.object(build_analytics, "build_tokenomics_analytics", side_effect=RuntimeError("offline")),
                patch.object(build_analytics, "build_near_intents_analytics", side_effect=RuntimeError("offline")),
                patch.object(build_analytics, "build_protocol_analytics", side_effect=RuntimeError("offline")),
                patch.object(build_analytics, "build_dashboard_metadata", side_effect=metadata),
            ):
                build_analytics.build_all_analytics()

            expected = (
                "network/snapshot.json",
                "tokenomics/snapshot.json",
                "near_intents/snapshot.json",
                "protocols/fees/snapshot.json",
                "protocols/revenue/snapshot.json",
                "protocols/dex_volume/snapshot.json",
                "dashboard.json",
            )
            for relative_path in expected:
                self.assertTrue((analytics_root / relative_path).is_file(), relative_path)

    def test_validator_aggregations_are_built_from_normalized_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "validators.json"
            path.write_text(json.dumps({
                "updated_at": "2026-11-12T00:00:00Z",
                "items": [
                    {"account_id": "alpha.poolv1.near", "is_active": True,
                     "stake_near": "10", "commission_pct": "10",
                     "delegators_count": 3, "blocks_produced": "9", "blocks_expected": "10"},
                    {"account_id": "beta.poolv1.near", "is_active": True,
                     "stake_near": "5", "commission_pct": "20",
                     "delegators_count": 2, "blocks_produced": "5", "blocks_expected": "5"},
                    {"account_id": "inactive.poolv1.near", "is_active": False,
                     "stake_near": "100", "commission_pct": "90",
                     "delegators_count": 100, "blocks_produced": "0", "blocks_expected": "10"},
                ],
            }), encoding="utf-8")

            result = build_validator_analytics(path, Decimal("30"))
            metrics = result["metrics"]
            self.assertEqual(metrics["total_active_stake"], Decimal("15"))
            self.assertEqual(metrics["staking_ratio"], Decimal("50"))
            self.assertEqual(metrics["active_validators_count"], 2)
            self.assertEqual(metrics["total_delegators"], 5)
            self.assertEqual(metrics["average_commission"], Decimal(40) / Decimal(3))
            self.assertEqual(metrics["block_production_rate"], Decimal("93.33333333333333333333333333"))
            self.assertEqual(result["validators"]["items"][0]["account_id"], "alpha.poolv1.near")


if __name__ == "__main__":
    unittest.main()
