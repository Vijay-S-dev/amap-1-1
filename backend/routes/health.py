"""
Health endpoint.

Per docs/BACKEND.md §12 and §17:
- Verifies only that the FastAPI application is running.
- Must NOT require the database — database health is a separate,
  later concern once backend-database integration is approved.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}

