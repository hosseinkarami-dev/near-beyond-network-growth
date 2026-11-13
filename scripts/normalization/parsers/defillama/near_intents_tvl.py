"""Normalize DefiLlama NEAR Intents TVL data from a local protocol payload."""
from datetime import datetime, timezone
from sources import SourceName, source_metadata


def _date(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def _series(rows, value_key):
    if not isinstance(rows, list):
        raise ValueError("Expected a time-series array")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or "date" not in row or value_key not in row:
            raise ValueError(f"Each time-series row must contain date and {value_key}")
        timestamp = row["date"]
        if timestamp in seen:
            raise ValueError(f"Duplicate timestamp: {timestamp}")
        seen.add(timestamp)
        result.append({"timestamp": timestamp, "date": _date(timestamp), "value": row[value_key]})
    return result


def _base(metric_id, name, unit, frequency, *, network="NEAR mainnet"):
    return {
        "schema_version": "1.0.0",
        "network": network,
        "source": source_metadata(SourceName.NEAR_INTENTS, attribution="DefiLlama"),
        "metric": {"id": metric_id, "name": name, "unit": unit, "frequency": frequency},
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def parse_near_intents_tvl(data):
    if not isinstance(data, dict) or data.get("name") != "NEAR Intents":
        raise ValueError("Expected the NEAR Intents protocol object")
    outputs = {}

    tvl = data.get("tvl")
    if isinstance(tvl, list) and tvl:
        observations = _series(tvl, "totalLiquidityUSD")
        latest = max(observations, key=lambda observation: observation["timestamp"])
        summary = _base("near_intents.tvl", "NEAR Intents TVL", "USD", "snapshot")
        summary["current_tvl"] = latest["value"]
        summary["current_timestamp"] = latest["timestamp"]
        summary["current_date"] = latest["date"]
        outputs["intents_tvl.json"] = summary
        daily = _base("near_intents.daily_tvl", "Daily NEAR Intents TVL", "USD", "daily")
        daily["observations"] = observations
        outputs["daily_intents_tvl.json"] = daily

    chain_current = data.get("currentChainTvls")
    if isinstance(chain_current, dict):
        tvl_rows = data.get("tvl")
        valid_timestamps = [
            row["date"] for row in tvl_rows
            if isinstance(row, dict) and isinstance(row.get("date"), int)
            and not isinstance(row.get("date"), bool)
        ] if isinstance(tvl_rows, list) else []
        current_timestamp = max(
            valid_timestamps, default=None,
        )
        if current_timestamp is None:
            raise ValueError("Cannot date currentChainTvls without a valid protocol TVL timestamp")
        items = []
        for chain, value in sorted(chain_current.items()):
            if not isinstance(chain, str) or not chain:
                raise ValueError("Current chain labels must be non-empty strings")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"Current TVL for {chain} must be non-negative numeric data")
            items.append({"chain": chain, "tvl_usd": value})
        chain_doc = _base("near_intents.tvl_by_chain", "NEAR Intents current TVL by chain", "USD", "snapshot")
        chain_doc["date"] = _date(current_timestamp)
        chain_doc["timestamp"] = current_timestamp
        chain_doc["items"] = items
        outputs["tvl_by_chain.json"] = chain_doc

    return outputs
