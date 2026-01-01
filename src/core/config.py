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

    # MCP Server
    MCP_SERVER_URL: str = "http://192.168.50.250:3847"
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

    # AI
    AI_MODEL: str = "openai:gpt-4o-mini"
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
