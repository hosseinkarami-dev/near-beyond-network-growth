# Project architecture

The pipeline keeps collection, normalization, analytics, and presentation in separate layers:

```text
source registry → collectors → data/raw → normalization → data/normalized
              → analytics builders → data/analytics → dashboard
```

## Python pipeline

- `scripts/main.py` is the command-line entry point. It runs fetch, normalize, then analytics.
- `scripts/sources.py` defines source identities, providers, endpoints, and raw paths. `scripts/paths.py` owns the canonical project and data roots. `scripts/units.py` and `scripts/buybacks.py` hold shared domain constants instead of duplicating them across layers.
- `scripts/fetch.py` coordinates source collection and shared HTTP policy. NearBlocks requests are spaced and transient throttling/server errors use retries with backoff. The daily validator stake collector runs last because it depends on block heights collected by the daily supply source.
- `scripts/collectors/` contains provider-specific collectors: BigQuery and FastNEAR. Reusable typed NEAR RPC calls live in `scripts/rpc_clients/`; SQL lives in `scripts/queries/`.
- `scripts/normalization/registry.py` maps raw sources to provider parsers. Parsers are grouped by provider under `scripts/normalization/parsers/`.
- `scripts/analytics/` groups calculations and output writers by dashboard domain. `build_analytics.py` isolates failures by section and writes fallbacks so other sections continue.
- `scripts/atomic_io.py`, `scripts/data_dirs.py`, and `scripts/validation.py` hold shared file-safety and JSON-validation helpers. `scripts/common.py` and `scripts/bigquery.py` remain compatibility exports; new code imports from the dedicated modules.

## Data and dashboard

- `data/raw/` stores provider responses and resumable collection checkpoints.
- `data/normalized/` stores validated, standardized source observations.
- `data/analytics/` stores calculated snapshots and time series. Period-specific series use separate JSON files.
- `dashboard/app/components/` contains reusable UI and chart components; pages select and display analytics outputs without calculating them.
- `dashboard/scripts/sync-analytics.mjs` copies analytics files into `dashboard/public/data/analytics` for Vite/Nuxt builds.

The standard run is `python scripts/main.py` from the project root. The daily active validator stake collector is intentionally last in the fetch sequence so it can use the latest completed daily-supply block references from that run.
