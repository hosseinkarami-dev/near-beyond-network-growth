<script setup lang="ts">
import { ChartNoAxesCombined, Coins, CircleDollarSign, TrendingUp, WalletCards, Flame } from '@lucide/vue'
import { formatCompact, formatCurrency, formatPercent } from '~/composables/useAnalytics'

const periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const { data, pending, error, refresh } = await useAsyncData('tokenomics-analytics', async () => {
  const paths = [
    'dashboard.json', 'tokenomics/snapshot.json', 'tokenomics/daily_near_price.json', 'tokenomics/daily_supply.json',
    'tokenomics/daily_tokenomics.json', 'tokenomics/daily_contract_rewards.json',
    ...periods.filter((period) => period !== 'daily').map((period) => `tokenomics/${period}_supply.json`),
  ]
  const docs = await Promise.all(paths.map((path) => $fetch<any>(`/data/analytics/${path}`)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })
const snapshot = computed(() => data.value?.['tokenomics/snapshot.json'])
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
const tokenomicsRows = computed(() => data.value?.['tokenomics/daily_tokenomics.json']?.items ?? [])
const priceByDate = computed(() => Object.fromEntries((data.value?.['tokenomics/daily_near_price.json']?.observations ?? []).map((row: any) => [row.date, Number(row.near_price)])))
const priceChart = computed(() => ({
  daily: { USD: [
    { name: 'NEAR price', type: 'line' as const, color: '#b4f273', area: true, data: (data.value?.['tokenomics/daily_near_price.json']?.observations ?? []).slice(-365).map((row: any) => [row.date, Number(row.near_price)]) },
    { name: '7-day average', type: 'line' as const, color: '#79c8ee', data: (data.value?.['tokenomics/daily_near_price.json']?.observations ?? []).slice(-365).map((row: any) => [row.date, row.moving_average_7d == null ? null : Number(row.moving_average_7d)]) },
    { name: '30-day average', type: 'line' as const, color: '#c3a5ff', data: (data.value?.['tokenomics/daily_near_price.json']?.observations ?? []).slice(-365).map((row: any) => [row.date, row.moving_average_30d == null ? null : Number(row.moving_average_30d)]) },
  ] },
}))
const supplyChart = computed(() => {
  const docs: Record<string, any> = { daily: data.value?.['tokenomics/daily_supply.json'] }
  for (const period of periods.filter((value) => value !== 'daily')) docs[period] = data.value?.[`tokenomics/${period}_supply.json`]
  const result: Record<string, Record<string, any[]>> = {}
  for (const [period, doc] of Object.entries(docs)) {
    const rows = doc?.observations ?? doc?.items ?? []
    result[period] = { NEAR: [
      { name: 'Total supply', type: 'line', color: '#f5c978', area: true, data: rows.map((row: any) => [row.date ?? row.period, Number(row.total_supply)]) },
      { name: 'Circulating supply', type: 'line', color: '#b4f273', data: rows.map((row: any) => [row.date ?? row.period, row.circulating_supply == null ? null : Number(row.circulating_supply)]) },
    ] }
  }
  return result
})
const tokenomicsPeriods = computed(() => data.value?.['tokenomics/daily_tokenomics.json']?.periods ?? {})
const supplyDynamicsChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = tokenomicsPeriods.value[period] ?? []
  return [period, { NEAR: [
    { name: 'Net issuance', type: 'line', color: '#b4f273', data: rows.map((row: any) => [row.period, row.net_issuance_near]) },
    { name: 'Gross issuance', type: 'line', color: '#79c8ee', data: rows.map((row: any) => [row.period, row.gross_issuance_near]) },
  ] }]
})))
const burnChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = tokenomicsPeriods.value[period] ?? []
  return [period, {
    NEAR: [
      { name: 'Net burn', type: 'line', color: '#ff8e84', area: true, data: rows.map((row: any) => [row.period, row.net_burn_near]) },
    ],
    USD: [
      { name: 'Net burn', type: 'line', color: '#ff8e84', area: true, data: rows.map((row: any) => [row.period, row.net_burn_usd]) },
    ],
  }]
})))
const burnRateChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = tokenomicsPeriods.value[period] ?? []
  return [period, { NEAR: [{ name: 'Burn Rate', type: 'line', color: '#79c8ee', area: true, valueFormat: 'percent', data: rows.map((row: any) => [row.period, row.burn_rate_pct]) }] }]
})))
const contractRewardsChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = tokenomicsPeriods.value[period] ?? []
  return [period, {
    NEAR: [{ name: 'Contract rewards', type: 'line', color: '#f5c978', area: true, data: rows.map((row: any) => [row.period, row.contract_rewards_near]) }],
    USD: [{ name: 'Contract rewards', type: 'line', color: '#f5c978', area: true, data: rows.map((row: any) => [row.period, row.contract_rewards_usd]) }],
  }]
})))
const inflationChart = computed(() => ({
  daily: { NEAR: [{ name: 'Trailing 30D annualized net inflation', type: 'line' as const, color: '#b4f273', area: true,
    valueFormat: 'percent' as const, data: (tokenomicsPeriods.value.daily ?? []).map((row: any) => [row.period, row.net_inflation_30d_annualized_pct]) }] },
}))
const latestBurn = computed(() => tokenomicsRows.value.at(-1))
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="2" :charts="2" />
  <DataLoadError v-else-if="error" title="Tokenomics data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading title="Tokenomics" description="NEAR price, supply, and market indicators." :updated-at="snapshot?.updated_at" />
    <div class="section-title-row tokenomics-section-title"><div><h2>Market value</h2><p>Spot market capitalization and fully diluted valuation · USD</p></div></div>
    <div class="metric-grid tokenomics-overview-metrics">
      <MetricCard label="Market cap" :value="formatCurrency(snapshot?.metrics?.market_cap, 'USD', 3)" :icon="ChartNoAxesCombined" tone="green" :change-label="''" />
      <MetricCard label="Fully diluted valuation (FDV)" :value="formatCurrency(snapshot?.metrics?.fdv_usd, 'USD', 3)" :icon="ChartNoAxesCombined" tone="violet" :change-label="''" :methodology="methodologies?.tokenomics?.fdv" />
    </div>
    <div class="section-title-row tokenomics-section-title"><div><h2>NEAR price</h2><p>Daily market price with 7-day and 30-day trend lines · USD</p></div></div>
    <div class="overview-grid tokenomics-metric-chart-layout">
      <AnalyticsChart title="NEAR price" subtitle="Daily price with 7-day and 30-day averages" :datasets="priceChart" :height="330" :methodology="methodologies?.tokenomics?.near_price" />
      <div class="metric-grid tokenomics-chart-metrics">
        <MetricCard label="NEAR price" :value="formatCurrency(snapshot?.metrics?.near_price?.value, 'USD', 3)" :change="formatPercent(snapshot?.metrics?.change_24h)" :icon="CircleDollarSign" tone="green" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="7-day moving average" :value="formatCurrency(snapshot?.metrics?.near_price?.moving_average_7d, 'USD', 3)" :icon="TrendingUp" tone="blue" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row tokenomics-section-title"><div><h2>Supply profile</h2><p>Total and circulating NEAR supply over time</p></div></div>
    <div class="overview-grid tokenomics-metric-chart-layout">
      <AnalyticsChart title="NEAR supply" subtitle="Period-end supply observations" :datasets="supplyChart" initial-period="monthly" :height="330" :methodology="methodologies?.tokenomics?.supply" />
      <div class="metric-grid tokenomics-chart-metrics">
        <MetricCard label="Circulating supply" :value="`${formatCompact(snapshot?.metrics?.circulating_supply)} NEAR`" :icon="WalletCards" tone="violet" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Total supply" :value="`${formatCompact(snapshot?.metrics?.total_supply)} NEAR`" :icon="Coins" tone="amber" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" />
      </div>
    </div>
    <div class="section-title-row tokenomics-section-title"><div><h2>Net inflation</h2><p>Trailing net supply growth, annualized over 30 days, 3 months, and 1 year</p></div></div>
    <div class="overview-grid tokenomics-metric-chart-layout">
      <LineChart title="Current net inflation · 30D annualized" subtitle="Includes the effect of token burn" :datasets="inflationChart" initial-period="daily" :height="320" :methodology="methodologies?.tokenomics?.net_inflation" />
      <div class="metric-grid tokenomics-chart-metrics">
        <MetricCard label="Current net inflation · 30D annualized" :value="formatPercent(snapshot?.metrics?.current_net_inflation_30d_annualized_pct)" :icon="TrendingUp" tone="green" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" :methodology="methodologies?.tokenomics?.net_inflation" />
        <MetricCard label="Current net inflation · 3M annualized" :value="formatPercent(snapshot?.metrics?.current_net_inflation_3m_annualized_pct)" :icon="TrendingUp" tone="blue" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" :methodology="methodologies?.tokenomics?.net_inflation" />
        <MetricCard label="Current net inflation · 1Y annualized" :value="formatPercent(snapshot?.metrics?.current_net_inflation_1y_annualized_pct)" :icon="TrendingUp" tone="violet" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" :methodology="methodologies?.tokenomics?.net_inflation" />
      </div>
    </div>
    <div class="section-title-row tokenomics-section-title"><div><h2>Token issuance</h2><p>Net issuance after burn alongside estimated gross issuance · NEAR</p></div></div>
    <LineChart title="Net and gross issuance" subtitle="Up to 365 daily observations; choose a calendar period" :datasets="supplyDynamicsChart" initial-period="daily" :height="360" :methodology="methodologies?.tokenomics?.supply_dynamics" />
    <div class="section-title-row tokenomics-section-title"><div><h2>Burn &amp; contract rewards</h2><p>Compare contract rewards with fee burn and its offset against gross issuance</p></div></div>
    <div class="tokenomics-burn-charts">
      <LineChart title="Contract rewards" subtitle="Rewards by calendar period · NEAR or USD" :datasets="contractRewardsChart" initial-period="daily" initial-currency="NEAR" :height="320" :methodology="methodologies?.tokenomics?.contract_rewards" />
      <div class="tokenomics-burn-chart-grid">
        <LineChart title="Net burn" subtitle="Gross fee burn less contract rewards · NEAR or USD" :datasets="burnChart" initial-period="daily" initial-currency="NEAR" :height="330" :methodology="methodologies?.tokenomics?.net_burn" />
        <LineChart title="Burn Rate" subtitle="Fee burn as a share of estimated gross issuance · %" :datasets="burnRateChart" initial-period="daily" :height="330" :methodology="methodologies?.tokenomics?.burn_rate" />
      </div>
      <div class="metric-grid tokenomics-burn-metrics">
        <MetricCard label="Net burn · latest day" :value="`${formatCompact(latestBurn?.net_burn_near, 2)} NEAR`" :detail="latestBurn?.date ?? '—'" :icon="Flame" tone="amber" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Burn Rate · latest day" :value="formatPercent(latestBurn?.burn_rate_pct)" :icon="TrendingUp" tone="violet" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" :methodology="methodologies?.tokenomics?.burn_rate" />
      </div>
    </div>
  </template>
</template>
