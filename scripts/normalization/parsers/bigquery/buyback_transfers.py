"""Validate and normalize the incremental buyback transfer aggregates."""

from datetime import date
from decimal import Decimal, InvalidOperation

from buybacks import BUYBACK_TRANSFER_TYPES
from sources import SourceName, get_source, source_metadata


TRANSFER_TYPES = BUYBACK_TRANSFER_TYPES
AMOUNT_FIELDS = (
    "native_inflow_near", "wrapped_inflow_near", "total_inflow_near",
    "native_transfer_count", "wrapped_transfer_count", "total_transfer_count",
)


def parse_buyback_transfers(raw_data):
    if not isinstance(raw_data, list):
        raise ValueError("Buyback transfer raw data must be a list")

    observations = []
    seen = set()
    for index, row in enumerate(raw_data):
        if not isinstance(row, dict):
            raise ValueError(f"Buyback transfer record {index} must be an object")
        try:
            day_text = row["utc_date"]
            day = date.fromisoformat(day_text)
            transfer_type = row["transfer_type"]
            sender = row["sender"]
            values = {}
            for field in AMOUNT_FIELDS:
                value = row[field]
                if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
                    raise TypeError(f"{field} must be numeric")
                numeric = value if isinstance(value, Decimal) else Decimal(str(value))
                if not numeric.is_finite() or numeric < 0:
                    raise ValueError(f"{field} must be finite and non-negative")
                if field.endswith("_count") and numeric != numeric.to_integral_value():
                    raise ValueError(f"{field} must be an integer")
                values[field] = int(numeric) if field.endswith("_count") else numeric
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Buyback transfer record {index} is invalid") from exc

        if day.isoformat() != day_text or transfer_type not in TRANSFER_TYPES:
            raise ValueError(f"Buyback transfer record {index} has an invalid date or transfer_type")
        if not isinstance(sender, str) or not sender:
            raise ValueError(f"Buyback transfer record {index} has an invalid sender")
        key = (day, transfer_type)
        if key in seen:
            raise ValueError(f"Duplicate buyback transfer observation: {key}")
        seen.add(key)
        observations.append({"date": day_text, "sender": sender, "transfer_type": transfer_type, **values})

    observations.sort(key=lambda row: (row["date"], row["transfer_type"]))
    return {
        "daily_buyback_transfers.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.BIGQUERY_BUYBACK_TRANSFERS,
                dataset=get_source(SourceName.BIGQUERY_BUYBACK_TRANSFERS).dataset,
            ),
            "metric": {
                "unit": "NEAR",
                "frequency": "daily",
                "dimensions": ["transfer_type", "sender"],
            },
            "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
            "observations": observations,
        }
    }
