"""Normalize compact FastNEAR daily active-stake aggregates."""

from datetime import date

from sources import SourceName, source_metadata


def _integer_text(value, label: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isdigit():
        number = int(value)
    else:
        raise ValueError(f"{label} must be an integer")
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return str(number)


def parse_daily_active_validator_stake(raw_data):
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("items"), list):
        raise ValueError("FastNEAR raw document must contain an items list")

    items = []
    seen_dates = set()
    for index, record in enumerate(raw_data["items"]):
        if not isinstance(record, dict):
            raise ValueError(f"FastNEAR daily item {index} must be an object")
        try:
            date_text = record["utc_date"]
            day = date.fromisoformat(date_text)
            block_height = int(_integer_text(record["block_height"], "block_height"))
            total_stake_yocto = _integer_text(
                record["total_active_stake_yocto"],
                f"FastNEAR item {index} total_active_stake_yocto",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"FastNEAR daily item {index} is malformed") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"FastNEAR daily item {index} date must use YYYY-MM-DD")
        if day in seen_dates:
            raise ValueError(f"FastNEAR raw document has duplicate date {day}")
        items.append({
            "date": date_text,
            "block_height": block_height,
            "total_active_stake_yocto": total_stake_yocto,
        })
        seen_dates.add(day)

    items.sort(key=lambda item: item["date"])
    return {
        "daily_active_validator_stake.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE,
                method="validators",
                reference="daily_supply.json block_height",
            ),
            "time": {"timezone": "UTC", "date_convention": "UTC date from daily_supply.json"},
            "metric": {
                "unit": "NEAR",
                "input_unit": "yoctoNEAR",
                "aggregation": "sum_current_validators_during_raw_collection",
                "precision": "integer_yoctoNEAR",
            },
            "items": items,
        }
    }
