<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChartSeries } from '~/composables/useAnalytics'
type MethodologyEntry = { title: string, description: string }

const props = withDefaults(defineProps<{
  title: string
  subtitle?: string
  datasets: Record<string, Record<string, ChartSeries[]>>
  initialPeriod?: string
  initialCurrency?: string
  height?: number
  compact?: boolean
  methodology?: MethodologyEntry | MethodologyEntry[]
}>(), { height: 300, compact: false })

const periods = computed(() => Object.keys(props.datasets))
const selectedPeriod = ref(props.initialPeriod ?? periods.value[0] ?? '')
watch(periods, (values) => {
  if (!values.includes(selectedPeriod.value)) selectedPeriod.value = values[0] ?? ''
}, { immediate: true })
const currencies = computed(() => Object.keys(props.datasets[selectedPeriod.value] ?? {}))
const selectedCurrency = ref(props.initialCurrency ?? currencies.value[0] ?? 'USD')
watch(currencies, (values) => {
  if (!values.includes(selectedCurrency.value)) selectedCurrency.value = values[0] ?? 'USD'
}, { immediate: true })
const series = computed(() => props.datasets[selectedPeriod.value]?.[selectedCurrency.value] ?? [])
const visibleSeries = computed(() => selectedPeriod.value === 'daily'
  ? series.value.map((item) => item.type === 'pie'
    ? item
    : { ...item, data: (item.data as [string, number | null][]).slice(-180) })
  : series.value)
const hasPie = computed(() => series.value.some((item) => item.type === 'pie'))
const hasData = computed(() => series.value.some((item) => Array.isArray(item.data) && item.data.length > 0))
const chartReady = ref(false)

watch([selectedPeriod, selectedCurrency, visibleSeries], () => {
  chartReady.value = false
})
</script>

<template>
  <section class="panel-card chart-card">
    <header class="panel-header chart-header">
      <div class="chart-heading"><div><h2>{{ title }}</h2><p v-if="subtitle">{{ subtitle }}</p></div></div>
      <div class="chart-controls">
        <MethodologyTip v-if="methodology" :items="methodology" />
        <ChartPeriodSelect v-if="periods.length > 1" v-model="selectedPeriod" :options="periods" />
        <div v-if="currencies.length > 1" class="currency-control" aria-label="Currency">
          <button v-for="currency in currencies" :key="currency" :class="{ selected: selectedCurrency === currency }" @click="selectedCurrency = currency">{{ currency }}</button>
        </div>
        <slot name="actions" />
      </div>
    </header>
    <div class="chart-body" :class="{ 'chart-body-compact': compact }">
      <div v-if="hasData" class="chart-render-stage">
        <ChartCanvas :class="{ 'chart-canvas-ready': chartReady }" :series="visibleSeries" :height="height" :pie="hasPie" @ready="chartReady = true" />
        <Transition name="chart-skeleton">
          <div v-if="!chartReady" class="chart-skeleton" :style="{ height: `${height}px` }" aria-label="Loading chart">
            <div class="skeleton-legend"><i /><span /><i /><span /></div>
            <div class="skeleton-chart-grid"><i v-for="line in 4" :key="line" /></div>
            <div class="skeleton-chart-bars"><i v-for="bar in 12" :key="bar" :style="{ height: `${22 + ((bar * 37) % 65)}%` }" /></div>
            <div class="skeleton-chart-axis"><i v-for="tick in 6" :key="tick" /></div>
          </div>
        </Transition>
      </div>
      <div v-else class="chart-empty">No observations for this selection.</div>
    </div>
    <slot name="footer" />
  </section>
</template>
