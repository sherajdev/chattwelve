"""
Configuration settings for ChatTwelve backend.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ChatTwelve"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./chattwelve.db"
    DATABASE_PATH: str = "./chattwelve.db"

    # MCP Server (set via MCP_SERVER_URL environment variable)
    MCP_SERVER_URL: str = "http://localhost:3847"
    MCP_TIMEOUT_SECONDS: int = 30

    # Session
    SESSION_TIMEOUT_MINUTES: int = 60
    SESSION_CLEANUP_INTERVAL_MINUTES: int = 15

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Cache TTL (seconds)
    CACHE_TTL_PRICE: int = 45  # 30-60 seconds for price data
    CACHE_TTL_HISTORICAL: int = 300  # 5 minutes for historical data
    CACHE_TTL_INDICATOR: int = 300  # 5 minutes for indicator data

    # Query Limits
    MAX_QUERY_LENGTH: int = 5000

    # AI - OpenRouter
    OPENROUTER_API_KEY: Optional[str] = None
    AI_PRIMARY_MODEL: str = "openai/gpt-5.2"
    AI_FALLBACK_MODEL: str = "google/gemini-3-flash-preview"
    AI_APP_URL: Optional[str] = None  # Optional: for OpenRouter analytics
    AI_APP_TITLE: str = "ChatTwelve"
    USE_AI_AGENT: bool = True  # Use AI agent with tool calling (True) or manual routing (False)

    # Web Search - Tavily API
    TAVILY_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
