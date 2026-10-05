# KORA API — backend conventions

The backend of the KORA Internal Operations Platform. Current state, milestones and open decisions are in `docs/implementation/PROJECT_STATE.md`. Read it at the start of a session.

## Stack (approved; don't add or swap technologies without approval)

- Python 3.13, FastAPI, `uv` (project and dependencies), `src/` layout, package `kora_api`
- Config: `pydantic-settings`, using env vars with the `KORA_` prefix (see `.env.example`)
- Data: PostgreSQL, SQLAlchemy 2 async (asyncpg), Alembic. Local DB via `compose.yaml` (Docker Compose is for local PostgreSQL only)
- Tests: pytest + HTTPX (`AsyncClient` + `ASGITransport`, anyio marker)
- Quality: Ruff (lint + format), Pyright in strict mode

## Commands (run from `backend/`)

```bash
uv sync
uv run uvicorn kora_api.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
docker compose up -d postgres
uv run alembic upgrade head
uv run python -m kora_api.access.bootstrap <username>   # one-time first System Admin
```

All four checks (pytest, ruff check, ruff format --check, pyright) must pass before work is considered done. pytest needs the compose PostgreSQL running.

## Architecture

- **Modular monolith with domain-first vertical slices.** Each business domain gets its own package under `kora_api/`. That package owns its routes, schemas, services and persistence. Domains talk to each other only through explicit public interfaces, never through each other's internals.
- Create a domain package only when you implement real behavior for it. Don't create empty placeholder folders.
- No speculative abstractions: no generic base repositories, generic CRUD services or permission engines until a concrete need is approved.
- Keep `main.py` (the app factory) and route handlers thin. Logic belongs in the domain's services.
- `core/` holds cross-cutting infrastructure only (config, and the DB engine/session in `core/database.py`). It contains no business logic.
- All ORM models subclass `kora_api.core.database.Base`. Get sessions through the `get_db_session` dependency, and override it in tests. Never open a module-level session or connection.
- Schema changes go through Alembic migrations in `migrations/`. Register new model modules in `migrations/env.py` (`MODEL_MODULES`). Never run migrations on app startup. Migrations are append-only: never edit one that has been applied; add a new one.
- Tables use UUID primary keys and timezone-aware UTC timestamps. Get the current time from `kora_api.core.clock.utcnow()` so tests can freeze it.
- DB tests use the `db_session`/`db_client`/`client_factory` fixtures. These run against `kora_test` inside a rolled-back transaction. Never point tests at the development database.
- API routes are versioned under `/api/v1`. They are composed in `api/router.py` and `api/v1/router.py`.
- The app must start, and `/api/v1/health` must respond, without a database or other external services.
- API docs are enabled only in `local` and `test`, through `Settings.docs_enabled`. Never add a way to enable them in `staging` or `production`.

## Access & authentication (`kora_api.access`)

- Authentication uses a server-side session cookie (`kora_session`: HttpOnly, Secure). Unsafe methods also need an `X-CSRF-Token` header that matches the session's CSRF token.
- Guard normal routes with `CurrentAccount`. It enforces the temporary-password gate. `AuthenticatedSession` (no gate) is only for the sign-out, sign-out-all, current-account and change-password routes.
- Every credential failure returns the same generic 401. Never reveal whether a username exists.
- Never log or return passwords, password hashes, session tokens or CSRF tokens. 422 responses omit `input` (`core/errors.py`), and the engine hides SQL parameters.
- System Admin is a separate grant, not an organizational role, and gives no implicit access to operational data. The final active System Admin can never be deactivated or have the grant revoked.
- Policy values (password, session, throttle) live in `access/policy.py`. Change them only with approval.

## Domain rules that constrain design

- Authorization = role defaults + organizational scope + per-user overrides.
- Only a System Admin manages permissions and member administration.
- Preserve historical meaning. Prefer archival or deactivation over destructive deletion.
- Recruitment & Selection is a separate platform. Don't invent an integration contract with it.

## Working rules

- Don't invent business behavior or API contracts. Ask when the requirements are unclear.
- Never commit secrets or `.env`. Add new settings to `Settings` and `.env.example` with safe defaults.
- Write type-annotated code that passes Pyright strict mode. Every endpoint needs a focused test.
- Update `docs/implementation/PROJECT_STATE.md` at each meaningful milestone, and keep it concise and accurate.
- Keep completion reports concise: completed work, the verification result, and blockers or deviations only.
