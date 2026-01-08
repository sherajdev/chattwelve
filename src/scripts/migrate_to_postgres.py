#!/usr/bin/env python3
"""
Migration script: SQLite to PostgreSQL
Migrates system_prompts and sessions data from SQLite to PostgreSQL (Supabase)

Usage:
    python -m src.scripts.migrate_to_postgres

Requires:
    - POSTGRES_URL environment variable set
    - SQLite database at ./chattwelve.db
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

import aiosqlite

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings
from src.core.postgres import init_postgres_pool, close_postgres_pool, get_connection
from src.core.logging import get_logger

logger = get_logger(__name__)


async def migrate_system_prompts(sqlite_db: aiosqlite.Connection) -> int:
    """Migrate system_prompts table from SQLite to PostgreSQL."""
    logger.info("Migrating system_prompts...")

    sqlite_db.row_factory = aiosqlite.Row
    cursor = await sqlite_db.execute("SELECT * FROM system_prompts")
    rows = await cursor.fetchall()

    migrated = 0
    async with get_connection() as conn:
        for row in rows:
            try:
                # Check if prompt already exists by name
                existing = await conn.fetchrow(
                    "SELECT id FROM system_prompts WHERE name = $1 AND user_id IS NOT DISTINCT FROM $2",
                    row["name"],
                    row["user_id"] if "user_id" in row.keys() else None
                )

                if existing:
                    logger.info(f"  Skipping existing prompt: {row['name']}")
                    continue

                # Insert new prompt
                await conn.execute(
                    """
                    INSERT INTO system_prompts (id, user_id, name, prompt, description, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    uuid.UUID(row["id"]) if row["id"] else uuid.uuid4(),
                    row["user_id"] if "user_id" in row.keys() else None,
                    row["name"],
                    row["prompt"],
                    row["description"],
                    bool(row["is_active"]),
                    datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                    datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
                )
                migrated += 1
                logger.info(f"  Migrated prompt: {row['name']}")

            except Exception as e:
                logger.error(f"  Failed to migrate prompt {row['name']}: {e}")

    return migrated


async def migrate_sessions_to_chat_sessions(sqlite_db: aiosqlite.Connection) -> tuple[int, int]:
    """
    Migrate sessions from SQLite to PostgreSQL chat_sessions and chat_messages.

    Only migrates sessions that have a user_id (authenticated sessions).
    Converts the JSON context array into individual chat_messages rows.
    """
    logger.info("Migrating sessions...")

    sqlite_db.row_factory = aiosqlite.Row
    cursor = await sqlite_db.execute(
        "SELECT * FROM sessions WHERE user_id IS NOT NULL"
    )
    rows = await cursor.fetchall()

    sessions_migrated = 0
    messages_migrated = 0

    async with get_connection() as conn:
        for row in rows:
            try:
                user_id = row["user_id"]

                # Check if user profile exists - create if not
                profile_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM profiles WHERE id = $1)",
                    user_id
                )

                if not profile_exists:
                    logger.info(f"  Creating profile for user: {user_id[:8]}...")
                    # Create a basic profile (email will be synced when user logs in)
                    await conn.execute(
                        """
                        INSERT INTO profiles (id, email, display_name)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        user_id,
                        f"migrated-{user_id[:8]}@placeholder.local",
                        None
                    )

                # Parse context to get title from first user message
                context = json.loads(row["context"]) if row["context"] else []
                title = "Migrated Chat"
                for msg in context:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        title = content[:50] + "..." if len(content) > 50 else content
                        break

                # Create chat session
                session_id = uuid.uuid4()
                created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow()
                last_activity = datetime.fromisoformat(row["last_activity"]) if row["last_activity"] else datetime.utcnow()

                await conn.execute(
                    """
                    INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at, last_message_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    session_id,
                    user_id,
                    title,
                    created_at,
                    last_activity,
                    last_activity,
                    json.loads(row["metadata"]) if row["metadata"] else {}
                )
                sessions_migrated += 1

                # Migrate messages from context
                for i, msg in enumerate(context):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    model = msg.get("model")
                    metadata = {k: v for k, v in msg.items() if k not in ("role", "content", "model")}

                    # Calculate message time (spread messages evenly)
                    msg_time = created_at
                    if len(context) > 1:
                        time_delta = (last_activity - created_at) / len(context)
                        msg_time = created_at + (time_delta * i)

                    await conn.execute(
                        """
                        INSERT INTO chat_messages (session_id, role, content, model, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        session_id,
                        role,
                        content,
                        model,
                        metadata,
                        msg_time
                    )
                    messages_migrated += 1

                logger.info(f"  Migrated session {row['id'][:8]}... ({len(context)} messages)")

            except Exception as e:
                logger.error(f"  Failed to migrate session {row['id'][:8]}...: {e}")

    return sessions_migrated, messages_migrated


async def run_migration():
    """Run the full migration."""
    print("=" * 60)
    print("ChatTwelve: SQLite to PostgreSQL Migration")
    print("=" * 60)

    # Check configuration
    if not settings.POSTGRES_URL:
        print("\nERROR: POSTGRES_URL environment variable not set!")
        print("Please set POSTGRES_URL to your PostgreSQL connection string.")
        print("\nExample:")
        print("  export POSTGRES_URL='postgresql://user:password@host:5432/database'")
        sys.exit(1)

    sqlite_path = settings.DATABASE_PATH
    if not os.path.exists(sqlite_path):
        print(f"\nERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    print(f"\nSource: {sqlite_path}")
    print(f"Target: {settings.POSTGRES_URL.split('@')[1] if '@' in settings.POSTGRES_URL else 'PostgreSQL'}")
    print()

    # Initialize PostgreSQL
    print("Connecting to PostgreSQL...")
    await init_postgres_pool()
    print("Connected!\n")

    # Open SQLite
    async with aiosqlite.connect(sqlite_path) as sqlite_db:
        # Migrate system prompts
        prompts_count = await migrate_system_prompts(sqlite_db)
        print(f"\nMigrated {prompts_count} system prompts")

        # Migrate sessions to chat_sessions + chat_messages
        sessions_count, messages_count = await migrate_sessions_to_chat_sessions(sqlite_db)
        print(f"Migrated {sessions_count} sessions with {messages_count} messages")

    # Close PostgreSQL
    await close_postgres_pool()

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - System prompts migrated: {prompts_count}")
    print(f"  - Chat sessions migrated: {sessions_count}")
    print(f"  - Chat messages migrated: {messages_count}")
    print("\nNote: The SQLite database is preserved. You can delete it manually")
    print("once you've verified the PostgreSQL data is correct.")


if __name__ == "__main__":
    asyncio.run(run_migration())
