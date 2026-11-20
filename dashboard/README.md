# Dashboard

This is the Nuxt frontend. It reads the JSON files built by the Python pipeline and presents them in the Dashboard, Research & Methodology, Network, Tokenomics, Intents, and Protocols pages. Calculations and period aggregation belong to `scripts/analytics/`, not to Vue components.

## Run locally

From this directory:

```sh
npm install
npm run dev
```

The app needs to be served over HTTP; opening an HTML file directly will leave the data requests without their expected base path. The `dev`, `build`, and `generate` commands sync `../data/analytics/` into `public/data/analytics/` before Nuxt runs. A completed `py ../scripts/build_analytics.py` also syncs the built files. If you need to sync by hand, run `npm run sync:data`.

The default data URL is `/data/analytics`. Override it with `NUXT_PUBLIC_ANALYTICS_BASE_URL` in a local `.env` file. See `.env.example`.

## Data availability

Raw responses, normalized records, analytics outputs, and the dashboard's public data copy are generated locally and ignored by Git. On a fresh checkout, run `py ../scripts/main.py` from this directory (or `python3 ../scripts/main.py` on macOS/Linux) to fetch, normalize, build Analytics, and sync the dashboard data.

Collectors and analytics sections handle unavailable sources independently. One missing source can leave its own card or chart empty, but it should not prevent unrelated sections from rendering. Existing saved data is retained when a refresh fails.

## Code layout

- `app/components/shell/` holds navigation and the shared app frame.
- `app/components/ui/` holds reusable headings, cards, tables, and panels.
- `app/components/charts/` holds ECharts wrappers and period/currency controls.
- `app/pages/` holds the Overview and detailed research tabs.
- `app/composables/` holds theme state, formatting helpers, and analytics-file access.
- `scripts/sync-analytics.mjs` copies Analytics JSON into the public directory before a dashboard command.

`LineChart`, `BarChart`, `PieChart`, and `MixedChart` all use the shared `AnalyticsChart` component. Pages pass prepared series to these components; they do not aggregate underlying daily data.
