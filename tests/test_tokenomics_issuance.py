import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analytics.tokenomics_issuance import build_issuance_analytics


class TokenomicsIssuanceTests(unittest.TestCase):
    def test_burn_coverage_uses_near_and_preserves_daily_flow_aggregation(self):
        monday = date(2026, 1, 5)
        tuesday = date(2026, 1, 6)
        supplies = {
            monday: {"total_supply": Decimal("1000")},
            tuesday: {"total_supply": Decimal("1018")},
        }
        supply_metrics = {
            monday: {"daily_net_supply_change_near": Decimal("8")},
            tuesday: {"daily_net_supply_change_near": Decimal("18")},
        }
        burns = {
            monday: {"net_burn_near": Decimal("2"), "net_burn_usd": Decimal("9000")},
            tuesday: {"net_burn_near": Decimal("2"), "net_burn_usd": Decimal("9000")},
        }

        _rows, document, _metrics = build_issuance_analytics(
            supplies,
            supply_metrics,
            burns,
            {monday: Decimal("1"), tuesday: Decimal("1")},
            network="NEAR mainnet",
            updated_at=None,
        )

        daily = document["items"]
        self.assertEqual(daily[0]["burn_coverage_pct"], Decimal("20"))
        self.assertEqual(daily[1]["burn_coverage_pct"], Decimal("10"))
        self.assertEqual(daily[0]["net_burn_near"], Decimal("2"))

        weekly = document["periods"]["weekly"][0]
        self.assertEqual(weekly["net_burn_near"], Decimal("4"))
        self.assertEqual(weekly["gross_issuance_near"], Decimal("30"))
        self.assertEqual(weekly["burn_coverage_pct"], Decimal("4") / Decimal("30") * Decimal("100"))
        self.assertEqual(
            document["metric"]["burn_coverage_formula"],
            "net_burn_near / estimated_gross_issuance_near * 100",
        )


if __name__ == "__main__":
    unittest.main()
