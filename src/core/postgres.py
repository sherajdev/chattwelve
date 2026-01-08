"""
PostgreSQL connection pool using asyncpg.
Connects to the same Supabase PostgreSQL database used by BetterAuth.
"""

import json
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection):
    """Initialize connection with JSON codec for JSONB columns."""
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )
    await conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )


async def init_postgres_pool() -> asyncpg.Pool:
    """Initialize the PostgreSQL connection pool."""
    global _pool

    if _pool is not None:
        return _pool

    database_url = settings.POSTGRES_URL
    if not database_url:
        raise ValueError("POSTGRES_URL environment variable is required for PostgreSQL connection")

    logger.info("Initializing PostgreSQL connection pool")

    try:
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            statement_cache_size=100,
            init=_init_connection,  # Register JSON codecs on each connection
        )
        logger.info("PostgreSQL connection pool initialized successfully")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL pool: {e}")
        raise


async def close_postgres_pool() -> None:
    """Close the PostgreSQL connection pool."""
    global _pool

    if _pool is not None:
        logger.info("Closing PostgreSQL connection pool")
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


def get_pool() -> asyncpg.Pool:
    """Get the PostgreSQL connection pool."""
    if _pool is None:
        raise RuntimeError("PostgreSQL pool not initialized. Call init_postgres_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a connection from the pool as a context manager."""
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection


async def execute(query: str, *args) -> str:
    """Execute a query and return the status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list:
    """Execute a query and return all rows."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> Optional[asyncpg.Record]:
    """Execute a query and return the first row."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Execute a query and return the first value of the first row."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)


async def health_check() -> tuple[bool, Optional[str]]:
    """Check if PostgreSQL connection is healthy."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                return True, None
            return False, "Unexpected health check result"
    except RuntimeError as e:
        return False, f"Pool not initialized: {e}"
    except Exception as e:
        return False, f"PostgreSQL health check failed: {e}"
