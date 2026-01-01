"""
Cache repository for database operations.
"""

import json
import hashlib
import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any

from src.core.config import settings
from src.core.logging import logger, log_cache_hit, log_cache_miss


class CacheRepository:
    """Repository for cache database operations."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DATABASE_PATH

    def _generate_cache_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """
        Generate a cache key from query type and parameters.

        Args:
            query_type: Type of query (price, quote, historical, etc.)
            params: Query parameters

        Returns:
            SHA256 hash as cache key
        """
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        key_string = f"{query_type}:{sorted_params}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_ttl(self, query_type: str) -> int:
        """
        Get TTL for a query type.

        Args:
            query_type: Type of query

        Returns:
            TTL in seconds
        """
        if query_type == "price":
            return settings.CACHE_TTL_PRICE
        elif query_type in ("historical", "indicator"):
            return settings.CACHE_TTL_HISTORICAL
        else:
            return settings.CACHE_TTL_PRICE

    async def get(
        self,
        query_type: str,
        params: Dict[str, Any],
        allow_stale: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a query.

        Args:
            query_type: Type of query
            params: Query parameters
            allow_stale: Whether to return stale cache entries

        Returns:
            Cached response data or None if not found/expired
        """
        cache_key = self._generate_cache_key(query_type, params)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if allow_stale:
                # Return any cached entry, even if expired
                cursor = await db.execute(
                    "SELECT * FROM cache WHERE key = ?",
                    (cache_key,)
                )
            else:
                # Only return non-expired entries
                cursor = await db.execute(
                    """
                    SELECT * FROM cache
                    WHERE key = ?
                    AND datetime(created_at, '+' || ttl_seconds || ' seconds') > datetime('now')
                    """,
                    (cache_key,)
                )

            row = await cursor.fetchone()

            if row:
                log_cache_hit(cache_key, query_type)
                data = json.loads(row["response_data"])

                # Check if this is stale data
                created_at = datetime.fromisoformat(row["created_at"])
                ttl = row["ttl_seconds"]
                is_stale = (datetime.utcnow() - created_at).total_seconds() > ttl

                if is_stale:
                    data["_stale"] = True
                    data["_cached_at"] = created_at.isoformat()

                return data

            log_cache_miss(cache_key, query_type)
            return None

    async def set(
        self,
        query_type: str,
        params: Dict[str, Any],
        response_data: Dict[str, Any]
    ) -> str:
        """
        Cache a response.

        Args:
            query_type: Type of query
            params: Query parameters
            response_data: Response data to cache

        Returns:
            Cache key
        """
        cache_key = self._generate_cache_key(query_type, params)
        ttl = self._get_ttl(query_type)
        now = datetime.utcnow()

        async with aiosqlite.connect(self.db_path) as db:
            # Use INSERT OR REPLACE to update existing entries
            await db.execute(
                """
                INSERT OR REPLACE INTO cache (key, query_type, response_data, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    query_type,
                    json.dumps(response_data),
                    now.isoformat(),
                    ttl
                )
            )
            await db.commit()

        logger.debug(f"Cached {query_type} response with TTL {ttl}s")
        return cache_key

    async def invalidate(self, query_type: str, params: Dict[str, Any]) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            query_type: Type of query
            params: Query parameters

        Returns:
            True if entry was deleted, False if not found
        """
        cache_key = self._generate_cache_key(query_type, params)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM cache WHERE key = ?",
                (cache_key,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM cache")
            row = await cursor.fetchone()
            count = row[0] if row else 0

            await db.execute("DELETE FROM cache")
            await db.commit()

        logger.info(f"Cleared {count} cache entries")
        return count

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Total entries
            cursor = await db.execute("SELECT COUNT(*) FROM cache")
            total = (await cursor.fetchone())[0]

            # Entries by type
            cursor = await db.execute(
                "SELECT query_type, COUNT(*) FROM cache GROUP BY query_type"
            )
            by_type = {row[0]: row[1] for row in await cursor.fetchall()}

            # Expired entries
            cursor = await db.execute("""
                SELECT COUNT(*) FROM cache
                WHERE datetime(created_at, '+' || ttl_seconds || ' seconds') < datetime('now')
            """)
            expired = (await cursor.fetchone())[0]

            return {
                "total_entries": total,
                "by_type": by_type,
                "expired_entries": expired,
                "active_entries": total - expired
            }


# Global repository instance
cache_repo = CacheRepository()
