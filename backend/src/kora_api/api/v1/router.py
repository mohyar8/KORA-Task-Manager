from fastapi import APIRouter

from kora_api.access.admin_router import access_router, admin_router
from kora_api.access.audit_router import router as audit_router
from kora_api.access.router import router as auth_router
from kora_api.announcements.router import router as announcements_router
from kora_api.api.v1 import health
from kora_api.calendar.router import router as calendar_router
from kora_api.league.router import router as league_router
from kora_api.messaging.router import router as messaging_router
from kora_api.notes.router import router as notes_router
from kora_api.notifications.router import router as notifications_router
from kora_api.organization.router import (
    directory_router,
    members_router,
    structure_router,
    units_router,
)
from kora_api.summary.router import router as summary_router
from kora_api.task_files.router import router as task_files_router
from kora_api.task_requests.router import router as task_requests_router
from kora_api.tasks.router import series_router, tasks_router

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(auth_router)
router.include_router(access_router)
router.include_router(units_router)
router.include_router(directory_router)
router.include_router(structure_router)
router.include_router(members_router)
router.include_router(admin_router)
router.include_router(audit_router)
router.include_router(tasks_router)
router.include_router(series_router)
router.include_router(announcements_router)
router.include_router(notifications_router)
router.include_router(calendar_router)
router.include_router(league_router)
router.include_router(notes_router)
router.include_router(messaging_router)
router.include_router(task_files_router)
router.include_router(summary_router)
router.include_router(task_requests_router)
