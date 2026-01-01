"""
Request schemas for ChatTwelve API.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    session_id: str = Field(
        ...,
        description="Session ID for conversation context",
        min_length=1,
        max_length=64
    )
    query: str = Field(
        ...,
        description="Natural language question about market data",
        min_length=1,
        max_length=5000
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, v: str) -> str:
        """Ensure query is not just whitespace."""
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session ID format."""
        if not v.strip():
            raise ValueError("Session ID cannot be empty")
        # Allow UUID format or alphanumeric with hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError("Session ID contains invalid characters")
        return v.strip()


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session."""

    metadata: Optional[dict] = Field(
        default=None,
        description="Optional metadata to associate with the session"
    )
