"""Shared helpers for fetching and saving raw JSON responses."""

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atomic_io import atomic_write_bytes, atomic_write_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


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
    BINANCE_NEARUSDT_DAILY_KLINES = "binance_nearusdt_daily_klines"
    BIGQUERY_DAILY_SUPPLY = "bigquery_daily_supply"
    BIGQUERY_DAILY_GROSS_BURN = "bigquery_daily_gross_burn"
    BIGQUERY_DAILY_CONTRACT_REWARDS = "bigquery_daily_contract_rewards"


class SourceProvider(StrEnum):
    NEARBLOCKS = "NearBlocks"
    DEFILLAMA = "DefiLlama"
    BINANCE = "Binance"
    BIGQUERY = "Google BigQuery"


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
        name=SourceName.NEAR_BLOCKS,
        provider=SourceProvider.NEARBLOCKS,
        url="https://api.nearblocks.io/v3/address-stats",
        raw_filename="address_stats.json",
        raw_directory=Path("nearblocks"),
        dataset="Address Statistics",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_BLOCKS_NETWORK_STATS,
        provider=SourceProvider.NEARBLOCKS,
        url="https://api.nearblocks.io/v3/stats",
        raw_filename="stats.json",
        raw_directory=Path("nearblocks"),
        dataset="Network Statistics",
        frequency="snapshot",
    ),
    Source(
        name=SourceName.NEAR_TXN_STATS,
        provider=SourceProvider.NEARBLOCKS,
        url="https://api.nearblocks.io/v3/txn-stats",
        raw_filename="txn_stats.json",
        raw_directory=Path("nearblocks"),
        dataset="Transaction Statistics",
        frequency="daily",
    ),
    Source(
        name=SourceName.DEFILLAMA_CHAIN_TVL,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/v2/historicalChainTvl/Near",
        raw_filename="historical_chain_tvl.json",
        raw_directory=Path("defillama"),
        dataset="Historical Chain TVL",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_FEES,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/overview/fees/Near?dataType=dailyFees",
        raw_filename="near_fees.json",
        raw_directory=Path("defillama"),
        dataset="Fees Overview",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_REVENUE,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/overview/fees/Near?dataType=dailyRevenue",
        raw_filename="near_revenue.json",
        raw_directory=Path("defillama"),
        dataset="Revenue Overview",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_DEX_VOLUMES,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/overview/dexs/Near",
        raw_filename="near_dex_volumes.json",
        raw_directory=Path("defillama"),
        dataset="DEX Volume Overview",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_INTENTS_DEX_VOLUME,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/summary/dexs/near-intents",
        raw_filename="near_intents_dex_volume.json",
        raw_directory=Path("defillama"),
        dataset="NEAR Intents DEX Volume",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_INTENTS,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/protocol/near-intents",
        raw_filename="near_intents.json",
        raw_directory=Path("defillama"),
        dataset="NEAR Intents Protocol TVL",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_INTENTS_TOKEN_BREAKDOWN,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/v2/chart/tvl/protocol/near-intents/token-breakdown",
        raw_filename="near_intents_daily_tvl_by_token.json",
        raw_directory=Path("defillama"),
        dataset="NEAR Intents TVL by Token",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_HOLDERS_REVENUE,
        provider=SourceProvider.DEFILLAMA,
        url="https://api.llama.fi/overview/fees/Near?dataType=dailyHoldersRevenue",
        raw_filename="near_holders_revenue.json",
        raw_directory=Path("defillama"),
        dataset="Holders Revenue Overview",
        frequency="daily",
    ),
    Source(
        name=SourceName.NEAR_STABLECOIN_CHARTS,
        provider=SourceProvider.DEFILLAMA,
        url="https://stablecoins.llama.fi/stablecoincharts/Near",
        raw_filename="near_stablecoin.json",
        raw_directory=Path("defillama"),
        dataset="Stablecoin Charts",
        frequency="daily",
    ),
    Source(
        name=SourceName.BINANCE_NEARUSDT_DAILY_KLINES,
        provider=SourceProvider.BINANCE,
        url="https://data-api.binance.vision/api/v3/klines",
        raw_filename="near_price.json",
        raw_directory=Path("binance"),
        dataset="Spot Klines",
        frequency="daily",
    ),
    Source(
        name=SourceName.BIGQUERY_DAILY_SUPPLY,
        provider=SourceProvider.BIGQUERY,
        url=None,
        raw_filename="daily_supply.json",
        raw_directory=Path("bigquery"),
        dataset="Daily Supply",
        frequency="daily",
    ),
    Source(
        name=SourceName.BIGQUERY_DAILY_GROSS_BURN,
        provider=SourceProvider.BIGQUERY,
        url=None,
        raw_filename="daily_gross_burn.json",
        raw_directory=Path("bigquery"),
        dataset="Daily Gross Burn",
        frequency="daily",
    ),
    Source(
        name=SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS,
        provider=SourceProvider.BIGQUERY,
        url=None,
        raw_filename="daily_contract_rewards.json",
        raw_directory=Path("bigquery"),
        dataset="Daily Contract Rewards",
        frequency="daily",
    ),
)

SOURCES_BY_NAME = {source.name: source for source in SOURCES}
if len(SOURCES_BY_NAME) != len(SOURCES):
    raise ValueError("Each data source must have a unique name")


def get_source(name: SourceName) -> Source:
    """Return the canonical configuration for a registered data source."""
    try:
        return SOURCES_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"Unknown data source: {name}") from exc


def source_metadata(name: SourceName, **extra: object) -> dict[str, object]:
    """Build normalized source metadata from the canonical source definition."""
    source = get_source(name)
    metadata: dict[str, object] = {"provider": source.provider.value}
    if source.url is not None:
        metadata["endpoint"] = source.url
    metadata.update(extra)
    return metadata


def raw_path(source: Source) -> Path:
    return RAW_DATA_DIR / source.raw_directory / source.raw_filename


def nearblocks_api_key() -> str | None:
    """Return an optional NearBlocks key from the environment or project .env."""

    configured_key = os.environ.get("NEARBLOCKS_API_KEY", "").strip()
    if configured_key:
        return configured_key

    try:
        lines = (PROJECT_ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        name, separator, value = entry.partition("=")
        if not separator or name.strip() != "NEARBLOCKS_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            value = value.split("#", maxsplit=1)[0].strip()
        return value or None

    return None


def fetch_json(source: Source, timeout: int = 30) -> bool:
    """Fetch valid, non-empty JSON and save the exact response bytes."""

    try:
        headers = {"Accept": "application/json"}
        if source.provider is SourceProvider.NEARBLOCKS:
            headers["User-Agent"] = "NEARscope-Analytics/1.0"
            api_key = nearblocks_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        if source.url is None:
            raise ValueError(f"{source.name} does not have an HTTP endpoint")

        request = Request(
            source.url,
            method="GET",
            headers=headers,
        )

        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read()

        if not raw.strip():
            raise ValueError("Empty response")

        json.loads(raw)

        output = raw_path(source)
        atomic_write_bytes(output, raw)

        print(
            f"{source.name}: success "
            f"(HTTP {status}, {len(raw)} bytes) -> {output}"
        )
        return True

    except (
        HTTPError,
        HTTPException,
        URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        status = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else ""
        detail = f" ({status})" if status else ""

        print(f"{source.name}: failure{detail}: {exc}")
        return False


def fetch_binance_klines(source: Source, timeout: int = 30, today: date | None = None) -> bool:
    """Fetch NEARUSDT daily klines in bounded, resumable calendar chunks."""
    output = raw_path(source)
    current_day = today or datetime.now(timezone.utc).date()
    day_ms = 86_400_000
    initial_day = date(2021, 1, 1)

    try:
        if output.exists():
            records = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("Existing Binance raw data must be a list")
            timestamps = []
            for index, record in enumerate(records):
                if not isinstance(record, list) or len(record) != 12:
                    raise ValueError(f"Existing Binance record {index} is malformed")
                timestamp = record[0]
                if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                    raise ValueError(f"Existing Binance record {index} has an invalid open time")
                timestamps.append(timestamp)
            if timestamps != sorted(set(timestamps)):
                raise ValueError("Existing Binance records must be chronological and unique")
            latest_day = (datetime.fromtimestamp(timestamps[-1] / 1000, timezone.utc).date()
                          if timestamps else None)
            if latest_day is not None and latest_day >= current_day:
                print(f"{source.name}: already current through {latest_day}; no request needed")
                return True
            start_day = latest_day + timedelta(days=1) if latest_day else initial_day
        else:
            records = []
            start_day = initial_day
            atomic_write_text(output, "[]\n")

        by_timestamp = {record[0]: record for record in records}
        if source.url is None:
            raise ValueError(f"{source.name} does not have an HTTP endpoint")
        parts = urlsplit(source.url)
        while start_day <= current_day:
            end_day = min(start_day + timedelta(days=364), current_day)
            params = urlencode({
                "symbol": "NEARUSDT",
                "interval": "1d",
                "startTime": (start_day - date(1970, 1, 1)).days * day_ms,
                "endTime": (end_day - date(1970, 1, 1)).days * day_ms + day_ms - 1,
            })
            request_url = urlunsplit((parts.scheme, parts.netloc, parts.path, params, ""))
            request = Request(request_url, method="GET", headers={"Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                status = response.status
                payload = json.loads(response.read())
            if not isinstance(payload, list):
                raise ValueError("Binance Kline response must be a list")
            if not payload:
                break
            added = 0
            for index, record in enumerate(payload):
                if not isinstance(record, list) or len(record) != 12:
                    raise ValueError(f"Binance response record {index} is malformed")
                timestamp = record[0]
                if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                    raise ValueError(f"Binance response record {index} has an invalid open time")
                record_day = datetime.fromtimestamp(timestamp / 1000, timezone.utc).date()
                if start_day <= record_day <= end_day and timestamp not in by_timestamp:
                    by_timestamp[timestamp] = record
                    added += 1
            records = [by_timestamp[key] for key in sorted(by_timestamp)]
            atomic_write_text(output, json.dumps(records, separators=(",", ":")))
            print(f"{source.name}: fetched through {end_day} (HTTP {status}, {added} new days)")
            if added == 0:
                break
            latest_day = datetime.fromtimestamp(records[-1][0] / 1000, timezone.utc).date()
            if latest_day >= current_day:
                break
            start_day = end_day + timedelta(days=1)
        return True
    except (
        HTTPError, HTTPException, URLError, TimeoutError, OSError,
        json.JSONDecodeError, ValueError, OverflowError,
    ) as exc:
        status = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else ""
        detail = f" ({status})" if status else ""
        print(f"{source.name}: failure{detail}: {exc}")
        return False


def fetch_all(sources: tuple[Source, ...] = SOURCES) -> bool:
    """Attempt every configured source, isolating failures to that source."""

    all_succeeded = True
    for source in sources:
        try:
            if source.provider is SourceProvider.BIGQUERY:
                succeeded = fetch_bigquery(source)
            elif source.name == SourceName.BINANCE_NEARUSDT_DAILY_KLINES:
                succeeded = fetch_binance_klines(source)
            else:
                succeeded = fetch_json(source)
        except Exception as exc:
            print(f"{source.name}: failure: {type(exc).__name__}: {exc}")
            succeeded = False

        if not succeeded:
            all_succeeded = False

    return all_succeeded


def fetch_bigquery(source: Source) -> bool:
    """Collect a registered BigQuery dataset using its provider client."""

    try:
        from bigquery import (
            collect_daily_gross_burn,
            collect_daily_contract_rewards,
            collect_daily_supply,
        )

        collectors = {
            SourceName.BIGQUERY_DAILY_SUPPLY: collect_daily_supply,
            SourceName.BIGQUERY_DAILY_GROSS_BURN: collect_daily_gross_burn,
            SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS: collect_daily_contract_rewards,
        }
        return collectors[source.name](raw_path(source))
    except Exception as exc:
        print(f"{source.name}: failure: {exc}")
        return False
