import { computed, onMounted, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export function useDashboardTheme() {
  const theme = useState<ThemeMode>('dashboard-theme', () => 'dark')
  const isDark = computed(() => theme.value === 'dark')

  onMounted(() => {
    const stored = localStorage.getItem('near-dashboard-theme')
    if (stored === 'light' || stored === 'dark') theme.value = stored
  })

  watch(theme, (value) => {
    if (import.meta.client) {
      document.documentElement.dataset.theme = value
      localStorage.setItem('near-dashboard-theme', value)
    }
  }, { immediate: true })

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, isDark, toggleTheme }
}
