from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kora_api.api.router import api_router
from kora_api.core.config import Settings, get_settings
from kora_api.core.database import create_engine, create_session_factory
from kora_api.core.errors import register_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await engine.dispose()

    docs = settings.docs_enabled
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.session_factory = create_session_factory(engine)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
