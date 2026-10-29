# Progress Tracker

Statuses reflect verified evidence only. "Done" means the module's acceptance criteria
were checked with the commands listed.

| # | Module | Status | Evidence |
|---|---|---|---|
| 1 | Project setup and design | Done | Docs reviewed; architecture rewritten to match the implementation |
| 2 | Backend foundation | Done | App starts; `/health` OK; pip-tools lock; config validated at startup; consistent error format |
| 3 | Task management API | Done | Create, list, get, and cancel endpoints; PostgreSQL + Alembic; API and persistence tests |
| 4 | Deterministic agent planning | Done | Mock planner with 8 scenarios; `AgentPlan` schema; determinism and validation tests |
| 5 | Review and policy engine | Done | Risk, review requirement, and authorization as separate modules; structured and baseline modes |
| 6 | Safe execution and audit | Done | 7 allowlisted mock tools; authorization before each call; verification; append-only audit log |
| 7 | Frontend | Done (local) | React + TS UI; 15 Vitest tests; 6 Playwright e2e tests against the real backend |
| 8 | Database and state-machine integrity | Done (backend) | Lifecycle tests; DB CHECK constraints; append-only triggers; migration downgrade and upgrade run in tests |
| 9 | Security and reliability | Done | security.md maps each control to its tests; bundle and history secret scans clean |
| 10 | LLM integration | Adapter done; live call not verified | Anthropic adapter tested with a fake client; no live API call has been made (no key configured) |
| 11 | Evaluation | Done (simulation) | Pre-registered plan (`a30b066`); 96 runs, reproducible; see evaluation-results.md. No human study |
| 12 | Deployment and CI/CD | CI done; deployment prepared, **blocked on account setup** | `render.yaml` + Neon plan; production start command rehearsed locally. Needs Render and Neon accounts (docs/deployment.md §3) |
| 13 | Portfolio delivery | Not started | |

## Verification log

### 2026-10-29: backend milestone

Commands run locally on macOS, Python 3.11.16, PostgreSQL 18.3 (Homebrew):

```text
pytest                      157 passed
ruff check .                All checks passed
mypy                        Success: no issues found in 37 source files
pip check                   No broken requirements found
alembic upgrade head        OK (also downgrade base → upgrade head)
```

## Known open items

- A task stays in PLANNING if the process crashes while the planner runs (no recovery job).
- The demo has no authentication: reviewer identity is a self-declared label.

### 2026-10-29: frontend milestone

```text
npm run typecheck           OK
npm run lint (oxlint)       0 warnings
npm test (vitest)           15 passed
npm run build               OK (≈91 kB gzipped JS)
npm run test:e2e            6 passed (desktop Chromium + Pixel 7 viewport)
```

Screenshots in `docs/screenshots/` are captured from the e2e run (`SCREENSHOTS=1 npm run test:e2e`).
