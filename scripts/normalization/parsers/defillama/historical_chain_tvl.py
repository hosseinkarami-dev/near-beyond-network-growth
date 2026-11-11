"""Parser for DefiLlama historical chain TVL responses."""
from datetime import datetime, timezone

from common import SourceName, source_metadata


def parse_historical_chain_tvl(raw_data):
    """Return normalized TVL metric data keyed by output filename."""
    observations = []
    seen_timestamps = set()
    for point in raw_data:
        timestamp = point["date"]
        if timestamp in seen_timestamps:
            raise ValueError(f"Duplicate TVL timestamp: {timestamp}")
        seen_timestamps.add(timestamp)
        observations.append({
            "timestamp": point["date"] * 1000,
            "date": datetime.fromtimestamp(point["date"], tz=timezone.utc).date().isoformat(),
            "value": point["tvl"],
        })

    return {
        "tvl_usd.json": {
            "schema_version": "1.0.0",
            "metric": {
                "id": "near.tvl_usd",
                "name": "NEAR chain TVL",
                "category": "tvl",
                "description": "Total value locked attributed to the NEAR chain by DefiLlama.",
                "entity": "NEAR mainnet",
                "unit": "USD",
                "value_type": "decimal",
                "frequency": "daily",
                "aggregation": "period_end_snapshot",
                "source_metric": "TVL",
            },
            "source": source_metadata(SourceName.DEFILLAMA_CHAIN_TVL, attribution="DefiLlama"),
            "time": {
                "timezone": "UTC",
                "timestamp_unit": "milliseconds",
                "date_convention": "UTC calendar date of timestamp",
            },
            "observations": observations,
        }
    }
