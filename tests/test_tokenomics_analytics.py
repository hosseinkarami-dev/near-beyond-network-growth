import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analytics.tokenomics import build_tokenomics_analytics


class TokenomicsAnalyticsTests(unittest.TestCase):
    def test_moving_averages_require_complete_calendar_windows(self):
        from analytics.tokenomics import _price_rows

        prices = {
            date(2024, 1, 1) + timedelta(days=offset): Decimal(offset + 1)
            for offset in range(7) if offset != 3
        }
        rows = _price_rows(prices)
        self.assertIsNone(rows[-1]["moving_average_7d"])
        self.assertIsNone(rows[-1]["moving_average_30d"])

    def test_snapshot_keeps_tokenomics_metrics_and_uses_normalized_supply(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "normalized"
            network_dir = root / "nearblocks" / "stats" / "network"
            tokenomics_dir = root / "nearblocks" / "stats" / "tokenomics"
            price_dir = root / "binance" / "near_price"
            supply_dir = root / "bigquery"
            network_dir.mkdir(parents=True)
            tokenomics_dir.mkdir(parents=True)
            price_dir.mkdir(parents=True)
            supply_dir.mkdir(parents=True)
            source_metrics = {
                "avg_block_time": {"value": "0.5"},
                "change_24h": {"value": "-2.3"},
                "circulating_supply": {"value": "1311062886052171257973403355659208"},
                "gas_price": {"value": "100000000"},
                "market_cap": {"value": "4829496201.00000000"},
                "near_btc_price": {"value": "0.00004859"},
                "near_price": {"value": "3.68000000"},
                "nodes_online": {"value": 338},
                "total_supply": {"value": "1311062886052171257973403355659208"},
                "total_txns": {"value": "5476436201"},
                "tps": {"value": 7},
                "volume_24h": {"value": "270690670.00000000"},
            }
            (network_dir / "summary.json").write_text(json.dumps({
                "network": "NEAR mainnet", "updated_at": "2026-11-08T17:48:43Z",
                "metrics": {field: value for field, value in source_metrics.items()
                            if field in {"avg_block_time", "gas_price", "nodes_online", "total_txns", "tps"}},
            }), encoding="utf-8")
            (tokenomics_dir / "summary.json").write_text(json.dumps({
                "network": "NEAR mainnet", "updated_at": "2026-11-08T17:48:43Z",
                "metrics": {
                    "change_24h": {"value": "-2.3"},
                    "circulating_supply": {"value": "1311062886.052171257973403355659208"},
                    "market_cap": {"value": "4829496201.00000000"},
                    "near_btc_price": {"value": "0.00004859"},
                    "near_price": {"value": "3.68000000"},
                    "total_supply": {"value": "1311062886.052171257973403355659208"},
                    "volume_24h": {"value": "270690670.00000000"},
                    "daily_burn": {"value": "0.000001"},
                    "net_supply_change": {"value": "-0.000001"},
                },
            }), encoding="utf-8")
            start = date(2024, 1, 1)
            observations = []
            for offset in range(35):
                day = start + timedelta(days=offset)
                observations.append({
                    "date": day.isoformat(),
                    "timestamp": (day - date(1970, 1, 1)).days * 86_400_000,
                    "price": str(offset + 1),
                })
            (price_dir / "nearusdt_1d_close_price.json").write_text(json.dumps({
                "market": {"symbol": "NEARUSDT"},
                "metric": {"unit": "USDT"},
                "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
                "observations": observations,
            }), encoding="utf-8")
            (supply_dir / "daily_supply.json").write_text(json.dumps({
                "metric": {"unit": "NEAR", "aggregation": "period_end_snapshot",
                           "supply_precision": "approximate_float64"},
                "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
                "observations": [
                    {"date": (start + timedelta(days=offset)).isoformat(),
                     "timestamp": ((start + timedelta(days=offset)) - date(1970, 1, 1)).days * 86_400_000,
                     "total_supply": str(1000 + offset),
                     "circulating_supply": str(900 + offset)}
                    for offset in range(35)
                ],
            }), encoding="utf-8")

            flow_observations = [
                {"utc_date": (start + timedelta(days=offset)).isoformat(),
                 "gross_tokens_burnt_near": "0.5"}
                for offset in range(35)
            ]
            (supply_dir / "daily_gross_burn.json").write_text(json.dumps({
                "source": {"provider": "Google BigQuery"},
                "metric": {"unit": "NEAR", "frequency": "daily"},
                "observations": flow_observations,
            }), encoding="utf-8")
            (supply_dir / "daily_contract_rewards.json").write_text(json.dumps({
                "source": {
                    "provider": "Google BigQuery",
                    "data_status": "synthetic",
                    "is_synthetic": True,
                    "purpose": "development_and_dashboard_testing",
                },
                "metric": {"unit": "NEAR", "frequency": "daily"},
                "observations": [
                    {"utc_date": (start + timedelta(days=offset)).isoformat(),
                     "contract_rewards_near": "0.125000000000000001"}
                    for offset in range(35)
                ],
            }), encoding="utf-8")

            output_path = build_tokenomics_analytics(root, Path(temp) / "analytics" / "tokenomics")
            snapshot = json.loads(output_path.read_text(encoding="utf-8"))
            daily = json.loads((output_path.parent / "daily_metrics.json").read_text(encoding="utf-8"))
            daily_tokenomics = json.loads((output_path.parent / "daily_tokenomics.json").read_text(encoding="utf-8"))
            weekly_supply = json.loads((output_path.parent / "weekly_supply.json").read_text(encoding="utf-8"))
            monthly_supply = json.loads((output_path.parent / "monthly_supply.json").read_text(encoding="utf-8"))
            daily_supply = json.loads((output_path.parent / "daily_supply.json").read_text(encoding="utf-8"))
            demo_path = output_path.parent / "contract_rewards_demo.json"
            self.assertFalse(demo_path.exists())
            build_tokenomics_analytics(
                root, output_path.parent, include_synthetic_demo=True
            )
            demo = json.loads(demo_path.read_text(encoding="utf-8"), parse_float=Decimal)

        self.assertEqual(snapshot["network"], "NEAR mainnet")
        self.assertEqual(snapshot["metrics"]["total_supply"], 1034)
        self.assertEqual(snapshot["metrics"]["circulating_supply"], 934)
        self.assertEqual(snapshot["metrics"]["near_price"], {
            "value": 35,
            "moving_average_7d": 32,
            "moving_average_30d": 20.5,
        })
        self.assertEqual(snapshot["metrics"]["daily_burn"], "0.000001")
        self.assertEqual(snapshot["metrics"]["non_circulating_supply_near"], 100)
        self.assertAlmostEqual(snapshot["metrics"]["circulating_supply_ratio_pct"], 934 / 1034 * 100)
        self.assertEqual(snapshot["metrics"]["net_supply_change_30d_near"], 30)
        self.assertEqual(snapshot["metrics"]["gross_burn_30d_near"], 15)
        self.assertEqual(snapshot["metrics"]["estimated_gross_issuance_30d_near"], 45)
        self.assertEqual(snapshot["metrics"]["deflationary_days_30d"], 0)
        self.assertTrue(snapshot["data_quality"]["daily_contract_rewards"]["is_synthetic"])
        self.assertNotIn("contract_rewards_30d_near", snapshot["metrics"])
        self.assertNotIn("tps", snapshot["metrics"])
        self.assertEqual(len(daily["observations"]), 35)
        self.assertIsNone(daily["observations"][0]["moving_average_7d"])
        self.assertEqual(daily["observations"][6]["moving_average_7d"], 4)
        self.assertEqual(daily["observations"][29]["moving_average_30d"], 15.5)
        self.assertEqual(len(daily_supply["items"]), 35)
        self.assertEqual(weekly_supply["items"][0]["total_supply"], 1006)
        self.assertEqual(weekly_supply["items"][0]["circulating_supply"], 906)
        self.assertEqual(monthly_supply["items"][0]["total_supply"], 1030)
        self.assertEqual(weekly_supply["metric"]["aggregation"], "period_end_snapshot")
        self.assertEqual(daily_tokenomics["items"][-1]["daily_net_supply_change_near"], 1)
        self.assertEqual(daily_tokenomics["items"][-1]["estimated_gross_issuance_near"], 1.5)
        self.assertTrue(demo["is_synthetic"])
        self.assertEqual(demo["summary"]["total_30d_near"], Decimal("3.750000000000000030"))


if __name__ == "__main__":
    unittest.main()
