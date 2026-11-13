"""Normalize the locally stored DefiLlama NEAR DEX volume response."""
from datetime import datetime, timezone
from sources import SourceName, source_metadata


def _document(metric_id, name, frequency, *, values=None, observations=None):
    doc = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "source": source_metadata(SourceName.NEAR_DEX_VOLUMES, attribution="DefiLlama"),
        "metric": {"id": metric_id, "name": name, "unit": "USD",
                   "frequency": frequency, "metric_type": "dailyVolume"},
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if values is not None:
        doc["values"] = values
    if observations is not None:
        doc["observations"] = observations
    return doc


def _observations(rows, *, breakdown=False):
    if not isinstance(rows, list):
        raise ValueError("Expected chart data to be an array")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Chart entries must be [timestamp, value]")
        timestamp, value = row
        if not isinstance(timestamp, (int, float)):
            raise ValueError("Chart timestamp must be numeric")
        if timestamp in seen:
            raise ValueError(f"Duplicate timestamp: {timestamp}")
        seen.add(timestamp)
        if breakdown and not isinstance(value, dict):
            raise ValueError("Breakdown values must be protocol-value objects")
        result.append({"timestamp": timestamp, "date": datetime.fromtimestamp(
            timestamp, timezone.utc).date().isoformat(), "value": value})
    return result


def parse_dex_volumes(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    if data.get("chain") != "Near":
        raise ValueError("Response chain is not Near")

    summary_fields = ("total24h", "total48hto24h", "totalLastFullDay", "total7d",
                     "total14dto7d", "total30d", "total60dto30d", "total1y",
                     "total7DaysAgo", "total30DaysAgo", "totalAllTime", "change_1d",
                     "change_7d", "change_1m", "change_7dover7d", "change_30dover30d")
    summary = {key.replace("total", "total_").replace("AllTime", "all_time")
               .replace("DaysAgo", "_days_ago").replace("hto", "h_to_")
               .replace("dto", "d_to_").replace("_", "_"): data[key]
               for key in summary_fields if key in data}
    outputs = {"summary.json": _document(
        "near.tracked_protocol_dex_volume", "Tracked protocol DEX volume", "snapshot",
        values=summary)}

    if "totalDataChart" in data:
        outputs["daily_tracked_protocol_dex_volume.json"] = _document(
            "near.daily_tracked_protocol_dex_volume", "Daily tracked protocol DEX volume",
            "daily", observations=_observations(data["totalDataChart"]))
    if "totalDataChartBreakdown" in data:
        outputs["daily_tracked_protocol_dex_volume_breakdown.json"] = _document(
            "near.daily_tracked_protocol_dex_volume_breakdown",
            "Daily tracked protocol DEX volume by protocol", "daily",
            observations=_observations(data["totalDataChartBreakdown"], breakdown=True))

    protocols = data.get("protocols")
    if protocols is not None:
        if not isinstance(protocols, list):
            raise ValueError("protocols must be an array")
        fields = ("name", "id", "slug", "category", "total24h", "total7d", "total30d",
                  "totalAllTime", "change_1d", "change_7d", "change_30dover30d")
        field_names = {"total24h": "total_24h", "total7d": "total_7d", "total30d": "total_30d",
                       "totalAllTime": "total_all_time", "change_1d": "change_1d",
                       "change_7d": "change_7d", "change_30dover30d": "change_30d_over_30d"}
        records = []
        for protocol in protocols:
            if not isinstance(protocol, dict):
                raise ValueError("Each protocol must be an object")
            records.append({field_names.get(key, key): protocol.get(key)
                            for key in fields if key in protocol})
        outputs["protocol_dex_volume_ranking.json"] = _document(
            "near.protocol_dex_volume", "Protocol DEX volume ranking", "snapshot",
            values=records)
    return outputs
