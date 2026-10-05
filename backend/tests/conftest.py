import asyncio
import os
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from kora_api.core import clock
from kora_api.core.config import Settings
from kora_api.core.database import get_db_session
from kora_api.main import create_app

BACKEND_DIR = Path(__file__).resolve().parent.parent
# A dedicated database on the local compose PostgreSQL; never the development database.
TEST_DATABASE_URL = os.environ.get(
    "KORA_TEST_DATABASE_URL", "postgresql+asyncpg://kora:kora@localhost:5432/kora_test"
)

ClientFactory = Callable[[], AsyncClient]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client for tests that need no database."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- Database-backed tests ---------------------------------------------------------------------


async def _create_database_if_missing(url: URL) -> None:
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            found = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not found:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Create the test database if needed and migrate it to head (once per run)."""
    url = make_url(TEST_DATABASE_URL)
    if not (url.database or "").endswith("_test"):
        pytest.fail(f"Refusing to use non-test database {url.database!r}; name must end in _test.")
    asyncio.run(_create_database_if_missing(url))

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    command.upgrade(config, "head")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def db_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside an outer transaction that is rolled back after each test.

    Application commits only release savepoints, so tests never leave data behind.
    """
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def db_app(test_database_url: str, db_session: AsyncSession) -> FastAPI:
    app = create_app(Settings(environment="test", database_url=SecretStr(test_database_url)))

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _session_override
    return app


@pytest.fixture
async def client_factory(db_app: FastAPI) -> AsyncIterator[ClientFactory]:
    """Builds independent clients (separate cookie jars) against the same app and database."""
    clients: list[AsyncClient] = []

    def make() -> AsyncClient:
        # https so the Secure session cookie is stored and sent.
        ac = AsyncClient(transport=ASGITransport(app=db_app), base_url="https://test")
        clients.append(ac)
        return ac

    yield make
    for ac in clients:
        await ac.aclose()


@pytest.fixture
def db_client(client_factory: ClientFactory) -> AsyncClient:
    return client_factory()


class FrozenClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> FrozenClock:
    frozen = FrozenClock(clock.utcnow())
    monkeypatch.setattr(clock, "utcnow", lambda: frozen.now)
    return frozen
