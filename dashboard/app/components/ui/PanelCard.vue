<script setup lang="ts">
import { ArrowUpRight } from '@lucide/vue'

withDefaults(defineProps<{ title: string, subtitle?: string, link?: string }>(), {})
</script>

<template>
  <section class="panel-card">
    <header class="panel-header">
      <div><h2>{{ title }}</h2><p v-if="subtitle">{{ subtitle }}</p></div>
      <NuxtLink v-if="link" :to="link" class="panel-link">View details <ArrowUpRight :size="14" /></NuxtLink>
      <slot name="actions" />
    </header>
    <div class="panel-body"><slot /></div>
  </section>
</template>
