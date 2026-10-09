# Deployment Plan

## 1. Objective

Deploy AI Agent Review Harness as a publicly accessible web application with a frontend, Python backend API, and persistent PostgreSQL database.

The deployment must support the primary demonstration workflow without requiring a paid LLM API.

## 2. Planned Hosting Architecture

- Frontend: Vercel.
- Backend: A hosting provider supporting persistent Python web services and Docker.
- Database: Managed PostgreSQL.
- Source control: GitHub.
- CI/CD: GitHub Actions.
- Local development: Python virtual environment initially, followed by Docker Compose.

Select specific providers after checking current pricing, free-tier restrictions, regional availability, persistent storage, and deployment requirements.

## 3. Local Development

The local environment will include:

- Python 3.11 virtual environment.
- FastAPI backend.
- React and TypeScript frontend.
- PostgreSQL database.
- Environment-based configuration.
- Automated backend tests.

Docker Compose will later be added to simplify local database and service setup.

## 4. Environment Configuration

Provide an .env.example file containing placeholder values for required configuration, including:

- Database connection URL.
- Application environment.
- Allowed frontend origin.
- Logging configuration.
- Optional LLM provider key.

Never commit real credentials or expose server-side secrets to the frontend.

Validate required configuration when the backend starts.

## 5. Database Deployment

Use managed PostgreSQL for persistent production data.

Provide:

- Version-controlled Alembic migrations.
- A documented migration procedure.
- Foreign-key constraints and appropriate indexes.
- A backup and recovery approach supported by the selected provider.

Do not reset production data automatically when the application starts.

## 6. Backend Deployment

The backend must provide:

- Health checks.
- Request validation.
- Consistent error responses.
- Database connection management.
- Structured logging.
- Request and execution timeouts.
- Explicit CORS configuration.
- Backend-enforced authorization.
- OpenAPI documentation.

Do not expose credentials, stack traces, or internal configuration through public endpoints.

## 7. Frontend Deployment

The frontend must:

- Use a configurable backend API URL.
- Handle loading, empty, success, and error states.
- Avoid exposing server-side secrets.
- Communicate with the deployed backend over HTTPS.
- Support desktop and mobile screen sizes.

Configure CORS for the actual deployed frontend origin.

## 8. CI/CD

GitHub Actions should run relevant checks on pull requests and appropriate pushes.

Planned checks include:

- Backend dependency installation.
- Python linting and type checks.
- Backend unit and integration tests.
- Frontend linting and type checks.
- Frontend production build.
- Authorization-related tests.

Deployment must occur only after required checks pass.

Store deployment credentials in the appropriate secret-management system.

## 9. Release Procedure

1. Run backend tests.
2. Run frontend checks and production build.
3. Build and verify the backend container.
4. Provision or verify PostgreSQL.
5. Configure environment variables.
6. Apply database migrations using a controlled procedure.
7. Deploy the backend.
8. Verify API health and database connectivity.
9. Deploy the frontend.
10. Test the full workflow through public HTTPS URLs.
11. Verify persistence across backend restarts.
12. Verify authorization and error handling.
13. Enable automated deployment after the initial release is verified.

## 10. Demo Mode

The application must support deterministic mock-agent demonstrations without an LLM key.

A reviewer should be able to create a task, inspect a plan, review assumptions, make a decision, inspect the audit timeline, and view clearly labelled demonstration data.

Demo data must not be presented as experimental results.

## 11. Monitoring and Recovery

Document the selected provider's health checks, logs, backup facilities, and recovery options.

Avoid logging credentials, tokens, or unnecessary personal information.

Define how failed deployments and database migration problems will be investigated and recovered.

## 12. Deployment Acceptance Criteria

- A public HTTPS frontend is available.
- The deployed backend API is accessible.
- PostgreSQL data persists across service restarts.
- The primary review workflow works in demo mode.
- Environment configuration and secrets are handled safely.
- Automated checks run in CI.
- The README contains verified URLs and setup instructions.
- Deployment and known limitations are documented.

## 13. Known Limitations

Hosting plans, pricing, free-tier availability, and regional support must be verified before selecting providers.

A public deployment does not by itself establish production readiness.