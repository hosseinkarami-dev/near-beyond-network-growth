import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import SourceName
from normalization.parsers.bigquery.daily_flows import (
    parse_daily_contract_rewards,
    parse_daily_gross_burn,
)
from normalization.registry import PARSER_REGISTRATIONS


class BigQueryDailyFlowNormalizationTests(unittest.TestCase):
    def test_contract_rewards_passthrough_keeps_precision_and_synthetic_provenance(self):
        result = parse_daily_contract_rewards([{
            "utc_date": "2026-11-10",
            "contract_rewards_near": Decimal("743.281945120000000001"),
        }])["daily_contract_rewards.json"]

        self.assertEqual(result["observations"], [{
            "utc_date": "2026-11-10",
            "contract_rewards_near": Decimal("743.281945120000000001"),
        }])
        self.assertEqual(result["source"]["data_status"], "synthetic")
        self.assertTrue(result["source"]["is_synthetic"])
        self.assertEqual(result["source"]["purpose"], "development_and_dashboard_testing")
        self.assertEqual(result["metric"]["unit"], "NEAR")

    def test_gross_burn_is_normalized_without_unit_conversion(self):
        result = parse_daily_gross_burn([{
            "utc_date": "2026-11-10",
            "gross_tokens_burnt_near": Decimal("0.000000000000000001"),
        }])["daily_gross_burn.json"]
        self.assertEqual(
            result["observations"][0]["gross_tokens_burnt_near"],
            Decimal("0.000000000000000001"),
        )
        self.assertNotIn("is_synthetic", result["source"])

    def test_contract_rewards_rejects_invalid_duplicate_and_negative_records(self):
        invalid_records = [
            [{"utc_date": "2026-02-30", "contract_rewards_near": 1}],
            [
                {"utc_date": "2026-11-10", "contract_rewards_near": 1},
                {"utc_date": "2026-11-10", "contract_rewards_near": 2},
            ],
            [{"utc_date": "2026-11-10", "contract_rewards_near": -1}],
            [{"utc_date": "2026-11-10", "contract_rewards_near": True}],
        ]
        for records in invalid_records:
            with self.subTest(records=records), self.assertRaises(ValueError):
                parse_daily_contract_rewards(records)

    def test_only_contract_rewards_uses_bom_tolerant_raw_reader(self):
        registration = next(
            entry for entry in PARSER_REGISTRATIONS
            if entry.source is SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS
        )
        self.assertEqual(registration.raw_encoding, "utf-8-sig")
        self.assertTrue(registration.parse_float_as_decimal)
        self.assertEqual(date.fromisoformat("2026-11-10").isoformat(), "2026-11-10")


if __name__ == "__main__":
    unittest.main()
