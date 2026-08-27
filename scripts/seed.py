"""
CLI Database Seeder for AMAP.
"""

import argparse
import sys
from pathlib import Path

# Add database/seed to path
SEED_DIR = Path(__file__).resolve().parent.parent / "database" / "seed"
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

from seed_data import run_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAP Database Demo Seeder")
    parser.add_argument("--db-url", type=str, help="PostgreSQL connection string")
    args = parser.parse_args()

    success = run_seed(db_url=args.db_url)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
