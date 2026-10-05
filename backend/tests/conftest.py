from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from kora_api.core.config import Settings
from kora_api.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
