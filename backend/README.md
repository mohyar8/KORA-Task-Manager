# KORA API (backend)

Requires [uv](https://docs.astral.sh/uv/), which provides Python 3.13. The local database needs Docker with Compose.

Run all commands from `backend/`.

```bash
uv sync                                           # install
cp .env.example .env                              # optional local config
uv run uvicorn kora_api.main:app --reload         # run (http://127.0.0.1:8000/api/v1/health)
uv run pytest                                     # test
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

API docs (`/docs`, `/redoc`, `/openapi.json`) are on only in the `local` and `test` environments, and always off in `staging` and `production`.
