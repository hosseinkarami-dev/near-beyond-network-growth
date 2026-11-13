"""Normalize the current NearBlocks validator and staking snapshot."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sources import SourceName, source_metadata


def _source_data(raw_data):
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("data"), dict):
        raise ValueError("Expected NearBlocks validator response with a data object")
    return raw_data["data"]


def _decimal(value, field):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    # NearBlocks endpoints can expose token quantities in yoctoNEAR. The
    # human-readable validator summary is already in NEAR; detect raw yocto.
    if number >= Decimal("1e24"):
        number /= Decimal("1e24")
    return format(number, "f")


def _count(value, field):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError(f"{field} must be a non-negative integer")
    return int(number)


def parse_validators_info(raw_data):
    data = _source_data(raw_data)
    total_staked = data.get("total_staked")
    if total_staked is None:
        # The v3 endpoint currently names this field ``total_stake``.
        total_staked = data.get("total_stake")
    metrics = {
        "total_staked": {
            "metric_id": "near.total_staked", "name": "Total staked",
            "value": _decimal(total_staked, "total_staked"),
            "unit": "NEAR", "value_type": "decimal",
        },
        "current_validators_count": {
            "metric_id": "near.current_validators_count", "name": "Current validators",
            "value": _count(data.get("current_validators_count"), "current_validators_count"),
            "unit": "validators", "value_type": "integer",
        },
        "total_validators_count": {
            "metric_id": "near.total_validators_count", "name": "Total validators",
            "value": _count(data.get("total_validators_count"), "total_validators_count"),
            "unit": "validators", "value_type": "integer",
        },
    }
    return {
        "summary.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.NEAR_BLOCKS_VALIDATORS_INFO,
                attribution="Powered by NearBlocks.io APIs",
            ),
            "snapshot_type": "validator_staking",
            "frequency": "snapshot",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": metrics,
        }
    }
