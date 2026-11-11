<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  description?: string
  updatedAt?: string
}>()

function formattedDate(value?: string) {
  if (!value) return 'Latest data'
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? 'Latest data' : `Updated ${new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(parsed)} UTC`
}
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow"><span class="network-status-dot" /> {{ eyebrow ?? 'NEAR MAINNET' }}</div>
      <h1>{{ title }}<span class="title-period">.</span></h1>
      <p v-if="description" class="page-description">{{ description }}</p>
    </div>
    <div class="heading-meta">
      <span class="meta-date"><span class="meta-pulse" /> {{ formattedDate(updatedAt) }}</span>
    </div>
  </div>
</template>
