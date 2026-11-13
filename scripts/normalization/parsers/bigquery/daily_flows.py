"""Normalize daily BigQuery token-flow datasets without recalculating values."""

from datetime import date
from decimal import Decimal, InvalidOperation

from sources import SourceName, get_source, source_metadata


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


def parse_contract_reward_event_audit(raw_data):
    """Normalize audited daily reward aggregates and preserve audit coverage."""

    if not isinstance(raw_data, dict) or raw_data.get("complete") is not True:
        raise ValueError("contract reward audit must be a complete raw document")
    query_range = raw_data.get("query_range")
    if not isinstance(query_range, dict):
        raise ValueError("contract reward audit query_range must be an object")
    items = raw_data.get("items")
    if not isinstance(items, list):
        raise ValueError("contract reward audit items must be a list")

    observations = []
    seen_dates = set()
    numeric_fields = (
        "total_reward_events", "valid_reward_events", "missing_previous_balance",
        "ambiguous_order", "non_positive_delta", "event_count_coverage_pct",
        "contract_rewards_near",
    )
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"contract reward audit item {index} must be an object")
        try:
            date_text = item["utc_date"]
            day = date.fromisoformat(date_text)
            values = {}
            for field in numeric_fields:
                raw_value = item[field]
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, Decimal)):
                    raise TypeError(f"{field} must be numeric")
                value = raw_value if isinstance(raw_value, Decimal) else Decimal(str(raw_value))
                if not value.is_finite() or value < 0:
                    raise ValueError(f"{field} must be finite and non-negative")
                values[field] = value
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"contract reward audit item {index} is invalid") from exc
        if day.isoformat() != date_text or day in seen_dates:
            raise ValueError(f"contract reward audit item {index} has an invalid or duplicate date")
        if values["valid_reward_events"] > values["total_reward_events"]:
            raise ValueError(f"contract reward audit item {index} has more valid than total events")
        seen_dates.add(day)
        observations.append({"utc_date": date_text, **values})

    source = source_metadata(
        SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT,
        dataset=get_source(SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT).dataset,
    )
    return {
        "contract_reward_event_audit.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source,
            "query_range": query_range,
            "metric": {
                "id": "near.audited_contract_rewards",
                "name": "Audited contract rewards",
                "unit": "NEAR",
                "frequency": "daily",
                "value_type": "decimal",
                "aggregation": "sum_of_valid_reward_event_balance_deltas",
            },
            "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
            "observations": observations,
        }
    }
