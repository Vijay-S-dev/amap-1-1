from app.database import get_db_connection


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
