"""
Session management routes for ChatTwelve API.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status

from src.core.config import settings
from src.core.logging import logger
from src.database.session_repo import session_repo
from src.api.schemas.requests import CreateSessionRequest
from src.api.schemas.responses import SessionResponse, SessionDeleteResponse


router = APIRouter(prefix="/api/session", tags=["Session"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest = None):
    """
    Create a new conversation session.

    Returns a unique session ID that should be used for subsequent chat requests.
    Sessions expire after the configured timeout period.
    """
    metadata = request.metadata if request else None

    try:
        session = await session_repo.create(metadata=metadata)

        # Calculate expiration time
        expires_at = session.created_at + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)

        return SessionResponse(
            session_id=session.id,
            created_at=session.created_at.isoformat() + "Z",
            expires_at=expires_at.isoformat() + "Z"
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(session_id: str):
    """
    Delete/end a conversation session.

    Removes the session and all associated context from the database.
    """
    try:
        # Check if session exists
        exists = await session_repo.exists(session_id)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )

        # Delete the session
        deleted = await session_repo.delete(session_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete session"
            )

        return SessionDeleteResponse(
            message="Session deleted successfully",
            session_id=session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """
    Get session information.

    Returns session details including creation time and expiration.
    """
    try:
        session = await session_repo.get(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )

        # Calculate expiration time
        expires_at = session.created_at + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)

        return SessionResponse(
            session_id=session.id,
            created_at=session.created_at.isoformat() + "Z",
            expires_at=expires_at.isoformat() + "Z"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session"
        )
