import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run the real backend (against a dedicated database) and the real frontend.
export const PYTHON = process.env.E2E_PYTHON ?? '.venv/bin/python' // relative to the repo root (webServer cwd)
export const DATABASE_URL = process.env.E2E_DATABASE_URL ?? 'postgresql+psycopg://localhost/review_harness_e2e'
const API_PORT = 8765
const WEB_PORT = 5174

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
  webServer: [
    {
      command: `${PYTHON} -m alembic upgrade head && ${PYTHON} -m uvicorn backend.app.main:app --port ${API_PORT}`,
      cwd: '..',
      url: `http://localhost:${API_PORT}/health/ready`,
      env: {
        DATABASE_URL,
        CORS_ALLOWED_ORIGINS: `http://localhost:${WEB_PORT}`,
        PLANNER: 'mock',
        RATE_LIMIT_PER_MINUTE: '0',
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { VITE_API_BASE_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
