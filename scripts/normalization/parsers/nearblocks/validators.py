"""Normalize NearBlocks validator records without aggregating them."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sources import SourceName, source_metadata


def _pages(raw_data):
    if isinstance(raw_data, dict) and isinstance(raw_data.get("pages"), list):
        pages = raw_data["pages"]
    else:
        pages = [raw_data]
    rows = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise ValueError(f"Validator page {index} must contain a data list")
        rows.extend(page["data"])
    if not rows:
        raise ValueError("NearBlocks returned no validator records")
    return rows


def _first(row, *fields):
    for field in fields:
        if field in row and row[field] is not None:
            return row[field], field
    return None, None


def _decimal(value, field, *, yocto=False):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    if yocto and result >= Decimal("1e24"):
        result /= Decimal("1e24")
    return format(result, "f")


def _active(row):
    value, _ = _first(row, "is_active", "active")
    if value is not None:
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "active", "current"}
        return bool(value)
    status, _ = _first(row, "status", "state", "staking_status")
    if isinstance(status, str):
        return status.strip().lower() in {"active", "current", "producing"}
    raise ValueError("Validator record must declare is_active or status")


def _commission_pct(row):
    value, field = _first(
        row, "commission_pct", "commission_percent", "commission_rate",
        "commission_ratio", "fee_ratio", "commission", "fee",
    )
    if value is None:
        numerator, _ = _first(row, "fee_numerator")
        denominator, _ = _first(row, "fee_denominator")
        if numerator is not None and denominator is not None:
            if Decimal(str(denominator)) == 0:
                return None
            return _decimal(Decimal(str(numerator)) * 100 / Decimal(str(denominator)), "commission_pct")
        return None
    if isinstance(value, dict):
        numerator, _ = _first(value, "numerator")
        denominator, _ = _first(value, "denominator")
        if numerator is None or denominator is None or Decimal(str(denominator)) == 0:
            return None
        return _decimal(Decimal(str(numerator)) * 100 / Decimal(str(denominator)), "commission_pct")
    text = str(value).strip()
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1].strip()
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Validator commission must be numeric") from exc
    if field in {"commission_pct", "commission_percent"} or is_percent:
        pass
    elif field in {"commission_rate", "commission_ratio", "fee_ratio"}:
        amount *= 100
    if not amount.is_finite() or amount < 0 or amount > 100:
        raise ValueError("Validator commission must be between 0 and 100 percent")
    return format(amount, "f")


def _record(row, index):
    if not isinstance(row, dict):
        raise ValueError(f"Validator record {index} must be an object")
    account, _ = _first(row, "account_id", "account", "validator_id", "validator")
    if not isinstance(account, str) or not account.strip():
        raise ValueError(f"Validator record {index} has no account identifier")
    stake, _ = _first(
        row, "stake", "total_stake", "amount_staked", "staked", "current_epoch_stake",
    )
    delegators, _ = _first(row, "delegators_count", "delegators", "num_delegators")
    if isinstance(delegators, list):
        delegators = len(delegators)
    if delegators is not None:
        try:
            delegators = int(delegators)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Validator record {index} delegators must be an integer") from exc
        if delegators < 0:
            raise ValueError(f"Validator record {index} delegators must be non-negative")
    block_stats = row.get("block_stats") if isinstance(row.get("block_stats"), dict) else {}
    produced, _ = _first(
        row, "blocks_produced", "produced_blocks", "num_produced_blocks",
        "current_epoch_blocks_produced",
    )
    expected, _ = _first(
        row, "blocks_expected", "expected_blocks", "num_expected_blocks",
        "current_epoch_blocks_expected",
    )
    if produced is None:
        produced, _ = _first(block_stats, "produced", "blocks_produced")
    if expected is None:
        expected, _ = _first(block_stats, "expected", "blocks_expected")
    return {
        "account_id": account.strip(),
        "is_active": _active(row),
        "stake_near": _decimal(stake, f"validator {account} stake", yocto=True),
        "commission_pct": _commission_pct(row),
        "delegators_count": delegators,
        "blocks_produced": _decimal(produced, f"validator {account} blocks_produced"),
        "blocks_expected": _decimal(expected, f"validator {account} blocks_expected"),
    }


def parse_validators(raw_data):
    rows = [_record(row, index) for index, row in enumerate(_pages(raw_data))]
    accounts = [row["account_id"] for row in rows]
    if len(accounts) != len(set(accounts)):
        raise ValueError("NearBlocks validator response contains duplicate account identifiers")
    return {
        "validators.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.NEAR_BLOCKS_VALIDATORS,
                attribution="Powered by NearBlocks.io APIs",
            ),
            "snapshot_type": "validator_registry",
            "frequency": "snapshot",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "items": rows,
        }
    }
