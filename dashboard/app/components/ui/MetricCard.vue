<script setup lang="ts">
import type { Component } from 'vue'
import { ArrowDownRight, ArrowUpRight, Minus } from '@lucide/vue'

const props = withDefaults(defineProps<{
  label: string
  value: string | number
  change?: string | number | null
  changeLabel?: string
  icon?: Component
  tone?: 'green' | 'blue' | 'violet' | 'amber'
  bodyAlign?: 'top' | 'center' | 'bottom'
  valueSize?: 'default' | 'large' | 'xlarge'
  mobileBodyAlign?: 'left' | 'center' | 'right' | 'inherit'
  detail?: string
  methodology?: { title: string, description: string }
}>(), { changeLabel: 'vs. previous day', tone: 'green', bodyAlign: 'top', valueSize: 'default', mobileBodyAlign: 'inherit' })

const changeValue = computed(() => Number(typeof props.change === 'string' ? props.change.replace('%', '') : props.change))
const changeState = computed(() => !Number.isFinite(changeValue.value) ? 'neutral' : changeValue.value >= 0 ? 'positive' : 'negative')
</script>

<template>
  <article class="metric-card">
    <div class="metric-topline">
      <span class="metric-label">{{ label }}</span>
      <span class="metric-actions">
        <MethodologyTip v-if="methodology" :items="methodology" />
        <span class="metric-icon" :class="`tone-${tone}`"><component :is="icon" v-if="icon" :size="17" /></span>
      </span>
    </div>
    <div class="metric-body" :class="[`metric-body-${bodyAlign}`, `metric-body-mobile-${mobileBodyAlign}`]">
      <div class="metric-value" :class="`metric-value-${valueSize}`">{{ value }}</div>
      <div class="metric-bottomline">
        <span v-if="change !== undefined && change !== null" class="metric-change" :class="`change-${changeState}`">
          <ArrowUpRight v-if="changeState === 'positive'" :size="14" />
          <ArrowDownRight v-else-if="changeState === 'negative'" :size="14" />
          <Minus v-else :size="13" />
          {{ change }}
        </span>
        <span v-if="changeLabel" class="metric-change-label">{{ changeLabel }}</span>
        <span v-else-if="detail" class="metric-change-label">{{ detail }}</span>
      </div>
    </div>
  </article>
</template>
