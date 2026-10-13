import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from '@playwright/test'

const frontendDirectory = dirname(fileURLToPath(import.meta.url))
const backendDirectory = resolve(frontendDirectory, '../backend')
const virtualEnvironmentPython = join(backendDirectory, '.venv', 'bin', 'python')
const pythonExecutable = process.env.CAREERLENS_E2E_PYTHON
  || (existsSync(virtualEnvironmentPython) ? virtualEnvironmentPython : 'python3')
const quoteForShell = (value: string) => `'${value.replaceAll("'", "'\\''")}'`

const apiPort = Number(process.env.CAREERLENS_E2E_API_PORT || 18001)
const frontendPort = Number(process.env.CAREERLENS_E2E_FRONTEND_PORT || 15174)
const recordDemo = process.env.CAREERLENS_RECORD_DEMO === 'true'
const apiUrl = `http://127.0.0.1:${apiPort}`
const frontendUrl = `http://127.0.0.1:${frontendPort}`
const useCiDatabase = process.env.CAREERLENS_E2E_USE_CI_DATABASE === 'true'
const ciDatabaseUrl = useCiDatabase ? process.env.DATABASE_URL : undefined
if (useCiDatabase && !ciDatabaseUrl) {
  throw new Error('DATABASE_URL is required when using the CI PostgreSQL database.')
}
const localDatabaseDirectory = ciDatabaseUrl
  ? undefined
  : mkdtempSync(join(tmpdir(), 'careerlens-playwright-'))
const databaseUrl = ciDatabaseUrl
  || `sqlite+pysqlite:///${join(localDatabaseDirectory!, 'careerlens.sqlite3')}`

export default defineConfig({
  testDir: resolve(frontendDirectory, 'e2e'),
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  globalTeardown: resolve(frontendDirectory, 'e2e/global-teardown.ts'),
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: frontendUrl,
    trace: 'retain-on-failure',
    ...(recordDemo
      ? {
          viewport: { width: 1280, height: 720 },
          video: { mode: 'on' as const, size: { width: 1280, height: 720 } },
        }
      : {}),
  },
  webServer: [
    {
      command: `${quoteForShell(pythonExecutable)} e2e_prepare.py && ${quoteForShell(pythonExecutable)} -m uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: backendDirectory,
      env: {
        DATABASE_URL: databaseUrl,
        JWT_SECRET_KEY: 'playwright-test-only-secret-not-for-deployment',
        CORS_ALLOWED_ORIGINS: frontendUrl,
        CAREER_ANALYSIS_PROVIDER: 'rules',
      },
      url: `${apiUrl}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      cwd: frontendDirectory,
      env: { VITE_API_BASE_URL: apiUrl },
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
