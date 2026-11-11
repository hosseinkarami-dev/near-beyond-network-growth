"""Google BigQuery query definitions and raw dataset collectors."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from common import SourceName, get_source, raw_path
from atomic_io import atomic_write_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY_DIR = Path(__file__).resolve().parent / "queries"
DAILY_SUPPLY_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_SUPPLY))
DAILY_GROSS_BURN_PATH = raw_path(get_source(SourceName.BIGQUERY_DAILY_GROSS_BURN))


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
DAILY_CONTRACT_REWARDS_QUERY = QueryDefinition(
    name="daily_contract_rewards",
    sql_file="daily_contract_rewards.sql",
    start_date=date(2020, 1, 1),
)


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


def collect_daily_contract_rewards(
    output_path: Path = raw_path(get_source(SourceName.BIGQUERY_DAILY_CONTRACT_REWARDS)),
    *,
    client: Any | None = None,
    today_utc: date | None = None,
) -> bool:
    """Append missing completed UTC days of contract rewards to raw JSON."""

    return _collect_daily_dataset(
        DAILY_CONTRACT_REWARDS_QUERY,
        output_path,
        client=client,
        today_utc=today_utc,
    )


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
            existing = json.loads(output_path.read_text(encoding="utf-8"))
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
