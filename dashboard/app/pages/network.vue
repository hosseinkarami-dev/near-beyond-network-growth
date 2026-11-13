<script setup lang="ts">
import { Activity, CircleDollarSign, Clock3, Cpu, FilePlus2, Layers3, UsersRound, Wallet, Zap, Coins } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCompact, formatCurrency, formatPercent, makeCurrencySeries, makeSeries } from '~/composables/useAnalytics'
const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string

const periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const { data, pending, error, refresh } = await useAsyncData('network-analytics', async () => {
  const paths = [
    'dashboard.json', 'network/snapshot.json', 'network/stablecoin_supply.json',
    ...periods.map((period) => `network/${period}_metrics.json`),
    ...periods.filter((period) => period !== 'daily').map((period) => `network/${period}_stablecoin_supply.json`),
  ]
  const docs = await Promise.all(paths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })
const snapshot = computed(() => data.value?.['network/snapshot.json'])
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
const stablecoinSupply = computed(() => data.value?.['network/stablecoin_supply.json'])
const stablecoinMetrics = computed(() => snapshot.value?.key_metrics?.stablecoin_supply_usd)
const stablecoinPercent = (value: number | string | null | undefined) => value == null ? '—' : formatPercent(value)
const stablecoinCurrencyChange = (value: number | string | null | undefined) => {
  if (value == null) return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return `${amount > 0 ? '+' : ''}${formatCurrency(amount, 'USD', 1)}`
}
const stablecoinSeries = computed(() => ({
  ...Object.fromEntries(periods.map((period) => {
    const document = period === 'daily'
      ? stablecoinSupply.value
      : data.value?.[`network/${period}_stablecoin_supply.json`]
    const rows = document?.observations ?? []
    return [period, { USD: [{
      name: 'Circulating stablecoin supply · USD',
      type: 'line' as const,
      color: '#79c8ee',
      area: true,
      data: rows.map((row: any) => [
        row.period ?? row.date,
        row.total_circulating_usd == null ? null : Number(row.total_circulating_usd),
      ]),
    }] }]
  })),
}))
const datasets = computed(() => makeSeries(
  Object.fromEntries(periods.map((period) => [period, data.value?.[`network/${period}_metrics.json`]]).filter(([, value]) => value)),
  [
    { key: 'transactions', label: 'Transactions', type: 'bar', color: '#b4f273' },
    { key: 'active_accounts', label: 'Active accounts', type: 'line', color: '#79c8ee', axis: 1 },
  ],
))
const feeDatasets = computed(() => {
  const result: Record<string, Record<string, any[]>> = {}
  for (const period of periods) {
    const rows = data.value?.[`network/${period}_metrics.json`]?.observations ?? []
    result[period] = {
      NEAR: [{ name: 'Transaction fees · NEAR', type: 'bar', color: '#b4f273', data: rows.map((row: any) => [row.period ?? row.date, row.transaction_fees_near == null ? null : Number(row.transaction_fees_near)]) }],
      USD: [{ name: 'Transaction fees · USD', type: 'bar', color: '#79c8ee', data: rows.map((row: any) => [row.period ?? row.date, row.transaction_fees_usd == null ? null : Number(row.transaction_fees_usd)]) }],
    }
  }
  return result
})
const contracts = computed(() => makeSeries(
  Object.fromEntries(periods.map((period) => [period, data.value?.[`network/${period}_metrics.json`]]).filter(([, value]) => value)),
  [
    { key: 'new_contracts', label: 'New contracts', type: 'bar', color: '#f5c978' },
    { key: 'active_contracts', label: 'Active contracts', type: 'line', color: '#79c8ee', axis: 1 },
  ],
))
const market = computed(() => makeCurrencySeries(
  Object.fromEntries(periods.map((period) => [period, data.value?.[`network/${period}_metrics.json`]]).filter(([, value]) => value)),
  {
    USD: [{ key: 'tvl_usd', label: 'Network TVL', type: 'line', color: '#b4f273', area: true }],
    NEAR: [{ key: 'tvl_near', label: 'Network TVL', type: 'line', color: '#79c8ee', area: true }],
  },
))
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="13" :charts="5" />
  <DataLoadError v-else-if="error" title="Network data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading title="Network" description="Daily network usage, activity, and performance." :updated-at="snapshot?.network?.updated_at" />
    <div class="section-title-row network-section-title"><div><h2>Network health</h2><p>Chain-wide indicators and latest network state</p></div></div>
    <div class="metric-grid network-extra-metrics">
      <MetricCard label="Average block time" :value="snapshot?.network_stats?.avg_block_time == null ? '—' : `${Number(snapshot.network_stats.avg_block_time).toFixed(3)} s`" :icon="Clock3" tone="blue" />
      <MetricCard label="TPS" :value="formatCompact(snapshot?.network_stats?.tps)" :icon="Activity" tone="amber" />
      <MetricCard label="Nodes online" :value="formatCompact(snapshot?.network_stats?.nodes_online)" :icon="Cpu" tone="violet" />
    </div>
    <div class="section-title-row network-section-title"><div><h2>Network trends</h2><p>Historical activity, fees, contracts, and total value locked</p></div></div>
    <div class="overview-grid network-metric-chart-layout network-chart-row">
      <MixedChart title="Network activity" subtitle="Transactions and active accounts" :datasets="datasets" initial-period="daily" :height="330" />
      <div class="metric-grid network-chart-metrics">
        <MetricCard label="Total transactions" :value="formatCompact(snapshot?.network_stats?.total_txns)" :icon="Zap" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Transactions · 24h" :value="formatCompact(snapshot?.key_metrics?.transactions?.value)" :change="formatPercent(snapshot?.key_metrics?.transactions?.change_24h_pct)" :icon="Activity" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Active accounts" :value="formatCompact(snapshot?.key_metrics?.active_accounts?.value)" :change="formatPercent(snapshot?.key_metrics?.active_accounts?.change_24h_pct)" :icon="UsersRound" tone="blue" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="overview-grid network-metric-chart-layout network-chart-row">
      <MixedChart title="Contract activity" subtitle="New contracts and active contracts" :datasets="contracts" initial-period="daily" :height="290" />
      <div class="metric-grid network-chart-metrics">
        <MetricCard label="New contracts" :value="formatCompact(snapshot?.key_metrics?.new_contracts?.value)" :detail="`${formatCompact(snapshot?.key_metrics?.new_contracts?.sum_7d)} in 7 days`" :change-label="''" :icon="FilePlus2" tone="amber" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Active contracts" :value="formatCompact(snapshot?.key_metrics?.active_contracts?.value)" :change="formatPercent(snapshot?.key_metrics?.active_contracts?.change_24h_pct)" :icon="Wallet" tone="violet" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="overview-grid network-metric-chart-layout network-chart-row">
      <BarChart title="Transaction fees" subtitle="Choose the fee unit and calendar period" :datasets="feeDatasets" initial-period="daily" initial-currency="USD" :height="290" :methodology="methodologies?.network?.transaction_fees" />
      <div class="metric-grid network-chart-metrics">
        <MetricCard label="Total transaction fees" :value="`${formatCompact(snapshot?.key_metrics?.total_transaction_fees_near?.value, 2)} NEAR`" :icon="CircleDollarSign" tone="green" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Transaction fees · 24h" :value="`${formatCompact(snapshot?.key_metrics?.transaction_fees_near?.value, 2)} NEAR`" :change="formatPercent(snapshot?.key_metrics?.transaction_fees_near?.change_24h_pct)" :icon="CircleDollarSign" tone="blue" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="overview-grid network-metric-chart-layout network-chart-row">
      <LineChart title="Network TVL" subtitle="Period-end network value" :datasets="market" initial-period="monthly" initial-currency="USD" :height="290" />
      <div class="metric-grid network-chart-metrics">
        <MetricCard label="Network TVL" :value="formatCurrency(snapshot?.key_metrics?.tvl_usd?.value, 'USD', 0)" :change="formatPercent(snapshot?.key_metrics?.tvl_usd?.change_24h_pct)" :icon="Layers3" tone="blue" body-align="center" value-size="xlarge" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row network-section-title"><div><h2>Stablecoin supply</h2><p>Circulating stablecoin value on NEAR · USD</p></div></div>
    <div class="overview-grid network-stablecoin-layout">
      <LineChart title="Stablecoin supply" subtitle="Daily values and period-end snapshots · USD" :datasets="stablecoinSeries" initial-period="monthly" initial-currency="USD" :height="310" :methodology="methodologies?.network?.stablecoin_supply" />
      <div class="metric-grid network-stablecoin-metrics">
        <MetricCard label="Current supply" :value="formatCurrency(stablecoinMetrics?.value, 'USD', 1)" :detail="stablecoinMetrics?.date ? `As of ${stablecoinMetrics.date}` : 'No valid observation'" :icon="Coins" tone="blue" :change-label="''" body-align="center" mobile-body-align="left" />
        <MetricCard label="30D net change" :value="stablecoinCurrencyChange(stablecoinMetrics?.change_30d_usd)" :change="stablecoinPercent(stablecoinMetrics?.change_30d_pct)" change-label="30-day supply change" :icon="CircleDollarSign" tone="green" body-align="center" mobile-body-align="left" />
        <MetricCard label="90D net change" :value="stablecoinCurrencyChange(stablecoinMetrics?.change_90d_usd)" :change="stablecoinPercent(stablecoinMetrics?.change_90d_pct)" change-label="90-day supply change" :icon="CircleDollarSign" tone="violet" body-align="center" mobile-body-align="left" />
      </div>
    </div>
  </template>
</template>
