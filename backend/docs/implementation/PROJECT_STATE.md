# KORA Internal Operations Platform — Backend Project State

_Last updated: 2026-10-05 (Milestone 2)_

## Current phase

Foundation. A runnable, tested FastAPI skeleton with a persistence foundation exists. No business domain, table or migration revision is implemented yet.

## Repository baseline

- Git root: `KORA-Task-Manager/`, branch `main`, no commits yet. The backend lives in `backend/`.
- Implemented: package `kora_api` (`src/` layout) with an app factory, settings, versioned router composition, and `GET /api/v1/health` (no DB).
- Persistence: `core/database.py` provides the shared `Base` (with a constraint naming convention), a lazy async engine, a session factory on `app.state`, and an injectable `get_db_session` dependency. Alembic (async) lives in `migrations/` and reads `KORA_DATABASE_URL`; there are no revisions yet. `compose.yaml` defines a local PostgreSQL 17.

## Confirmed technical decisions

- Python 3.13; FastAPI; `uv` for project and dependency management; `src/` layout; package `kora_api`.
- Architecture: a modular monolith with domain-first vertical slices.
- Configuration: `pydantic-settings`, using env vars prefixed `KORA_`. Optional `.env`; `.env.example` is committed.
- Tests: pytest + HTTPX (`AsyncClient` + `ASGITransport`, via anyio's pytest plugin).
- Quality: Ruff for lint and format; Pyright in strict mode.
- Data: PostgreSQL (production), SQLAlchemy 2 async with asyncpg, and Alembic. The engine connects lazily, so the app starts without a DB. Migrations are run manually and never on startup.
- Local infrastructure: Docker Compose, for local PostgreSQL only.
- API docs: enabled only when `KORA_ENVIRONMENT` is `local` or `test`, and disabled in `staging` and `production`. There is no override.
- `.serena/` is git-ignored at the repo root.
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
- Test-database strategy for DB-backed tests (separate DB or schema, transaction rollback, fixtures)
- Primary key type for tables (e.g. UUID vs bigint); timestamp and soft-delete/archival column conventions
- Deployment target, containerization, and CI

## Milestone status

| Milestone | Status |
|---|---|
| M0: Repository baseline and state record | Done |
| M1: FastAPI foundation (uv, config, health endpoint, tooling, tests) | Done |
| M2: Persistence foundation (SQLAlchemy async, Alembic, local PostgreSQL, docs toggle) | Done. Live DB not yet verified: Docker is not installed on the dev machine |

## Next intended work

First, verify M2 against a live database: install Docker, run `docker compose up -d postgres`, then `uv run alembic upgrade head`.

M3 (to be scoped): the first domain slice, likely Access & accounts. It is blocked on these decisions: the authentication mechanism, the authorization model, the primary key, timestamp and archival conventions, and the test-database strategy.
