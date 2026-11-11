<script setup lang="ts">
import { Activity, CalendarDays, History, Layers3, TrendingUp, Wallet, Coins, ChartNoAxesCombined } from '@lucide/vue'
import { formatCurrency, formatPercent, makeCurrencySeries, makeSeries } from '~/composables/useAnalytics'

const periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const tokenPeriods = ['daily', ...periods.filter((period) => period !== 'daily')]
const { data, pending, error, refresh } = await useAsyncData('intents-analytics', async () => {
  const paths = [
    'dashboard.json', 'near_intents/snapshot.json', 'near_intents/tvl_by_chain.json',
    'near_intents/current_tvl_by_token.json', 'near_intents/tvl_by_token_chart.json',
    ...periods.map((period) => `near_intents/${period}_metrics.json`),
    ...tokenPeriods.map((period) => `near_intents/${period}_tvl_by_token.json`),
  ]
  const docs = await Promise.all(paths.map((path) => $fetch<any>(`/data/analytics/${path}`)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })
const snapshot = computed(() => data.value?.['near_intents/snapshot.json'])
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
const metricDocuments = computed(() =>
  Object.fromEntries(periods.map((period) => [period, data.value?.[`near_intents/${period}_metrics.json`]]).filter(([, value]) => value)),
)
const volumeChart = computed(() => makeSeries(metricDocuments.value, [
  { key: 'volume_usd', label: 'Swap volume', type: 'bar', color: '#b4f273' },
]))
const tvlChart = computed(() => makeCurrencySeries(metricDocuments.value, {
  USD: [{ key: 'tvl_usd', label: 'TVL', type: 'line', color: '#79c8ee', area: true }],
  NEAR: [{ key: 'tvl_near', label: 'TVL', type: 'line', color: '#b4f273', area: true }],
}))
const valueCaptureChart = computed(() => makeSeries(metricDocuments.value, [
  { key: 'gross_fees_usd', label: 'Gross Fees', type: 'line', color: '#ff9f6e' },
  { key: 'revenue_usd', label: 'Revenue', type: 'line', color: '#f5c978' },
  { key: 'holders_revenue_usd', label: 'Holders revenue', type: 'line', color: '#c3a5ff' },
  { key: 'revenue_capture_rate_30d_pct', label: '30-Day Revenue Capture Rate', type: 'line', color: '#79c8ee', axis: 1, valueFormat: 'percent' },
]))
const keyMetrics = computed(() => snapshot.value?.key_metrics ?? {})
const metricChange = (value: unknown) => value == null ? undefined : formatPercent(value as number | string)
const currentTokenDistribution = computed(() => {
  const doc = data.value?.['near_intents/current_tvl_by_token.json']
  return { current: {
    USD: [{ name: 'Current TVL by token', type: 'pie' as const, data: doc?.pie_usd ?? [] }],
    NEAR: [{ name: 'Current TVL by token', type: 'pie' as const, data: doc?.pie_near ?? [] }],
  } }
})
const tokenChart = computed(() => {
  const docs = data.value?.['near_intents/tvl_by_token_chart.json']?.periods ?? {}
  const colors = ['#b4f273', '#79c8ee', '#c3a5ff', '#f5c978', '#ff8e84', '#65d6b4', '#9da8ff', '#f49abd']
  return Object.fromEntries(tokenPeriods.map((period) => {
    const rows = docs[period] ?? []
    const make = (field: 'tokens' | 'tokens_near', other: 'other_usd' | 'other_near') => [
      ...(data.value?.['near_intents/current_tvl_by_token.json']?.top_tokens ?? []).map((token: string, index: number) => ({
        name: token, type: 'line' as const, color: colors[index]!,
        data: rows.map((row: any) => [row.period, row[field]?.[token] ?? null]),
      })),
      { name: 'Other tokens', type: 'line' as const, color: '#a7b0a2', data: rows.map((row: any) => [row.period, row[other]]) },
    ]
    return [period, { USD: make('tokens', 'other_usd'), NEAR: make('tokens_near', 'other_near') }]
  }))
})
const chainItems = computed(() => data.value?.['near_intents/tvl_by_chain.json']?.items ?? [])
const chainRankedItems = computed(() => chainItems.value.map((item: any) => ({ name: item.chain, value: Number(item.tvl_usd) })))
const chainTotal = computed(() => data.value?.['near_intents/tvl_by_chain.json']?.total_tvl_usd ?? 0)
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="3" :charts="5" />
  <DataLoadError v-else-if="error" title="NEAR Intents data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading eyebrow="CROSS-CHAIN ACTIVITY" title="NEAR Intents" description="Swap activity, liquidity, and value capture across connected chains." :updated-at="snapshot?.updated_at" />
    <div class="section-title-row intents-section-title">
      <div><h2>Long-range overview</h2><p>Trailing volume and cumulative value captured · USD</p></div>
    </div>
    <div class="metric-grid intents-overview-metrics">
      <MetricCard label="1Y Volume" :value="formatCurrency(keyMetrics.volume_usd?.total_1y, 'USD', 1)" detail="Trailing 12 months" :icon="CalendarDays" tone="amber" :change-label="''" />
      <MetricCard label="All-time Volume" :value="formatCurrency(keyMetrics.volume_usd?.total_all_time, 'USD', 1)" detail="Since inception" :icon="History" tone="violet" :change-label="''" />
      <MetricCard label="Total Gross Fees" :value="formatCurrency(keyMetrics.gross_fees_usd?.cumulative_total, 'USD', 1)" detail="Since first available observation" :icon="Coins" tone="green" :change-label="''" />
    </div>
    <div class="section-title-row intents-section-title">
      <div><h2>Swap volume trend</h2><p>Choose daily, weekly, monthly, quarterly, or yearly data · USD</p></div>
    </div>
    <div class="overview-grid intents-metric-chart-layout intents-chart-row">
      <AnalyticsChart title="Swap volume" subtitle="Daily swap value · USD" :datasets="volumeChart" initial-period="daily" :height="390" :methodology="methodologies?.near_intents?.volume" />
      <div class="metric-grid intents-chart-metrics">
        <MetricCard label="24h Volume" :value="formatCurrency(keyMetrics.volume_usd?.total_24h, 'USD', 1)" :change="metricChange(keyMetrics.volume_usd?.change_24h_pct)" :change-label="keyMetrics.volume_usd?.change_24h_pct == null ? '' : 'vs. previous 24h'" :icon="Activity" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="7d Volume" :value="formatCurrency(keyMetrics.volume_usd?.total_7d, 'USD', 1)" :change="metricChange(keyMetrics.volume_usd?.change_7d_pct)" :change-label="keyMetrics.volume_usd?.change_7d_pct == null ? '' : 'vs. previous 7d'" :icon="CalendarDays" tone="blue" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="30d Volume" :value="formatCurrency(keyMetrics.volume_usd?.total_30d, 'USD', 1)" :change="metricChange(keyMetrics.volume_usd?.change_30d_pct)" :change-label="keyMetrics.volume_usd?.change_30d_pct == null ? '' : 'vs. previous 30d'" :icon="TrendingUp" tone="violet" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row intents-section-title">
      <div><h2>Fees &amp; revenue trends</h2><p>Gross fees, retained revenue, and value attributed to holders · USD</p></div>
    </div>
    <div class="overview-grid intents-metric-chart-layout intents-chart-row">
      <AnalyticsChart title="NEAR Intents value capture" subtitle="Gross Fees, Revenue, Holders revenue, and 30-day capture rate" :datasets="valueCaptureChart" initial-period="daily" :height="390" :methodology="[methodologies?.near_intents?.gross_fees, methodologies?.near_intents?.revenue, methodologies?.near_intents?.holders_revenue, methodologies?.near_intents?.revenue_capture_rate_30d].filter(Boolean)" />
      <div class="metric-grid intents-chart-metrics">
        <MetricCard label="Gross Fees · 7d" :value="formatCurrency(keyMetrics.gross_fees_usd?.total_7d, 'USD', 1)" :change="metricChange(keyMetrics.gross_fees_usd?.change_7d_pct)" :change-label="keyMetrics.gross_fees_usd?.change_7d_pct == null ? '' : 'vs. previous 7d'" :icon="Coins" tone="amber" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Revenue · 7d" :value="formatCurrency(keyMetrics.revenue_usd?.total_7d, 'USD', 1)" :change="metricChange(keyMetrics.revenue_usd?.change_7d_pct)" :change-label="keyMetrics.revenue_usd?.change_7d_pct == null ? '' : 'vs. previous 7d'" :icon="ChartNoAxesCombined" tone="green" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Holders revenue · 7d" :value="formatCurrency(keyMetrics.holders_revenue_usd?.total_7d, 'USD', 1)" :change="metricChange(keyMetrics.holders_revenue_usd?.change_7d_pct)" :change-label="keyMetrics.holders_revenue_usd?.change_7d_pct == null ? '' : 'vs. previous 7d'" :icon="Wallet" tone="violet" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row intents-section-title">
      <div><h2>TVL overview</h2><p>Historical period-end value across supported chains · USD or NEAR</p></div>
    </div>
    <div class="overview-grid intents-metric-chart-layout intents-chart-row">
      <AnalyticsChart title="NEAR Intents TVL" subtitle="Historical value across supported chains · USD or NEAR" :datasets="tvlChart" initial-period="daily" initial-currency="USD" :height="320" :methodology="methodologies?.near_intents?.tvl" />
      <div class="metric-grid intents-chart-metrics">
        <MetricCard label="Current TVL" :value="formatCurrency(keyMetrics.tvl_usd?.value ?? snapshot?.tvl_usd, 'USD', 1)" :change="metricChange(keyMetrics.tvl_usd?.change_7d_pct)" :change-label="keyMetrics.tvl_usd?.change_7d_pct == null ? '' : 'vs. 7d ago'" :icon="Layers3" tone="blue" body-align="center" value-size="xlarge" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row intents-section-title">
      <div><h2>TVL breakdown</h2><p>Current balances by chain and token, plus historical token values · USD or NEAR</p></div>
    </div>
    <div class="overview-grid intents-tvl-grid">
      <PieChart title="Current TVL by token" :subtitle="`${data?.['near_intents/current_tvl_by_token.json']?.date ?? ''} · ${data?.['near_intents/current_tvl_by_token.json']?.items?.length ?? 0} tokens · USD or NEAR`" :datasets="currentTokenDistribution" initial-period="current" initial-currency="USD" :height="320" :methodology="methodologies?.near_intents?.current_tvl_by_token" />
      <RankedMetricList title="TVL by chain" subtitle="Largest chains by current TVL · USD" :items="chainRankedItems" :total-value="chainTotal" total-label="Total across chains" :badge="`${chainItems.length} CHAINS`" :scrollable="true" empty-message="No chain TVL observations are available." :methodology="methodologies?.near_intents?.tvl_by_chain" />
    </div>
    <div class="overview-grid intents-token-grid">
      <AnalyticsChart title="TVL by token" subtitle="Period-end token value · USD or NEAR" :datasets="tokenChart" initial-period="daily" initial-currency="USD" :height="330" :methodology="methodologies?.near_intents?.tvl_by_token" />
    </div>
  </template>
</template>
