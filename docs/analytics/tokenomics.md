# Tokenomics analytics

The Tokenomics analytics builder consumes normalized datasets under `data/normalized`. It does not read raw files.

## Supply observations and net inflation

`daily_supply.json` is the existing BigQuery period-end supply snapshot. Its values have `approximate_float64` source precision. Raw source timestamps inspected for this dataset occur close to 23:59 UTC on each `utc_date`; each date is therefore treated as that UTC day's period-end observation. The daily change assigned to date D is `total_supply(D) - total_supply(D-1)`, which approximates the flow over UTC date D. A missing prior calendar date leaves the daily change null.

Non-circulating supply is `total_supply - circulating_supply`. Circulating supply ratio is `(circulating_supply / total_supply) * 100`. These describe a supply snapshot and liquid availability; changes in circulating supply are not total-supply inflation.

For N-day supply growth, the builder compares observations exactly N UTC calendar days apart:

- `net_supply_change_Nd_near = supply(end) - supply(end - N days)`
- `net_supply_growth_Nd_pct = (supply(end) / supply(end - N days) - 1) * 100`
- `net_inflation_Nd_annualized_pct = ((supply(end) / supply(end - N days)) ** (365 / N) - 1) * 100`

The 30-day annualized rate is the current net inflation KPI. Endpoints are not interpolated. Deflationary-day counts require every daily supply change in the complete N-day window.

## Gross burn and estimated issuance

`daily_gross_burn.json` is the normalized BigQuery gross burn series, expressed in NEAR. Estimated gross issuance is reconstructed as:

`estimated_gross_issuance_near = daily_net_supply_change_near + gross_burn_near`

It is an estimate, not an independently observed protocol issuance value. Daily period-end supply has approximate float64 precision, and any unmodeled supply adjustment can prevent exact reconciliation. Negative estimates are preserved and reported as data-quality anomalies rather than clamped. A rolling burn offset is the ratio of period gross-burn total to period estimated-issuance total; it is null when the denominator is unavailable or non-positive. Complete daily observations are required for flow totals and rolling ratios.

Neither this estimate nor gross burn is Effective Emissions. Effective Emissions also accounts for changes to liquid supply and mechanisms such as staking, locking, and buybacks; this project does not independently measure all those mechanisms.

## Contract rewards

`daily_contract_rewards.json` is currently a synthetic PowerShell fixture for development and dashboard testing. Its BigQuery normalization keeps its UTC date and `contract_rewards_near` value without dividing or converting units and adds dataset-level source metadata that identifies it as synthetic. The fixture is excluded from production Tokenomics metrics. To generate the separate demo analytics file, set `NEAR_INCLUDE_SYNTHETIC_DATA=1` when running `scripts/build_analytics.py`; the dashboard's dev script syncs this labeled file, while production dashboard sync omits it.

The synthetic chart and 30D/90D/365D totals are demonstrations only and must not be cited as observed NEAR network activity. Rolling totals are null unless every UTC date in the window is present. Contract rewards are historical fee rebates, not newly issued supply, gross burn, or protocol revenue. [nearcore's gas documentation](https://github.com/near/nearcore/blob/master/docs/architecture/how/gas.md) describes contract rewards through protocol version 86; protocol-version-87 behavior must be validated against actual observations and must not be inferred from this synthetic fixture.

## Outputs

- `snapshot.json`: latest tokenomics metrics, derived/estimated metric labels, and dataset coverage.
- `daily_tokenomics.json`: supply, net-change, gross-burn, estimated-issuance, and burn-offset daily observations.
- `contract_rewards_demo.json`: optional, separately labeled synthetic demo output; never merged into production snapshot metrics.
- Existing price and period-end supply files retain their current schemas and roles.

Protocol revenue-to-issuance comparisons are not generated because the current source definitions and USD valuation conventions have not been reconciled sufficiently for a defensible ratio. Revenue is not treated as burn or supply removal.
