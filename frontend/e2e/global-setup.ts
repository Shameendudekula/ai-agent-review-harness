import { execFileSync } from 'node:child_process'

import { DATABASE_URL, PYTHON } from '../playwright.config'

// Start every run from an empty database so results and screenshots are reproducible.
export default function globalSetup() {
  execFileSync(PYTHON, ['scripts/reset_test_database.py'], {
    cwd: '..',
    env: { ...process.env, DATABASE_URL },
    stdio: 'inherit',
  })
}
