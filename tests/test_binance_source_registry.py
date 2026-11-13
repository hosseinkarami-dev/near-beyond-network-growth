import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sources import SOURCES, SourceName, raw_path
from fetch import fetch_all


class BinanceKlineSourceRegistryTests(unittest.TestCase):
    def test_single_registration_has_expected_request_and_raw_path(self):
        matching = [source for source in SOURCES
                    if source.name == SourceName.BINANCE_NEARUSDT_DAILY_KLINES]
        self.assertEqual(len(matching), 1)
        source = matching[0]

        self.assertEqual(
            source.url,
            "https://data-api.binance.vision/api/v3/klines",
        )
        self.assertEqual(
            parse_qs(urlsplit(source.url).query),
            {},
        )
        self.assertEqual(
            raw_path(source),
            Path("data/raw/binance/near_price.json").resolve(),
        )
        self.assertEqual(source.provider, "Binance")
        self.assertEqual(source.dataset, "Spot Klines")
        self.assertEqual(source.frequency, "daily")

    def test_default_fetch_workflow_includes_the_source_without_credentials(self):
        self.assertIn(SourceName.BINANCE_NEARUSDT_DAILY_KLINES,
                      {source.name for source in SOURCES})
        self.assertIn(SourceName.BINANCE_NEARUSDT_DAILY_KLINES,
                      {source.name for source in fetch_all.__defaults__[0]})


if __name__ == "__main__":
    unittest.main()
