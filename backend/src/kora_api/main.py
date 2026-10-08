from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kora_api.access.dependencies import register_access_error_handlers
from kora_api.announcements.service import visible_announcement_ids
from kora_api.api.router import api_router
from kora_api.core.config import Settings, get_settings
from kora_api.core.database import create_engine, create_session_factory
from kora_api.core.errors import register_error_handlers
from kora_api.organization import events as organization_events
from kora_api.organization.facts import SqlOrganizationFacts
from kora_api.tasks.series import visible_series_ids
from kora_api.tasks.service import on_membership_changed as tasks_on_membership_changed
from kora_api.tasks.service import visible_task_ids


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
    # Composition root: `access` consumes organization facts only through this interface.
    app.state.organization_facts = SqlOrganizationFacts()
    # Tasks drop assignees who become inactive or leave a task's scope (idempotent).
    organization_events.on_membership_changed(tasks_on_membership_changed)
    # Notifications re-check source access through these checkers (notifications never
    # imports the source modules).
    app.state.notification_sources = {
        "task": visible_task_ids,
        "task_series": visible_series_ids,
        "announcement": visible_announcement_ids,
    }
    register_error_handlers(app)
    register_access_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
