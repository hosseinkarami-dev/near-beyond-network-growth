"""Parsers for NearBlocks address statistics."""
from datetime import date, datetime, time, timezone
from sources import SourceName, source_metadata


def parse_address_statistics(raw_data):
    """Return independent normalized metrics from a NearBlocks response."""
    rows = raw_data["data"]
    metrics = (
        ("new_contracts", "New contracts", "contracts", "new_contracts"),
        ("active_contracts", "Active contracts", "contracts", "active_contracts"),
        ("active_accounts", "Active accounts", "accounts", "active_accounts"),
    )
    outputs = {}

    for metric_id, name, unit, source_key in metrics:
        observations = []
        seen_dates = set()
        for row in rows:
            day = date.fromisoformat(row["date"])
            if day in seen_dates:
                raise ValueError(f"Duplicate address-stat date: {day.isoformat()}")
            seen_dates.add(day)
            timestamp = int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp() * 1000)
            value = row.get(source_key)
            observations.append({
                "timestamp": timestamp,
                "date": day.isoformat(),
                "value": value
            })

        outputs[f"{metric_id}.json"] = {
            "schema_version": "1.0.0",
            "metric": {
                "id": f"near.{metric_id}",
                "name": name,
                "category": "addresses",
                "description": f"Daily {name.lower()} reported by NearBlocks.",
                "entity": "NEAR mainnet",
                "unit": unit,
                "value_type": "integer",
                "frequency": "daily",
                "aggregation": "interval_count",
                "source_metric": source_key,
            },
            "source": source_metadata(
                SourceName.NEAR_BLOCKS,
                attribution="Powered by NearBlocks.io APIs",
            ),
            "time": {
                "timezone": "UTC",
                "timestamp_unit": "milliseconds",
                "date_convention": "UTC calendar date of timestamp",
            },
            "observations": observations,
        }

    return outputs
