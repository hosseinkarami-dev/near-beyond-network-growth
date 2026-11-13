"""Raw source fetching and orchestration."""

import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atomic_io import atomic_write_bytes, atomic_write_text
from console_ui import console
from paths import PROJECT_ROOT
from sources import SOURCES, Source, SourceName, SourceProvider, get_source, raw_path
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


NEARBLOCKS_MIN_REQUEST_INTERVAL_SECONDS = 1.0
NEARBLOCKS_BACKOFF_BASE_SECONDS = 1.0
NEARBLOCKS_MAX_ATTEMPTS = 5
NEARBLOCKS_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_last_nearblocks_response_at: float | None = None


def _retry_after_seconds(error: HTTPError) -> float | None:
    """Read Retry-After as seconds or an HTTP date when provided by NearBlocks."""

    raw_value = error.headers.get("Retry-After") if error.headers else None
    if not raw_value:
        return None
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw_value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0)
        except (TypeError, ValueError, OverflowError):
            return None


def _nearblocks_urlopen(request: Request, timeout: int):
    """Rate-limit NearBlocks and retry transient throttling/server responses."""

    global _last_nearblocks_response_at
    for attempt in range(NEARBLOCKS_MAX_ATTEMPTS):
        if _last_nearblocks_response_at is not None:
            elapsed = time.monotonic() - _last_nearblocks_response_at
            wait_seconds = NEARBLOCKS_MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if wait_seconds > 0:
                time.sleep(wait_seconds)
        try:
            response = urlopen(request, timeout=timeout)
            _last_nearblocks_response_at = time.monotonic()
            return response
        except HTTPError as exc:
            _last_nearblocks_response_at = time.monotonic()
            if exc.code not in NEARBLOCKS_RETRYABLE_STATUS_CODES \
                    or attempt + 1 >= NEARBLOCKS_MAX_ATTEMPTS:
                raise
            retry_after = _retry_after_seconds(exc)
            backoff = NEARBLOCKS_BACKOFF_BASE_SECONDS * (2 ** attempt)
            wait_seconds = max(retry_after or 0.0, backoff)
            console.print(
                f"[yellow]![/yellow] NearBlocks HTTP {exc.code}; retrying in {wait_seconds:.1f}s "
                f"[dim]({attempt + 1}/{NEARBLOCKS_MAX_ATTEMPTS - 1})[/dim]"
            )
            exc.close()
            time.sleep(wait_seconds)
    raise RuntimeError("NearBlocks retry loop exited unexpectedly")


def nearblocks_api_key() -> str | None:
    """Return an optional NearBlocks key from the environment or project .env."""

    configured_key = os.environ.get("NEARBLOCKS_API_KEY", "").strip()
    if configured_key:
        return configured_key

    try:
        lines = (PROJECT_ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        name, separator, value = entry.partition("=")
        if not separator or name.strip() != "NEARBLOCKS_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            value = value.split("#", maxsplit=1)[0].strip()
        return value or None

    return None


def _utc_date(value: object) -> date | None:
    """Interpret common ISO and Unix timestamp values as a UTC calendar date."""
    try:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                if not value.isdigit():
                    return None
                value = int(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        timestamp = float(value)
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        if timestamp < 100_000_000:
            return None
        return datetime.fromtimestamp(timestamp, timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _latest_daily_date(value: object, key: str | None = None) -> date | None:
    """Find the newest date in the common daily API response shapes."""
    dates: list[date] = []
    if isinstance(value, dict):
        for field, child in value.items():
            if str(field).lower() in {"date", "timestamp", "time", "datetime"}:
                parsed = _utc_date(child)
                if parsed is not None:
                    dates.append(parsed)
            dates.extend([d for d in [_latest_daily_date(child, str(field))] if d is not None])
    elif isinstance(value, list):
        if len(value) >= 2 and not isinstance(value[0], (dict, list)):
            parsed = _utc_date(value[0])
            if parsed is not None:
                dates.append(parsed)
        for child in value:
            parsed_child = _latest_daily_date(child, key)
            if parsed_child is not None:
                dates.append(parsed_child)
    elif key and key.lower() in {"date", "timestamp", "time", "datetime"}:
        parsed = _utc_date(value)
        if parsed is not None:
            dates.append(parsed)
    return max(dates) if dates else None


def fetch_json(source: Source, timeout: int = 30) -> bool:
    """Fetch valid, non-empty JSON and save the exact response bytes."""

    try:
        output = raw_path(source)
        if source.frequency == "daily" and source.provider in {
            SourceProvider.NEARBLOCKS, SourceProvider.DEFILLAMA,
        } and output.exists():
            previous = json.loads(output.read_text(encoding="utf-8-sig"))
            yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
            latest_date = _latest_daily_date(previous)
            if latest_date is not None and latest_date >= yesterday:
                console.print(f"[green]OK[/green] {source.name} [dim]current through {latest_date}; request skipped[/dim]")
                return True

        headers = {"Accept": "application/json"}
        if source.provider is SourceProvider.NEARBLOCKS:
            headers["User-Agent"] = "NEARscope-Analytics/1.0"
            api_key = nearblocks_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        if source.url is None:
            raise ValueError(f"{source.name} does not have an HTTP endpoint")

        request = Request(
            source.url,
            method="GET",
            headers=headers,
        )

        open_request = _nearblocks_urlopen if source.provider is SourceProvider.NEARBLOCKS else urlopen
        with open_request(request, timeout=timeout) as response:
            raw = response.read()

        if not raw.strip():
            raise ValueError("Empty response")

        json.loads(raw)

        atomic_write_bytes(output, raw)

        console.print(f"[green]✓[/green] {source.name} [dim]({len(raw):,} bytes)[/dim]")
        return True

    except (
        HTTPError,
        HTTPException,
        URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        status = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else ""
        detail = f" ({status})" if status else ""

        console.print(f"[red]✗[/red] {source.name} [dim]{detail} {exc}[/dim]")
        return False


def fetch_nearblocks_validators(source: Source, timeout: int = 30) -> bool:
    """Fetch every cursor page of validator data and preserve each response."""
    pages = []
    cursor = None
    seen_cursors = set()
    try:
        if source.url is None:
            raise ValueError(f"{source.name} does not have an HTTP endpoint")
        parts = urlsplit(source.url)
        for page_number in range(100):
            params = {"limit": 100}
            if cursor:
                params["next"] = cursor
            request_url = urlunsplit((
                parts.scheme, parts.netloc, parts.path, urlencode(params), "",
            ))
            headers = {"Accept": "application/json", "User-Agent": "NEARscope-Analytics/1.0"}
            api_key = nearblocks_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            with _nearblocks_urlopen(Request(request_url, headers=headers), timeout=timeout) as response:
                raw = response.read()
            if not raw.strip():
                raise ValueError(f"Empty response on validator page {page_number + 1}")
            page = json.loads(raw)
            if not isinstance(page, dict) or not isinstance(page.get("data"), list):
                raise ValueError(f"Validator page {page_number + 1} must contain a data list")
            pages.append(page)
            pagination = page.get("pagination")
            next_cursor = page.get("next_page")
            if next_cursor is None and isinstance(pagination, dict):
                next_cursor = pagination.get("next_page") or pagination.get("next")
            meta = page.get("meta")
            if next_cursor is None and isinstance(meta, dict):
                next_cursor = meta.get("next_page") or meta.get("next")
            if next_cursor is None:
                break
            next_cursor = str(next_cursor)
            if next_cursor in seen_cursors:
                raise ValueError("NearBlocks validator pagination returned a repeated cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise ValueError("NearBlocks validator pagination exceeded 100 pages")

        output = raw_path(source)
        atomic_write_text(output, json.dumps({"pages": pages}, separators=(",", ":")))
        total_items = sum(len(page["data"]) for page in pages)
        console.print(f"[green]✓[/green] {source.name} [dim]{total_items:,} validators · {len(pages)} pages[/dim]")
        return True
    except (
        HTTPError, HTTPException, URLError, TimeoutError, OSError,
        json.JSONDecodeError, ValueError,
    ) as exc:
        status_text = f" (HTTP {exc.code})" if isinstance(exc, HTTPError) else ""
        console.print(f"[red]✗[/red] {source.name} [dim]{status_text} {exc}[/dim]")
        return False


def fetch_binance_klines(source: Source, timeout: int = 30, today: date | None = None) -> bool:
    """Fetch NEARUSDT daily klines in bounded, resumable calendar chunks."""
    output = raw_path(source)
    current_day = today or datetime.now(timezone.utc).date()
    latest_complete_day = current_day - timedelta(days=1)
    day_ms = 86_400_000
    initial_day = date(2021, 1, 1)

    try:
        if output.exists():
            records = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("Existing Binance raw data must be a list")
            timestamps = []
            for index, record in enumerate(records):
                if not isinstance(record, list) or len(record) != 12:
                    raise ValueError(f"Existing Binance record {index} is malformed")
                timestamp = record[0]
                if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                    raise ValueError(f"Existing Binance record {index} has an invalid open time")
                timestamps.append(timestamp)
            if timestamps != sorted(set(timestamps)):
                raise ValueError("Existing Binance records must be chronological and unique")
            latest_day = (datetime.fromtimestamp(timestamps[-1] / 1000, timezone.utc).date()
                          if timestamps else None)
            if latest_day is not None and latest_day >= latest_complete_day:
                console.print(f"[green]✓[/green] {source.name} [dim]already current through {latest_day}[/dim]")
                return True
            start_day = latest_day + timedelta(days=1) if latest_day else initial_day
        else:
            records = []
            start_day = initial_day
            atomic_write_text(output, "[]\n")

        by_timestamp = {record[0]: record for record in records}
        if source.url is None:
            raise ValueError(f"{source.name} does not have an HTTP endpoint")
        parts = urlsplit(source.url)
        while start_day <= latest_complete_day:
            end_day = min(start_day + timedelta(days=364), latest_complete_day)
            params = urlencode({
                "symbol": "NEARUSDT",
                "interval": "1d",
                "startTime": (start_day - date(1970, 1, 1)).days * day_ms,
                "endTime": (end_day - date(1970, 1, 1)).days * day_ms + day_ms - 1,
            })
            request_url = urlunsplit((parts.scheme, parts.netloc, parts.path, params, ""))
            request = Request(request_url, method="GET", headers={"Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
            if not isinstance(payload, list):
                raise ValueError("Binance Kline response must be a list")
            if not payload:
                break
            added = 0
            for index, record in enumerate(payload):
                if not isinstance(record, list) or len(record) != 12:
                    raise ValueError(f"Binance response record {index} is malformed")
                timestamp = record[0]
                if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                    raise ValueError(f"Binance response record {index} has an invalid open time")
                record_day = datetime.fromtimestamp(timestamp / 1000, timezone.utc).date()
                if start_day <= record_day <= end_day and timestamp not in by_timestamp:
                    by_timestamp[timestamp] = record
                    added += 1
            records = [by_timestamp[key] for key in sorted(by_timestamp)]
            atomic_write_text(output, json.dumps(records, separators=(",", ":")))
            console.print(f"[green]✓[/green] {source.name} [dim]through {end_day} · {added} new days[/dim]")
            if added == 0:
                break
            latest_day = datetime.fromtimestamp(records[-1][0] / 1000, timezone.utc).date()
            if latest_day >= latest_complete_day:
                break
            start_day = end_day + timedelta(days=1)
        return True
    except (
        HTTPError, HTTPException, URLError, TimeoutError, OSError,
        json.JSONDecodeError, ValueError, OverflowError,
    ) as exc:
        status = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else ""
        detail = f" ({status})" if status else ""
        console.print(f"[red]✗[/red] {source.name} [dim]{detail} {exc}[/dim]")
        return False


def fetch_bigquery(source: Source) -> bool:
    """Collect a registered BigQuery dataset using its provider client."""

    try:
        from collectors.bigquery import (
            collect_buyback_transfers,
            collect_contract_reward_audit,
            collect_daily_gross_burn,
            collect_daily_supply,
        )

        collectors = {
            SourceName.BIGQUERY_DAILY_SUPPLY: collect_daily_supply,
            SourceName.BIGQUERY_DAILY_GROSS_BURN: collect_daily_gross_burn,
            SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT: collect_contract_reward_audit,
            SourceName.BIGQUERY_BUYBACK_TRANSFERS: collect_buyback_transfers,
        }
        return collectors[source.name](raw_path(source))
    except Exception as exc:
        console.print(f"[red]✗[/red] {source.name} [dim]{exc}[/dim]")
        return False


def fetch_buyback_wallet_balance(source: Source, timeout: float = 30) -> bool:
    """Refresh the latest liquid balance snapshot for the buyback wallet."""
    try:
        from collectors.buyback_wallet_balance import collect_buyback_wallet_balance

        return collect_buyback_wallet_balance(source, timeout=timeout)
    except Exception as exc:
        console.print(f"[red]✗[/red] {source.name} [dim]{type(exc).__name__}: {exc}[/dim]")
        return False


def _fetch_order(sources: tuple[Source, ...]) -> tuple[Source, ...]:
    """Defer daily validator stake until all source data, including supply, is ready."""

    stake_source_name = SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE
    return tuple(source for source in sources if source.name != stake_source_name) + tuple(
        source for source in sources if source.name == stake_source_name
    )


def fetch_all(sources: tuple[Source, ...] = SOURCES) -> bool:
    """Attempt every source and isolate failures to the affected dataset."""

    all_succeeded = True
    ordered_sources = _fetch_order(sources)
    with Progress(
        SpinnerColumn(style="bright_green"), TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=28), "{task.completed}/{task.total}", TimeElapsedColumn(),
        console=console, transient=False,
    ) as progress:
        task = progress.add_task("Fetching sources", total=len(ordered_sources))
        for source in ordered_sources:
            progress.update(task, description=f"Fetching {source.name}")
            try:
                if source.provider is SourceProvider.BIGQUERY:
                    succeeded = fetch_bigquery(source)
                elif source.name == SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE:
                    from collectors.fastnear_validator_stake import collect_daily_active_validator_stake

                    succeeded = collect_daily_active_validator_stake(source)
                elif source.name == SourceName.BINANCE_NEARUSDT_DAILY_KLINES:
                    succeeded = fetch_binance_klines(source)
                elif source.name == SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE:
                    succeeded = fetch_buyback_wallet_balance(source)
                elif source.name == SourceName.NEAR_BLOCKS_VALIDATORS:
                    succeeded = fetch_nearblocks_validators(source)
                else:
                    succeeded = fetch_json(source)
            except Exception as exc:
                console.print(f"[red]✗[/red] {source.name} [dim]{type(exc).__name__}: {exc}[/dim]")
                succeeded = False
            all_succeeded = all_succeeded and succeeded
            progress.advance(task)
    return all_succeeded


def main() -> int:
    """Run the raw data collection phase."""

    return 0 if fetch_all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
