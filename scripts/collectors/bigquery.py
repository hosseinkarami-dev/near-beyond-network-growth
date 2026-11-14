"""Google BigQuery query definitions and raw dataset collectors."""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_text
from console_ui import dataset_saved, dataset_skipped, dataset_up_to_date, error, stage
from google.cloud import bigquery
from request_state import request_finished, request_started
from sources import SourceName, get_source, raw_path


QUERY_DIR = Path(__file__).resolve().parents[1] / "queries"
DAILY_SUPPLY_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_SUPPLY))
DAILY_GROSS_BURN_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_GROSS_BURN))
CONTRACT_REWARD_AUDIT_PATH = raw_path(get_source(SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT))
CONTRACT_REWARD_AUDIT_START = date(2026, 1, 1)
CONTRACT_REWARD_AUDIT_END = date(2026, 10, 4)
CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED = 320 * 1024**3
BUYBACK_TRANSFERS_START = date(2026, 4, 1)
BUYBACK_MAX_BYTES_BILLED = 100 * 1024**3


@dataclass(frozen=True)
class QueryDefinition:
    """Configuration for a daily BigQuery dataset query."""

    name: str
    sql_file: str
    start_date: date


DAILY_SUPPLY_QUERY = QueryDefinition(
    name="daily_supply",
    sql_file="daily_supply.sql",
    start_date=date(2020, 1, 1),
)
DAILY_GROSS_BURN_QUERY = QueryDefinition(
    name="daily_gross_burn",
    sql_file="daily_gross_burn.sql",
    start_date=date(2020, 1, 1),
)


__all__ = [
    "BUYBACK_MAX_BYTES_BILLED",
    "BUYBACK_TRANSFERS_START",
    "CONTRACT_REWARD_AUDIT_END",
    "CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED",
    "CONTRACT_REWARD_AUDIT_PATH",
    "CONTRACT_REWARD_AUDIT_START",
    "DAILY_GROSS_BURN_PATH",
    "DAILY_GROSS_BURN_QUERY",
    "DAILY_SUPPLY_PATH",
    "DAILY_SUPPLY_QUERY",
    "QUERY_DEFINITION",
    "COLLECT_BUYBACK_TRANSFERS",
    "COLLECT_CONTRACT_REWARD_AUDIT",
    "COLLECT_DAILY_GROSS_BURN",
    "COLLECT_DAILY_SUPPLY",
    "QueryDefinition",
    "collect_buyback_transfers",
    "collect_contract_reward_audit",
    "collect_daily_gross_burn",
    "collect_daily_supply",
]


def _load_query(definition: QueryDefinition, start_date: date, end_date: date) -> str:
    """Load a query and configure its requested date range."""

    sql = (QUERY_DIR / definition.sql_file).read_text(encoding="utf-8")
    return (sql.replace("{{start_date}}", start_date.isoformat())
            .replace("{{end_date}}", end_date.isoformat()))


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Cannot serialize BigQuery value: {type(value).__name__}")


def _query_rows(source_name: SourceName, client: Any, query: str, *, job_config=None):
    """Run a BigQuery request and persist its request timestamp and outcome."""
    source = get_source(source_name)
    request_started(source)
    try:
        job = client.query(query, job_config=job_config) if job_config is not None else client.query(query)
        rows = [dict(row.items()) for row in job.result()]
    except BaseException as exc:
        request_finished(source, exc)
        raise
    request_finished(source)
    return rows


def collect_daily_supply(
    output_path: Path = DAILY_SUPPLY_PATH,
    *,
    client: Any | None = None,
    today_utc: date | None = None,
) -> bool:
    """Append any missing completed UTC days to the raw daily supply JSON."""

    return _collect_daily_dataset(
        DAILY_SUPPLY_QUERY, output_path, client=client, today_utc=today_utc
    )


def collect_daily_gross_burn(
    output_path: Path = DAILY_GROSS_BURN_PATH,
    *,
    client: Any | None = None,
    today_utc: date | None = None,
) -> bool:
    """Append daily raw burn aggregates; tokens_burnt is source FLOAT precision."""

    return _collect_daily_dataset(
        DAILY_GROSS_BURN_QUERY, output_path, client=client, today_utc=today_utc
    )


def collect_contract_reward_audit(
    output_path: Path = CONTRACT_REWARD_AUDIT_PATH,
    *,
    client: Any | None = None,
) -> bool:
    """Run the fixed-range audit once; expand an older complete range atomically."""

    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            error(
                "Contract reward event audit raw output is unreadable; refusing to rerun",
                details=f"{type(exc).__name__}: {exc}",
            )
            return False
        query_range = existing.get("query_range") if isinstance(existing, dict) else None
        complete_existing = (
            existing.get("complete") is True
            and isinstance(existing.get("items"), list)
            and isinstance(query_range, dict)
        ) if isinstance(existing, dict) else False
        if not complete_existing:
            error("Contract reward event audit raw output is not marked complete; refusing to rerun")
            return False
        requested_start = CONTRACT_REWARD_AUDIT_START.isoformat()
        requested_end = CONTRACT_REWARD_AUDIT_END.isoformat()
        if query_range.get("start_date") == requested_start and query_range.get("end_date") == requested_end:
            dataset_skipped("Contract reward event audit", "complete raw result already exists")
            return True
        try:
            existing_covers_requested = (
                query_range.get("start_date") == requested_start
                and date.fromisoformat(query_range["end_date"])
                >= CONTRACT_REWARD_AUDIT_END
            )
        except (KeyError, TypeError, ValueError):
            existing_covers_requested = False
        if existing_covers_requested:
            dataset_skipped("Contract reward event audit", "complete raw result covers the configured range")
            return True
        try:
            can_expand = (
                date.fromisoformat(query_range["start_date"]) > CONTRACT_REWARD_AUDIT_START
                and query_range.get("end_date") == requested_end
            )
        except (KeyError, TypeError, ValueError):
            can_expand = False
        if not can_expand:
            error("Contract reward event audit range is incompatible; refusing to replace existing raw data")
            return False
        stage(
            "Contract reward event audit",
            f"expanding range {query_range['start_date']} → {requested_start}",
        )

    try:
        sql = (QUERY_DIR / "contract_reward_event_audit.sql").read_text(encoding="utf-8")
        bq_client = client or bigquery.Client()
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED
        )
        rows = _query_rows(
            SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT, bq_client, sql,
            job_config=job_config,
        )
        items = []
        for row in rows:
            row_date = row.get("utc_date")
            if isinstance(row_date, datetime):
                row_date = row_date.date()
            if isinstance(row_date, date):
                row["utc_date"] = row_date.isoformat()
            items.append(row)

        document = {
            "schema_version": "1.0.0",
            "dataset": "Contract Reward Event Audit",
            "source": "bigquery-public-data.crypto_near_mainnet_us.account_changes",
            "query_file": "contract_reward_event_audit.sql",
            "query_range": {
                "start_date": CONTRACT_REWARD_AUDIT_START.isoformat(),
                "end_date": CONTRACT_REWARD_AUDIT_END.isoformat(),
                "seed_lookback_days": 7,
            },
            "complete": True,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "row_count": len(items),
            "items": items,
        }
        atomic_write_text(
            output_path,
            json.dumps(document, indent=2, ensure_ascii=False, default=_json_value) + "\n",
        )
        print(f"contract_reward_event_audit: saved {len(items)} daily rows -> {output_path}")
        return True
    except Exception as exc:
        error(
            f"Contract reward event audit failed ({type(exc).__name__})",
            details=str(exc),
        )
        return False


def collect_buyback_transfers(
    output_path: Path | None = None,
    *,
    client: Any | None = None,
    today_utc: date | None = None,
) -> bool:
    """Incrementally collect whatever buyback-wallet inflow types BigQuery returns."""

    output_path = Path(output_path) if output_path is not None else raw_path(
        get_source(SourceName.BIGQUERY_BUYBACK_TRANSFERS)
    )
    try:
        today = today_utc or datetime.now(timezone.utc).date()
        last_complete_day = today - timedelta(days=1)
        existing: list[dict[str, Any]] = []
        if output_path.exists():
            existing = json.loads(output_path.read_text(encoding="utf-8-sig"))
            if not isinstance(existing, list):
                raise ValueError("buyback_transfers raw JSON must contain a list")

        by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        for index, row in enumerate(existing):
            if not isinstance(row, dict):
                raise ValueError(f"buyback_transfers record {index} must be an object")
            try:
                day = date.fromisoformat(row["utc_date"])
                transfer_type = row["transfer_type"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"buyback_transfers record {index} needs utc_date and transfer_type") from exc
            sender = row.get("sender")
            if (day.isoformat() != row["utc_date"]
                    or not isinstance(transfer_type, str) or not transfer_type.strip()
                    or not isinstance(sender, str) or not sender.strip()):
                raise ValueError(f"buyback_transfers record {index} has an invalid date or transfer_type")
            key = (day.isoformat(), transfer_type, sender)
            if key in by_key:
                raise ValueError(f"buyback_transfers contains duplicate {key}")
            by_key[key] = row

        observed_through = max(
            (date.fromisoformat(day) for day, _, _ in by_key
             if date.fromisoformat(day) <= last_complete_day),
            default=None,
        )
        range_start = max(
            BUYBACK_TRANSFERS_START,
            observed_through + timedelta(days=1) if observed_through else BUYBACK_TRANSFERS_START,
        )
        if range_start > last_complete_day:
            dataset_up_to_date("buyback transfers", observed_through)
            return True

        bq_client = client or bigquery.Client()
        job_config = bigquery.QueryJobConfig(maximum_bytes_billed=BUYBACK_MAX_BYTES_BILLED)
        range_end = last_complete_day + timedelta(days=1)
        query = _load_query(
            QueryDefinition("buyback_transfers", "buyback_transfers.sql", BUYBACK_TRANSFERS_START),
            range_start,
            range_end,
        )
        rows = _query_rows(
            SourceName.BIGQUERY_BUYBACK_TRANSFERS, bq_client, query,
            job_config=job_config,
        )
        new_rows = 0
        for row in rows:
            row_day = row.get("utc_date")
            if isinstance(row_day, datetime):
                row_day = row_day.date()
            elif isinstance(row_day, str):
                row_day = date.fromisoformat(row_day)
            if not isinstance(row_day, date):
                raise ValueError("buyback query returned a row without a valid utc_date")
            if not range_start <= row_day < range_end:
                continue
            transfer_type = row.get("transfer_type")
            sender = row.get("sender")
            if not isinstance(transfer_type, str) or not transfer_type.strip():
                raise ValueError("buyback query returned a row without a transfer_type")
            if not isinstance(sender, str) or not sender.strip():
                raise ValueError("buyback query returned a row without a sender")
            row["utc_date"] = row_day.isoformat()
            by_key[(row_day.isoformat(), transfer_type, sender)] = row
            new_rows += 1

        merged = [by_key[key] for key in sorted(by_key)]
        atomic_write_text(
            output_path,
            json.dumps(merged, indent=2, ensure_ascii=False, default=_json_value) + "\n",
        )
        print(
            f"buyback_transfers: collected {range_start} through {last_complete_day} "
            f"({new_rows} transfer rows; {len({row['transfer_type'] for row in rows if row.get('transfer_type')})} distinct types)"
        )
        return True
    except Exception as exc:
        failure_details = str(exc)
        billing = re.search(
            r"exceeded limit for bytes billed:\s*(\d+)\.\s*(\d+)\s+or higher required",
            failure_details,
            re.IGNORECASE,
        )
        if billing:
            cap_gib = int(billing.group(1)) / (1024**3)
            required_gib = int(billing.group(2)) / (1024**3)
            message = (
                f"Buyback transfers query exceeds the {cap_gib:.0f} GiB billing cap; "
                f"BigQuery requires at least {required_gib:.1f} GiB"
            )
        else:
            message = f"Buyback transfers query failed ({type(exc).__name__})"
        error(message, details=failure_details)
        return False


def _collect_daily_dataset(
    definition: QueryDefinition,
    output_path: Path,
    *,
    client: Any | None,
    today_utc: date | None,
) -> bool:
    """Append missing completed UTC dates for a configured BigQuery dataset."""

    try:
        today = today_utc or datetime.now(timezone.utc).date()
        end_date = today
        existing: list[dict[str, Any]] = []
        if output_path.exists():
            # Existing raw JSON may have been saved with a UTF-8 BOM by a
            # Windows editor. Strip it when reading before appending rows.
            existing = json.loads(output_path.read_text(encoding="utf-8-sig"))
            if not isinstance(existing, list):
                raise ValueError(f"{definition.name} JSON must contain a list of records")

        dates = {date.fromisoformat(record["utc_date"]) for record in existing}
        last_date = max(dates) if dates else None
        start_date = (last_date + timedelta(days=1)) if last_date else definition.start_date
        if start_date >= end_date:
            dataset_up_to_date(definition.name, last_date)
            return True


        query = _load_query(definition, start_date, end_date)
        bq_client = client or bigquery.Client()
        source_name = (
            SourceName.BIGQUERY_DAILY_SUPPLY
            if definition.name == "daily_supply"
            else SourceName.BIGQUERY_DAILY_GROSS_BURN
        )
        rows = _query_rows(source_name, bq_client, query)
        known_dates = dates
        additions = []
        for row in rows:
            row_date = row["utc_date"]
            if isinstance(row_date, datetime):
                row_date = row_date.date()
            row_date = date.fromisoformat(row_date) if isinstance(row_date, str) else row_date
            if row_date not in known_dates:
                row["utc_date"] = row_date.isoformat()
                additions.append(row)
                known_dates.add(row_date)

        merged = existing + additions
        merged.sort(key=lambda record: record["utc_date"])
        atomic_write_text(
            output_path,
            json.dumps(merged, indent=2, default=_json_value) + "\n",
        )
        dataset_saved(definition.name, len(additions), output_path)
        return True
    except Exception as exc:
        error(
            f"{definition.name.replace('_', ' ').title()} collection failed ({type(exc).__name__})",
            details=str(exc),
        )
        return False


# Uppercase public aliases provide the requested casing for pipeline imports;
# the conventional class and function names remain available for compatibility.
QUERY_DEFINITION = QueryDefinition
COLLECT_BUYBACK_TRANSFERS = collect_buyback_transfers
COLLECT_CONTRACT_REWARD_AUDIT = collect_contract_reward_audit
COLLECT_DAILY_GROSS_BURN = collect_daily_gross_burn
COLLECT_DAILY_SUPPLY = collect_daily_supply
