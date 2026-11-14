# NEAR Intents analytics

The builder is `scripts/analytics/near_intents.py`. It reads normalized DefiLlama series and NEAR-USDT closes, then writes dashboard-ready data to `data/analytics/near_intents/`. It keeps flow totals separate from point-in-time TVL and token balances.

## Volume and reported economics

`daily_metrics.json` has one item for each date found in at least one input series. Its fields include:

- `volume_usd`: NEAR Intents swap volume.
- `gross_fees_usd`: fees reported for NEAR Intents before the revenue split.
- `revenue_usd`: revenue attributed to NEAR Intents after supplier allocations.
- `holders_revenue_usd`: separately reported holder allocation.
- `tvl_usd` and `tvl_near`: period-end snapshots, with NEAR conversion using that date's Binance NEAR-USDT close.
- `revenue_capture_rate_30d_pct`: trailing 30-date ratio, when the full window is available.

Volume, fees, and revenue are separate DefiLlama series. Revenue is selected by the `NEAR Intents` name from the NEAR ecosystem revenue breakdown; it is not inferred from volume or fees. Holder revenue remains separate and is not added to revenue again. These classifications are provider-reported and may reflect periodic revenue sweeps, so same-day amounts need not line up.

The capture rate is:

```text
(sum of the 30 daily NEAR Intents revenue values
 ÷ sum of gross fees over the same 30 UTC dates) × 100
```

It is the ratio of sums, not the average of daily ratios. It is not capped at 100%. Missing dates or values in either 30-day window, or a zero fee denominator, leave the rate null. A rate over 100% can result when reported revenue is swept on a different schedule from fee recognition; it is not holder yield.

The 24-hour, 7-day, and 30-day flow KPIs require every date in the current window and in the comparison window. Comparison is against the immediately preceding window of equal length. All-time totals sum available dated observations through the latest usable observation; gaps are not imputed. TVL change compares the exact calendar date seven or thirty days earlier.

## TVL and composition

`tvl_usd` is a point-in-time estimate of assets in the NEAR Intents Verifier contracts across supported chains. `tvl_near` divides the same-date USD value by that date's NEARUSDT close. Period files take the last available snapshot in each calendar period; they do not sum TVL observations.

The token breakdown is sourced from DefiLlama's historical token TVL series. `current_tvl_by_token.json` contains the latest snapshot and pie-chart groupings. The `*_tvl_by_token.json` files retain period-end snapshots; corresponding `*_tvl_by_token_chart.json` files prepare the leading token series plus an `Other` remainder. The per-token NEAR amounts use the same snapshot date's NEARUSDT price. `tvl_by_chain.json` is the current chain split, not a historical flow series.

## Files

- `snapshot.json`: KPI values, source update information, TVL summaries, and provider coverage note.
- `daily_metrics.json`: daily flows, snapshots, and the rolling capture rate.
- `{weekly,monthly,quarterly,yearly}_metrics.json`: calendar-period flow sums with period-end TVL fields and the capture rate at the period's final available date.
- `current_tvl_by_token.json`, `*_tvl_by_token.json`, and `*_tvl_by_token_chart.json`: current and historical token composition.
- `tvl_by_chain.json`: latest chain breakdown.

Missing input files or invalid data make the NEAR Intents section unavailable for that build; the analytics coordinator writes an empty fallback for this section and continues building other sections. It does not fill unknown values with zero.

## Sources and limits

Inputs are normalized DefiLlama NEAR Intents volume and TVL, NEAR ecosystem fees/revenue/holders-revenue breakdowns, token TVL and chain TVL, plus Binance daily NEARUSDT closes. USDT is used as the USD proxy. Provider definitions, timestamps, and update schedules can differ. NEAR Intents TVL overlaps broader NEAR TVL, so the two should not be added together. Reported revenue and holder revenue are not independently audited cash distributions, and a buyback-wallet transfer does not prove a market purchase.

