import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analytics.protocols import CATEGORIES, _build_category


class ProtocolAnalyticsTests(unittest.TestCase):
    def test_ranked_protocols_are_written_to_separate_breakdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normalized_root = root / "normalized" / "defillama"
            source_dir = normalized_root / CATEGORIES["fees"]["directory"]
            source_dir.mkdir(parents=True)
            price_path = root / "normalized" / "binance" / "near_price" / "nearusdt_1d_close_price.json"
            price_path.parent.mkdir(parents=True)
            price_path.write_text(json.dumps({"observations": [{"date": "2025-01-01", "price": 5}]}))

            (source_dir / "daily_protocol_fees1.json").write_text(json.dumps({
                "metric": {"frequency": "daily", "unit": "USD"},
                "observations": [{"date": "2025-01-01", "value": 20}],
            }))
            (source_dir / "daily_protocol_fees_breakdown.json").write_text(json.dumps({
                "observations": [{"date": "2025-01-01", "values": {"Protocol A": 20}}],
            }))
            (source_dir / "summary.json").write_text(json.dumps({"values": {"total_30d": 20}}))
            (source_dir / "protocol_fees_ranking.json").write_text(json.dumps({
                "updated_at": "2025-01-02T00:00:00Z",
                "values": [{"name": "Protocol A", "id": "1", "total30d": 20}],
            }))

            outputs = _build_category(
                "fees", CATEGORIES["fees"], normalized_root, root / "analytics" / "protocols", {
                    date(2025, 1, 1): 5,
                },
            )
            snapshot = json.loads(outputs["snapshot"].read_text())
            breakdown = json.loads(outputs["protocol_breakdown"].read_text())

            self.assertNotIn("ranked_protocols", snapshot)
            self.assertEqual(breakdown["aggregation"], "ranked")
            self.assertEqual(breakdown["items"][0]["name"], "Protocol A")


if __name__ == "__main__":
    unittest.main()
