from fastapi import APIRouter

from kora_api.api.v1.router import router as v1_router

api_router = APIRouter(prefix="/api")
api_router.include_router(v1_router)
