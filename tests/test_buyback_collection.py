import json
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from collectors.bigquery import BUYBACK_TRANSFERS_START, collect_buyback_transfers
from normalization.parsers.bigquery.buyback_transfers import parse_buyback_transfers


BUYBACK_QUERY_PATH = REPOSITORY_ROOT / "scripts" / "queries" / "buyback_transfers.sql"


def transfer_sources_from_query() -> dict[str, str]:
    sql = BUYBACK_QUERY_PATH.read_text(encoding="utf-8")
    pairs = re.findall(
        r"STRUCT\('([^']+)'\s+AS sender,\s*'([^']+)'\s+AS transfer_type\)",
        sql,
    )
    return {transfer_type: sender for sender, transfer_type in pairs}


class BuybackCollectionTests(unittest.TestCase):
    def test_query_owns_transfer_sender_mapping(self):
        sources = transfer_sources_from_query()
        self.assertTrue(sources)
        for sender in sources.values():
            self.assertIn(sender, BUYBACK_QUERY_PATH.read_text(encoding="utf-8"))

    def test_complete_data_through_yesterday_skips_bigquery_without_all_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "buyback_transfers.json"
            rows = [{
                "utc_date": day.isoformat(),
                "transfer_type": "type_currently_returned_by_query",
                "sender": "source.near",
                "native_inflow_near": "0",
                "wrapped_inflow_near": "0",
                "total_inflow_near": "0",
                "native_transfer_count": 0,
                "wrapped_transfer_count": 0,
                "total_transfer_count": 0,
            } for day in (BUYBACK_TRANSFERS_START, BUYBACK_TRANSFERS_START.replace(day=2))]
            path.write_text(json.dumps(rows), encoding="utf-8")

            with (
                patch("collectors.bigquery.bigquery.Client") as client_factory,
                patch("collectors.bigquery.dataset_up_to_date"),
            ):
                self.assertTrue(collect_buyback_transfers(
                    path,
                    today_utc=BUYBACK_TRANSFERS_START.replace(day=3),
                ))

            client_factory.assert_not_called()

    def test_query_starts_after_latest_raw_date_and_keeps_sparse_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "buyback_transfers.json"
            client = Mock()
            future_type = "new_transfer_type"
            client.query.return_value.result.return_value = [{
                "utc_date": date(2026, 11, 13),
                "sender": "new-source.near",
                "transfer_type": future_type,
                "native_inflow_near": "9401.5",
                "wrapped_inflow_near": "0",
                "total_inflow_near": "9401.5",
                "native_transfer_count": 23,
                "wrapped_transfer_count": 0,
                "total_transfer_count": 23,
            }]
            existing = [{
                "utc_date": f"2026-11-{day:02d}",
                "sender": "source.near",
                "transfer_type": "existing_source_type",
                "native_inflow_near": "0",
                "wrapped_inflow_near": "0",
                "total_inflow_near": "0",
                "native_transfer_count": 0,
                "wrapped_transfer_count": 0,
                "total_transfer_count": 0,
            } for day in range(1, 13)]
            path.write_text(json.dumps(existing), encoding="utf-8")

            with (
                patch("collectors.bigquery.request_started"),
                patch("collectors.bigquery.request_finished"),
            ):
                self.assertTrue(collect_buyback_transfers(
                    path, client=client, today_utc=date(2026, 11, 14),
                ))

            query = client.query.call_args.args[0]
            self.assertIn("DATE('2026-11-13')", query)
            self.assertIn("DATE('2026-11-14')", query)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved[-1]["utc_date"], "2026-11-13")
            self.assertEqual(len(saved), len(existing) + 1)
            normalized = parse_buyback_transfers(saved)
            self.assertEqual(
                normalized["daily_buyback_transfers.json"]["observations"][-1]["transfer_type"],
                future_type,
            )

    def test_empty_query_does_not_create_rows_or_a_separate_state_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "buyback_transfers.json"
            client = Mock()
            client.query.return_value.result.return_value = []

            with (
                patch("collectors.bigquery.request_started"),
                patch("collectors.bigquery.request_finished"),
            ):
                self.assertTrue(collect_buyback_transfers(
                    path, client=client, today_utc=BUYBACK_TRANSFERS_START + timedelta(days=1),
                ))

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])
            self.assertFalse(path.with_name("buyback_transfers_state.json").exists())


if __name__ == "__main__":
    unittest.main()
