from typing import Literal

import pytest
from httpx import ASGITransport, AsyncClient

from kora_api.core.config import Settings
from kora_api.main import create_app

pytestmark = pytest.mark.anyio

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

Environment = Literal["local", "test", "staging", "production"]


async def _status_codes(settings: Settings) -> list[int]:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return [(await client.get(path)).status_code for path in DOC_PATHS]


@pytest.mark.parametrize("environment", ["local", "test"])
async def test_docs_available(environment: Environment) -> None:
    assert await _status_codes(Settings(environment=environment)) == [200, 200, 200]


@pytest.mark.parametrize("environment", ["staging", "production"])
async def test_docs_disabled(environment: Environment) -> None:
    assert await _status_codes(Settings(environment=environment)) == [404, 404, 404]


@pytest.mark.parametrize("environment", ["staging", "production"])
async def test_docs_cannot_be_reenabled_via_env(
    environment: Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KORA_ENVIRONMENT", environment)
    monkeypatch.setenv("KORA_API_DOCS_ENABLED", "true")
    assert await _status_codes(Settings()) == [404, 404, 404]
