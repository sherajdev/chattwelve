"""
ChatTwelve - Main FastAPI Application
Conversational AI-powered backend for market data queries
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.logging import logger, log_response_time
from src.database.init_db import init_database
from src.api.schemas.responses import HealthResponse, MCPHealthResponse, AIHealthResponse
from src.services.ai_service import ai_service
from src.api.routes.session import router as session_router
from src.api.routes.chat import router as chat_router
from src.api.routes.prompts import router as prompts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_database()
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Conversational AI-powered backend for market data queries via TwelveData MCP",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session_router)
app.include_router(chat_router)
app.include_router(prompts_router)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Middleware to log response times."""
    import time
    start_time = time.time()

    response = await call_next(request)

    process_time_ms = (time.time() - start_time) * 1000
    log_response_time(request.url.path, process_time_ms)
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))

    return response


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns the application health status, version, and current timestamp.
    """
    now = datetime.utcnow()

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        timestamp=now.isoformat() + "Z"
    )


@app.get("/api/mcp-health", response_model=MCPHealthResponse)
async def mcp_health_check():
    """
    MCP server health check endpoint.

    Checks connectivity to the TwelveData MCP server.
    """
    import httpx

    mcp_url = settings.MCP_SERVER_URL
    connected = False
    message = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{mcp_url}/health")
            connected = response.status_code == 200
            if connected:
                message = "MCP server is healthy"
            else:
                message = f"MCP server returned status {response.status_code}"
    except httpx.ConnectError:
        message = "Failed to connect to MCP server"
    except httpx.TimeoutException:
        message = "Connection to MCP server timed out"
    except Exception as e:
        message = f"Error checking MCP server: {str(e)}"

    status = "connected" if connected else "disconnected"

    return MCPHealthResponse(
        status=status,
        mcp_server_url=mcp_url,
        connected=connected,
        message=message
    )


@app.get("/api/ai-health", response_model=AIHealthResponse)
async def ai_health_check():
    """
    AI service health check endpoint.

    Checks connectivity to OpenRouter and returns AI model configuration.
    """
    model_info = ai_service.get_model_info()

    # Perform health check
    is_healthy, error = await ai_service.health_check()

    if is_healthy:
        status = "healthy"
        message = "OpenRouter API is reachable and responding"
    elif model_info.get("initialized") and not is_healthy:
        status = "degraded"
        message = error or "OpenRouter API check failed but service was previously initialized"
    else:
        status = "unavailable"
        message = error or "AI service is not available"

    return AIHealthResponse(
        status=status,
        available=is_healthy,
        primary_model=model_info.get("primary_model", "unknown"),
        fallback_model=model_info.get("fallback_model", "unknown"),
        message=message,
        last_error=model_info.get("last_error")
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
