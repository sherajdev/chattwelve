"""
PostgreSQL repository for user profiles.
Extends BetterAuth user data with app-specific settings.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.core.postgres import get_connection
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Profile:
    """User profile data model."""
    id: str  # BetterAuth user.id
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    preferences: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProfileRepository:
    """Repository for user profile operations using PostgreSQL."""

    def _record_to_profile(self, record) -> Profile:
        """Convert an asyncpg Record to a Profile object."""
        return Profile(
            id=record["id"],
            email=record["email"],
            display_name=record["display_name"],
            avatar_url=record["avatar_url"],
            preferences=record["preferences"] or {},
            created_at=record["created_at"],
            updated_at=record["updated_at"]
        )

    async def get_by_id(self, user_id: str) -> Optional[Profile]:
        """
        Get a user profile by ID.

        Args:
            user_id: BetterAuth user ID

        Returns:
            Profile object or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM profiles WHERE id = $1",
                user_id
            )
            if not row:
                return None
            return self._record_to_profile(row)

    async def get_by_email(self, email: str) -> Optional[Profile]:
        """
        Get a user profile by email.

        Args:
            email: User email address

        Returns:
            Profile object or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM profiles WHERE email = $1",
                email
            )
            if not row:
                return None
            return self._record_to_profile(row)

    async def create(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> Profile:
        """
        Create a new user profile.

        Called when a user signs up via BetterAuth.

        Args:
            user_id: BetterAuth user ID
            email: User email
            display_name: Optional display name
            avatar_url: Optional avatar URL
            preferences: Optional initial preferences

        Returns:
            Created Profile object
        """
        prefs = preferences or {}

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profiles (id, email, display_name, avatar_url, preferences)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                email,
                display_name,
                avatar_url,
                prefs
            )

        logger.info(f"Created profile for user: {user_id[:8]}...")
        return self._record_to_profile(row)

    async def upsert(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Profile:
        """
        Create or update a user profile.

        Used for BetterAuth sync - creates profile if doesn't exist,
        updates email/name if it does.

        Args:
            user_id: BetterAuth user ID
            email: User email
            display_name: Optional display name
            avatar_url: Optional avatar URL

        Returns:
            Profile object
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profiles (id, email, display_name, avatar_url)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
                    avatar_url = COALESCE(EXCLUDED.avatar_url, profiles.avatar_url),
                    updated_at = NOW()
                RETURNING *
                """,
                user_id,
                email,
                display_name,
                avatar_url
            )

        logger.info(f"Upserted profile for user: {user_id[:8]}...")
        return self._record_to_profile(row)

    async def update(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a user profile.

        Args:
            user_id: User ID
            display_name: New display name (optional)
            avatar_url: New avatar URL (optional)
            preferences: New preferences dict (replaces existing)

        Returns:
            True if updated, False if profile not found
        """
        updates = []
        params = []
        param_count = 0

        if display_name is not None:
            param_count += 1
            updates.append(f"display_name = ${param_count}")
            params.append(display_name)

        if avatar_url is not None:
            param_count += 1
            updates.append(f"avatar_url = ${param_count}")
            params.append(avatar_url)

        if preferences is not None:
            param_count += 1
            updates.append(f"preferences = ${param_count}")
            params.append(preferences)

        if not updates:
            return True  # Nothing to update

        # Add user_id as last parameter
        param_count += 1
        params.append(user_id)

        query = f"""
            UPDATE profiles
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = ${param_count}
        """

        async with get_connection() as conn:
            result = await conn.execute(query, *params)
            updated = result == "UPDATE 1"

        if updated:
            logger.info(f"Updated profile for user: {user_id[:8]}...")

        return updated

    async def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Merge preferences with existing (partial update).

        Args:
            user_id: User ID
            preferences: Preferences to merge

        Returns:
            True if updated, False if profile not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE profiles
                SET preferences = preferences || $1, updated_at = NOW()
                WHERE id = $2
                """,
                preferences,
                user_id
            )
            return result == "UPDATE 1"

    async def delete(self, user_id: str) -> bool:
        """
        Delete a user profile.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM profiles WHERE id = $1",
                user_id
            )
            deleted = result == "DELETE 1"

        if deleted:
            logger.info(f"Deleted profile for user: {user_id[:8]}...")

        return deleted

    async def exists(self, user_id: str) -> bool:
        """
        Check if a profile exists.

        Args:
            user_id: User ID to check

        Returns:
            True if exists, False otherwise
        """
        async with get_connection() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM profiles WHERE id = $1)",
                user_id
            )
            return result


# Global repository instance
profile_repo = ProfileRepository()
