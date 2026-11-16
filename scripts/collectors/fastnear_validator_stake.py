"""Resumable daily stake collection from the FastNEAR archival RPC."""

import json
import random
import time
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError

from atomic_io import atomic_write_text
from sources import Source, SourceName, get_source, raw_path
from rpc_clients.near import NearRpcClient
from console_ui import console, error

DAILY_SUPPLY_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_SUPPLY))
LOOKBACK_MONTHS = 3
MAX_ATTEMPTS = 6
REQUEST_TIMEOUT_SECONDS = 30


def _request_start_date(today: date | None = None) -> date:
    """Return the date three calendar months before today, clamping month ends."""

    current_date = today or datetime.now(timezone.utc).date()
    month_index = current_date.year * 12 + current_date.month - 1 - LOOKBACK_MONTHS
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    day = min(current_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _height(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("daily_supply block_height must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise ValueError("daily_supply block_height must be a positive integer")
    if result <= 0:
        raise ValueError("daily_supply block_height must be a positive integer")
    return result


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _read_supply_blocks(path: Path, start_date: date) -> list[dict[str, Any]]:
    raw_rows = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw_rows, list):
        raise ValueError("daily_supply.json must contain a list of raw records")
    by_date: dict[date, dict[str, Any]] = {}
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise ValueError(f"daily_supply record {index} must be an object")
        try:
            date_text = row["utc_date"]
            day = date.fromisoformat(date_text)
            block_height = _height(row["block_height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"daily_supply record {index} needs utc_date and block_height") from exc
        if day.isoformat() != date_text:
            raise ValueError(f"daily_supply record {index} date must use YYYY-MM-DD")
        if day >= start_date:
            if day in by_date:
                raise ValueError(f"daily_supply.json has duplicate date {day}")
            by_date[day] = {"date": day.isoformat(), "block_height": block_height}
    return [by_date[day] for day in sorted(by_date)]


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _read_checkpoint(path: Path, source: Source, start_date: date) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "1.0.0", "network": "NEAR mainnet",
                "source": {"provider": source.provider.value, "endpoint": source.url,
                           "method": "validators", "reference": "daily_supply.json block_height"},
                "requested_start_date": start_date.isoformat(), "items": []}
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError(f"{path.name} checkpoint must be an object with an items list")
    return document


def _write_checkpoint(path: Path, document: dict[str, Any], items: dict[str, dict[str, Any]]) -> None:
    document["items"] = [items[key] for key in sorted(items)]
    document["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    atomic_write_text(path, json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def collect_daily_active_validator_stake(
    source: Source | None = None,
    *,
    supply_path: Path = DAILY_SUPPLY_PATH,
    output_path: Path | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
    base_backoff_seconds: float = 1.0,
    sleep: Callable = time.sleep,
) -> bool:
    """Fetch missing daily snapshots, checkpointing each exact aggregate."""

    source = source or get_source(SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE)
    output = Path(output_path) if output_path is not None else raw_path(source)
    initial_start_date = _request_start_date()
    try:
        if source.url is None:
            raise ValueError("FastNEAR archival RPC endpoint is not configured")
        if not Path(supply_path).exists():
            raise FileNotFoundError(f"Required raw block references are unavailable: {supply_path}")
        document = _read_checkpoint(output, source, initial_start_date)
        existing_items: dict[str, dict[str, Any]] = {}
        for item in document["items"]:
            if isinstance(item, dict) and isinstance(item.get("utc_date"), str):
                existing_items[item["utc_date"]] = item

        # The rolling three-month window is only a bootstrap default. Once raw
        # data exists, continue from the day after its latest saved observation.
        latest_saved_date = max(
            (date.fromisoformat(day) for day in existing_items if _is_iso_date(day)),
            default=None,
        )
        request_start_date = (
            latest_saved_date + timedelta(days=1)
            if latest_saved_date is not None
            else initial_start_date
        )
        is_initial_collection = latest_saved_date is None
        block_rows = _read_supply_blocks(Path(supply_path), request_start_date)
        if not block_rows:
            if existing_items:
                console.print(
                    f"[cyan]FastNEAR daily stake[/cyan] [dim]up to date; no daily supply block references after {latest_saved_date}[/dim]"
                )
                return True
            raise ValueError(f"No daily supply block references found since {request_start_date}")

        expected_dates = {row["date"] for row in block_rows}
        end_date = date.fromisoformat(block_rows[-1]["date"])
        missing_days = [
            day.isoformat()
            for day in (date.fromordinal(n)
                        for n in range(request_start_date.toordinal(), end_date.toordinal() + 1))
            if day.isoformat() not in expected_dates
        ]
        if missing_days:
            print(f"{source.name}: daily_supply is missing {len(missing_days)} reference dates; available dates will still be collected")

        pending_rows = []
        for row in block_rows:
            existing = existing_items.get(row["date"])
            total_stake_text = existing.get("total_active_stake_yocto") if isinstance(existing, dict) else None
            has_stake_data = isinstance(total_stake_text, str) and total_stake_text.isdigit()
            if existing is None or existing.get("block_height") != row["block_height"] or not has_stake_data:
                pending_rows.append(row)

        if pending_rows:
            collection_type = "First-time collection" if is_initial_collection else "Incremental collection"
            console.print(
                f"[cyan]FastNEAR daily stake · {request_start_date} to {end_date}[/cyan]\n"
                f"[dim]{collection_type} may take a few minutes. Please wait while progress updates below.[/dim]"
            )

        completed = 0
        failures: list[dict[str, str]] = []
        # fetch_all owns a Rich Progress display while this collector runs.
        # Starting rich.progress.track here would create a second Live display
        # on the same console and raise LiveError before any RPC requests run.
        total_pending = len(pending_rows)
        for row_index, row in enumerate(pending_rows, start=1):
            day_text = row["date"]
            block_height = row["block_height"]
            request_error: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    with NearRpcClient(source.url, timeout=timeout, source=source) as rpc:
                        block_response = rpc.block(block_height)
                        epoch_id = _field(_field(block_response, "header"), "epoch_id")
                        epoch_id_value = _field(epoch_id, "root")
                        if epoch_id_value is None:
                            epoch_id_value = epoch_id
                        if not isinstance(epoch_id_value, str) or not epoch_id_value:
                            raise ValueError("block response must contain header.epoch_id")
                        response = rpc.validators(epoch_id_value)
                    validators = _field(response, "current_validators")
                    if not isinstance(validators, list):
                        raise ValueError("RPC result must contain a current_validators list")
                    total_stake_yocto = 0
                    for index, validator in enumerate(validators):
                        stake = _field(validator, "stake")
                        stake_value = _field(stake, "root")
                        if stake_value is None:
                            stake_value = stake
                        if isinstance(stake_value, bool) or not (
                            isinstance(stake_value, int)
                            or isinstance(stake_value, str) and stake_value.isdigit()
                        ):
                            raise ValueError(f"current_validators[{index}].stake must be an integer")
                        total_stake_yocto += int(stake_value)
                    item = {
                        "utc_date": day_text,
                        "block_height": block_height,
                        "total_active_stake_yocto": str(total_stake_yocto),
                    }
                    existing_items[day_text] = item
                    _write_checkpoint(output, document, existing_items)
                    completed += 1
                    break
                except Exception as exc:
                    status_code = getattr(exc, "status_code", getattr(exc, "code", None))
                    is_retryable = (
                        status_code in {408, 425, 429, 500, 502, 503, 504}
                        or isinstance(exc, (URLError, TimeoutError, OSError))
                        or isinstance(exc, HTTPError)
                        and status_code in {408, 425, 429, 500, 502, 503, 504}
                        or "timeout" in type(exc).__name__.lower()
                    )
                    if not is_retryable or attempt + 1 >= max_attempts:
                        request_error = exc
                        break
                    backoff = min(base_backoff_seconds * (2 ** attempt), 60.0)
                    backoff += random.uniform(0, min(backoff * 0.25, 2.0))
                    console.print(f"[yellow]![/yellow] {day_text} retrying in {backoff:.1f}s [dim]{exc}[/dim]")
                    sleep(backoff)
            if request_error is not None:
                failures.append({
                    "date": day_text,
                    "block_height": str(block_height),
                    "error": str(request_error),
                })
                error(
                    f"FastNEAR stake request failed for {day_text} · block {block_height}",
                    details=f"{type(request_error).__name__}: {request_error}",
                )
                continue

            if completed and completed % 10 == 0:
                console.print(
                    f"[green]OK[/green] saved {completed}/{total_pending} day(s) "
                    f"[dim]latest {day_text} · request {row_index}/{total_pending}[/dim]"
                )

        console.print(f"[green]OK[/green] {source.name}: {len(existing_items)} days saved, {completed} new -> {output}")
        if failures:
            console.print(f"[yellow]![/yellow] {len(failures)} RPC day(s) unavailable [dim]{failures[:5]}[/dim]")
        if missing_days or failures:
            if missing_days:
                console.print(f"[dim]daily_supply has no heights for {missing_days[:5]}[/dim]")
            return False
        return True
    except Exception as exc:
        error(
            f"{source.name} failed; saved checkpoints are preserved",
            details=f"{type(exc).__name__}: {exc}",
        )
        return False
