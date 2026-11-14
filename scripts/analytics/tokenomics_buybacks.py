"""Aggregate normalized buyback transfer and wallet-balance sources."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from analytics.periods import CHART_PERIODS, period_bounds
from validation import validate_json


PERIODS = CHART_PERIODS
BUYBACK_TRANSFERS_PATH = Path("bigquery/buyback/daily_buyback_transfers.json")
BUYBACK_BALANCE_PATH = Path("fastnear/buyback/buyback_wallet_balance.json")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal number") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return result


def _load_transfer_rows(path: Path) -> dict[tuple[date, str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list):
        raise ValueError(f"{path.name} must contain observations")
    rows: dict[tuple[date, str, str], dict[str, Any]] = {}
    for index, item in enumerate(observations):
        try:
            day_text = item["date"]
            day = date.fromisoformat(day_text)
            transfer_type = item["transfer_type"]
            if not isinstance(transfer_type, str) or not transfer_type.strip():
                raise ValueError("transfer_type must be a non-empty string")
            values = {
                field: _decimal(item[field], field)
                for field in (
                    "native_inflow_near", "wrapped_inflow_near", "total_inflow_near",
                    "native_transfer_count", "wrapped_transfer_count", "total_transfer_count",
                )
            }
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{path.name} observation {index} is invalid") from exc
        if day.isoformat() != day_text:
            raise ValueError(f"{path.name} observation {index} has an invalid date")
        sender = item.get("sender")
        if not isinstance(sender, str) or not sender.strip():
            raise ValueError(f"{path.name} observation {index} has an invalid sender")
        key = (day, transfer_type, sender)
        if key in rows:
            raise ValueError(f"{path.name} has duplicate observation {key}")
        rows[key] = {"sender": sender, **values}
    return rows


def _period_rows(rows: dict[tuple[date, str, str], dict[str, Any]], period: str) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    with localcontext() as context:
        context.prec = 60
        for (day, transfer_type, _sender), values in sorted(rows.items()):
            period_key = day.isoformat() if period == "daily" else period_bounds(day, period)[0]
            group_key = (period_key, transfer_type)
            group = groups.setdefault(group_key, {
                "period": period_key,
                "date": day.isoformat(),
                "transfer_type": transfer_type,
                "native_inflow_near": Decimal(0),
                "wrapped_inflow_near": Decimal(0),
                "total_inflow_near": Decimal(0),
                "native_transfer_count": Decimal(0),
                "wrapped_transfer_count": Decimal(0),
                "total_transfer_count": Decimal(0),
            })
            group["date"] = day.isoformat()
            for field in (
                "native_inflow_near", "wrapped_inflow_near", "total_inflow_near",
                "native_transfer_count", "wrapped_transfer_count", "total_transfer_count",
            ):
                group[field] += values[field]
    return sorted(groups.values(), key=lambda row: (row["period"], row["transfer_type"]))


def add_buyback_analytics(
    normalized_root: Path,
    output_dir: Path,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Write daily/period transfer analytics and add latest RPC balance metrics."""

    normalized_root = Path(normalized_root)
    output_dir = Path(output_dir)
    transfer_path = normalized_root / BUYBACK_TRANSFERS_PATH
    transfer_rows = _load_transfer_rows(transfer_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for period in PERIODS:
        document = {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "metric": {
                "unit": "NEAR",
                "frequency": period,
                "aggregation": "sum_by_transfer_type",
                "transfer_types": sorted({key[1] for key in transfer_rows}),
            },
            "observations": _period_rows(transfer_rows, period),
        }
        (output_dir / f"{period}_buyback_transfers.json").write_text(
            validate_json(document), encoding="utf-8"
        )

    breakdown: dict[str, Decimal] = {}
    with localcontext() as context:
        context.prec = 60
        for (_, transfer_type, _sender), values in transfer_rows.items():
            breakdown[transfer_type] = (
                breakdown.get(transfer_type, Decimal(0)) + values["total_inflow_near"]
            )
    breakdown_document = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "metric": {
            "unit": "NEAR",
            "aggregation": "cumulative_sum_over_available_history_by_transfer_type",
            "transfer_types": sorted(breakdown),
        },
        "observations": [
            {
                "transfer_type": transfer_type,
                "total_inflow_near": value,
            }
            for transfer_type, value in sorted(breakdown.items())
        ],
    }
    breakdown_path = output_dir / "buyback_transfer_type_breakdown.json"
    breakdown_path.write_text(validate_json(breakdown_document), encoding="utf-8")

    metrics = snapshot.setdefault("metrics", {})
    balance_path = normalized_root / BUYBACK_BALANCE_PATH
    metrics["buyback_wallet_balance_near"] = None
    metrics["buyback_wallet_balance_date"] = None
    metrics["buyback_wallet_locked_near"] = None
    balance_status = "unavailable"
    if balance_path.exists():
        balance = _read_json(balance_path)
        balance_metrics = balance.get("metrics") if isinstance(balance, dict) else None
        if not isinstance(balance_metrics, dict):
            raise ValueError("buyback wallet balance metrics must be an object")
        amount = balance_metrics.get("balance_near")
        locked = balance_metrics.get("locked_near")
        metrics["buyback_wallet_balance_near"] = _decimal(amount, "balance_near")
        metrics["buyback_wallet_locked_near"] = _decimal(locked, "locked_near")
        metrics["buyback_wallet_balance_date"] = balance.get("snapshot_date")
        balance_status = "observed_finalized_rpc"

    return {
        "transfer_observations": len(transfer_rows),
        "transfer_status": "observed" if transfer_rows else "unavailable",
        "balance_status": balance_status,
        "latest_transfer_date": max((day for day, _, _ in transfer_rows), default=None),
        "analytics_path": output_dir / "daily_buyback_transfers.json",
        "breakdown_path": breakdown_path,
    }
