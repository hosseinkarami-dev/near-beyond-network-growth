import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bigquery import collect_daily_gross_burn
from sources import SOURCES, SourceName, raw_path
from fetch import fetch_all


class BigQueryDailyBurnTests(unittest.TestCase):
    def test_source_is_registered_at_expected_raw_path(self):
        sources = [s for s in SOURCES if s.name == SourceName.BIGQUERY_DAILY_GROSS_BURN]
        self.assertEqual(len(sources), 1)
        self.assertEqual(raw_path(sources[0]), Path("data/raw/bigquery/daily_gross_burn.json").resolve())
        self.assertIn(SourceName.BIGQUERY_DAILY_GROSS_BURN, {s.name for s in fetch_all.__defaults__[0]})

    def test_queries_execution_outcomes_and_returns_gross_burn_in_near(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_gross_burn.json"
            client = Mock()
            client.query.return_value.result.return_value = [
                {
                    "utc_date": date(2020, 1, 1),
                    "gross_tokens_burnt_near": 1.2345678901234568,
                }
            ]

            self.assertTrue(collect_daily_gross_burn(path, client=client, today_utc=date(2020, 1, 2)))

            sql = client.query.call_args.args[0]
            self.assertIn("`bigquery-public-data.crypto_near_mainnet_us.execution_outcomes`", sql)
            self.assertIn("SUM(tokens_burnt) / 1e24 AS gross_tokens_burnt_near", sql)
            self.assertNotIn("{{table}}", sql)
            record = json.loads(path.read_text())[0]
            self.assertEqual(record["utc_date"], "2020-01-01")
            self.assertEqual(record["gross_tokens_burnt_near"], 1.2345678901234568)

    def test_incremental_collection_starts_after_last_record_and_skips_duplicate_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_gross_burn.json"
            original = [{"utc_date": "2020-01-01", "gross_tokens_burnt_near": 123}]
            path.write_text(json.dumps(original))
            client = Mock()
            client.query.return_value.result.return_value = [
                {"utc_date": date(2020, 1, 1), "gross_tokens_burnt_near": 456},
                {"utc_date": date(2020, 1, 2), "gross_tokens_burnt_near": 789},
            ]

            self.assertTrue(collect_daily_gross_burn(path, client=client, today_utc=date(2020, 1, 3)))

            self.assertIn("DATE('2020-01-02')", client.query.call_args.args[0])
            records = json.loads(path.read_text())
            self.assertEqual([r["utc_date"] for r in records], ["2020-01-01", "2020-01-02"])
            self.assertEqual(records[0], original[0])


if __name__ == "__main__":
    unittest.main()
