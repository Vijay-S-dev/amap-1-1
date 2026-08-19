"""
API v1 router aggregation.

Per docs/BACKEND.md #11, this establishes ONLY the versioning/routing
foundation. Final business endpoint paths must not be invented here
before their API contracts are defined and approved.
"""

from fastapi import APIRouter

from routes.v1.health import router as health_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)

