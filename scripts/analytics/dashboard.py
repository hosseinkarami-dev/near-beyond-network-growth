"""Build top-level metadata for the analytics dashboard."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import ANALYTICS_DATA_DIR
from validation import validate_json


ANALYTICS_ROOT = ANALYTICS_DATA_DIR
SECTIONS = (
    {
        "id": "network",
        "title": "Network",
        "description": "NEAR network activity and key metrics.",
        "directory": "network",
    },
    {
        "id": "tokenomics",
        "title": "Tokenomics",
        "description": "NEAR price and supply metrics.",
        "directory": "tokenomics",
    },
    {
        "id": "near_intents",
        "title": "NEAR Intents",
        "description": "NEAR Intents volume, TVL, and holders revenue.",
        "directory": "near_intents",
    },
    {
        "id": "protocols_fees",
        "title": "Protocol Fees",
        "description": "Fees generated across tracked NEAR protocols.",
        "directory": "protocols/fees",
    },
    {
        "id": "protocols_revenue",
        "title": "Protocol Revenue",
        "description": "Revenue generated across tracked NEAR protocols.",
        "directory": "protocols/revenue",
    },
    {
        "id": "protocols_dex_volume",
        "title": "Protocol DEX Volume",
        "description": "DEX volume across tracked NEAR protocols.",
        "directory": "protocols/dex_volume",
    },
)

METHODOLOGIES = {
    "network": {
        "transaction_fees": {
            "title": "Transaction fees",
            "description": "USD fees are calculated by multiplying that UTC day's NEAR fee total by its NEARUSDT closing price. USDT is used as the USD price proxy.",
        },
        "tvl": {
            "title": "Network TVL currency conversion",
            "description": "TVL in NEAR is calculated by dividing the same UTC date's USD TVL by that date's NEARUSDT close. USDT is used as the USD price proxy; TVL values are snapshots and are never summed across dates.",
        },
        "stablecoin_supply": {
            "title": "Stablecoin supply",
            "description": "USD supply is the sum of DefiLlama totalCirculatingUSD values across the distinct peg categories returned for NEAR. Minted, unreleased, and bridged-to values are excluded. Daily values use the UTC date from the source timestamp; weekly, monthly, quarterly, and yearly charts show period-end snapshots. The dashboard renders at most the latest 365 observations per series. The 30-day and 90-day comparisons use the closest valid observation to each reference date without interpolation; percentage change is blank when the reference supply is zero or unavailable.",
        },
    },
    "tokenomics": {
        "near_price": {
            "title": "NEAR price moving averages",
            "description": "The 7-day and 30-day lines are simple arithmetic means of daily NEARUSDT closes, rounded to 8 decimal places. An average is left empty until its full window is available.",
        },
        "fdv": {
            "title": "NEAR fully diluted valuation",
            "description": "FDV is calculated as NEAR's daily closing price multiplied by total supply. Price and supply are matched on the latest UTC calendar date present in both histories; the Binance NEARUSDT close is used as the USD price proxy, and the BigQuery supply value is approximate float64. The result is rounded to cents.",
        },
        "supply": {
            "title": "Supply history",
            "description": "Supply is a point-in-time value. Weekly, monthly, quarterly, and yearly views use the last available observation in each period; supply is never summed across dates. Missing circulating-supply values remain empty.",
        },
        "staking": {
            "title": "NEAR staking ratio",
            "description": "Staking ratio is the sum of active validator stake divided by latest circulating supply, multiplied by 100. Validator stake comes from the current NearBlocks validator list; circulating supply comes from the normalized daily supply dataset and has approximate float64 precision.",
        },
        "buybacks": {
            "title": "NEAR Intents buybacks",
            "description": "The BigQuery query identifies native NEAR transfers and wNEAR ft_transfer events into buybacks.multisignature.near and groups returned amounts by transfer_type. Analytics sums flows into daily and calendar-period bars. The available series shows recurring NEAR Intents inflows and more episodic 1Click & other revenue flows, including 502,793 NEAR on 2026-09-09. These inflows do not prove completed purchases. The current wallet balance is a separate finalized FastNEAR RPC liquid balance and excludes locked stake.",
        },
        "historical_active_stake": {
            "title": "Historical active validator stake",
            "description": "For each UTC date from 2026-09-01 onward, the sampled block height comes from daily_supply.json. FastNEAR resolves that block to its epoch and returns the epoch's current_validators; their stake values are summed with arbitrary-precision integers and only the exact YoctoNEAR total is checkpointed in raw. Analytics converts it to NEAR and joins it to that date's total supply for the chart. Daily values are shown as-is; weekly, monthly, quarterly, and yearly views select the last available daily snapshot in each calendar period and do not accumulate values. Dates already present with the same block height are skipped on later fetches.",
        },
        "validators": {
            "title": "NEAR validators",
            "description": "Validator concentration uses active validator stake: top-N shares are the summed stake of the N largest validators divided by total active stake. HHI is the sum of squared percentage stake shares (0–10,000). Delegator counts are summed per active validator and may double-count accounts that delegate to multiple validators. Average commission is stake-weighted. Block production rate is total produced blocks divided by expected blocks where both are available.",
        },
        "supply_dynamics": {
            "title": "Supply dynamics and gross issuance",
            "description": "Net issuance is derived from consecutive daily total-supply snapshots. Net burn equals the execution outcome tokens_burnt amount minus separately credited daily contract rewards. tokens_burnt can include refund penalties, deleted gas-key balances, and global-contract deployment charges, and is not reconstructed from gas_burnt × gas_price. Estimated gross issuance equals net issuance plus net burn; it is null when either daily input is unavailable. Issuance is approximate because total supply uses float64 and unmodeled adjustments may affect reconciliation.",
        },
        "net_burn": {
            "title": "Net fee burn",
            "description": "Daily net fee burn equals NEAR execution outcome tokens_burnt minus separately credited daily contract rewards. tokens_burnt can include refund penalties, deleted gas-key balances, and global-contract deployment charges; it is not reconstructed from gas_burnt × gas_price. USD values convert each day's NEAR amount using that UTC day's NEARUSDT close; period values sum daily observations.",
        },
        "net_inflation": {
            "title": "Trailing 30-day annualized net inflation",
            "description": "For each date, compare total supply with the supply exactly 30 calendar days earlier, then annualize the compounded growth: ((ending supply / starting supply)^(365/30) - 1) × 100. This measures net total supply growth and therefore includes the effect of burned tokens.",
        },
        "burn_coverage": {
            "title": "Burn Coverage",
            "description": "Daily Burn Coverage (%) = (Net Fee Burn (NEAR) / Estimated Gross Issuance (NEAR)) x 100. Net Fee Burn is net burn after subtracting contract rewards from execution outcome tokens_burnt. It is undefined when either value is unavailable or estimated gross issuance is zero or negative. Longer periods retain the existing flow aggregation: sum daily net burn and gross issuance within the calendar period, then calculate their ratio.",
        },
    },
    "near_intents": {
        "volume": {
            "title": "NEAR Intents volume",
            "description": "The value of spot swaps processed through NEAR Intents, counted once per swap and before subtracting fees. Deposits, withdrawals, and transfers are not swap volume. Daily USD observations come from normalized DefiLlama NEAR Intents volume data (near_intents_dex_volume/daily_volume.json).",
        },
        "near_intents_kpis": {
            "title": "NEAR Intents KPI windows",
            "description": "Flow totals use UTC calendar dates. The 24h value is the latest daily observation; 7d and 30d values sum the latest seven or thirty calendar dates. Comparison percentages use the immediately preceding equal-length calendar window. A value or comparison is left empty unless every required date is present, and percentage change is empty when its comparison total is zero. TVL is a point-in-time value compared with the exact date 7 or 30 days earlier.",
        },
        "tvl": {
            "title": "NEAR Intents TVL",
            "description": "The USD value of tokens locked in NEAR Intents Verifier contracts across supported chains comes from normalized DefiLlama TVL data (near_intents/daily_intents_tvl.json). NEAR-denominated TVL divides that same date's USD value by the Binance NEARUSDT closing price. TVL is a snapshot; period views use the last available value rather than adding values across dates.",
        },
        "tvl_by_chain": {
            "title": "NEAR Intents TVL by chain",
            "description": "Current TVL snapshots are shown by supported chain using normalized DefiLlama current-chain TVL data. Values are point-in-time balances and are not summed across dates; the NEAR conversion uses the same snapshot date's NEARUSDT close.",
        },
        "current_tvl_by_token": {
            "title": "Current NEAR Intents TVL by token",
            "description": "The latest available period-end token balances in NEAR Intents Verifier contracts, sourced from normalized DefiLlama historical TVL-by-token snapshots. USD values are converted using the same snapshot date's NEARUSDT close.",
        },
        "tvl_by_token": {
            "title": "NEAR Intents TVL by token over time",
            "description": "Each point is a period-end TVL snapshot by token. USD values come from normalized DefiLlama historical TVL-by-token data; NEAR values use the NEARUSDT close on the snapshot date. Values are never summed across dates, and tokens outside the eight largest current balances are grouped as Other tokens in the chart.",
        },
        "revenue": {
            "title": "NEAR Intents revenue",
            "description": "Revenue retained after amounts allocated to solvers and other suppliers are excluded. NEAR and wNEAR swept into revenue wallets are split by destination into front-end affiliate revenue and Other; transfers between those wallets are excluded. Daily USD values are selected for NEAR Intents from normalized DefiLlama protocol revenue data (near_revenue/daily_protocol_revenue_breakdown.json).",
        },
        "gross_fees": {
            "title": "NEAR Intents gross fees",
            "description": "Gross fees are the total fees paid by users before subtracting amounts allocated to solvers and other suppliers. Daily USD values are selected specifically for NEAR Intents from the normalized DefiLlama protocol fees breakdown (near_fees/daily_protocol_fees_breakdown.json), not from all protocols or from volume. The all-time cumulative total sums the available daily NEAR Intents observations. Weekly, monthly, quarterly, and yearly values sum available daily values without filling missing dates. Trailing KPI windows require every UTC date in the window; otherwise the KPI is empty. Fees and revenue are separate reported series and are not derived from one another, so they may not reconcile day-by-day in the source data.",
        },
        "revenue_capture_rate_30d": {
            "title": "30-day revenue capture rate",
            "description": "For each date, the rate is (sum of the 30 daily NEAR Intents Revenue values ending on that UTC date ÷ sum of Gross Fees over those same 30 dates) × 100. It uses Revenue and Gross Fees only; Holders Revenue remains a separate chart series and is excluded. The ratio is not capped. Revenue can be recognized in periodic wallet sweeps while related fees accrued on earlier dates, so a sweep can temporarily lift the rolling revenue numerator above the rolling fees denominator and produce a rate above 100%. This is a timing effect in revenue recognition, not a clamp or a daily-ratio calculation.",
        },
        "holders_revenue": {
            "title": "Holders revenue",
            "description": "The portion of revenue attributed to token holders. Since 2026-02-23, NEAR Intents captured revenue has funded open-market NEAR buybacks; the purchased NEAR is not burned. Daily USD values are selected for NEAR Intents from normalized DefiLlama holders-revenue data (near_holders_revenue/daily_holders_revenue_breakdown.json).",
        },
    },
    "protocols": {
        "fees": {
            "title": "Protocol fees",
            "description": "Gross fees paid by users before splitting amounts retained by the protocol from amounts paid to liquidity providers, solvers, or other suppliers. NEAR values convert each daily USD amount using that UTC date's NEARUSDT closing price, then sum the converted daily values for longer periods. Missing prices remain unavailable; USDT is the USD price proxy.",
        },
        "revenue": {
            "title": "Protocol revenue",
            "description": "Fees retained after supplier-side shares are excluded. Revenue can go to the treasury, team, or token holders. NEAR values convert each daily USD amount using that UTC date's NEARUSDT closing price, then sum the converted daily values for longer periods. Missing prices remain unavailable; USDT is the USD price proxy.",
        },
        "dex_volume": {
            "title": "DEX volume",
            "description": "The value of spot swaps. Each swap is counted once and gross of fees; liquidity actions, deposits, withdrawals, transfers, and NFT trades are excluded. NEAR values convert each daily USD amount using that UTC date's NEARUSDT closing price, then sum the converted daily values for longer periods. Missing prices remain unavailable; USDT is the USD price proxy.",
        },
        "breakdown": {
            "title": "Protocol breakdown",
            "description": "Each line shows a protocol's amount over time. The six largest protocols in the selected period are shown individually; the rest are grouped as Other protocols. The distribution pie defaults to the sum of all available daily protocol amounts and can also show the latest daily, weekly, monthly, quarterly, or yearly total.",
        },
    },
}


def _section_metadata(section: dict[str, str]) -> dict[str, Any] | None:
    directory = ANALYTICS_ROOT / section["directory"]
    if not directory.is_dir():
        return None
    files = sorted(
        path.relative_to(ANALYTICS_ROOT).as_posix()
        for path in directory.rglob("*.json")
        if path.is_file()
    )
    if not files:
        return None
    return {
        "id": section["id"],
        "title": section["title"],
        "description": section["description"],
        "files": files,
    }


def _latest_data_update(sections: list[dict[str, Any]]) -> str | None:
    timestamps = []
    for section in sections:
        for relative_path in section["files"]:
            if not relative_path.endswith("snapshot.json"):
                continue
            with (ANALYTICS_ROOT / relative_path).open(encoding="utf-8") as source:
                document = json.load(source)
            updated_at = document.get("updated_at") if isinstance(document, dict) else None
            if isinstance(updated_at, str):
                try:
                    parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                timestamps.append(parsed.astimezone(timezone.utc))
    if not timestamps:
        return None
    return max(timestamps).isoformat().replace("+00:00", "Z")


def build_dashboard_metadata(output_path: Path = ANALYTICS_ROOT / "dashboard.json") -> Path:
    sections = [metadata for section in SECTIONS
                if (metadata := _section_metadata(section)) is not None]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    document = {
        "schema_version": "1.0.0",
        "title": "NEAR Blockchain Analytics Dashboard",
        "description": "An overview of NEAR network activity, tokenomics, NEAR Intents, and protocol metrics.",
        "network": "NEAR mainnet",
        "timezone": "UTC",
        "updated_at": now,
        "latest_data_update": _latest_data_update(sections),
        "methodologies": METHODOLOGIES,
        "sections": sections,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(validate_json(document), encoding="utf-8")
    from console_ui import console
    console.print("[green]OK[/green] Dashboard metadata ready")
    return output_path
