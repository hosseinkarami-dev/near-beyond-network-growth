<script setup lang="ts">
import { Info, X } from '@lucide/vue'
import { onBeforeUnmount, watch } from 'vue'

type MethodologyEntry = { title: string, description: string }

defineProps<{ items: MethodologyEntry | MethodologyEntry[] }>()
const open = ref(false)
function closeOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}
watch(open, (shown) => {
  if (!import.meta.client) return
  if (shown) window.addEventListener('keydown', closeOnEscape)
  else window.removeEventListener('keydown', closeOnEscape)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', closeOnEscape)
})
</script>

<template>
  <button class="methodology-trigger" type="button" aria-label="How this is calculated" @click.stop="open = true">
    <Info :size="14" />
  </button>
  <Teleport to="body">
    <Transition name="methodology-dialog">
      <div v-if="open" class="methodology-overlay" @click.self="open = false" @keydown.esc="open = false">
        <section class="methodology-dialog" role="dialog" aria-modal="true" aria-label="Calculation methodology">
          <header class="methodology-dialog-header">
            <div><span>METRIC NOTES</span><h2>How this is calculated</h2></div>
            <button class="methodology-close" type="button" aria-label="Close methodology" @click="open = false"><X :size="17" /></button>
          </header>
          <div class="methodology-dialog-body">
            <article v-for="(item, index) in (Array.isArray(items) ? items : [items])" :key="`${item.title}-${index}`" class="methodology-entry">
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </article>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
