"""
Logging configuration for ChatTwelve backend.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("chattwelve")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger


# Global logger instance
logger = setup_logging()


def log_request(
    session_id: str,
    query: str,
    endpoint: str = "/api/chat"
) -> None:
    """Log incoming request details."""
    logger.info(
        f"REQUEST | session={session_id[:8]}... | endpoint={endpoint} | query={query[:100]}..."
    )


def log_mcp_call(
    tool: str,
    parameters: dict,
    response_time_ms: float,
    success: bool = True
) -> None:
    """Log MCP tool call details."""
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"MCP_CALL | tool={tool} | params={parameters} | time={response_time_ms:.2f}ms | status={status}"
    )


def log_cache_hit(cache_key: str, query_type: str) -> None:
    """Log cache hit."""
    logger.debug(f"CACHE_HIT | key={cache_key[:16]}... | type={query_type}")


def log_cache_miss(cache_key: str, query_type: str) -> None:
    """Log cache miss."""
    logger.debug(f"CACHE_MISS | key={cache_key[:16]}... | type={query_type}")


def log_error(
    error: Exception,
    context: Optional[str] = None,
    include_traceback: bool = True
) -> None:
    """Log error with optional stack trace."""
    import traceback

    error_msg = f"ERROR | {type(error).__name__}: {str(error)}"
    if context:
        error_msg = f"{error_msg} | context={context}"

    if include_traceback:
        tb = traceback.format_exc()
        logger.error(f"{error_msg}\n{tb}")
    else:
        logger.error(error_msg)


def log_response_time(endpoint: str, response_time_ms: float) -> None:
    """Log endpoint response time for performance monitoring."""
    logger.info(f"RESPONSE_TIME | endpoint={endpoint} | time={response_time_ms:.2f}ms")
