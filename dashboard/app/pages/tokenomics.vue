<script setup lang="ts">
import { ChartNoAxesCombined, Coins, CircleDollarSign, TrendingUp, WalletCards, Flame, UsersRound } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCompact, formatCurrency, formatIdentifierLabel, formatPercent } from '~/composables/useAnalytics'
const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string

const periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const { data, pending, error, refresh } = await useAsyncData('tokenomics-analytics', async () => {
  const paths = [
    'dashboard.json', 'tokenomics/snapshot.json', 'tokenomics/daily_near_price.json', 'tokenomics/daily_supply.json',
    'tokenomics/daily_tokenomics.json',
    'tokenomics/daily_burn.json', 'tokenomics/daily_issuance.json',
    ...periods.filter((period) => period !== 'daily').flatMap((period) => [
      `tokenomics/${period}_tokenomics.json`, `tokenomics/${period}_burn.json`,
      `tokenomics/${period}_issuance.json`, `tokenomics/${period}_active_validator_stake.json`,
    ]),
    'tokenomics/buyback_transfer_type_breakdown.json',
    ...periods.map((period) => `tokenomics/${period}_buyback_transfers.json`),
    'tokenomics/daily_active_validator_stake.json',
    ...periods.filter((period) => period !== 'daily').map((period) => `tokenomics/${period}_supply.json`),
  ]
  const docs = await Promise.all(paths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })
const snapshot = computed(() => data.value?.['tokenomics/snapshot.json'])
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
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
const historicalActiveStakeChart = computed(() => {
  return Object.fromEntries(periods.map((period) => {
    const document = period === 'daily'
      ? data.value?.['tokenomics/daily_active_validator_stake.json']
      : data.value?.[`tokenomics/${period}_active_validator_stake.json`]
    const rows = document?.items ?? []
    return [period, { 'NEAR / %': [
      {
        name: 'Active validator stake', type: 'line' as const, color: '#f5c978',
        data: rows.map((row: any) => [row.date, row.total_active_stake_near == null ? null : Number(row.total_active_stake_near)]),
      },
      {
        name: 'Active stake as % of total supply', type: 'line' as const, color: '#79c8ee',
        yAxisIndex: 1, valueFormat: 'percent' as const,
        data: rows.map((row: any) => [row.date, row.staking_ratio_pct == null ? null : Number(row.staking_ratio_pct)]),
      },
    ] }]
  }))
})
function tokenomicsRows(period: string) {
  const document = period === 'daily'
    ? data.value?.['tokenomics/daily_tokenomics.json']
    : data.value?.[`tokenomics/${period}_tokenomics.json`]
  return document?.items ?? []
}
function burnRows(period: string) {
  const document = period === 'daily'
    ? data.value?.['tokenomics/daily_burn.json']
    : data.value?.[`tokenomics/${period}_burn.json`]
  return document?.items ?? []
}
function issuanceRows(period: string) {
  const document = period === 'daily'
    ? data.value?.['tokenomics/daily_issuance.json']
    : data.value?.[`tokenomics/${period}_issuance.json`]
  return document?.items ?? []
}
const buybackPie = computed(() => ({
  daily: { NEAR: [{
    name: 'Cumulative buyback inflow',
    type: 'pie' as const,
    data: (data.value?.['tokenomics/buyback_transfer_type_breakdown.json']?.observations ?? []).map((row: any) => ({
      name: formatIdentifierLabel(row.transfer_type),
      value: Number(row.total_inflow_near),
    })),
  }] },
}))
const supplyDynamicsChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = issuanceRows(period)
  return [period, { NEAR: [
    { name: 'Net issuance', type: 'line', color: '#b4f273', data: rows.map((row: any) => [row.period ?? row.date, row.net_issuance_near]) },
    { name: 'Gross issuance', type: 'line', color: '#79c8ee', data: rows.map((row: any) => [row.period ?? row.date, row.gross_issuance_near]) },
  ] }]
})))
const burnChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = burnRows(period)
  return [period, {
    NEAR: [
      { name: 'Net burn', type: 'line', color: '#ff8e84', area: true, data: rows.map((row: any) => [row.period ?? row.date, row.net_burn_near]) },
    ],
    USD: [
      { name: 'Net burn', type: 'line', color: '#ff8e84', area: true, data: rows.map((row: any) => [row.period ?? row.date, row.net_burn_usd]) },
    ],
  }]
})))
const burnCoverageChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = issuanceRows(period)
  return [period, { NEAR: [{ name: 'Burn Coverage', type: 'line', color: '#79c8ee', area: true, valueFormat: 'percent', data: rows.map((row: any) => [row.period ?? row.date, row.burn_coverage_pct]) }] }]
})))
const contractRewardsChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = burnRows(period)
  return [period, {
    NEAR: [{ name: 'Contract rewards', type: 'bar', color: '#f5c978', data: rows.map((row: any) => [row.period ?? row.date, row.contract_rewards_near]) }],
    USD: [{ name: 'Contract rewards', type: 'bar', color: '#f5c978', data: rows.map((row: any) => [row.period ?? row.date, row.contract_rewards_usd]) }],
  }]
})))
const buybackPalette = ['#79c8ee', '#b4f273', '#f5c978', '#c3a5ff', '#ff9f6e', '#7bd6c1']
const buybackChart = computed(() => Object.fromEntries(periods.map((period) => {
  const rows = data.value?.[`tokenomics/${period}_buyback_transfers.json`]?.observations ?? []
  const types = [...new Set(rows.map((row: any) => row.transfer_type).filter((type: any) => typeof type === 'string'))].sort()
  return [period, { NEAR: types.map((type, index) => ({
    name: formatIdentifierLabel(type), type: 'bar', color: buybackPalette[index % buybackPalette.length], stack: 'buybacks',
    data: rows.filter((row: any) => row.transfer_type === type).map((row: any) => [row.period ?? row.date, Number(row.total_inflow_near)]),
  })) }]
})))
const inflationChart = computed(() => ({
  daily: { NEAR: [{ name: 'Trailing 30D annualized net inflation', type: 'line' as const, color: '#b4f273', area: true,
    valueFormat: 'percent' as const, data: tokenomicsRows('daily').map((row: any) => [row.date, row.net_inflation_30d_annualized_pct]) }] },
}))
function formatRate(value: number | string | null | undefined) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? `${amount.toFixed(2)}%` : '—'
}
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="2" :charts="2" />
  <DataLoadError v-else-if="error" title="Tokenomics data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading title="Tokenomics" description="NEAR price, supply, and market indicators." :updated-at="snapshot?.updated_at" />
    <div class="section-title-row tokenomics-section-title"><div><h2>Market capitalization</h2><p>Spot market capitalization · USD</p></div></div>
    <div class="metric-grid tokenomics-overview-metrics">
      <MetricCard label="Market cap" :value="formatCurrency(snapshot?.metrics?.market_cap, 'USD', 3)" :icon="ChartNoAxesCombined" tone="green" :change-label="''" />
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
    <div class="section-title-row tokenomics-section-title"><div><h2>Staking &amp; validators</h2><p>Active network stake, validator concentration, and production</p></div></div>
    <div class="metric-grid validator-metric-grid">
      <MetricCard label="Total active stake" :value="`${formatCompact(snapshot?.metrics?.total_active_stake, 2)} NEAR`" :detail="`As of ${snapshot?.metrics?.total_active_stake_as_of_date ?? '—'}`" :icon="WalletCards" tone="green" :change-label="''" :methodology="methodologies?.tokenomics?.staking" />
      <MetricCard label="Staking ratio · circulating supply" :value="formatRate(snapshot?.metrics?.staking_ratio)" :icon="ChartNoAxesCombined" tone="blue" :change-label="''" :methodology="methodologies?.tokenomics?.staking" />
      <MetricCard label="Active validators" :value="formatCompact(snapshot?.metrics?.active_validators_count, 0)" :icon="UsersRound" tone="violet" :change-label="''" :methodology="methodologies?.tokenomics?.validators" />
      <MetricCard label="Top 10 stake share" :value="formatRate(snapshot?.metrics?.top_10_stake_share)" :icon="ChartNoAxesCombined" tone="amber" :change-label="''" :methodology="methodologies?.tokenomics?.validators" />
    </div>
    <LineChart class="tokenomics-active-stake-chart" title="Active validator stake and share of total supply" subtitle="Stake in NEAR and active stake as a percentage of total supply · period-end snapshots" :datasets="historicalActiveStakeChart" initial-period="daily" :height="320" :methodology="methodologies?.tokenomics?.historical_active_stake" />
    <ValidatorTable :items="snapshot?.validators?.items ?? []" />
    <div class="section-title-row tokenomics-section-title"><div><h2>NEAR Intents buybacks</h2><p>Daily transfers into the buyback multisig, grouped by transfer source · NEAR</p></div></div>
    <div class="overview-grid tokenomics-metric-chart-layout">
      <AnalyticsChart title="Buyback transfers by source" subtitle="Inflows in NEAR" :datasets="buybackChart" initial-period="daily" :height="340" :methodology="methodologies?.tokenomics?.buybacks" />
      <div class="tokenomics-buyback-side">
        <AnalyticsChart title="Buyback flow breakdown" subtitle="Cumulative inflow by transfer type · NEAR" :datasets="buybackPie" :height="260" :methodology="methodologies?.tokenomics?.buybacks" />
        <div class="metric-grid tokenomics-chart-metrics">
          <MetricCard label="Buyback wallet · liquid balance" :value="`${formatCompact(snapshot?.metrics?.buyback_wallet_balance_near, 2)} NEAR`" :detail="`As of ${snapshot?.metrics?.buyback_wallet_balance_date ?? '—'}`" :icon="WalletCards" tone="green" :change-label="''" mobile-body-align="left" body-align="center" :methodology="methodologies?.tokenomics?.buybacks" />
        </div>
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
    <LineChart title="Net and gross issuance" subtitle="Starts where burn data is available · daily flows summed within each calendar period" :datasets="supplyDynamicsChart" initial-period="daily" :height="360" :methodology="methodologies?.tokenomics?.supply_dynamics" />
    <div class="section-title-row tokenomics-section-title"><div><h2>Burn &amp; contract rewards</h2><p>Compare contract rewards with fee burn and its offset against gross issuance</p></div></div>
    <div class="tokenomics-burn-charts">
      <LineChart title="Contract rewards" subtitle="Rewards by calendar period · NEAR or USD" :datasets="contractRewardsChart" initial-period="daily" initial-currency="NEAR" :height="320" :methodology="methodologies?.tokenomics?.contract_rewards" />
      <div class="tokenomics-burn-chart-grid">
        <LineChart title="Net burn" subtitle="Tokens burnt less contract rewards · NEAR or USD" :datasets="burnChart" initial-period="daily" initial-currency="NEAR" :height="330" :methodology="methodologies?.tokenomics?.net_burn" />
        <LineChart title="Burn Coverage" subtitle="Share of estimated gross issuance offset by net fee burn · %" :datasets="burnCoverageChart" initial-period="daily" :height="330" :methodology="methodologies?.tokenomics?.burn_coverage" />
      </div>
      <div class="metric-grid tokenomics-burn-metrics">
        <MetricCard label="Net burn · latest day" :value="`${formatCompact(snapshot?.metrics?.latest_net_burn_near, 2)} NEAR`" :detail="snapshot?.metrics?.latest_net_burn_date ?? '—'" :icon="Flame" tone="amber" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" />
        <MetricCard label="Burn Coverage · latest day" :value="formatPercent(snapshot?.metrics?.latest_burn_coverage_pct)" :detail="snapshot?.metrics?.latest_burn_coverage_date ?? '—'" :icon="TrendingUp" tone="violet" :change-label="''" body-align="center" value-size="large" mobile-body-align="left" :methodology="methodologies?.tokenomics?.burn_coverage" />
      </div>
    </div>
  </template>
</template>
