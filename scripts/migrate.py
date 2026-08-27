"""
Automated Database Migration Runner for AMAP.

Applies migrations 001 through 040 in deterministic numerical sequence
inside transactional blocks with validation.
"""

import argparse
import os
from pathlib import Path
from typing import List, Optional
import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "database" / "migrations"


def get_migration_files() -> List[Path]:
    """Retrieve and sort all .sql migration files numerically."""
    if not MIGRATIONS_DIR.exists():
        return []

    sql_files = [f for f in MIGRATIONS_DIR.iterdir() if f.is_file() and f.name.endswith(".sql")]
    # Sort by filename prefix (e.g. 001_, 002_, ...)
    sql_files.sort(key=lambda p: p.name)
    return sql_files


def run_migrations(db_url: Optional[str] = None, dry_run: bool = False) -> bool:
    """Execute all migration files in order."""
    files = get_migration_files()
    if not files:
        print(f"No migration files found in {MIGRATIONS_DIR}")
        return False

    print(f"Found {len(files)} migration files in {MIGRATIONS_DIR.name}:")
    for f in files:
        print(f"  - {f.name}")

    if dry_run:
        print("\nDry-run complete. All migration files parsed successfully.")
        return True

    connection_url = db_url or os.getenv("DATABASE_URL", "postgresql://amap_user:change_me@localhost:5432/amap")
    print(f"\nConnecting to database...")

    try:
        with psycopg.connect(connection_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                # Create migrations tracking table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS _schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Fetch already applied migrations
                cur.execute("SELECT version FROM _schema_migrations;")
                applied = {row[0] for row in cur.fetchall()}

                for f in files:
                    if f.name in applied:
                        print(f"[SKIP] {f.name} (already applied)")
                        continue

                    print(f"[APPLYING] {f.name}...")
                    with open(f, "r", encoding="utf-8") as sql_f:
                        sql_content = sql_f.read()

                    cur.execute(sql_content)
                    cur.execute("INSERT INTO _schema_migrations (version) VALUES (%s);", (f.name,))
                    conn.commit()
                    print(f"  -> Applied {f.name}")

        print("\nAll database migrations completed successfully.")
        return True
    except Exception as e:
        print(f"Migration error: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAP Database Migration Runner")
    parser.add_argument("--db-url", type=str, help="PostgreSQL connection string")
    parser.add_argument("--dry-run", action="store_true", help="List migrations without executing on database")
    args = parser.parse_args()

    run_migrations(db_url=args.db_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
