import { cp, mkdir, rename, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, isAbsolute, relative, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const source = resolve(scriptDir, '../../data/analytics')
const destination = resolve(scriptDir, '../public/data/analytics')
const staging = `${destination}.staging`
const publicRoot = resolve(scriptDir, '../public')
for (const target of [destination, staging]) {
  const targetRelative = relative(publicRoot, target)
  if (!targetRelative || targetRelative.startsWith('..') || isAbsolute(targetRelative)) {
    throw new Error(`Refusing to replace analytics data outside ${publicRoot}: ${target}`)
  }
}

await mkdir(dirname(destination), { recursive: true })
await rm(staging, { recursive: true, force: true })
try {
  await cp(source, staging, { recursive: true })
}
catch (error) {
  if (error?.code !== 'ENOENT') throw error
  await mkdir(staging, { recursive: true })
  console.warn(`Analytics source directory is unavailable; syncing an empty dataset from ${source}`)
}
await rm(destination, { recursive: true, force: true })
await rename(staging, destination)
console.log(`Synced analytics data to ${destination}`)
