# Analytics datasets

Analytics is the hand-off between normalized source data and the dashboard. Builders in `scripts/analytics/` validate the inputs they need, join sources, apply metric definitions, and write JSON under `data/analytics/`. The dashboard reads those files and formats them for display; it should not recreate formulas or aggregate daily observations.

## Build and failure behavior

From the repository root, run:

```shell
py scripts/build_analytics.py
```

Use `python3` instead of `py` on macOS and Linux. This rebuilds analytics from `data/normalized/` and syncs the results to `dashboard/public/data/analytics/`. It does not fetch provider data. Use `py scripts/main.py` to run collection, normalization, analytics, and the final dashboard sync in order.

Network, Tokenomics, NEAR Intents, and Protocols are built as independent sections. If a section cannot use its inputs, the builder writes that section's empty fallback and continues with the others. A missing observation is not silently changed to zero. Zero is used only where the metric's source or a documented completeness rule establishes it.

All dates are UTC calendar dates. Output names and schemas below describe the current builders; source history and coverage can change as new data arrive.

## Domain guides

- [Network](network.md): daily activity, fees, TVL, USD conversion, stablecoin supply, and exact-date joins.
- [Tokenomics](tokenomics.md): supply, issuance and burn estimates, staking, validators, historical stake, and buyback-wallet flows.
- [NEAR Intents](near-intents.md): volume, TVL, fees, revenue, holder revenue, capture rate, and token/chain views.
- [Protocols](protocols.md): app-level fees, revenue, DEX volume, protocol breakdowns, and rankings.

## Output map

| Directory | Main files | What they contain |
| --- | --- | --- |
| `network/` | `daily_metrics.json`, `snapshot.json`, `{weekly,monthly,quarterly,yearly}_metrics.json` | Joined usage, fees, TVL, price, and overview metrics. Separate stablecoin files hold its daily and period-end series. |
| `tokenomics/` | `snapshot.json`, `daily_tokenomics.json`, `daily_supply.json`, `daily_burn.json`, `daily_issuance.json`, `daily_active_validator_stake.json` | Current metrics and supply, burn, issuance, validator stake histories. Calendar-period files are separate. |
| `near_intents/` | `snapshot.json`, `daily_metrics.json`, `{weekly,monthly,quarterly,yearly}_metrics.json` | Volume and reported fee/revenue flows alongside TVL snapshots and the rolling capture-rate series. |
| `near_intents/` | `{daily,weekly,monthly,quarterly,yearly}_tvl_by_token*.json`, `current_tvl_by_token.json`, `tvl_by_chain.json` | Historical token TVL snapshots, compact chart series, latest token breakdown, and current chain breakdown. |
| `protocols/fees/`, `protocols/revenue/`, `protocols/dex_volume/` | `snapshot.json`, `daily_metrics.json`, `daily_breakdown.json`, `{weekly,monthly,quarterly,yearly}_{metrics,breakdown}.json` | Each category's chain-level flow and protocol-level breakdown in USD and NEAR. Ranking files are emitted where the source provides them. |
| repository root | `dashboard.json` | Dashboard section/file metadata, update timestamps, and methodology text used by the UI. |

Weekly, monthly, quarterly, and yearly files are calendar buckets, not rolling windows. Flow metrics are summed within a bucket; supply, TVL, token balances, and stake use the last available snapshot. Exceptions and exact rules are documented in each domain guide.

## Reading coverage

Do not assume every section ends on the same date. Each provider updates on its own schedule, and some builders require exact date matches across sources. Use the dates and coverage fields in the generated JSON for the specific metric being discussed. A blank value can mean that an input or a complete comparison window is unavailable; it does not automatically mean zero activity.

