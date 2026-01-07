"""
Session repository for database operations.
"""

import json
import uuid
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.core.config import settings
from src.core.logging import logger


@dataclass
class Session:
    """Session data model."""
    id: str
    user_id: Optional[str]
    created_at: datetime
    last_activity: datetime
    context: List[Dict[str, Any]]
    request_count: int
    request_window_start: datetime
    metadata: Dict[str, Any]


class SessionRepository:
    """Repository for session database operations."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DATABASE_PATH

    async def create(self, metadata: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> Session:
        """
        Create a new session.

        Args:
            metadata: Optional metadata to associate with session
            user_id: Optional authenticated user ID

        Returns:
            Created session object
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        meta = metadata or {}

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions (id, user_id, created_at, last_activity, context, request_count, request_window_start, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    now.isoformat(),
                    now.isoformat(),
                    "[]",
                    0,
                    now.isoformat(),
                    json.dumps(meta)
                )
            )
            await db.commit()

        logger.info(f"Created session: {session_id[:8]}... (User: {user_id or 'Guest'})")

        return Session(
            id=session_id,
            user_id=user_id,
            created_at=now,
            last_activity=now,
            context=[],
            request_count=0,
            request_window_start=now,
            metadata=meta
        )

    async def get(self, session_id: str, check_expiry: bool = True) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID to look up
            check_expiry: If True, returns None for expired sessions

        Returns:
            Session object or None if not found or expired (when check_expiry=True)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Handle case where user_id might not exist in old DBs
            try:
                user_id = row["user_id"]
            except (IndexError, KeyError):
                user_id = None

            session = Session(
                id=row["id"],
                user_id=user_id,
                created_at=datetime.fromisoformat(row["created_at"]),
                last_activity=datetime.fromisoformat(row["last_activity"]),
                context=json.loads(row["context"]),
                request_count=row["request_count"],
                request_window_start=datetime.fromisoformat(row["request_window_start"]),
                metadata=json.loads(row["metadata"])
            )

            # Check if session is expired
            if check_expiry and self.is_expired(session):
                logger.info(f"Session expired: {session_id[:8]}...")
                return None

            return session

    def is_expired(self, session: Session) -> bool:
        """
        Check if a session has expired.

        Args:
            session: Session object to check

        Returns:
            True if session is expired, False otherwise
        """
        now = datetime.utcnow()
        timeout = timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
        return (now - session.last_activity) >= timeout

    async def update_activity(self, session_id: str) -> bool:
        """
        Update the last_activity timestamp for a session.

        Args:
            session_id: Session ID to update

        Returns:
            True if updated, False if session not found
        """
        now = datetime.utcnow()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE sessions SET last_activity = ? WHERE id = ?",
                (now.isoformat(), session_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_context(self, session_id: str, context: List[Dict[str, Any]]) -> bool:
        """
        Update the conversation context for a session.

        Args:
            session_id: Session ID to update
            context: New context to store

        Returns:
            True if updated, False if session not found
        """
        now = datetime.utcnow()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE sessions SET context = ?, last_activity = ? WHERE id = ?",
                (json.dumps(context), now.isoformat(), session_id)
            )
            await db.commit()
            return cursor.rowcount > 0

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

        now = datetime.utcnow()
        window_duration = timedelta(seconds=settings.RATE_LIMIT_WINDOW_SECONDS)

        # Check if we need to reset the window
        if now - session.request_window_start >= window_duration:
            # Reset window
            new_count = 1
            new_window_start = now
        else:
            # Increment count
            new_count = session.request_count + 1
            new_window_start = session.request_window_start

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE sessions
                SET request_count = ?, request_window_start = ?, last_activity = ?
                WHERE id = ?
                """,
                (new_count, new_window_start.isoformat(), now.isoformat(), session_id)
            )
            await db.commit()

        # Calculate seconds until reset
        time_in_window = (now - new_window_start).total_seconds()
        seconds_until_reset = max(0, settings.RATE_LIMIT_WINDOW_SECONDS - int(time_in_window))

        return new_count, seconds_until_reset

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if session not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted session: {session_id[:8]}...")

        return deleted

    async def exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: Session ID to check

        Returns:
            True if exists, False otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def list_by_user(self, user_id: str, limit: int = 50) -> List[Session]:
        """
        Get all sessions for a specific user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of sessions to return

        Returns:
            List of sessions ordered by last activity (newest first)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM sessions 
                WHERE user_id = ? 
                ORDER BY last_activity DESC 
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = await cursor.fetchall()

            sessions = []
            for row in rows:
                session = Session(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_activity=datetime.fromisoformat(row["last_activity"]),
                    context=json.loads(row["context"]),
                    request_count=row["request_count"],
                    request_window_start=datetime.fromisoformat(row["request_window_start"]),
                    metadata=json.loads(row["metadata"])
                )
                # Skip expired sessions
                if not self.is_expired(session):
                    sessions.append(session)

            logger.info(f"Found {len(sessions)} sessions for user: {user_id[:8]}...")
            return sessions


# Global repository instance
session_repo = SessionRepository()
