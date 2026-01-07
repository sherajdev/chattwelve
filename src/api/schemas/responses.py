"""
Response schemas for ChatTwelve API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Literal
from datetime import datetime


# Response Types
ResponseType = Literal["price", "quote", "historical", "indicator", "conversion", "comparison"]


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Technical error message")


class PriceData(BaseModel):
    """Price response data."""

    symbol: str
    price: float
    change_percent: Optional[float] = None


class QuoteData(BaseModel):
    """Detailed quote response data."""

    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    change_percent: Optional[float] = None
    fifty_two_week_high: Optional[float] = Field(None, alias="52_week_high")
    fifty_two_week_low: Optional[float] = Field(None, alias="52_week_low")

    class Config:
        populate_by_name = True


class CandleData(BaseModel):
    """Single candle data for historical response."""

    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None


class HistoricalData(BaseModel):
    """Historical time series response data."""

    symbol: str
    interval: str
    candles: List[CandleData]


class IndicatorData(BaseModel):
    """Technical indicator response data."""

    symbol: str
    indicator: str
    period: Optional[int] = None
    values: List[dict]


class ConversionData(BaseModel):
    """Currency conversion response data."""

    from_currency: str = Field(..., alias="from")
    to_currency: str = Field(..., alias="to")
    amount: float
    result: float
    rate: float

    class Config:
        populate_by_name = True


class ChatResponse(BaseModel):
    """Successful chat response."""

    answer: str = Field(..., description="Conversational AI response")
    type: ResponseType = Field(..., description="Type of response data")
    data: Any = Field(..., description="Structured data varying by response type")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    formatted_time: str = Field(..., description="Human-readable timestamp")


class ErrorResponse(BaseModel):
    """Error response schema."""

    answer: str = Field(..., description="User-friendly error message")
    error: ErrorDetail = Field(..., description="Error details")
    cached_data: Optional[Any] = Field(
        None,
        description="Stale cached data if available"
    )


class SessionResponse(BaseModel):
    """Session creation response."""

    session_id: str = Field(..., description="Unique session identifier")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    expires_at: Optional[str] = Field(None, description="ISO 8601 expiration timestamp")


class SessionDeleteResponse(BaseModel):
    """Session deletion response."""

    message: str = Field(..., description="Success message")
    session_id: str = Field(..., description="Deleted session ID")


class SessionInfo(BaseModel):
    """Session info for list response."""

    session_id: str = Field(..., description="Unique session identifier")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    last_activity: str = Field(..., description="ISO 8601 last activity timestamp")
    title: Optional[str] = Field(None, description="Session title from metadata")
    message_count: int = Field(0, description="Number of messages in session")


class SessionListResponse(BaseModel):
    """List of sessions response."""

    sessions: List[SessionInfo] = Field(..., description="List of sessions")
    count: int = Field(..., description="Total number of sessions")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")


class MCPHealthResponse(BaseModel):
    """MCP server health check response."""

    status: str = Field(..., description="MCP connection status")
    mcp_server_url: str = Field(..., description="MCP server URL")
    connected: bool = Field(..., description="Whether MCP server is reachable")
    message: Optional[str] = Field(None, description="Additional status message")


class AIHealthResponse(BaseModel):
    """AI service health check response."""

    status: str = Field(..., description="AI service status: healthy, degraded, or unavailable")
    available: bool = Field(..., description="Whether AI service is available")
    primary_model: str = Field(..., description="Configured primary AI model")
    fallback_model: str = Field(..., description="Configured fallback AI model")
    message: Optional[str] = Field(None, description="Additional status message")
    last_error: Optional[str] = Field(None, description="Last error message if any")


class RateLimitError(BaseModel):
    """Rate limit error response."""

    answer: str = Field(
        default="You've made too many requests. Please wait a moment before trying again.",
        description="User-friendly rate limit message"
    )
    error: ErrorDetail = Field(
        default=ErrorDetail(
            code="RATE_LIMITED",
            message="Rate limit exceeded"
        )
    )
    retry_after_seconds: int = Field(..., description="Seconds until rate limit resets")
    requests_made: int = Field(..., description="Number of requests made in window")
    requests_limit: int = Field(..., description="Maximum requests allowed in window")


class PromptResponse(BaseModel):
    """System prompt response."""

    id: str = Field(..., description="Prompt ID")
    user_id: Optional[str] = Field(None, description="User ID (null for system defaults)")
    name: str = Field(..., description="Prompt name")
    prompt: str = Field(..., description="System prompt text")
    description: Optional[str] = Field(None, description="Prompt description")
    is_active: bool = Field(..., description="Whether this is the active prompt")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 update timestamp")


class PromptListResponse(BaseModel):
    """List of system prompts response."""

    prompts: List[PromptResponse] = Field(..., description="List of system prompts")
    count: int = Field(..., description="Total number of prompts")


class PromptDeleteResponse(BaseModel):
    """Prompt deletion response."""

    message: str = Field(..., description="Success message")
    prompt_id: str = Field(..., description="Deleted prompt ID")
