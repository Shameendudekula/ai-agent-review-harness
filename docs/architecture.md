# System Architecture

## 1. Project Overview

AI Agent Review Harness is a modular monolith that allows developers to supervise AI-assisted software engineering tasks.

The system exposes agent plans, assumptions, review decisions, execution results, and audit history through a web application.

The first version uses a deterministic mock agent. Real LLM integration will be added later.

## 2. Technology Stack

- Frontend: React, TypeScript, Vite
- Backend: Python 3.11, FastAPI, Pydantic
- ORM: SQLAlchemy
- Database migrations: Alembic
- Database: PostgreSQL
- Backend testing: pytest
- Version control: Git and GitHub
- Containers: Docker and Docker Compose
- CI/CD: GitHub Actions
- Planned hosting: Vercel frontend, Python API hosting, managed PostgreSQL

Hosting providers will be selected after checking their current pricing and limits.

## 3. Component Responsibilities

- **Frontend:** Task creation, task details, review controls, history and metrics.
- **API layer:** HTTP request validation, routing and consistent responses.
- **Application services:** Task workflows and orchestration.
- **Domain layer:** Task states, valid transitions and business rules.
- **Agent adapter:** Common interface for mock and real agents.
- **Review policy:** Risk assessment and review requirements.
- **Tool execution:** Restricted actions with backend authorization.
- **Persistence:** Database access and migrations.
- **Audit and evaluation:** Event history and measured outcomes.

## 4. Task Lifecycle

Initial states:

- CREATED
- PLANNING
- AWAITING_REVIEW
- RUNNING
- COMPLETED
- FAILED
- CANCELLED

Proposed transitions:

- CREATED -> PLANNING
- PLANNING -> AWAITING_REVIEW
- PLANNING -> RUNNING when policy permits execution without review
- PLANNING -> FAILED when planning cannot recover
- AWAITING_REVIEW -> RUNNING after required approval and authorization
- AWAITING_REVIEW -> PLANNING when a proposal is rejected for revision
- AWAITING_REVIEW -> PLANNING when clarification requires a revised plan
- AWAITING_REVIEW -> CANCELLED when cancellation is accepted
- RUNNING -> AWAITING_REVIEW at a required checkpoint
- RUNNING -> COMPLETED after success criteria are verified
- RUNNING -> FAILED when execution or verification fails
- RUNNING -> CANCELLED after safe cancellation handling

The backend must reject transitions not explicitly permitted by the domain rules.

COMPLETED, FAILED, and CANCELLED are terminal states in the initial version. Retrying a failed task requires an explicit operation.

Rejecting a proposal does not automatically cancel or fail the task. Review decisions and task status are separate concepts.

Approval, authorization, execution, and outcome verification are distinct steps.

## 5. Initial Database Entities

- **tasks:** Task description, requirements, constraints, status and timestamps.
- **agent_runs:** Planning and execution attempts associated with tasks.
- **assumptions:** Assumptions, supporting evidence, consequences and review status.
- **review_decisions:** Decisions, associated proposals, rationale and timestamps.
- **execution_events:** Ordered task events, decisions, execution attempts and results.

Relationships:

- One task can have multiple agent runs.
- One task can have multiple assumptions.
- One task can have multiple review decisions.
- One task can have multiple execution events.
- Related records must reference their parent task.

Use foreign keys, timestamps, validated status values and appropriate indexes.

Introduce additional entities only when needed by an implemented feature.

## 6. Security Boundaries

The frontend is not a security boundary.

The backend independently validates task transitions, review decisions, tool permissions and execution requests.

Model-generated content is untrusted. The initial system must not execute arbitrary shell commands or allow unrestricted filesystem access.

Consequential actions require explicit approval enforced by the backend.

## 7. Deployment Architecture

Planned deployment:

- Vercel for the frontend.
- A persistent Python web service for the API.
- Managed PostgreSQL for persistent records.
- GitHub for source control.
- GitHub Actions for automated checks.

During local development, the frontend and backend communicate over HTTP. Docker Compose will later provide a reproducible environment including PostgreSQL.

In production, the frontend communicates with the backend over HTTPS. The backend connects to PostgreSQL using protected configuration.

## 8. Key Design Decisions

- **Modular monolith:** Reduces initial development and deployment complexity.
- **Deterministic mock agent:** Enables repeatable demonstrations without paid API access.
- **Rule-based review policy:** Makes decisions inspectable and testable.
- **PostgreSQL:** Provides relational integrity for tasks, decisions and history.
- **Backend authorization:** Prevents client-side or model-generated instructions from bypassing permissions.
- **Optional LLM integration:** Keeps demo mode functional without provider credentials.

## 9. Acceptance Criteria

- Component responsibilities are documented.
- Task states and permitted transitions are specified.
- Initial database entities and relationships are documented.
- Frontend, backend, database and hosting topology are described.
- Security boundaries and key design decisions are explicit.
- The architecture supports deterministic demonstrations and automated testing.