"""Build Near Intents analytics from normalized DefiLlama datasets."""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from analytics.periods import CALENDAR_PERIODS, period_bounds
from paths import ANALYTICS_DATA_DIR, NORMALIZED_DATA_DIR
from validation import validate_json


NORMALIZED_ROOT = NORMALIZED_DATA_DIR / "defillama"
ANALYTICS_DIR = ANALYTICS_DATA_DIR / "near_intents"
VOLUME_DIR = Path("near_intents_dex_volume")
TVL_DIR = Path("near_intents")
PERIODS = CALENDAR_PERIODS
PROTOCOL_FLOWS = {
    "holders_revenue_usd": ("near_holders_revenue/daily_holders_revenue_breakdown.json", "protocols"),
    "revenue_usd": ("near_revenue/daily_protocol_revenue_breakdown.json", "values"),
    "gross_fees_usd": ("near_fees/daily_protocol_fees_breakdown.json", "values"),
}
TOKEN_TVL_PATH = Path("near_intents_token_breakdown/daily_tvl_by_token.json")
PRICE_PATH = Path("binance/near_price/nearusdt_1d_close_price.json")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _read_series(
    path: Path, *, latest_same_day: bool = False,
) -> tuple[dict[date, Decimal | None], dict[str, Any]]:
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list):
        raise ValueError(f"{path.name} must contain an observations array")
    metric = document.get("metric")
    if not isinstance(metric, dict) or metric.get("unit") != "USD" \
            or metric.get("frequency") != "daily":
        raise ValueError(f"{path.name} must be a daily USD series")

    rows: dict[date, Decimal | None] = {}
    timestamps: dict[date, int] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = observation["date"]
            day = date.fromisoformat(date_text)
            timestamp = observation["timestamp"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path.name} observation {index} has an invalid date or timestamp") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"{path.name} observation {index} date must use YYYY-MM-DD")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError(f"{path.name} observation {index} timestamp must be integer seconds")
        if datetime.fromtimestamp(timestamp, timezone.utc).date() != day:
            raise ValueError(f"{path.name} observation {index} timestamp does not match its UTC date")
        if day in rows:
            if not latest_same_day or timestamp == timestamps[day]:
                raise ValueError(f"{path.name} contains duplicate date/timestamp {day}")
            if timestamp < timestamps[day]:
                continue
        timestamps[day] = timestamp
        value = observation.get("value")
        if value is None:
            rows[day] = None
            continue
        try:
            amount = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"{path.name} observation {index} value must be numeric") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError(f"{path.name} observation {index} value must be finite and non-negative")
        rows[day] = amount
    return dict(sorted(rows.items())), document


def _read_protocol_flow(
    path: Path, value_field: str, *, allow_missing_protocol: bool = False,
) -> dict[date, Decimal | None]:
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list):
        raise ValueError(f"{path.name} must contain an observations array")
    metric = document.get("metric")
    if not isinstance(metric, dict) or metric.get("unit") != "USD" \
            or metric.get("frequency") != "daily":
        raise ValueError(f"{path.name} must be a daily USD protocol breakdown")
    values: dict[date, Decimal] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = observation["date"]
            day = date.fromisoformat(date_text)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path.name} observation {index} has an invalid date") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"{path.name} observation {index} date must use YYYY-MM-DD")
        if day in values:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        breakdown = observation.get(value_field)
        if not isinstance(breakdown, dict):
            raise ValueError(f"{path.name} observation {index} must contain {value_field}")
        if any(not isinstance(name, str) for name in breakdown):
            raise ValueError(f"{path.name} observation {index} protocol names must be strings")
        if "NEAR Intents" not in breakdown and not allow_missing_protocol:
            raise ValueError(f"{path.name} observation {index} has no NEAR Intents breakdown value")
        if "NEAR Intents" not in breakdown:
            values[day] = None
            continue
        # Deliberately select this protocol from the breakdown; never derive it from daily totals.
        amount = breakdown["NEAR Intents"]
        try:
            parsed = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{path.name} observation {index} has invalid NEAR Intents value") from exc
        if not parsed.is_finite() or parsed < 0:
            raise ValueError(f"{path.name} observation {index} value must be finite and non-negative")
        values[day] = parsed
    if not any(value is not None for value in values.values()):
        raise ValueError(f"{path.name} has no NEAR Intents values")
    return dict(sorted(values.items()))


def _read_near_prices(path: Path) -> dict[date, Decimal]:
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list) or document.get("market", {}).get("symbol") != "NEARUSDT":
        raise ValueError(f"{path.name} must contain NEARUSDT price observations")
    if document.get("metric", {}).get("unit") != "USDT":
        raise ValueError(f"{path.name} must contain NEARUSDT prices")
    prices: dict[date, Decimal] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = observation["date"]
            day = date.fromisoformat(date_text)
            price = Decimal(str(observation["price"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"{path.name} observation {index} has invalid price data") from exc
        if day.isoformat() != date_text or not price.is_finite() or price <= 0:
            raise ValueError(f"{path.name} observation {index} has invalid date or price")
        if day in prices:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        prices[day] = price
    if not prices:
        raise ValueError(f"{path.name} contains no NEAR price observations")
    return prices


def _usd_to_near(value: Decimal | None, price: Decimal | None) -> Decimal | None:
    if value is None or price is None or price <= 0:
        return None
    return (value / price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _read_token_tvl(path: Path) -> tuple[dict[date, dict[str, Any]], dict[str, Any]]:
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list):
        raise ValueError(f"{path.name} must contain an observations array")
    metric = document.get("metric")
    timing = document.get("time")
    if not isinstance(metric, dict) or metric.get("unit") != "USD" \
            or metric.get("aggregation") != "period_end_snapshot":
        raise ValueError(f"{path.name} must contain period-end USD token TVL snapshots")
    if not isinstance(timing, dict) or timing.get("timezone") != "UTC" \
            or timing.get("timestamp_unit") != "milliseconds":
        raise ValueError(f"{path.name} must declare UTC dates and millisecond timestamps")

    rows: dict[date, dict[str, Any]] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"{path.name} observation {index} must be an object")
        try:
            date_text = observation["date"]
            day = date.fromisoformat(date_text)
            timestamp = observation["timestamp"]
            raw_tokens = observation["tokens"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path.name} observation {index} has invalid snapshot data") from exc
        if day.isoformat() != date_text or isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError(f"{path.name} observation {index} has an invalid date or timestamp")
        if datetime.fromtimestamp(timestamp / 1000, timezone.utc).date() != day:
            raise ValueError(f"{path.name} observation {index} timestamp does not match its UTC date")
        if not isinstance(raw_tokens, dict) or not raw_tokens:
            raise ValueError(f"{path.name} observation {index} must contain token values")

        tokens: dict[str, Decimal] = {}
        for token, raw_value in raw_tokens.items():
            if not isinstance(token, str) or not token:
                raise ValueError(f"{path.name} observation {index} has an invalid token label")
            try:
                value = raw_value if isinstance(raw_value, Decimal) else Decimal(str(raw_value))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"{path.name} observation {index} has invalid USD TVL for {token}") from exc
            if not value.is_finite() or value < 0:
                raise ValueError(f"{path.name} observation {index} has invalid USD TVL for {token}")
            if value > 0:
                tokens[token] = value

        previous = rows.get(day)
        if previous is None or timestamp > previous["timestamp"]:
            rows[day] = {"timestamp": timestamp, "tokens": tokens}
    if not rows:
        raise ValueError(f"{path.name} contains no token TVL snapshots")
    return dict(sorted(rows.items())), document


def _token_tvl_period_items(
    rows: dict[date, dict[str, Any]], period: str, prices: dict[date, Decimal],
) -> list[dict[str, Any]]:
    groups: dict[str, list[date]] = {}
    bounds: dict[str, tuple[date, date]] = {}
    for day in rows:
        if period == "daily":
            key, start, end = day.isoformat(), day, day
        else:
            key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append(day)
        bounds[key] = (start, end)

    items = []
    for key in sorted(groups):
        last_day = groups[key][-1]
        start, end = bounds[key]
        items.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "date": last_day.isoformat(),
            "tokens": rows[last_day]["tokens"],
            "tokens_near": ({
                token: _usd_to_near(value, prices.get(last_day))
                for token, value in rows[last_day]["tokens"].items()
            } if prices.get(last_day) is not None else None),
        })
    return items


def _period_items(
    flows: dict[str, dict[date, Decimal | None]],
    tvl: dict[date, Decimal | None],
    tvl_near: dict[date, Decimal | None],
    period: str,
) -> list[dict[str, Any]]:
    dates = sorted(set(tvl).union(*(set(series) for series in flows.values())))
    groups: dict[str, list[date]] = {}
    bounds: dict[str, tuple[date, date]] = {}
    for day in dates:
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append(day)
        bounds[key] = (start, end)

    items = []
    for key in sorted(groups):
        period_days = groups[key]
        start, end = bounds[key]
        tvl_days = [day for day in period_days if tvl.get(day) is not None]
        latest_tvl_day = tvl_days[-1] if tvl_days else None
        item = {
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": period_days[-1].isoformat(),
            "days_observed": len(period_days),
            "tvl_as_of_date": latest_tvl_day.isoformat() if latest_tvl_day else None,
            "tvl_usd": tvl[latest_tvl_day] if latest_tvl_day else None,
            "tvl_near": tvl_near.get(latest_tvl_day) if latest_tvl_day else None,
        }
        for field, series in flows.items():
            flow_days = [day for day in period_days if series.get(day) is not None]
            item[field] = sum((series[day] for day in flow_days), Decimal(0)) if flow_days else None
            item[f"{field}_days_observed"] = len(flow_days)
        item["revenue_capture_rate_30d_pct"] = _rolling_revenue_capture_rate(
            flows, period_days[-1],
        )
        items.append(item)
    return items


def _complete_window_total(
    series: dict[date, Decimal | None], end: date, days: int, *, offset: int = 0,
) -> Decimal | None:
    """Sum an exact UTC calendar window only when every date has a value."""
    window_end = end - timedelta(days=offset)
    window_start = window_end - timedelta(days=days - 1)
    expected_dates = [window_start + timedelta(days=index) for index in range(days)]
    if any(day not in series or series[day] is None for day in expected_dates):
        return None
    return sum((series[day] for day in expected_dates), Decimal(0))


def _rolling_revenue_capture_rate(
    flows: dict[str, dict[date, Decimal | None]], end: date,
) -> Decimal | None:
    revenue = _complete_window_total(flows.get("revenue_usd", {}), end, 30)
    gross_fees = _complete_window_total(flows.get("gross_fees_usd", {}), end, 30)
    if revenue is None or gross_fees is None or gross_fees == 0:
        return None
    return ((revenue / gross_fees) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )


def _flow_kpis(series: dict[date, Decimal | None]) -> dict[str, Any]:
    available_dates = [day for day, value in series.items() if value is not None]
    if not available_dates:
        return {
            "date": None,
            "total_24h": None, "change_24h_pct": None,
            "total_7d": None, "change_7d_pct": None,
            "total_30d": None, "change_30d_pct": None,
        }

    latest = max(available_dates)
    result: dict[str, Any] = {"date": latest.isoformat()}
    result["total_all_time"] = sum((value for day, value in series.items()
                                     if day <= latest and value is not None), Decimal(0))
    for days, suffix in ((1, "24h"), (7, "7d"), (30, "30d")):
        current = _complete_window_total(series, latest, days)
        previous = _complete_window_total(series, latest, days, offset=days)
        change = None
        if current is not None and previous is not None and previous != 0:
            change = (((current - previous) / previous) * Decimal(100)).quantize(Decimal("0.01"))
        result[f"total_{suffix}"] = current
        result[f"change_{suffix}_pct"] = change
    return result


def _snapshot_kpis(series: dict[date, Decimal | None]) -> dict[str, Any]:
    available_dates = [day for day, value in series.items() if value is not None]
    if not available_dates:
        return {"value": None, "date": None, "change_7d_pct": None, "change_30d_pct": None}
    latest = max(available_dates)
    current = series[latest]
    result: dict[str, Any] = {"value": current, "date": latest.isoformat()}
    for days in (7, 30):
        previous = series.get(latest - timedelta(days=days))
        change = None
        if previous is not None and previous != 0:
            change = (((current - previous) / previous) * Decimal(100)).quantize(Decimal("0.01"))
        result[f"change_{days}d_pct"] = change
    return result


def _write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(validate_json(document), encoding="utf-8")


def build_near_intents_analytics(
    normalized_root: Path = NORMALIZED_ROOT,
    output_dir: Path = ANALYTICS_DIR,
) -> dict[str, Path]:
    normalized_root = Path(normalized_root)
    output_dir = Path(output_dir)

    volume, _ = _read_series(normalized_root / VOLUME_DIR / "daily_volume.json")
    tvl, _ = _read_series(normalized_root / TVL_DIR / "daily_intents_tvl.json",
                          latest_same_day=True)
    near_prices = _read_near_prices(normalized_root.parent / PRICE_PATH)
    tvl_near = {day: _usd_to_near(value, near_prices.get(day)) for day, value in tvl.items()}
    token_tvl, token_tvl_document = _read_token_tvl(normalized_root / TOKEN_TVL_PATH)
    protocol_flows = {
        field: _read_protocol_flow(
            normalized_root / relative, key,
            allow_missing_protocol=(field in {
                "holders_revenue_usd", "revenue_usd", "gross_fees_usd",
            }),
        )
        for field, (relative, key) in PROTOCOL_FLOWS.items()
    }
    volume_summary = _read_json(normalized_root / VOLUME_DIR / "summary.json")
    tvl_summary = _read_json(normalized_root / TVL_DIR / "intents_tvl.json")
    fees_document = _read_json(normalized_root / PROTOCOL_FLOWS["gross_fees_usd"][0])

    volume_values = volume_summary.get("values")
    if not isinstance(volume_values, dict):
        raise ValueError("NEAR Intents volume summary must contain values")
    current_tvl = tvl_summary.get("current_tvl")
    if current_tvl is None:
        raise ValueError("NEAR Intents TVL summary must contain current_tvl")

    flows = {"volume_usd": volume, **protocol_flows}
    gross_fee_kpis = _flow_kpis(protocol_flows["gross_fees_usd"])
    key_metrics = {
        "volume_usd": {
            **_flow_kpis(volume),
            "total_1y": volume_values.get("total_1y"),
            "total_all_time": volume_values.get("total_all_time"),
        },
        "gross_fees_usd": {
            **gross_fee_kpis,
            "cumulative_total": gross_fee_kpis["total_all_time"],
        },
        "revenue_usd": _flow_kpis(protocol_flows["revenue_usd"]),
        "holders_revenue_usd": _flow_kpis(protocol_flows["holders_revenue_usd"]),
        "tvl_usd": _snapshot_kpis(tvl),
        "tvl_near": _snapshot_kpis(tvl_near),
    }
    all_dates = sorted(set(tvl).union(*(set(series) for series in flows.values())))
    daily_items = [
        {
            "date": day.isoformat(),
            "tvl_usd": tvl.get(day),
            "tvl_near": tvl_near.get(day),
            **{field: series.get(day) for field, series in flows.items()},
            "revenue_capture_rate_30d_pct": _rolling_revenue_capture_rate(flows, day),
        }
        for day in all_dates
    ]
    latest_capture_rate = next(
        (item for item in reversed(daily_items) if item["revenue_capture_rate_30d_pct"] is not None),
        None,
    )
    key_metrics["revenue_capture_rate_30d_pct"] = {
        "value": latest_capture_rate["revenue_capture_rate_30d_pct"] if latest_capture_rate else None,
        "date": latest_capture_rate["date"] if latest_capture_rate else None,
    }
    snapshot = {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "volume": volume_values,
        "tvl_usd": current_tvl,
        "tvl_near": tvl_near.get(max(day for day, value in tvl.items() if value is not None)),
        "key_metrics": key_metrics,
        "updated_at": max(volume_summary.get("updated_at", ""), tvl_summary.get("updated_at", ""),
                           token_tvl_document.get("updated_at", ""),
                           fees_document.get("updated_at", "")),
        "coverage_note": volume_summary.get("coverage_note"),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    daily_path = output_dir / "daily_metrics.json"
    _write_json(daily_path, {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "time": {"timezone": "UTC", "date_convention": "UTC calendar date"},
        "metrics": {
            **{field: "flow" for field in flows},
            "tvl_usd": "period_end_snapshot",
            "tvl_near": "period_end_snapshot",
            "revenue_capture_rate_30d_pct": "rolling_30d_ratio",
        },
        "units": {**{field: "USD" for field in flows}, "tvl_usd": "USD", "tvl_near": "NEAR"},
        "items": daily_items,
    })
    outputs["daily_metrics"] = daily_path

    snapshot_path = output_dir / "snapshot.json"
    _write_json(snapshot_path, snapshot)
    outputs["snapshot"] = snapshot_path

    latest_token_day = next(reversed(token_tvl))
    latest_token_snapshot = token_tvl[latest_token_day]
    ranked_tokens = sorted(latest_token_snapshot["tokens"].items(), key=lambda item: (-item[1], item[0]))
    top_tokens = [token for token, _ in ranked_tokens[:8]]
    current_token_path = output_dir / "current_tvl_by_token.json"
    _write_json(current_token_path, {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "date": latest_token_day.isoformat(),
        "timestamp": latest_token_snapshot["timestamp"],
        "unit": "USD",
        "units": {"tvl_usd": "USD", "tvl_near": "NEAR"},
        "aggregation": "current_snapshot",
        "items": [
            {"token": token, "tvl_usd": value,
             "tvl_near": _usd_to_near(value, near_prices.get(latest_token_day))}
            for token, value in sorted(latest_token_snapshot["tokens"].items(),
                                       key=lambda item: (-item[1], item[0]))
        ],
        "top_tokens": top_tokens,
        "pie_usd": ([{"name": token, "value": value} for token, value in ranked_tokens[:7]] +
                    ([{"name": "Other tokens", "value": sum((value for _, value in ranked_tokens[7:]), Decimal(0))}]
                     if sum((value for _, value in ranked_tokens[7:]), Decimal(0)) > 0 else [])),
        "pie_near": ([{"name": token, "value": _usd_to_near(value, near_prices.get(latest_token_day))} for token, value in ranked_tokens[:7]] +
                     ([{"name": "Other tokens", "value": _usd_to_near(sum((value for _, value in ranked_tokens[7:]), Decimal(0)), near_prices.get(latest_token_day))}]
                      if sum((value for _, value in ranked_tokens[7:]), Decimal(0)) > 0 else [])),
    })
    outputs["current_tvl_by_token"] = current_token_path

    for period in ("daily", *PERIODS):
        path = output_dir / f"{period}_tvl_by_token.json"
        _write_json(path, {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "unit": "USD",
            "units": {"tokens": "USD", "tokens_near": "NEAR"},
            "aggregation": "period_end_snapshot",
            "items": _token_tvl_period_items(token_tvl, period, near_prices),
        })
        outputs[f"{period}_tvl_by_token"] = path

    for period in ("daily", *PERIODS):
        items = _token_tvl_period_items(token_tvl, period, near_prices)
        chart_items = [{
            "period": row.get("period", row.get("date")),
            "tokens": {token: (row.get("tokens") or {}).get(token) for token in top_tokens},
            "tokens_near": {token: (row.get("tokens_near") or {}).get(token) for token in top_tokens},
            "other_usd": sum((Decimal(str(value)) for token, value in (row.get("tokens") or {}).items()
                              if token not in top_tokens and value is not None), Decimal(0)),
            "other_near": sum((Decimal(str(value)) for token, value in (row.get("tokens_near") or {}).items()
                               if token not in top_tokens and value is not None), Decimal(0)),
        } for row in items]
        chart_path = output_dir / f"{period}_tvl_by_token_chart.json"
        _write_json(chart_path, {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "unit": "USD",
            "units": {"tokens": "USD", "tokens_near": "NEAR"},
            "items": chart_items,
        })
        outputs[f"{period}_tvl_by_token_chart"] = chart_path

    for period in PERIODS:
        path = output_dir / f"{period}_metrics.json"
        _write_json(path, {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "period": period,
            "aggregation": {
                **{field: "sum" for field in flows},
                "tvl_usd": "period_end_snapshot",
                "tvl_near": "period_end_snapshot",
                "revenue_capture_rate_30d_pct": "rolling_30d_ratio",
            },
            "units": {
                **{field: "USD" for field in flows},
                "tvl_usd": "USD",
                "tvl_near": "NEAR",
                "revenue_capture_rate_30d_pct": "%",
            },
            "coverage_note": volume_summary.get("coverage_note"),
            "items": _period_items(flows, tvl, tvl_near, period),
        })
        outputs[f"{period}_metrics"] = path

    chain_tvl = _read_json(normalized_root / TVL_DIR / "tvl_by_chain.json")
    chain_date = date.fromisoformat(chain_tvl["date"])
    chain_price = near_prices.get(chain_date)
    chain_tvl_path = output_dir / "tvl_by_chain.json"
    chain_total = sum((Decimal(str(item["tvl_usd"])) for item in chain_tvl["items"]
                       if item.get("tvl_usd") is not None and Decimal(str(item["tvl_usd"])) > 0), Decimal(0))
    _write_json(chain_tvl_path, {
        "schema_version": "1.0.0",
        "network": "NEAR mainnet",
        "date": chain_tvl["date"],
        "total_tvl_usd": chain_total,
        "unit": "USD",
        "units": {"tvl_usd": "USD", "tvl_near": "NEAR"},
        "items": [
            {**item, "tvl_near": _usd_to_near(
                Decimal(str(item["tvl_usd"])) if item.get("tvl_usd") is not None else None,
                chain_price,
            )}
            for item in sorted(
                (item for item in chain_tvl["items"]
                 if item.get("tvl_usd") is not None and Decimal(str(item["tvl_usd"])) > 0),
                key=lambda item: (-Decimal(str(item["tvl_usd"])), str(item.get("chain", "")).casefold()),
            )
        ],
    })
    outputs["tvl_by_chain"] = chain_tvl_path

    from console_ui import console
    console.print(
        f"[green]OK[/green] NEAR Intents [dim]· {len(daily_items):,} combined days · "
        f"volume {len(volume):,} · TVL {len(tvl):,} · token TVL {len(token_tvl):,} · "
        f"{len(outputs)} outputs[/dim]"
    )
    return outputs
