"""Registered raw data source definitions and path helpers."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import paths


class SourceName(StrEnum):
    NEAR_BLOCKS = "nearblocks"
    NEAR_TXN_STATS = "near_txn_stats"
    DEFILLAMA_CHAIN_TVL = "defillama_chain_tvl"
    NEAR_FEES = "near_fees"
    NEAR_REVENUE = "near_revenue"
    NEAR_DEX_VOLUMES = "near_dex_volumes"
    NEAR_INTENTS_DEX_VOLUME = "near_intents_dex_volume"
    NEAR_INTENTS = "near_intents"
    NEAR_INTENTS_TOKEN_BREAKDOWN = "near_intents_token_breakdown"
    NEAR_HOLDERS_REVENUE = "near_holders_revenue"
    NEAR_STABLECOIN_CHARTS = "near_stablecoin"
    NEAR_BLOCKS_NETWORK_STATS = "nearblocks_network_stats"
    NEAR_BLOCKS_VALIDATORS_INFO = "nearblocks_validators_info"
    NEAR_BLOCKS_VALIDATORS = "nearblocks_validators"
    BINANCE_NEARUSDT_DAILY_KLINES = "binance_nearusdt_daily_klines"
    BIGQUERY_DAILY_SUPPLY = "bigquery_daily_supply"
    BIGQUERY_DAILY_GROSS_BURN = "bigquery_daily_gross_burn"
    BIGQUERY_CONTRACT_REWARD_AUDIT = "bigquery_contract_reward_audit"
    BIGQUERY_BUYBACK_TRANSFERS = "bigquery_buyback_transfers"
    FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE = "fastnear_daily_active_validator_stake"
    FASTNEAR_BUYBACK_WALLET_BALANCE = "fastnear_buyback_wallet_balance"


class SourceProvider(StrEnum):
    NEARBLOCKS = "NearBlocks"
    DEFILLAMA = "DefiLlama"
    BINANCE = "Binance"
    BIGQUERY = "Google BigQuery"
    FASTNEAR_RPC = "FastNEAR archival RPC"


@dataclass(frozen=True)
class Source:
    name: SourceName
    provider: SourceProvider
    url: str | None
    raw_filename: str
    raw_directory: Path
    dataset: str
    frequency: str


SOURCES = (
    Source(
        SourceName.NEAR_BLOCKS, SourceProvider.NEARBLOCKS,
        "https://api.nearblocks.io/v3/address-stats", "address_stats.json",
        Path("nearblocks"), "Address Statistics", "daily",
    ),
    Source(
        SourceName.NEAR_BLOCKS_NETWORK_STATS, SourceProvider.NEARBLOCKS,
        "https://api.nearblocks.io/v3/stats", "stats.json", Path("nearblocks"),
        "Network Statistics", "snapshot",
    ),
    Source(
        SourceName.NEAR_BLOCKS_VALIDATORS_INFO, SourceProvider.NEARBLOCKS,
        "https://api.nearblocks.io/v3/validators/info", "validators_info.json",
        Path("nearblocks"), "Validator Staking Information", "snapshot",
    ),
    Source(
        SourceName.NEAR_BLOCKS_VALIDATORS, SourceProvider.NEARBLOCKS,
        "https://api.nearblocks.io/v3/validators", "validators.json",
        Path("nearblocks"), "Validators", "snapshot",
    ),
    Source(
        SourceName.NEAR_TXN_STATS, SourceProvider.NEARBLOCKS,
        "https://api.nearblocks.io/v3/txn-stats", "txn_stats.json",
        Path("nearblocks"), "Transaction Statistics", "daily",
    ),
    Source(
        SourceName.DEFILLAMA_CHAIN_TVL, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/v2/historicalChainTvl/Near", "historical_chain_tvl.json",
        Path("defillama"), "Historical Chain TVL", "daily",
    ),
    Source(
        SourceName.NEAR_FEES, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/overview/fees/Near?dataType=dailyFees", "near_fees.json",
        Path("defillama"), "Fees Overview", "daily",
    ),
    Source(
        SourceName.NEAR_REVENUE, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/overview/fees/Near?dataType=dailyRevenue", "near_revenue.json",
        Path("defillama"), "Revenue Overview", "daily",
    ),
    Source(
        SourceName.NEAR_DEX_VOLUMES, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/overview/dexs/Near", "near_dex_volumes.json",
        Path("defillama"), "DEX Volume Overview", "daily",
    ),
    Source(
        SourceName.NEAR_INTENTS_DEX_VOLUME, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/summary/dexs/near-intents", "near_intents_dex_volume.json",
        Path("defillama"), "NEAR Intents DEX Volume", "daily",
    ),
    Source(
        SourceName.NEAR_INTENTS, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/protocol/near-intents", "near_intents.json",
        Path("defillama"), "NEAR Intents Protocol TVL", "daily",
    ),
    Source(
        SourceName.NEAR_INTENTS_TOKEN_BREAKDOWN, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/v2/chart/tvl/protocol/near-intents/token-breakdown",
        "near_intents_daily_tvl_by_token.json", Path("defillama"),
        "NEAR Intents TVL by Token", "daily",
    ),
    Source(
        SourceName.NEAR_HOLDERS_REVENUE, SourceProvider.DEFILLAMA,
        "https://api.llama.fi/overview/fees/Near?dataType=dailyHoldersRevenue",
        "near_holders_revenue.json", Path("defillama"),
        "Holders Revenue Overview", "daily",
    ),
    Source(
        SourceName.NEAR_STABLECOIN_CHARTS, SourceProvider.DEFILLAMA,
        "https://stablecoins.llama.fi/stablecoincharts/Near", "near_stablecoin.json",
        Path("defillama"), "Stablecoin Charts", "daily",
    ),
    Source(
        SourceName.BINANCE_NEARUSDT_DAILY_KLINES, SourceProvider.BINANCE,
        "https://data-api.binance.vision/api/v3/klines", "near_price.json",
        Path("binance"), "Spot Klines", "daily",
    ),
    Source(
        SourceName.BIGQUERY_DAILY_SUPPLY, SourceProvider.BIGQUERY, None,
        "daily_supply.json", Path("bigquery"), "Daily Supply", "daily",
    ),
    Source(
        SourceName.BIGQUERY_DAILY_GROSS_BURN, SourceProvider.BIGQUERY, None,
        "daily_gross_burn.json", Path("bigquery"), "Daily Gross Burn", "daily",
    ),
    Source(
        SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT, SourceProvider.BIGQUERY, None,
        "contract_reward_event_audit.json", Path("bigquery"), "Contract Reward Event Audit", "one-time",
    ),
    Source(
        SourceName.BIGQUERY_BUYBACK_TRANSFERS, SourceProvider.BIGQUERY, None,
        "buyback_transfers.json", Path("bigquery"), "Buyback Transfers", "daily",
    ),
    Source(
        SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE, SourceProvider.FASTNEAR_RPC,
        "https://archival-rpc.mainnet.fastnear.com", "daily_active_validator_stake.json",
        Path("fastnear"), "Daily Active Validator Stake", "daily",
    ),
    Source(
        SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE, SourceProvider.FASTNEAR_RPC,
        "https://archival-rpc.mainnet.fastnear.com", "buyback_wallet_balance.json",
        Path("fastnear"), "Buyback Wallet Balance", "snapshot",
    ),
)

SOURCES_BY_NAME = {source.name: source for source in SOURCES}
if len(SOURCES_BY_NAME) != len(SOURCES):
    raise ValueError("Each data source must have a unique name")


def get_source(name: SourceName) -> Source:
    try:
        return SOURCES_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"Unknown data source: {name}") from exc


def source_metadata(name: SourceName, **extra: object) -> dict[str, object]:
    source = get_source(name)
    metadata: dict[str, object] = {"provider": source.provider.value}
    if source.url is not None:
        metadata["endpoint"] = source.url
    metadata.update(extra)
    return metadata


def raw_path(source: Source) -> Path:
    return paths.RAW_DATA_DIR / source.raw_directory / source.raw_filename
