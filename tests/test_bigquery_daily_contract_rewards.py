import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bigquery import collect_daily_contract_rewards
from common import SOURCES, SourceName, fetch_all, raw_path


class BigQueryDailyContractRewardsTests(unittest.TestCase):
    def test_source_is_registered_for_bigquery_fetching(self):
        sources = [
            source
            for source in SOURCES
            if source.name == SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS
        ]
        self.assertEqual(len(sources), 1)
        self.assertEqual(
            raw_path(sources[0]),
            Path("data/raw/bigquery/daily_contract_rewards.json").resolve(),
        )
        self.assertIn(
            SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS,
            {source.name for source in fetch_all.__defaults__[0]},
        )

    def test_missing_file_queries_from_start_date_and_writes_raw_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_contract_rewards.json"
            client = Mock()
            client.query.return_value.result.return_value = [
                {"utc_date": date(2020, 1, 1), "contract_rewards_near": 12.5}
            ]

            self.assertTrue(
                collect_daily_contract_rewards(
                    path, client=client, today_utc=date(2020, 1, 3)
                )
            )

            sql = client.query.call_args.args[0]
            self.assertIn(
                "`bigquery-public-data.crypto_near_mainnet_us.account_changes`", sql
            )
            self.assertIn("DATE('2020-01-01')", sql)
            self.assertIn("DATE('2020-01-03')", sql)
            self.assertNotIn("{{table}}", sql)
            self.assertEqual(
                json.loads(path.read_text())[0]["contract_rewards_near"], 12.5
            )

    def test_incremental_collection_starts_after_latest_existing_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_contract_rewards.json"
            original = [
                {"utc_date": "2020-01-02", "contract_rewards_near": 4.0},
                {"utc_date": "2020-01-01", "contract_rewards_near": 3.0},
            ]
            path.write_text(json.dumps(original))
            client = Mock()
            client.query.return_value.result.return_value = [
                {"utc_date": date(2020, 1, 2), "contract_rewards_near": 99.0},
                {"utc_date": date(2020, 1, 3), "contract_rewards_near": 5.0},
            ]

            self.assertTrue(
                collect_daily_contract_rewards(
                    path, client=client, today_utc=date(2020, 1, 4)
                )
            )

            sql = client.query.call_args.args[0]
            self.assertIn("DATE('2020-01-03')", sql)
            records = json.loads(path.read_text())
            self.assertEqual(
                [record["utc_date"] for record in records],
                ["2020-01-01", "2020-01-02", "2020-01-03"],
            )
            self.assertEqual(records[1]["contract_rewards_near"], 4.0)
            self.assertEqual(records[2]["contract_rewards_near"], 5.0)


if __name__ == "__main__":
    unittest.main()
