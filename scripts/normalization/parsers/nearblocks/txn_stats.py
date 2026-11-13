"""Normalize selected daily transaction statistics from NearBlocks."""
from datetime import date, datetime, time, timezone
from sources import SourceName, source_metadata


def parse_txn_stats(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Expected an object containing a data array")

    outputs = {}
    for field, metric_id, name, unit in (
        ("txns", "near.daily_transactions", "Daily transactions", "transactions"),
        ("txn_fee", "near.daily_transaction_fees", "Daily transaction fees", "NEAR"),
    ):
        observations = []
        seen_dates = set()
        for row in data["data"]:
            if not isinstance(row, dict) or "date" not in row or field not in row:
                raise ValueError(f"Each data row must contain date and {field}")
            day = date.fromisoformat(row["date"])
            if day in seen_dates:
                raise ValueError(f"Duplicate transaction-stat date: {day.isoformat()}")
            seen_dates.add(day)
            timestamp = int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp() * 1000)
            value = row[field]
            # Keep decimal strings (notably txn_fee) unchanged to avoid float precision loss.
            observations.append({"timestamp": timestamp, "date": day.isoformat(), "value": value})

        observations.sort(key=lambda observation: observation["timestamp"])
        outputs["daily_transactions.json" if field == "txns" else "daily_transaction_fees.json"] = {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.NEAR_TXN_STATS,
                attribution="Powered by NearBlocks.io APIs",
            ),
            "metric": {"id": metric_id, "name": name, "unit": unit,
                       "frequency": "daily", "value_type": "integer" if field == "txns" else "decimal"},
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
            "observations": observations,
        }
    return outputs
