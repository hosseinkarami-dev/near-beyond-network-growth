<script setup lang="ts">
import { AlertTriangle, RotateCw } from '@lucide/vue'

withDefaults(defineProps<{ title: string, message?: string, retrying?: boolean }>(), {
  message: 'The analytics files could not be reached. Check the connection and try again.',
  retrying: false,
})
defineEmits<{ retry: [] }>()
</script>

<template>
  <section class="data-error-card" role="alert">
    <div class="data-error-icon"><AlertTriangle :size="21" :stroke-width="1.8" /></div>
    <span class="data-error-eyebrow">DATA CONNECTION</span>
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <button class="data-error-retry" :disabled="retrying" @click="$emit('retry')">
      <RotateCw :size="15" :class="{ 'is-spinning': retrying }" />
      {{ retrying ? 'Trying again…' : 'Try again' }}
    </button>
  </section>
</template>
