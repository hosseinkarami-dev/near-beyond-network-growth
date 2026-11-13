"""Daily burn analytics, independent of the Tokenomics supply series."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from analytics.periods import CHART_PERIODS, period_bounds


PROTOCOL_V87_ZERO_REWARDS_FROM = date(2026, 11, 5)


def _ratio_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * Decimal(100)


def _periods(rows: dict[date, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    recent = list(rows.items())[-365:]
    for period in CHART_PERIODS:
        groups: dict[str, list[tuple[date, dict[str, Any]]]] = {}
        for day, row in recent:
            key = day.isoformat() if period == "daily" else period_bounds(day, period)[0]
            groups.setdefault(key, []).append((day, row))
        observations = []
        for key, group in groups.items():
            sums = {}
            for field in (
                "gross_burn_near", "contract_rewards_near", "net_burn_near",
                "contract_rewards_usd", "gross_burn_usd", "net_burn_usd",
            ):
                values = [row.get(field) for _, row in group]
                sums[field] = sum(values, Decimal(0)) if all(v is not None for v in values) else None
            observations.append({
                "period": key,
                "date": group[-1][0].isoformat(),
                **sums,
            })
        output[period] = observations
    return output


def build_burn_analytics(
    supplies: dict[date, dict[str, Decimal | None]],
    gross_burn: dict[date, Decimal],
    contract_rewards: dict[date, Decimal],
    reward_audit_range: tuple[date, date] | None,
    prices: dict[date, Decimal],
    *,
    network: str | None,
    updated_at: str | None,
) -> tuple[dict[date, dict[str, Any]], dict[str, Any], dict[str, int]]:
    """Build daily gross burn, rewards, and net burn; zero only when justified."""

    rows: dict[date, dict[str, Any]] = {}
    zero_counts = {"audit_no_events": 0, "protocol_v87": 0}
    if not supplies:
        return rows, {}, zero_counts

    first, last = next(iter(supplies)), next(reversed(supplies))
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        rewards = contract_rewards.get(day)
        reward_status = "observed_audit" if rewards is not None else "unavailable"
        if day >= PROTOCOL_V87_ZERO_REWARDS_FROM:
            rewards = Decimal(0)
            reward_status = "protocol_v87_zero"
            zero_counts["protocol_v87"] += 1
        elif reward_audit_range and reward_audit_range[0] <= day <= reward_audit_range[1] and rewards is None:
            rewards = Decimal(0)
            reward_status = "complete_audit_no_events"
            zero_counts["audit_no_events"] += 1

        gross = gross_burn.get(day)
        net = gross - rewards if gross is not None and rewards is not None else None
        price = prices.get(day)
        gross_usd = gross * price if gross is not None and price is not None else None
        rewards_usd = rewards * price if rewards is not None and price is not None else None
        net_usd = net * price if net is not None and price is not None else None
        rows[day] = {
            "gross_burn_near": gross,
            "contract_rewards_near": rewards,
            "contract_rewards_status": reward_status,
            "net_burn_near": net,
            "gross_burn_usd": gross_usd,
            "contract_rewards_usd": rewards_usd,
            "net_burn_usd": net_usd,
        }

    document = {
        "schema_version": "1.0.0",
        "network": network,
        "updated_at": updated_at,
        "sources": {
            "gross_burn": "BigQuery NEAR execution_outcomes tokens_burnt",
            "contract_rewards": "BigQuery account_changes contract_reward_event_audit",
        },
        "metric": {
            "unit": "NEAR",
            "net_burn_formula": "gross_tokens_burnt_near - contract_rewards_near",
            "reward_zero_policy": {
                "within_audit_range": "zero when the complete audit has no reward events for the UTC date",
                "after_protocol_v87": PROTOCOL_V87_ZERO_REWARDS_FROM.isoformat(),
            },
        },
        "items": [
            {"date": day.isoformat(), **values}
            for day, values in rows.items()
        ],
        "periods": _periods(rows),
        "data_quality": {
            "protocol_v87_zero_days": zero_counts["protocol_v87"],
            "complete_audit_zero_event_days": zero_counts["audit_no_events"],
        },
    }
    return rows, document, zero_counts

