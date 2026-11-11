<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import AppHeader from '~/components/shell/AppHeader.vue'
import AppSidebar from '~/components/shell/AppSidebar.vue'

const mobileOpen = ref(false)
const isMobile = ref(false)
let mobileQuery: MediaQueryList | undefined

function syncViewport(event?: MediaQueryListEvent) {
  isMobile.value = event?.matches ?? mobileQuery?.matches ?? false
  if (!isMobile.value) mobileOpen.value = false
}

onMounted(() => {
  mobileQuery = window.matchMedia('(max-width: 760px)')
  syncViewport()
  mobileQuery.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => mobileQuery?.removeEventListener('change', syncViewport))
</script>

<template>
  <div class="app-shell">
    <AppSidebar :mobile-open="mobileOpen" :mobile-enabled="isMobile" @close="mobileOpen = false" />
    <div class="app-main">
      <AppHeader :mobile-menu-visible="isMobile" @menu="mobileOpen = !mobileOpen" />
      <main class="page-content">
        <slot />
      </main>
      <footer class="app-footer">
        <span>NEAR mainnet analytics</span>
        <span>Data shown in UTC</span>
      </footer>
    </div>
  </div>
</template>
