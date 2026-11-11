<script setup lang="ts">
import type { ChartSeries } from '~/composables/useAnalytics'
type MethodologyEntry = { title: string, description: string }

withDefaults(defineProps<{
  title: string
  subtitle?: string
  datasets: Record<string, Record<string, ChartSeries[]>>
  initialPeriod?: string
  initialCurrency?: string
  height?: number
  methodology?: MethodologyEntry | MethodologyEntry[]
}>(), { height: 300 })
</script>

<template><AnalyticsChart v-bind="$props" :height="height + 34" /></template>
