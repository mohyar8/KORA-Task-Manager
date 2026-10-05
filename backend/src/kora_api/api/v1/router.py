from fastapi import APIRouter

from kora_api.api.v1 import health

router = APIRouter(prefix="/v1")
router.include_router(health.router)
