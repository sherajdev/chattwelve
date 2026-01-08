"""
Profile management routes for ChatTwelve API.
Handles user profile CRUD operations using PostgreSQL.
"""

from fastapi import APIRouter, HTTPException, status

from src.core.config import settings
from src.core.logging import get_logger
from src.database.pg_profile_repo import profile_repo
from src.database.pg_session_repo import pg_session_repo
from src.database.pg_message_repo import pg_message_repo
from src.api.schemas.requests import CreateProfileRequest, UpdateProfileRequest, CreateChatSessionRequest
from src.api.schemas.responses import (
    ProfileResponse,
    ChatSessionResponse,
    ChatSessionListResponse,
    ChatMessageResponse,
    ChatMessagesResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/profile", tags=["Profile"])


def _check_postgres_configured():
    """Check if PostgreSQL is configured."""
    if not settings.POSTGRES_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL is not configured. Set POSTGRES_URL environment variable."
        )


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(request: CreateProfileRequest):
    """
    Create a new user profile.

    Called when a user signs up via BetterAuth.
    Creates the profile in PostgreSQL with optional display name and avatar.
    """
    _check_postgres_configured()

    try:
        profile = await profile_repo.create(
            user_id=request.user_id,
            email=request.email,
            display_name=request.display_name,
            avatar_url=request.avatar_url
        )

        return ProfileResponse(
            id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            preferences=profile.preferences,
            created_at=profile.created_at.isoformat() + "Z",
            updated_at=profile.updated_at.isoformat() + "Z"
        )

    except Exception as e:
        logger.error(f"Failed to create profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile"
        )


@router.post("/sync", response_model=ProfileResponse)
async def sync_profile(request: CreateProfileRequest):
    """
    Sync a user profile from BetterAuth.

    Creates the profile if it doesn't exist, or updates if it does.
    Used by BetterAuth callbacks to ensure profile exists.
    """
    _check_postgres_configured()

    try:
        profile = await profile_repo.upsert(
            user_id=request.user_id,
            email=request.email,
            display_name=request.display_name,
            avatar_url=request.avatar_url
        )

        return ProfileResponse(
            id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            preferences=profile.preferences,
            created_at=profile.created_at.isoformat() + "Z",
            updated_at=profile.updated_at.isoformat() + "Z"
        )

    except Exception as e:
        logger.error(f"Failed to sync profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync profile"
        )


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str):
    """
    Get a user profile by ID.

    Returns the profile with all settings and preferences.
    """
    _check_postgres_configured()

    try:
        profile = await profile_repo.get_by_id(user_id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {user_id}"
            )

        return ProfileResponse(
            id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            preferences=profile.preferences,
            created_at=profile.created_at.isoformat() + "Z",
            updated_at=profile.updated_at.isoformat() + "Z"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile"
        )


@router.put("/{user_id}", response_model=ProfileResponse)
async def update_profile(user_id: str, request: UpdateProfileRequest):
    """
    Update a user profile.

    Updates display name, avatar, and/or preferences.
    """
    _check_postgres_configured()

    try:
        # Check if profile exists
        existing = await profile_repo.get_by_id(user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {user_id}"
            )

        # Update profile
        updated = await profile_repo.update(
            user_id=user_id,
            display_name=request.display_name,
            avatar_url=request.avatar_url,
            preferences=request.preferences
        )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )

        # Get updated profile
        profile = await profile_repo.get_by_id(user_id)

        return ProfileResponse(
            id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            preferences=profile.preferences,
            created_at=profile.created_at.isoformat() + "Z",
            updated_at=profile.updated_at.isoformat() + "Z"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update profile {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.patch("/{user_id}/preferences")
async def update_preferences(user_id: str, preferences: dict):
    """
    Merge preferences with existing user preferences.

    Partial update - only updates provided keys.
    """
    _check_postgres_configured()

    try:
        # Check if profile exists
        existing = await profile_repo.get_by_id(user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {user_id}"
            )

        updated = await profile_repo.update_preferences(user_id, preferences)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update preferences"
            )

        return {"message": "Preferences updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update preferences for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )


# Chat session routes (PostgreSQL)
@router.post("/{user_id}/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(user_id: str, request: CreateChatSessionRequest = None):
    """
    Create a new chat session for a user.

    Sessions are linked to authenticated users and persist across logins.
    """
    _check_postgres_configured()

    # Verify user_id matches
    if request and request.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID mismatch"
        )

    try:
        title = request.title if request else "New Chat"
        metadata = request.metadata if request else None

        session = await pg_session_repo.create(
            user_id=user_id,
            title=title,
            metadata=metadata
        )

        return ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at.isoformat() + "Z",
            updated_at=session.updated_at.isoformat() + "Z",
            last_message_at=session.last_message_at.isoformat() + "Z",
            message_count=0
        )

    except Exception as e:
        logger.error(f"Failed to create chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session"
        )


@router.get("/{user_id}/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions(user_id: str, limit: int = 50):
    """
    Get all chat sessions for a user.

    Returns sessions ordered by last message time (newest first).
    """
    _check_postgres_configured()

    try:
        sessions = await pg_session_repo.list_by_user(user_id, limit)

        session_responses = []
        for s in sessions:
            # Get message count
            message_count = await pg_message_repo.get_message_count(s.id)

            session_responses.append(ChatSessionResponse(
                id=s.id,
                user_id=s.user_id,
                title=s.title,
                created_at=s.created_at.isoformat() + "Z",
                updated_at=s.updated_at.isoformat() + "Z",
                last_message_at=s.last_message_at.isoformat() + "Z",
                message_count=message_count
            ))

        return ChatSessionListResponse(
            sessions=session_responses,
            count=len(session_responses)
        )

    except Exception as e:
        logger.error(f"Failed to list sessions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions"
        )


@router.get("/{user_id}/sessions/{session_id}/messages", response_model=ChatMessagesResponse)
async def get_session_messages(user_id: str, session_id: str, limit: int = 100, offset: int = 0):
    """
    Get messages for a chat session.

    Verifies user owns the session before returning messages.
    """
    _check_postgres_configured()

    try:
        # Verify user owns session
        session = await pg_session_repo.get_for_user(session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or unauthorized"
            )

        messages = await pg_message_repo.get_session_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        message_responses = [
            ChatMessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                model=m.model,
                metadata=m.metadata,
                created_at=m.created_at.isoformat() + "Z"
            )
            for m in messages
        ]

        return ChatMessagesResponse(
            messages=message_responses,
            count=len(message_responses),
            session_id=session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )


@router.delete("/{user_id}/sessions/{session_id}")
async def delete_chat_session(user_id: str, session_id: str):
    """
    Delete a chat session and all its messages.

    Verifies user owns the session before deleting.
    """
    _check_postgres_configured()

    try:
        deleted = await pg_session_repo.delete_for_user(session_id, user_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or unauthorized"
            )

        return {"message": "Session deleted successfully", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )
