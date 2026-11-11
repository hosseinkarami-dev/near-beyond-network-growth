# Network analytics

Run `python scripts/build_analytics.py` to refresh these outputs. The builder reads existing normalized Network and Binance price data only. It makes no external requests and does not alter Raw or Normalized files.

## Daily dataset: `daily_metrics.json`

The file contains a small UTC envelope (`schema_version`, `network`, `time`) and `observations`. Each observation has exactly these ten fields:

| Field | Unit | Input / calculation | JSON type |
| --- | --- | --- | --- |
| `date` | UTC date | Exact date in every selected source | string (`YYYY-MM-DD`) |
| `transactions` | transactions | `network/daily_transactions.json` | integer |
| `transaction_fees_near` | NEAR | `network/daily_transaction_fees.json` | number |
| `transaction_fees_usd` | USD | `transaction_fees_near * near_usd_price` | number |
| `near_usd_price` | USD per NEAR | `markets/binance/nearusdt_1d_close_price.json` daily close | number |
| `active_accounts` | accounts | `network/active_accounts.json` | integer |
| `active_contracts` | contracts | `network/active_contracts.json` | integer |
| `new_contracts` | contracts | `network/new_contracts.json` | integer |
| `tvl_usd` | USD | `network/tvl_usd.json` | number |
| `tvl_near` | NEAR | `tvl_usd / same-day near_usd_price` | number |

The builder uses an inner join of the seven source series on exact UTC `date`. Only dates present in every source with valid, non-null required values survive. `tvl_near` is derived after the join from that date's USD TVL and NEARUSDT close. A zero or invalid price also excludes its date. No artificial dates, price filling, interpolation, or null-to-zero conversion is used. Explicit count zeroes remain zero.

## Currency conversion

`near_to_usd(amount_near, near_usd_price)` and `usd_to_near(amount_usd, near_usd_price)` return `Decimal` values, or `None` if an input is missing or invalid or the price is not positive. Fee conversion and TVL denomination use the closing price on the same date; unmatched dates are excluded by the join and never use a neighboring price. TVL remains a point-in-time value in either denomination and is never summed across dates.

Binance quotes NEAR in USDT. This layer treats USDT as the USD pricing proxy. The output `near_usd_price` retains the source close to eight decimals so the USD fee calculation can be audited. USD fee amounts are rounded for output after Decimal multiplication.

## Snapshot: `snapshot.json`

The compact snapshot has exactly three top-level sections:

- `network`: `name` and source `updated_at`.
- `network_stats`: `avg_block_time`, `tps`, `nodes_online`, and `gas_price` from the existing normalized summary. Numeric values are written as JSON numbers.
- `key_metrics`: latest values and calendar-date changes for transactions, USD fees, active accounts/contracts, USD and NEAR TVL, and NEAR price. `new_contracts` instead includes its 24h absolute change and 7d/30d sums. Both TVL metrics use same-date USD/NEAR price conversion.

All overview calculations read the serialized final daily dataset. Percentage comparisons use the exact calendar date 1, 7, or 30 days earlier. Averages and sums require every date in their full calendar window. If the target date or any window date is missing, the result is null; the builder never substitutes another date.

## Precision

Calculations use `Decimal` and do not use binary floating point. Rounding occurs only during JSON serialization, with round-half-even and insignificant trailing zeroes removed. Decimal values are emitted as JSON numbers, not strings.

| Value | Output precision |
| --- | ---: |
| NEAR amounts | 8 decimal places |
| USD amounts | 2 decimal places |
| Ratios | 6 decimal places |
| Percentages | 4 decimal places |
| Rolling averages | 2 decimal places |
| Count metrics and rolling sums | Integers |
| Source NEAR/USDT close (`near_usd_price`) | 8 decimal places, retained for auditability |

## Inputs and current overlap

Daily inputs are NearBlocks transactions, transaction fees, active accounts, active contracts, and new contracts; DefiLlama TVL; and Binance NEARUSDT daily close. All are interpreted as UTC dates. Dates and timestamps are validated, and duplicate dates in a source fail the build.

At the inspected input revision, the union contains 2,290 distinct dates. The date inner join leaves 190 dates, from 2021-08-20 through 2022-02-25. The sources contain 2,289 rows each for the five NearBlocks metrics, 1,906 TVL rows, and 500 price rows. `new_contracts` contains 25 null observations in its full history; none falls in the shared date range. The final joined rows have no null or invalid values. USDT is a proxy, not a guarantee of exact USD parity.
