# NEARscope · Beyond Network Growth

NEARscope is a research dashboard and data pipeline for examining whether NEAR ecosystem growth is translating into sustainable economic value. The project separates source collection, normalization, analytics, and presentation so that dashboard pages display prepared datasets rather than calculating financial or tokenomics metrics in the browser.

## Project layout

```text
data/
  raw/          Provider responses and resumable collection checkpoints
  normalized/   Validated, standardized source observations
  analytics/    Dashboard-ready snapshots, time series, and period outputs
dashboard/
  app/          Nuxt/Vue pages, components, charts, and styling
  public/data/  Local copy of Analytics JSON served to the dashboard
scripts/
  collectors/   Provider-specific BigQuery and FastNEAR collectors
  normalization/ Provider parsers and source-to-normalized registry
  analytics/   Domain analytics builders and output writers
  queries/     BigQuery SQL files
  rpc_clients/ Reusable typed NEAR JSON-RPC client
tests/          Python unittest suite
docs/           Architecture and metric definitions
```

The data flow is:

```text
Providers → collectors → data/raw → parsers → data/normalized
          → analytics builders → data/analytics → dashboard
```

Raw files preserve provider data or resumable checkpoints. Normalization validates and standardizes those inputs. Analytics performs joins, formulas, aggregations, and period construction. The dashboard reads Analytics JSON and formats it for display.

## Requirements and setup

- Python 3.11 or later
- Node.js and npm compatible with the installed Nuxt 4 toolchain
- Google Cloud Application Default Credentials for BigQuery collection
- A NearBlocks API key is optional; it can improve access limits

From the repository root, install the Python dependencies:

```powershell
py -m pip install -r requirements.txt
```

For BigQuery collection, authenticate with Application Default Credentials before running the full pipeline:

```powershell
gcloud auth application-default login
```

If your Google account does not provide a default project, set `GOOGLE_CLOUD_PROJECT` in the environment. Set `NEARBLOCKS_API_KEY` in the environment or in a root `.env` file when you have a key. Do not commit credentials or secret values.

## Run the data pipeline

Run from the repository root:

```powershell
py scripts/main.py
```

The command runs three stages in order:

1. **Fetch** updates registered sources and raw checkpoints.
2. **Normalize** parses available raw data into standardized JSON.
3. **Analytics** builds dashboard snapshots and time series.

Fetch failures are reported as warnings; the available sources continue through normalization and analytics. Analytics builders isolate sections so a missing source can leave that section empty without preventing unrelated sections from being generated. Re-running the pipeline is supported: incremental collectors skip dates and records already present where the source supports incremental collection. Daily collectors use completed UTC dates, so the current UTC day is not treated as a complete observation.

The daily historical validator-stake collector runs at the end of Fetch because it uses block heights from raw BigQuery `daily_supply.json`. It checkpoints successful days so a later run can continue without requesting already-collected dates again. The contract-reward event audit is a fixed-range query and is not an open-ended daily feed; its configured range is 2026-01-01 through 2026-11-04.

You can also run individual local stages from the repository root:

```powershell
py scripts/normalize.py       # rebuild normalized files from available raw JSON
py scripts/build_analytics.py # rebuild Analytics from local normalized JSON; no provider fetch
```

The Python test suite uses the standard library:

```powershell
py -m unittest discover -s tests
```

## Run the dashboard

From the dashboard directory:

```powershell
cd dashboard
npm install
npm run dev
```

Open the local URL printed by Nuxt. Do not open `dashboard/index.html` through `file://`; the application is served by Nuxt/Vite and reads JSON over HTTP.

The `dev`, `build`, and `generate` npm scripts synchronize `data/analytics/` into `dashboard/public/data/analytics/` before starting. After rebuilding Analytics while a dev server is already running, refresh its served copy with:

```powershell
npm run sync:data
```

Create a production build with `npm run build`; `npm run preview` previews the generated Nuxt build.

### Analytics data URL

The dashboard's public data base URL is configurable with `NUXT_PUBLIC_ANALYTICS_BASE_URL`. Its default is `/data/analytics`. Copy `dashboard/.env.example` to `dashboard/.env` and change that variable only when serving Analytics JSON from a different path or hosted base URL. The default value is unchanged in the Nuxt configuration.

## Dashboard pages

- **Dashboard** is the concise Investment Thesis overview: investment KPIs, economic value versus supply expansion, buyback-wallet inflows and balance, network security, ecosystem activity/liquidity, and market/supply context.
- **Research & Methodology** explains the research question, framework, metric definitions, formulas, findings from generated snapshots, balanced implications, sources, and reproduction steps.
- **Network**, **Tokenomics**, **Intents**, and **Protocols** contain the detailed analysis for their respective areas.

Chart period aggregation and metric calculations belong to `scripts/analytics/`. Vue pages may select or format existing Analytics fields, but must not recalculate period totals, ratios, or other derived measures.

## Metric definitions and interpretation

- **Net issuance** is the change between consecutive daily total-supply snapshots: `total_supply(D) - total_supply(D-1)`.
- **Net fee burn** is `execution_outcomes.tokens_burnt - contract_rewards`. The project uses the reported `tokens_burnt` amount; it does not reconstruct burn as gas burnt times gas price.
- **Estimated gross issuance** is `net issuance + net fee burn`. It is inferred from supply change and burn data, not directly fetched as validator/staking rewards.
- **Annualized net inflation (30D)** is `((supply(D) / supply(D-30))^(365/30) - 1) × 100`. It uses compounded annualization and includes the effect of burns through total-supply change.
- **Burn Coverage** is `sum(net fee burn) / sum(estimated gross issuance) × 100` for the selected period. Period totals are aggregated in Analytics before calculating the ratio.
- **NEAR Intents 30-day revenue capture rate** is the sum of reported daily revenue divided by the sum of gross fees over the same trailing 30 dates, multiplied by 100. Revenue sweeps can shift recognition timing; the result is uncapped and may exceed 100% in a window.
- **Staking ratio** is current active validator stake divided by latest circulating supply, multiplied by 100. The validator stake comes from NearBlocks; the supply denominator has approximate FLOAT64 precision.
- **Top 10 stake share** is the combined stake of the ten largest active validators divided by total active validator stake. It is a concentration measure within active stake.
- **Buyback-wallet inflows** record transfers into `buybacks.multisignature.near`, grouped by attributed source and transfer type. An inflow does not establish that a market purchase occurred or quantify a completed buyback. The wallet balance is a separate finalized RPC snapshot.

Important limitations and exact source definitions are documented in `docs/analytics/`, particularly `tokenomics.md` and `near_intents.md`. USD conversions that use Binance NEARUSDT use USDT as a USD price proxy. Supply observations are approximate FLOAT64 values; historical validator stake is an exact YoctoNEAR sum before conversion to NEAR.

## Data sources

- **NearBlocks API:** network statistics, address/transaction statistics, validator summary (`/v3/validators/info`), and validator records (`/v3/validators`).
- **DefiLlama API:** NEAR chain TVL, stablecoin charts, protocol fees/revenue/DEX volume, and NEAR Intents volume and TVL.
- **Google BigQuery public NEAR mainnet:** daily supply snapshots, execution-outcome `tokens_burnt`, contract-reward event audit, and buyback-wallet transfers. Queries are maintained in `scripts/queries/` and registered in `scripts/sources.py`.
- **Binance Spot API:** daily NEARUSDT klines used for price history and USD conversion.
- **FastNEAR archival RPC:** block/validator calls used for historical active stake and `view_account` for the current buyback-wallet balance.

Source endpoints, raw filenames, and update frequencies are registered in `scripts/sources.py`. BigQuery query configuration and collectors live in `scripts/collectors/bigquery.py`; FastNEAR collectors live in `scripts/collectors/`; parsers are registered in `scripts/normalization/registry.py`. Analytics output files and calculations are organized by domain under `scripts/analytics/`.
