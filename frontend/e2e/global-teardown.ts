import { readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export default async function globalTeardown() {
  // The config creates one disposable DB directory per run. Ports are fixed,
  // so only one local Playwright run can be active at a time.
  for (const entry of readdirSync(tmpdir(), { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.startsWith('careerlens-playwright-')) {
      rmSync(join(tmpdir(), entry.name), { recursive: true, force: true })
    }
  }
}
