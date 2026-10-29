# AI Agent Review Harness — Requirements

## 1. Problem Statement

AI coding agents can make incorrect assumptions, propose risky changes, and interrupt developers unnecessarily. This project investigates a structured review workflow that balances agent autonomy with human oversight.

## 2. Primary User

A software developer supervising an AI coding agent during a software engineering task.

## 3. Product Goal

Build an application that allows a developer to inspect an agent's proposed plan, review assumptions, make approval decisions, control permitted tool execution, and inspect a persistent audit history.

## 4. MVP Functional Requirements

### FR-01: Task Management
Users can create, retrieve, and inspect tasks with requirements, constraints, status, and timestamps.

### FR-02: Agent Planning
A deterministic mock agent generates a structured plan containing proposed actions, assumptions, missing information, and potential risks.

### FR-03: Assumption Review
Users can inspect assumptions, review supporting evidence, correct assumptions, and request clarification.

### FR-04: Human Review
Users can approve or reject proposals, request clarification, and request revision when permitted by the review policy.

*Change (2026-10-29):* "defer" was dropped; the agreed decision set is approve, reject, request clarification, and request revision.

### FR-05: Review Policy
A transparent rule-based policy evaluates risk, reversibility, evidence, unresolved assumptions, and authorization requirements.

### FR-06: Controlled Execution
The system executes only allowlisted mock tools. Consequential actions require explicit authorization enforced by the backend.

### FR-07: Audit History
The system records task changes, review decisions, tool execution attempts, execution results, and final outcomes.

### FR-08: Evaluation Dashboard
Users can inspect per-task execution history and audit events in the UI. Evaluation results are delivered as a reproducible report (`docs/evaluation-results.md`, `evaluation/results/`) rather than an in-app dashboard.

*Change (2026-10-29):* the in-app evaluation dashboard was replaced by the committed report; see docs/progress.md.

## 5. Initial Task States

- CREATED
- PLANNING
- AWAITING_REVIEW
- RUNNING
- COMPLETED
- FAILED
- CANCELLED

The backend must validate permitted state transitions. Clients cannot set arbitrary task states.

## 6. Non-Functional Requirements

- Validate external input using typed schemas.
- Enforce authorization on the server.
- Persist application records in PostgreSQL.
- Maintain version-controlled database migrations.
- Provide automated backend tests.
- Support deterministic demo mode without an LLM API key.
- Keep secrets out of source control and application logs.
- Provide consistent error responses and structured logging.
- Support responsive, accessible frontend interactions.
- Document local setup, deployment, and security limitations.

## 7. Security Requirements

- Treat model-generated content as untrusted.
- Use strict tool allowlists and input validation.
- Never execute arbitrary model-generated shell commands.
- Require backend authorization for consequential actions.
- Record review decisions and execution attempts.
- Protect credentials and restrict cross-origin requests to approved frontend origins.

## 8. Initial Scope Exclusions

- Unrestricted shell execution.
- Autonomous production changes.
- Multi-agent orchestration.
- Kubernetes or unnecessary distributed infrastructure.
- Mandatory paid LLM integration.
- Claims of statistically validated improvements without evaluation evidence.

## 9. MVP Acceptance Criteria

1. A user can create a task and retrieve it.
2. The mock agent generates a structured plan.
3. The user can inspect and review a flagged assumption.
4. The backend validates review decisions and task state transitions.
5. An approved, permitted mock action can execute.
6. Rejected or unauthorized actions cannot execute.
7. Task history and review decisions persist across backend restarts.
8. The audit timeline accurately distinguishes proposed, approved, and executed actions.
9. The primary workflow works without an LLM API key.
10. Automated tests verify core workflow and authorization behavior.
11. The application can be deployed with a public HTTPS frontend, API, and persistent database.

## 10. Evaluation Principle

The project will compare a basic approval-or-stop workflow with the proposed structured review workflow using predefined tasks and success criteria.

Potential measures include task success, errors, intervention count, review time, rework, and human understanding.

No experimental results will be fabricated. Any human-participant study will require appropriate approval, consent, and privacy safeguards before data collection.
