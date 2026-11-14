# Protocol analytics

`scripts/analytics/protocols.py` builds app-level fee, revenue, and DEX-volume datasets from normalized DefiLlama data. It writes to `data/analytics/protocols/`. These measures describe tracked NEAR applications; they are not the same as NEAR network transaction fees or the NEAR Intents volume series.

## Categories

| Directory | Metric | Source scope |
| --- | --- | --- |
| `fees/` | `fees_usd` | Gross user fees by tracked protocol. |
| `revenue/` | `revenue_usd` | Reported revenue by tracked protocol after supplier-side allocations, as defined by the provider. |
| `dex_volume/` | `volume_usd` | Spot swap volume by tracked protocol. |

Daily amount files are read from the normalized category inputs. Breakdown files retain provider protocol names and amounts by date. The builder also converts each daily protocol amount into NEAR using the same UTC date's Binance NEARUSDT close. A missing or invalid price leaves that NEAR value unavailable; it does not borrow a price from a neighboring date. USDT is the project's USD proxy.

## Output files

Each category directory contains:

- `snapshot.json`: provider summary and update information
- `daily_metrics.json`: chain-level USD amount and its NEAR equivalent by date
- `daily_breakdown.json`: per-protocol USD and NEAR values, plus prepared chart series
- `{weekly,monthly,quarterly,yearly}_metrics.json`: sums of daily values within each calendar period
- `{weekly,monthly,quarterly,yearly}_breakdown.json`: per-protocol sums within each calendar period and chart-ready series
- `protocol_breakdown.json` and/or a ranking file: compact provider ranking where one is available

The breakdown charts show the six largest protocols for the selected observations and group the rest as `Other protocols`. Distribution values are the sums over the selected dates. The latest-period distribution is based on the last available daily breakdown. Fees and DEX volume have provider rankings; revenue is not given a ranking output by this builder.

The holders-revenue provider series is handled in the NEAR Intents analytics pipeline, which selects the `NEAR Intents` breakdown for the dashboard. The Protocols builder does not create a second holder-revenue category. It also clears stale holder-revenue output left by older layouts.

## Aggregation and interpretation

Weekly, monthly, quarterly, and yearly observations are calendar-period sums, not cumulative totals. If a protocol has no value for a date, it is not fabricated as a zero row. For a period breakdown, the output combines the protocol amounts returned for the dates present in that period. Check `days_observed` and source coverage before comparing periods with different numbers of observations.

Fees, revenue, and volume answer different questions. Gross fees include amounts later allocated to suppliers; reported revenue excludes some of those allocations; DEX volume is the notional value of swaps. Do not add these series together or treat app revenue as revenue paid to NEAR token holders. DefiLlama classifications can change and may not align day by day across endpoints.

## Failure behavior


The coordinator builds protocol categories independently inside the builder. If a category's normalized inputs are missing or invalid, it writes an empty snapshot for that category and continues with the others. A missing source is not evidence of zero fees, revenue, or volume.



