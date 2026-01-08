"""
PostgreSQL repository for chat sessions.
Stores conversation sessions linked to authenticated users.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.core.postgres import get_connection
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatSession:
    """Chat session data model."""
    id: str  # UUID as string
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    request_count: int
    request_window_start: datetime
    metadata: Dict[str, Any]


class PgSessionRepository:
    """Repository for chat session operations using PostgreSQL."""

    def _record_to_session(self, record) -> ChatSession:
        """Convert an asyncpg Record to a ChatSession object."""
        return ChatSession(
            id=str(record["id"]),
            user_id=record["user_id"],
            title=record["title"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            last_message_at=record["last_message_at"],
            request_count=record["request_count"],
            request_window_start=record["request_window_start"],
            metadata=record["metadata"] or {}
        )

    async def create(
        self,
        user_id: str,
        title: str = "New Chat",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: Authenticated user ID (from BetterAuth)
            title: Session title (default: "New Chat")
            metadata: Optional metadata

        Returns:
            Created ChatSession object
        """
        meta = metadata or {}

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_sessions (user_id, title, metadata)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                user_id,
                title,
                meta
            )

        session = self._record_to_session(row)
        logger.info(f"Created chat session: {session.id[:8]}... for user: {user_id[:8]}...")
        return session

    async def get(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session UUID

        Returns:
            ChatSession object or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chat_sessions WHERE id = $1",
                uuid.UUID(session_id)
            )
            if not row:
                return None
            return self._record_to_session(row)

    async def get_for_user(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID, ensuring it belongs to the user.

        Args:
            session_id: Session UUID
            user_id: User ID for authorization check

        Returns:
            ChatSession object or None if not found or unauthorized
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chat_sessions WHERE id = $1 AND user_id = $2",
                uuid.UUID(session_id),
                user_id
            )
            if not row:
                return None
            return self._record_to_session(row)

    async def list_by_user(self, user_id: str, limit: int = 50) -> List[ChatSession]:
        """
        Get all chat sessions for a user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession objects ordered by last message (newest first)
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_sessions
                WHERE user_id = $1
                ORDER BY last_message_at DESC
                LIMIT $2
                """,
                user_id,
                limit
            )

        sessions = [self._record_to_session(row) for row in rows]
        logger.info(f"Found {len(sessions)} sessions for user: {user_id[:8]}...")
        return sessions

    async def update_title(self, session_id: str, title: str) -> bool:
        """
        Update the session title.

        Args:
            session_id: Session ID
            title: New title

        Returns:
            True if updated, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "UPDATE chat_sessions SET title = $1 WHERE id = $2",
                title,
                uuid.UUID(session_id)
            )
            return result == "UPDATE 1"

    async def update_activity(self, session_id: str) -> bool:
        """
        Update the last activity timestamp.

        Args:
            session_id: Session ID

        Returns:
            True if updated, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = NOW()
                WHERE id = $1
                """,
                uuid.UUID(session_id)
            )
            return result == "UPDATE 1"

    async def increment_request_count(self, session_id: str) -> tuple[int, int]:
        """
        Increment the request count for rate limiting.

        Resets the count if the window has expired.

        Args:
            session_id: Session ID

        Returns:
            Tuple of (current_count, seconds_until_reset)
        """
        session = await self.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        now = datetime.now(timezone.utc)
        window_duration = timedelta(seconds=settings.RATE_LIMIT_WINDOW_SECONDS)

        # Make request_window_start timezone-aware if it isn't
        window_start = session.request_window_start
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)

        # Check if we need to reset the window
        if now - window_start >= window_duration:
            new_count = 1
            new_window_start = now
        else:
            new_count = session.request_count + 1
            new_window_start = window_start

        async with get_connection() as conn:
            await conn.execute(
                """
                UPDATE chat_sessions
                SET request_count = $1, request_window_start = $2, updated_at = NOW()
                WHERE id = $3
                """,
                new_count,
                new_window_start,
                uuid.UUID(session_id)
            )

        # Calculate seconds until reset
        time_in_window = (now - new_window_start).total_seconds()
        seconds_until_reset = max(0, settings.RATE_LIMIT_WINDOW_SECONDS - int(time_in_window))

        return new_count, seconds_until_reset

    async def delete(self, session_id: str) -> bool:
        """
        Delete a chat session and all its messages (CASCADE).

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM chat_sessions WHERE id = $1",
                uuid.UUID(session_id)
            )
            deleted = result == "DELETE 1"

        if deleted:
            logger.info(f"Deleted chat session: {session_id[:8]}...")

        return deleted

    async def delete_for_user(self, session_id: str, user_id: str) -> bool:
        """
        Delete a chat session, ensuring it belongs to the user.

        Args:
            session_id: Session ID
            user_id: User ID for authorization

        Returns:
            True if deleted, False if not found or unauthorized
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM chat_sessions WHERE id = $1 AND user_id = $2",
                uuid.UUID(session_id),
                user_id
            )
            return result == "DELETE 1"

    async def exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: Session ID

        Returns:
            True if exists, False otherwise
        """
        async with get_connection() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM chat_sessions WHERE id = $1)",
                uuid.UUID(session_id)
            )
            return result

    async def get_session_count_for_user(self, user_id: str) -> int:
        """
        Get the number of sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions
        """
        async with get_connection() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM chat_sessions WHERE user_id = $1",
                user_id
            )


# Global repository instance
pg_session_repo = PgSessionRepository()
