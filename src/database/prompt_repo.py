"""
Prompt repository for managing AI system prompts.
"""

import json
import uuid
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.core.config import settings
from src.core.logging import logger


@dataclass
class SystemPrompt:
    """System prompt data model."""
    id: str
    user_id: Optional[str]
    name: str
    prompt: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PromptRepository:
    """Repository for system prompts database operations."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DATABASE_PATH

    def _row_to_prompt(self, row) -> SystemPrompt:
        """Convert a database row to a SystemPrompt object."""
        # Handle user_id which might not exist in older databases
        try:
            user_id = row["user_id"]
        except (IndexError, KeyError):
            user_id = None

        return SystemPrompt(
            id=row["id"],
            user_id=user_id,
            name=row["name"],
            prompt=row["prompt"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )

    async def get_active_prompt(self, user_id: Optional[str] = None) -> Optional[SystemPrompt]:
        """
        Get the currently active system prompt for a user.

        For authenticated users, returns their active prompt or falls back to the default.
        For unauthenticated users (user_id=None), returns only the system default prompt.

        Args:
            user_id: Optional user ID to get user-specific active prompt

        Returns:
            Active SystemPrompt or None if no active prompt exists
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # For authenticated users, try to get their active prompt first
            if user_id:
                cursor = await db.execute(
                    "SELECT * FROM system_prompts WHERE user_id = ? AND is_active = 1 LIMIT 1",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if row:
                    return self._row_to_prompt(row)

            # Fall back to default system prompt (user_id is NULL)
            cursor = await db.execute(
                "SELECT * FROM system_prompts WHERE user_id IS NULL AND is_active = 1 LIMIT 1"
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_prompt(row)

    async def get_by_id(self, prompt_id: str) -> Optional[SystemPrompt]:
        """
        Get a system prompt by ID.

        Args:
            prompt_id: Prompt ID to look up

        Returns:
            SystemPrompt object or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM system_prompts WHERE id = ?",
                (prompt_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_prompt(row)

    async def get_by_name(self, name: str, user_id: Optional[str] = None) -> Optional[SystemPrompt]:
        """
        Get a system prompt by name for a specific user.

        Args:
            name: Prompt name to look up
            user_id: Optional user ID (None for system default prompts)

        Returns:
            SystemPrompt object or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id:
                cursor = await db.execute(
                    "SELECT * FROM system_prompts WHERE name = ? AND user_id = ?",
                    (name, user_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM system_prompts WHERE name = ? AND user_id IS NULL",
                    (name,)
                )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_prompt(row)

    async def list_all(self, user_id: Optional[str] = None) -> List[SystemPrompt]:
        """
        Get all system prompts for a user.

        For authenticated users, returns system defaults + user's custom prompts.
        For unauthenticated users (user_id=None), returns only system default prompts.

        Args:
            user_id: Optional user ID to include user-specific prompts

        Returns:
            List of SystemPrompt objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if user_id:
                # Get both system defaults (user_id IS NULL) and user's prompts
                cursor = await db.execute(
                    """SELECT * FROM system_prompts 
                       WHERE user_id IS NULL OR user_id = ? 
                       ORDER BY user_id NULLS FIRST, created_at DESC""",
                    (user_id,)
                )
            else:
                # Only get system default prompts
                cursor = await db.execute(
                    "SELECT * FROM system_prompts WHERE user_id IS NULL ORDER BY created_at DESC"
                )

            rows = await cursor.fetchall()
            return [self._row_to_prompt(row) for row in rows]

    async def create(
        self,
        name: str,
        prompt: str,
        description: Optional[str] = None,
        is_active: bool = False,
        user_id: Optional[str] = None
    ) -> SystemPrompt:
        """
        Create a new system prompt.

        Args:
            name: Unique name for the prompt (per user)
            prompt: The system prompt text
            description: Optional description
            is_active: Whether this should be the active prompt
            user_id: Optional user ID (None for system default prompts)

        Returns:
            Created SystemPrompt object
        """
        prompt_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with aiosqlite.connect(self.db_path) as db:
            # If setting as active, deactivate user's other prompts first
            if is_active:
                if user_id:
                    await db.execute(
                        "UPDATE system_prompts SET is_active = 0 WHERE user_id = ?",
                        (user_id,)
                    )
                else:
                    await db.execute(
                        "UPDATE system_prompts SET is_active = 0 WHERE user_id IS NULL"
                    )

            await db.execute(
                """
                INSERT INTO system_prompts (id, user_id, name, prompt, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (prompt_id, user_id, name, prompt, description, int(is_active), now.isoformat(), now.isoformat())
            )
            await db.commit()

        logger.info(f"Created system prompt: {name} for user {user_id or 'system'} (active={is_active})")

        return SystemPrompt(
            id=prompt_id,
            user_id=user_id,
            name=name,
            prompt=prompt,
            description=description,
            is_active=is_active,
            created_at=now,
            updated_at=now
        )

    async def update(
        self,
        prompt_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update a system prompt.

        Args:
            prompt_id: ID of the prompt to update
            name: New name (optional)
            prompt: New prompt text (optional)
            description: New description (optional)
            is_active: New active status (optional)

        Returns:
            True if updated, False if prompt not found
        """
        # Get existing prompt
        existing = await self.get_by_id(prompt_id)
        if not existing:
            return False

        # Build update query
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if prompt is not None:
            updates.append("prompt = ?")
            params.append(prompt)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(int(is_active))

        if not updates:
            return True  # Nothing to update

        # Always update the updated_at timestamp
        now = datetime.utcnow()
        updates.append("updated_at = ?")
        params.append(now.isoformat())

        # Add prompt_id to params
        params.append(prompt_id)

        async with aiosqlite.connect(self.db_path) as db:
            # If setting as active, deactivate user's other prompts first
            if is_active:
                # Get the user_id of this prompt to scope deactivation
                cursor = await db.execute(
                    "SELECT user_id FROM system_prompts WHERE id = ?",
                    (prompt_id,)
                )
                row = await cursor.fetchone()
                if row:
                    prompt_user_id = row[0]
                    if prompt_user_id:
                        await db.execute(
                            "UPDATE system_prompts SET is_active = 0 WHERE user_id = ?",
                            (prompt_user_id,)
                        )
                    else:
                        await db.execute(
                            "UPDATE system_prompts SET is_active = 0 WHERE user_id IS NULL"
                        )

            cursor = await db.execute(
                f"UPDATE system_prompts SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await db.commit()

            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated system prompt: {prompt_id}")

        return updated

    async def delete(self, prompt_id: str) -> bool:
        """
        Delete a system prompt.

        Args:
            prompt_id: ID of the prompt to delete

        Returns:
            True if deleted, False if prompt not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM system_prompts WHERE id = ?",
                (prompt_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted system prompt: {prompt_id}")

        return deleted

    async def set_active(self, prompt_id: str, user_id: Optional[str] = None) -> bool:
        """
        Set a prompt as the active one for a user (deactivates user's other prompts).

        Args:
            prompt_id: ID of the prompt to activate
            user_id: Optional user ID (for scoping deactivation)

        Returns:
            True if successful, False if prompt not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            # First check if prompt exists and get its user_id
            cursor = await db.execute(
                "SELECT user_id FROM system_prompts WHERE id = ?",
                (prompt_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return False

            prompt_user_id = row[0]

            # Deactivate other prompts for the same user scope
            if prompt_user_id:
                await db.execute(
                    "UPDATE system_prompts SET is_active = 0 WHERE user_id = ?",
                    (prompt_user_id,)
                )
            else:
                await db.execute(
                    "UPDATE system_prompts SET is_active = 0 WHERE user_id IS NULL"
                )

            # Activate the specified prompt
            await db.execute(
                "UPDATE system_prompts SET is_active = 1, updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), prompt_id)
            )
            await db.commit()

        logger.info(f"Set active system prompt: {prompt_id}")
        return True


# Global repository instance
prompt_repo = PromptRepository()
