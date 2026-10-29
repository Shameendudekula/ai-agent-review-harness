# Security Design

This document describes the controls that are implemented and the tests that check
them. It also lists the residual risks that remain. Passing tests do not make the
application production-secure; see §9.

## 1. Objective

An agent may *propose* anything. Nothing it proposes may run unless the backend
authorizes it from trusted records, immediately before execution, and the action uses
an allowlisted tool with valid arguments. Human approval is one input to that
decision, not a substitute for it.

## 2. Trust boundaries

| Component | Trust | Why |
|---|---|---|
| Browser / frontend | Untrusted | Any client can send any request; the UI is a convenience |
| Task text, reviewer text | Untrusted | User input; may contain injection attempts |
| Planner output (mock or LLM) | Untrusted | Parsed and validated, never executed directly |
| Backend policy and tool registry | Trusted | Code under version control |
| `review_decisions`, `audit_events` | Trusted history | Append-only, enforced by database triggers |
| Cached state columns on `proposed_actions` | Display only | Never used for authorization |
| LLM provider | External | Key held server-side; failures are contained |

## 3. Controls and their tests

| Control | Implementation | Tests |
|---|---|---|
| Strict input validation; unknown fields rejected (no `"approved": true` smuggling) | Pydantic models with `extra="forbid"` | `test_invalid_create_requests_are_rejected`, `test_client_cannot_forge_approval_fields` |
| Agent output validated before storage; untrusted output never echoed in errors | `AgentPlan` schema; error summaries list field locations only | `test_invalid_plans_are_rejected`, `test_planner_output_with_wrong_shape_is_rejected` |
| The agent cannot approve itself or declare an action safe | No approval fields in the plan schema; the agent's risk estimate can only raise risk | `test_agent_can_raise_but_not_lower_risk`, `test_invalid_plans_are_rejected` |
| Tool allowlist; strict argument schemas; no shell, filesystem, or network tools | `tools/registry.py` (7 simulated tools) | `test_registry_contains_only_mock_tools`, `test_unknown_tool_is_forbidden`, `test_invalid_arguments_are_forbidden` |
| Forbidden actions cannot be approved and never execute | Policy state BLOCKED; review API returns 409 `action_blocked`; authorization denies again | `test_blocked_action_cannot_be_approved`, `test_forbidden_actions_are_denied_even_with_approval` |
| Authorization just before execution, derived from decision records rather than state columns | `policy/authorization.py` | `test_forged_review_state_column_does_not_authorize`, `test_tampered_review_state_does_not_authorize_execution` |
| Rejected actions never execute; stale or cross-task decisions do not apply | Decision lookup scoped to the current run and action | `test_rejection_wins_over_approval`, `test_approval_from_a_previous_run_does_not_carry_over`, `test_decision_for_action_of_another_task_is_rejected` |
| Explicit lifecycle; invalid transitions rejected | `domain/lifecycle.py`, DB CHECK constraints | `test_undocumented_transitions_are_rejected`, `test_database_constraint_rejects_invalid_status` |
| Duplicate or concurrent operations | Row lock per task; state checks; at most one execution per action | `test_duplicate_decision_is_rejected`, `test_execute_is_not_repeatable` |
| Execution failures fail closed and are not retried blindly | Stop at the first failure; only planning failures are retryable | `test_execution_failure_is_recorded_and_not_retryable`, `test_unexpected_tool_result_fails_execution` |
| Tamper-resistant history | Append-only triggers on `audit_events` and `review_decisions` | `test_audit_and_decision_tables_are_append_only` |
| Prompt injection does not grant permissions | Injected instructions can only change *proposals*, which still pass policy and authorization; the LLM prompt delimits untrusted text | `test_prompt_injection_cannot_execute_unlisted_tool` (both modes), e2e `prompt injection` |
| No internal details in errors | Generic 500 and 503 responses; details logged server-side | `test_unhandled_error_returns_generic_500`, `test_database_outage_returns_503_without_details`, `test_tool_crash_does_not_leak_internal_error` |
| Planner and provider failures contained | `PlannerError` mapping; task fails at PLANNING and is retryable | `test_planner_failures_are_contained`, `test_provider_errors_become_safe_planner_errors` |
| Secrets server-side only | `SecretStr`; never in responses or the bundle | `test_api_key_is_not_exposed_in_repr`, `test_no_secrets_in_public_responses`; bundle scan (§6) |
| Configuration validated at startup | Required `DATABASE_URL`; key required when `PLANNER=anthropic` | `test_missing_database_url_fails_fast`, `test_llm_planner_requires_api_key` |
| CORS allowlist; only GET/POST and `Content-Type` | `CORSMiddleware` from `CORS_ALLOWED_ORIGINS` | `test_cors_allows_only_configured_origins` |
| Rate limiting on state-changing requests | In-memory sliding window per client IP | `test_rate_limit_applies_to_state_changing_requests` |
| LLM cost bound | `max_tokens`, timeout, at most 2 attempts | `test_valid_response_becomes_validated_plan` (checks request parameters) |

## 4. Prompt injection

Prompt injection is **mitigated, not eliminated.** An attacker who controls the task
text can influence what an LLM *proposes*: different plans, misleading descriptions,
or understated risk. The design limits what such influence can achieve:

- Only allowlisted tools with schema-valid arguments can run, whatever is proposed.
- Risk comes from trusted tool metadata, so an understated risk is ignored.
- Executing a state-changing action in structured mode needs a recorded human
  approval.
- Text such as "this is pre-approved" carries no authority anywhere in the system.

What remains: a manipulated plan could propose an *allowlisted* action with harmful but
valid arguments, together with a convincing description. Whether that is caught
depends on the reviewer. This is the core reason the review workflow exists, and also
why it is not sufficient on its own (see evaluation-results.md, approve-all reviewer).

## 5. Data and logging

- Audit payloads store decisions, reason codes, tool names, and simulated results.
  They do not store credentials. Reviewer rationale is stored as typed.
- LLM run metadata stores the model, request ID, token counts, and stop reason. It
  never stores the API key.
- Server logs record request paths and exception traces. Request bodies are not
  logged.

## 6. Secrets

- Real values live only in `.env` (git-ignored) or the hosting provider's
  environment settings. `.env.example` holds placeholders.
- The frontend receives only `VITE_API_BASE_URL`, which is public. Checked by scanning
  the production bundle for configuration names (`ANTHROPIC`, `DATABASE_URL`,
  `postgresql`, `sk-ant`): none found on 2026-10-29.
- Git history scanned for API-key patterns on 2026-10-29: none found.

## 7. Authentication: a deliberate demo limitation

The public demo has **no authentication**:

- Anyone with the URL can create tasks and record decisions.
- The reviewer name is a self-declared label, not an identity.
- All data is visible to all visitors. The UI states this in a banner.

This is acceptable only because every tool is simulated and no real system can be
affected. Mitigations for the demo are input size limits, rate limiting, and the
absence of any real side effects.

For any non-demo use, the minimum would be authenticated users, per-user task
ownership checks on every endpoint, reviewer identity tied to the authenticated user,
and a rule that the task creator cannot approve their own high-risk actions.

## 8. Reliability notes

- Each operation is one transaction under a task row lock. A database failure rolls
  the operation back and returns 503.
- Planning releases the lock while the planner runs. If the process crashes during
  that window, the task remains in PLANNING; there is no recovery job yet.
- The rate limiter's state is held in each process, so it resets on restart and is
  not shared between instances.

## 9. Not established

- No penetration test, threat-model review by a third party, or dependency audit
  beyond `npm audit` and `pip check`.
- No isolation for real code execution: none is needed, because none exists. Adding
  real tools would require sandboxing, egress control, and a new threat model.
- Prompt-injection robustness of a real LLM has not been measured.
