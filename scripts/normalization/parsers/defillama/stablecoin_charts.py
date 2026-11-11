"""Normalize DefiLlama's NEAR stablecoin market chart."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from common import SourceName, get_source, source_metadata


VALUE_FIELDS = (
    ("totalCirculating", "total_circulating_by_peg"),
    ("totalCirculatingUSD", "total_circulating_usd_by_peg"),
)


def _timestamp(value, index):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"Record {index} date must be an integer Unix timestamp in seconds")
    try:
        timestamp = int(value)
    except ValueError as exc:
        raise ValueError(f"Record {index} date is not an integer Unix timestamp") from exc
    if isinstance(value, str) and str(timestamp) != value:
        raise ValueError(f"Record {index} date must be a canonical integer string")
    try:
        day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError(f"Record {index} date is outside the supported timestamp range") from exc
    return timestamp, day


def _decimal_string(value, index, field):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"Record {index} {field} must not be a float or boolean")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Record {index} {field} must be a decimal value or null") from exc
    if not number.is_finite():
        raise ValueError(f"Record {index} {field} must be finite")
    return format(number, "f")


def parse_stablecoin_charts(raw_data):
    """Preserve circulating quantities by peg without including minted supply."""
    if not isinstance(raw_data, list):
        raise ValueError("Expected a list of stablecoin chart records")

    observations = []
    seen_dates = set()
    previous_timestamp = None

    for index, row in enumerate(raw_data):
        if not isinstance(row, dict):
            raise ValueError(f"Record {index} must be an object")
        if "date" not in row:
            raise ValueError(f"Record {index} is missing date")
        timestamp, day = _timestamp(row["date"], index)
        if day in seen_dates:
            raise ValueError(f"Duplicate stablecoin observation date: {day}")
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise ValueError(f"Unsorted stablecoin observation at record {index}: {day}")
        seen_dates.add(day)
        previous_timestamp = timestamp

        observation = {"date": day, "timestamp": timestamp}
        for raw_field, normalized_field in VALUE_FIELDS:
            if raw_field not in row:
                continue
            nested = row[raw_field]
            if nested is None:
                observation[normalized_field] = None
                continue
            if not isinstance(nested, dict):
                raise ValueError(f"Record {index} {raw_field} must be an object or null")
            categories = {}
            for category, value in nested.items():
                if not isinstance(category, str) or not category:
                    raise ValueError(f"Record {index} {raw_field} contains an invalid peg category")
                categories[category] = (
                    None if value is None else _decimal_string(value, index, raw_field)
                )
            observation[normalized_field] = categories
        observations.append(observation)

    return {
        "daily_stablecoin_market_data.json": {
            "schema_version": "1.0.0",
            "network": "NEAR",
            "source": source_metadata(
                SourceName.NEAR_STABLECOIN_CHARTS,
                attribution="DefiLlama",
                dataset=get_source(SourceName.NEAR_STABLECOIN_CHARTS).dataset,
            ),
            "metric": {
                "id": "near.stablecoin_market_data",
                "name": "Stablecoin Market Data",
                "unit": "peg-specific units and USD",
                "frequency": "daily",
                "value_type": "decimal",
            },
            "time": {
                "timezone": "UTC",
                "timestamp_unit": "seconds",
                "date_convention": "UTC calendar date of timestamp",
            },
            "observations": observations,
        }
    }
