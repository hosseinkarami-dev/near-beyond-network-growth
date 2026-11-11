"""Fixture-based P0 contracts for the registered normalization parsers."""

import sys
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from normalization.parsers.defillama.dex_volumes import parse_dex_volumes
from normalization.parsers.defillama.fees_revenue import parse_fees, parse_revenue
from normalization.parsers.defillama.historical_chain_tvl import parse_historical_chain_tvl
from normalization.parsers.defillama.holders_revenue import parse_holders_revenue
from normalization.parsers.defillama.near_intents_tvl import parse_near_intents_tvl
from normalization.parsers.defillama.near_intents_token_breakdown import (
    parse_near_intents_token_breakdown,
)
from normalization.parsers.defillama.near_intents_volume import parse_near_intents_volume
from normalization.parsers.defillama.stablecoin_charts import parse_stablecoin_charts
from normalization.parsers.binance.daily_klines import parse_binance_nearusdt_daily_klines
from normalization.parsers.nearblocks.address_stats import parse_address_statistics
from normalization.parsers.nearblocks.network_stats import (
    parse_network_stats,
    parse_tokenomics_summary,
)
from normalization.parsers.nearblocks.txn_stats import parse_txn_stats
from normalization.parsers.bigquery.daily_supply import parse_daily_supply
from normalization.parsers.bigquery.daily_flows import (
    parse_daily_contract_rewards,
    parse_daily_gross_burn,
)
from common import SOURCES, SourceName, raw_path
from normalization.registry import NORMALIZED_DATA_DIR, PARSER_REGISTRATIONS


def address_fixture():
    return {"data": [
        {"date": "1970-01-02", "new_contracts": 4, "active_contracts": 5,
         "active_accounts": 6},
    ]}


def txn_fixture():
    return {"data": [
        {"date": "1970-01-02", "txns": 20, "txn_fee": "0.000000000000000001"},
        {"date": "1970-01-01", "txns": 10, "txn_fee": "0.000000000000000002"},
    ]}


def stats_fixture():
    return {"data": {"avg_block_time": "0.5", "tps": 7,
                      "nodes_online": 3, "gas_price": "100"}}


def tokenomics_fixture():
    return {"data": {"total_supply": "1000000000000000000000001"}}


def daily_supply_fixture():
    return [{"utc_date": "2024-01-01", "total_supply": 1_000_000_000_000_000_000_000_000_000,
             "circulating_supply": 900_000_000_000_000_000_000_000_000}]


def tvl_chain_fixture():
    return [{"date": 86400, "tvl": 12.5}, {"date": 86399, "tvl": 10.0}]


def overview_fixture():
    return {
        "chain": "Near",
        "total30d": 4.5,
        "totalAllTime": 10,
        "change_30dover30d": 2,
        "totalDataChart": [[86400, 4.5], [86399, 3.0]],
        "totalDataChartBreakdown": [[86400, {"app": 4.5}]],
        "protocols": [{"name": "app", "id": "1", "slug": "app",
                       "category": "DEX", "total30d": 4.5, "totalAllTime": 10}],
    }


def dex_fixture():
    return {
        "chain": "Near", "total24h": 7.5, "totalDataChart": [[86400, 7.5], [86399, 6]],
        "totalDataChartBreakdown": [[86400, {"app": 7.5}]],
        "protocols": [{"name": "app", "id": "1", "total30d": 5}],
    }


def intents_volume_fixture():
    return {
        "name": "NEAR Intents", "chain": "Near", "total24h": 9,
        "totalDataChart": [[86400, 9], [86399, 8]],
        "totalDataChartBreakdown": [[86400, {"Near": 9}]],
    }


def intents_tvl_fixture():
    return {
        "name": "NEAR Intents",
        "tvl": [{"date": 172800, "totalLiquidityUSD": 20},
                {"date": 86400, "totalLiquidityUSD": 10}],
        "tokensInUsd": [{"date": 86400, "tokens": {"NEAR": 10}}],
        "tokens": [{"date": 86400, "tokens": {"NEAR": "2.5"}}],
        "currentChainTvls": {"Near": 10},
        "chainTvls": {"Near": {"tvl": [{"date": 86400, "totalLiquidityUSD": 10}]}},
    }


def intents_token_tvl_fixture():
    return [
        [172800, {"NEAR": 15.25, "USDC": 5}],
        [86400, {"NEAR": 10, "USDC": 3.5}],
    ]


def holders_fixture():
    return {
        "chain": "Near", "total30d": None,
        "totalDataChart": [[86400, 3.5], [86399, 2.5]],
        "totalDataChartBreakdown": [[86400, {"app": 3.5}]],
        "protocols": [{"name": "app", "total30d": 3.5}],
    }


def stablecoin_fixture():
    return [{
        "date": "0",
        "totalCirculating": {"peggedUSD": 1},
        "totalCirculatingUSD": {"peggedUSD": 1},
        "totalMintedUSD": {"peggedUSD": 1},
    }]


def binance_kline_fixture():
    return [[1707696000000, "3.12600000", "3.40000000", "3.07400000",
             "3.38100000", "29291296.60000000", 1707782399999,
             "94683494.15360000", 182716, "15189946.40000000",
             "49178978.08710000", "0"]]


class RegisteredParserContractTests(unittest.TestCase):
    def test_holders_revenue_registration_is_separate_from_protocol_revenue(self):
        registration = next(entry for entry in PARSER_REGISTRATIONS
                            if entry.parser is parse_holders_revenue)
        self.assertEqual(registration.normalized_directory,
                         NORMALIZED_DATA_DIR / "defillama" / "near_holders_revenue")

    def test_near_intents_token_tvl_uses_flat_raw_file_and_normalized_directory(self):
        registration = next(
            entry for entry in PARSER_REGISTRATIONS
            if entry.parser is parse_near_intents_token_breakdown
        )
        source = next(source for source in SOURCES if source.name == registration.source)
        self.assertEqual(source.name, SourceName.NEAR_INTENTS_TOKEN_BREAKDOWN)
        self.assertEqual(source.raw_directory, Path("defillama"))
        self.assertEqual(source.raw_filename, "near_intents_daily_tvl_by_token.json")
        self.assertEqual(
            raw_path(source),
            Path("data/raw/defillama/near_intents_daily_tvl_by_token.json").resolve(),
        )
        self.assertEqual(
            registration.normalized_directory,
            NORMALIZED_DATA_DIR / "defillama" / "near_intents_token_breakdown",
        )
        self.assertEqual(
            set(parse_near_intents_token_breakdown(intents_token_tvl_fixture())),
            {"daily_tvl_by_token.json"},
        )

    def test_all_registered_parsers_have_fixture_output_contracts(self):
        fixtures = {
            parse_address_statistics: (address_fixture(), {"new_contracts.json", "active_contracts.json",
                                                            "active_accounts.json"}),
            parse_txn_stats: (txn_fixture(), {"daily_transactions.json", "daily_transaction_fees.json"}),
            parse_network_stats: (stats_fixture(), {"summary.json"}),
            parse_tokenomics_summary: (tokenomics_fixture(), {"summary.json"}),
            parse_daily_supply: (daily_supply_fixture(), {"daily_supply.json"}),
            parse_daily_gross_burn: ([{"utc_date": "2024-01-01",
                                      "gross_tokens_burnt_near": Decimal("0.25")}],
                                     {"daily_gross_burn.json"}),
            parse_daily_contract_rewards: ([{"utc_date": "2024-01-01",
                                             "contract_rewards_near": Decimal("0.5")}],
                                           {"daily_contract_rewards.json"}),
            parse_historical_chain_tvl: (tvl_chain_fixture(), {"tvl_usd.json"}),
            parse_fees: (overview_fixture(), {"summary.json", "daily_protocol_fees1.json",
                                               "daily_protocol_fees_breakdown.json",
                                               "protocol_fees_ranking.json"}),
            parse_revenue: (overview_fixture(), {"summary.json", "daily_protocol_revenue.json",
                                                  "daily_protocol_revenue_breakdown.json"}),
            parse_dex_volumes: (dex_fixture(), {"summary.json", "daily_tracked_protocol_dex_volume.json",
                                                "daily_tracked_protocol_dex_volume_breakdown.json",
                                                "protocol_dex_volume_ranking.json"}),
            parse_near_intents_volume: (intents_volume_fixture(), {"summary.json", "daily_volume.json"}),
            parse_near_intents_token_breakdown: (
                intents_token_tvl_fixture(), {"daily_tvl_by_token.json"},
            ),
            parse_near_intents_tvl: (intents_tvl_fixture(), {"intents_tvl.json", "daily_intents_tvl.json",
                                                              "tvl_by_chain.json"}),
            parse_holders_revenue: (holders_fixture(), {"ecosystem_holders_revenue.json",
                                                         "daily_holders_revenue.json",
                                                         "daily_holders_revenue_breakdown.json"}),
            parse_stablecoin_charts: (stablecoin_fixture(),
                                      {"daily_stablecoin_market_data.json"}),
            parse_binance_nearusdt_daily_klines: (binance_kline_fixture(),
                                                   {"nearusdt_1d_close_price.json"}),
        }
        self.assertEqual(len(PARSER_REGISTRATIONS), 17)
        self.assertEqual({registration.parser for registration in PARSER_REGISTRATIONS}, set(fixtures))
        for registration in PARSER_REGISTRATIONS:
            raw, expected_names = fixtures[registration.parser]
            with self.subTest(parser=registration.parser.__name__, output=registration.normalized_directory.name):
                output = registration.parser(deepcopy(raw))
                self.assertEqual(set(output), expected_names)


    def test_representative_raw_field_mappings_and_metadata(self):
        address = parse_address_statistics(address_fixture())
        self.assertEqual(address["active_accounts.json"]["observations"][0]["value"], 6)
        self.assertEqual(address["new_contracts.json"]["metric"]["source_metric"], "new_contracts")

        txns = parse_txn_stats(txn_fixture())
        self.assertEqual(txns["daily_transactions.json"]["observations"][0]["value"], 10)
        self.assertEqual(txns["daily_transactions.json"]["observations"][1]["value"], 20)
        self.assertEqual(txns["daily_transaction_fees.json"]["observations"][0]["value"],
                         "0.000000000000000002")
        self.assertEqual(txns["daily_transaction_fees.json"]["metric"]["unit"], "NEAR")

        stats = parse_network_stats(stats_fixture())["summary.json"]
        self.assertEqual(stats["metrics"]["avg_block_time"]["value"], "0.5")
        self.assertEqual(set(stats["metrics"]), set(stats_fixture()["data"]))
        self.assertEqual(stats["frequency"], "snapshot")

        supply = parse_tokenomics_summary(tokenomics_fixture())["summary.json"]["metrics"]
        self.assertEqual(supply["total_supply"]["value"], "1.000000000000000000000001")
        self.assertEqual(supply["total_supply"]["unit"], "NEAR")
        self.assertEqual(set(supply), {"total_supply"})

        daily_supply = parse_daily_supply(daily_supply_fixture())["daily_supply.json"]
        self.assertEqual(daily_supply["observations"][0]["total_supply"], "1000")
        self.assertEqual(daily_supply["observations"][0]["circulating_supply"], "900")
        self.assertEqual(daily_supply["metric"]["aggregation"], "period_end_snapshot")

        tvl = parse_historical_chain_tvl(tvl_chain_fixture())["tvl_usd.json"]
        self.assertEqual(tvl["observations"][0]["value"], 12.5)
        self.assertEqual(tvl["observations"][0]["timestamp"], 86400000)
        self.assertEqual(tvl["metric"]["aggregation"], "period_end_snapshot")

        fees = parse_fees(overview_fixture())
        self.assertEqual(fees["summary.json"]["values"]["total_30d"], 4.5)
        self.assertEqual(fees["daily_protocol_fees1.json"]["observations"][0]["timestamp"], 86400000)
        self.assertEqual(fees["protocol_fees_ranking.json"]["values"][0]["id"], "1")

        revenue = parse_revenue(overview_fixture())
        self.assertEqual(revenue["summary.json"]["values"]["growth_30d"], 2)
        self.assertEqual(revenue["daily_protocol_revenue_breakdown.json"]["observations"][0]["values"],
                         {"app": 4.5})

        dex = parse_dex_volumes(dex_fixture())
        self.assertEqual(dex["summary.json"]["values"]["total_24h"], 7.5)
        self.assertEqual(dex["daily_tracked_protocol_dex_volume.json"]["observations"][0]["timestamp"], 86400)
        self.assertEqual(dex["protocol_dex_volume_ranking.json"]["values"][0]["total_30d"], 5)

        volume = parse_near_intents_volume(intents_volume_fixture())
        self.assertEqual(volume["summary.json"]["values"]["total_24h"], 9)

        intents_tvl = parse_near_intents_tvl(intents_tvl_fixture())
        chain_tvl = intents_tvl["tvl_by_chain.json"]
        self.assertEqual(chain_tvl["date"], "1970-01-03")
        self.assertEqual(chain_tvl["items"], [{"chain": "Near", "tvl_usd": 10}])
        self.assertNotIn("protocol", intents_tvl["intents_tvl.json"])

        holders = parse_holders_revenue(holders_fixture())
        self.assertIsNone(holders["ecosystem_holders_revenue.json"]["summary"]["total30d"])
        self.assertEqual(holders["daily_holders_revenue.json"]["timestamp_unit"], "unix_seconds")
        self.assertEqual(
            holders["daily_holders_revenue_breakdown.json"]["observations"][0]["protocols"],
            {"app": 3.5},
        )

    def test_required_missing_and_null_field_contracts(self):
        with self.assertRaises((KeyError, TypeError)):
            parse_address_statistics({"data": [{"new_contracts": 1}]})
        address_null = address_fixture()
        address_null["data"][0]["active_accounts"] = None
        self.assertIsNone(parse_address_statistics(address_null)["active_accounts.json"]["observations"][0]["value"])

        with self.assertRaises(ValueError):
            parse_txn_stats({"data": [{"date": "1970-01-01", "txns": 1}]})
        txn_null = {"data": [{"date": "1970-01-01", "txns": None, "txn_fee": None}]}
        self.assertIsNone(parse_txn_stats(txn_null)["daily_transactions.json"]["observations"][0]["value"])
        self.assertIsNone(parse_txn_stats(txn_null)["daily_transaction_fees.json"]["observations"][0]["value"])

        missing_stats = stats_fixture()
        del missing_stats["data"]["tps"]
        self.assertNotIn("tps", parse_network_stats(missing_stats)["summary.json"]["metrics"])
        null_stats = stats_fixture()
        null_stats["data"]["tps"] = None
        self.assertIsNone(parse_network_stats(null_stats)["summary.json"]["metrics"]["tps"]["value"])

        no_supply = parse_tokenomics_summary(stats_fixture())["summary.json"]
        self.assertEqual(no_supply["metrics"], {})
        with self.assertRaises(TypeError):
            parse_tokenomics_summary({"data": {"total_supply": None}})

        with self.assertRaises((KeyError, TypeError)):
            parse_historical_chain_tvl([{"date": 86400}])
        self.assertIsNone(parse_historical_chain_tvl([{"date": 86400, "tvl": None}])
                          ["tvl_usd.json"]["observations"][0]["value"])

        missing_overview = overview_fixture()
        del missing_overview["protocols"]
        with self.assertRaises(ValueError):
            parse_fees(missing_overview)
        null_overview = overview_fixture()
        null_overview["total30d"] = None
        self.assertIsNone(parse_fees(null_overview)["summary.json"]["values"]["total_30d"])
        self.assertIsNone(parse_revenue(null_overview)["summary.json"]["values"]["total_30d"])

        with self.assertRaises(ValueError):
            parse_dex_volumes({"chain": "Other"})
        null_dex = dex_fixture()
        null_dex["total24h"] = None
        self.assertIsNone(parse_dex_volumes(null_dex)["summary.json"]["values"]["total_24h"])

        with self.assertRaises(ValueError):
            parse_near_intents_volume({"name": "wrong", "chain": "Near"})
        null_intents = intents_volume_fixture()
        null_intents["total24h"] = None
        self.assertIsNone(parse_near_intents_volume(null_intents)["summary.json"]["values"]["total_24h"])

        with self.assertRaises(ValueError):
            parse_near_intents_tvl({"name": "wrong"})
        null_tvl = {"name": "NEAR Intents", "tvl": [{"date": 86400, "totalLiquidityUSD": None}]}
        self.assertIsNone(parse_near_intents_tvl(null_tvl)["intents_tvl.json"]["current_tvl"])

        with self.assertRaises(ValueError):
            parse_holders_revenue({"chain": None})
        null_holders = {"chain": "Near", "total30d": None}
        self.assertIsNone(parse_holders_revenue(null_holders)
                          ["ecosystem_holders_revenue.json"]["summary"]["total30d"])

    def test_malformed_roots_and_rows_raise(self):
        malformed = (
            (parse_address_statistics, {"data": ["not-a-row"]}),
            (parse_txn_stats, {"data": [None]}),
            (parse_network_stats, []),
            (parse_tokenomics_summary, []),
            (parse_historical_chain_tvl, [{"date": "bad", "tvl": 1}]),
            (parse_fees, {"totalDataChart": [[1]], "protocols": []}),
            (parse_revenue, {"totalDataChart": [[1]], "protocols": []}),
            (parse_dex_volumes, {"chain": "Near", "totalDataChart": [[1]]}),
            (parse_near_intents_volume, {"name": "NEAR Intents", "chain": "Near",
                                         "totalDataChart": [[1]]}),
            (parse_near_intents_tvl, {"name": "NEAR Intents", "tvl": [{}]}),
            (parse_near_intents_token_breakdown, [[True, {"NEAR": 1}]]),
            (parse_near_intents_token_breakdown, [[86400, {"NEAR": float("nan")}]]),
            (parse_holders_revenue, {"chain": "Near", "totalDataChart": [[1]]}),
        )
        for parser, raw in malformed:
            with self.subTest(parser=parser.__name__):
                with self.assertRaises((KeyError, TypeError, ValueError, OverflowError, OSError)):
                    parser(raw)


class TimestampAndUtcTests(unittest.TestCase):
    def test_utc_boundaries_and_output_timestamp_units(self):
        address = parse_address_statistics(address_fixture())["active_accounts.json"]
        self.assertEqual(address["observations"][0]["timestamp"], 86400000)
        self.assertEqual(address["observations"][0]["date"], "1970-01-02")
        self.assertEqual(address["time"]["timezone"], "UTC")

        txns = parse_txn_stats(txn_fixture())["daily_transactions.json"]
        self.assertEqual([row["timestamp"] for row in txns["observations"]], [0, 86400000])
        self.assertEqual([row["date"] for row in txns["observations"]], ["1970-01-01", "1970-01-02"])
        self.assertEqual(txns["time"]["timestamp_unit"], "milliseconds")

        chain = parse_historical_chain_tvl(tvl_chain_fixture())["tvl_usd.json"]["observations"]
        self.assertEqual(chain[0]["timestamp"], 86400000)
        self.assertEqual(chain[0]["date"], "1970-01-02")
        self.assertEqual(chain[1]["date"], "1970-01-01")

        fees = parse_fees(overview_fixture())["daily_protocol_fees1.json"]["observations"]
        self.assertEqual((fees[0]["timestamp"], fees[0]["date"]), (86400000, "1970-01-02"))
        self.assertEqual((fees[1]["timestamp"], fees[1]["date"]), (86399000, "1970-01-01"))

        dex = parse_dex_volumes(dex_fixture())["daily_tracked_protocol_dex_volume.json"]["observations"]
        self.assertEqual((dex[0]["timestamp"], dex[0]["date"]), (86400, "1970-01-02"))

        volume = parse_near_intents_volume(intents_volume_fixture())["daily_volume.json"]["observations"]
        self.assertEqual((volume[0]["timestamp"], volume[0]["date"]), (86400, "1970-01-02"))

        token_tvl = parse_near_intents_token_breakdown(
            intents_token_tvl_fixture(),
        )["daily_tvl_by_token.json"]
        self.assertEqual(
            [(row["timestamp"], row["date"]) for row in token_tvl["observations"]],
            [(86400000, "1970-01-02"), (172800000, "1970-01-03")],
        )
        self.assertEqual(token_tvl["time"]["timestamp_unit"], "milliseconds")

        tvl = parse_near_intents_tvl(intents_tvl_fixture())
        self.assertEqual((tvl["daily_intents_tvl.json"]["observations"][0]["timestamp"],
                          tvl["daily_intents_tvl.json"]["observations"][0]["date"]),
                         (172800, "1970-01-03"))

        holders = parse_holders_revenue(holders_fixture())["daily_holders_revenue.json"]
        self.assertEqual((holders["observations"][0]["timestamp"], holders["observations"][0]["date"]),
                         (86400, "1970-01-02"))
        self.assertEqual(holders["timestamp_unit"], "unix_seconds")

    def test_snapshot_selection_uses_greatest_source_timestamp(self):
        raw = intents_tvl_fixture()
        output = parse_near_intents_tvl(raw)
        snapshot = output["intents_tvl.json"]
        self.assertEqual(snapshot["current_timestamp"], 172800)
        self.assertEqual(snapshot["current_date"], "1970-01-03")
        self.assertEqual(snapshot["current_tvl"], 20)

    def test_duplicate_dates_or_timestamps_are_rejected_where_defined(self):
        duplicate_addresses = {"data": [
            {"date": "1970-01-01", "new_contracts": 1, "active_contracts": 1,
             "active_accounts": 1},
            {"date": "1970-01-01", "new_contracts": 2, "active_contracts": 2,
             "active_accounts": 2},
        ]}
        with self.assertRaises(ValueError):
            parse_address_statistics(duplicate_addresses)

        duplicate_txns = {"data": [
            {"date": "1970-01-01", "txns": 1, "txn_fee": "1"},
            {"date": "1970-01-01", "txns": 2, "txn_fee": "2"},
        ]}
        with self.assertRaises(ValueError):
            parse_txn_stats(duplicate_txns)

        with self.assertRaises(ValueError):
            parse_historical_chain_tvl([{"date": 86400, "tvl": 1}, {"date": 86400, "tvl": 2}])

        duplicate_fees = overview_fixture()
        duplicate_fees["totalDataChart"] = [[86400, 1], [86400, 2]]
        with self.assertRaises(ValueError):
            parse_fees(duplicate_fees)

        duplicate_dex = dex_fixture()
        duplicate_dex["totalDataChart"] = [[86400, 1], [86400, 2]]
        with self.assertRaises(ValueError):
            parse_dex_volumes(duplicate_dex)

        duplicate_volume = intents_volume_fixture()
        duplicate_volume["totalDataChart"] = [[86400, 1], [86400, 2]]
        with self.assertRaises(ValueError):
            parse_near_intents_volume(duplicate_volume)

        with self.assertRaisesRegex(ValueError, "Duplicate token TVL timestamp"):
            parse_near_intents_token_breakdown([[86400, {}], [86400, {}]])

        duplicate_tvl = {"name": "NEAR Intents", "tvl": [
            {"date": 86400, "totalLiquidityUSD": 1},
            {"date": 86400, "totalLiquidityUSD": 2},
        ]}
        with self.assertRaises(ValueError):
            parse_near_intents_tvl(duplicate_tvl)

        duplicate_holders = {"chain": "Near", "totalDataChart": [[86400, 1], [86400, 2]]}
        with self.assertRaises(ValueError):
            parse_holders_revenue(duplicate_holders)

    def test_invalid_and_nanosecond_scale_timestamps_are_rejected(self):
        invalid_date = {"data": [{"date": "2023-02-30", "txns": 1, "txn_fee": "1"}]}
        with self.assertRaises(ValueError):
            parse_txn_stats(invalid_date)

        invalid_rows = [
            (parse_historical_chain_tvl, [{"date": "not-an-epoch", "tvl": 1}]),
            (parse_fees, {**overview_fixture(), "totalDataChart": [["bad", 1]]}),
            (parse_dex_volumes, {**dex_fixture(), "totalDataChart": [["bad", 1]]}),
            (parse_near_intents_volume, {**intents_volume_fixture(), "totalDataChart": [["bad", 1]]}),
            (parse_near_intents_tvl, {"name": "NEAR Intents", "tvl": [{"date": "bad", "totalLiquidityUSD": 1}]}),
            (parse_holders_revenue, {"chain": "Near", "totalDataChart": [["bad", 1]]}),
        ]
        for parser, raw in invalid_rows:
            with self.subTest(parser=parser.__name__):
                with self.assertRaises((TypeError, ValueError, OverflowError, OSError)):
                    parser(raw)

        nanoseconds = 1_700_000_000_000_000_000
        for parser, raw in (
            (parse_historical_chain_tvl, [{"date": nanoseconds, "tvl": 1}]),
            (parse_fees, {**overview_fixture(), "totalDataChart": [[nanoseconds, 1]]}),
            (parse_dex_volumes, {**dex_fixture(), "totalDataChart": [[nanoseconds, 1]]}),
            (parse_near_intents_volume, {**intents_volume_fixture(), "totalDataChart": [[nanoseconds, 1]]}),
            (parse_near_intents_tvl, {"name": "NEAR Intents", "tvl": [{"date": nanoseconds, "totalLiquidityUSD": 1}]}),
            (parse_holders_revenue, {"chain": "Near", "totalDataChart": [[nanoseconds, 1]]}),
        ):
            with self.subTest(parser=parser.__name__, unit="nanoseconds"):
                with self.assertRaises((TypeError, ValueError, OverflowError, OSError)):
                    parser(raw)


if __name__ == "__main__":
    unittest.main()
