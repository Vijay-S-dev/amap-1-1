"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from routes.database import router as database_router
from routes.health import router as health_router


api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(database_router)
