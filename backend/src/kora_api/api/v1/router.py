from fastapi import APIRouter

from kora_api.access.admin_router import access_router, admin_router
from kora_api.access.router import router as auth_router
from kora_api.announcements.router import router as announcements_router
from kora_api.api.v1 import health
from kora_api.notifications.router import router as notifications_router
from kora_api.organization.router import members_router, units_router
from kora_api.tasks.router import series_router, tasks_router

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(auth_router)
router.include_router(access_router)
router.include_router(units_router)
router.include_router(members_router)
router.include_router(admin_router)
router.include_router(tasks_router)
router.include_router(series_router)
router.include_router(announcements_router)
router.include_router(notifications_router)
