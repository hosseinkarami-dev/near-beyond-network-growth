"""Normalize locally stored DefiLlama NEAR Intents volume data."""
from datetime import datetime, timezone
from sources import SourceName, source_metadata


def _utc_date(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def _chart(rows):
    if not isinstance(rows, list):
        raise ValueError("Chart data must be an array")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Chart records must be [timestamp, value]")
        timestamp, value = row
        if not isinstance(timestamp, int):
            raise ValueError("Chart timestamp must be an integer Unix timestamp")
        if timestamp in seen:
            raise ValueError(f"Duplicate timestamp: {timestamp}")
        seen.add(timestamp)
        result.append({"timestamp": timestamp, "date": _utc_date(timestamp), "value": value})
    return result


def _doc(metric_id, name, frequency, source_meta, *, values=None, observations=None):
    document = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "source": source_meta,
        "metric": {"id": metric_id, "name": name, "unit": "USD",
                   "frequency": frequency, "metric_type": "dailyVolume"},
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if values is not None:
        document["values"] = values
    if observations is not None:
        document["observations"] = observations
    return document


def parse_near_intents_volume(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    if data.get("name") != "NEAR Intents" or data.get("chain") != "Near":
        raise ValueError("Unexpected protocol identity or chain")

    source_meta = source_metadata(
        SourceName.NEAR_INTENTS_DEX_VOLUME,
        attribution="DefiLlama",
        protocol_name=data["name"],
        protocol_id=data.get("id"),
        protocol_slug=data.get("slug"),
        chains=data.get("chains"),
    )
    summary_fields = {"total24h": "total_24h", "total48hto24h": "total_48h_to_24h",
                      "total7d": "total_7d", "total30d": "total_30d",
                      "total1y": "total_1y", "annualized1y": "annualized_1y",
                      "totalAllTime": "total_all_time", "change_1d": "change_1d"}
    summary = {normalized: data[source] for source, normalized in summary_fields.items()
               if source in data}

    outputs = {"summary.json": _doc(
        "near_intents.volume_summary", "NEAR Intents DEX volume summary", "snapshot",
        source_meta, values=summary)}

    if isinstance(data.get("totalDataChart"), list):
        outputs["daily_volume.json"] = _doc(
            "near_intents.daily_dex_volume", "NEAR Intents daily DEX volume", "daily",
            source_meta, observations=_chart(data["totalDataChart"]))

    return outputs
