"""Normalize DefiLlama's historical NEAR Intents TVL by-token snapshots."""

import math
from datetime import datetime, timezone
from sources import SourceName, source_metadata


def parse_near_intents_token_breakdown(data):
    if not isinstance(data, list):
        raise ValueError("Expected token TVL breakdown as an array")

    observations = []
    seen_timestamps = set()
    for index, point in enumerate(data):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"Token TVL point {index} must be [timestamp, token-breakdown]")
        timestamp, token_values = point
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError(f"Token TVL point {index} timestamp must be an integer")
        if timestamp in seen_timestamps:
            raise ValueError(f"Duplicate token TVL timestamp: {timestamp}")
        if not isinstance(token_values, dict):
            raise ValueError(f"Token TVL point {index} breakdown must be an object")

        tokens = {}
        for token, value in token_values.items():
            if not isinstance(token, str) or not token.strip():
                raise ValueError(f"Token TVL point {index} contains an invalid token name")
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value) or value < 0:
                raise ValueError(f"Token TVL point {index} has invalid USD value for {token}")
            tokens[token] = value

        seen_timestamps.add(timestamp)
        observations.append({
            "timestamp": timestamp * 1000,
            "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
            "tokens": tokens,
        })

    observations.sort(key=lambda row: row["timestamp"])
    return {
        "daily_tvl_by_token.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.NEAR_INTENTS_TOKEN_BREAKDOWN,
                attribution="DefiLlama",
            ),
            "metric": {
                "id": "near_intents.tvl_by_token",
                "name": "NEAR Intents TVL by token",
                "unit": "USD",
                "frequency": "daily",
                "aggregation": "period_end_snapshot",
            },
            "time": {
                "timezone": "UTC",
                "timestamp_unit": "milliseconds",
                "date_convention": "UTC calendar date of timestamp",
            },
            "observations": observations,
        }
    }
