"""
Chat routes for ChatTwelve API.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from src.core.logging import logger
from src.api.schemas.requests import ChatRequest
from src.api.schemas.responses import ChatResponse, ErrorResponse
from src.services.chat_service import chat_service


router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a natural language query about market data.

    Accepts a question and returns both a conversational answer
    and structured market data from TwelveData.
    """
    try:
        response, error = await chat_service.process_chat(
            session_id=request.session_id,
            query=request.query
        )

        if error:
            # Return error response with appropriate status code
            if error.error.code == "SESSION_NOT_FOUND":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error.model_dump()
                )
            elif error.error.code == "SESSION_EXPIRED":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error.model_dump()
                )
            elif error.error.code == "RATE_LIMITED":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error.model_dump()
                )
            elif error.error.code in ("NO_SYMBOL", "NO_INDICATOR", "MISSING_CURRENCIES"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error.model_dump()
                )
            else:
                # Return 200 with error info for MCP errors (service degradation)
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=error.model_dump()
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "answer": "An unexpected error occurred. Please try again.",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
        )
