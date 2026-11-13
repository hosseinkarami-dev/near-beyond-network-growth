export default defineNuxtConfig({
  compatibilityDate: '2026-11-09',
  devtools: { enabled: false },
  runtimeConfig: {
    public: {
      analyticsBaseUrl: '/data/analytics',
    },
  },
  components: [{ path: '~/components', pathPrefix: false }],
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      title: 'NEAR Investment Thesis',
      titleTemplate: '%s · NEARscope',
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
      meta: [
        { name: 'description', content: 'An investment thesis view of NEAR network activity, token economics, value capture, and ecosystem metrics.' },
        { name: 'theme-color', content: '#101310' },
      ],
    },
  },
  typescript: { strict: true },
});
