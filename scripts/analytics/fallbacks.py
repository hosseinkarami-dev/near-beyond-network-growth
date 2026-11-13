"""Minimal snapshots that keep dashboard sections available without source data."""
from pathlib import Path
from typing import Any

from data_dirs import clear_directory
from validation import validate_json


NETWORK_ROOT = Path("network")
TOKENOMICS_ROOT = Path("tokenomics")
INTENTS_ROOT = Path("near_intents")
PROTOCOL_ROOT = Path("protocols")


def _write_snapshot(root: Path, document: dict[str, Any]) -> Path:
    path = root / "snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(validate_json(document), encoding="utf-8")
    return path


def _reset(path: Path) -> None:
    path = Path(path)
    clear_directory(path, allowed_parent=path.parent)


def write_empty_network_snapshot(root: Path) -> Path:
    section = Path(root) / NETWORK_ROOT
    _reset(section)
    return _write_snapshot(section, {
        "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": None,
        "network_stats": {}, "key_metrics": {},
        "data_status": "unavailable",
    })


def write_empty_tokenomics_snapshot(root: Path) -> Path:
    section = Path(root) / TOKENOMICS_ROOT
    _reset(section)
    snapshot = _write_snapshot(section, {
        "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": None,
        "metrics": {}, "validators": {"updated_at": None, "items": []},
        "data_status": "unavailable",
    })
    empty_series = (
        "daily_tokenomics.json", "daily_burn.json", "daily_issuance.json",
        "daily_active_validator_stake.json", "daily_buyback_transfers.json",
    )
    period_series = (
        "tokenomics", "burn", "issuance", "active_validator_stake", "buyback_transfers",
    )
    documents = [(name, {"items": []}) for name in empty_series]
    for period in ("weekly", "monthly", "quarterly", "yearly"):
        documents.extend((f"{period}_{series}.json", {"items": []}) for series in period_series)
    documents.append(("buyback_transfer_type_breakdown.json", {"observations": []}))
    for name, document in documents:
        (section / name).write_text(validate_json({
            "schema_version": "1.0.0", "network": "NEAR mainnet",
            "data_status": "unavailable", **document,
        }), encoding="utf-8")
    return snapshot


def write_empty_intents_snapshot(root: Path) -> Path:
    section = Path(root) / INTENTS_ROOT
    _reset(section)
    return _write_snapshot(section, {
        "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": None,
        "volume": {}, "tvl_usd": None, "tvl_near": None, "key_metrics": {},
        "data_status": "unavailable",
    })


def write_empty_protocol_snapshots(root: Path) -> dict[str, Path]:
    return {
        category: write_empty_protocol_snapshot(root, category)
        for category in ("fees", "revenue", "dex_volume")
    }


def write_empty_protocol_snapshot(root: Path, category: str) -> Path:
    section = Path(root) / PROTOCOL_ROOT / category
    _reset(section)
    return _write_snapshot(section, {
        "schema_version": "1.0.0", "network": "NEAR mainnet", "updated_at": None,
        "summary": {}, "data_status": "unavailable",
    })
