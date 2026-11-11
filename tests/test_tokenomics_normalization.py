import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from normalization.parsers.nearblocks.network_stats import (
    parse_network_stats,
    parse_tokenomics_summary,
)
from normalization.units import yocto_near_to_near
from validation import validate_json


class YoctoNearConversionTests(unittest.TestCase):
    def test_exact_conversion_and_large_value(self):
        self.assertEqual(yocto_near_to_near("1000000000000000000000000"), "1")
        self.assertEqual(
            yocto_near_to_near("1311062886052171257973403355659208"),
            "1311062886.052171257973403355659208",
        )

    def test_small_fractional_burn(self):
        self.assertEqual(yocto_near_to_near("1"), "0.000000000000000000000001")

    def test_negative_supply_change_is_preserved(self):
        self.assertEqual(yocto_near_to_near("-1234567890123456789012345"), "-1.234567890123456789012345")

    def test_rejects_float_input(self):
        with self.assertRaises(TypeError):
            yocto_near_to_near(1.0)

    def test_json_validation_rejects_non_finite_values(self):
        with self.assertRaises(ValueError):
            validate_json({"value": float("nan")})

    def test_json_validation_returns_parseable_json_text(self):
        serialized = validate_json({"value": "exact"})
        self.assertEqual(json.loads(serialized), {"value": "exact"})

    def test_json_validation_preserves_decimal_as_number(self):
        serialized = validate_json({"value": Decimal("1234567890.123456789012345678")})
        self.assertEqual(json.loads(serialized, parse_float=Decimal)["value"],
                         Decimal("1234567890.123456789012345678"))

    def test_tokenomics_values_are_in_tokenomics_summary(self):
        raw = {"data": {
            "avg_block_time": "0.6", "tps": 1, "nodes_online": 2, "gas_price": "1",
            "total_supply": "1000000000000000000000001",
            "circulating_supply": "2000000000000000000000002",
            "daily_burn": "1",
            "net_supply_change": "-1",
            "change_24h": "-2.3338", "market_cap": "4829496201.00000000",
            "near_btc_price": "0.00004859", "near_price": "3.68000000",
            "volume_24h": "270690670.00000000",
        }}
        before = json.dumps(raw)
        blockchain = parse_network_stats(raw)["summary.json"]
        document = parse_tokenomics_summary(raw)["summary.json"]
        self.assertEqual(json.dumps(raw), before)
        self.assertEqual(set(blockchain["metrics"]), {
            "avg_block_time", "tps", "nodes_online", "gas_price",
        })
        self.assertEqual(set(document["metrics"]), {
            "total_supply", "circulating_supply", "daily_burn", "net_supply_change",
            "change_24h", "market_cap", "near_btc_price", "near_price", "volume_24h",
        })
        expected = {
            "total_supply": "1.000000000000000000000001",
            "circulating_supply": "2.000000000000000000000002",
            "daily_burn": "0.000000000000000000000001",
            "net_supply_change": "-0.000000000000000000000001",
        }
        for field, value in expected.items():
            self.assertEqual(document["metrics"][field]["unit"], "NEAR")
            self.assertEqual(document["metrics"][field]["value"], value)
            self.assertIsInstance(document["metrics"][field]["value"], str)
        self.assertEqual(document["metrics"]["near_price"]["value"], "3.68000000")


if __name__ == "__main__":
    unittest.main()
