"""
PostgreSQL repository for chat messages.
Stores individual messages instead of JSON context array.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.core.postgres import get_connection
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    """Chat message data model."""
    id: str  # UUID as string
    session_id: str
    role: str  # 'user', 'assistant', or 'system'
    content: str
    model: Optional[str]  # AI model used (for assistant messages)
    metadata: Dict[str, Any]
    created_at: datetime


class PgMessageRepository:
    """Repository for chat message operations using PostgreSQL."""

    def _record_to_message(self, record) -> ChatMessage:
        """Convert an asyncpg Record to a ChatMessage object."""
        return ChatMessage(
            id=str(record["id"]),
            session_id=str(record["session_id"]),
            role=record["role"],
            content=record["content"],
            model=record["model"],
            metadata=record["metadata"] or {},
            created_at=record["created_at"]
        )

    async def add(
        self,
        session_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Add a new message to a session.

        Args:
            session_id: Chat session UUID
            role: Message role ('user', 'assistant', or 'system')
            content: Message content
            model: AI model used (for assistant messages)
            metadata: Optional metadata (tools used, response time, etc.)

        Returns:
            Created ChatMessage object
        """
        meta = metadata or {}

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_messages (session_id, role, content, model, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                uuid.UUID(session_id),
                role,
                content,
                model,
                meta
            )

        message = self._record_to_message(row)
        logger.debug(f"Added {role} message to session {session_id[:8]}...")
        return message

    async def add_user_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Convenience method to add a user message.

        Args:
            session_id: Chat session UUID
            content: User's message content
            metadata: Optional metadata

        Returns:
            Created ChatMessage object
        """
        return await self.add(session_id, "user", content, metadata=metadata)

    async def add_assistant_message(
        self,
        session_id: str,
        content: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Convenience method to add an assistant message.

        Args:
            session_id: Chat session UUID
            content: Assistant's response content
            model: AI model that generated the response
            metadata: Optional metadata (tools used, etc.)

        Returns:
            Created ChatMessage object
        """
        return await self.add(session_id, "assistant", content, model=model, metadata=metadata)

    async def get_by_id(self, message_id: str) -> Optional[ChatMessage]:
        """
        Get a message by ID.

        Args:
            message_id: Message UUID

        Returns:
            ChatMessage object or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chat_messages WHERE id = $1",
                uuid.UUID(message_id)
            )
            if not row:
                return None
            return self._record_to_message(row)

    async def get_session_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        order: str = "asc"
    ) -> List[ChatMessage]:
        """
        Get all messages for a session.

        Args:
            session_id: Chat session UUID
            limit: Maximum number of messages (None for all)
            offset: Number of messages to skip
            order: 'asc' (oldest first) or 'desc' (newest first)

        Returns:
            List of ChatMessage objects
        """
        order_dir = "ASC" if order == "asc" else "DESC"

        query = f"""
            SELECT * FROM chat_messages
            WHERE session_id = $1
            ORDER BY created_at {order_dir}
        """
        params = [uuid.UUID(session_id)]

        if limit is not None:
            query += f" LIMIT ${len(params) + 1}"
            params.append(limit)

        if offset > 0:
            query += f" OFFSET ${len(params) + 1}"
            params.append(offset)

        async with get_connection() as conn:
            rows = await conn.fetch(query, *params)

        return [self._record_to_message(row) for row in rows]

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[ChatMessage]:
        """
        Get the most recent messages for context.

        Args:
            session_id: Chat session UUID
            limit: Maximum number of messages

        Returns:
            List of ChatMessage objects (oldest first for context building)
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM (
                    SELECT * FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                ) sub
                ORDER BY created_at ASC
                """,
                uuid.UUID(session_id),
                limit
            )

        return [self._record_to_message(row) for row in rows]

    async def get_context_for_ai(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get recent messages formatted for AI context.

        Args:
            session_id: Chat session UUID
            limit: Maximum number of messages

        Returns:
            List of dicts with 'role' and 'content' keys
        """
        messages = await self.get_recent_messages(session_id, limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def get_message_count(self, session_id: str) -> int:
        """
        Get the number of messages in a session.

        Args:
            session_id: Chat session UUID

        Returns:
            Number of messages
        """
        async with get_connection() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = $1",
                uuid.UUID(session_id)
            )

    async def delete(self, message_id: str) -> bool:
        """
        Delete a specific message.

        Args:
            message_id: Message UUID

        Returns:
            True if deleted, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM chat_messages WHERE id = $1",
                uuid.UUID(message_id)
            )
            return result == "DELETE 1"

    async def delete_session_messages(self, session_id: str) -> int:
        """
        Delete all messages in a session.

        Args:
            session_id: Chat session UUID

        Returns:
            Number of messages deleted
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM chat_messages WHERE session_id = $1",
                uuid.UUID(session_id)
            )
            # Parse "DELETE N" to get count
            count = int(result.split()[1]) if result.startswith("DELETE") else 0

        if count > 0:
            logger.info(f"Deleted {count} messages from session {session_id[:8]}...")

        return count

    async def search_messages(
        self,
        user_id: str,
        query: str,
        limit: int = 20
    ) -> List[ChatMessage]:
        """
        Search messages across all user's sessions.

        Args:
            user_id: User ID to scope search
            query: Search query string
            limit: Maximum results

        Returns:
            List of matching ChatMessage objects
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT m.* FROM chat_messages m
                JOIN chat_sessions s ON m.session_id = s.id
                WHERE s.user_id = $1 AND m.content ILIKE $2
                ORDER BY m.created_at DESC
                LIMIT $3
                """,
                user_id,
                f"%{query}%",
                limit
            )

        return [self._record_to_message(row) for row in rows]


# Global repository instance
pg_message_repo = PgMessageRepository()
