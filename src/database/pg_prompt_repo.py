"""
PostgreSQL repository for system prompts.
User-customizable AI system prompts.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from src.core.postgres import get_connection
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SystemPrompt:
    """System prompt data model."""
    id: str  # UUID as string
    user_id: Optional[str]  # NULL for system defaults
    name: str
    prompt: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PgPromptRepository:
    """Repository for system prompt operations using PostgreSQL."""

    def _record_to_prompt(self, record) -> SystemPrompt:
        """Convert an asyncpg Record to a SystemPrompt object."""
        return SystemPrompt(
            id=str(record["id"]),
            user_id=record["user_id"],
            name=record["name"],
            prompt=record["prompt"],
            description=record["description"],
            is_active=record["is_active"],
            created_at=record["created_at"],
            updated_at=record["updated_at"]
        )

    async def get_active_prompt(self, user_id: Optional[str] = None) -> Optional[SystemPrompt]:
        """
        Get the currently active system prompt for a user.

        For authenticated users, returns their active prompt or falls back to system default.
        For unauthenticated users (user_id=None), returns only the system default prompt.

        Args:
            user_id: Optional user ID for user-specific active prompt

        Returns:
            Active SystemPrompt or None if no active prompt exists
        """
        async with get_connection() as conn:
            # For authenticated users, try user's active prompt first
            if user_id:
                row = await conn.fetchrow(
                    "SELECT * FROM system_prompts WHERE user_id = $1 AND is_active = true LIMIT 1",
                    user_id
                )
                if row:
                    return self._record_to_prompt(row)

            # Fall back to system default (user_id IS NULL)
            row = await conn.fetchrow(
                "SELECT * FROM system_prompts WHERE user_id IS NULL AND is_active = true LIMIT 1"
            )
            if not row:
                return None

            return self._record_to_prompt(row)

    async def get_by_id(self, prompt_id: str) -> Optional[SystemPrompt]:
        """
        Get a system prompt by ID.

        Args:
            prompt_id: Prompt UUID

        Returns:
            SystemPrompt object or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM system_prompts WHERE id = $1",
                uuid.UUID(prompt_id)
            )
            if not row:
                return None
            return self._record_to_prompt(row)

    async def get_by_name(self, name: str, user_id: Optional[str] = None) -> Optional[SystemPrompt]:
        """
        Get a system prompt by name for a specific user.

        Args:
            name: Prompt name
            user_id: Optional user ID (None for system defaults)

        Returns:
            SystemPrompt object or None if not found
        """
        async with get_connection() as conn:
            if user_id:
                row = await conn.fetchrow(
                    "SELECT * FROM system_prompts WHERE name = $1 AND user_id = $2",
                    name,
                    user_id
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM system_prompts WHERE name = $1 AND user_id IS NULL",
                    name
                )

            if not row:
                return None
            return self._record_to_prompt(row)

    async def list_all(self, user_id: Optional[str] = None) -> List[SystemPrompt]:
        """
        Get all system prompts for a user.

        For authenticated users, returns system defaults + user's custom prompts.
        For unauthenticated users, returns only system defaults.

        Args:
            user_id: Optional user ID to include user-specific prompts

        Returns:
            List of SystemPrompt objects
        """
        async with get_connection() as conn:
            if user_id:
                # System defaults + user's prompts
                rows = await conn.fetch(
                    """
                    SELECT * FROM system_prompts
                    WHERE user_id IS NULL OR user_id = $1
                    ORDER BY user_id NULLS FIRST, created_at DESC
                    """,
                    user_id
                )
            else:
                # Only system defaults
                rows = await conn.fetch(
                    "SELECT * FROM system_prompts WHERE user_id IS NULL ORDER BY created_at DESC"
                )

            return [self._record_to_prompt(row) for row in rows]

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
            user_id: Optional user ID (None for system defaults)

        Returns:
            Created SystemPrompt object
        """
        async with get_connection() as conn:
            async with conn.transaction():
                # If setting as active, deactivate other prompts first
                if is_active:
                    if user_id:
                        await conn.execute(
                            "UPDATE system_prompts SET is_active = false WHERE user_id = $1",
                            user_id
                        )
                    else:
                        await conn.execute(
                            "UPDATE system_prompts SET is_active = false WHERE user_id IS NULL"
                        )

                row = await conn.fetchrow(
                    """
                    INSERT INTO system_prompts (user_id, name, prompt, description, is_active)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    """,
                    user_id,
                    name,
                    prompt,
                    description,
                    is_active
                )

        result = self._record_to_prompt(row)
        logger.info(f"Created system prompt: {name} for user {user_id or 'system'} (active={is_active})")
        return result

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
        # Get existing to check it exists
        existing = await self.get_by_id(prompt_id)
        if not existing:
            return False

        updates = []
        params = []
        param_count = 0

        if name is not None:
            param_count += 1
            updates.append(f"name = ${param_count}")
            params.append(name)

        if prompt is not None:
            param_count += 1
            updates.append(f"prompt = ${param_count}")
            params.append(prompt)

        if description is not None:
            param_count += 1
            updates.append(f"description = ${param_count}")
            params.append(description)

        if is_active is not None:
            param_count += 1
            updates.append(f"is_active = ${param_count}")
            params.append(is_active)

        if not updates:
            return True  # Nothing to update

        # Add prompt_id as last parameter
        param_count += 1
        params.append(uuid.UUID(prompt_id))

        async with get_connection() as conn:
            async with conn.transaction():
                # If setting as active, deactivate others first
                if is_active:
                    if existing.user_id:
                        await conn.execute(
                            "UPDATE system_prompts SET is_active = false WHERE user_id = $1",
                            existing.user_id
                        )
                    else:
                        await conn.execute(
                            "UPDATE system_prompts SET is_active = false WHERE user_id IS NULL"
                        )

                result = await conn.execute(
                    f"UPDATE system_prompts SET {', '.join(updates)} WHERE id = ${param_count}",
                    *params
                )

        updated = result == "UPDATE 1"
        if updated:
            logger.info(f"Updated system prompt: {prompt_id}")

        return updated

    async def delete(self, prompt_id: str) -> bool:
        """
        Delete a system prompt.

        Args:
            prompt_id: ID of the prompt to delete

        Returns:
            True if deleted, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM system_prompts WHERE id = $1",
                uuid.UUID(prompt_id)
            )
            deleted = result == "DELETE 1"

        if deleted:
            logger.info(f"Deleted system prompt: {prompt_id}")

        return deleted

    async def set_active(self, prompt_id: str) -> bool:
        """
        Set a prompt as the active one (deactivates others in same scope).

        Args:
            prompt_id: ID of the prompt to activate

        Returns:
            True if successful, False if prompt not found
        """
        # Get prompt to determine user scope
        existing = await self.get_by_id(prompt_id)
        if not existing:
            return False

        async with get_connection() as conn:
            async with conn.transaction():
                # Deactivate other prompts in same scope
                if existing.user_id:
                    await conn.execute(
                        "UPDATE system_prompts SET is_active = false WHERE user_id = $1",
                        existing.user_id
                    )
                else:
                    await conn.execute(
                        "UPDATE system_prompts SET is_active = false WHERE user_id IS NULL"
                    )

                # Activate this prompt
                await conn.execute(
                    "UPDATE system_prompts SET is_active = true WHERE id = $1",
                    uuid.UUID(prompt_id)
                )

        logger.info(f"Set active system prompt: {prompt_id}")
        return True


# Global repository instance
pg_prompt_repo = PgPromptRepository()
