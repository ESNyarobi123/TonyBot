"""
ERICKsky Signal Engine - PostgreSQL Connection Manager
Provides connection pooling and context-managed sessions.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.pool
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection, cursor as PgCursor

from config import settings

logger = logging.getLogger(__name__)


class DBManager:
    """Thread-safe PostgreSQL connection pool manager."""

    _instance: Optional["DBManager"] = None
    _pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def __new__(cls) -> "DBManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, min_conn: int = 2, max_conn: int = 10) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                connect_timeout=10,
                options="-c timezone=UTC",
            )
            logger.info(
                "PostgreSQL pool initialized (%d–%d connections)", min_conn, max_conn
            )
        except psycopg2.Error as exc:
            logger.critical("Failed to create DB pool: %s", exc)
            raise

    def get_connection(self) -> PgConnection:
        """Acquire a connection from the pool."""
        if self._pool is None:
            self.initialize()
        conn = self._pool.getconn()
        conn.autocommit = False
        return conn

    def release_connection(self, conn: PgConnection) -> None:
        """Return a connection to the pool."""
        if self._pool and conn:
            self._pool.putconn(conn)

    @contextmanager
    def connection(self) -> Generator[PgConnection, None, None]:
        """Context manager: auto-commit on success, rollback on exception."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("DB transaction rolled back: %s", exc)
            raise
        finally:
            self.release_connection(conn)

    @contextmanager
    def cursor(self) -> Generator[PgCursor, None, None]:
        """Context manager yielding a DictCursor inside a transaction."""
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur

    def execute(self, query: str, params: tuple = ()) -> list:
        """Execute a SELECT query and return all rows as dicts."""
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Execute a SELECT query and return one row."""
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def execute_write(self, query: str, params: tuple = ()) -> Optional[int]:
        """Execute INSERT/UPDATE/DELETE and return lastrowid if available."""
        with self.cursor() as cur:
            cur.execute(query, params)
            try:
                row = cur.fetchone()
                return row["id"] if row else None
            except Exception:
                return None

    def health_check(self) -> bool:
        """Verify database connectivity."""
        try:
            result = self.execute_one("SELECT 1 AS ok")
            return result is not None and result.get("ok") == 1
        except Exception as exc:
            logger.error("DB health check failed: %s", exc)
            return False

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")


# Singleton instance used throughout the application
db = DBManager()
