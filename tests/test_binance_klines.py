import sys
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import SOURCES, SourceName, raw_path
from normalization.parsers.binance.daily_klines import (
    OUTPUT_FILENAME,
    parse_binance_nearusdt_daily_klines,
)
from normalization.registry import NORMALIZED_DATA_DIR, PARSER_REGISTRATIONS


def candle(open_time=1707696000000, *, close="3.38100000", open_value="3.12600000"):
    return [
        open_time,
        open_value,
        "3.40000000",
        "3.07400000",
        close,
        "29291296.60000000",
        open_time + 86399999,
        "94683494.15360000",
        182716,
        "15189946.40000000",
        "49178978.08710000",
        "0",
    ]


class BinanceKlineParserTests(unittest.TestCase):
    def test_maps_daily_close_and_utc_millisecond_times(self):
        document = parse_binance_nearusdt_daily_klines([candle()])[OUTPUT_FILENAME]
        observation = document["observations"][0]
        self.assertEqual(observation, {
            "date": "2024-02-12",
            "timestamp": 1707696000000,
            "price": "3.38100000",
        })
        self.assertEqual(set(observation), {"date", "timestamp", "price"})
        self.assertEqual(document["time"]["timezone"], "UTC")
        self.assertEqual(document["time"]["timestamp_unit"], "milliseconds")
        self.assertEqual(document["market"]["symbol"], "NEARUSDT")
        self.assertEqual(document["market"]["interval"], "1d")

    def test_preserves_decimal_strings_exactly(self):
        raw = candle(close="100000000000000000000.123456789")
        observation = parse_binance_nearusdt_daily_klines([raw])[OUTPUT_FILENAME]["observations"][0]
        self.assertEqual(observation["price"], "100000000000000000000.123456789")
        self.assertIsInstance(observation["price"], str)

    def test_rejects_malformed_rows_types_and_non_finite_decimals(self):
        with self.assertRaisesRegex(ValueError, "Expected a list"):
            parse_binance_nearusdt_daily_klines({})
        with self.assertRaisesRegex(ValueError, "exactly 12"):
            parse_binance_nearusdt_daily_klines([[0, "1"]])
        row = candle()
        row[0] = True
        with self.assertRaisesRegex(ValueError, "open_time must be an integer"):
            parse_binance_nearusdt_daily_klines([row])
        row = candle()
        row[4] = float("nan")
        with self.assertRaisesRegex(ValueError, "decimal string"):
            parse_binance_nearusdt_daily_klines([row])
        row = candle()
        row[4] = "Infinity"
        with self.assertRaisesRegex(ValueError, "finite"):
            parse_binance_nearusdt_daily_klines([row])

    def test_rejects_duplicate_dates_and_non_chronological_candles(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_binance_nearusdt_daily_klines([candle(), candle(1707696000000)])
        with self.assertRaisesRegex(ValueError, "not chronological"):
            parse_binance_nearusdt_daily_klines([candle(1707782400000), candle(1707696000000)])

    def test_parser_does_not_mutate_raw_input(self):
        raw = [candle(), candle(1707782400000)]
        before = deepcopy(raw)
        parse_binance_nearusdt_daily_klines(raw)
        self.assertEqual(raw, before)

    def test_parser_is_registered_to_the_existing_binance_source_and_output_path(self):
        matching = [item for item in PARSER_REGISTRATIONS
                    if item.parser is parse_binance_nearusdt_daily_klines]
        self.assertEqual(len(matching), 1)
        registration = matching[0]
        self.assertEqual(registration.source, SourceName.BINANCE_NEARUSDT_DAILY_KLINES)
        self.assertEqual(registration.normalized_directory, NORMALIZED_DATA_DIR / "binance" / "near_price")
        self.assertEqual(OUTPUT_FILENAME, "nearusdt_1d_close_price.json")

        sources = [source for source in SOURCES if source.name == registration.source]
        self.assertEqual(len(sources), 1)
        self.assertEqual(raw_path(sources[0]),
                         Path("data/raw/binance/near_price.json").resolve())


if __name__ == "__main__":
    unittest.main()
