# KORA API (backend)

Requires [uv](https://docs.astral.sh/uv/), which provides Python 3.13. The local database needs Docker with Compose.

Run all commands from `backend/`.

```bash
uv sync                                           # install
cp .env.example .env                              # optional local config
uv run uvicorn kora_api.main:app --reload         # run (http://127.0.0.1:8000/api/v1/health)
uv run pytest                                     # test (needs local PostgreSQL running)
uv run ruff check .                               # lint
uv run ruff format .                              # format (use --check to verify only)
uv run pyright                                    # type-check
```

## Database (local PostgreSQL)

```bash
docker compose up -d postgres                     # start (data persists in volume kora_pgdata)
docker compose ps                                 # verify: status should be "healthy"
uv run alembic upgrade head                       # apply migrations
uv run alembic current                            # verify migration state against the DB
uv run alembic revision --autogenerate -m "msg"   # create a migration from model changes
uv run alembic upgrade head --sql                 # check Alembic config offline (no DB needed)
docker compose down                               # stop (add -v to delete the data volume)
```

The app starts without a database. Migrations never run automatically.

Tests use a separate `kora_test` database on the same server. The suite creates it if it's missing and migrates it to head. Each test runs in a transaction that is rolled back afterwards, so the development database is never touched. Override the URL with `KORA_TEST_DATABASE_URL`; the database name must end in `_test`.

## First System Admin (one-time)

```bash
uv run python -m kora_api.access.bootstrap <username>
```

This prints a temporary password once. It expires in 7 days and must be changed at first sign-in. The command refuses to run again once any System Admin has ever existed.

## First organization structure

KORA and the PMO are seeded by migration. Creating Administrations and Teams requires the `organization.manage` permission, and System Admin carries no implicit access. So a System Admin first gives an account (possibly their own) an explicit, reasoned grant at KORA scope:

```
POST /api/v1/admin/accounts/{account_id}/overrides
{"permission": "organization.manage", "unit_id": "<KORA id>", "effect": "grant", "reason": "..."}
```

The KORA id is `6b0a0000-0000-4000-8000-000000000001`. That account then creates units through `/api/v1/organization/units`. Members are provisioned at `/api/v1/admin/members`.

## Tasks

Tasks live at `/api/v1/tasks`, and weekly series at `/api/v1/task-series`. Members get `task.view` and `task.create` at their role's unit, and leaders and managers get `task.manage` (see `PROJECT_STATE.md`). Due times must include a time-zone offset.

## Announcements and notifications

Announcements live at `/api/v1/announcements`; leaders and managers get `announcement.publish` and `announcement.manage` at their role's unit. In-app notifications and per-category preferences live at `/api/v1/notifications`.

## Calendar

Events and meetings live at `/api/v1/calendar/events`. `GET /api/v1/calendar?from=...&to=...` (times with an offset, at most 366 days) returns your events together with the due dates of open tasks you created or are assigned to.

## Audit log

Successful state changes are recorded in an append-only audit log (`audit_records`; a database trigger rejects updates and deletes). Only System Admins can read it, at `GET /api/v1/admin/audit-records` (newest first; `limit`/`cursor` paging; filters `occurred_from`/`occurred_to` with offsets, `action`, `actor_account_id`, `resource_type`, `resource_id`, `scope_unit_id`) and `GET /api/v1/admin/audit-records/{id}`. Records hold only short, allowlisted metadata, and reading them grants no access to the tasks, announcements, events or Members they describe. The log starts at migration `6b1e9c4d2a7f`; earlier changes are not backfilled.

API docs (`/docs`, `/redoc`, `/openapi.json`) are on only in the `local` and `test` environments, and always off in `staging` and `production`.

## Release verification

Run all of these from `backend/` with the compose PostgreSQL up. All must pass:

```bash
uv run pytest                                     # full suite, incl. tests/test_end_to_end.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run alembic check                              # models match the migrated dev database
```

To prove a clean install, use a new, disposable database (never `kora` or `kora_test`):

```bash
docker compose exec -T postgres psql -U kora -d postgres -c "CREATE DATABASE kora_disposable_check"
export KORA_DATABASE_URL=postgresql+asyncpg://kora:kora@localhost:5432/kora_disposable_check
uv run alembic upgrade head && uv run alembic check
uv run python -m kora_api.access.bootstrap firstadmin   # succeeds once
uv run python -m kora_api.access.bootstrap secondadmin  # must be refused
unset KORA_DATABASE_URL
docker compose exec -T postgres psql -U kora -d postgres -c "DROP DATABASE kora_disposable_check"
```

## Production configuration

- `KORA_ENVIRONMENT=production` (or `staging`) requires an explicit `KORA_DATABASE_URL` and `KORA_DEBUG=false`; otherwise startup fails. API docs are off.
- Session and CSRF cookies are always `Secure` (and the session cookie `HttpOnly`); there is no setting to relax this. The API must therefore be served over HTTPS.
- No CORS middleware is configured: browsers may call the API only from the same origin. Serve the frontend and `/api` from one origin (e.g. behind one reverse proxy); cross-origin access needs an approved requirement first.
- Run migrations (`alembic upgrade head`) and the one-time bootstrap manually; the app never does either on startup.

## Not in scope (deferred)

File uploads, chat and direct messages, email/push notifications, RSVP and attendance, recurring calendar events, external integrations, and Recruitment & Selection (a separate platform) are not implemented.

## Deploying on Vercel (multi-service project)

The repository root `vercel.json` deploys `backend/` (FastAPI, entrypoint `index.py`) and `frontend/` (Vite) as one project on one domain: `/api/*` goes to the backend unchanged (routes already live under `/api/v1`), everything else to the frontend. Same origin means the `Secure` cookies and CSRF header work without CORS.

Set these environment variables on the project (never commit them):

- `KORA_ENVIRONMENT=production`
- `KORA_DATABASE_URL=postgresql+asyncpg://…` — a hosted PostgreSQL (the app refuses to start in production with the local credentials).

Migrations and the first System Admin are **not** run by Vercel: run `uv run alembic upgrade head` and `uv run python -m kora_api.access.bootstrap <username>` once from a machine that can reach that database.
