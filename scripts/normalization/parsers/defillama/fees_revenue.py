"""Normalization parsers for DefiLlama fees and revenue payloads."""
from datetime import datetime, timezone
from common import SourceName, source_metadata


def _validate_root(data):
    required = ("totalDataChart", "protocols")
    if not isinstance(data, dict) or any(key not in data for key in required):
        raise ValueError("Expected object with totalDataChart and protocols fields")
    if not isinstance(data["totalDataChart"], list) or not isinstance(data["protocols"], list):
        raise ValueError("totalDataChart and protocols must be arrays")


def _date(timestamp):
    if not isinstance(timestamp, (int, float)):
        raise ValueError("Chart timestamp must be numeric")
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def _chart(data):
    seen = set()
    points = []
    for row in data["totalDataChart"]:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Each totalDataChart entry must be [timestamp, value]")
        timestamp, value = row
        if timestamp in seen:
            raise ValueError(f"Duplicate timestamp: {timestamp}")
        seen.add(timestamp)
        points.append({"timestamp": timestamp * 1000, "date": _date(timestamp), "value": value})
    return points


def _breakdown(data):
    seen = set()
    observations = []
    for row in data.get("totalDataChartBreakdown", []):
        if not isinstance(row, list) or len(row) != 2 or not isinstance(row[1], dict):
            raise ValueError("Each breakdown entry must be [timestamp, protocol-values object]")
        timestamp, values = row
        if timestamp in seen:
            raise ValueError(f"Duplicate breakdown timestamp: {timestamp}")
        seen.add(timestamp)
        observations.append({"timestamp": timestamp * 1000, "date": _date(timestamp),
                             "values": values})
    return observations


def _document(data, metric_id, name, unit, frequency, source_name, observations=None, values=None):
    return {
        "schema_version": "1.0.0",
        "network": "NEAR",
        "source": source_metadata(
            source_name,
            attribution="DefiLlama",
            chain=data.get("chain"),
        ),
        "metric": {"id": metric_id, "name": name, "unit": unit, "frequency": frequency},
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **({"observations": observations} if observations is not None else {"values": values}),
    }


def parse_fees(data):
    _validate_root(data)
    mapping = {
        "total24h": "total_24h", "total7d": "total_7d", "total30d": "total_30d",
        "totalAllTime": "all_time", "change_1d": "daily_growth",
        "change_7dover7d": "weekly_growth", "change_30dover30d": "monthly_growth",
    }
    values = {target: data.get(source) for source, target in mapping.items()}
    summary = _document(
        data, "near.ecosystem_fees", "NEAR ecosystem fees", "USD", "snapshot",
        SourceName.NEAR_FEES, values=values,
    )
    summary["metric"]["growth_unit"] = "percent"
    protocols = _protocol_records(data)
    return {
        "summary.json": summary,
        "daily_protocol_fees1.json": _document(
            data, "near.daily_protocol_fees", "Daily protocol fees", "USD", "daily",
            SourceName.NEAR_FEES, observations=_chart(data),
        ),
        "daily_protocol_fees_breakdown.json": _document(data, "near.daily_protocol_fees_breakdown",
            "Daily protocol fees by protocol", "USD", "daily", SourceName.NEAR_FEES,
            observations=_breakdown(data)),
        "protocol_fees_ranking.json": _document(data, "near.protocol_fees_ranking",
            "Protocol fees ranking", "USD", "snapshot", SourceName.NEAR_FEES, values=protocols),
    }


def _protocol_records(data):
    required = ("name", "id", "slug", "category", "total30d", "totalAllTime")
    records = []
    for protocol in data["protocols"]:
        if not isinstance(protocol, dict):
            raise ValueError("Each protocol entry must be an object")
        record = {key: protocol.get(key) for key in required}
        if record["name"] is None or record["id"] is None:
            raise ValueError("Protocol name and id are required")
        records.append(record)
    return records


def parse_revenue(data):
    _validate_root(data)
    summary_values = {"total_30d": data.get("total30d"), "all_time": data.get("totalAllTime"),
                      "growth_30d": data.get("change_30dover30d"), "growth_unit": "percent"}
    return {
        "summary.json": _document(data, "near.protocol_revenue", "NEAR protocol revenue",
                                   "USD", "snapshot", SourceName.NEAR_REVENUE, values=summary_values),
        "daily_protocol_revenue.json": _document(
            data, "near.daily_protocol_revenue", "Daily protocol revenue", "USD", "daily",
            SourceName.NEAR_REVENUE, observations=_chart(data),
        ),
        "daily_protocol_revenue_breakdown.json": _document(data, "near.daily_protocol_revenue_breakdown",
            "Daily protocol revenue by protocol", "USD", "daily", SourceName.NEAR_REVENUE,
            observations=_breakdown(data)),
    }
