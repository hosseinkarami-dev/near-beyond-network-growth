"""Build tokenomics price history and snapshot from normalized source data."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any

from analytics.periods import CALENDAR_PERIODS, CHART_PERIODS, period_bounds
from analytics.tokenomics_burn import (
    PROTOCOL_V87_ZERO_REWARDS_FROM,
    build_burn_analytics,
)
from analytics.tokenomics_issuance import build_issuance_analytics
from analytics.tokenomics_buybacks import add_buyback_analytics
from analytics.validators import build_validator_analytics
from paths import ANALYTICS_DATA_DIR, NORMALIZED_DATA_DIR
from units import YOCTO_PER_NEAR
from validation import validate_json


NORMALIZED_ROOT = NORMALIZED_DATA_DIR
ANALYTICS_TOKENOMICS_DIR = ANALYTICS_DATA_DIR / "tokenomics"
TOKENOMICS_STATS_PATH = Path("nearblocks/stats/tokenomics/summary.json")
VALIDATORS_INFO_PATH = Path("nearblocks/validators/summary.json")
VALIDATORS_LIST_PATH = Path("nearblocks/validators/validators.json")
PRICE_HISTORY_PATH = Path("binance/near_price/nearusdt_1d_close_price.json")
DAILY_SUPPLY_PATH = Path("bigquery/daily_supply.json")
DAILY_GROSS_BURN_PATH = Path("bigquery/daily_gross_burn.json")
CONTRACT_REWARD_EVENT_AUDIT_PATH = Path("bigquery/contract_reward_event_audit.json")
DAILY_ACTIVE_VALIDATOR_STAKE_PATH = Path("fastnear/validators/daily_active_validator_stake.json")
SUPPLY_PERIODS = CALENDAR_PERIODS
PRICE_METRIC_QUANTUM = Decimal("0.00000001")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _load_daily_prices(path: Path) -> dict[date, Decimal]:
    document = _read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("observations"), list):
        raise ValueError(f"{path.name} must be a normalized document with observations")
    if document.get("market", {}).get("symbol") != "NEARUSDT":
        raise ValueError(f"{path.name} must contain the NEARUSDT market")
    if document.get("metric", {}).get("unit") != "USDT":
        raise ValueError(f"{path.name} must contain prices in USDT")
    timing = document.get("time")
    if not isinstance(timing, dict) or timing.get("timezone") != "UTC" \
            or timing.get("timestamp_unit") != "milliseconds":
        raise ValueError(f"{path.name} must declare UTC dates and millisecond timestamps")

    prices: dict[date, Decimal] = {}
    epoch = date(1970, 1, 1)
    for index, observation in enumerate(document["observations"]):
        if not isinstance(observation, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = observation["date"]
            day = date.fromisoformat(date_text)
            value = Decimal(str(observation["price"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{path.name} observation {index} has an invalid date or price") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"{path.name} observation {index} date must use YYYY-MM-DD")
        timestamp = observation.get("timestamp")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError(f"{path.name} observation {index} timestamp must be an integer")
        if timestamp != (day - epoch).days * 86_400_000:
            raise ValueError(f"{path.name} observation {index} timestamp does not match its date")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{path.name} observation {index} price must be positive and finite")
        if day in prices:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        prices[day] = value
    if not prices:
        raise ValueError(f"{path.name} contains no price observations")
    return dict(sorted(prices.items()))


def _load_daily_active_validator_stake(path: Path) -> dict[date, dict[str, Any]]:
    """Convert normalized exact YoctoNEAR daily stake totals to NEAR."""
    document = _read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError(f"{path.name} must be a normalized document with items")

    observations: dict[date, dict[str, Any]] = {}
    for index, item in enumerate(document["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"{path.name} item {index} must be an object")
        try:
            date_text = item["date"]
            day = date.fromisoformat(date_text)
            total_stake_text = item["total_active_stake_yocto"]
            block_height = int(item["block_height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path.name} item {index} is missing date, height, or validators") from exc
        if day.isoformat() != date_text or day in observations:
            raise ValueError(f"{path.name} item {index} has an invalid or duplicate date")
        if not isinstance(total_stake_text, str) or not total_stake_text.isdigit():
            raise ValueError(f"{path.name} item {index} total stake must be an integer string")
        total_stake_yocto = int(total_stake_text)

        with localcontext() as context:
            context.prec = 50
            total_stake_near = Decimal(total_stake_yocto) / Decimal(YOCTO_PER_NEAR)
        observations[day] = {
            "block_height": block_height,
            "total_active_stake_yocto": str(total_stake_yocto),
            "total_active_stake_near": total_stake_near,
        }
    return dict(sorted(observations.items()))


def _price_rows(prices: dict[date, Decimal]) -> list[dict[str, Any]]:
    rows = []
    for day, price in prices.items():
        row: dict[str, Any] = {"date": day.isoformat(), "near_price": price}
        for length, field in ((7, "moving_average_7d"), (30, "moving_average_30d")):
            window = [day - timedelta(days=offset) for offset in range(length - 1, -1, -1)]
            average = (
                sum((prices[item] for item in window), Decimal(0)) / Decimal(length)
                if all(item in prices for item in window) else None
            )
            row[field] = average.quantize(PRICE_METRIC_QUANTUM, rounding=ROUND_HALF_UP) if average is not None else None
        rows.append(row)
    return rows


def _load_daily_supply(path: Path) -> dict[date, dict[str, Decimal | None]]:
    document = _read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("observations"), list):
        raise ValueError(f"{path.name} must be a normalized document with observations")
    metric = document.get("metric")
    timing = document.get("time")
    if not isinstance(metric, dict) or metric.get("unit") != "NEAR" \
            or metric.get("aggregation") != "period_end_snapshot":
        raise ValueError(f"{path.name} must contain period-end NEAR supply metrics")
    if not isinstance(timing, dict) or timing.get("timezone") != "UTC" \
            or timing.get("timestamp_unit") != "milliseconds":
        raise ValueError(f"{path.name} must declare UTC dates and millisecond timestamps")
    supplies: dict[date, dict[str, Decimal]] = {}
    for index, row in enumerate(document["observations"]):
        if not isinstance(row, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = row["date"]
            day = date.fromisoformat(date_text)
            total = Decimal(str(row["total_supply"]))
            raw_circulating = row["circulating_supply"]
            circulating = None if raw_circulating is None else Decimal(str(raw_circulating))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{path.name} observation {index} has invalid supply data") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"{path.name} observation {index} date must use YYYY-MM-DD")
        if not total.is_finite() or (circulating is not None and not circulating.is_finite()) \
                or total < 0 or (circulating is not None and circulating < 0):
            raise ValueError(f"{path.name} observation {index} supply must be finite and non-negative")
        if day in supplies:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        supplies[day] = {"total_supply": total, "circulating_supply": circulating}
    if not supplies:
        raise ValueError(f"{path.name} contains no supply observations")
    return dict(sorted(supplies.items()))


def _load_daily_flow(path: Path, field: str) -> tuple[dict[date, Decimal], dict[str, Any]]:
    """Load a normalized BigQuery flow series, preserving decimal values."""

    document = _read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("observations"), list):
        raise ValueError(f"{path.name} must be a normalized document with observations")
    metric = document.get("metric")
    source = document.get("source")
    if not isinstance(metric, dict) or metric.get("unit") != "NEAR" \
            or metric.get("frequency") != "daily":
        raise ValueError(f"{path.name} must contain daily NEAR observations")

    observations: dict[date, Decimal] = {}
    for index, row in enumerate(document["observations"]):
        if not isinstance(row, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = row["utc_date"]
            day = date.fromisoformat(date_text)
            value = Decimal(str(row[field]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{path.name} observation {index} has invalid date or {field}") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"{path.name} observation {index} date must use YYYY-MM-DD")
        if not value.is_finite() or value < 0:
            raise ValueError(f"{path.name} observation {index} {field} must be non-negative and finite")
        if day in observations:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        observations[day] = value
    return dict(sorted(observations.items())), source if isinstance(source, dict) else {}


def _load_contract_reward_audit(
    path: Path,
) -> tuple[dict[date, Decimal], tuple[date, date] | None]:
    """Load audited rewards and the full query window used to establish zeroes."""

    document = _read_json(path)
    query_range = document.get("query_range") if isinstance(document, dict) else None
    if not isinstance(query_range, dict):
        raise ValueError(f"{path.name} must declare its complete query_range")
    try:
        start = date.fromisoformat(query_range["start_date"])
        end = date.fromisoformat(query_range["end_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} has an invalid query_range") from exc
    if start > end:
        raise ValueError(f"{path.name} query_range start is after its end")
    rewards, _ = _load_daily_flow(path, "contract_rewards_near")
    if any(day < start or day > end for day in rewards):
        raise ValueError(f"{path.name} contains observations outside its query_range")
    return rewards, (start, end)


def _ratio_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * Decimal(100)


def _supply_period_rows(
    supplies: dict[date, dict[str, Decimal]], period: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[date, dict[str, Decimal], date, date]]] = {}
    for day, values in supplies.items():
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, values, start, end))
    items = []
    for key in sorted(groups):
        last_day, last_values, start, end = groups[key][-1]
        items.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": last_day.isoformat(),
            "as_of_date": last_day.isoformat(),
            "total_supply": last_values["total_supply"],
            "circulating_supply": last_values["circulating_supply"],
        })
    return items


def _stake_supply_period_rows(
    observations: list[dict[str, Any]], period: str,
) -> list[dict[str, Any]]:
    """Return period-end snapshots; stake and supply are never summed over time."""
    if period == "daily":
        return [
            {
                "period": row["date"],
                "period_start": row["date"],
                "period_end": row["date"],
                **row,
            }
            for row in observations
        ]

    groups: dict[str, list[tuple[date, date, date, dict[str, Any]]]] = {}
    for row in observations:
        day = date.fromisoformat(row["date"])
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, start, end, row))

    items = []
    for key in sorted(groups):
        last_day, start, end, last_row = groups[key][-1]
        items.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "date": last_day.isoformat(),
            "total_active_stake_near": last_row["total_active_stake_near"],
            "total_supply": last_row["total_supply"],
            "staking_ratio_pct": last_row["staking_ratio_pct"],
        })
    return items


def _tokenomics_period_series(
    daily_rows: dict[date, dict[str, Decimal | None]],
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate supply and inflation only; burn and issuance have own datasets."""
    output: dict[str, list[dict[str, Any]]] = {}
    recent_days = list(daily_rows)[-365:]
    for period in CHART_PERIODS:
        groups: dict[str, list[tuple[date, dict[str, Decimal | None]]]] = {}
        for day in recent_days:
            key = day.isoformat() if period == "daily" else period_bounds(day, period)[0]
            groups.setdefault(key, []).append((day, daily_rows[day]))
        items = []
        for key, rows in groups.items():
            items.append({
                "period": key,
                "date": rows[-1][0].isoformat(),
                "daily_net_inflation_pct": rows[-1][1].get("daily_net_inflation_pct"),
                "net_inflation_30d_annualized_pct": rows[-1][1].get("net_inflation_30d_annualized_pct"),
            })
        output[period] = items
    return output


def build_tokenomics_analytics(
    normalized_root: Path = NORMALIZED_ROOT,
    output_dir: Path = ANALYTICS_TOKENOMICS_DIR,
) -> Path:
    """Build Tokenomics outputs exclusively from normalized datasets."""

    normalized_root = Path(normalized_root)
    output_dir = Path(output_dir)
    prices = _load_daily_prices(normalized_root / PRICE_HISTORY_PATH)
    price_rows = _price_rows(prices)
    supplies = _load_daily_supply(normalized_root / DAILY_SUPPLY_PATH)
    validator_stake_path = normalized_root / DAILY_ACTIVE_VALIDATOR_STAKE_PATH
    validator_stake_status = "unavailable"
    try:
        daily_active_validator_stake = (
            _load_daily_active_validator_stake(validator_stake_path)
            if validator_stake_path.exists() else {}
        )
        if daily_active_validator_stake:
            validator_stake_status = "observed_exact_yoctoNEAR"
    except Exception as exc:
        print(f"tokenomics daily active validator stake: unavailable; {type(exc).__name__}: {exc}")
        daily_active_validator_stake = {}
    gross_burn_path = normalized_root / DAILY_GROSS_BURN_PATH
    gross_burn, gross_burn_source = (
        _load_daily_flow(gross_burn_path, "gross_tokens_burnt_near")
        if gross_burn_path.exists() else ({}, {})
    )
    contract_rewards_path = normalized_root / CONTRACT_REWARD_EVENT_AUDIT_PATH
    contract_rewards, contract_reward_audit_range = (
        _load_contract_reward_audit(contract_rewards_path)
        if contract_rewards_path.exists() else ({}, None)
    )
    tokenomics_path = normalized_root / TOKENOMICS_STATS_PATH
    tokenomics_summary = _read_json(tokenomics_path)
    normalized_metrics = tokenomics_summary.get("metrics")
    if not isinstance(normalized_metrics, dict):
        raise ValueError("tokenomics summary metrics must be an object")
    metrics = {
        field: metric["value"]
        for field, metric in normalized_metrics.items()
        if isinstance(metric, dict) and "value" in metric
    }

    latest_price = price_rows[-1]
    metrics["near_price"] = {
        "value": latest_price["near_price"],
        "moving_average_7d": latest_price["moving_average_7d"],
        "moving_average_30d": latest_price["moving_average_30d"],
    }
    latest_supply_day, latest_supply = next(reversed(supplies.items()))
    metrics["total_supply"] = latest_supply["total_supply"]
    metrics["circulating_supply"] = latest_supply["circulating_supply"]
    circulating = latest_supply["circulating_supply"]
    metrics["non_circulating_supply_near"] = (
        latest_supply["total_supply"] - circulating if circulating is not None else None
    )
    metrics["circulating_supply_ratio_pct"] = _ratio_pct(
        circulating, latest_supply["total_supply"]
    )

    metrics.update({
        "total_staked": None,
        "current_validators_count": None,
        "total_validators_count": None,
        "total_active_stake_as_of_date": None,
    })
    validators_summary_metrics = {}
    validators_path = normalized_root / VALIDATORS_INFO_PATH
    if validators_path.exists():
        validators_summary = _read_json(validators_path)
        validators_summary_metrics = validators_summary.get("metrics")
        if not isinstance(validators_summary_metrics, dict):
            raise ValueError("validator summary metrics must be an object")
        validators_updated_at = validators_summary.get("updated_at")
        if isinstance(validators_updated_at, str):
            try:
                metrics["total_active_stake_as_of_date"] = datetime.fromisoformat(
                    validators_updated_at.replace("Z", "+00:00")
                ).date().isoformat()
            except ValueError:
                pass
        for field in ("total_staked", "current_validators_count", "total_validators_count"):
            metric = validators_summary_metrics.get(field)
            value = metric.get("value") if isinstance(metric, dict) else None
            metrics[field] = value
    total_active_stake = metrics.get("total_staked")
    total_active_stake = Decimal(str(total_active_stake)) if total_active_stake is not None else None
    current_validators = metrics.get("current_validators_count")
    validator_analytics = build_validator_analytics(
        normalized_root / VALIDATORS_LIST_PATH,
        circulating,
        network_total_stake=total_active_stake,
        active_validators_count=int(current_validators) if current_validators is not None else None,
    )
    metrics.update(validator_analytics["metrics"])
    # Keep the summary endpoint values authoritative for network totals.
    if total_active_stake is not None:
        metrics["total_active_stake"] = total_active_stake
        metrics["staking_ratio"] = _ratio_pct(total_active_stake, circulating)
    if current_validators is not None:
        metrics["active_validators_count"] = current_validators

    daily_rows: dict[date, dict[str, Decimal | None]] = {}
    all_supply_dates = list(supplies)
    for offset in range((all_supply_dates[-1] - all_supply_dates[0]).days + 1):
        day = all_supply_dates[0] + timedelta(days=offset)
        values = supplies.get(day)
        if values is None:
            # A null row creates a visible chart gap without inventing a value.
            daily_rows[day] = {
                "total_supply": None,
                "circulating_supply": None,
                "non_circulating_supply_near": None,
                "circulating_supply_ratio_pct": None,
                "daily_net_supply_change_near": None,
                "net_issuance_near": None,
                "daily_net_inflation_pct": None,
                "net_inflation_30d_annualized_pct": None,
            }
            continue
        previous = supplies.get(day - timedelta(days=1))
        previous_total = previous.get("total_supply") if previous else None
        total = values.get("total_supply")
        change = total - previous_total if total is not None and previous_total is not None else None
        current_circulating = values.get("circulating_supply")
        net_inflation = _ratio_pct(change, previous_total)
        start_30d = supplies.get(day - timedelta(days=30), {}).get("total_supply")
        inflation_30d = None
        if start_30d is not None and total is not None and start_30d > 0 and total >= 0:
            with localcontext() as context:
                context.prec = 50
                inflation_30d = ((total / start_30d) ** (Decimal(365) / Decimal(30)) - 1) * 100
        daily_rows[day] = {
            "total_supply": total,
            "circulating_supply": current_circulating,
            "non_circulating_supply_near": (
                total - current_circulating
                if total is not None and current_circulating is not None else None
            ),
            "circulating_supply_ratio_pct": _ratio_pct(current_circulating, total),
            "daily_net_supply_change_near": change,
            "net_issuance_near": change,
            "daily_net_inflation_pct": net_inflation,
            "net_inflation_30d_annualized_pct": inflation_30d,
        }

    burn_rows, burn_document, reward_zero_counts = build_burn_analytics(
        supplies,
        gross_burn,
        contract_rewards,
        contract_reward_audit_range,
        prices,
        network=None,
        updated_at=None,
    )
    issuance_rows, issuance_document, flow_metrics = build_issuance_analytics(
        supplies,
        daily_rows,
        burn_rows,
        prices,
        network=None,
        updated_at=None,
    )
    for document in (burn_document, issuance_document):
        document["network"] = tokenomics_summary.get("network")
        document["updated_at"] = tokenomics_summary.get("updated_at")

    metrics.update(flow_metrics)
    latest_net_burn_day = next(
        (day for day in reversed(burn_rows) if burn_rows[day]["net_burn_near"] is not None),
        None,
    )
    latest_burn_coverage_day = next(
        (day for day in reversed(issuance_rows) if issuance_rows[day]["burn_coverage_pct"] is not None),
        None,
    )
    metrics["latest_net_burn_near"] = (
        burn_rows[latest_net_burn_day]["net_burn_near"] if latest_net_burn_day else None
    )
    metrics["latest_net_burn_date"] = latest_net_burn_day.isoformat() if latest_net_burn_day else None
    metrics["latest_burn_coverage_pct"] = (
        issuance_rows[latest_burn_coverage_day]["burn_coverage_pct"] if latest_burn_coverage_day else None
    )
    metrics["latest_burn_coverage_date"] = latest_burn_coverage_day.isoformat() if latest_burn_coverage_day else None
    metrics["current_net_inflation_30d_annualized_pct"] = metrics.get(
        "net_inflation_30d_annualized_pct"
    )
    metrics["current_net_inflation_3m_annualized_pct"] = metrics.get(
        "net_inflation_90d_annualized_pct"
    )
    metrics["current_net_inflation_1y_annualized_pct"] = metrics.get(
        "net_inflation_365d_annualized_pct"
    )

    common_days = sorted(set(prices).intersection(supplies))
    if not common_days:
        raise ValueError("NEAR price and supply history have no matching UTC dates for FDV")
    fdv_day = common_days[-1]
    fdv = prices[fdv_day] * supplies[fdv_day]["total_supply"]
    metrics["fdv_usd"] = fdv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    latest_supply_date = latest_supply_day.isoformat()
    latest_supply_change = daily_rows[latest_supply_day]["daily_net_supply_change_near"]
    metrics["daily_net_supply_change_near"] = latest_supply_change
    metrics["daily_net_inflation_pct"] = daily_rows[latest_supply_day]["daily_net_inflation_pct"]
    latest_stake_day = next(reversed(daily_active_validator_stake), None)
    metrics["historical_active_validator_stake_near"] = (
        daily_active_validator_stake[latest_stake_day]["total_active_stake_near"]
        if latest_stake_day is not None else None
    )
    metrics["historical_active_validator_stake_date"] = (
        latest_stake_day.isoformat() if latest_stake_day is not None else None
    )

    def coverage(values: dict[date, Any], status: str = "observed") -> dict[str, Any]:
        if not values:
            return {"data_status": status, "observations": 0, "start_date": None, "latest_date": None}
        first, last = next(iter(values)), next(reversed(values))
        expected_days = (last - first).days + 1
        return {
            "data_status": status,
            "observations": len(values),
            "start_date": first.isoformat(),
            "latest_date": last.isoformat(),
            "missing_calendar_dates": expected_days - len(values),
        }

    negative_issuance_dates = [
        day.isoformat() for day, row in issuance_rows.items()
        if row["gross_issuance_near"] is not None
        and row["gross_issuance_near"] < 0
    ]
    unusual_burn_offset_dates = [
        day.isoformat() for day, row in issuance_rows.items()
        if row["burn_offset_pct"] is not None
        and (row["burn_offset_pct"] < 0 or row["burn_offset_pct"] > 100)
    ]
    data_quality = {
        "daily_supply": coverage(supplies, "observed_approximate_float64"),
        "daily_active_validator_stake": coverage(
            daily_active_validator_stake,
            validator_stake_status,
        ),
        "daily_gross_burn": coverage(gross_burn),
        "contract_reward_event_audit": coverage(contract_rewards, "audited_valid_reward_events"),
        "contract_rewards_zero_filled": {
            "policy": "zero for absent events within the complete audit range and after protocol version 87",
            "protocol_v87_zero_from": PROTOCOL_V87_ZERO_REWARDS_FROM.isoformat(),
            **reward_zero_counts,
        },
        "estimated_gross_issuance": {
            "status": "estimated",
            "definition": "daily net issuance plus net burn (tokens_burnt minus contract rewards)",
            "limitation": "Null when supply change or gross burn is missing, and before reward audit coverage when contract rewards are unknown; reconciliation is approximate because total supply source values use float64 and may include unmodeled supply adjustments.",
            "negative_daily_observation_count": len(negative_issuance_dates),
            "negative_daily_observation_dates": negative_issuance_dates[:30],
            "burn_offset_outside_0_100_count": len(unusual_burn_offset_dates),
            "burn_offset_outside_0_100_dates": unusual_burn_offset_dates[:30],
        },
    }

    snapshot = {
        "schema_version": "1.0.0",
        "network": tokenomics_summary.get("network"),
        "updated_at": tokenomics_summary.get("updated_at"),
        "metrics": metrics,
        "validators": validator_analytics["validators"],
        "data_quality": data_quality,
        "metric_types": {
            "daily_net_supply_change_near": "derived_from_observed_total_supply",
            "historical_active_validator_stake_near": "sum_current_validators_stake_in_exact_yoctoNEAR_then_convert_to_NEAR",
            "daily_net_burn_near": "tokens_burnt_minus_contract_rewards",
            "daily_net_inflation_pct": "derived_from_observed_total_supply",
        "gross_issuance_near": "estimated_from_net_supply_change_plus_observed_net_burn",
        },
    }
    buyback_quality = add_buyback_analytics(normalized_root, output_dir, snapshot)
    snapshot["data_quality"]["buyback_transfers"] = {
        "data_status": buyback_quality["transfer_status"],
        "observations": buyback_quality["transfer_observations"],
        "latest_date": (
            buyback_quality["latest_transfer_date"].isoformat()
            if buyback_quality["latest_transfer_date"] else None
        ),
    }
    snapshot["data_quality"]["buyback_wallet_balance"] = {
        "data_status": buyback_quality["balance_status"],
        "snapshot_date": metrics["buyback_wallet_balance_date"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_document = {
        "schema_version": "1.0.0",
        "network": tokenomics_summary.get("network"),
        "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
        "observations": price_rows,
    }
    daily_path = output_dir / "daily_near_price.json"
    daily_path.write_text(validate_json(daily_document), encoding="utf-8")

    daily_tokenomics_document = {
        "schema_version": "1.0.0",
        "network": tokenomics_summary.get("network"),
        "time": {
            "timezone": "UTC",
            "date_convention": "UTC calendar date; daily supply uses the normalized period-end snapshot date",
        },
        "metric": {"scope": "supply_and_inflation_only"},
        "items": [
            {
                "date": day.isoformat(),
                **{field: values.get(field) for field in (
                    "total_supply", "circulating_supply", "non_circulating_supply_near",
                    "circulating_supply_ratio_pct", "daily_net_inflation_pct",
                    "net_inflation_30d_annualized_pct",
                )},
            }
            for day, values in daily_rows.items()
        ],
    }
    (output_dir / "daily_tokenomics.json").write_text(
        validate_json(daily_tokenomics_document), encoding="utf-8"
    )
    for period, items in _tokenomics_period_series(daily_rows).items():
        if period == "daily":
            continue
        period_document = {
            "schema_version": "1.0.0",
            "network": tokenomics_summary.get("network"),
            "period": period,
            "metric": {"scope": "supply_and_inflation_only"},
            "items": items,
        }
        (output_dir / f"{period}_tokenomics.json").write_text(
            validate_json(period_document), encoding="utf-8"
        )

    burn_periods = burn_document.pop("periods", {})
    (output_dir / "daily_burn.json").write_text(
        validate_json(burn_document), encoding="utf-8"
    )
    for period, items in burn_periods.items():
        if period == "daily":
            continue
        (output_dir / f"{period}_burn.json").write_text(validate_json({
            "schema_version": "1.0.0",
            "network": burn_document.get("network"),
            "period": period,
            "metric": burn_document.get("metric"),
            "items": items,
        }), encoding="utf-8")

    issuance_periods = issuance_document.pop("periods", {})
    (output_dir / "daily_issuance.json").write_text(
        validate_json(issuance_document), encoding="utf-8"
    )
    for period, items in issuance_periods.items():
        if period == "daily":
            continue
        (output_dir / f"{period}_issuance.json").write_text(validate_json({
            "schema_version": "1.0.0",
            "network": issuance_document.get("network"),
            "period": period,
            "metric": issuance_document.get("metric"),
            "items": items,
        }), encoding="utf-8")

    daily_supply_document = {
        "schema_version": "1.0.0",
        "network": tokenomics_summary.get("network"),
        "metric": {"unit": "NEAR", "aggregation": "daily_snapshot",
                   "source_precision": "approximate_float64"},
        "items": [
            {"date": day.isoformat(), **values}
            for day, values in supplies.items()
        ],
    }
    (output_dir / "daily_supply.json").write_text(validate_json(daily_supply_document), encoding="utf-8")

    daily_active_stake_document = {
        "schema_version": "1.0.0",
        "network": tokenomics_summary.get("network"),
        "data_status": "observed" if daily_active_validator_stake else "unavailable",
        "metric": {
            "unit": "percent",
            "formula": "total_active_stake_near / total_supply * 100",
            "aggregation": "sum_current_validators_per_daily_block",
            "precision": "exact_integer_yoctoNEAR_before_conversion",
        },
        "items": [
            {
                "date": day.isoformat(),
                "block_height": values["block_height"],
                "total_active_stake_near": values["total_active_stake_near"],
                "total_supply": supplies.get(day, {}).get("total_supply"),
                "staking_ratio_pct": _ratio_pct(
                    values["total_active_stake_near"],
                    supplies.get(day, {}).get("total_supply"),
                ),
            }
            for day, values in daily_active_validator_stake.items()
        ],
    }
    daily_active_stake_items = daily_active_stake_document["items"]
    daily_active_stake_document["items"] = _stake_supply_period_rows(
        daily_active_stake_items, "daily"
    )
    (output_dir / "daily_active_validator_stake.json").write_text(
        validate_json(daily_active_stake_document), encoding="utf-8"
    )
    for period in CHART_PERIODS:
        if period == "daily":
            continue
        period_document = {
            "schema_version": "1.0.0",
            "network": tokenomics_summary.get("network"),
            "period": period,
            "data_status": "observed" if daily_active_validator_stake else "unavailable",
            "metric": daily_active_stake_document["metric"],
            "items": _stake_supply_period_rows(daily_active_stake_items, period),
        }
        (output_dir / f"{period}_active_validator_stake.json").write_text(
            validate_json(period_document), encoding="utf-8"
        )
    for period in SUPPLY_PERIODS:
        period_document = {
            "schema_version": "1.0.0",
            "network": tokenomics_summary.get("network"),
            "period": period,
            "metric": {"unit": "NEAR", "aggregation": "period_end_snapshot",
                       "source_precision": "approximate_float64"},
            "items": _supply_period_rows(supplies, period),
        }
        (output_dir / f"{period}_supply.json").write_text(validate_json(period_document), encoding="utf-8")

    output_path = output_dir / "snapshot.json"
    output_path.write_text(validate_json(snapshot), encoding="utf-8")
    (output_dir / "daily_metrics.json").unlink(missing_ok=True)
    from console_ui import console
    console.print("[green]OK[/green] Tokenomics [dim]· snapshot and daily series ready[/dim]")
    return output_path
