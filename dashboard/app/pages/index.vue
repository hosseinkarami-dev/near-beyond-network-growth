<script setup lang="ts">
import { Activity, ArrowRight, ChartNoAxesCombined, CircleDollarSign, Coins, Layers3, Shield, TrendingUp, UsersRound, Wallet, Zap } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCompact, formatCurrency, formatPercent, makeSeries } from '~/composables/useAnalytics'

const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string
const paths = [
  'dashboard.json', 'network/snapshot.json', 'network/daily_metrics.json', 'network/stablecoin_supply.json',
  'near_intents/monthly_metrics.json', 'protocols/dex_volume/monthly_metrics.json',
  'tokenomics/snapshot.json', 'tokenomics/daily_near_price.json',
  'tokenomics/daily_supply.json', 'tokenomics/daily_tokenomics.json', 'tokenomics/daily_issuance.json', 'tokenomics/daily_burn.json',
  'tokenomics/daily_buyback_transfers.json', 'near_intents/snapshot.json', 'near_intents/daily_metrics.json',
  'protocols/revenue/snapshot.json', 'protocols/revenue/daily_metrics.json',
]
const { data, pending, error, refresh } = await useAsyncData('dashboard-investment-thesis-overview', async () => {
  const docs = await Promise.all(paths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })

const doc = (path: string) => data.value?.[path]
const tokenomics = computed(() => doc('tokenomics/snapshot.json'))
const intents = computed(() => doc('near_intents/snapshot.json'))
const protocolRevenue = computed(() => doc('protocols/revenue/snapshot.json')?.summary)
const network = computed(() => doc('network/snapshot.json'))
const networkRows = computed(() => doc('network/daily_metrics.json')?.observations ?? [])
const stablecoinRows = computed(() => doc('network/stablecoin_supply.json')?.observations ?? [])
const intentsMonthlyRows = computed(() => doc('near_intents/monthly_metrics.json')?.items ?? [])
const dexMonthlyRows = computed(() => doc('protocols/dex_volume/monthly_metrics.json')?.items ?? [])
const intentRows = computed(() => doc('near_intents/daily_metrics.json')?.items ?? [])
const revenueRows = computed(() => doc('protocols/revenue/daily_metrics.json')?.items ?? [])
const issuanceRows = computed(() => doc('tokenomics/daily_issuance.json')?.items ?? [])
const priceRows = computed(() => doc('tokenomics/daily_near_price.json')?.observations ?? [])
const supplyRows = computed(() => doc('tokenomics/daily_supply.json')?.items ?? [])
const buybackRows = computed(() => doc('tokenomics/daily_buyback_transfers.json')?.observations ?? [])
const methods = computed(() => doc('dashboard.json')?.methodologies)
const latestSupply = computed(() => supplyRows.value.at(-1))
const number = (value: unknown) => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value)
const pct = (value: unknown) => value == null ? '—' : formatPercent(value as number | string)
const rate = (value: unknown) => {
  const amount = number(value)
  return amount == null ? '—' : `${amount.toFixed(2)}%`
}

const economicChart = computed(() => ({ daily: { USD: [
  { name: 'NEAR Intents volume', type: 'line' as const, color: '#b4f273', area: true, data: intentRows.value.map((row: any) => [row.date, number(row.volume_usd)]) },
  { name: 'NEAR Intents revenue', type: 'line' as const, color: '#c3a5ff', yAxisIndex: 1, data: intentRows.value.map((row: any) => [row.date, number(row.revenue_usd)]) },
  { name: 'NEAR ecosystem revenue', type: 'line' as const, color: '#79c8ee', yAxisIndex: 1, data: revenueRows.value.map((row: any) => [row.date, number(row.revenue_usd)]) },
] } }))
const captureChart = computed(() => makeSeries({ daily: { items: intentRows.value } }, [
  { key: 'revenue_capture_rate_30d_pct', label: '30-day revenue capture rate', type: 'line', color: '#c3a5ff', valueFormat: 'percent' },
]))
const issuanceChart = computed(() => ({ daily: { NEAR: [
  { name: 'Estimated gross issuance', type: 'line' as const, color: '#f5c978', data: issuanceRows.value.map((row: any) => [row.date, number(row.gross_issuance_near)]) },
  { name: 'Net fee burn', type: 'line' as const, color: '#79c8ee', data: issuanceRows.value.map((row: any) => [row.date, number(row.net_burn_near)]) },
] } }))
const inflationChart = computed(() => ({ daily: { Percent: [
  { name: 'Annualized net inflation · 30D', type: 'line' as const, color: '#ff9f6e', valueFormat: 'percent' as const, data: (doc('tokenomics/daily_tokenomics.json')?.items ?? []).map((row: any) => [row.date, number(row.net_inflation_30d_annualized_pct)]) },
] } }))
const buybackPalette = ['#b4f273', '#79c8ee', '#c3a5ff', '#f5c978', '#ff9f6e', '#7bd6c1']
const buybackChart = computed(() => {
  const types = [...new Set(buybackRows.value.map((row: any) => row.transfer_type).filter((type: any) => typeof type === 'string'))].sort()
  return { daily: { NEAR: types.map((type, index) => ({
    name: type, type: 'bar' as const, color: buybackPalette[index % buybackPalette.length],
    stack: 'buyback-inflow',
    data: buybackRows.value.filter((row: any) => row.transfer_type === type).map((row: any) => [row.date, number(row.total_inflow_near)]),
  })) } }
})
const priceChart = computed(() => ({ daily: { USD: [
  { name: 'NEAR price', type: 'line' as const, color: '#b4f273', area: true, data: priceRows.value.map((row: any) => [row.date, number(row.near_price)]) },
  { name: '7-day average', type: 'line' as const, color: '#79c8ee', data: priceRows.value.map((row: any) => [row.date, number(row.moving_average_7d)]) },
  { name: '30-day average', type: 'line' as const, color: '#c3a5ff', data: priceRows.value.map((row: any) => [row.date, number(row.moving_average_30d)]) },
] } }))
const supplyChart = computed(() => ({ daily: { NEAR: [
  { name: 'Total supply', type: 'line' as const, color: '#f5c978', area: true, data: supplyRows.value.map((row: any) => [row.date, number(row.total_supply)]) },
  { name: 'Circulating supply', type: 'line' as const, color: '#b4f273', data: supplyRows.value.map((row: any) => [row.date, number(row.circulating_supply)]) },
] } }))
const ecosystemTvlChart = computed(() => ({ daily: { USD: [
  { name: 'Network TVL', type: 'line' as const, color: '#79c8ee', area: true, data: networkRows.value.map((row: any) => [row.date, number(row.tvl_usd)]) },
  { name: 'NEAR Intents TVL', type: 'line' as const, color: '#b4f273', data: intentRows.value.map((row: any) => [row.date, number(row.tvl_usd)]) },
] } }))
const ecosystemVolumeChart = computed(() => ({ monthly: { USD: [
  { name: 'Protocol DEX volume', type: 'bar' as const, color: '#79c8ee', data: dexMonthlyRows.value.map((row: any) => [row.period, number(row.value_usd)]) },
  { name: 'NEAR Intents volume', type: 'line' as const, color: '#b4f273', yAxisIndex: 1, data: intentsMonthlyRows.value.map((row: any) => [row.period, number(row.volume_usd)]) },
] } }))
const networkActivityChart = computed(() => ({ daily: { Counts: [
  { name: 'Transactions', type: 'bar' as const, color: '#b4f273', data: networkRows.value.map((row: any) => [row.date, number(row.transactions)]) },
  { name: 'Active accounts', type: 'line' as const, color: '#79c8ee', yAxisIndex: 1, data: networkRows.value.map((row: any) => [row.date, number(row.active_accounts)]) },
] } }))
const stablecoinChart = computed(() => ({ daily: { USD: [{
  name: 'Stablecoin circulating supply', type: 'line' as const, color: '#c3a5ff', area: true,
  data: stablecoinRows.value.map((row: any) => [row.date, number(row.total_circulating_usd)]),
}] } }))
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="6" :charts="4" />
  <DataLoadError v-else-if="error" title="Dashboard data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading eyebrow="BEYOND NETWORK GROWTH" title="NEAR Investment Thesis" description="Does NEAR’s ecosystem growth translate into durable economic value and meaningful value capture?" :updated-at="doc('dashboard.json')?.latest_data_update" />

    <section class="dashboard-thesis-section overview-thesis-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Investment indicators</h2><p>Core indicators of valuation, value capture, supply expansion, and participation.</p></div></div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-six">
        <MetricCard label="Market cap" :value="formatCurrency(tokenomics?.metrics?.market_cap, 'USD', 2)" :change-label="''" :icon="ChartNoAxesCombined" tone="violet" />
        <MetricCard label="NEAR price" :value="formatCurrency(tokenomics?.metrics?.near_price?.value, 'USD', 3)" :change="pct(tokenomics?.metrics?.change_24h)" change-label="24h" :icon="CircleDollarSign" tone="green" />
        <MetricCard label="Annualized net inflation · 30D" :value="rate(tokenomics?.metrics?.net_inflation_30d_annualized_pct)" :change-label="''" :icon="Activity" tone="amber" :methodology="methods?.tokenomics?.net_inflation" />
        <MetricCard label="Burn coverage · 30D" :value="rate(tokenomics?.metrics?.burn_offset_30d_pct)" :change-label="''" :icon="Coins" tone="blue" :methodology="methods?.tokenomics?.burn_coverage" />
        <MetricCard label="Staking ratio" :value="rate(tokenomics?.metrics?.staking_ratio)" detail="of circulating supply" :change-label="''" :icon="Shield" tone="green" :methodology="methods?.tokenomics?.staking" />
        <MetricCard label="NEAR Intents volume · 30D" :value="formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1)" :change-label="''" :icon="Layers3" tone="violet" :methodology="methods?.near_intents?.volume" />
      </div>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Economic value vs. supply expansion</h2><p>Compare ecosystem activity and reported revenue with issuance, fee burn, and net inflation.</p></div><NuxtLink to="/intents" class="panel-link">Intents analysis <ArrowRight :size="13" /></NuxtLink></div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-economic">
        <MetricCard label="NEAR ecosystem revenue · 30D" :value="formatCurrency(protocolRevenue?.total_30d, 'USD', 1, 1)" :change-label="''" :icon="ChartNoAxesCombined" tone="blue" />
        <MetricCard label="NEAR Intents revenue · 30D" :value="formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 1, 1)" :change-label="''" :icon="Coins" tone="violet" />
        <MetricCard label="NEAR Intents revenue capture · 30D" :value="rate(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value)" :detail="`As of ${intents?.key_metrics?.revenue_capture_rate_30d_pct?.date ?? '—'}`" :change-label="''" :icon="Activity" tone="green" :methodology="methods?.near_intents?.revenue_capture_rate_30d" />
        <MetricCard label="Estimated gross issuance · 30D" :value="`${formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2)} NEAR`" :change-label="''" :icon="TrendingUp" tone="amber" :methodology="methods?.tokenomics?.supply_dynamics" />
        <MetricCard label="Net fee burn · 30D" :value="`${formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2)} NEAR`" :change-label="''" :icon="Coins" tone="blue" :methodology="methods?.tokenomics?.net_burn" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="Activity and reported revenue" subtitle="NEAR Intents volume and NEAR ecosystem revenue · USD · dual scale" :datasets="economicChart" initial-period="daily" :height="280" :methodology="[methods?.near_intents?.volume, methods?.near_intents?.revenue].filter(Boolean)" />
        <AnalyticsChart title="Revenue capture rate" subtitle="Trailing 30-day NEAR Intents revenue relative to gross fees" :datasets="captureChart" initial-period="daily" :height="280" :methodology="methods?.near_intents?.revenue_capture_rate_30d" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="Issuance and net fee burn" subtitle="Daily flows · NEAR · last 180 days" :datasets="issuanceChart" initial-period="daily" :height="260" :methodology="[methods?.tokenomics?.supply_dynamics, methods?.tokenomics?.net_burn].filter(Boolean)" />
        <AnalyticsChart title="Annualized net inflation" subtitle="Trailing 30-day total supply growth, annualized" :datasets="inflationChart" initial-period="daily" :height="260" :methodology="methods?.tokenomics?.net_inflation" />
      </div>
      <p class="dashboard-source-note">NEAR chain &amp; app revenue covers DefiLlama's tracked chain and protocol listings. It includes the NEAR Intents entry, so it overlaps with the Intents-specific revenue card and should not be added to it. Gross issuance is estimated from net supply change plus net fee burn; net inflation is derived from total-supply snapshots and includes burn effects.</p>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Buyback wallet inflows</h2><p>Observed deposits grouped by attributed source and transfer type.</p></div><NuxtLink to="/tokenomics" class="panel-link">Tokenomics details <ArrowRight :size="13" /></NuxtLink></div>
      <div class="overview-grid buyback-overview-grid">
        <AnalyticsChart title="Daily wallet inflows by source" subtitle="NEAR inflows grouped by attributed source · stacked · last 180 days" :datasets="buybackChart" initial-period="daily" :height="275" :methodology="methods?.tokenomics?.buybacks" />
        <MetricCard label="Buyback wallet · liquid balance" :value="`${formatCompact(tokenomics?.metrics?.buyback_wallet_balance_near, 2)} NEAR`" :detail="`As of ${tokenomics?.metrics?.buyback_wallet_balance_date ?? 'date unavailable'}`" :change-label="''" :icon="Wallet" tone="green" value-size="large" body-align="center" mobile-body-align="center" :methodology="methods?.tokenomics?.buybacks" />
      </div>
      <p class="dashboard-source-note">Wallet inflows show funds transferred to the multisig. They do not verify whether or when NEAR was purchased, executed, or burned.</p>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Network security</h2><p>Active economic security and the current validator stake distribution.</p></div><NuxtLink to="/tokenomics" class="panel-link">Validator analysis <ArrowRight :size="13" /></NuxtLink></div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-four">
        <MetricCard label="Total active stake" :value="`${formatCompact(tokenomics?.metrics?.total_active_stake, 2)} NEAR`" :change-label="''" :icon="Wallet" tone="green" />
        <MetricCard label="Staking ratio · circulating supply" :value="rate(tokenomics?.metrics?.staking_ratio)" :change-label="''" :icon="Shield" tone="blue" />
        <MetricCard label="Active validators" :value="formatCompact(tokenomics?.metrics?.active_validators_count, 0)" :detail="`of ${formatCompact(tokenomics?.metrics?.total_validators_count, 0)} registered`" :icon="Activity" tone="amber" />
        <MetricCard label="Top 10 stake share" :value="rate(tokenomics?.metrics?.top_10_stake_share)" :change-label="''" :icon="Coins" tone="violet" />
      </div>
      <p class="dashboard-source-note">Current validator metrics are a point-in-time NearBlocks snapshot. Historical active stake uses sampled daily RPC observations and is available in Tokenomics.</p>
    </section>

    <section class="dashboard-thesis-section dashboard-context-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Ecosystem activity &amp; liquidity</h2><p>Context for adoption and capital flows, alongside the core economic indicators above.</p></div><NuxtLink to="/network" class="panel-link">Network details <ArrowRight :size="13" /></NuxtLink></div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-six">
        <MetricCard label="Transactions · 24h" :value="formatCompact(network?.key_metrics?.transactions?.value, 1, 1)" :change="pct(network?.key_metrics?.transactions?.change_24h_pct)" change-label="vs previous 24h" :icon="Activity" tone="green" />
        <MetricCard label="Active accounts" :value="formatCompact(network?.key_metrics?.active_accounts?.value)" :change="pct(network?.key_metrics?.active_accounts?.change_24h_pct)" change-label="vs previous 24h" :icon="UsersRound" tone="blue" />
        <MetricCard label="Network throughput" :value="formatCompact(network?.network_stats?.tps)" detail="Transactions per second" :change-label="''" :icon="Zap" tone="amber" />
        <MetricCard label="Stablecoin supply" :value="formatCurrency(network?.key_metrics?.stablecoin_supply_usd?.value, 'USD', 1)" :change="pct(network?.key_metrics?.stablecoin_supply_usd?.change_30d_pct)" change-label="30D change" :icon="Coins" tone="violet" />
        <MetricCard label="Network TVL" :value="formatCurrency(network?.key_metrics?.tvl_usd?.value, 'USD', 1)" :change="pct(network?.key_metrics?.tvl_usd?.change_30d_pct)" change-label="30D change" :icon="Layers3" tone="blue" />
        <MetricCard label="NEAR Intents TVL" :value="formatCurrency(intents?.key_metrics?.tvl_usd?.value, 'USD', 1)" :detail="`As of ${intents?.key_metrics?.tvl_usd?.date ?? '—'}`" :change-label="''" :icon="Layers3" tone="green" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="Network TVL vs. NEAR Intents TVL" subtitle="Reported liquidity snapshots · USD · last 180 days" :datasets="ecosystemTvlChart" initial-period="daily" :height="250" />
        <AnalyticsChart title="Stablecoin supply" subtitle="Circulating stablecoin value · USD · last 180 days" :datasets="stablecoinChart" initial-period="daily" :height="250" :methodology="methods?.network?.stablecoin_supply" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="Monthly swap volume" subtitle="Protocol DEX volume and NEAR Intents volume · USD" :datasets="ecosystemVolumeChart" initial-period="monthly" :height="250" />
        <AnalyticsChart title="Network activity" subtitle="Transactions and active accounts · last 180 days" :datasets="networkActivityChart" initial-period="daily" :height="250" />
      </div>
      <p class="dashboard-source-note">TVL series are point-in-time reported values and are not additive. DEX volume and Intents volume may overlap. Monthly values are Analytics period outputs; the current month is partial.</p>
    </section>

    <section class="dashboard-thesis-section dashboard-market-section">
      <div class="section-title-row dashboard-section-title"><div><h2>Market &amp; supply context</h2><p>Price performance and supply history · secondary to the core thesis indicators.</p></div></div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-two dashboard-market-metrics">
        <MetricCard label="Market cap" :value="formatCurrency(tokenomics?.metrics?.market_cap, 'USD', 2)" :change-label="''" :icon="ChartNoAxesCombined" tone="violet" />
        <MetricCard label="Circulating supply" :value="`${formatCompact(tokenomics?.metrics?.circulating_supply)} NEAR`" :detail="`Total ${formatCompact(tokenomics?.metrics?.total_supply)} NEAR`" :icon="Coins" tone="blue" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="NEAR price" subtitle="Daily close and 7-day / 30-day averages · USD" :datasets="priceChart" initial-period="daily" :height="245" :methodology="methods?.tokenomics?.near_price" />
        <AnalyticsChart title="NEAR supply" subtitle="Period-end total and circulating supply · NEAR" :datasets="supplyChart" initial-period="daily" :height="245" :methodology="methods?.tokenomics?.supply" />
      </div>
    </section>
  </template>
</template>
