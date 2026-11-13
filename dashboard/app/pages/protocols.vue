<script setup lang="ts">
import { Activity, CalendarDays, Coins, Layers3, TrendingUp } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCurrency, formatPercent } from '~/composables/useAnalytics'
const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string

const periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const categories = [
  { id: 'fees', label: 'Fees', folder: 'fees', color: '#b4f273', metricField: 'fees_usd' },
  { id: 'revenue', label: 'Revenue', folder: 'revenue', color: '#c3a5ff', metricField: 'revenue_usd' },
  { id: 'dex_volume', label: 'DEX volume', folder: 'dex_volume', color: '#79c8ee', metricField: 'volume_usd' },
]
const selectedCategory = ref('fees')
const category = computed(() => categories.find((item) => item.id === selectedCategory.value) ?? categories[0]!)

const { data, pending, error, refresh } = await useAsyncData('protocol-analytics', async () => {
  const paths = categories.flatMap((item) => [
    `protocols/${item.folder}/snapshot.json`,
    `protocols/${item.folder}/daily_breakdown.json`,
    ...(item.id === 'fees' || item.id === 'dex_volume'
      ? [`protocols/${item.folder}/protocol_breakdown.json`]
      : []),
    ...periods.map((period) => `protocols/${item.folder}/${period}_breakdown.json`),
    ...periods.map((period) => `protocols/${item.folder}/${period}_metrics.json`),
  ])
  const allPaths = ['dashboard.json', ...paths]
  const docs = await Promise.all(allPaths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(allPaths.map((path, index) => [path, docs[index]]))
}, { server: false })

const snapshot = computed(() => data.value?.[`protocols/${category.value.folder}/snapshot.json`])
const summary = computed(() => snapshot.value?.summary ?? {})
const methodologies = computed(() => data.value?.['dashboard.json']?.methodologies)
const pieChart = computed(() => {
  const result: Record<string, Record<string, any[]>> = {}
  for (const period of ['all_time', 'daily', ...periods.filter((value) => value !== 'daily')]) {
    const docPeriod = period === 'all_time' ? 'daily' : period
    const doc = data.value?.[`protocols/${category.value.folder}/${docPeriod}_breakdown.json`]
    const usd = period === 'all_time' ? doc?.charts?.USD?.distribution : doc?.charts?.latest_USD?.distribution
    const near = period === 'all_time' ? doc?.charts?.NEAR?.distribution : doc?.charts?.latest_NEAR?.distribution
    result[period] = {
      USD: [{ name: category.value.label, type: 'pie', color: category.value.color, data: usd ?? [] }],
      NEAR: [{ name: category.value.label, type: 'pie', color: category.value.color, data: near ?? [] }],
    }
  }
  return result
})
const timeSeries = computed(() => {
  const result: Record<string, Record<string, any[]>> = {}
  for (const period of periods) {
    const rows = data.value?.[`protocols/${category.value.folder}/${period}_metrics.json`]?.items ?? []
    result[period] = Object.fromEntries((['USD', 'NEAR'] as const).map((currency) => {
      const field = currency === 'USD' ? 'value_usd' : 'value_near'
      return [currency, [{
        name: category.value.label,
        type: period === 'daily' ? 'line' : 'bar',
        color: category.value.color,
        area: period === 'daily',
        data: rows.map((row: any) => [row.period ?? row.date, row[field] == null ? null : Number(row[field])]),
      }]]
    }))
  }
  return result
})
const breakdownSeries = computed(() => {
  const colors = ['#b4f273', '#79c8ee', '#c3a5ff', '#f5c978', '#ff8e84', '#65d6b4']
  const result: Record<string, Record<string, any[]>> = {}
  for (const period of periods) {
    const chart = data.value?.[`protocols/${category.value.folder}/${period}_breakdown.json`]?.charts
    result[period] = Object.fromEntries((['USD', 'NEAR'] as const).map((currency) => {
      const prepared = chart?.[currency]
      const names = prepared?.protocols ?? []
      const rows = prepared?.items ?? []
      const series = names.map((name: string, index: number) => ({
        name, type: 'line' as const, color: colors[index]!,
        data: rows.map((row: any) => [row.period, row.protocols?.[name] ?? null]),
      }))
      series.push({ name: 'Other protocols', type: 'line', color: '#a7b0a2', data: rows.map((row: any) => [row.period, row.other]) })
      return [currency, series]
    }))
  }
  return result
})
const isDexVolume = computed(() => category.value.id === 'dex_volume')
const isRevenue = computed(() => category.value.id === 'revenue')
const summaryCards = computed(() => {
  const firstNumber = (...keys: string[]) => {
    for (const key of keys) {
      const value = summary.value[key]
      if (typeof value === 'number' && Number.isFinite(value)) return value
    }
    return undefined
  }
  if (isRevenue.value) {
    const growth = summary.value.growth_unit === 'percent' ? firstNumber('growth_30d') : undefined
    return [
      { key: 'total_30d', label: '30d Revenue', value: firstNumber('total_30d'), change: growth, changeLabel: 'vs. previous 30d' },
      { key: 'all_time', label: 'All-time Revenue', value: firstNumber('all_time'), change: undefined, changeLabel: '', detail: 'Since inception' },
    ].filter((item) => item.value !== undefined)
  }
  if (isDexVolume.value) {
    return [
      { key: 'total_24h', label: '24h Volume', value: firstNumber('total_24h'), change: firstNumber('change_1d'), changeLabel: 'vs. previous 24h' },
      { key: 'total_7d', label: '7d Volume', value: firstNumber('total_7d'), change: firstNumber('change_7dover7d'), changeLabel: 'vs. previous 7d' },
      { key: 'total_30d', label: '30d Volume', value: firstNumber('total_30d'), change: firstNumber('change_30dover30d'), changeLabel: 'vs. previous 30d' },
      { key: 'all_time', label: 'All-time Volume', value: firstNumber('total_all_time'), change: undefined, changeLabel: '', detail: 'Since inception' },
      { key: 'total_1y', label: '1Y Volume', value: firstNumber('total_1y'), change: undefined, changeLabel: '' },
    ]
  }
  return [
    { key: 'total_24h', label: '24h Fees', value: firstNumber('total_24h'), change: firstNumber('daily_growth'), changeLabel: 'Daily growth' },
    { key: 'total_7d', label: '7d Fees', value: firstNumber('total_7d'), change: firstNumber('weekly_growth'), changeLabel: 'Weekly growth' },
    { key: 'total_30d', label: '30d Fees', value: firstNumber('total_30d'), change: firstNumber('monthly_growth'), changeLabel: 'Monthly growth' },
    { key: 'all_time', label: 'All-time Fees', value: firstNumber('all_time'), change: undefined, changeLabel: '', detail: 'Since inception' },
  ].filter((item) => item.value !== undefined)
})
const overviewKeys = computed(() => isRevenue.value
  ? ['total_30d', 'all_time']
  : isDexVolume.value ? ['total_1y', 'all_time'] : ['total_30d', 'all_time'])
const overviewCards = computed(() => summaryCards.value.filter((item) => overviewKeys.value.includes(item.key)))
const trendCards = computed(() => summaryCards.value.filter((item) => !overviewKeys.value.includes(item.key)))
const selectedCategoryMethodology = computed(() => methodologies.value?.protocols?.[category.value.id === 'dex_volume' ? 'dex_volume' : category.value.id])

function currency(value: unknown) {
  return formatCurrency(value as number | string | null | undefined, 'USD', 0)
}

function volumeCurrency(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  const fractionDigits = Math.abs(amount) >= 1_000_000_000 ? 2 : Math.abs(amount) >= 1_000_000 ? 1 : 0
  return formatCurrency(amount, 'USD', fractionDigits)
}

function revenueCurrency(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? formatCurrency(amount, 'USD', 2) : '—'
}
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="2" :charts="3" />
  <DataLoadError v-else-if="error" title="Protocol data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading title="Protocols" description="Explore fees, revenue, and DEX volume across the NEAR ecosystem." :updated-at="snapshot?.updated_at" />
    <div class="protocol-tabs" role="tablist" aria-label="Protocol metric">
      <button v-for="item in categories" :key="item.id" role="tab" :aria-selected="selectedCategory === item.id" :class="{ selected: selectedCategory === item.id }" @click="selectedCategory = item.id">{{ item.label }}</button>
    </div>

    <div class="section-title-row protocol-section-title">
      <div><h2>Protocol snapshot</h2><p>Monthly and long-range totals · USD</p></div>
    </div>
    <div class="metric-grid protocol-overview-metrics">
      <MetricCard v-for="(item, index) in overviewCards" :key="item.key" :label="item.label"
        :value="isDexVolume ? volumeCurrency(item.value) : isRevenue ? revenueCurrency(item.value) : currency(item.value)" :change="item.change === undefined ? undefined : formatPercent(item.change)"
        :change-label="item.change === undefined ? '' : item.changeLabel"
        :detail="item.detail"
        :icon="[Coins, Activity, TrendingUp, Layers3, CalendarDays][index]"
        :tone="['green', 'blue', 'violet', 'amber', 'amber'][index]" />
    </div>

    <div class="section-title-row protocol-section-title">
      <div><h2>{{ category.label }} trends</h2><p>Choose a calendar period and currency to explore the series</p></div>
    </div>
    <div class="overview-grid protocol-metric-chart-layout protocol-chart-row" :class="{ 'protocol-trend-layout-wide': trendCards.length === 0 }">
      <BarChart :title="`${category.label} over time`" subtitle="Calendar period totals · USD or NEAR" :datasets="timeSeries" initial-period="daily" initial-currency="USD" :height="390" :methodology="selectedCategoryMethodology" />
      <div v-if="trendCards.length" class="metric-grid protocol-chart-metrics">
        <MetricCard v-for="(item, index) in trendCards" :key="item.key" :label="item.label"
          :value="isDexVolume ? volumeCurrency(item.value) : isRevenue ? revenueCurrency(item.value) : currency(item.value)" :change="item.change === undefined ? undefined : formatPercent(item.change)"
          :change-label="item.change === undefined ? '' : item.changeLabel"
          :detail="item.detail"
          :icon="[Coins, Activity, TrendingUp, Layers3, CalendarDays][index]"
          :tone="['green', 'blue', 'violet'][index]"
          body-align="center" mobile-body-align="left" :value-size="trendCards.length === 1 ? 'xlarge' : 'large'" />
      </div>
    </div>

    <div class="section-title-row protocol-section-title">
      <div><h2>Protocol distribution &amp; contributions</h2><p>Current distribution alongside historical protocol contributions</p></div>
    </div>
    <div class="overview-grid protocol-distribution-grid">
      <PieChart :title="`${category.label} distribution`" subtitle="Protocol contribution totals · USD or NEAR" :datasets="pieChart" initial-period="all_time" initial-currency="USD" :height="310" />
      <LineChart :title="`${category.label} breakdown over time`" subtitle="Protocol contributions · USD or NEAR" :datasets="breakdownSeries" initial-period="daily" initial-currency="USD" :height="310" :methodology="methodologies?.protocols?.breakdown" />
    </div>

  </template>
</template>
