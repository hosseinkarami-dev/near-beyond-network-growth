"""Normalize daily BigQuery supply snapshots from yoctoNEAR to NEAR."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from sources import SourceName, get_source, source_metadata
from units import YOCTO_PER_NEAR


def _near_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError("BigQuery supply values must be numeric")
    try:
        yocto = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("BigQuery supply values must be finite numbers") from exc
    if not yocto.is_finite():
        raise ValueError("BigQuery supply values must be finite numbers")
    with localcontext() as context:
        context.prec = max(50, len(yocto.as_tuple().digits) + 8)
        near = yocto / Decimal(YOCTO_PER_NEAR)
    text = format(near, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def parse_daily_supply(raw_data):
    if not isinstance(raw_data, list):
        raise ValueError("Expected BigQuery daily supply records as a list")
    observations = []
    seen_dates = set()
    epoch = date(1970, 1, 1)
    for index, record in enumerate(raw_data):
        if not isinstance(record, dict):
            raise ValueError(f"Daily supply record {index} must be an object")
        try:
            day_text = record["utc_date"]
            day = date.fromisoformat(day_text)
            total_supply = _near_value(record["total_supply"])
            raw_circulating_supply = record["circulating_supply"]
            circulating_supply = (
                _near_value(raw_circulating_supply)
                if raw_circulating_supply is not None else None
            )
            # A zero circulating supply alongside a positive total supply is a
            # source gap, not a meaningful NEAR supply observation.
            if (circulating_supply is not None
                    and Decimal(circulating_supply) == 0
                    and Decimal(total_supply) > 0):
                circulating_supply = None
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Daily supply record {index} is missing valid supply data") from exc
        if day.isoformat() != day_text:
            raise ValueError(f"Daily supply record {index} date must use YYYY-MM-DD")
        if day in seen_dates:
            raise ValueError(f"Daily supply contains duplicate date {day}")
        seen_dates.add(day)
        observations.append({
            "date": day_text,
            "timestamp": (day - epoch).days * 86_400_000,
            "total_supply": total_supply,
            "circulating_supply": circulating_supply,
        })
    return {
        "daily_supply.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.BIGQUERY_DAILY_SUPPLY,
                dataset=get_source(SourceName.BIGQUERY_DAILY_SUPPLY).dataset,
            ),
            "metric": {
                "id": "near.daily_supply",
                "name": "Daily NEAR supply",
                "unit": "NEAR",
                "frequency": "daily",
                "value_type": "decimal",
                "aggregation": "period_end_snapshot",
                "supply_precision": "approximate_float64",
            },
            "time": {"timezone": "UTC", "timestamp_unit": "milliseconds"},
            "observations": observations,
        }
    }
