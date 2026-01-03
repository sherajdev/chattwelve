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

    async def get_active_prompt(self) -> Optional[SystemPrompt]:
        """
        Get the currently active system prompt.

        Returns:
            Active SystemPrompt or None if no active prompt exists
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM system_prompts WHERE is_active = 1 LIMIT 1"
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return SystemPrompt(
                id=row["id"],
                name=row["name"],
                prompt=row["prompt"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"])
            )

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

            return SystemPrompt(
                id=row["id"],
                name=row["name"],
                prompt=row["prompt"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"])
            )

    async def get_by_name(self, name: str) -> Optional[SystemPrompt]:
        """
        Get a system prompt by name.

        Args:
            name: Prompt name to look up

        Returns:
            SystemPrompt object or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM system_prompts WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return SystemPrompt(
                id=row["id"],
                name=row["name"],
                prompt=row["prompt"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"])
            )

    async def list_all(self) -> List[SystemPrompt]:
        """
        Get all system prompts.

        Returns:
            List of SystemPrompt objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM system_prompts ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()

            prompts = []
            for row in rows:
                prompts.append(SystemPrompt(
                    id=row["id"],
                    name=row["name"],
                    prompt=row["prompt"],
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"])
                ))

            return prompts

    async def create(
        self,
        name: str,
        prompt: str,
        description: Optional[str] = None,
        is_active: bool = False
    ) -> SystemPrompt:
        """
        Create a new system prompt.

        Args:
            name: Unique name for the prompt
            prompt: The system prompt text
            description: Optional description
            is_active: Whether this should be the active prompt

        Returns:
            Created SystemPrompt object
        """
        prompt_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with aiosqlite.connect(self.db_path) as db:
            # If setting as active, deactivate all others first
            if is_active:
                await db.execute("UPDATE system_prompts SET is_active = 0")

            await db.execute(
                """
                INSERT INTO system_prompts (id, name, prompt, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (prompt_id, name, prompt, description, int(is_active), now.isoformat(), now.isoformat())
            )
            await db.commit()

        logger.info(f"Created system prompt: {name} (active={is_active})")

        return SystemPrompt(
            id=prompt_id,
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
            # If setting as active, deactivate all others first
            if is_active:
                await db.execute("UPDATE system_prompts SET is_active = 0")

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

    async def set_active(self, prompt_id: str) -> bool:
        """
        Set a prompt as the active one (deactivates all others).

        Args:
            prompt_id: ID of the prompt to activate

        Returns:
            True if successful, False if prompt not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            # First check if prompt exists
            cursor = await db.execute(
                "SELECT COUNT(*) FROM system_prompts WHERE id = ?",
                (prompt_id,)
            )
            row = await cursor.fetchone()
            if not row or row[0] == 0:
                return False

            # Deactivate all prompts
            await db.execute("UPDATE system_prompts SET is_active = 0")

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
