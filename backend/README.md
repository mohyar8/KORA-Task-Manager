# KORA API (backend)

Requires [uv](https://docs.astral.sh/uv/). uv provides Python 3.13 automatically.

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
