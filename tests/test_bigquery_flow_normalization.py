import sys
import unittest
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sources import SourceName
from normalization.parsers.bigquery.daily_flows import (
    parse_contract_reward_event_audit,
    parse_daily_gross_burn,
)
from normalization.registry import PARSER_REGISTRATIONS


class BigQueryDailyFlowNormalizationTests(unittest.TestCase):
    def test_audited_contract_rewards_preserve_event_coverage(self):
        raw = {
            "complete": True,
            "query_range": {"start_date": "2026-08-04", "end_date": "2026-11-04"},
            "items": [{
                "utc_date": "2026-11-04",
                "total_reward_events": 10,
                "valid_reward_events": 9,
                "missing_previous_balance": 1,
                "ambiguous_order": 0,
                "non_positive_delta": 0,
                "event_count_coverage_pct": Decimal("90"),
                "contract_rewards_near": Decimal("743.281945120000000001"),
            }],
        }
        result = parse_contract_reward_event_audit(raw)["contract_reward_event_audit.json"]
        self.assertEqual(result["observations"][0]["contract_rewards_near"], Decimal("743.281945120000000001"))
        self.assertEqual(result["observations"][0]["valid_reward_events"], 9)
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

    def test_contract_reward_audit_uses_bom_tolerant_raw_reader(self):
        registration = next(
            entry for entry in PARSER_REGISTRATIONS
            if entry.source is SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT
        )
        self.assertEqual(registration.raw_encoding, "utf-8-sig")
        self.assertTrue(registration.parse_float_as_decimal)


if __name__ == "__main__":
    unittest.main()
