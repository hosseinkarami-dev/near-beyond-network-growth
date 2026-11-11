<script setup lang="ts">
import {
  Activity, ArrowRight, ChartNoAxesCombined, CircleDollarSign, Coins,
  Layers3, TrendingUp, UsersRound, Wallet, Zap,
} from '@lucide/vue'
import { formatCompact, formatCurrency, formatPercent, makeSeries } from '~/composables/useAnalytics'

const { data, pending, error, refresh } = await useAsyncData('dashboard-investment-thesis', async () => {
  const paths = [
    'dashboard.json',
    'network/snapshot.json', 'network/daily_metrics.json', 'network/stablecoin_supply.json',
    'near_intents/snapshot.json', 'near_intents/daily_metrics.json', 'near_intents/monthly_metrics.json',
    'tokenomics/snapshot.json', 'tokenomics/daily_near_price.json', 'tokenomics/daily_supply.json',
    'protocols/revenue/snapshot.json', 'protocols/dex_volume/snapshot.json', 'protocols/dex_volume/monthly_metrics.json',
  ]
  const docs = await Promise.all(paths.map((path) => $fetch<any>(`/data/analytics/${path}`)))
  return Object.fromEntries(paths.map((path, index) => [path, docs[index]]))
}, { server: false })

const network = computed(() => data.value?.['network/snapshot.json'])
const networkRows = computed(() => (data.value?.['network/daily_metrics.json']?.observations ?? []).slice(-365))
const stablecoinRows = computed(() => (data.value?.['network/stablecoin_supply.json']?.observations ?? []).slice(-365))
const intents = computed(() => data.value?.['near_intents/snapshot.json'])
const intentRows = computed(() => (data.value?.['near_intents/daily_metrics.json']?.items ?? []).slice(-365))
const latestIntent = computed(() => intentRows.value.at(-1))
const tokenomics = computed(() => data.value?.['tokenomics/snapshot.json'])
const priceRows = computed(() => (data.value?.['tokenomics/daily_near_price.json']?.observations ?? []).slice(-365))
const supplyRows = computed(() => (data.value?.['tokenomics/daily_supply.json']?.items ?? []).slice(-365))
const latestSupply = computed(() => supplyRows.value.at(-1))
const protocolRevenue = computed(() => data.value?.['protocols/revenue/snapshot.json']?.summary)
const dexVolume = computed(() => data.value?.['protocols/dex_volume/snapshot.json']?.summary)
const dexMonthlyRows = computed(() => data.value?.['protocols/dex_volume/monthly_metrics.json']?.items ?? [])
const intentMonthlyRows = computed(() => data.value?.['near_intents/monthly_metrics.json']?.items ?? [])
const stablecoin = computed(() => network.value?.key_metrics?.stablecoin_supply_usd)
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
const latestDataUpdate = computed(() => data.value?.['dashboard.json']?.latest_data_update)
const optionalPercent = (value: number | string | null | undefined) => value == null ? null : formatPercent(value)
const stablecoinDetail = computed(() => {
  if (!stablecoin.value) return 'No valid supply observation'
  return `As of ${stablecoin.value.date} · 30D ${optionalPercent(stablecoin.value.change_30d_pct) ?? '—'} · 90D ${optionalPercent(stablecoin.value.change_90d_pct) ?? '—'}`
})

const activityChart = computed(() => makeSeries({ daily: { observations: networkRows.value } }, [
  { key: 'transactions', label: 'Transactions', type: 'bar', color: '#b4f273' },
  { key: 'active_accounts', label: 'Active accounts', type: 'line', color: '#79c8ee', axis: 1 },
]))
const stablecoinChart = computed(() => ({
  daily: { USD: [{
    name: 'Circulating stablecoin supply · USD', type: 'line' as const,
    color: '#79c8ee', area: true,
    data: stablecoinRows.value.map((row: any) => [row.date, row.total_circulating_usd == null ? null : Number(row.total_circulating_usd)]),
  }] },
}))
const priceChart = computed(() => ({
  daily: { USD: [
    { name: 'NEAR price', type: 'line' as const, color: '#b4f273', area: true, data: priceRows.value.map((row: any) => [row.date, row.near_price == null ? null : Number(row.near_price)]) },
    { name: '7-day average', type: 'line' as const, color: '#79c8ee', data: priceRows.value.map((row: any) => [row.date, row.moving_average_7d == null ? null : Number(row.moving_average_7d)]) },
    { name: '30-day average', type: 'line' as const, color: '#c3a5ff', data: priceRows.value.map((row: any) => [row.date, row.moving_average_30d == null ? null : Number(row.moving_average_30d)]) },
  ] },
}))
const supplyChart = computed(() => ({
  daily: { NEAR: [
    { name: 'Total supply', type: 'line' as const, color: '#f5c978', area: true, data: supplyRows.value.map((row: any) => [row.date, row.total_supply == null ? null : Number(row.total_supply)]) },
    { name: 'Circulating supply', type: 'line' as const, color: '#b4f273', data: supplyRows.value.map((row: any) => [row.date, row.circulating_supply == null ? null : Number(row.circulating_supply)]) },
  ] },
}))
const valueCaptureChart = computed(() => makeSeries({ daily: { items: intentRows.value } }, [
  { key: 'gross_fees_usd', label: 'Gross Fees', type: 'line', color: '#ff9f6e' },
  { key: 'revenue_usd', label: 'Revenue', type: 'line', color: '#f5c978' },
  { key: 'holders_revenue_usd', label: 'Holders revenue', type: 'line', color: '#c3a5ff' },
  { key: 'revenue_capture_rate_30d_pct', label: '30-Day Revenue Capture Rate', type: 'line', color: '#79c8ee', axis: 1, valueFormat: 'percent' },
]))
const ecosystemTvlChart = computed(() => ({
  daily: { USD: [
    { name: 'Network TVL', type: 'line' as const, color: '#79c8ee', area: true, data: networkRows.value.map((row: any) => [row.date, row.tvl_usd == null ? null : Number(row.tvl_usd)]) },
    { name: 'NEAR Intents TVL', type: 'line' as const, color: '#b4f273', data: intentRows.value.map((row: any) => [row.date, row.tvl_usd == null ? null : Number(row.tvl_usd)]) },
  ] },
}))
const ecosystemVolumeChart = computed(() => ({
  monthly: { USD: [
    { name: 'Protocol DEX volume', type: 'bar' as const, color: '#79c8ee', data: dexMonthlyRows.value.map((row: any) => [row.period, row.value_usd == null ? null : Number(row.value_usd)]) },
    { name: 'NEAR Intents volume', type: 'line' as const, color: '#b4f273', data: intentMonthlyRows.value.map((row: any) => [row.period, row.volume_usd == null ? null : Number(row.volume_usd)]) },
  ] },
}))
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="4" :charts="4" />
  <DataLoadError v-else-if="error" title="Dashboard data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading
      eyebrow="NEAR INVESTMENT THESIS"
      title="NEAR, in context"
      description="A research view of network adoption, token economics, value capture, and ecosystem activity."
      :updated-at="latestDataUpdate"
    />

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title">
        <div><h2>Network activity &amp; adoption</h2><p>Are on-chain usage and stablecoin liquidity growing?</p></div>
        <NuxtLink to="/network" class="panel-link">Explore Network <ArrowRight :size="13" /></NuxtLink>
      </div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-four">
        <MetricCard label="Transactions · 24h" :value="formatCompact(network?.key_metrics?.transactions?.value)" :change="optionalPercent(network?.key_metrics?.transactions?.change_24h_pct)" :change-label="network?.key_metrics?.transactions?.change_24h_pct == null ? '' : 'vs previous 24h'" :icon="Activity" tone="green" />
        <MetricCard label="Active accounts" :value="formatCompact(network?.key_metrics?.active_accounts?.value)" :change="optionalPercent(network?.key_metrics?.active_accounts?.change_24h_pct)" :change-label="network?.key_metrics?.active_accounts?.change_24h_pct == null ? '' : 'vs previous 24h'" :icon="UsersRound" tone="blue" />
        <MetricCard label="Network throughput" :value="formatCompact(network?.network_stats?.tps)" detail="Transactions per second" :change-label="''" :icon="Zap" tone="amber" />
        <MetricCard label="Stablecoin supply" :value="formatCurrency(stablecoin?.value, 'USD', 1)" :detail="stablecoinDetail" :change-label="''" :icon="Coins" tone="violet" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="Network activity" subtitle="Transactions and active accounts · last 365 observations" :datasets="activityChart" initial-period="daily" :height="250" />
        <AnalyticsChart title="Stablecoin supply" subtitle="Circulating value · USD · last 365 observations" :datasets="stablecoinChart" initial-period="daily" :height="250" :methodology="methodologies?.network?.stablecoin_supply" />
      </div>
      <p class="dashboard-source-note">Sources: Network analytics (NearBlocks) and stablecoin supply analytics (DefiLlama). Stablecoin 30D/90D comparisons use the Analytics snapshot as provided.</p>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title">
        <div><h2>Token economics</h2><p>What do current price, supply, and valuation data show?</p></div>
        <NuxtLink to="/tokenomics" class="panel-link">Explore Tokenomics <ArrowRight :size="13" /></NuxtLink>
      </div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-four">
        <MetricCard label="NEAR price" :value="formatCurrency(tokenomics?.metrics?.near_price?.value, 'USD', 3)" :change="optionalPercent(tokenomics?.metrics?.change_24h)" :icon="CircleDollarSign" tone="green" />
        <MetricCard label="Circulating supply" :value="`${formatCompact(tokenomics?.metrics?.circulating_supply)} NEAR`" :detail="`Total supply: ${formatCompact(tokenomics?.metrics?.total_supply)} NEAR · as of ${latestSupply?.date ?? '—'}`" :change-label="''" :icon="Wallet" tone="blue" />
        <MetricCard label="Market cap" :value="formatCurrency(tokenomics?.metrics?.market_cap, 'USD', 3)" :change-label="''" :icon="ChartNoAxesCombined" tone="violet" />
        <MetricCard label="Fully diluted valuation" :value="formatCurrency(tokenomics?.metrics?.fdv_usd, 'USD', 3)" :change-label="''" :icon="TrendingUp" tone="amber" :methodology="methodologies?.tokenomics?.fdv" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="NEAR price" subtitle="Daily close and 7-day / 30-day averages · USD" :datasets="priceChart" initial-period="daily" :height="250" :methodology="methodologies?.tokenomics?.near_price" />
        <AnalyticsChart title="NEAR supply" subtitle="Daily total and circulating supply · NEAR" :datasets="supplyChart" initial-period="daily" :height="250" :methodology="methodologies?.tokenomics?.supply" />
      </div>
      <p class="dashboard-source-note">Sources: Tokenomics snapshot, BigQuery supply history, and Binance NEARUSDT price data used by existing analytics. Historical supply snapshots are available; separate issuance, inflation, burn, and net supply change metrics are not currently exposed by Analytics.</p>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title">
        <div><h2>Revenue &amp; value capture</h2><p>Do network activity and Intents flows appear alongside fees, retained revenue, and holder allocation?</p></div>
        <nav class="dashboard-thesis-links" aria-label="Revenue analysis sections">
          <NuxtLink to="/network" class="panel-link">Network</NuxtLink>
          <NuxtLink to="/protocols" class="panel-link">Protocols</NuxtLink>
          <NuxtLink to="/intents" class="panel-link">Intents</NuxtLink>
        </nav>
      </div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-three">
        <MetricCard label="Network transaction fees · 24h" :value="formatCurrency(network?.key_metrics?.transaction_fees_usd?.value, 'USD', 2)" :change="optionalPercent(network?.key_metrics?.transaction_fees_usd?.change_24h_pct)" :change-label="network?.key_metrics?.transaction_fees_usd?.change_24h_pct == null ? '' : 'vs previous 24h'" :icon="CircleDollarSign" tone="blue" />
        <MetricCard label="Protocol revenue · 30d" :value="formatCurrency(protocolRevenue?.total_30d, 'USD', 1)" :change="optionalPercent(protocolRevenue?.growth_30d)" :change-label="protocolRevenue?.growth_30d == null ? '' : 'vs previous 30d'" :icon="ChartNoAxesCombined" tone="green" />
        <MetricCard label="NEAR Intents gross fees · 7d" :value="formatCurrency(intents?.key_metrics?.gross_fees_usd?.total_7d, 'USD', 1)" :change="optionalPercent(intents?.key_metrics?.gross_fees_usd?.change_7d_pct)" :change-label="intents?.key_metrics?.gross_fees_usd?.change_7d_pct == null ? '' : 'vs previous 7d'" :icon="Coins" tone="amber" />
        <MetricCard label="NEAR Intents revenue · 7d" :value="formatCurrency(intents?.key_metrics?.revenue_usd?.total_7d, 'USD', 1)" :change="optionalPercent(intents?.key_metrics?.revenue_usd?.change_7d_pct)" :change-label="intents?.key_metrics?.revenue_usd?.change_7d_pct == null ? '' : 'vs previous 7d'" :icon="TrendingUp" tone="green" />
        <MetricCard label="Revenue capture rate · 30d" :value="optionalPercent(latestIntent?.revenue_capture_rate_30d_pct) ?? '—'" :detail="latestIntent?.date ? `As of ${latestIntent.date}` : 'No valid observation'" :change-label="''" :icon="Activity" tone="blue" />
        <MetricCard label="Holders revenue · 7d" :value="formatCurrency(intents?.key_metrics?.holders_revenue_usd?.total_7d, 'USD', 1)" :change="optionalPercent(intents?.key_metrics?.holders_revenue_usd?.change_7d_pct)" :change-label="intents?.key_metrics?.holders_revenue_usd?.change_7d_pct == null ? '' : 'vs previous 7d'" :icon="UsersRound" tone="violet" />
      </div>
      <div class="overview-grid dashboard-chart-grid dashboard-wide-chart">
        <AnalyticsChart title="NEAR Intents value capture" subtitle="Gross Fees, Revenue, Holders revenue, and 30-day capture rate · USD" :datasets="valueCaptureChart" initial-period="daily" :height="285" :methodology="[methodologies?.near_intents?.gross_fees, methodologies?.near_intents?.revenue, methodologies?.near_intents?.holders_revenue, methodologies?.near_intents?.revenue_capture_rate_30d].filter(Boolean)" />
      </div>
      <p class="dashboard-source-note">Sources: Network analytics, DefiLlama protocol revenue, and NEAR Intents analytics. Holders revenue is an allocation of captured revenue; it is not additional revenue and should not be read as token burn.</p>
    </section>

    <section class="dashboard-thesis-section">
      <div class="section-title-row dashboard-section-title">
        <div><h2>Ecosystem growth</h2><p>Are liquidity and swap activity developing across the network?</p></div>
        <nav class="dashboard-thesis-links" aria-label="Ecosystem analysis sections">
          <NuxtLink to="/network" class="panel-link">Network</NuxtLink>
          <NuxtLink to="/intents" class="panel-link">Intents</NuxtLink>
          <NuxtLink to="/protocols" class="panel-link">Protocols</NuxtLink>
        </nav>
      </div>
      <div class="metric-grid dashboard-metrics dashboard-metrics-four">
        <MetricCard label="Network TVL" :value="formatCurrency(network?.key_metrics?.tvl_usd?.value, 'USD', 1)" :change="optionalPercent(network?.key_metrics?.tvl_usd?.change_24h_pct)" :change-label="network?.key_metrics?.tvl_usd?.change_24h_pct == null ? '' : 'vs previous 24h'" :icon="Layers3" tone="blue" />
        <MetricCard label="NEAR Intents TVL" :value="formatCurrency(intents?.key_metrics?.tvl_usd?.value ?? intents?.tvl_usd, 'USD', 1)" :detail="intents?.key_metrics?.tvl_usd?.date ? `As of ${intents.key_metrics.tvl_usd.date}` : 'Current snapshot'" :change-label="''" :icon="Layers3" tone="violet" />
        <MetricCard label="Protocol DEX volume · 24h" :value="formatCurrency(dexVolume?.total_24h, 'USD', 1)" :change="optionalPercent(dexVolume?.change_1d)" :change-label="dexVolume?.change_1d == null ? '' : 'vs previous 24h'" :icon="Activity" tone="green" />
        <MetricCard label="NEAR Intents volume · 24h" :value="formatCurrency(intents?.key_metrics?.volume_usd?.total_24h ?? intents?.volume?.total_24h, 'USD', 1)" :change="optionalPercent(intents?.key_metrics?.volume_usd?.change_24h_pct)" :change-label="intents?.key_metrics?.volume_usd?.change_24h_pct == null ? '' : 'vs previous 24h'" :icon="Zap" tone="amber" />
      </div>
      <div class="overview-grid dashboard-chart-grid">
        <AnalyticsChart title="TVL trends" subtitle="Network TVL and NEAR Intents TVL · USD" :datasets="ecosystemTvlChart" initial-period="daily" :height="250" />
        <AnalyticsChart title="Monthly swap volume trends" subtitle="Protocol DEX volume and NEAR Intents volume · USD" :datasets="ecosystemVolumeChart" initial-period="monthly" :height="250" :methodology="methodologies?.protocols?.dex_volume" />
      </div>
      <p class="dashboard-source-note">Sources: Network and NEAR Intents analytics, plus DefiLlama protocol volume. TVL and volume are separate reported measures, not additive totals; protocol DEX volume and Intents volume may overlap.</p>
    </section>
  </template>
</template>
