import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from buybacks import BUYBACK_TRANSFER_SENDERS, BUYBACK_TRANSFER_TYPES
from collectors.bigquery import BUYBACK_TRANSFERS_START, collect_buyback_transfers


class BuybackCollectionTests(unittest.TestCase):
    def test_configured_backfill_start_is_april_first_2026(self):
        self.assertEqual(BUYBACK_TRANSFERS_START, date(2026, 4, 1))

    def test_complete_data_through_yesterday_skips_bigquery(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "buyback_transfers.json"
            rows = [
                {
                    "utc_date": day.isoformat(),
                    "transfer_type": transfer_type,
                    "sender": BUYBACK_TRANSFER_SENDERS[transfer_type],
                }
                for day in (date(2026, 4, 1), date(2026, 4, 2))
                for transfer_type in BUYBACK_TRANSFER_TYPES
            ]
            path.write_text(json.dumps(rows), encoding="utf-8")

            with patch("collectors.bigquery.bigquery.Client") as client_factory:
                self.assertTrue(collect_buyback_transfers(path, today_utc=date(2026, 4, 3)))

            client_factory.assert_not_called()

    def test_missing_data_queries_from_april_first_and_merges_all_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "buyback_transfers.json"
            client = Mock()
            client.query.return_value.result.return_value = [
                {
                    "utc_date": date(2026, 4, 1),
                    "sender": BUYBACK_TRANSFER_SENDERS[transfer_type],
                    "transfer_type": transfer_type,
                }
                for transfer_type in BUYBACK_TRANSFER_TYPES
            ]

            self.assertTrue(collect_buyback_transfers(
                path, client=client, today_utc=date(2026, 4, 2),
            ))

            query = client.query.call_args.args[0]
            self.assertIn("DATE('2026-04-01')", query)
            self.assertIn("DATE('2026-04-02')", query)
            for sender in BUYBACK_TRANSFER_SENDERS.values():
                self.assertIn(sender, query)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual({row["transfer_type"] for row in saved}, BUYBACK_TRANSFER_TYPES)


if __name__ == "__main__":
    unittest.main()
