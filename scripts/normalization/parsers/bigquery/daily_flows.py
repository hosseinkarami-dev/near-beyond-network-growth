"""Normalize daily BigQuery token-flow datasets without recalculating values."""

from datetime import date
from decimal import Decimal, InvalidOperation

from common import SourceName, get_source, source_metadata


def _normalize_daily_flow(raw_data, *, source_name, value_field, metric_id, metric_name,
                          data_status=None):
    if not isinstance(raw_data, list):
        raise ValueError(f"{metric_name} records must be a list")

    observations = []
    seen_dates = set()
    for index, record in enumerate(raw_data):
        if not isinstance(record, dict):
            raise ValueError(f"{metric_name} record {index} must be an object")
        try:
            date_text = record["utc_date"]
            day = date.fromisoformat(date_text)
            raw_value = record[value_field]
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, Decimal)):
                raise TypeError(f"{value_field} must be numeric")
            value = raw_value if isinstance(raw_value, Decimal) else Decimal(str(raw_value))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{metric_name} record {index} has invalid date or value") from exc

        if day.isoformat() != date_text:
            raise ValueError(f"{metric_name} record {index} date must use YYYY-MM-DD")
        if day in seen_dates:
            raise ValueError(f"{metric_name} contains duplicate date {day}")
        if not value.is_finite() or value < 0:
            raise ValueError(f"{metric_name} values must be finite and non-negative")
        seen_dates.add(day)
        # Keep the source field names and date values intact. No unit conversion,
        # interpolation, or aggregation happens in normalization.
        observations.append({"utc_date": date_text, value_field: value})

    source = source_metadata(source_name, dataset=get_source(source_name).dataset)
    if data_status is not None:
        source.update(data_status=data_status["data_status"],
                      is_synthetic=data_status["is_synthetic"],
                      purpose=data_status["purpose"])

    document = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "source": source,
        "metric": {
            "id": metric_id,
            "name": metric_name,
            "unit": "NEAR",
            "frequency": "daily",
            "value_type": "decimal",
        },
        "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
        "observations": observations,
    }
    return document


def parse_daily_gross_burn(raw_data):
    """Pass daily gross burn records through with validation and source metadata."""

    return {
        "daily_gross_burn.json": _normalize_daily_flow(
            raw_data,
            source_name=SourceName.BIGQUERY_DAILY_GROSS_BURN,
            value_field="gross_tokens_burnt_near",
            metric_id="near.daily_gross_burn",
            metric_name="Daily gross burn",
        )
    }


def parse_daily_contract_rewards(raw_data):
    """Pass the synthetic daily contract rewards fixture through unchanged."""

    return {
        "daily_contract_rewards.json": _normalize_daily_flow(
            raw_data,
            source_name=SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS,
            value_field="contract_rewards_near",
            metric_id="near.daily_contract_rewards",
            metric_name="Daily contract rewards",
            data_status={
                "data_status": "synthetic",
                "is_synthetic": True,
                "purpose": "development_and_dashboard_testing",
            },
        )
    }
