<script setup lang="ts">
withDefaults(defineProps<{ metrics?: number, charts?: number }>(), { metrics: 4, charts: 2 })
</script>

<template>
  <div class="page-loading-skeleton" role="status" aria-label="Loading analytics">
    <div class="page-loading-heading">
      <i class="skeleton-block skeleton-eyebrow" />
      <i class="skeleton-block skeleton-title" />
      <i class="skeleton-block skeleton-description" />
    </div>
    <div class="page-loading-metrics">
      <div v-for="item in metrics" :key="item" class="page-loading-metric">
        <i class="skeleton-block skeleton-metric-label" />
        <i class="skeleton-block skeleton-metric-value" />
        <i class="skeleton-block skeleton-metric-foot" />
      </div>
    </div>
    <div class="page-loading-charts">
      <div v-for="item in charts" :key="item" class="page-loading-chart">
        <div class="page-loading-chart-heading"><i class="skeleton-block skeleton-chart-title" /><i class="skeleton-block skeleton-chart-control" /></div>
        <div class="page-loading-chart-plot"><i v-for="line in 4" :key="line" class="skeleton-block skeleton-chart-line" /><div class="page-loading-chart-bars"><i v-for="bar in 10" :key="bar" class="skeleton-block" :style="{ height: `${20 + ((bar * 31 + item * 17) % 65)}%` }" /></div></div>
      </div>
    </div>
    <span class="page-loading-caption">Loading analytics data…</span>
  </div>
</template>
