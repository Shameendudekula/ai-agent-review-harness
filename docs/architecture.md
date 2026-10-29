# System Architecture

This document describes the implemented system. Where a design element is planned but
not yet built, it is marked **(planned)**.

## 1. Overview

AI Agent Review Harness is a modular monolith: one FastAPI application with internal
modules for task workflow, agent planning, review policy, authorization, restricted
tool execution, and audit history, backed by PostgreSQL.

An agent (a deterministic mock by default, optionally an LLM) proposes a plan. The
backend validates the plan, assesses the risk of each proposed action, decides which
actions need human review, records human decisions, authorizes each action
immediately before execution, runs only allowlisted mock tools, verifies the results,
and records every step in an append-only audit log.

## 2. Technology

| Layer | Technology |
|---|---|
| API | Python 3.11, FastAPI, Pydantic 2, Uvicorn |
| Persistence | PostgreSQL, SQLAlchemy 2 (ORM), Alembic migrations, psycopg 3 |
| Agent | Deterministic mock planner; optional Anthropic Messages API adapter |
| Tests | pytest, HTTPX (in-process ASGI transport), real PostgreSQL test database |
| Quality | ruff (lint), mypy (strict) |
| Frontend | React, TypeScript, Vite **(planned at the time of writing; see README status)** |

## 3. Backend module layout

```text
backend/app/
├── main.py              app factory: middleware, CORS, error handlers, routers
├── config.py            environment-based settings (validated at startup)
├── db.py                engine, session factory, declarative base
├── errors.py            error types and consistent JSON error responses
├── models.py            SQLAlchemy models
├── domain/              enums and the task lifecycle state machine
├── agent/               plan schema, planner interface, mock planner, LLM adapter
├── policy/              risk assessment, review requirements, authorization
├── tools/               allowlisted mock tools and result verification
├── services/            workflows and transaction boundaries
└── api/                 routes, request/response schemas, rate limiting
```

Route handlers parse input and shape output only. Services own transactions. Policy
modules are pure functions with no database or HTTP access, which makes them easy to
unit-test.

## 4. Request flow

```text
HTTP request ─► route (validate input) ─► service (lock task row, one transaction)
                                             │
                    ┌────────────────────────┼─────────────────────────┐
                    ▼                        ▼                         ▼
              lifecycle rules         planner + AgentPlan        policy: risk → review
                                       validation                requirement → authorize
                                             │
                                             ▼
                                    tools (allowlist) → verification → audit events
```

## 5. Task lifecycle

States: `CREATED`, `PLANNING`, `AWAITING_REVIEW`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.

| From | To | When |
|---|---|---|
| CREATED | PLANNING | Planning is requested |
| CREATED | CANCELLED | The task is cancelled before planning |
| PLANNING | AWAITING_REVIEW | The plan has actions pending review, open questions, or nothing executable |
| PLANNING | RUNNING | Policy requires no review (structured mode only) |
| PLANNING | FAILED | The planner errored or its output failed validation |
| AWAITING_REVIEW | PLANNING | The reviewer requests a revision or clarification |
| AWAITING_REVIEW | RUNNING | Baseline: plan approved. Structured: review complete and execution requested |
| AWAITING_REVIEW | CANCELLED | Cancelled, or (baseline) the plan is rejected |
| RUNNING | COMPLETED | Every executed action succeeded and passed verification |
| RUNNING | FAILED | Authorization denial, tool failure, or verification failure |
| FAILED | PLANNING | Explicit planning retry, allowed only if the failure happened during planning |

All other transitions are rejected (`409 invalid_transition`). Execution failures
cannot be retried, because a partially executed plan may already have had side
effects. Execution is synchronous, so `RUNNING` cannot be interrupted. The earlier
design's `RUNNING → AWAITING_REVIEW` checkpoint and `RUNNING → CANCELLED` transition
were therefore not implemented.

Review decisions are separate records. A rejected action does not cancel the task: the
remaining actions can still run, or the reviewer can request a revision.

## 6. Review modes (evaluation conditions)

| | Structured (proposed workflow) | Baseline (approve-or-stop) |
|---|---|---|
| Review unit | Each action whose risk is MEDIUM or HIGH | The whole plan |
| Low-risk actions | Run without review | Still need plan approval |
| Decisions | APPROVE, REJECT (per action); REQUEST_REVISION, REQUEST_CLARIFICATION (re-plan) | APPROVE or REJECT (stop) the plan |
| Open questions | Block execution until clarified | Not surfaced |
| Execution start | Explicit `execute` after the review is complete | Immediately on plan approval |
| Allowlist and authorization | Enforced | Enforced |

Both modes use the same planner, tools, authorization, and audit log, so evaluation
differences come from the review workflow alone.

## 7. Policy: risk, review requirement, authorization

These are three separate functions, each returning machine-readable reason codes.

1. **Risk assessment** (`policy/risk.py`) assigns an ordinal level, not a numeric score:
   - `FORBIDDEN`: the tool is not allowlisted or its arguments are invalid.
   - `HIGH`: the effect is irreversible or external.
   - `MEDIUM`: the action changes state reversibly, depends on an `UNSUPPORTED` assumption, or the agent flagged risk itself.
   - `LOW`: none of the above.

   Side effects come from the trusted tool registry. The agent's own estimate can raise
   the level but never lower it.
2. **Review requirement** (`policy/review.py`) maps risk and mode to `NOT_REQUIRED`,
   `PENDING`, or `BLOCKED`.
3. **Authorization** (`policy/authorization.py`) runs immediately before each tool
   call. It ignores the cached state columns and re-derives everything from:
   - the task's status and the current run;
   - the tool registry and argument validation;
   - a fresh risk assessment;
   - the append-only `review_decisions` records.

   A forged state column or a client-supplied flag therefore cannot authorize anything.

A human approval is one input to authorization; it is not authorization itself.

## 8. Data model

```text
tasks 1─* agent_runs 1─* assumptions
  │           └────────1─* proposed_actions
  ├─* review_decisions (→ agent_run, optional → proposed_action)
  └─* audit_events     (→ optional agent_run, optional → proposed_action)
```

| Table | Purpose | Key constraints |
|---|---|---|
| `tasks` | Description, review mode, lifecycle status, failure stage and reason | CHECK on enum columns; index on status |
| `agent_runs` | One row per planning attempt (initial, revision, clarification, retry), with reviewer input, planner name, summary, steps, open questions, error, and metadata | UNIQUE (task_id, attempt_number) |
| `assumptions` | Assumptions declared in a run, with basis (STATED / INFERRED / UNSUPPORTED), evidence, and consequence if wrong | UNIQUE (agent_run_id, key) |
| `proposed_actions` | Tool calls proposed in a run. Agent-supplied fields are kept separate from policy fields and from review, authorization, execution, and verification state | UNIQUE (agent_run_id, sequence) and (agent_run_id, key) |
| `review_decisions` | Human decisions, either per action or plan-wide | Append-only (trigger) |
| `audit_events` | Ordered event log per task | UNIQUE (task_id, sequence); append-only (trigger) |

**Why `proposed_actions` became a table.** The original design listed five entities.
Actions are reviewed, authorized, executed, and verified individually, and decisions
need a foreign key to the action they concern. That is not possible if actions are a
JSON blob inside `agent_runs`.

**Why `audit_events` instead of `execution_events`.** The table records the whole
lifecycle (planning, assumptions, decisions, authorization, and outcomes), not only
execution.

**Ordering.** `audit_events.sequence` is assigned as max + 1 while the task row is
locked, so it is gap-free and strictly increasing per task. The global identity
column gives a total insertion order across tasks.

## 9. Transactions and concurrency

- Each state-changing operation locks the task row (`SELECT … FOR UPDATE`) and commits
  once. Concurrent requests for the same task run one after another; a duplicate
  approval gets `409 already_decided`.
- Planning runs in three phases. The first moves the task to PLANNING and commits.
  The second calls the planner without holding a lock. The third re-locks the task and
  persists the result. A slow LLM call therefore never holds a lock. If the process
  dies during phase 2, the task stays in PLANNING (a known limitation; see
  security.md).
- `TRUNCATE` (used only by tests) bypasses the append-only triggers. Application code
  never updates or deletes those tables.

## 10. Security boundaries

The frontend, the planner output, and the task text are all untrusted. The backend
validates every request with schemas that reject unknown fields, enforces lifecycle
transitions, runs only allowlisted tools with strictly validated arguments, and
authorizes each action from trusted records. See [security.md](security.md).

## 11. Deployment topology

See [deployment.md](deployment.md). The API serves `/health` (liveness) and
`/health/ready` (database reachability).
