"""MySQL connection pooling + small query helpers."""
import mysql.connector
from mysql.connector import pooling

from config import Config

_pool = None


def init_pool():
    """Create the connection pool once, on first use (lazy init)."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="pos_pool",
            pool_size=5,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
    return _pool


def get_connection():
    """Grab a connection from the pool. Caller is responsible for closing it
    (use the `with get_connection() as conn:` pattern or call conn.close())."""
    pool = init_pool()
    return pool.get_connection()


def query_all(sql, params=None):
    """Run a SELECT and return all rows as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def query_one(sql, params=None):
    """Run a SELECT and return the first row as a dict, or None."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE. Returns (lastrowid, rowcount)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        last_id, row_count = cursor.lastrowid, cursor.rowcount
        cursor.close()
        return last_id, row_count
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
