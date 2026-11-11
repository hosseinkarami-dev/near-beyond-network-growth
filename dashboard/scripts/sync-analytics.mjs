import { cp, mkdir, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const source = resolve(scriptDir, '../../data/analytics')
const destination = resolve(scriptDir, '../public/data/analytics')

await rm(destination, { recursive: true, force: true })
await mkdir(dirname(destination), { recursive: true })
await cp(source, destination, { recursive: true })
console.log(`Synced analytics data to ${destination}`)
