from fastapi import APIRouter

from kora_api.access.router import router as access_router
from kora_api.api.v1 import health

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(access_router)
