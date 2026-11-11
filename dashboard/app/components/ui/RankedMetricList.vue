<script setup lang="ts">
import { computed } from 'vue'
type MethodologyEntry = { title: string, description: string }
import { chartColorForTheme, formatCurrency } from '~/composables/useAnalytics'

type RankedItem = { name: string, value: number }
const props = withDefaults(defineProps<{
  title: string
  subtitle?: string
  items: RankedItem[]
  color?: string
  badge?: string
  methodology?: MethodologyEntry | MethodologyEntry[]
  limit?: number
  scrollable?: boolean
  totalLabel?: string
  totalValue?: number
  emptyMessage?: string
}>(), { color: '#b4f273', scrollable: false, emptyMessage: 'No observations are available.' })

const visibleItems = computed(() => props.limit ? props.items.slice(0, props.limit) : props.items)
const maxValue = computed(() => Math.max(0, ...visibleItems.value.map((item) => Number(item.value) || 0)))
const { isDark } = useDashboardTheme()
const barColor = computed(() => chartColorForTheme(props.color, isDark.value))
</script>

<template>
  <section class="panel-card ranked-metric-card" :class="{ 'ranked-metric-scrollable': scrollable }">
    <header class="panel-header">
      <div><h2>{{ title }}</h2><p v-if="subtitle">{{ subtitle }}</p></div>
      <MethodologyTip v-if="methodology" :items="methodology" />
      <span v-if="badge" class="table-unit">{{ badge }}</span>
    </header>
    <div v-if="totalLabel && totalValue !== undefined" class="tvl-total">
      <span>{{ totalLabel }}</span><strong>{{ formatCurrency(totalValue, 'USD', 0) }}</strong>
    </div>
    <div class="leader-list" :class="{ 'leader-list-scroll': scrollable }">
      <div v-for="(item, index) in visibleItems" :key="item.name" class="leader-row">
        <span class="leader-rank">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="leader-name">{{ item.name }}</span>
        <span class="leader-value">{{ formatCurrency(item.value, 'USD', 0) }}</span>
        <span class="leader-track"><i :style="{ width: `${maxValue ? Math.max(2, item.value / maxValue * 100) : 0}%`, background: barColor }" /></span>
      </div>
      <div v-if="!visibleItems.length" class="chart-empty protocol-empty">{{ emptyMessage }}</div>
    </div>
  </section>
</template>
