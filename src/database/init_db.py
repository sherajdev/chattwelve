"""
Database initialization for ChatTwelve.
"""

import aiosqlite
from pathlib import Path
from src.core.config import settings
from src.core.logging import logger


async def init_database() -> None:
    """
    Initialize the SQLite database with required tables.

    Creates:
    - sessions: Conversation session storage
    - cache: Query response cache
    """
    db_path = Path(settings.DATABASE_PATH)

    logger.info(f"Initializing database at {db_path}")

    async with aiosqlite.connect(db_path) as db:
        # Create sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                context TEXT DEFAULT '[]',
                request_count INTEGER DEFAULT 0,
                request_window_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Create cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                query_type TEXT NOT NULL,
                response_data TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ttl_seconds INTEGER NOT NULL
            )
        """)

        # Create indexes for better query performance
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_activity
            ON sessions(last_activity)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_created_at
            ON cache(created_at)
        """)

        await db.commit()

    logger.info("Database initialized successfully")


async def get_db_connection() -> aiosqlite.Connection:
    """
    Get a database connection.

    Returns:
        aiosqlite.Connection: Database connection
    """
    db_path = Path(settings.DATABASE_PATH)
    return await aiosqlite.connect(db_path)


async def cleanup_expired_sessions() -> int:
    """
    Remove expired sessions from the database.

    Returns:
        Number of sessions cleaned up
    """
    from datetime import datetime, timedelta

    timeout = timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
    cutoff = datetime.utcnow() - timeout

    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_activity < ?",
            (cutoff.isoformat(),)
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count > 0:
            await db.execute(
                "DELETE FROM sessions WHERE last_activity < ?",
                (cutoff.isoformat(),)
            )
            await db.commit()
            logger.info(f"Cleaned up {count} expired sessions")

        return count


async def cleanup_expired_cache() -> int:
    """
    Remove expired cache entries from the database.

    Returns:
        Number of cache entries cleaned up
    """
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        # Delete entries where created_at + ttl_seconds < now
        cursor = await db.execute("""
            SELECT COUNT(*) FROM cache
            WHERE datetime(created_at, '+' || ttl_seconds || ' seconds') < datetime('now')
        """)
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count > 0:
            await db.execute("""
                DELETE FROM cache
                WHERE datetime(created_at, '+' || ttl_seconds || ' seconds') < datetime('now')
            """)
            await db.commit()
            logger.info(f"Cleaned up {count} expired cache entries")

        return count


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())
