# AI Agent Review Harness

**Make an AI agent's plan, assumptions, and risky actions reviewable before anything runs, and enforce the result in the backend.**

[![CI](https://github.com/Shameendudekula/ai-agent-review-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/Shameendudekula/ai-agent-review-harness/actions/workflows/ci.yml)

An independent portfolio project exploring human-in-the-loop oversight of AI agents:
how a structured, risk-based review workflow compares with a simple approve-or-stop
gate, and how to keep human approval separate from backend authorization.

**Live demo:** https://review-harness-web.onrender.com · API docs: https://review-harness-api.onrender.com/docs

> **Status (2026-10-29):** deployed and verified (Render + Neon, free tiers). Backend,
> frontend, tests, CI, and a simulated evaluation are complete. The API sleeps when
> idle, so the **first request can take about a minute**. The demo uses a
> deterministic mock agent and simulated tools; nothing real is changed.

![Structured review of a risky action](docs/screenshots/01-structured-review.png)

## What it does

1. A user creates a task. An agent proposes a plan with **steps, assumptions** (each
   marked stated, inferred, or unsupported), **open questions**, and **proposed tool
   actions** with success criteria.
2. A rule-based **policy** rates each action LOW / MEDIUM / HIGH / FORBIDDEN, using
   trusted tool metadata rather than the agent's own claim, and explains why it does or
   does not need review.
3. A reviewer **approves or rejects individual actions**, **requests a revision**, or
   **answers the agent's questions**. Revised plans come back for review. Rejecting
   one action does not cancel the task.
4. Execution is a separate, explicit step. Immediately before each tool call the
   backend **re-authorizes** the action from append-only decision records. A forged
   status field, a client flag, or text saying "pre-approved" cannot authorize
   anything.
5. Only **allowlisted, simulated tools** run. Each result is **verified** against the
   plan's success criteria.
6. Every step is written to an **append-only audit trail**.

A **baseline mode** (approve or stop the whole plan) runs on the same engine, which is
what makes the comparison in the evaluation possible.

## Highlights for reviewers

| Area | What to look at |
|---|---|
| Architecture | Modular monolith; pure policy functions; three-phase planning that never holds a lock during a planner call → [architecture.md](docs/architecture.md) |
| Security | Approval ≠ authorization; allowlist; append-only history enforced by DB triggers; prompt-injection handling and residual risks → [security.md](docs/security.md) |
| Testing | 157 backend tests on real PostgreSQL, 15 frontend tests, 6 Playwright end-to-end journeys, all in CI |
| Evaluation | Pre-registered, reproducible simulation (96 runs) with honest limits → [evaluation-results.md](docs/evaluation-results.md) |

## Technology

| Layer | Stack |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL (psycopg 3) |
| Agent | Deterministic mock planner (default); optional Anthropic adapter behind a provider-independent interface |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router |
| Quality | pytest + HTTPX, Vitest + Testing Library, Playwright, ruff, mypy (strict), oxlint |
| Delivery | GitHub Actions CI; deployed on Render (API + static site, Frankfurt) with Neon PostgreSQL |

## Repository layout

```text
backend/app/        FastAPI app: api/, services/, policy/, agent/, tools/, domain/, models.py
backend/migrations/ Alembic migrations
frontend/           React app (src/), Vitest tests (src/test/), Playwright tests (e2e/)
evaluation/         Simulated evaluation harness and committed results
tests/              Backend unit and API/integration tests
docs/               Requirements, architecture, security, API, evaluation, deployment, portfolio
render.yaml         Deployment blueprint
```

## Run it locally

Requires Python 3.11, Node.js 22+, and PostgreSQL. Docker is not required.

```bash
# Backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
createdb review_harness && createdb review_harness_test
cp .env.example .env
alembic upgrade head
uvicorn backend.app.main:app --reload            # http://127.0.0.1:8000/docs

# Frontend (second terminal)
cd frontend && npm ci && npm run dev             # http://localhost:5173
```

The default planner is the deterministic mock, so no API key is needed. Pick one of
the example tasks on the home page to see each scenario.

## Tests

```bash
pytest && ruff check . && mypy                                   # backend
cd frontend && npm run typecheck && npm run lint && npm test     # frontend
npx playwright install chromium && createdb review_harness_e2e
npm run test:e2e                                                 # real browser + real backend
```

Latest local results (2026-10-29): 157 passed · ruff clean · mypy clean · 15 passed ·
6 passed. CI runs the same commands on every push.

## Evaluation in one paragraph

Eight deterministic scenarios (incorrect assumption, risky deletion, missing
information, prompt injection, execution failure, and others) ran under both workflows
with two scripted reviewers. With an *attentive* simulated reviewer, the structured
workflow met all 8 success criteria versus 5/8 for the baseline, and needed fewer
decisions per task (0.75 vs 1.0). With an *approve-all* reviewer, both workflows
executed the same two harmful actions. The unlisted shell command was blocked in every
case, by authorization rather than by review. **This is a simulation whose reviewer
model partly builds in the result. It is not evidence about human reviewers**; see the
[full results and limitations](docs/evaluation-results.md).

## Documentation

[Requirements](docs/requirements.md) · [Architecture](docs/architecture.md) ·
[API](docs/api.md) · [Security](docs/security.md) ·
[Evaluation plan](docs/evaluation-plan.md) · [Evaluation results](docs/evaluation-results.md) ·
[Deployment](docs/deployment.md) · [Progress](docs/progress.md) ·
[Portfolio notes](docs/portfolio.md)

## Limitations

- Every tool is simulated; nothing real is changed.
- The demo has no authentication; the reviewer name is a label.
- The evaluation is a simulation; human understanding and review time are not measured.
- The LLM adapter is unit-tested with a fake client; no live LLM run has been verified.

## Ownership

Independently designed and built as a personal portfolio project by Dudekula Shameen,
with AI pair-programming assistance (Claude Code). It is not affiliated with,
sponsored by, or endorsed by any company or university.

## License

Not yet selected.
