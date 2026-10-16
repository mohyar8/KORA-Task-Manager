"""Vercel entrypoint: exposes the FastAPI `app` from the `src/` layout.

The application itself lives in `src/kora_api` (see `kora_api.main.create_app`); this file only
makes sure the package is importable when the platform runs the service from `backend/`.
Routes already live under `/api/v1/...`, so the root `vercel.json` forwards `/api/*` unchanged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from kora_api.main import app

__all__ = ["app"]
