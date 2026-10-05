from fastapi import FastAPI

from kora_api.api.router import api_router
from kora_api.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(api_router)
    return app


app = create_app()
