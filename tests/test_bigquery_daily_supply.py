import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bigquery import collect_daily_supply
from common import SOURCES, SourceName, fetch_all, raw_path


def row(day, supply):
    return {
        "block_timestamp_utc": "2020-01-01T23:00:00+00:00",
        "utc_date": date.fromisoformat(day),
        "total_supply": supply,
    }


class BigQueryDailySupplyTests(unittest.TestCase):
    def test_source_is_registered_at_expected_raw_path(self):
        sources = [s for s in SOURCES if s.name == SourceName.BIGQUERY_DAILY_SUPPLY]
        self.assertEqual(len(sources), 1)
        self.assertEqual(raw_path(sources[0]), Path("data/raw/bigquery/daily_supply.json").resolve())
        self.assertIn(SourceName.BIGQUERY_DAILY_SUPPLY, {s.name for s in fetch_all.__defaults__[0]})

    def test_missing_file_queries_from_start_date_and_writes_raw_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_supply.json"
            client = Mock()
            client.query.return_value.result.return_value = [row("2020-01-01", 1.25)]

            self.assertTrue(collect_daily_supply(path, client=client, today_utc=date(2020, 1, 3)))

            sql = client.query.call_args.args[0]
            self.assertIn("`bigquery-public-data.crypto_near_mainnet_us.circulating_supply`", sql)
            self.assertNotIn("{{table}}", sql)
            self.assertIn("DATE('2020-01-01')", sql)
            self.assertIn("DATE('2020-01-03')", sql)
            self.assertEqual(json.loads(path.read_text())[0]["utc_date"], "2020-01-01")

    def test_incremental_query_appends_only_new_dates_and_preserves_old_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_supply.json"
            original = [{"utc_date": "2020-01-01", "total_supply": 10}]
            path.write_text(json.dumps(original))
            client = Mock()
            client.query.return_value.result.return_value = [
                row("2020-01-02", 11), row("2020-01-02", 12), row("2020-01-03", 13)
            ]

            self.assertTrue(collect_daily_supply(path, client=client, today_utc=date(2020, 1, 4)))

            sql = client.query.call_args.args[0]
            self.assertIn("DATE('2020-01-02')", sql)
            records = json.loads(path.read_text())
            self.assertEqual([record["utc_date"] for record in records], [
                "2020-01-01", "2020-01-02", "2020-01-03"
            ])
            self.assertEqual(records[0], original[0])

    def test_up_to_date_does_not_create_client_or_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_supply.json"
            path.write_text(json.dumps([{"utc_date": "2020-01-02"}]))
            with patch("bigquery.bigquery.Client") as client_factory:
                self.assertTrue(collect_daily_supply(path, today_utc=date(2020, 1, 3)))
            client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
