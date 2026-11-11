export default defineNuxtConfig({
  compatibilityDate: '2026-11-09',
  devtools: { enabled: false },
  components: [{ path: '~/components', pathPrefix: false }],
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      title: 'NEAR Analytics',
      titleTemplate: '%s · NEAR Analytics',
      meta: [
        { name: 'description', content: 'A clear view of NEAR network activity, tokenomics, and ecosystem analytics.' },
        { name: 'theme-color', content: '#101310' },
      ],
    },
  },
  typescript: { strict: true },
});
