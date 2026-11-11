"""Normalize DefiLlama Holders Revenue data without deriving metrics."""
from datetime import datetime, timezone
from common import SourceName, source_metadata


def _snake(key):
    import re
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def _metadata(metric_id, name, frequency):
    return {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "source": source_metadata(SourceName.NEAR_HOLDERS_REVENUE, attribution="DefiLlama"),
        "metric": {"id": metric_id, "name": name, "unit": "USD", "frequency": frequency},
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _chart(rows):
    if not isinstance(rows, list):
        raise ValueError("totalDataChart must be an array")
    points, seen = [], set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Chart points must be [timestamp, value]")
        timestamp, value = row
        if not isinstance(timestamp, (int, float)):
            raise ValueError("Chart timestamp must be numeric")
        if timestamp in seen:
            raise ValueError(f"Duplicate chart timestamp: {timestamp}")
        seen.add(timestamp)
        points.append({"timestamp": timestamp,
                       "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
                       "value": value})
    return points


def _snake_record(value):
    if isinstance(value, dict):
        return {_snake(key): _snake_record(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snake_record(item) for item in value]
    return value


def parse_holders_revenue(data):
    if not isinstance(data, dict) or not isinstance(data.get("chain"), str):
        raise ValueError("Expected DefiLlama overview object with chain")
    outputs = {}

    summary_fields = {key: value for key, value in data.items()
                      if key not in {"totalDataChart", "totalDataChartBreakdown", "protocols",
                                     "breakdown24h", "breakdown30d", "allChains"}}
    summary = _metadata("near.ecosystem_holders_revenue", "NEAR ecosystem holders revenue", "snapshot")
    summary["summary"] = _snake_record(summary_fields)
    outputs["ecosystem_holders_revenue.json"] = summary

    if "totalDataChart" in data:
        doc = _metadata("near.daily_holders_revenue", "Daily holders revenue", "daily")
        doc["timestamp_unit"] = "unix_seconds"
        doc["observations"] = _chart(data["totalDataChart"])
        outputs["daily_holders_revenue.json"] = doc

    breakdown = data.get("totalDataChartBreakdown")
    if isinstance(breakdown, list) and breakdown:
        points, seen = [], set()
        meaningful = False
        for row in breakdown:
            if not isinstance(row, list) or len(row) != 2 or not isinstance(row[1], dict):
                raise ValueError("Breakdown points must be [timestamp, protocol-values object]")
            timestamp, values = row
            if timestamp in seen:
                raise ValueError(f"Duplicate breakdown timestamp: {timestamp}")
            seen.add(timestamp)
            if values:
                meaningful = True
            points.append({"timestamp": timestamp,
                           "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
                           "protocols": values})
        if meaningful:
            doc = _metadata("near.daily_holders_revenue_breakdown",
                            "Daily holders revenue by protocol", "daily")
            doc["timestamp_unit"] = "unix_seconds"
            doc["observations"] = points
            outputs["daily_holders_revenue_breakdown.json"] = doc
    return outputs
