# KORA Internal Operations Platform — Backend Project State

_Last updated: 2026-10-05 (Milestone 1)_

## Current phase

Foundation. A runnable, tested FastAPI skeleton exists. No business domain is implemented yet.

## Repository baseline

- Git root: `KORA-Task-Manager/`, branch `main`, no commits yet. The backend lives in `backend/`.
- Implemented: package `kora_api` (`src/` layout) with an app factory, settings, versioned router composition, and `GET /api/v1/health` (no DB). There is one HTTPX-based test.

## Confirmed technical decisions

- Python 3.13; FastAPI; `uv` for project and dependency management; `src/` layout; package `kora_api`.
- Architecture: a modular monolith with domain-first vertical slices.
- Configuration: `pydantic-settings`, using env vars prefixed `KORA_`. Optional `.env`; `.env.example` is committed.
- Tests: pytest + HTTPX (`AsyncClient` + `ASGITransport`, via anyio's pytest plugin).
- Quality: Ruff for lint and format; Pyright in strict mode.
- Data foundation (approved, **not yet installed or wired**): PostgreSQL, SQLAlchemy 2 async, Alembic.
- Runtime server: uvicorn.

## Functional scope

Five internal domains:

1. Access & accounts
2. Organization & members
3. Tasks, workspaces & analytics
4. Communication & reminders
5. Governance & audit

**Platform boundary:** Recruitment & Selection is a separate platform with its own entry point. It is not one of these domains.

## Critical rules affecting backend foundations

- **Authorization** = role defaults + organizational scope + per-user overrides.
- **System Admin alone** manages permissions and member administration.
- **Preserve historical meaning.** Prefer archival or deactivation over destructive deletion.
- **Recruitment & Selection stays separate.** Do not invent an integration contract with it.

## Unresolved technical decisions (do not guess; get explicit approval)

- Authentication mechanism (sessions vs tokens, identity provider, password handling)
- How authorization (role + scope + override) is modeled and enforced
- Audit/history storage strategy
- Background jobs and scheduling for reminders; notification delivery channels
- API conventions (error format, pagination, IDs, timestamps/timezones)
- Local PostgreSQL setup for development and tests
- Whether OpenAPI docs (`/docs`, `/openapi.json`) stay exposed outside local environments
- Deployment target, containerization, and CI

## Milestone status

| Milestone | Status |
|---|---|
| M0: Repository baseline and state record | Done |
| M1: FastAPI foundation (uv, config, health endpoint, tooling, tests) | Done |

## Next intended work

M2: the database foundation. Add the SQLAlchemy 2 async engine/session and the Alembic setup against PostgreSQL. Keep health independent of the DB. M2 adds no domain models. Before starting, decide how a local PostgreSQL instance will be provided for development and tests.
