<script setup lang="ts">
import {
  Activity, ArrowLeftRight, Blocks, BookOpenCheck, Coins, LayoutDashboard, X,
} from '@lucide/vue'

defineProps<{ mobileOpen: boolean, mobileEnabled: boolean }>()
defineEmits<{ close: [] }>()

const route = useRoute()
const groups = [
  {
    label: 'Overview',
    links: [
      { label: 'Dashboard', to: '/', icon: LayoutDashboard },
      { label: 'Research & Methodology', to: '/research', icon: BookOpenCheck },
    ],
  },
  {
    label: 'Analytics',
    links: [
      { label: 'Network', to: '/network', icon: Activity },
      { label: 'Tokenomics', to: '/tokenomics', icon: Coins },
      { label: 'Intents', to: '/intents', icon: ArrowLeftRight },
      { label: 'Protocols', to: '/protocols', icon: Blocks },
    ],
  },
]
</script>

<template>
  <div v-if="mobileEnabled && mobileOpen" class="sidebar-backdrop" @click="$emit('close')" />
  <aside class="sidebar" :class="{ 'sidebar-open': mobileEnabled && mobileOpen }">
    <div class="brand-row">
      <NuxtLink to="/" class="brand-mark" @click="$emit('close')">
        <span class="brand-symbol">N</span>
        <span class="brand-copy">
          <strong>NEAR<span>scope</span></strong>
          <small>BEYOND NETWORK GROWTH</small>
        </span>
      </NuxtLink>
      <button v-if="mobileEnabled" class="icon-button mobile-close" aria-label="Close navigation" @click="$emit('close')">
        <X :size="18" />
      </button>
    </div>

    <nav class="side-nav" aria-label="Main navigation">
      <section v-for="group in groups" :key="group.label" class="nav-group">
        <p class="nav-label">{{ group.label }}</p>
        <NuxtLink
          v-for="link in group.links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          :class="{ active: route.path === link.to }"
          @click="$emit('close')"
        >
          <component :is="link.icon" :size="18" :stroke-width="1.8" />
          <span>{{ link.label }}</span>
        </NuxtLink>
      </section>
    </nav>

    <div class="sidebar-bottom">
      <LiveNearPrice />
      <span class="sidebar-version">NEAR Ecosystem Analytics &amp; Investment Research</span>
    </div>
  </aside>
</template>
