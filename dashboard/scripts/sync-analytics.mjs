import { cp, mkdir, rename, rm, stat } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const source = resolve(scriptDir, '../../data/analytics')
const destination = resolve(scriptDir, '../public/data/analytics')
const staging = `${destination}.staging`
const publicRoot = resolve(scriptDir, '../public')
const lockDirectory = resolve(scriptDir, '../.sync-analytics.lock')
const lockTimeoutMs = 60_000
const staleLockMs = 30 * 60_000
for (const target of [destination, staging]) {
  const targetRelative = relative(publicRoot, target)
  if (!targetRelative || targetRelative.startsWith('..') || isAbsolute(targetRelative)) {
    throw new Error(`Refusing to replace analytics data outside ${publicRoot}: ${target}`)
  }
}

async function acquireSyncLock() {
  const deadline = Date.now() + lockTimeoutMs
  while (Date.now() < deadline) {
    try {
      await mkdir(lockDirectory)
      return
    }
    catch (error) {
      if (error?.code !== 'EEXIST') throw error
      const lock = await stat(lockDirectory).catch(() => null)
      if (lock && Date.now() - lock.mtimeMs > staleLockMs) {
        await rm(lockDirectory, { recursive: true, force: true })
        continue
      }
      await delay(100)
    }
  }
  throw new Error(`Timed out waiting for analytics sync lock: ${lockDirectory}`)
}

await acquireSyncLock()
try {
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
  const repositoryRoot = resolve(scriptDir, '../..')
  const displayDestination = relative(repositoryRoot, destination).split('\\').join('/')
  console.log(`✓ Analytics data ready · ${displayDestination}`)
}
finally {
  await rm(lockDirectory, { recursive: true, force: true })
}
