"""Google BigQuery query definitions and raw dataset collectors."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_text
from buybacks import BUYBACK_TRANSFER_SENDERS, BUYBACK_TRANSFER_TYPES
from google.cloud import bigquery
from sources import SourceName, get_source, raw_path


QUERY_DIR = Path(__file__).resolve().parents[1] / "queries"
DAILY_SUPPLY_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_SUPPLY))
DAILY_GROSS_BURN_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_GROSS_BURN))
CONTRACT_REWARD_AUDIT_PATH = raw_path(get_source(SourceName.BIGQUERY_CONTRACT_REWARD_AUDIT))
CONTRACT_REWARD_AUDIT_START = date(2026, 1, 1)
CONTRACT_REWARD_AUDIT_END = date(2026, 11, 4)
CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED = 320 * 1024**3
BUYBACK_TRANSFERS_START = date(2026, 4, 1)
BUYBACK_TYPE_SENDERS = BUYBACK_TRANSFER_SENDERS
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
    "BUYBACK_TRANSFER_TYPES",
    "BUYBACK_TYPE_SENDERS",
    "CONTRACT_REWARD_AUDIT_END",
    "CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED",
    "CONTRACT_REWARD_AUDIT_PATH",
    "CONTRACT_REWARD_AUDIT_START",
    "DAILY_GROSS_BURN_PATH",
    "DAILY_GROSS_BURN_QUERY",
    "DAILY_SUPPLY_PATH",
    "DAILY_SUPPLY_QUERY",
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
            print(f"contract_reward_event_audit: raw output exists but is unreadable; refusing to rerun: {exc}")
            return False
        query_range = existing.get("query_range") if isinstance(existing, dict) else None
        complete_existing = (
            existing.get("complete") is True
            and isinstance(existing.get("items"), list)
            and isinstance(query_range, dict)
        ) if isinstance(existing, dict) else False
        if not complete_existing:
            print("contract_reward_event_audit: raw output exists but is not marked complete; refusing to rerun")
            return False
        requested_start = CONTRACT_REWARD_AUDIT_START.isoformat()
        requested_end = CONTRACT_REWARD_AUDIT_END.isoformat()
        if query_range.get("start_date") == requested_start and query_range.get("end_date") == requested_end:
            print("contract_reward_event_audit: complete raw result already exists; BigQuery request skipped")
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
            print("contract_reward_event_audit: complete raw result covers the configured range; BigQuery request skipped")
            return True
        try:
            can_expand = (
                date.fromisoformat(query_range["start_date"]) > CONTRACT_REWARD_AUDIT_START
                and query_range.get("end_date") == requested_end
            )
        except (KeyError, TypeError, ValueError):
            can_expand = False
        if not can_expand:
            print("contract_reward_event_audit: existing complete range is incompatible; refusing to replace it")
            return False
        print(
            "contract_reward_event_audit: expanding complete raw range "
            f"from {query_range['start_date']} to {requested_start}; existing data will be kept unless query succeeds"
        )

    try:
        sql = (QUERY_DIR / "contract_reward_event_audit.sql").read_text(encoding="utf-8")
        bq_client = client or bigquery.Client()
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=CONTRACT_REWARD_AUDIT_MAX_BYTES_BILLED
        )
        rows = [dict(row.items()) for row in bq_client.query(sql, job_config=job_config).result()]
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
        print(f"contract_reward_event_audit: failure: {type(exc).__name__}: {exc}")
        return False


def collect_buyback_transfers(
    output_path: Path | None = None,
    *,
    client: Any | None = None,
    today_utc: date | None = None,
) -> bool:
    """Incrementally collect daily buyback-wallet inflows by transfer type."""

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

        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for index, row in enumerate(existing):
            if not isinstance(row, dict):
                raise ValueError(f"buyback_transfers record {index} must be an object")
            try:
                day = date.fromisoformat(row["utc_date"])
                transfer_type = row["transfer_type"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"buyback_transfers record {index} needs utc_date and transfer_type") from exc
            if transfer_type == "internal_treasury_transfer" \
                    and row.get("sender") == "1csfundsadmin.sputnik-dao.near":
                transfer_type = "oneclick_and_other_revenue"
                row["transfer_type"] = transfer_type
            if day.isoformat() != row["utc_date"] or transfer_type not in BUYBACK_TRANSFER_TYPES:
                raise ValueError(f"buyback_transfers record {index} has an invalid date or transfer_type")
            key = (day.isoformat(), transfer_type)
            if key in by_key:
                raise ValueError(f"buyback_transfers contains duplicate {key}")
            by_key[key] = row

        missing_by_day: list[tuple[date, tuple[str, ...]]] = []
        for ordinal in range(BUYBACK_TRANSFERS_START.toordinal(), last_complete_day.toordinal() + 1):
            day_text = date.fromordinal(ordinal).isoformat()
            missing_types = tuple(sorted(
                transfer_type for transfer_type in BUYBACK_TRANSFER_TYPES
                if (day_text, transfer_type) not in by_key
            ))
            if missing_types:
                missing_by_day.append((date.fromisoformat(day_text), missing_types))

        if not missing_by_day:
            latest = max((date.fromisoformat(day) for day, _ in by_key), default=None)
            print(f"buyback_transfers: raw data already complete through {latest}; BigQuery request skipped")
            return True

        # Query only consecutive date ranges with the same missing transfer types.
        ranges: list[tuple[date, date, tuple[str, ...]]] = []
        range_start = previous = missing_by_day[0][0]
        range_types = missing_by_day[0][1]
        for day, missing_types in missing_by_day[1:]:
            if day != previous + timedelta(days=1) or missing_types != range_types:
                ranges.append((range_start, previous + timedelta(days=1), range_types))
                range_start = day
                range_types = missing_types
            previous = day
        ranges.append((range_start, previous + timedelta(days=1), range_types))

        bq_client = client or bigquery.Client()
        job_config = bigquery.QueryJobConfig(maximum_bytes_billed=BUYBACK_MAX_BYTES_BILLED)
        for range_start, range_end, range_types in ranges:
            query = _load_query(
                QueryDefinition("buyback_transfers", "buyback_transfers.sql", BUYBACK_TRANSFERS_START),
                range_start,
                range_end,
            ).replace(
                "{{senders}}",
                ", ".join(f"'{BUYBACK_TYPE_SENDERS[transfer_type]}'" for transfer_type in range_types),
            )
            rows = [dict(row.items()) for row in bq_client.query(query, job_config=job_config).result()]
            for row in rows:
                row_day = row.get("utc_date")
                if isinstance(row_day, datetime):
                    row_day = row_day.date()
                if isinstance(row_day, date):
                    row["utc_date"] = row_day.isoformat()
                key = (row.get("utc_date"), row.get("transfer_type"))
                if key[1] not in BUYBACK_TRANSFER_TYPES:
                    raise ValueError(f"buyback query returned unknown transfer_type: {key[1]}")
                by_key[key] = row

            for ordinal in range(range_start.toordinal(), range_end.toordinal()):
                day_text = date.fromordinal(ordinal).isoformat()
                if any((day_text, transfer_type) not in by_key for transfer_type in range_types):
                    raise ValueError(f"buyback query omitted a transfer type for {day_text}")
            merged = [by_key[key] for key in sorted(by_key)]
            atomic_write_text(
                output_path,
                json.dumps(merged, indent=2, ensure_ascii=False, default=_json_value) + "\n",
            )
            print(
                f"buyback_transfers: collected {range_start} through {range_end - timedelta(days=1)} "
                f"for {', '.join(range_types)} ({len(rows)} transfer-type rows)"
            )
        return True
    except Exception as exc:
        print(f"buyback_transfers: failure: {type(exc).__name__}: {exc}")
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
            print(f"{definition.name}: up to date through {last_date}")
            return True

        query = _load_query(definition, start_date, end_date)
        bq_client = client or bigquery.Client()
        rows = [dict(row.items()) for row in bq_client.query(query).result()]
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
        print(f"{definition.name}: collected {len(additions)} records -> {output_path}")
        return True
    except Exception as exc:
        print(f"{definition.name}: failure: {exc}")
        return False
