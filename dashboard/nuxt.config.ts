import { mkdir, readdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const dashboardDirectory = dirname(fileURLToPath(import.meta.url))

async function prepareAnalyticsOutputDirectories(sourceDirectory: string, outputDirectory: string) {
  await mkdir(outputDirectory, { recursive: true })
  const entries = await readdir(sourceDirectory, { withFileTypes: true })
  for (const entry of entries) {
    if (entry.isDirectory()) {
      await prepareAnalyticsOutputDirectories(
        resolve(sourceDirectory, entry.name),
        resolve(outputDirectory, entry.name),
      )
    }
  }
}

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
  nitro: {
    hooks: {
      'rollup:before': async (nitro) => {
        const sourceDirectory = resolve(dashboardDirectory, 'public/data/analytics')
        const outputDirectory = resolve(nitro.options.output.publicDir, 'data/analytics')
        await prepareAnalyticsOutputDirectories(sourceDirectory, outputDirectory)
      },
    },
  },
  app: {
    head: {
      title: 'NEAR Investment Thesis',
      titleTemplate: '%s · NEARProtocol',
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
      meta: [
        { name: 'description', content: 'An investment thesis view of NEAR network activity, token economics, value capture, and ecosystem metrics.' },
        { name: 'theme-color', content: '#101310' },
      ],
    },
  },
  typescript: { strict: true },
});
