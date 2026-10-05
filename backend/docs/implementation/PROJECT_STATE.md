# KORA Internal Operations Platform — Backend Project State

_Last updated: 2026-10-05 (Milestone 3B)_

## Current phase

Access & accounts, part 1. The authentication and account-security foundation is implemented. Authorization (roles, permissions, scopes, overrides) is not yet.

## Repository baseline

- Git root: `KORA-Task-Manager/`, branch `main`. The backend lives in `backend/`.
- Implemented: package `kora_api` (`src/` layout) with an app factory, settings, versioned router composition, and `GET /api/v1/health` (no DB).
- Persistence: `core/database.py` provides the shared `Base` (with a constraint naming convention), a lazy async engine, a session factory on `app.state`, and an injectable `get_db_session` dependency. Alembic (async) lives in `migrations/` and reads `KORA_DATABASE_URL` (or an explicit `sqlalchemy.url`). `compose.yaml` defines a local PostgreSQL 17.
- Migrations: `8335857d616c` (access foundation): `user_accounts`, `auth_sessions`, `login_throttles`, `system_admin_grants`.
- `kora_api.access`:
  - Endpoints under `/api/v1/auth`: sign-in, sign-out, sign-out-all, me, change-password.
  - Argon2id hashing, server-side sessions, CSRF protection, a per-username login throttle, and the temporary-password gate (`CurrentAccount`).
  - A one-time bootstrap command for the first System Admin.
  - A final-System-Admin guard in the `deactivate_account` / `revoke_system_admin` services. These have no HTTP endpoints yet.

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
- Tables: UUID primary keys and timezone-aware UTC timestamps. Time comes from `core/clock.py`.
- Tests: a separate `kora_test` database on the compose server, migrated to head once per run. Each test runs in a rolled-back transaction.
- Accounts:
  - User Account is separate from Member.
  - Usernames: case-insensitive (stored lowercase), `[a-z0-9._-]`, 3–64 characters.
  - Passwords: Argon2id via `argon2-cffi`, 8–128 characters, no composition rules.
  - Temporary passwords: random, expire after 7 days, and force a password change.
- Sessions:
  - Opaque 256-bit tokens; only SHA-256 hashes are stored.
  - Cookie `kora_session`: HttpOnly, Secure (in every environment; browsers accept it on `localhost`), SameSite=Lax, Path=/api. The token is never returned in a response body.
  - CSRF uses a session-bound, non-secret token in the `kora_csrf` cookie (readable, Secure, SameSite=Strict, Path=/), echoed in the `X-CSRF-Token` header. Every authenticated unsafe request requires it; sign-in does not.
  - 8-hour idle timeout and 7-day absolute lifetime. Password change and sign-out-all revoke all sessions.
- No secret disclosure: 422 responses never echo submitted values, and the DB engine uses `hide_parameters=True` so SQL logs and errors omit bound values.
- Sign-in throttle: 5 failures per normalized username within 15 minutes locks it for 15 minutes (429 with `Retry-After`). This also applies to usernames that don't exist. Credential failures return the same generic 401.
- System Admin:
  - An append-only grant, separate from organizational roles, with no implicit operational-data access.
  - Bootstrap only through the CLI, and only if no grant ever existed.
  - The final active System Admin cannot be deactivated or revoked.

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

- How authorization (role + scope + override) is modeled and enforced. This includes deny/grant precedence, scope inheritance, and how scope references organization data that doesn't exist yet.
- Who can create, reset and deactivate accounts, and through which API (account provisioning)
- Audit/history storage strategy
- Background jobs and scheduling for reminders; notification delivery channels
- API conventions (error format, pagination, IDs, timestamps/timezones)
- Archival column conventions for future domain tables
- Cleanup and retention for expired sessions and stale throttle rows
- Deployment target, containerization, and CI

## Milestone status

| Milestone | Status |
|---|---|
| M0: Repository baseline and state record | Done |
| M1: FastAPI foundation (uv, config, health endpoint, tooling, tests) | Done |
| M2: Persistence foundation (SQLAlchemy async, Alembic, local PostgreSQL, docs toggle) | Done (verified against live PostgreSQL in M3B) |
| M3A: Identity & access plan | Done |
| M3B: Authentication & account-security foundation | Done |

## Next intended work

M3C (to be scoped): authorization foundation. This covers the permission catalog, organizational roles and their defaults, scope, user grant/deny overrides, and `require_permission` dependencies. It is blocked on the authorization decisions above, especially how scope relates to organization data.
