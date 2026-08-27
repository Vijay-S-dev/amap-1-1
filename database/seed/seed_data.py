"""
Python Database Seeder for AMAP.
Executes raw SQL seeds or populates PostgreSQL / Supabase via psycopg.
"""

import os
from pathlib import Path
from typing import Optional
import psycopg

SEED_SQL_PATH = Path(__file__).resolve().parent / "seed.sql"


def run_seed(db_url: Optional[str] = None) -> bool:
    """Execute seed.sql on target database."""
    connection_url = db_url or os.getenv("DATABASE_URL", "postgresql://amap_user:change_me@localhost:5432/amap")

    if not SEED_SQL_PATH.exists():
        print(f"Error: Seed file not found at {SEED_SQL_PATH}")
        return False

    with open(SEED_SQL_PATH, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print(f"Connecting to database: {connection_url.split('@')[-1] if '@' in connection_url else connection_url}")
    try:
        with psycopg.connect(connection_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_content)
        print("Database seeded successfully with Acme Motors demo scenario.")
        return True
    except Exception as e:
        print(f"Seeding failed or database unreachable: {e}")
        return False


if __name__ == "__main__":
    run_seed()
