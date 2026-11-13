import json
import tempfile
import sys
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import paths
import fetch as fetching
from sources import SOURCES, SourceName, raw_path
from fetch import fetch_json
from normalization.parsers.defillama.stablecoin_charts import parse_stablecoin_charts
from normalization.registry import NORMALIZED_DATA_DIR, PARSER_REGISTRATIONS


class StablecoinChartsTests(unittest.TestCase):
    def fixture(self):
        return [{
            "date": "1657411200",
            "totalCirculating": {"peggedUSD": 112838897, "peggedEUR": Decimal("12.5")},
            "totalCirculatingUSD": {"peggedUSD": Decimal("112827614.25"), "peggedEUR": "13.75"},
            "totalMintedUSD": {"peggedUSD": 115122052},
        }]

    def test_unix_seconds_convert_to_utc_date_and_preserve_timestamp(self):
        document = parse_stablecoin_charts(self.fixture())["daily_stablecoin_market_data.json"]
        observation = document["observations"][0]
        self.assertEqual(observation["date"], "2022-07-10")
        self.assertEqual(observation["timestamp"], 1657411200)
        self.assertIs(type(observation["timestamp"]), int)
        self.assertEqual(document["time"]["timezone"], "UTC")
        self.assertEqual(document["time"]["timestamp_unit"], "seconds")

    def test_preserves_all_peg_categories_as_exact_decimal_strings_and_excludes_minted(self):
        observation = parse_stablecoin_charts(self.fixture())[
            "daily_stablecoin_market_data.json"]["observations"][0]
        self.assertEqual(observation["total_circulating_by_peg"], {
            "peggedUSD": "112838897", "peggedEUR": "12.5",
        })
        self.assertEqual(observation["total_circulating_usd_by_peg"], {
            "peggedUSD": "112827614.25", "peggedEUR": "13.75",
        })
        self.assertNotIn("total_minted_usd", observation)
        self.assertEqual(type(observation["total_circulating_usd_by_peg"]["peggedUSD"]), str)

    def test_preserves_nulls_and_omits_missing_categories(self):
        data = [{
            "date": 0,
            "totalCirculating": None,
            "totalCirculatingUSD": {"peggedUSD": None, "peggedEUR": "1.25"},
        }]
        observation = parse_stablecoin_charts(data)[
            "daily_stablecoin_market_data.json"]["observations"][0]
        self.assertIsNone(observation["total_circulating_by_peg"])
        self.assertEqual(observation["total_circulating_usd_by_peg"], {
            "peggedUSD": None, "peggedEUR": "1.25",
        })
        missing = parse_stablecoin_charts([{"date": 0}])[
            "daily_stablecoin_market_data.json"]["observations"][0]
        self.assertNotIn("total_circulating_usd_by_peg", missing)

    def test_rejects_invalid_timestamps_malformed_values_and_categories(self):
        for timestamp in ("not-a-timestamp", 1657411200.5, True, None):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                parse_stablecoin_charts([{"date": timestamp}])
        with self.assertRaises(ValueError):
            parse_stablecoin_charts({"date": 0})
        with self.assertRaisesRegex(ValueError, "must be an object"):
            parse_stablecoin_charts([None])
        with self.assertRaisesRegex(ValueError, "missing date"):
            parse_stablecoin_charts([{"totalCirculating": {"peggedUSD": 1}}])
        with self.assertRaisesRegex(ValueError, "must be an object or null"):
            parse_stablecoin_charts([{"date": 0, "totalCirculating": "bad"}])
        with self.assertRaises(ValueError):
            parse_stablecoin_charts([{"date": 0, "totalCirculating": {"peggedUSD": float("nan")}}])

    def test_rejects_duplicate_dates_and_unsorted_observations(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_stablecoin_charts([{"date": 0}, {"date": 100}])
        with self.assertRaisesRegex(ValueError, "Unsorted"):
            parse_stablecoin_charts([{"date": 86400}, {"date": 0}])

    def test_parser_does_not_mutate_raw_input(self):
        raw = self.fixture()
        before = deepcopy(raw)
        parse_stablecoin_charts(raw)
        self.assertEqual(raw, before)

    def test_fetch_preserves_the_complete_raw_response_bytes(self):
        source = next(source for source in SOURCES if source.name == SourceName.NEAR_STABLECOIN_CHARTS)
        payload = b'[ {"date": 0, "totalCirculatingUSD": {"peggedUSD": 1}} ]\n'

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return payload

        with tempfile.TemporaryDirectory() as temp, \
                patch.object(paths, "RAW_DATA_DIR", Path(temp)), \
                patch.object(fetching, "urlopen", return_value=Response()):
            self.assertTrue(fetch_json(source))
            self.assertEqual(raw_path(source).read_bytes(), payload)

    def test_registration_uses_expected_raw_source_and_normalized_path(self):
        registrations = [entry for entry in PARSER_REGISTRATIONS
                         if entry.parser is parse_stablecoin_charts]
        self.assertEqual(len(registrations), 1)
        registration = registrations[0]
        self.assertEqual(registration.source, SourceName.NEAR_STABLECOIN_CHARTS)
        self.assertEqual(registration.normalized_directory,
                         NORMALIZED_DATA_DIR / "defillama" / "near_stablecoin")
        sources = [source for source in SOURCES if source.name == registration.source]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].url, "https://stablecoins.llama.fi/stablecoincharts/Near")
        self.assertEqual(raw_path(sources[0]),
                         Path("data/raw/defillama/near_stablecoin.json").resolve())


if __name__ == "__main__":
    unittest.main()
