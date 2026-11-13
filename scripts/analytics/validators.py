"""Build validator concentration, performance metrics, and leaderboard rows."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source, parse_float=Decimal)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _ratio_pct(numerator, denominator):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100


def build_validator_analytics(
    normalized_path: Path,
    circulating_supply: Decimal | None,
    *,
    network_total_stake: Decimal | None = None,
    active_validators_count: int | None = None,
    leaderboard_limit: int = 10,
) -> dict[str, Any]:
    """Aggregate normalized validator rows; never reads raw API payloads."""
    empty = {
        "metrics": {
            "total_active_stake": None,
            "staking_ratio": None,
            "active_validators_count": None,
            "top_1_stake_share": None,
            "top_3_stake_share": None,
            "top_5_stake_share": None,
            "top_10_stake_share": None,
            "top_20_stake_share": None,
            "hhi_concentration_index": None,
            "total_delegators": None,
            "average_commission": None,
            "block_production_rate": None,
        },
        "validators": {"updated_at": None, "items": []},
    }
    normalized_path = Path(normalized_path)
    if not normalized_path.exists():
        return empty

    document = _read_json(normalized_path)
    rows = document.get("items") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{normalized_path.name} must contain normalized validator items")
    active = [row for row in rows if isinstance(row, dict) and row.get("is_active") is True]
    metrics = dict(empty["metrics"])
    metrics["active_validators_count"] = (
        active_validators_count if active_validators_count is not None else len(active)
    )

    stakes = [_number(row.get("stake_near")) for row in active]
    stakes_complete = all(value is not None for value in stakes)
    total_stake = sum(stakes, Decimal(0)) if stakes_complete else None
    stake_denominator = network_total_stake if network_total_stake is not None else total_stake
    metrics["total_active_stake"] = stake_denominator
    metrics["staking_ratio"] = _ratio_pct(stake_denominator, circulating_supply)
    registry_complete = active_validators_count is None or len(active) >= active_validators_count

    ranked = sorted(
        ((row, stake) for row, stake in zip(active, stakes) if stake is not None),
        key=lambda entry: (-entry[1], str(entry[0].get("account_id", ""))),
    )
    if stake_denominator is not None and stake_denominator > 0:
        shares = [stake / stake_denominator * 100 for _, stake in ranked]
        for count in (1, 3, 5, 10, 20):
            metrics[f"top_{count}_stake_share"] = sum(shares[:count], Decimal(0))
        if registry_complete:
            metrics["hhi_concentration_index"] = sum(
                (share * share for share in shares), Decimal(0)
            )

    delegators = [row.get("delegators_count") for row in active]
    if registry_complete and all(value is not None for value in delegators):
        metrics["total_delegators"] = sum(int(value) for value in delegators)

    commissions = [_number(row.get("commission_pct")) for row in active]
    if registry_complete and stakes_complete and all(value is not None for value in commissions) and total_stake and total_stake > 0:
        metrics["average_commission"] = sum(
            (stake * commission for stake, commission in zip(stakes, commissions)), Decimal(0)
        ) / total_stake

    produced = [_number(row.get("blocks_produced")) for row in active]
    expected = [_number(row.get("blocks_expected")) for row in active]
    if registry_complete and all(value is not None for value in produced + expected):
        expected_total = sum(expected, Decimal(0))
        metrics["block_production_rate"] = _ratio_pct(sum(produced, Decimal(0)), expected_total)

    leaderboard = []
    for index, (row, stake) in enumerate(ranked[:leaderboard_limit], start=1):
        produced_value = _number(row.get("blocks_produced"))
        expected_value = _number(row.get("blocks_expected"))
        production_rate = _ratio_pct(produced_value, expected_value)
        leaderboard.append({
            "rank": index,
            "account_id": row["account_id"],
            "stake_near": stake,
            "stake_share": _ratio_pct(stake, stake_denominator),
            "commission_pct": _number(row.get("commission_pct")),
            "delegators_count": row.get("delegators_count"),
            "block_production_rate": production_rate,
        })

    return {
        "metrics": metrics,
        "validators": {"updated_at": document.get("updated_at"), "items": leaderboard},
    }
