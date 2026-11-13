"""Build periodic analytics for NEAR ecosystem protocol flows."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from analytics.periods import CALENDAR_PERIODS, period_bounds
from analytics.fallbacks import write_empty_protocol_snapshot
from paths import ANALYTICS_DATA_DIR, NORMALIZED_DATA_DIR
from validation import validate_json


NORMALIZED_ROOT = NORMALIZED_DATA_DIR / "defillama"
ANALYTICS_ROOT = ANALYTICS_DATA_DIR / "protocols"
PERIODS = CALENDAR_PERIODS
CATEGORIES = {
    "fees": {
        "directory": "near_fees",
        "daily_file": "daily_protocol_fees1.json",
        "breakdown_file": "daily_protocol_fees_breakdown.json",
        "summary_file": "summary.json",
        "ranking_file": "protocol_fees_ranking.json",
        "metric": "fees_usd",
        "breakdown_key": "values",
        "summary_key": "values",
        "ranking_key": "total30d",
        "ranking_fields": ("name", "id", "slug", "category", "total30d", "totalAllTime"),
    },
    "revenue": {
        "directory": "near_revenue",
        "daily_file": "daily_protocol_revenue.json",
        "breakdown_file": "daily_protocol_revenue_breakdown.json",
        "summary_file": "summary.json",
        "metric": "revenue_usd",
        "breakdown_key": "values",
        "summary_key": "values",
    },
    "dex_volume": {
        "directory": "near_dex_volumes",
        "daily_file": "daily_tracked_protocol_dex_volume.json",
        "breakdown_file": "daily_tracked_protocol_dex_volume_breakdown.json",
        "summary_file": "summary.json",
        "ranking_file": "protocol_dex_volume_ranking.json",
        "metric": "volume_usd",
        "breakdown_key": "value",
        "summary_key": "values",
        "ranking_key": "total_30d",
        "ranking_fields": ("name", "id", "slug", "category", "total_24h", "total_7d",
                           "total_30d", "total_all_time", "change_1d", "change_7d",
                           "change_30d_over_30d"),
    },
    "holders_revenue": {
        "directory": "near_holders_revenue",
        "daily_file": "daily_holders_revenue.json",
        "breakdown_file": "daily_holders_revenue_breakdown.json",
        "summary_file": "ecosystem_holders_revenue.json",
        "metric": "holders_revenue_usd",
        "breakdown_key": "protocols",
        "summary_key": "summary",
    },
}


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _day(value: Any, path: Path, index: int) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{path.name} item {index} date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{path.name} item {index} has invalid date {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{path.name} item {index} date must be YYYY-MM-DD")
    return parsed


def _number(value: Any, path: Path, index: int) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} item {index} must contain numeric values") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{path.name} item {index} values must be finite and non-negative")
    return parsed


def _load_daily(path: Path, field: str) -> dict[date, Decimal | None]:
    document = _read_json(path)
    items = document.get("observations") if isinstance(document, dict) else None
    metric = document.get("metric") if isinstance(document, dict) else None
    if not isinstance(items, list) or not isinstance(metric, dict) \
            or metric.get("frequency") != "daily" or metric.get("unit") != "USD":
        raise ValueError(f"{path.name} must be a daily USD dataset")
    series = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{path.name} item {index} must be an object")
        day = _day(item.get("date"), path, index)
        if day in series:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        series[day] = _number(item.get("value"), path, index)
    return dict(sorted(series.items()))


def _load_breakdown(path: Path, field: str) -> dict[date, dict[str, Decimal | None]]:
    document = _read_json(path)
    items = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"{path.name} must contain daily observations")
    breakdown = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{path.name} item {index} must be an object")
        day = _day(item.get("date"), path, index)
        if day in breakdown:
            raise ValueError(f"{path.name} contains duplicate date {day}")
        values = item.get(field)
        if not isinstance(values, dict):
            raise ValueError(f"{path.name} item {index} must have a {field} object")
        breakdown[day] = {
            str(name): _number(value, path, index) for name, value in values.items()
        }
    return dict(sorted(breakdown.items()))


def _load_near_prices(normalized_root: Path) -> dict[date, Decimal]:
    path = normalized_root.parent / "binance" / "near_price" / "nearusdt_1d_close_price.json"
    document = _read_json(path)
    observations = document.get("observations") if isinstance(document, dict) else None
    if not isinstance(observations, list):
        raise ValueError(f"{path.name} must contain daily price observations")
    prices = {}
    for index, item in enumerate(observations):
        day = _day(item.get("date"), path, index)
        price = _number(item.get("price"), path, index)
        if price is None or price <= 0:
            continue
        prices[day] = price
    return prices


def _near_series(series: dict[date, Decimal | None], prices: dict[date, Decimal]) -> dict[date, Decimal | None]:
    return {
        day: (value / prices[day] if value is not None and day in prices else None)
        for day, value in series.items()
    }


def _near_breakdown(
    breakdown: dict[date, dict[str, Decimal | None]], prices: dict[date, Decimal],
) -> dict[date, dict[str, Decimal | None]]:
    return {
        day: {
            name: (value / prices[day] if value is not None and day in prices else None)
            for name, value in values.items()
        }
        for day, values in breakdown.items()
    }


def _period_metrics(series: dict[date, Decimal | None], period: str) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[date, Decimal | None, date, date]]] = {}
    for day, value in series.items():
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, value, start, end))
    items = []
    for key in sorted(groups):
        group = groups[key]
        present = [(day, value) for day, value, _, _ in group if value is not None]
        start, end = group[0][2], group[0][3]
        items.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": group[-1][0].isoformat(),
            "days_observed": len(group),
            "value_usd": sum((value for _, value in present), Decimal(0)) if present else None,
        })
    return items


def _period_breakdown(
    breakdown: dict[date, dict[str, Decimal | None]], period: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[date, dict[str, Decimal | None], date, date]]] = {}
    for day, values in breakdown.items():
        key, start, end = period_bounds(day, period)
        groups.setdefault(key, []).append((day, values, start, end))
    items = []
    for key in sorted(groups):
        group = groups[key]
        names = sorted({name for _, values, _, _ in group for name in values})
        totals = {
            name: sum((values[name] for _, values, _, _ in group
                       if values.get(name) is not None), Decimal(0))
            if any(values.get(name) is not None for _, values, _, _ in group) else None
            for name in names
        }
        start, end = group[0][2], group[0][3]
        items.append({
            "period": key,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "start_date": start.isoformat(),
            "date": group[-1][0].isoformat(),
            "days_observed": len(group),
            "protocols": totals,
        })
    return items


def _chart_breakdown(items: list[dict[str, Any]], field: str) -> dict[str, Any]:
    totals: dict[str, Decimal] = {}
    for row in items:
        for name, value in (row.get(field) or {}).items():
            if value is not None:
                totals[name] = totals.get(name, Decimal(0)) + Decimal(str(value))
    leaders = [name for name, _ in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))[:6]]
    names = set(leaders)
    return {
        "protocols": leaders,
        "items": [{
            "period": row.get("period", row.get("date")),
            "protocols": {name: (row.get(field) or {}).get(name) for name in leaders},
            "other": sum((Decimal(str(value)) for name, value in (row.get(field) or {}).items()
                          if name not in names and value is not None), Decimal(0)),
        } for row in items],
        "distribution": [{"name": name, "value": value} for name, value in
                         sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))[:6]] +
                        ([{"name": "Other protocols", "value": sum(
                            (value for name, value in totals.items() if name not in names), Decimal(0))}]
                         if sum((value for name, value in totals.items() if name not in names), Decimal(0)) > 0 else []),
    }


def _compact_ranking(document: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    records = document.get("values", document.get("records", []))
    if not isinstance(records, list):
        return []
    ranking_key = config["ranking_key"]
    records = sorted(
        (record for record in records if isinstance(record, dict)),
        key=lambda record: (
            _number(record.get(ranking_key), Path("ranking.json"), 0) is None,
            -_number(record.get(ranking_key), Path("ranking.json"), 0)
            if _number(record.get(ranking_key), Path("ranking.json"), 0) is not None else Decimal(0),
            str(record.get("name", "")),
        ),
    )
    compact = []
    for rank, record in enumerate(records, start=1):
        item = {key: record[key] for key in config["ranking_fields"] if key in record}
        item["rank"] = rank
        if "id" not in item and "defillama_id" in record:
            item["id"] = record["defillama_id"]
        if "slug" not in item and "module" in record:
            item["slug"] = record["module"]
        compact.append(item)
    return compact


def _write(path: Path, document: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(validate_json(document), encoding="utf-8")
    return path


def _build_category(
    name: str, config: dict[str, Any], normalized_root: Path, output_root: Path,
    prices: dict[date, Decimal],
) -> dict[str, Path]:
    source_dir = normalized_root / config["directory"]
    output_dir = output_root / name
    daily_path = source_dir / config["daily_file"]
    series = _load_daily(daily_path, "value")
    breakdown = _load_breakdown(source_dir / config["breakdown_file"], config["breakdown_key"])
    ecosystem_series = series
    if name == "holders_revenue":
        # The chart is the only daily source that isolates NEAR Intents.
        if set(breakdown) != set(series):
            raise ValueError("holders revenue breakdown dates must match the ecosystem daily series")
        if any("NEAR Intents" not in values for values in breakdown.values()):
            raise ValueError("holders revenue breakdown is missing a NEAR Intents value")
        series = {day: values["NEAR Intents"] for day, values in breakdown.items()}
        breakdown = {day: {"NEAR Intents": value} for day, value in series.items()}
    series_near = _near_series(series, prices)
    breakdown_near = _near_breakdown(breakdown, prices)
    summary_doc = _read_json(source_dir / config["summary_file"])
    summary_values = summary_doc.get(config["summary_key"], {})
    if not isinstance(summary_values, dict):
        raise ValueError(f"{config['summary_file']} summary values must be an object")
    ranking = None
    ranking_doc = None
    if "ranking_file" in config:
        ranking_doc = _read_json(source_dir / config["ranking_file"])
        ranking = _compact_ranking(ranking_doc, config)
    outputs = {}
    daily_items = [{
        "date": day.isoformat(),
        config["metric"]: value,
        "value_usd": value,
        "value_near": series_near[day],
    } for day, value in series.items()]
    outputs["daily_metrics"] = _write(output_dir / "daily_metrics.json", {
        "schema_version": "1.0.0", "network": "NEAR mainnet",
        "metric": config["metric"], "unit": "USD", "units": {"USD": "USD", "NEAR": "NEAR"}, "items": daily_items,
    })
    daily_breakdown_items = [
        {"date": day.isoformat(), "protocols": values, "protocols_near": breakdown_near[day]}
        for day, values in breakdown.items()
    ]
    outputs["daily_breakdown"] = _write(output_dir / "daily_breakdown.json", {
        "schema_version": "1.0.0", "network": "NEAR mainnet",
        "unit": "USD", "units": {"protocols": "USD", "protocols_near": "NEAR"},
        "items": daily_breakdown_items,
        "charts": {"USD": _chart_breakdown(daily_breakdown_items, "protocols"),
                   "NEAR": _chart_breakdown(daily_breakdown_items, "protocols_near"),
                   "latest_USD": _chart_breakdown(daily_breakdown_items[-1:], "protocols"),
                   "latest_NEAR": _chart_breakdown(daily_breakdown_items[-1:], "protocols_near")},
    })

    for period in PERIODS:
        usd_metrics = _period_metrics(series, period)
        near_metrics = _period_metrics(series_near, period)
        for usd_item, near_item in zip(usd_metrics, near_metrics):
            usd_item["value_near"] = near_item["value_usd"]
        outputs[f"{period}_metrics"] = _write(output_dir / f"{period}_metrics.json", {
            "schema_version": "1.0.0", "network": "NEAR mainnet", "period": period,
            "aggregation": "sum", "metric": config["metric"],
            "unit": "USD", "units": {"USD": "USD", "NEAR": "NEAR"}, "items": usd_metrics,
        })
        usd_breakdown = _period_breakdown(breakdown, period)
        near_period_breakdown = _period_breakdown(breakdown_near, period)
        for usd_item, near_item in zip(usd_breakdown, near_period_breakdown):
            usd_item["protocols_near"] = near_item["protocols"]
        outputs[f"{period}_breakdown"] = _write(output_dir / f"{period}_breakdown.json", {
            "schema_version": "1.0.0", "network": "NEAR mainnet", "period": period,
            "aggregation": "sum_by_protocol",
            "unit": "USD", "units": {"protocols": "USD", "protocols_near": "NEAR"},
            "items": usd_breakdown,
            "charts": {"USD": _chart_breakdown(usd_breakdown, "protocols"),
                       "NEAR": _chart_breakdown(usd_breakdown, "protocols_near"),
                       "latest_USD": _chart_breakdown(usd_breakdown[-1:], "protocols"),
                       "latest_NEAR": _chart_breakdown(usd_breakdown[-1:], "protocols_near")},
        })

    updated_at = max(summary_doc.get("updated_at", ""),
                     ranking_doc.get("updated_at", "") if ranking_doc else "")
    if name == "holders_revenue":
        (output_dir / "snapshot.json").unlink(missing_ok=True)

        # Keep the chain-wide aggregate and full ranking, but label their scope explicitly.
        ecosystem_dir = output_dir / "ecosystem"
        outputs["ecosystem_daily_metrics"] = _write(ecosystem_dir / "daily_metrics.json", {
            "schema_version": "1.0.0", "network": "NEAR mainnet",
            "metric": "ecosystem_holders_revenue_usd", "unit": "USD",
            "items": [{"date": day.isoformat(), "ecosystem_holders_revenue_usd": value}
                      for day, value in ecosystem_series.items()],
        })
        for period in PERIODS:
            outputs[f"ecosystem_{period}_metrics"] = _write(
                ecosystem_dir / f"{period}_metrics.json", {
                    "schema_version": "1.0.0", "network": "NEAR mainnet", "period": period,
                    "aggregation": "sum", "metric": "ecosystem_holders_revenue_usd", "unit": "USD",
                    "items": _period_metrics(ecosystem_series, period),
                }
            )
        ecosystem_snapshot = {
            "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": updated_at,
            "summary": summary_values,
        }
        if ranking is not None:
            outputs["ecosystem_protocol_breakdown"] = _write(
                ecosystem_dir / "protocol_breakdown.json", {
                    "schema_version": "1.0.0", "network": "NEAR mainnet",
                    "updated_at": updated_at, "aggregation": "ranked",
                    "items": ranking,
                }
            )
        else:
            (ecosystem_dir / "protocol_breakdown.json").unlink(missing_ok=True)
        coverage_note = summary_doc.get("coverage_note") or (
            ranking_doc.get("coverage_note") if ranking_doc else None
        )
        if coverage_note:
            ecosystem_snapshot["coverage_note"] = coverage_note
        outputs["ecosystem_snapshot"] = _write(ecosystem_dir / "snapshot.json", ecosystem_snapshot)
    else:
        snapshot = {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "updated_at": updated_at,
            "summary": summary_values,
        }
        if ranking is not None:
            outputs["protocol_breakdown"] = _write(
                output_dir / "protocol_breakdown.json", {
                    "schema_version": "1.0.0", "network": "NEAR mainnet",
                    "updated_at": updated_at, "aggregation": "ranked",
                    "unit": "USD", "items": ranking,
                }
            )
        else:
            (output_dir / "protocol_breakdown.json").unlink(missing_ok=True)
        coverage_note = summary_doc.get("coverage_note") or (
            ranking_doc.get("coverage_note") if ranking_doc else None
        )
        if coverage_note:
            snapshot["coverage_note"] = coverage_note
        outputs["snapshot"] = _write(output_dir / "snapshot.json", snapshot)
    return outputs


def build_protocol_analytics(
    normalized_root: Path = NORMALIZED_ROOT,
    output_root: Path = ANALYTICS_ROOT,
) -> dict[str, dict[str, Path]]:
    """Build daily, calendar-period, breakdown, and ranking analytics for protocols."""

    normalized_root = Path(normalized_root)
    output_root = Path(output_root)
    try:
        prices = _load_near_prices(normalized_root)
    except Exception as exc:
        print(f"protocol analytics: NEAR price unavailable; NEAR conversions will be empty: "
              f"{type(exc).__name__}: {exc}")
        prices = {}

    results = {}
    for category, config in CATEGORIES.items():
        if category == "holders_revenue":
            continue
        try:
            results[category] = _build_category(
                category, config, normalized_root, output_root, prices,
            )
        except Exception as exc:
            print(f"protocol analytics {category}: unavailable; writing an empty category snapshot: "
                  f"{type(exc).__name__}: {exc}")
            snapshot_path = write_empty_protocol_snapshot(output_root.parent, category)
            results[category] = {"snapshot": snapshot_path}
    holders_dir = output_root.parent / "near_intents" / "holders_revenue"
    if holders_dir.exists():
        for stale_path in holders_dir.rglob("*.json"):
            stale_path.unlink()
        for directory in sorted((path for path in holders_dir.rglob("*") if path.is_dir()), reverse=True):
            directory.rmdir()
        holders_dir.rmdir()
    old_dir = output_root / "holders_revenue"
    if old_dir.exists():
        for stale_path in old_dir.rglob("*.json"):
            stale_path.unlink()
        for directory in sorted((p for p in old_dir.rglob("*") if p.is_dir()), reverse=True):
            directory.rmdir()
        old_dir.rmdir()
    for category, outputs in results.items():
        output_dir = next(iter(outputs.values())).parent
        from console_ui import console
        console.print(f"[green]OK[/green] Protocols · {category} [dim]({len(outputs)} outputs)[/dim]")
    return results
