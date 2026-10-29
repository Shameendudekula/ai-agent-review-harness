# AI Agent Review Harness

**A human-in-the-loop review system for reliable AI-assisted software engineering.**

## Overview

AI coding agents can make incorrect assumptions, propose risky changes, and interrupt developers unnecessarily.

AI Agent Review Harness is an independent portfolio project exploring how structured human oversight can balance agent autonomy, task reliability, and review effort.

The application is designed to expose agent plans, assumptions, proposed actions, review decisions, execution outcomes, and audit history.

**Project status:** Backend foundation in progress (FastAPI app with a tested health endpoint). No workflow features are implemented yet.

This repository does not yet represent a completed or deployed application.

## Goals

- Make agent assumptions and proposed actions visible.
- Support human approval, rejection, clarification, and revision.
- Apply a transparent, rule-based review policy.
- Restrict tool execution through backend authorization.
- Maintain a persistent audit history.
- Evaluate review workflows using repeatable tasks and predefined metrics.
- Provide a public demonstration that works without a paid LLM API.

## Planned Features

1. Task creation and tracking.
2. Deterministic mock-agent planning.
3. Structured assumption and risk review.
4. Human approval and clarification workflow.
5. Restricted mock-tool execution.
6. Persistent audit events.
7. Evaluation dashboard.
8. Optional real LLM integration.
9. Automated tests and CI/CD.
10. Public deployment.

These features are planned and must not be assumed to be implemented until verified.

## Technology Stack

| Layer | Planned technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python 3.11, FastAPI, Pydantic |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Database | PostgreSQL |
| Backend tests | pytest |
| Version control | Git and GitHub |
| Containers | Docker and Docker Compose |
| CI/CD | GitHub Actions |
| Frontend hosting | Vercel |
| Backend and database hosting | Providers to be selected |

## Architecture

The planned architecture is a modular monolith.

The frontend communicates with the FastAPI backend. The backend coordinates task workflows, agent planning, review policies, restricted tool execution, persistence, and audit events.

A deterministic mock agent will be implemented first. A provider-independent adapter will allow optional LLM integration later.

See [Architecture](docs/architecture.md) for component responsibilities, lifecycle rules, database entities, and deployment topology.

## Repository Structure

```text
ai-agent-review-harness/
├── backend/
├── frontend/
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── security.md
│   ├── evaluation-plan.md
│   └── deployment.md
├── .github/
├── .env.example
├── docker-compose.yml
└── README.md
```

The backend, frontend, and deployment files will be introduced as their modules are implemented. This tree describes the intended structure, not the current repository contents.

## Documentation

- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Security Design](docs/security.md)
- [Evaluation Plan](docs/evaluation-plan.md)
- [Deployment Plan](docs/deployment.md)

## Development Status

| Module | Status |
|---|---|
| Project setup and design | Done |
| Backend foundation | In progress |
| Task management API | Not started |
| Agent planning engine | Not started |
| Human review and policy engine | Not started |
| Safe execution and audit history | Not started |
| Frontend | Not started |
| Testing and security verification | Not started |
| LLM integration | Not started |
| Evaluation | Not started |
| Deployment and CI/CD | Not started |
| Portfolio documentation and demonstration | Not started |

## Local Development

Requires Python 3.11. From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

The API then serves `GET http://127.0.0.1:8000/health` and interactive docs at `/docs`.

Frontend and database setup will be added when those components exist.

## Testing

```bash
pytest
```

The suite currently contains a single health-endpoint test.

## Security

The planned design treats model-generated content as untrusted and requires backend-enforced authorization for tool execution.

The initial version will use restricted mock tools rather than unrestricted shell execution.

See [Security Design](docs/security.md) for trust boundaries, authorization rules, secrets handling, and known limitations.

## Evaluation

The project proposes a comparison between a basic approval-or-stop workflow and a structured review workflow.

Potential metrics include task success, error severity, intervention count, review time, rework, and detection of incorrect assumptions.

No experimental findings or performance improvements are claimed at this stage.

See [Evaluation Plan](docs/evaluation-plan.md).

## Deployment

The target is a public HTTPS frontend, a deployed Python API, and persistent PostgreSQL storage.

Hosting providers will be selected after checking pricing, resource limits, regional availability, and operational requirements.

See [Deployment Plan](docs/deployment.md).

Live URLs will be added only after deployment and smoke testing have been completed successfully.

## Contributions and Project Ownership

This is an independently developed portfolio project. Its purpose is to demonstrate software engineering, AI oversight, security-conscious design, testing, and reproducible evaluation.

Project ownership and individual contributions will be described honestly as implementation progresses.

## License

A license has not yet been selected. Licensing will be decided before public distribution of the completed project.
