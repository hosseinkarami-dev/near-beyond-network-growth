<script setup lang="ts">
import { Menu, Moon, Sun } from '@lucide/vue'

defineProps<{ mobileMenuVisible: boolean }>()
defineEmits<{ menu: [] }>()
const route = useRoute()
const { isDark, toggleTheme } = useDashboardTheme()
const pageNames: Record<string, string> = {
  '/': 'Dashboard', '/network': 'Network', '/tokenomics': 'Tokenomics',
  '/intents': 'Intents', '/protocols': 'Protocols',
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <button v-if="mobileMenuVisible" class="icon-button mobile-menu" aria-label="Open navigation" @click="$emit('menu')">
        <Menu :size="19" />
      </button>
      <div class="breadcrumbs"><span>Workspace</span><span class="crumb-divider">/</span><strong>{{ pageNames[route.path] ?? 'Analytics' }}</strong></div>
    </div>
    <div class="topbar-actions">
      <div class="topbar-network"><span class="network-status-dot" /> Mainnet</div>
      <span class="topbar-divider" />
      <button class="theme-toggle" :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'" @click="toggleTheme">
        <Sun v-if="isDark" :size="17" />
        <Moon v-else :size="17" />
        <span>{{ isDark ? 'Light mode' : 'Dark mode' }}</span>
      </button>
    </div>
  </header>
</template>
