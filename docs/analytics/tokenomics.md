# Tokenomics analytics

The Tokenomics analytics builder consumes normalized datasets under `data/normalized`. It does not read raw files.

Pipeline availability: missing or invalid inputs for one analytics section produce an empty section snapshot, and the other sections still build. Validator records are optional; when that source is unavailable, validator metrics and the leaderboard remain empty without blocking Tokenomics or other sections.

## Supply observations and net inflation

`daily_supply.json` is the existing BigQuery period-end supply snapshot. Its values have `approximate_float64` source precision. Raw source timestamps inspected for this dataset occur close to 23:59 UTC on each `utc_date`; each date is therefore treated as that UTC day's period-end observation. The daily change assigned to date D is `total_supply(D) - total_supply(D-1)`, which approximates the flow over UTC date D. A missing prior calendar date leaves the daily change null.

Non-circulating supply is `total_supply - circulating_supply`. Circulating supply ratio is `(circulating_supply / total_supply) * 100`. These describe a supply snapshot and liquid availability; changes in circulating supply are not total-supply inflation.

## Staking and validators

`nearblocks/validators/summary.json` is a current snapshot from NearBlocks `/v3/validators/info`. `total_staked` is normalized to NEAR (converting yoctoNEAR values when supplied); validator counts are integers. `nearblocks/validators/validators.json` contains normalized validator records from the paginated `/v3/validators` endpoint. Analytics computes total active stake, active stake as a share of latest circulating supply, concentration shares for the largest 1/3/5/10/20 validators, and HHI (sum of squared percentage stake shares, on the 0–10,000 scale). The circulating-supply denominator comes from BigQuery daily supply and has `approximate_float64` precision. Delegator counts are summed per active validator and may double-count accounts delegated to multiple validators. Average commission is weighted by active stake. Block production rate is produced blocks divided by expected blocks when both values are present.

Validator analytics are written into `snapshot.json`: aggregate values are under `metrics`, and the 20 largest active validators are under `validators.items`. The dashboard formats and displays these values without calculating aggregates.

## NEAR Intents buybacks

`buyback_transfers.json` is collected from BigQuery starting 2026-04-01. On each run, the collector resumes after the latest dated row in the raw file and requests through the last completed UTC day. The query returns matching transfers for the configured senders; it does not create a row for every date or write synthetic zero-flow days. Consequently, an empty date is not proof that a query confirmed zero activity, and older gaps are not revisited by an ordinary incremental run. The query recognizes native NEAR transfers and wNEAR `ft_transfer` events into `buybacks.multisignature.near`. It currently classifies `intents.near` as `intents_transfer`, `fefundsadmin.sputnik-dao.near` as `frontend_revenue`, and `1csfundsadmin.sputnik-dao.near` as `oneclick_and_other_revenue`. The downstream normalizer and analytics use the `transfer_type` values returned by the query rather than assuming a fixed chart-series list.

The recorded daily series shows recurring NEAR Intents inflows and more episodic 1Click & other revenue flows. The largest daily amount in that category is 502,793 NEAR on 2026-09-09. These are observed inflows attributed to their transfer sources; they do not by themselves prove that a purchase was executed or establish the later custody of purchased tokens.

Normalization validates the source rows and keeps the transfer type and amounts distinct. Analytics builds daily and calendar-period flow sums by transfer type; weekly, monthly, quarterly, and yearly observations are sums within their periods, not cumulative balances. `buyback_wallet_balance.json` is a current finalized RPC `view_account` snapshot. Its `balance_near` is the wallet's liquid `amount` and excludes `locked` stake. RPC failure leaves the previous snapshot available.

Analytics writes one file per frequency: `daily_buyback_transfers.json`, `weekly_buyback_transfers.json`, `monthly_buyback_transfers.json`, `quarterly_buyback_transfers.json`, and `yearly_buyback_transfers.json`. Period files sum daily flows within each calendar bucket and are not cumulative. `buyback_transfer_type_breakdown.json` contains the cumulative observed inflow by transfer type for the pie chart. The Tokenomics snapshot exposes the latest wallet balance. The dashboard only selects and displays prepared series, the breakdown, and the snapshot metric.

Historical active validator stake uses daily block heights from raw BigQuery `daily_supply.json`. When its checkpoint is empty, the collector starts three calendar months before the current UTC date. On later runs it continues after the last saved date, preserving successful results and retrying dates that failed. For each date it resolves the block epoch through FastNEAR's `block` RPC, then calls `validators` for that epoch. It sums `current_validators[].stake` as an arbitrary-precision integer in yoctoNEAR and saves only the date, block height, and total in a resumable raw JSON checkpoint. Normalization validates that compact record; Analytics converts the exact total to NEAR and joins it with that date's total supply. Weekly, monthly, quarterly, and yearly files select the last available daily snapshot in each calendar period; stake and supply are not summed or accumulated. No CSV is produced.

For N-day supply growth, the builder compares observations exactly N UTC calendar days apart:

- `net_supply_change_Nd_near = supply(end) - supply(end - N days)`
- `net_supply_growth_Nd_pct = (supply(end) / supply(end - N days) - 1) * 100`
- `net_inflation_Nd_annualized_pct = ((supply(end) / supply(end - N days)) ** (365 / N) - 1) * 100`

The 30-day annualized rate is the current net inflation KPI. Endpoints are not interpolated. Deflationary-day counts require every daily supply change in the complete N-day window.

## Gross burn and estimated issuance

`daily_gross_burn.json` is the normalized BigQuery `tokens_burnt` series from NEAR `execution_outcomes`, expressed in NEAR. The nearcore outcome records the charged/burnt amount before separately crediting the function-call contract reward; it can also include refund penalties, deleted gas-key balances, and global-contract deployment charges. It is not safely reconstructed as `gas_burnt × gas_price`, because gas pricing may create a deficit. Contract rewards come from the fixed-range `contract_reward_event_audit.json` BigQuery query over `account_changes`; only events classified as valid contribute to `contract_rewards_near`. The audit reports per-day event counts and event-count coverage. Analytics writes burn observations and calendar periods to `daily_burn.json`, and issuance observations and periods to `daily_issuance.json`. Supply/inflation history stays in `daily_tokenomics.json`.

Net burn subtracts audited contract rewards from gross burn. Estimated gross issuance is reconstructed as:

`net_burn_near = execution_outcomes.tokens_burnt_near - contract_rewards_near`

This subtraction is intentional: nearcore records the outcome's burnt/charged amount, then credits the contract reward separately. The reward credit therefore offsets part of that amount when measuring the net reduction in supply. It must not be subtracted from `gas_burnt × gas_price`; that is not the source metric and can differ due to gas-price deficits.

`estimated_gross_issuance_near = net_issuance_near + net_burn_near`

`net_issuance_near` is the daily total-supply change, `total_supply(D) - total_supply(D-1)`. Gross issuance is null for a day unless both net issuance and net burn are available. Period gross issuance is the sum of complete daily net-issuance and net-burn observations for that period. The dashboard reads these datasets and does no flow calculations.

The snapshot's `latest_net_burn_*` and `latest_burn_coverage_*` values each carry their own observation date and use the latest date where that metric is available. Burn Coverage is calculated in NEAR: `(net_burn_near / estimated_gross_issuance_near) * 100`. Longer-period values preserve the existing aggregation by summing daily net burn and estimated gross issuance within the calendar period, then dividing those totals. A later supply-only date may remain in the daily supply history while these burn metrics correctly point to an earlier complete date.

It is an estimate, not an independently observed protocol issuance value. Daily period-end supply has approximate float64 precision, and any unmodeled supply adjustment can prevent exact reconciliation. Negative estimates are preserved and reported as data-quality anomalies rather than clamped. A rolling burn offset is the ratio of period net-burn total to period estimated-issuance total; it is null when the denominator is unavailable or non-positive. Complete daily observations are required for flow totals and rolling ratios.

Neither this estimate nor gross burn is Effective Emissions. Effective Emissions also accounts for changes to liquid supply and mechanisms such as staking, locking, and buybacks; this project does not independently measure all those mechanisms.

## Contract rewards

`contract_reward_event_audit.json` is a one-time BigQuery result. The collector is currently configured for 2026-01-01 through 2026-10-04 with a seven-day seed lookback. The cached raw file has also been experimentally extended through 2026-11-13; that extension is data already on disk, not the configured range for a future query. The query compares consecutive non-staked balances around `action_receipt_gas_reward` changes. Only positive deltas with an unambiguous order and a previous balance count toward that day's `contract_rewards_near`; other events are classified and reported in the audit. A missing event row inside a complete audited range means there were no qualifying reward events that day. The project retains the measured value for 2026-11-04 and applies its protocol-v87 zero-reward policy beginning 2026-11-05. Where neither a complete audit nor that policy supplies an answer, rewards remain unknown (`null`).

Contract rewards are historical fee rebates, not newly issued supply, gross burn, or protocol revenue. [nearcore's gas documentation](https://github.com/near/nearcore/blob/master/docs/architecture/how/gas.md) describes contract rewards through protocol version 86; later behavior should be checked against observed data.

## Outputs

- `snapshot.json`: latest tokenomics metrics, derived/estimated metric labels, and dataset coverage.
- `snapshot.json` also contains validator aggregate metrics and the top-20 active-stake leaderboard.
- `daily_tokenomics.json` and `{weekly,monthly,quarterly,yearly}_tokenomics.json`: supply and inflation observations by frequency.
- `daily_burn.json` and `{weekly,monthly,quarterly,yearly}_burn.json`: gross burn, contract rewards, and net burn observations by frequency.
- `daily_issuance.json` and `{weekly,monthly,quarterly,yearly}_issuance.json`: net issuance, estimated gross issuance, and Burn Coverage observations by frequency.
- `daily_active_validator_stake.json` and period-specific active-stake files: period-end stake and supply observations.
- Buyback transfer files by frequency plus `buyback_transfer_type_breakdown.json` for the cumulative chart breakdown.
- Existing price and period-end supply files retain their current schemas and roles.

Protocol revenue-to-issuance comparisons are not generated because the current source definitions and USD valuation conventions have not been reconciled sufficiently for a defensible ratio. Revenue is not treated as burn or supply removal.
