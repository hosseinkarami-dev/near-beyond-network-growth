"""Net and estimated gross issuance analytics, separate from supply charts."""

from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Any

from analytics.periods import CHART_PERIODS, period_bounds


FLOW_PERIOD_DAYS = (30, 90, 365)


def _ratio_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * Decimal(100)


def _chart_periods(rows: dict[date, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    recent = list(rows.items())[-365:]
    for period in CHART_PERIODS:
        groups: dict[str, list[tuple[date, dict[str, Any]]]] = {}
        for day, row in recent:
            key = day.isoformat() if period == "daily" else period_bounds(day, period)[0]
            groups.setdefault(key, []).append((day, row))
        observations = []
        for key, group in groups.items():
            sums = {}
            for field in (
                "net_issuance_near", "gross_issuance_near", "net_burn_near", "net_issuance_usd",
                "gross_issuance_usd",
            ):
                values = [row.get(field) for _, row in group]
                sums[field] = sum(values, Decimal(0)) if all(v is not None for v in values) else None
            net_burn_values = [row.get("net_burn_near") for _, row in group]
            net_burn_total = sum(net_burn_values, Decimal(0)) if all(v is not None for v in net_burn_values) else None
            sums["burn_coverage_pct"] = _ratio_pct(net_burn_total, sums["gross_issuance_near"])
            observations.append({
                "period": key,
                "period_start": group[0][0].isoformat(),
                "period_end": group[-1][0].isoformat(),
                "date": group[-1][0].isoformat(),
                **sums,
            })
        output[period] = observations
    return output


def _window_metrics(
    supplies: dict[date, dict[str, Decimal | None]],
    daily_supply_metrics: dict[date, dict[str, Decimal | None]],
    burn_rows: dict[date, dict[str, Any]],
    days: int,
) -> dict[str, Decimal | int | None]:
    if not supplies:
        return {}
    end = next(reversed(supplies))
    start = end - timedelta(days=days)
    start_supply = supplies.get(start, {}).get("total_supply")
    end_supply = supplies[end].get("total_supply")
    change = end_supply - start_supply if start_supply is not None and end_supply is not None else None
    growth = change / start_supply * 100 if change is not None and start_supply and start_supply > 0 else None
    annualized = None
    if start_supply is not None and end_supply is not None and start_supply > 0 and end_supply >= 0:
        with localcontext() as context:
            context.prec = 50
            annualized = ((end_supply / start_supply) ** (Decimal(365) / Decimal(days)) - 1) * 100

    supply_interval = [start + timedelta(days=i) for i in range(1, days + 1)]
    net_changes = [
        daily_supply_metrics.get(day, {}).get("daily_net_supply_change_near")
        for day in supply_interval
    ]

    # Flow metrics must stop at the latest day with both supply change and burn.
    # The latest supply snapshot can arrive before that day's burn data is complete.
    complete_flow_days = [
        day for day, burn in burn_rows.items()
        if day <= end
        and burn.get("net_burn_near") is not None
        and daily_supply_metrics.get(day, {}).get("net_issuance_near") is not None
    ]
    flow_end = max(complete_flow_days, default=None)
    flow_start = flow_end - timedelta(days=days) if flow_end is not None else None
    flow_start_supply = supplies.get(flow_start, {}).get("total_supply") if flow_start else None
    flow_interval = (
        [flow_start + timedelta(days=i) for i in range(1, days + 1)]
        if flow_start is not None else []
    )
    net_burn = [burn_rows.get(day, {}).get("net_burn_near") for day in flow_interval]
    gross_burn = [burn_rows.get(day, {}).get("gross_burn_near") for day in flow_interval]
    issuance = [daily_supply_metrics.get(day, {}).get("net_issuance_near") for day in flow_interval]
    has_complete_flow_window = len(flow_interval) == days and flow_start_supply is not None
    burn_total = (
        sum(net_burn, Decimal(0))
        if has_complete_flow_window and all(v is not None for v in net_burn) else None
    )
    gross_burn_total = (
        sum(gross_burn, Decimal(0))
        if has_complete_flow_window and all(v is not None for v in gross_burn) else None
    )
    issuance_total = (
        sum(issuance, Decimal(0))
        if has_complete_flow_window and all(v is not None for v in issuance) else None
    )
    gross_issuance = issuance_total + burn_total if issuance_total is not None and burn_total is not None else None
    gross_issuance_pct = _ratio_pct(gross_issuance, flow_start_supply)
    return {
        "net_supply_change_near": change,
        "net_supply_growth_pct": growth,
        "net_inflation_annualized_pct": annualized,
        "deflationary_days": sum(1 for v in net_changes if v is not None and v < 0) if all(v is not None for v in net_changes) else None,
        "net_burn_near": burn_total,
        "gross_burn_near": gross_burn_total,
        "gross_issuance_near": gross_issuance,
        "gross_issuance_pct": gross_issuance_pct,
        "gross_issuance_annualized_pct": gross_issuance_pct * Decimal(365) / Decimal(days) if gross_issuance_pct is not None else None,
        "burn_offset_pct": _ratio_pct(burn_total, gross_issuance),
    }


def build_issuance_analytics(
    supplies: dict[date, dict[str, Decimal | None]],
    daily_supply_metrics: dict[date, dict[str, Decimal | None]],
    burn_rows: dict[date, dict[str, Any]],
    prices: dict[date, Decimal],
    *,
    network: str | None,
    updated_at: str | None,
) -> tuple[dict[date, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rows: dict[date, dict[str, Any]] = {}
    first_burn_date = next((
        day for day, burn in burn_rows.items()
        if burn.get("net_burn_near") is not None
        and daily_supply_metrics.get(day, {}).get("daily_net_supply_change_near") is not None
    ), None)
    for day, supply_metrics in daily_supply_metrics.items():
        if first_burn_date is None or day < first_burn_date:
            continue
        burn = burn_rows.get(day, {})
        net_issuance = supply_metrics.get("daily_net_supply_change_near")
        net_burn = burn.get("net_burn_near")
        gross_issuance = net_issuance + net_burn if net_issuance is not None and net_burn is not None else None
        price = prices.get(day)
        net_issuance_usd = net_issuance * price if net_issuance is not None and price is not None else None
        gross_issuance_usd = gross_issuance * price if gross_issuance is not None and price is not None else None
        net_burn_usd = burn.get("net_burn_usd")
        rows[day] = {
            "net_issuance_near": net_issuance,
            "gross_issuance_near": gross_issuance,
            "net_issuance_usd": net_issuance_usd,
            "gross_issuance_usd": gross_issuance_usd,
            "net_burn_near": net_burn,
            "net_burn_usd": net_burn_usd,
            "burn_coverage_pct": _ratio_pct(net_burn, gross_issuance),
            "burn_offset_pct": _ratio_pct(net_burn, gross_issuance),
        }

    metrics = {}
    for days in FLOW_PERIOD_DAYS:
        suffix = f"{days}d"
        window = _window_metrics(supplies, daily_supply_metrics, burn_rows, days)
        metrics.update({
            f"net_supply_change_{suffix}_near": window.get("net_supply_change_near"),
            f"net_supply_growth_{suffix}_pct": window.get("net_supply_growth_pct"),
            f"net_inflation_{suffix}_annualized_pct": window.get("net_inflation_annualized_pct"),
            f"deflationary_days_{suffix}": window.get("deflationary_days"),
            f"net_burn_{suffix}_near": window.get("net_burn_near"),
            f"gross_burn_{suffix}_near": window.get("gross_burn_near"),
            f"gross_issuance_{suffix}_near": window.get("gross_issuance_near"),
            f"gross_issuance_{suffix}_pct": window.get("gross_issuance_pct"),
            f"gross_issuance_{suffix}_annualized_pct": window.get("gross_issuance_annualized_pct"),
            f"burn_offset_{suffix}_pct": window.get("burn_offset_pct"),
        })

    document = {
        "schema_version": "1.0.0",
        "network": network,
        "updated_at": updated_at,
        "metric": {
            "unit": "NEAR",
            "net_issuance_formula": "total_supply(D) - total_supply(D-1)",
            "estimated_gross_issuance_formula": "net_issuance_near + net_burn_near",
            "burn_coverage_formula": "net_burn_near / estimated_gross_issuance_near * 100",
            "period_aggregation": "sum daily flow values within each calendar period; not cumulative across periods",
        },
        "items": [
            {"date": day.isoformat(), **{field: values[field] for field in (
                "net_issuance_near", "gross_issuance_near", "net_issuance_usd",
                "gross_issuance_usd", "net_burn_near", "burn_coverage_pct", "burn_offset_pct",
            )}}
            for day, values in rows.items()
        ],
        "periods": _chart_periods(rows),
        "data_quality": {
            "issuance_start_date": next(iter(rows)).isoformat() if rows else None,
            "gross_issuance_observations": sum(1 for row in rows.values() if row["gross_issuance_near"] is not None),
        },
    }
    return rows, document, metrics

