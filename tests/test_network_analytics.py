import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analytics.network import DAILY_FIELDS, INPUTS, build_network_analytics, near_to_usd, usd_to_near


def utc_ms(day: date) -> int:
    return (day - date(1970, 1, 1)).days * 86_400_000


def make_fixture(root: Path, *, null_new_contract=False, zero_price_day=None,
                 invalid_price_day=None):
    start = date(2024, 1, 1)
    days = [date.fromordinal(start.toordinal() + index) for index in range(40)]
    value_sets = {}
    for field, spec in INPUTS.items():
        observations = []
        for offset, day in enumerate(days, start=1):
            if (field == "transactions" and offset == 4) or (field == "tvl_usd" and offset == 8):
                continue
            if field == "near_usd_price" and offset == 9:
                continue
            if field == "new_contracts" and null_new_contract and offset == 5:
                value = None
            elif field == "near_usd_price" and offset == zero_price_day:
                value = "0"
            elif field == "near_usd_price" and offset == invalid_price_day:
                value = "invalid"
            elif field == "transactions":
                value = offset
            elif field == "transaction_fees_near":
                value = "1.23456789"
            elif field == "active_accounts":
                value = 100 + offset
            elif field == "active_contracts":
                value = 200 + offset
            elif field == "new_contracts":
                value = offset
            elif field == "tvl_usd":
                value = 1000 + offset
            else:
                value = f"{offset}.12345678"
            key = spec["value_key"]
            observations.append({"date": day.isoformat(), "timestamp": utc_ms(day), key: value})
        value_sets[field] = observations

        if field == "near_usd_price":
            doc = {
                "network": "NEAR mainnet",
                "market": {"symbol": "NEARUSDT"},
                "metric": {"unit": "USDT", "frequency": "daily", "value_type": "decimal"},
                "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
                "observations": observations,
            }
        else:
            doc = {
                "network": "NEAR mainnet",
                "metric": {"unit": spec["unit"], "frequency": "daily", "value_type": spec["value_type"]},
                "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
                "observations": observations,
            }
        dest = (root / Path(spec["path"]).parent)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / Path(spec["path"]).name).write_text(json.dumps(doc), encoding="utf-8")

    summary = {
        "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": "2024-02-10T00:00:00Z",
        "source": {"provider": "NearBlocks", "endpoint": "not included in snapshot"},
        "metrics": {
            "avg_block_time": {"metric_id": "near.avg_block_time", "value": "0.59410000"},
            "tps": {"metric_id": "near.tps", "value": 7},
            "nodes_online": {"metric_id": "near.nodes_online", "value": 338},
            "gas_price": {"metric_id": "near.gas_price", "value": "100000000"},
        },
    }
    summary_dir = root / "nearblocks" / "stats" / "network"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    stablecoin_rows = [{
        "date": day.isoformat(),
        "total_circulating_usd_by_peg": {
            "peggedUSD": str(1000 + offset),
            "peggedEUR": str(100 * offset),
            "peggedGBP": None,
        },
    } for offset, day in enumerate(days, start=1)]
    stablecoin_dir = root / "defillama" / "near_stablecoin"
    stablecoin_dir.mkdir(parents=True, exist_ok=True)
    (stablecoin_dir / "daily_stablecoin_market_data.json").write_text(json.dumps({
        "source": {"provider": "DefiLlama", "endpoint": "stablecoincharts/Near"},
        "observations": stablecoin_rows,
    }), encoding="utf-8")
    return days, summary


class NearUsdConversionTests(unittest.TestCase):
    def test_conversions_use_decimal_arithmetic(self):
        self.assertEqual(near_to_usd("0.12345678", "2.5"), Decimal("0.308641950"))
        self.assertEqual(usd_to_near("2", "0.5"), Decimal("4"))

    def test_missing_zero_invalid_and_non_finite_prices_return_null(self):
        for price in (None, "0", "-1", "invalid", "NaN", "Infinity"):
            with self.subTest(price=price):
                self.assertIsNone(near_to_usd("1", price))
                self.assertIsNone(usd_to_near("1", price))
        self.assertIsNone(near_to_usd(None, "1"))
        self.assertIsNone(usd_to_near("invalid", "1"))


class NetworkAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input_root = self.root / "normalized"
        self.output_dir = self.root / "analytics" / "network"
        self.days, self.summary = make_fixture(self.input_root, null_new_contract=True)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, **kwargs):
        return build_network_analytics(self.input_root, self.output_dir, **kwargs)

    def read_outputs(self):
        result = self.build()
        daily = json.loads(result["daily"].read_text(encoding="utf-8"), parse_float=Decimal)
        snapshot = json.loads(result["snapshot"].read_text(encoding="utf-8"), parse_float=Decimal)
        return result, daily, snapshot

    def test_inner_join_excludes_missing_dates_and_null_values(self):
        result, daily, _ = self.read_outputs()
        report = result["report"]
        self.assertEqual(report["unique_dates_before_join"], 40)
        self.assertEqual(report["dates_after_inner_join"], 37)
        self.assertEqual(report["records_excluded_due_to_missing_dates"], 3)
        self.assertEqual(report["records_excluded_due_to_null_values"], 1)
        self.assertEqual(report["records_excluded_due_to_invalid_values"], 0)
        self.assertEqual(report["records_after_join_and_validation"], 36)
        self.assertEqual(report["first_date"], "2024-01-01")
        self.assertEqual(report["last_date"], "2024-02-09")
        dates = {row["date"] for row in daily["observations"]}
        self.assertNotIn("2024-01-04", dates)
        self.assertNotIn("2024-01-08", dates)
        self.assertNotIn("2024-01-09", dates)
        self.assertNotIn("2024-01-05", dates)
        self.assertEqual(set(daily["observations"][0]), set(DAILY_FIELDS))
        self.assertTrue(all(all(row[field] is not None for field in DAILY_FIELDS) for row in daily["observations"]))

    def test_zero_or_invalid_prices_exclude_the_shared_date_without_filling(self):
        make_fixture(self.input_root, zero_price_day=6, invalid_price_day=7)
        result, daily, _ = self.read_outputs()
        self.assertEqual(result["report"]["records_excluded_due_to_invalid_values"], 2)
        self.assertEqual(result["report"]["records_after_join_and_validation"], 35)
        dates = {row["date"] for row in daily["observations"]}
        self.assertNotIn("2024-01-06", dates)
        self.assertNotIn("2024-01-07", dates)

    def test_price_and_fee_are_joined_on_exact_date_and_rounded_as_json_numbers(self):
        result, daily, _ = self.read_outputs()
        day = next(row for row in daily["observations"] if row["date"] == "2024-01-10")
        self.assertEqual(day["near_usd_price"], Decimal("10.12345678"))
        self.assertEqual(day["transaction_fees_near"], Decimal("1.23456789"))
        self.assertEqual(day["transaction_fees_usd"], Decimal("12.5"))
        raw_text = result["daily"].read_text(encoding="utf-8")
        self.assertIn('"transaction_fees_usd": 12.5', raw_text)
        self.assertNotIn('"transaction_fees_usd": "12.5"', raw_text)

    def test_daily_rows_have_only_requested_source_and_conversion_fields(self):
        _, daily, _ = self.read_outputs()
        self.assertEqual(set(daily), {"schema_version", "network", "time", "observations"})
        self.assertTrue(all(set(row) == set(DAILY_FIELDS) for row in daily["observations"]))

    def test_calendar_periods_sum_flows_and_keep_period_end_stocks(self):
        self.build()
        weekly = json.loads((self.output_dir / "weekly_metrics.json").read_text(encoding="utf-8"))
        first = weekly["observations"][0]
        self.assertEqual(first["period"], "2024-W01")
        self.assertEqual(first["days_observed"], 5)
        self.assertEqual(first["transactions"], 19)
        self.assertEqual(first["new_contracts"], 19)
        self.assertEqual(first["active_accounts"], 107)
        self.assertEqual(first["tvl_usd"], 1007)
        self.assertEqual(weekly["aggregation"]["tvl_usd"], "period_end_snapshot")
        for period in ("monthly", "quarterly", "yearly"):
            self.assertTrue((self.output_dir / f"{period}_metrics.json").exists())

    def test_snapshot_is_compact_and_uses_final_joined_rows(self):
        _, daily, snapshot = self.read_outputs()
        self.assertEqual(set(snapshot), {"network", "network_stats", "key_metrics"})
        self.assertNotIn("daily_overview", snapshot)
        self.assertEqual(set(snapshot["network"]), {"name", "updated_at"})
        self.assertEqual(set(snapshot["network_stats"]), {"avg_block_time", "tps", "nodes_online", "gas_price"})
        self.assertEqual(snapshot["network"]["name"], self.summary["network"])
        self.assertEqual(snapshot["network"]["updated_at"], self.summary["updated_at"])
        self.assertEqual(snapshot["network_stats"]["avg_block_time"], Decimal("0.5941"))
        self.assertEqual(snapshot["network_stats"]["gas_price"], 100000000)
        metrics = snapshot["key_metrics"]
        self.assertEqual(set(metrics), {
            "transactions", "transaction_fees_near", "transaction_fees_usd", "active_accounts", "active_contracts",
            "new_contracts", "tvl_usd", "tvl_near", "near_usd_price", "stablecoin_supply_usd",
            "total_transaction_fees_near",
        })
        percentage_fields = {"value", "change_24h_pct", "change_7d_pct", "change_30d_pct"}
        for field in metrics.keys() - {"new_contracts", "stablecoin_supply_usd", "total_transaction_fees_near"}:
            self.assertEqual(set(metrics[field]), percentage_fields)
        self.assertEqual(set(metrics["new_contracts"]), {"value", "change_24h", "sum_7d", "sum_30d"})
        self.assertEqual(metrics["stablecoin_supply_usd"]["date"], "2024-02-09")
        self.assertNotIn("source", snapshot)
        self.assertNotIn("network_trends", snapshot)
        self.assertNotIn("data_freshness", snapshot)
        last = max(daily["observations"], key=lambda row: row["date"])
        self.assertEqual(daily["observations"][-1]["date"], last["date"])
        for field, metric in metrics.items():
            if field not in {"stablecoin_supply_usd", "total_transaction_fees_near"}:
                self.assertEqual(metric["value"], last[field])
        total_fees = metrics["total_transaction_fees_near"]
        self.assertEqual(total_fees["value"], sum(row["transaction_fees_near"] for row in daily["observations"]))
        self.assertEqual(total_fees["unit"], "NEAR")
        self.assertEqual(total_fees["through"], last["date"])

    def test_snapshot_uses_exact_dates_and_complete_calendar_windows(self):
        _, daily, snapshot = self.read_outputs()
        metrics = snapshot["key_metrics"]
        rows = {date.fromisoformat(row["date"]): row for row in daily["observations"]}
        latest_day = max(rows)
        self.assertEqual(latest_day.isoformat(), daily["observations"][-1]["date"])
        tx = metrics["transactions"]
        current, previous = rows[latest_day]["transactions"], rows[latest_day - timedelta(days=1)]["transactions"]
        self.assertEqual(tx["change_24h_pct"], ((Decimal(current - previous) / Decimal(previous)) * 100).quantize(Decimal("0.0001")))
        week_value = rows[latest_day - timedelta(days=7)]["transactions"]
        month_value = rows[latest_day - timedelta(days=30)]["transactions"]
        self.assertEqual(tx["change_7d_pct"], (Decimal(current - week_value) / Decimal(week_value) * 100).quantize(Decimal("0.0001")))
        self.assertEqual(tx["change_30d_pct"], (Decimal(current - month_value) / Decimal(month_value) * 100).quantize(Decimal("0.0001")))
        new_contracts = metrics["new_contracts"]
        self.assertEqual(new_contracts["change_24h"], rows[latest_day]["new_contracts"] - rows[latest_day - timedelta(days=1)]["new_contracts"])
        self.assertEqual(new_contracts["sum_7d"], sum(rows[latest_day - timedelta(days=n)]["new_contracts"] for n in range(7)))
        self.assertEqual(new_contracts["sum_30d"], sum(rows[latest_day - timedelta(days=n)]["new_contracts"] for n in range(30)))

    def test_missing_comparison_dates_and_zero_denominators_are_null(self):
        from analytics.network import _percentage_change, _snapshot_key_metrics

        self.assertIsNone(_percentage_change(10, 0))
        rows = [
            {"date": "2024-01-01", "transactions": 1, "transaction_fees_near": 1, "transaction_fees_usd": 1,
             "active_accounts": 1, "active_contracts": 1, "new_contracts": 1,
             "tvl_usd": 1, "tvl_near": 1, "near_usd_price": 1},
            {"date": "2024-01-03", "transactions": 3, "transaction_fees_near": 3, "transaction_fees_usd": 3,
             "active_accounts": 3, "active_contracts": 3, "new_contracts": 3,
             "tvl_usd": 3, "tvl_near": 3, "near_usd_price": 3},
        ]
        metrics = _snapshot_key_metrics(rows)
        self.assertEqual(metrics["total_transaction_fees_near"]["value"], Decimal(4))
        self.assertIsNone(metrics["transactions"]["change_24h_pct"])
        self.assertIsNone(metrics["transactions"]["change_7d_pct"])
        self.assertIsNone(metrics["new_contracts"]["change_24h"])
        self.assertIsNone(metrics["new_contracts"]["sum_7d"])
        self.assertIsNone(metrics["new_contracts"]["sum_30d"])

    def test_latest_snapshot_uses_maximum_date_and_rejects_unsorted_final_dataset(self):
        from analytics.network import _snapshot_key_metrics

        _, daily, _ = self.read_outputs()
        rows = daily["observations"]
        newest = rows[-1]
        self.assertEqual(max(row["date"] for row in rows), newest["date"])
        metrics = _snapshot_key_metrics(rows)
        self.assertEqual(metrics["transactions"]["value"], newest["transactions"])
        with self.assertRaisesRegex(ValueError, "maximum date"):
            _snapshot_key_metrics([rows[-1], rows[0]])

    def test_stablecoin_pipeline_sums_distinct_usd_peg_categories_and_uses_nearest_dates(self):
        result, _, snapshot = self.read_outputs()
        stablecoin = snapshot["key_metrics"]["stablecoin_supply_usd"]
        # Latest offset 40 totals 1040 + 4000; references are offsets 10 and 1.
        self.assertEqual(stablecoin["value"], Decimal("5040"))
        self.assertEqual(stablecoin["date"], "2024-02-09")
        self.assertEqual(stablecoin["reference_30d"], {
            "date": "2024-01-10", "value": Decimal("2010"),
        })
        self.assertEqual(stablecoin["change_30d_usd"], Decimal("3030"))
        self.assertEqual(stablecoin["change_30d_pct"], Decimal("150.7463"))
        # 90 days precedes the available range, so the closest available earlier day is used.
        self.assertEqual(stablecoin["reference_90d"], {
            "date": "2024-01-01", "value": Decimal("1101"),
        })
        self.assertEqual(stablecoin["change_90d_usd"], Decimal("3939"))
        analytics = json.loads(result["stablecoin"].read_text(encoding="utf-8"), parse_float=Decimal)
        self.assertEqual(len(analytics["observations"]), 40)
        self.assertEqual(analytics["observations"][-1]["total_circulating_usd"], Decimal("5040"))
        self.assertEqual(analytics["metric"]["excluded_source_fields"], [
            "totalMintedUSD", "totalUnreleased", "totalBridgedToUSD",
        ])
        self.assertEqual(analytics["observations"][-1]["total_circulating_usd_by_peg"], {
            "peggedUSD": Decimal("1040"), "peggedEUR": Decimal("4000"),
        })
        self.assertNotIn("totalMintedUSD", analytics["observations"][-1])

    def test_stablecoin_calendar_period_files_are_period_end_snapshots(self):
        from analytics.periods import period_bounds

        result = self.build()
        daily = json.loads(result["stablecoin"].read_text(encoding="utf-8"), parse_float=Decimal)
        daily_by_date = {date.fromisoformat(row["date"]): row for row in daily["observations"]}
        self.assertEqual(set(result["stablecoin_periods"]), {
            "weekly", "monthly", "quarterly", "yearly",
        })
        for period, path in result["stablecoin_periods"].items():
            document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
            self.assertEqual(document["period"], period)
            self.assertEqual(document["metric"]["aggregation"], "period_end_snapshot")
            rows = document["observations"]
            self.assertEqual(rows, sorted(rows, key=lambda row: row["period_start"]))
            for row in rows:
                members = [day for day in daily_by_date if period_bounds(day, period)[0] == row["period"]]
                last_day = max(members)
                self.assertEqual(row["date"], last_day.isoformat())
                self.assertEqual(row["total_circulating_usd"],
                                 daily_by_date[last_day]["total_circulating_usd"])

    def test_stablecoin_skips_missing_invalid_and_negative_records_and_guards_zero_denominators(self):
        from analytics.network import _stablecoin_supply

        rows = [
            {"date": "2024-01-01", "total_circulating_usd_by_peg": {"peggedUSD": "0"}},
            {"date": "2024-01-02", "total_circulating_usd_by_peg": {"peggedUSD": "bad"}},
            {"date": "2024-01-03", "total_circulating_usd_by_peg": {"peggedUSD": "-1"}},
            {"date": "2024-01-04", "total_circulating_usd_by_peg": {"peggedUSD": None}},
            {"date": "2024-01-05", "total_circulating_usd_by_peg": {"peggedUSD": "5"}},
        ]
        path = self.input_root / "defillama" / "near_stablecoin" / "daily_stablecoin_market_data.json"
        path.write_text(json.dumps({"source": {}, "observations": rows}), encoding="utf-8")
        analytics, metrics = _stablecoin_supply(self.input_root)
        self.assertEqual([row["date"] for row in analytics["observations"]], ["2024-01-01", "2024-01-05"])
        self.assertIsNone(metrics["change_30d_pct"])
        self.assertIsNone(metrics["change_90d_pct"])
        self.assertEqual(metrics["change_30d_usd"], Decimal("5"))

    def test_stablecoin_sorts_output_and_uses_earlier_date_for_equal_distance(self):
        from analytics.network import _stablecoin_supply

        rows = [
            {"date": "2024-01-31", "total_circulating_usd_by_peg": {"peggedUSD": "30"}},
            {"date": "2023-12-31", "total_circulating_usd_by_peg": {"peggedUSD": "0"}},
            {"date": "2024-01-02", "total_circulating_usd_by_peg": {"peggedUSD": "2"}},
        ]
        path = self.input_root / "defillama" / "near_stablecoin" / "daily_stablecoin_market_data.json"
        path.write_text(json.dumps({"source": {}, "observations": rows}), encoding="utf-8")
        analytics, metrics = _stablecoin_supply(self.input_root)
        self.assertEqual([row["date"] for row in analytics["observations"]], [
            "2023-12-31", "2024-01-02", "2024-01-31",
        ])
        self.assertEqual(metrics["reference_30d"]["date"], "2023-12-31")


if __name__ == "__main__":
    unittest.main()
