# API Reference

Interactive OpenAPI documentation is served at `/docs` when the backend is running.
This page summarizes the contract.

## Conventions

- JSON request and response bodies. Request bodies reject unknown fields.
- Errors always look like this:

  ```json
  {"error": {"code": "machine_readable_code", "message": "Human readable", "details": null}}
  ```

| Status | Typical codes |
|---|---|
| 404 | `not_found`, `action_not_found` |
| 405 | `method_not_allowed` |
| 409 | `invalid_transition`, `invalid_state`, `already_decided`, `action_blocked`, `review_not_required`, `action_required`, `open_questions`, `review_incomplete`, `nothing_to_execute`, `nothing_to_approve`, `decision_not_available`, `not_retryable` |
| 422 | `validation_error` (details list each field location and message) |
| 429 | `rate_limited` (POST requests only; includes a `Retry-After` header) |
| 500 | `internal_error` (generic message; details are logged server-side) |
| 503 | `database_unavailable` |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness. Does not check the database |
| GET | `/health/ready` | Readiness. Checks database connectivity |
| GET | `/api/v1/catalog` | Tools, reason-code explanations, authorization reasons, example tasks |
| POST | `/api/v1/tasks` | Create a task: `{title, description, review_mode?: STRUCTURED \| BASELINE}` |
| GET | `/api/v1/tasks?status=&limit=&offset=` | List tasks, newest first |
| GET | `/api/v1/tasks/{id}` | Task detail: current run with assumptions and actions, run history, decisions, `available_operations` |
| POST | `/api/v1/tasks/{id}/plan` | Run the planner (`CREATED` only) |
| POST | `/api/v1/tasks/{id}/reviews` | Record a decision: `{decision, action_id?, rationale?, reviewer?}` |
| POST | `/api/v1/tasks/{id}/execute` | Structured mode: start execution once the review is complete |
| POST | `/api/v1/tasks/{id}/retry-planning` | Retry after a planning failure |
| POST | `/api/v1/tasks/{id}/cancel` | Cancel (`CREATED` or `AWAITING_REVIEW`): `{reason?}` |
| GET | `/api/v1/tasks/{id}/events` | Audit events in order |

### Review decisions

| Mode | Decision | `action_id` | `rationale` | Effect |
|---|---|---|---|---|
| Structured | `APPROVE` | required | optional | Marks the action approved. Does not execute it |
| Structured | `REJECT` | required | required | The action will never execute; the task continues |
| Structured | `REQUEST_REVISION` | optional | required | Supersedes the plan; the agent re-plans using the feedback |
| Structured | `REQUEST_CLARIFICATION` | optional | required | Supersedes the plan; the agent re-plans using the answer |
| Baseline | `APPROVE` | must be absent | optional | Approves the whole plan and executes it |
| Baseline | `REJECT` | must be absent | required | Stops the task (`CANCELLED`) |

`available_operations` on the task detail lists what a client may attempt next. It is
advisory only: the server re-validates every operation.

### Action fields that keep stages distinct

| Field | Values |
|---|---|
| `risk_level` | LOW, MEDIUM, HIGH, FORBIDDEN |
| `review_state` | NOT_REQUIRED, PENDING, APPROVED, REJECTED, BLOCKED, SUPERSEDED |
| `authorization_state` | NOT_EVALUATED, GRANTED, DENIED (plus `authorization_reason`) |
| `execution_state` | NOT_STARTED, SUCCEEDED, FAILED, SKIPPED |
| `verification_state` | NOT_RUN, PASSED, FAILED |
