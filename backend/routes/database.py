Database health endpoint.

Verifies that the backend can connect to PostgreSQL.
"""

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.database import get_db


router = APIRouter(tags=["database"])


@router.get("/database/health")
def database_health(connection: Connection = Depends(get_db)) -> dict:
    """Verify PostgreSQL connectivity."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    return {"status": "ok"}
