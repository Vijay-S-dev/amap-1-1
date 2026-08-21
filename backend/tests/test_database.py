import pytest

from app.database import get_db, get_db_connection


def test_database_connection():
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            database, user = cur.fetchone()

        assert database == "amap"
        assert user == "amap_user"

    finally:
        conn.close()


def test_get_db_yields_working_connection():
    dependency = get_db()
    conn = next(dependency)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()

        assert result == (1,)

    finally:
        dependency.close()


def test_get_db_rolls_back_on_exception():
    dependency = get_db()
    conn = next(dependency)

    try:
        with pytest.raises(RuntimeError):
            try:
                raise RuntimeError("Simulated request failure")
            except RuntimeError as exc:
                dependency.throw(exc)

        assert conn.closed

    finally:
        if not conn.closed:
            dependency.close()
