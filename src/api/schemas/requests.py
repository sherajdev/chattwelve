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
    user_id: Optional[str] = Field(
        default=None,
        description="Optional authenticated user ID to associate with the session"
    )


class CreatePromptRequest(BaseModel):
    """Request schema for creating a new system prompt."""

    name: str = Field(
        ...,
        description="Unique name for the prompt",
        min_length=1,
        max_length=100
    )
    prompt: str = Field(
        ...,
        description="The system prompt text",
        min_length=1,
        max_length=10000
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description of the prompt",
        max_length=500
    )
    is_active: bool = Field(
        default=False,
        description="Whether this should be the active prompt"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID to associate prompt with a specific user"
    )

    @field_validator("name", "prompt")
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        """Ensure fields are not just whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class UpdatePromptRequest(BaseModel):
    """Request schema for updating a system prompt."""

    name: Optional[str] = Field(
        default=None,
        description="New name for the prompt",
        min_length=1,
        max_length=100
    )
    prompt: Optional[str] = Field(
        default=None,
        description="New prompt text",
        min_length=1,
        max_length=10000
    )
    description: Optional[str] = Field(
        default=None,
        description="New description",
        max_length=500
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="New active status"
    )

    @field_validator("name", "prompt")
    @classmethod
    def validate_not_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Ensure fields are not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip() if v else None
