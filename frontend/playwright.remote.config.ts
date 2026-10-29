import { defineConfig, devices } from '@playwright/test'

// Post-deploy smoke test: runs the e2e journeys against an already deployed frontend.
// Usage: E2E_BASE_URL=https://review-harness-web.onrender.com npx playwright test -c playwright.remote.config.ts
// It does not start servers or reset any database; it creates demo tasks in the target environment.
const baseURL = process.env.E2E_BASE_URL
if (!baseURL) throw new Error('Set E2E_BASE_URL to the deployed frontend URL')

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 30_000 },
  reporter: [['list']],
  use: { baseURL, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
})
