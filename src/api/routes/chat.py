"""
Chat routes for ChatTwelve API.
"""

import json
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse

from src.core.logging import logger
from src.api.schemas.requests import ChatRequest
from src.api.schemas.responses import ChatResponse, ErrorResponse
from src.services.chat_service import chat_service


router = APIRouter(prefix="/api/chat", tags=["Chat"])


async def generate_sse_events(
    session_id: str,
    query: str
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events for chat response streaming.

    Simulates streaming by breaking the response into chunks.

    Args:
        session_id: Session ID for the request
        query: Natural language query

    Yields:
        SSE-formatted event strings
    """
    try:
        # Send processing event
        yield f"event: processing\ndata: {json.dumps({'status': 'processing', 'query': query})}\n\n"
        await asyncio.sleep(0.1)  # Small delay for client to receive processing event

        # Process the chat request
        response, error = await chat_service.process_chat(
            session_id=session_id,
            query=query
        )

        if error:
            # Send error event
            yield f"event: error\ndata: {json.dumps(error.model_dump())}\n\n"
            return

        # Stream the response in chunks (simulated streaming of the answer)
        response_data = response.model_dump()
        answer = response_data.get("answer", "")

        # Stream answer in word chunks
        words = answer.split()
        accumulated = []

        for i, word in enumerate(words):
            accumulated.append(word)
            chunk_data = {
                "type": "chunk",
                "content": word,
                "accumulated": " ".join(accumulated),
                "progress": (i + 1) / len(words)
            }
            yield f"event: chunk\ndata: {json.dumps(chunk_data)}\n\n"
            await asyncio.sleep(0.02)  # Small delay between chunks

        # Send complete response event
        yield f"event: complete\ndata: {json.dumps(response_data)}\n\n"

        # Send done event
        yield f"event: done\ndata: {json.dumps({'status': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"SSE streaming error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


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


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Process a natural language query with streaming response.

    Returns a Server-Sent Events stream with the response chunks,
    allowing clients to display the answer progressively.

    Event types:
    - processing: Initial event indicating query is being processed
    - chunk: Individual word/token being streamed
    - complete: Full response data
    - done: Stream complete
    - error: Error occurred
    """
    return StreamingResponse(
        generate_sse_events(request.session_id, request.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
