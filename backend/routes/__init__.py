"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from routes.actions import router as actions_router
from routes.admin import router as admin_router
from routes.assistance import router as assistance_router
from routes.auth import router as auth_router
from routes.database import router as database_router
from routes.gestures import router as gestures_router
from routes.health import router as health_router
from routes.interactions import router as interactions_router
from routes.multimodal import router as multimodal_router
from routes.organization_management import router as organization_management_router
from routes.permissions import router as permissions_router
from routes.personalization import router as personalization_router
from routes.readiness import router as readiness_router
from routes.sessions import router as sessions_router
from routes.supervisor import router as supervisor_router
from routes.tasks import router as tasks_router
from routes.voice import router as voice_router


api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(database_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(readiness_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(organization_management_router)
api_v1_router.include_router(supervisor_router)
api_v1_router.include_router(sessions_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(actions_router)
api_v1_router.include_router(interactions_router)
api_v1_router.include_router(personalization_router)
api_v1_router.include_router(permissions_router)
api_v1_router.include_router(assistance_router)
api_v1_router.include_router(gestures_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(multimodal_router)
