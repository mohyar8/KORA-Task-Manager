from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.core.config import Settings
from kora_api.core.database import get_db_session
from kora_api.main import create_app

pytestmark = pytest.mark.anyio


def _app_with_probe() -> FastAPI:
    # Point at an unreachable database: providing a session must not open a connection.
    app = create_app(Settings(database_url=SecretStr("postgresql+asyncpg://x:x@127.0.0.1:1/x")))

    @app.get("/_probe")
    async def probe(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
        return {"session": type(session).__name__}

    return app


async def test_session_dependency_yields_async_session_without_connecting() -> None:
    app = _app_with_probe()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/_probe")

    assert response.json() == {"session": "AsyncSession"}
