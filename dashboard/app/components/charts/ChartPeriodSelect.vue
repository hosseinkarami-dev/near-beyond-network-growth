<script setup lang="ts">
import { Check, ChevronDown } from '@lucide/vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { periodNames } from '~/composables/useAnalytics'

const props = defineProps<{ modelValue: string, options: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const root = ref<HTMLElement | null>(null)
const open = ref(false)

function closeOnOutside(event: PointerEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

function choose(value: string) {
  emit('update:modelValue', value)
  open.value = false
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
  if (event.key === 'ArrowDown' && !open.value) {
    event.preventDefault()
    open.value = true
  }
}

onMounted(() => document.addEventListener('pointerdown', closeOnOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeOnOutside))
</script>

<template>
  <div ref="root" class="period-select" @keydown="handleKeydown">
    <button
      class="period-select-trigger"
      type="button"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="open = !open"
    >
      <span>{{ periodNames[modelValue] ?? modelValue }}</span>
      <ChevronDown :size="14" :class="{ 'chevron-open': open }" />
    </button>
    <Transition name="period-menu">
      <div v-if="open" class="period-select-menu" role="listbox" aria-label="Time period">
        <button
          v-for="option in options"
          :key="option"
          class="period-select-option"
          :class="{ selected: modelValue === option }"
          type="button"
          role="option"
          :aria-selected="modelValue === option"
          @click="choose(option)"
        >
          <span>{{ periodNames[option] ?? option }}</span>
          <Check v-if="modelValue === option" :size="14" />
        </button>
      </div>
    </Transition>
  </div>
</template>
