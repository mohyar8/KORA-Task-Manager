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

API docs (`/docs`, `/redoc`, `/openapi.json`) are on only in the `local` and `test` environments, and always off in `staging` and `production`.
