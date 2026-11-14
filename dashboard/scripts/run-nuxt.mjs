// Run Nuxt with serialized recursive directory creation on Windows.

import fs from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = new URL('.', import.meta.url)
const dashboardDirectory = fileURLToPath(new URL('..', scriptDirectory))
const command = process.argv[2]

if (!['build', 'generate'].includes(command)) {
  throw new Error('Usage: node scripts/run-nuxt.mjs <build|generate>')
}

const originalMkdir = fs.promises.mkdir.bind(fs.promises)
let mkdirQueue = Promise.resolve()
fs.promises.mkdir = async (path, options) => {
  const operation = mkdirQueue.then(() => originalMkdir(path, options))
  mkdirQueue = operation.catch(() => {})
  return operation
}

process.argv = [
  process.execPath,
  resolve(dashboardDirectory, 'node_modules/nuxt/bin/nuxt.mjs'),
  command,
]

await import('@nuxt/cli/cli')
