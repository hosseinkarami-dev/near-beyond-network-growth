"""Normalize daily Binance Spot closing prices for NEARUSDT."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from common import SourceName, source_metadata

OUTPUT_FILENAME = "nearusdt_1d_close_price.json"


def _utc_date(timestamp_ms, index):
    try:
        return (datetime(1970, 1, 1, tzinfo=timezone.utc)
                + timedelta(milliseconds=timestamp_ms)).date().isoformat()
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"Candle {index} has out-of-range open time") from exc


def _price_string(value, index):
    if not isinstance(value, str):
        raise ValueError(f"Candle {index} closing price must be a decimal string")
    try:
        price = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Candle {index} has an invalid closing price") from exc
    if not price.is_finite():
        raise ValueError(f"Candle {index} closing price must be finite")
    return value


def parse_binance_nearusdt_daily_klines(raw_data):
    """Emit the UTC date, original open timestamp, and exact daily close price."""
    if not isinstance(raw_data, list):
        raise ValueError("Expected a list of Binance Kline records")

    observations = []
    seen_dates = set()
    previous_open_time = None

    for index, candle in enumerate(raw_data):
        if not isinstance(candle, list) or len(candle) != 12:
            raise ValueError(f"Candle {index} must contain exactly 12 positional fields")
        open_time = candle[0]
        if isinstance(open_time, bool) or not isinstance(open_time, int):
            raise ValueError(f"Candle {index} open_time must be an integer")

        date = _utc_date(open_time, index)
        if date in seen_dates:
            raise ValueError(f"Duplicate Kline UTC date: {date}")
        if previous_open_time is not None and open_time <= previous_open_time:
            raise ValueError(f"Kline records are not chronological at candle {index}")
        seen_dates.add(date)
        previous_open_time = open_time

        observations.append({
            "date": date,
            "timestamp": open_time,
            "price": _price_string(candle[4], index),
        })

    return {
        OUTPUT_FILENAME: {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.BINANCE_NEARUSDT_DAILY_KLINES,
                attribution="Binance public Spot market data",
            ),
            "market": {
                "type": "spot",
                "symbol": "NEARUSDT",
                "base_asset": "NEAR",
                "quote_asset": "USDT",
                "interval": "1d",
            },
            "metric": {
                "id": "binance.nearusdt.daily_close_price",
                "name": "NEARUSDT daily Spot closing price",
                "unit": "USDT",
                "frequency": "daily",
                "value_type": "decimal",
            },
            "time": {
                "timezone": "UTC",
                "timestamp_unit": "milliseconds",
                "timestamp_convention": "Kline open time",
            },
            "observations": observations,
        }
    }
