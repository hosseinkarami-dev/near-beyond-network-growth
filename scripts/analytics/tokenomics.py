"""Build tokenomics price history and snapshot from normalized source data."""

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any

from common import PROJECT_ROOT
from analytics.periods import period_bounds
from validation import validate_json


NORMALIZED_ROOT = PROJECT_ROOT / "data" / "normalized"
ANALYTICS_TOKENOMICS_DIR = PROJECT_ROOT / "data" / "analytics" / "tokenomics"
TOKENOMICS_STATS_PATH = Path("nearblocks/stats/tokenomics/summary.json")
PRICE_HISTORY_PATH = Path("binance/near_price/nearusdt_1d_close_price.json")
DAILY_SUPPLY_PATH = Path("bigquery/daily_supply.json")
DAILY_GROSS_BURN_PATH = Path("bigquery/daily_gross_burn.json")
DAILY_CONTRACT_REWARDS_PATH = Path("bigquery/daily_contract_rewards.json")
SUPPLY_PERIODS = ("weekly", "monthly", "quarterly", "yearly")
CHART_PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")
PRICE_METRIC_QUANTUM = Decimal("0.00000001")
FLOW_PERIOD_DAYS = (30, 90, 365)


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


def _ratio_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * Decimal(100)


def _period_supply_metrics(
    supplies: dict[date, dict[str, Decimal | None]],
    daily_rows: dict[date, dict[str, Decimal | None]],
    gross_burn: dict[date, Decimal],
    days: int,
) -> dict[str, Decimal | int | None]:
    """Calculate calendar-day window metrics ending at the latest supply date."""

    output: dict[str, Decimal | int | None] = {}
    if not supplies:
        return output
    end_date = next(reversed(supplies))
    start_date = end_date - timedelta(days=days)
    start_supply = supplies.get(start_date, {}).get("total_supply")
    end_supply = supplies[end_date].get("total_supply")
    change = end_supply - start_supply if start_supply is not None and end_supply is not None else None
    growth = _ratio_pct(change, start_supply)
    annualized = None
    if start_supply is not None and end_supply is not None and start_supply > 0 and end_supply >= 0:
        with localcontext() as context:
            context.prec = 50
            annualized = ((end_supply / start_supply) ** (Decimal(365) / Decimal(days)) - 1) * 100
    output.update(
        net_supply_change_near=change,
        net_supply_growth_pct=growth,
        net_inflation_annualized_pct=annualized,
    )

    interval_dates = [start_date + timedelta(days=offset) for offset in range(1, days + 1)]
    daily_changes = [daily_rows.get(day, {}).get("daily_net_supply_change_near") for day in interval_dates]
    output["deflationary_days"] = (
        sum(1 for value in daily_changes if value is not None and value < 0)
        if all(value is not None for value in daily_changes) else None
    )

    burn_values = [gross_burn.get(day) for day in interval_dates]
    burn_total = sum(burn_values, Decimal(0)) if all(value is not None for value in burn_values) else None
    issuance_values = [daily_rows.get(day, {}).get("gross_issuance_near") for day in interval_dates]
    issuance_total = (
        sum(issuance_values, Decimal(0))
        if all(value is not None for value in issuance_values) else None
    )
    output["gross_burn_near"] = burn_total
    output["gross_issuance_near"] = issuance_total
    output["gross_issuance_pct"] = _ratio_pct(issuance_total, start_supply)
    issuance_rate = output["gross_issuance_pct"]
    output["gross_issuance_annualized_pct"] = (
        issuance_rate * Decimal(365) / Decimal(days) if issuance_rate is not None else None
    )
    output["burn_offset_pct"] = _ratio_pct(burn_total, issuance_total)
    return output


def _contract_rewards_totals(
    observations: dict[date, Decimal], days: int,
) -> Decimal | None:
    if not observations:
        return None
    end_date = next(reversed(observations))
    start_date = end_date - timedelta(days=days - 1)
    values = [observations.get(start_date + timedelta(days=offset)) for offset in range(days)]
    return sum(values, Decimal(0)) if all(value is not None for value in values) else None


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


def _tokenomics_period_series(
    daily_rows: dict[date, dict[str, Decimal | None]], prices: dict[date, Decimal],
) -> dict[str, list[dict[str, Any]]]:
    """Precompute bounded chart buckets so the dashboard only renders values."""
    output: dict[str, list[dict[str, Any]]] = {}
    recent_days = list(daily_rows)[-365:]
    for period in CHART_PERIODS:
        groups: dict[str, list[tuple[date, dict[str, Decimal | None]]]] = {}
        for day in recent_days:
            key = day.isoformat() if period == "daily" else period_bounds(day, period)[0]
            groups.setdefault(key, []).append((day, daily_rows[day]))
        items = []
        for key, rows in groups.items():
            net_values = [row.get("net_issuance_near") for _, row in rows]
            gross_values = [row.get("gross_issuance_near") for _, row in rows]
            burn_values = [row.get("net_burn_near") for _, row in rows]
            reward_values = [row.get("contract_rewards_near") for _, row in rows]
            reward_usd_values = [row.get("contract_rewards_usd") for _, row in rows]
            burn_usd_values = [row.get("token_burn_usd") for _, row in rows]
            issuance_usd_values = [row.get("estimated_gross_issuance_usd") for _, row in rows]
            usd_values = [row.get("net_burn_near") * prices[day]
                          for day, row in rows if row.get("net_burn_near") is not None and day in prices]
            items.append({
                "period": key,
                "date": rows[-1][0].isoformat(),
                "net_issuance_near": sum(net_values, Decimal(0)) if all(v is not None for v in net_values) else None,
                "gross_issuance_near": sum(gross_values, Decimal(0)) if all(v is not None for v in gross_values) else None,
                "net_burn_near": sum(burn_values, Decimal(0)) if all(v is not None for v in burn_values) else None,
                "contract_rewards_near": sum(reward_values, Decimal(0)) if all(v is not None for v in reward_values) else None,
                "contract_rewards_usd": sum(reward_usd_values, Decimal(0)) if all(v is not None for v in reward_usd_values) else None,
                "net_burn_usd": sum(usd_values, Decimal(0)) if len(usd_values) == len(rows) else None,
                "token_burn_usd": sum(burn_usd_values, Decimal(0)) if all(v is not None for v in burn_usd_values) else None,
                "estimated_gross_issuance_usd": sum(issuance_usd_values, Decimal(0)) if all(v is not None for v in issuance_usd_values) else None,
                "burn_rate_pct": _ratio_pct(
                    sum(burn_usd_values, Decimal(0)) if all(v is not None for v in burn_usd_values) else None,
                    sum(issuance_usd_values, Decimal(0)) if all(v is not None for v in issuance_usd_values) else None,
                ),
                "net_inflation_30d_annualized_pct": rows[-1][1].get("net_inflation_30d_annualized_pct"),
            })
        output[period] = items
    return output


def build_tokenomics_analytics(
    normalized_root: Path = NORMALIZED_ROOT,
    output_dir: Path = ANALYTICS_TOKENOMICS_DIR,
    *,
    include_synthetic_demo: bool = False,
) -> Path:
    """Build Tokenomics outputs exclusively from normalized datasets."""

    normalized_root = Path(normalized_root)
    output_dir = Path(output_dir)
    prices = _load_daily_prices(normalized_root / PRICE_HISTORY_PATH)
    price_rows = _price_rows(prices)
    supplies = _load_daily_supply(normalized_root / DAILY_SUPPLY_PATH)
    gross_burn_path = normalized_root / DAILY_GROSS_BURN_PATH
    gross_burn, gross_burn_source = (
        _load_daily_flow(gross_burn_path, "gross_tokens_burnt_near")
        if gross_burn_path.exists() else ({}, {})
    )
    contract_rewards_path = normalized_root / DAILY_CONTRACT_REWARDS_PATH
    contract_rewards, contract_rewards_source = (
        _load_daily_flow(contract_rewards_path, "contract_rewards_near")
        if contract_rewards_path.exists() else ({}, {})
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
                "gross_burn_near": None,
                "contract_rewards_near": None,
                "contract_rewards_usd": None,
                "token_burn_usd": None,
                "estimated_gross_issuance_usd": None,
                "burn_rate_pct": None,
                "net_burn_near": None,
                "net_burn_rate_pct": None,
                "gross_issuance_near": None,
                "burn_offset_pct": None,
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
        rewards = contract_rewards.get(day)
        net_burn = gross_burn[day] - rewards if day in gross_burn and rewards is not None else None
        issuance = (
            change + gross_burn[day]
            if change is not None and day in gross_burn else None
        )
        burn_usd = gross_burn[day] * prices[day] if day in gross_burn and day in prices else None
        issuance_usd = issuance * prices[day] if issuance is not None and day in prices else None
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
            "gross_burn_near": gross_burn.get(day),
            "contract_rewards_near": rewards,
            "contract_rewards_usd": rewards * prices[day] if rewards is not None and day in prices else None,
            "token_burn_usd": burn_usd,
            "estimated_gross_issuance_usd": issuance_usd,
            "burn_rate_pct": _ratio_pct(burn_usd, issuance_usd),
            "net_burn_near": net_burn,
            "net_burn_rate_pct": _ratio_pct(net_burn, previous_total),
            "gross_issuance_near": issuance,
            "burn_offset_pct": _ratio_pct(burn_usd, issuance_usd),
        }

    current_period_metrics: dict[str, Any] = {}
    for period_days in FLOW_PERIOD_DAYS:
        period = _period_supply_metrics(supplies, daily_rows, gross_burn, period_days)
        suffix = f"{period_days}d"
        current_period_metrics.update({
            f"net_supply_change_{suffix}_near": period.get("net_supply_change_near"),
            f"net_supply_growth_{suffix}_pct": period.get("net_supply_growth_pct"),
            f"net_inflation_{suffix}_annualized_pct": period.get("net_inflation_annualized_pct"),
            f"deflationary_days_{suffix}": period.get("deflationary_days"),
            f"gross_burn_{suffix}_near": period.get("gross_burn_near"),
            f"gross_issuance_{suffix}_near": period.get("gross_issuance_near"),
            f"gross_issuance_{suffix}_pct": period.get("gross_issuance_pct"),
            f"gross_issuance_{suffix}_annualized_pct": period.get("gross_issuance_annualized_pct"),
            f"burn_offset_{suffix}_pct": period.get("burn_offset_pct"),
        })
    metrics.update(current_period_metrics)
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
        day.isoformat() for day, row in daily_rows.items()
        if row["gross_issuance_near"] is not None
        and row["gross_issuance_near"] < 0
    ]
    unusual_burn_offset_dates = [
        day.isoformat() for day, row in daily_rows.items()
        if row["burn_offset_pct"] is not None
        and (row["burn_offset_pct"] < 0 or row["burn_offset_pct"] > 100)
    ]
    data_quality = {
        "daily_supply": coverage(supplies, "observed_approximate_float64"),
        "daily_gross_burn": coverage(gross_burn),
        "daily_contract_rewards": coverage(contract_rewards),
        "estimated_gross_issuance": {
            "status": "estimated",
            "definition": "daily net supply change plus daily gross burn",
            "limitation": "Reconciliation is approximate because total supply source values use float64 and may include unmodeled supply adjustments.",
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
        "data_quality": data_quality,
        "metric_types": {
            "daily_net_supply_change_near": "derived_from_observed_total_supply",
            "daily_net_inflation_pct": "derived_from_observed_total_supply",
            "gross_issuance_near": "estimated_from_net_supply_change_and_gross_burn",
        },
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
        "items": [{"date": day.isoformat(), **values} for day, values in daily_rows.items()],
        "periods": _tokenomics_period_series(daily_rows, prices),
    }
    (output_dir / "daily_tokenomics.json").write_text(
        validate_json(daily_tokenomics_document), encoding="utf-8"
    )

    demo_path = output_dir / "daily_contract_rewards.json"
    if contract_rewards:
        latest_reward_date = next(reversed(contract_rewards))
        demo_summary = {"latest_daily_near": contract_rewards[latest_reward_date]}
        for days in FLOW_PERIOD_DAYS:
            demo_summary[f"total_{days}d_near"] = _contract_rewards_totals(contract_rewards, days)
        demo_document = {
            "schema_version": "1.0.0",
            "network": tokenomics_summary.get("network"),
            "unit": "NEAR",
            "updated_at": tokenomics_summary.get("updated_at"),
            "summary": demo_summary,
            "coverage": coverage(contract_rewards),
            "observations": [
                {"date": day.isoformat(), "contract_rewards_near": value}
                for day, value in contract_rewards.items()
            ],
        }
        demo_path.write_text(validate_json(demo_document), encoding="utf-8")
    else:
        demo_path.unlink(missing_ok=True)
    (output_dir / "contract_rewards_demo.json").unlink(missing_ok=True)

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
    print(f"tokenomics analytics: wrote snapshot -> {output_path}")
    (output_dir / "daily_metrics.json").unlink(missing_ok=True)
    print(f"tokenomics analytics: wrote daily metrics -> {daily_path}")
    return output_path
