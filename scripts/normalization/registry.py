"""Parser registrations, kept separate from the fetch source registry."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from paths import NORMALIZED_DATA_DIR
from sources import SourceName
from normalization.parsers.binance.daily_klines import parse_binance_nearusdt_daily_klines
from normalization.parsers.bigquery.daily_flows import (
    parse_contract_reward_event_audit,
    parse_daily_gross_burn,
)
from normalization.parsers.bigquery.buyback_transfers import parse_buyback_transfers
from normalization.parsers.bigquery.daily_supply import parse_daily_supply
from normalization.parsers.defillama.dex_volumes import parse_dex_volumes
from normalization.parsers.defillama.fees_revenue import parse_fees, parse_revenue
from normalization.parsers.defillama.historical_chain_tvl import parse_historical_chain_tvl
from normalization.parsers.defillama.holders_revenue import parse_holders_revenue
from normalization.parsers.defillama.near_intents_token_breakdown import (
    parse_near_intents_token_breakdown,
)
from normalization.parsers.defillama.near_intents_tvl import parse_near_intents_tvl
from normalization.parsers.defillama.near_intents_volume import parse_near_intents_volume
from normalization.parsers.defillama.stablecoin_charts import parse_stablecoin_charts
from normalization.parsers.fastnear.validator_stake import parse_daily_active_validator_stake
from normalization.parsers.fastnear.buyback_balance import parse_buyback_wallet_balance
from normalization.parsers.nearblocks.address_stats import parse_address_statistics
from normalization.parsers.nearblocks.txn_stats import parse_txn_stats
from normalization.parsers.nearblocks.validators_info import parse_validators_info
from normalization.parsers.nearblocks.validators import parse_validators
from normalization.parsers.nearblocks.network_stats import (
    parse_network_stats,
    parse_tokenomics_summary,
)


@dataclass(frozen=True)
class ParserRegistration:
    source: SourceName
    parser: Callable
    normalized_directory: Path
    parse_float_as_decimal: bool = False
    raw_encoding: str = "utf-8"


PARSER_REGISTRATIONS = (
    ParserRegistration(
        source=SourceName.NEAR_BLOCKS,
        parser=parse_address_statistics,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "address_stats",
    ),
    ParserRegistration(
        source=SourceName.NEAR_TXN_STATS,
        parser=parse_txn_stats,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "txn_stats",
    ),
    ParserRegistration(
        source=SourceName.NEAR_BLOCKS_NETWORK_STATS,
        parser=parse_network_stats,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "stats" / "network",
    ),
    ParserRegistration(
        source=SourceName.NEAR_BLOCKS_NETWORK_STATS,
        parser=parse_tokenomics_summary,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "stats" / "tokenomics",
    ),
    ParserRegistration(
        source=SourceName.NEAR_BLOCKS_VALIDATORS_INFO,
        parser=parse_validators_info,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "validators",
        parse_float_as_decimal=True,
    ),
    ParserRegistration(
        source=SourceName.NEAR_BLOCKS_VALIDATORS,
        parser=parse_validators,
        normalized_directory=NORMALIZED_DATA_DIR / "nearblocks" / "validators",
        parse_float_as_decimal=True,
    ),
    ParserRegistration(
        source=SourceName.BIGQUERY_DAILY_SUPPLY,
        parser=parse_daily_supply,
        normalized_directory=NORMALIZED_DATA_DIR / "bigquery",
        parse_float_as_decimal=True,
    ),
    ParserRegistration(
        source=SourceName.BIGQUERY_DAILY_GROSS_BURN,
        parser=parse_daily_gross_burn,
        normalized_directory=NORMALIZED_DATA_DIR / "bigquery",
        parse_float_as_decimal=True,
    ),
    ParserRegistration(
        source=SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT,
        parser=parse_contract_reward_event_audit,
        normalized_directory=NORMALIZED_DATA_DIR / "bigquery",
        parse_float_as_decimal=True,
        raw_encoding="utf-8-sig",
    ),
    ParserRegistration(
        source=SourceName.BIGQUERY_BUYBACK_TRANSFERS,
        parser=parse_buyback_transfers,
        normalized_directory=NORMALIZED_DATA_DIR / "bigquery" / "buyback",
        parse_float_as_decimal=True,
        raw_encoding="utf-8-sig",
    ),
    ParserRegistration(
        source=SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE,
        parser=parse_daily_active_validator_stake,
        normalized_directory=NORMALIZED_DATA_DIR / "fastnear" / "validators",
    ),
    ParserRegistration(
        source=SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE,
        parser=parse_buyback_wallet_balance,
        normalized_directory=NORMALIZED_DATA_DIR / "fastnear" / "buyback",
        raw_encoding="utf-8-sig",
    ),
    ParserRegistration(
        source=SourceName.NEAR_STABLECOIN_CHARTS,
        parser=parse_stablecoin_charts,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_stablecoin",
        parse_float_as_decimal=True,
    ),
    ParserRegistration(
        source=SourceName.BINANCE_NEARUSDT_DAILY_KLINES,
        parser=parse_binance_nearusdt_daily_klines,
        normalized_directory=NORMALIZED_DATA_DIR / "binance" / "near_price",
    ),
    ParserRegistration(
        source=SourceName.DEFILLAMA_CHAIN_TVL,
        parser=parse_historical_chain_tvl,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "historical_chain_tvl",
    ),
    ParserRegistration(
        source=SourceName.NEAR_FEES,
        parser=parse_fees,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_fees",
    ),
    ParserRegistration(
        source=SourceName.NEAR_REVENUE,
        parser=parse_revenue,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_revenue",
    ),
    ParserRegistration(
        source=SourceName.NEAR_DEX_VOLUMES,
        parser=parse_dex_volumes,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_dex_volumes",
    ),
    ParserRegistration(
        source=SourceName.NEAR_INTENTS_DEX_VOLUME,
        parser=parse_near_intents_volume,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_intents_dex_volume",
    ),
    ParserRegistration(
        source=SourceName.NEAR_INTENTS,
        parser=parse_near_intents_tvl,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_intents",
    ),
    ParserRegistration(
        source=SourceName.NEAR_INTENTS_TOKEN_BREAKDOWN,
        parser=parse_near_intents_token_breakdown,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_intents_token_breakdown",
    ),
    ParserRegistration(
        source=SourceName.NEAR_HOLDERS_REVENUE,
        parser=parse_holders_revenue,
        normalized_directory=NORMALIZED_DATA_DIR / "defillama" / "near_holders_revenue",
    ),
)
