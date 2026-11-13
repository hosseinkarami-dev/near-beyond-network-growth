"""Build compact Network analytics outputs from normalized local datasets."""

import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

from analytics.periods import CALENDAR_PERIODS, period_bounds
from paths import ANALYTICS_DATA_DIR, NORMALIZED_DATA_DIR
from validation import validate_json


NORMALIZED_ROOT = NORMALIZED_DATA_DIR
ANALYTICS_NETWORK_DIR = ANALYTICS_DATA_DIR / "network"
ANALYTICS_TOKENOMICS_DIR = ANALYTICS_DATA_DIR / "tokenomics"
DAILY_OUTPUT = ANALYTICS_NETWORK_DIR / "daily_metrics.json"
SNAPSHOT_OUTPUT = ANALYTICS_NETWORK_DIR / "snapshot.json"
STABLECOIN_INPUT = "defillama/near_stablecoin/daily_stablecoin_market_data.json"


# Paths are relative to data/normalized. Decimal source values are parsed to Decimal.
INPUTS = {
    "transactions": {
        "path": "nearblocks/txn_stats/daily_transactions.json", "value_key": "value",
        "unit": "transactions", "value_type": "integer",
    },
    "transaction_fees_near": {
        "path": "nearblocks/txn_stats/daily_transaction_fees.json", "value_key": "value",
        "unit": "NEAR", "value_type": "decimal",
    },
    "active_accounts": {
        "path": "nearblocks/address_stats/active_accounts.json", "value_key": "value",
        "unit": "accounts", "value_type": "integer",
    },
    "active_contracts": {
        "path": "nearblocks/address_stats/active_contracts.json", "value_key": "value",
        "unit": "contracts", "value_type": "integer",
    },
    "new_contracts": {
        "path": "nearblocks/address_stats/new_contracts.json", "value_key": "value",
        "unit": "contracts", "value_type": "integer",
    },
    "tvl_usd": {
        "path": "defillama/historical_chain_tvl/tvl_usd.json", "value_key": "value",
        "unit": "USD", "value_type": "decimal",
    },
    "near_usd_price": {
        "path": "binance/near_price/nearusdt_1d_close_price.json", "value_key": "price",
        "unit": "USDT", "value_type": "decimal",
    },
}

DAILY_FIELDS = (
    "date", "transactions", "transaction_fees_near", "transaction_fees_usd", "near_usd_price",
    "active_accounts", "active_contracts", "new_contracts", "tvl_usd", "tvl_near",
)
INTEGER_FIELDS = {name for name, spec in INPUTS.items() if spec["value_type"] == "integer"}
DECIMAL_FIELDS = set(INPUTS) - INTEGER_FIELDS
INVALID = object()


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def near_to_usd(amount_near: Any, near_usd_price: Any) -> Decimal | None:
    """Convert NEAR to USD using its same-day USDT close as the USD proxy."""

    amount = _as_decimal(amount_near)
    price = _as_decimal(near_usd_price)
    if amount is None or price is None or price <= 0:
        return None
    return amount * price


def usd_to_near(amount_usd: Any, near_usd_price: Any) -> Decimal | None:
    """Convert USD to NEAR using its same-day USDT close as the USD proxy."""

    amount = _as_decimal(amount_usd)
    price = _as_decimal(near_usd_price)
    if amount is None or price is None or price <= 0:
        return None
    return amount / price


def _parse_date(value: Any, source_name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{source_name} observation date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{source_name} has invalid date {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{source_name} date must use YYYY-MM-DD format")
    return parsed


def _utc_midnight_timestamp(day: date) -> int:
    return (day - date(1970, 1, 1)).days * 86_400_000


def _load_input_series(
    normalized_root: Path,
) -> tuple[dict[str, dict[date, Any]], dict[str, int]]:
    series: dict[str, dict[date, Any]] = {}
    row_counts: dict[str, int] = {}
    for field, spec in INPUTS.items():
        path = normalized_root / spec["path"]
        document = _read_json(path)
        if not isinstance(document, dict) or not isinstance(document.get("observations"), list):
            raise ValueError(f"{path.name} must be a normalized document with observations")
        metric = document.get("metric")
        timing = document.get("time")
        if not isinstance(metric, dict) or metric.get("unit") != spec["unit"]:
            raise ValueError(f"{path.name} has an unexpected unit; expected {spec['unit']}")
        if metric.get("frequency") != "daily" or metric.get("value_type") != spec["value_type"]:
            raise ValueError(f"{path.name} has unexpected daily metric metadata")
        if not isinstance(timing, dict) or timing.get("timezone") != "UTC":
            raise ValueError(f"{path.name} must declare UTC dates")
        if timing.get("timestamp_unit") != "milliseconds":
            raise ValueError(f"{path.name} must use millisecond timestamps")
        if field == "near_usd_price" and document.get("market", {}).get("symbol") != "NEARUSDT":
            raise ValueError(f"{path.name} must contain the NEARUSDT market")

        values: dict[date, Any] = {}
        for index, observation in enumerate(document["observations"]):
            if not isinstance(observation, dict):
                raise ValueError(f"{path.name} observation {index} must be an object")
            day = _parse_date(observation.get("date"), path.name)
            timestamp = observation.get("timestamp")
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise ValueError(f"{path.name} timestamp must be an integer")
            if timestamp != _utc_midnight_timestamp(day):
                raise ValueError(f"{path.name} timestamp does not match UTC midnight for {day}")
            if day in values:
                raise ValueError(f"{path.name} contains duplicate date {day}")

            value = observation.get(spec["value_key"])
            if value is None:
                normalized_value = None
            elif field in INTEGER_FIELDS:
                normalized_value = value if isinstance(value, int) and not isinstance(value, bool) else INVALID
            else:
                normalized_value = _as_decimal(value)
                if normalized_value is None or (field == "near_usd_price" and normalized_value <= 0):
                    normalized_value = INVALID
            values[day] = normalized_value
        series[field] = values
        row_counts[field] = len(values)
    return series, row_counts


def _precision(field: str, metric: str | None = None) -> int:
    if field.endswith("_pct"):
        return 4
    if field in {"average_7d", "average_30d"}:
        return 2
    source_field = metric or field
    if source_field in {"transaction_fees_near", "total_transaction_fees_near", "near_usd_price"}:
        return 8
    if source_field in {"transaction_fees_usd", "tvl_usd", "tvl_near"}:
        return 2
    if source_field in {"avg_block_time"}:
        return 6
    return 6


def _decimal_number_text(value: Decimal, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = max(80, len(value.as_tuple().digits) + places + 4)
        rounded = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        return "0"
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _serialize_json(document: Any) -> str:
    """Emit Decimal values as rounded JSON number tokens without using float."""

    prefix = f"__DECIMAL_{uuid4().hex}_"
    numbers: dict[str, str] = {}

    def prepare(value: Any, field: str = "", metric: str | None = None) -> Any:
        if isinstance(value, Decimal):
            token = f"{prefix}{len(numbers)}__"
            numbers[token] = _decimal_number_text(value, _precision(field, metric))
            return token
        if isinstance(value, dict):
            next_metric = field if field in INPUTS or field == "total_transaction_fees_near" else metric
            return {key: prepare(item, key, next_metric) for key, item in value.items()}
        if isinstance(value, list):
            return [prepare(item, field, metric) for item in value]
        return value

    result = json.dumps(prepare(document), ensure_ascii=False, indent=2, allow_nan=False)
    pattern = re.compile('"' + re.escape(prefix) + r"\d+__\"")
    result = pattern.sub(lambda match: numbers[match.group()[1:-1]], result)
    return result + "\n"


def _complete_window(
    rows: dict[date, dict[str, Any]], day: date, field: str, length: int,
) -> list[Any] | None:
    dates = [day - timedelta(days=offset) for offset in range(length - 1, -1, -1)]
    if any(current not in rows or rows[current].get(field) is None for current in dates):
        return None
    return [rows[current][field] for current in dates]


def _percentage_change(current: Any, previous: Any) -> Decimal | None:
    if current is None or previous is None:
        return None
    prior = _as_decimal(previous)
    value = _as_decimal(current)
    if prior is None or value is None or prior == 0:
        return None
    return ((value - prior) / prior) * Decimal(100)


def _snapshot_key_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("daily_metrics.json must contain daily observations")
    by_date = {_parse_date(row["date"], "daily_metrics.json"): row for row in rows}
    latest_day = max(by_date)
    if _parse_date(rows[-1]["date"], "daily_metrics.json") != latest_day:
        raise ValueError("daily_metrics.json observations must end with the maximum date")
    latest = by_date[latest_day]
    fee_observations = [
        amount for row in rows
        if (amount := _as_decimal(row.get("transaction_fees_near"))) is not None
    ]
    fields = ("transactions", "transaction_fees_near", "transaction_fees_usd", "active_accounts", "active_contracts",
              "new_contracts", "tvl_usd", "tvl_near", "near_usd_price")
    key_metrics: dict[str, Any] = {}
    for field in fields:
        value = latest[field]
        previous_row = by_date.get(latest_day - timedelta(days=1))
        week_row = by_date.get(latest_day - timedelta(days=7))
        month_row = by_date.get(latest_day - timedelta(days=30))
        item: dict[str, Any] = {"value": value}
        if field == "new_contracts":
            item["change_24h"] = (
                value - previous_row[field] if previous_row else None
            )
            week = _complete_window(by_date, latest_day, field, 7)
            month = _complete_window(by_date, latest_day, field, 30)
            item["sum_7d"] = sum(week) if week is not None else None
            item["sum_30d"] = sum(month) if month is not None else None
        else:
            item["change_24h_pct"] = _percentage_change(
                value, previous_row.get(field) if previous_row else None
            )
            item["change_7d_pct"] = _percentage_change(value, week_row.get(field) if week_row else None)
            item["change_30d_pct"] = _percentage_change(value, month_row.get(field) if month_row else None)
        key_metrics[field] = item
    fee_dates = [
        day for day, row in by_date.items()
        if _as_decimal(row.get("transaction_fees_near")) is not None
    ]
    key_metrics["total_transaction_fees_near"] = {
        "value": sum(fee_observations, Decimal(0)),
        "unit": "NEAR",
        "from": min(fee_dates).isoformat() if fee_dates else None,
        "through": max(fee_dates).isoformat() if fee_dates else None,
    }
    return key_metrics


def _network_stats(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("summary.json metrics must be an object")
    required = {"avg_block_time", "tps", "nodes_online", "gas_price"}
    if not required.issubset(metrics):
        raise ValueError("summary.json must contain avg_block_time, tps, nodes_online, and gas_price")
    stats: dict[str, Any] = {}
    tokenomics_fields = {
        "change_24h", "circulating_supply", "market_cap", "near_btc_price",
        "near_price", "total_supply", "volume_24h",
    }
    for field, metric in metrics.items():
        if field in tokenomics_fields:
            continue
        value = metric.get("value") if isinstance(metric, dict) else None
        if value is None:
            if field in required:
                raise ValueError(f"summary.json is missing network statistic {field}")
            stats[field] = None
            continue
        if field in {"avg_block_time"}:
            parsed = _as_decimal(value)
            if parsed is None:
                raise ValueError(f"summary.json {field} must be numeric")
            stats[field] = parsed
        elif field == "gas_price" and isinstance(value, str) and value.isdigit():
            stats[field] = int(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            stats[field] = value
        elif isinstance(value, str) and value.isdigit():
            stats[field] = int(value)
        elif field in required:
            raise ValueError(f"summary.json {field} must be an integer value")
        else:
            parsed = _as_decimal(value)
            stats[field] = parsed if parsed is not None else value
    return stats


def _snapshot_document(
    daily_document: dict[str, Any], summary: dict[str, Any],
) -> dict[str, Any]:
    rows = daily_document.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("daily_metrics.json must contain daily observations")
    return {
        "network": {"name": summary.get("network"), "updated_at": summary.get("updated_at")},
        "network_stats": _network_stats(summary),
        "key_metrics": _snapshot_key_metrics(rows),
    }


def _stablecoin_supply(normalized_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build daily USD supply and snapshot KPIs from circulating peg categories."""
    document = _read_json(normalized_root / STABLECOIN_INPUT)
    source = document.get("source", {})
    rows = document.get("observations")
    if not isinstance(rows, list):
        raise ValueError("Normalized stablecoin data must contain observations")

    by_date: dict[date, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            continue
        try:
            day = date.fromisoformat(row["date"])
        except ValueError:
            continue
        if day in by_date:
            continue
        categories = row.get("total_circulating_usd_by_peg")
        if not isinstance(categories, dict):
            continue
        values: dict[str, Decimal] = {}
        valid = True
        for category, raw_value in categories.items():
            if raw_value is None:
                continue
            value = _as_decimal(raw_value)
            if value is None or value < 0:
                valid = False
                break
            values[str(category)] = value
        if not valid or not values:
            continue
        total = sum(values.values(), Decimal(0))
        by_date[day] = {
            "date": day.isoformat(),
            "total_circulating_usd": total,
            "total_circulating_usd_by_peg": values,
        }

    if not by_date:
        raise ValueError("No valid circulating stablecoin USD observations were found")
    days = sorted(by_date)
    current_day = days[-1]
    current = by_date[current_day]["total_circulating_usd"]
    references: dict[str, dict[str, Any] | None] = {}
    metrics: dict[str, Any] = {
        "value": current,
        "date": current_day.isoformat(),
    }
    for window in (30, 90):
        target = current_day - timedelta(days=window)
        reference_day = min(
            (day for day in days if day < current_day),
            key=lambda day: (abs((day - target).days), day > target, day),
            default=None,
        )
        reference = by_date[reference_day] if reference_day is not None else None
        references[f"{window}d"] = (
            {"date": reference_day.isoformat(), "value": reference["total_circulating_usd"]}
            if reference is not None else None
        )
        previous = reference["total_circulating_usd"] if reference is not None else None
        metrics[f"change_{window}d_usd"] = current - previous if previous is not None else None
        metrics[f"change_{window}d_pct"] = _percentage_change(current, previous)
        metrics[f"reference_{window}d"] = references[f"{window}d"]

    analytics_document = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "source": source,
        "metric": {
            "id": "near.stablecoin_supply_usd",
            "name": "Circulating stablecoin supply",
            "unit": "USD",
            "currency": "USD",
            "aggregation": "sum of totalCirculatingUSD across available peg categories",
            "period_aggregation": "period_end_snapshot",
            "excluded_source_fields": [
                "totalMintedUSD", "totalUnreleased", "totalBridgedToUSD",
            ],
        },
        "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
        "observations": [by_date[day] for day in days],
    }
    return analytics_document, metrics


def _stablecoin_period_rows(
    observations: list[dict[str, Any]], period: str,
) -> list[dict[str, Any]]:
    """Return the last valid daily supply observation in each calendar period."""
    groups: dict[str, list[tuple[date, dict[str, Any], date, date]]] = {}
    for row in observations:
        day = _parse_date(row["date"], "stablecoin_supply.json")
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, row, start, end))

    result = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda item: item[0])
        last_day, last_row, start, end = group[-1]
        result.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": last_day.isoformat(),
            "as_of_date": last_day.isoformat(),
            "days_observed": len(group),
            "total_circulating_usd": last_row["total_circulating_usd"],
            "total_circulating_usd_by_peg": last_row["total_circulating_usd_by_peg"],
        })
    return result


FLOW_FIELDS = {"transactions", "transaction_fees_near", "transaction_fees_usd", "new_contracts"}
PERIODS = CALENDAR_PERIODS


def _periodic_network_rows(rows: list[dict[str, Any]], period: str) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[date, dict[str, Any], date, date]]] = {}
    for row in rows:
        day = _parse_date(row["date"], "daily_metrics.json")
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, row, start, end))

    results = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda item: item[0])
        last_day, last_row, start, end = group[-1]
        aggregated: dict[str, Any] = {
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": last_day.isoformat(),
            "days_observed": len(group),
        }
        for field in DAILY_FIELDS[1:]:
            aggregated[field] = (
                sum((item[1][field] for item in group), 0)
                if field in FLOW_FIELDS else last_row[field]
            )
        results.append(aggregated)
    return results


def build_network_analytics(
    normalized_root: Path = NORMALIZED_ROOT,
    output_dir: Path = ANALYTICS_NETWORK_DIR,
) -> dict[str, Any]:
    """Inner-join complete normalized observations and write minimal outputs."""

    normalized_root = Path(normalized_root)
    output_dir = Path(output_dir)
    series, source_counts = _load_input_series(normalized_root)
    source_dates = [set(values) for values in series.values()]
    dates_before_join = set.union(*source_dates)
    joined_dates = set.intersection(*source_dates)

    null_excluded: set[date] = set()
    invalid_excluded: set[date] = set()
    observations: list[dict[str, Any]] = []
    with localcontext() as context:
        context.prec = 80
        for day in sorted(joined_dates):
            values = {field: series[field][day] for field in INPUTS}
            if any(value is None for value in values.values()):
                null_excluded.add(day)
                continue
            if any(value is INVALID for value in values.values()):
                invalid_excluded.add(day)
                continue
            usd_fees = near_to_usd(values["transaction_fees_near"], values["near_usd_price"])
            tvl_near = usd_to_near(values["tvl_usd"], values["near_usd_price"])
            if usd_fees is None or tvl_near is None:
                invalid_excluded.add(day)
                continue
            observations.append({
                "date": day.isoformat(),
                "transactions": values["transactions"],
                "transaction_fees_near": values["transaction_fees_near"],
                "transaction_fees_usd": usd_fees,
                "near_usd_price": values["near_usd_price"],
                "active_accounts": values["active_accounts"],
                "active_contracts": values["active_contracts"],
                "new_contracts": values["new_contracts"],
                "tvl_usd": values["tvl_usd"],
                "tvl_near": tvl_near,
            })

    expected_fields = set(DAILY_FIELDS)
    if any(set(row) != expected_fields or any(row[field] is None for field in DAILY_FIELDS) for row in observations):
        raise ValueError("Final daily rows must contain all required fields with non-null values")
    observations.sort(key=lambda row: row["date"])

    report = {
        "source_row_counts": source_counts,
        "unique_dates_before_join": len(dates_before_join),
        "dates_after_inner_join": len(joined_dates),
        "records_excluded_due_to_missing_dates": len(dates_before_join - joined_dates),
        "records_excluded_due_to_null_values": len(null_excluded),
        "records_excluded_due_to_invalid_values": len(invalid_excluded),
        "records_after_join_and_validation": len(observations),
        "first_date": observations[0]["date"] if observations else None,
        "last_date": observations[-1]["date"] if observations else None,
    }
    if not observations:
        raise ValueError("No complete daily rows remain after the inner join and value validation")

    daily_document = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
        "observations": observations,
    }
    summary_path = normalized_root / "nearblocks" / "stats" / "network" / "summary.json"
    with summary_path.open(encoding="utf-8") as source:
        summary = json.load(source)

    output_dir.mkdir(parents=True, exist_ok=True)
    daily_path = output_dir / "daily_metrics.json"
    daily_json = _serialize_json(daily_document)
    daily_path.write_text(validate_json(json.loads(daily_json, parse_float=Decimal)), encoding="utf-8")

    # Snapshot calculations intentionally consume the serialized, final inner-joined dataset.
    final_daily = _read_json(daily_path)
    snapshot = _snapshot_document(final_daily, summary)
    stablecoin_document, stablecoin_metrics = _stablecoin_supply(normalized_root)
    snapshot["key_metrics"]["stablecoin_supply_usd"] = stablecoin_metrics
    snapshot_path = output_dir / "snapshot.json"
    snapshot_json = _serialize_json(snapshot)
    snapshot_path.write_text(validate_json(json.loads(snapshot_json, parse_float=Decimal)), encoding="utf-8")
    stablecoin_path = output_dir / "stablecoin_supply.json"
    stablecoin_json = _serialize_json(stablecoin_document)
    stablecoin_path.write_text(
        validate_json(json.loads(stablecoin_json, parse_float=Decimal)), encoding="utf-8"
    )
    stablecoin_period_paths = {}
    for period in PERIODS:
        period_document = {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "metric": {
                "unit": "USD",
                "aggregation": "period_end_snapshot",
                "source": "DefiLlama totalCirculatingUSD",
            },
            "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
            "observations": _stablecoin_period_rows(
                stablecoin_document["observations"], period,
            ),
        }
        period_path = output_dir / f"{period}_stablecoin_supply.json"
        period_json = _serialize_json(period_document)
        period_path.write_text(
            validate_json(json.loads(period_json, parse_float=Decimal)), encoding="utf-8"
        )
        stablecoin_period_paths[period] = period_path

    for period in PERIODS:
        period_document = {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "aggregation": {
                field: "sum" if field in FLOW_FIELDS else "period_end_snapshot"
                for field in DAILY_FIELDS[1:]
            },
            "observations": _periodic_network_rows(final_daily["observations"], period),
        }
        period_path = output_dir / f"{period}_metrics.json"
        period_path.write_text(validate_json(period_document), encoding="utf-8")

    from console_ui import console
    from rich.table import Table

    table = Table(title="Network analytics", show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")
    table.add_row("Joined daily observations", f"{report['records_after_join_and_validation']:,}")
    table.add_row("Coverage", f"{report['first_date']} to {report['last_date']}")
    table.add_row("Excluded dates / null / invalid", (
        f"{report['records_excluded_due_to_missing_dates']:,} / "
        f"{report['records_excluded_due_to_null_values']:,} / "
        f"{report['records_excluded_due_to_invalid_values']:,}"
    ))
    console.print(table)
    console.print(f"[green]OK[/green] Network outputs ready [dim](daily + snapshot + {len(stablecoin_period_paths) + 1} stablecoin series)[/dim]")
    return {
        "daily": daily_path,
        "snapshot": snapshot_path,
        "stablecoin": stablecoin_path,
        "stablecoin_periods": stablecoin_period_paths,
        "report": report,
    }
