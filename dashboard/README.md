# NEARscope Investment Thesis

The dashboard reads generated JSON from `../data/analytics` and presents it through a modular Nuxt and Vue interface.

The dashboard data URL base can be overridden with `NUXT_PUBLIC_ANALYTICS_BASE_URL`. Its default remains `/data/analytics`; set the variable to another path or a hosted base URL when needed. See `.env.example`.

## Run locally

1. Open a terminal in `dashboard/`.
2. Run `npm install` once.
3. Run `npm run dev` and open the local URL printed by Nuxt.

The `dev`, `build`, and `generate` scripts copy the current Analytics JSON into `public/data/analytics` before Nuxt starts. The dashboard only reads these copies; it does not modify the source Analytics files.

## Partial data availability

The data pipeline isolates failures by source and analytics section. Missing or invalid raw data is skipped during normalization; a section whose required inputs are unavailable receives an empty snapshot while other sections continue building. Protocol categories are isolated from one another. Dashboard pages also treat an unavailable analytics JSON file as empty data, so one missing file does not prevent the page or the rest of the dashboard from rendering.

Run `python ../scripts/main.py` from the dashboard directory to fetch, normalize, and rebuild analytics. After that pipeline finishes, run `npm run sync:data` to refresh the data served by an already-running dev server.

## Structure

- `app/components/shell`: app navigation and top bar.
- `app/components/ui`: reusable headings, metric cards, and panels.
- `app/components/charts`: reusable ECharts container and period/currency controls.
- `app/pages`: overview, network, tokenomics, NEAR Intents, and protocol pages.
- `app/composables`: theme state, formatting, and Analytics data helpers.

`LineChart`, `BarChart`, `PieChart`, and `MixedChart` are reusable chart entry points built on `AnalyticsChart`. Charts accept multiple line, bar, and pie series, including mixed bar/line series and a second value axis. Period and currency controls are shown when the supplied datasets contain multiple choices.

The frontend dependencies are Nuxt 4, Vue ECharts with Apache ECharts 6, and Lucide Vue icons. DM Sans and Manrope are used for the interface typography.
