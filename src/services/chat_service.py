"""
Chat service for handling natural language market data queries.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from src.core.config import settings
from src.core.logging import logger, log_request
from src.database.session_repo import session_repo, Session
from src.database.cache_repo import cache_repo
from src.database.pg_session_repo import PgSessionRepository
from src.database.pg_message_repo import PgMessageRepository
from src.services.mcp_client import mcp_client, MCPToolResult
from src.services.query_processor import query_processor, QueryIntent, ParsedQuery
from src.services.ai_agent_service import ai_agent_service
from src.api.schemas.responses import (
    ChatResponse, ErrorResponse, ErrorDetail,
    PriceData, QuoteData, HistoricalData, CandleData,
    IndicatorData, ConversionData
)

# PostgreSQL repositories (initialized lazily)
_pg_session_repo: Optional[PgSessionRepository] = None
_pg_message_repo: Optional[PgMessageRepository] = None


def get_pg_session_repo() -> PgSessionRepository:
    """Get PostgreSQL session repository (lazy init)."""
    global _pg_session_repo
    if _pg_session_repo is None:
        _pg_session_repo = PgSessionRepository()
    return _pg_session_repo


def get_pg_message_repo() -> PgMessageRepository:
    """Get PostgreSQL message repository (lazy init)."""
    global _pg_message_repo
    if _pg_message_repo is None:
        _pg_message_repo = PgMessageRepository()
    return _pg_message_repo


class ChatService:
    """Service for handling chat requests."""

    def __init__(self):
        self.session_repo = session_repo
        self.cache_repo = cache_repo
        self.mcp_client = mcp_client
        self.query_processor = query_processor

    async def process_chat(
        self,
        session_id: str,
        query: str,
        user_id: Optional[str] = None
    ) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """
        Process a chat query.

        Args:
            session_id: Session ID for context
            query: Natural language query
            user_id: Optional authenticated user ID for PostgreSQL storage

        Returns:
            Tuple of (ChatResponse, None) on success or (None, ErrorResponse) on error
        """
        # Log the request
        log_request(session_id, query)

        # Use AI agent mode if enabled
        if settings.USE_AI_AGENT:
            return await self._process_with_ai_agent(session_id, query, user_id)

        # Validate session (with expiry check)
        session = await self.session_repo.get(session_id, check_expiry=True)
        if not session:
            # Check if session exists but is expired
            session_raw = await self.session_repo.get(session_id, check_expiry=False)
            if session_raw and self.session_repo.is_expired(session_raw):
                return None, ErrorResponse(
                    answer="Your session has expired. Please create a new session to continue.",
                    error=ErrorDetail(
                        code="SESSION_EXPIRED",
                        message=f"Session {session_id} has expired due to inactivity"
                    )
                )
            return None, ErrorResponse(
                answer="Session not found. Please create a new session.",
                error=ErrorDetail(
                    code="SESSION_NOT_FOUND",
                    message=f"Session {session_id} does not exist"
                )
            )

        # Check rate limit
        try:
            count, seconds_until_reset = await self.session_repo.increment_request_count(session_id)
            if count > settings.RATE_LIMIT_REQUESTS:
                return None, ErrorResponse(
                    answer=f"You've made too many requests. Please wait {seconds_until_reset} seconds before trying again.",
                    error=ErrorDetail(
                        code="RATE_LIMITED",
                        message=f"Rate limit exceeded: {count}/{settings.RATE_LIMIT_REQUESTS} requests"
                    )
                )
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")

        # Parse the query with session context for follow-up handling
        parsed = self.query_processor.parse(query, context=session.context)
        logger.info(f"Parsed query: intent={parsed.intent.value}, symbols={parsed.symbols}")

        # Handle the query based on intent
        try:
            if parsed.intent == QueryIntent.PRICE:
                response, error = await self._handle_price_query(parsed)
            elif parsed.intent == QueryIntent.QUOTE:
                response, error = await self._handle_quote_query(parsed)
            elif parsed.intent == QueryIntent.HISTORICAL:
                response, error = await self._handle_historical_query(parsed)
            elif parsed.intent == QueryIntent.INDICATOR:
                response, error = await self._handle_indicator_query(parsed)
            elif parsed.intent == QueryIntent.CONVERSION:
                response, error = await self._handle_conversion_query(parsed)
            elif parsed.intent == QueryIntent.COMMODITIES_LIST:
                response, error = await self._handle_commodities_list()
            else:
                response, error = await self._handle_price_query(parsed)

            # Update session context with this query's info (for follow-ups)
            if response and parsed.symbols:
                await self._update_session_context(session_id, session.context, parsed)

            return response, error

        except Exception as e:
            logger.error(f"Error processing chat: {e}")
            return None, ErrorResponse(
                answer="Sorry, I encountered an error processing your request. Please try again.",
                error=ErrorDetail(
                    code="PROCESSING_ERROR",
                    message=str(e)
                )
            )

    async def _process_with_ai_agent(
        self,
        session_id: str,
        query: str,
        user_id: Optional[str] = None
    ) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """
        Process chat query using AI agent with tool calling.

        Args:
            session_id: Session ID for context
            query: Natural language query
            user_id: Optional authenticated user ID for PostgreSQL storage

        Returns:
            Tuple of (ChatResponse, None) on success or (None, ErrorResponse) on error
        """
        session_context = []

        # If user_id provided, use PostgreSQL sessions
        if user_id:
            try:
                pg_session_repo = get_pg_session_repo()
                pg_message_repo = get_pg_message_repo()

                # Validate PostgreSQL session exists
                pg_session = await pg_session_repo.get(session_id)
                if not pg_session:
                    return None, ErrorResponse(
                        answer="Session not found. Please create a new session.",
                        error=ErrorDetail(
                            code="SESSION_NOT_FOUND",
                            message=f"Session {session_id} does not exist"
                        )
                    )

                # Verify session belongs to user
                if pg_session.user_id != user_id:
                    return None, ErrorResponse(
                        answer="You don't have access to this session.",
                        error=ErrorDetail(
                            code="SESSION_ACCESS_DENIED",
                            message="Session does not belong to this user"
                        )
                    )

                # Load recent messages as context
                recent_messages = await pg_message_repo.get_recent_messages(session_id, limit=10)
                session_context = [
                    {"role": m.role, "content": m.content[:200]}
                    for m in recent_messages
                ]

                # Save user message to PostgreSQL
                await pg_message_repo.add(
                    session_id=session_id,
                    role="user",
                    content=query
                )

            except Exception as e:
                logger.error(f"PostgreSQL session error: {e}")
                # Fall through to SQLite if PostgreSQL fails
                user_id = None

        # Fall back to SQLite sessions for guests or if PostgreSQL failed
        if not user_id:
            # Validate session (with expiry check)
            session = await self.session_repo.get(session_id, check_expiry=True)
            if not session:
                # Check if session exists but is expired
                session_raw = await self.session_repo.get(session_id, check_expiry=False)
                if session_raw and self.session_repo.is_expired(session_raw):
                    return None, ErrorResponse(
                        answer="Your session has expired. Please create a new session to continue.",
                        error=ErrorDetail(
                            code="SESSION_EXPIRED",
                            message=f"Session {session_id} has expired due to inactivity"
                        )
                    )
                return None, ErrorResponse(
                    answer="Session not found. Please create a new session.",
                    error=ErrorDetail(
                        code="SESSION_NOT_FOUND",
                        message=f"Session {session_id} does not exist"
                    )
                )

            # Check rate limit (only for SQLite sessions)
            try:
                count, seconds_until_reset = await self.session_repo.increment_request_count(session_id)
                if count > settings.RATE_LIMIT_REQUESTS:
                    return None, ErrorResponse(
                        answer=f"You've made too many requests. Please wait {seconds_until_reset} seconds before trying again.",
                        error=ErrorDetail(
                            code="RATE_LIMITED",
                            message=f"Rate limit exceeded: {count}/{settings.RATE_LIMIT_REQUESTS} requests"
                        )
                    )
            except Exception as e:
                logger.error(f"Rate limit check failed: {e}")

            session_context = session.context

        # Run the AI agent
        try:
            result = await ai_agent_service.run_agent(
                user_query=query,
                session_context={"context": session_context}
            )

            if not result.success:
                return None, ErrorResponse(
                    answer="I encountered an error processing your request. Please try again.",
                    error=ErrorDetail(
                        code="AI_AGENT_ERROR",
                        message=result.error or "Unknown error"
                    )
                )

            now = datetime.utcnow()

            # Save response based on storage type
            if user_id:
                # Save assistant message to PostgreSQL
                try:
                    pg_message_repo = get_pg_message_repo()
                    pg_session_repo = get_pg_session_repo()

                    await pg_message_repo.add(
                        session_id=session_id,
                        role="assistant",
                        content=result.content,
                        model=result.model_used,
                        metadata={
                            "tools_used": result.tools_used,
                            "used_fallback": result.used_fallback
                        }
                    )

                    # Update session title if it's still default
                    pg_session = await pg_session_repo.get(session_id)
                    if pg_session and pg_session.title == "New Chat":
                        new_title = query[:50] + ("..." if len(query) > 50 else "")
                        await pg_session_repo.update_title(session_id, new_title)

                except Exception as e:
                    logger.error(f"Failed to save message to PostgreSQL: {e}")
            else:
                # Update SQLite session context
                context_entry = {
                    "query": query,
                    "response": result.content[:200],  # Store summary
                    "tools_used": result.tools_used,
                    "timestamp": now.isoformat()
                }
                new_context = session_context[-9:] + [context_entry]
                await self.session_repo.update_context(session_id, new_context)

            # Return AI agent response
            return ChatResponse(
                answer=result.content,
                type="price",  # Generic type for AI responses
                data={
                    "model_used": result.model_used,
                    "tools_used": result.tools_used,
                    "used_fallback": result.used_fallback
                },
                timestamp=now.isoformat() + "Z",
                formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
            ), None

        except Exception as e:
            logger.error(f"AI agent error: {e}")
            return None, ErrorResponse(
                answer="Sorry, I encountered an error processing your request. Please try again.",
                error=ErrorDetail(
                    code="AI_AGENT_ERROR",
                    message=str(e)
                )
            )

    async def _update_session_context(
        self,
        session_id: str,
        current_context: list,
        parsed: ParsedQuery
    ) -> None:
        """
        Update session context with the current query's information.

        Stores symbol and intent info for follow-up query handling.

        Args:
            session_id: Session ID to update
            current_context: Current context list
            parsed: Parsed query with extracted parameters
        """
        try:
            # Create context entry for this query
            context_entry = {
                "query": parsed.raw_query,
                "symbols": parsed.symbols,
                "intent": parsed.intent.value,
                "indicator": parsed.indicator,
                "interval": parsed.interval,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Append to context (limit to last 10 entries to prevent bloat)
            new_context = current_context[-9:] + [context_entry]

            # Update in database
            await self.session_repo.update_context(session_id, new_context)
            logger.debug(f"Updated session context: {len(new_context)} entries")
        except Exception as e:
            logger.error(f"Failed to update session context: {e}")

    async def _handle_price_query(self, parsed: ParsedQuery) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle price queries."""
        if not parsed.symbols:
            return None, ErrorResponse(
                answer="I couldn't identify a trading symbol in your query. Please specify a symbol like 'gold', 'AAPL', or 'EUR/USD'.",
                error=ErrorDetail(
                    code="NO_SYMBOL",
                    message="No trading symbol found in query"
                )
            )

        symbol = parsed.symbols[0]

        # Check cache first
        cache_params = {"symbol": symbol}
        cached = await self.cache_repo.get("price", cache_params)
        if cached and not cached.get("_stale"):
            return self._format_price_response(symbol, cached)

        # Call MCP
        result = await self.mcp_client.get_price(symbol)

        if not result.success:
            # Try to serve stale cache
            cached = await self.cache_repo.get("price", cache_params, allow_stale=True)
            if cached:
                response, _ = self._format_price_response(symbol, cached)
                response.answer = f"⚠️ Using cached data (may be stale): {response.answer}"
                return response, None

            return None, ErrorResponse(
                answer=f"Sorry, I couldn't get the price for {symbol}. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        # Cache the result
        await self.cache_repo.set("price", cache_params, result.data)

        return self._format_price_response(symbol, result.data)

    async def _handle_quote_query(self, parsed: ParsedQuery) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle detailed quote queries."""
        if not parsed.symbols:
            return None, ErrorResponse(
                answer="I couldn't identify a trading symbol. Please specify a symbol like 'AAPL' or 'EUR/USD'.",
                error=ErrorDetail(
                    code="NO_SYMBOL",
                    message="No trading symbol found in query"
                )
            )

        symbol = parsed.symbols[0]

        # Check cache
        cache_params = {"symbol": symbol}
        cached = await self.cache_repo.get("quote", cache_params)
        if cached and not cached.get("_stale"):
            return self._format_quote_response(symbol, cached)

        # Call MCP
        result = await self.mcp_client.get_quote(symbol)

        if not result.success:
            cached = await self.cache_repo.get("quote", cache_params, allow_stale=True)
            if cached:
                response, _ = self._format_quote_response(symbol, cached)
                response.answer = f"⚠️ Using cached data: {response.answer}"
                return response, None

            return None, ErrorResponse(
                answer=f"Sorry, I couldn't get quote data for {symbol}. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        await self.cache_repo.set("quote", cache_params, result.data)
        return self._format_quote_response(symbol, result.data)

    async def _handle_historical_query(self, parsed: ParsedQuery) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle historical data queries."""
        if not parsed.symbols:
            return None, ErrorResponse(
                answer="Please specify a symbol to get historical data for.",
                error=ErrorDetail(
                    code="NO_SYMBOL",
                    message="No trading symbol found in query"
                )
            )

        symbol = parsed.symbols[0]

        # Check cache
        cache_params = {
            "symbol": symbol,
            "interval": parsed.interval,
            "outputsize": parsed.outputsize
        }
        cached = await self.cache_repo.get("historical", cache_params)
        if cached and not cached.get("_stale"):
            return self._format_historical_response(symbol, parsed.interval, cached)

        # Call MCP
        result = await self.mcp_client.get_time_series(
            symbol=symbol,
            interval=parsed.interval,
            outputsize=parsed.outputsize
        )

        if not result.success:
            cached = await self.cache_repo.get("historical", cache_params, allow_stale=True)
            if cached:
                response, _ = self._format_historical_response(symbol, parsed.interval, cached)
                response.answer = f"⚠️ Using cached data: {response.answer}"
                return response, None

            return None, ErrorResponse(
                answer=f"Sorry, I couldn't get historical data for {symbol}. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        await self.cache_repo.set("historical", cache_params, result.data)
        return self._format_historical_response(symbol, parsed.interval, result.data)

    async def _handle_indicator_query(self, parsed: ParsedQuery) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle technical indicator queries."""
        if not parsed.symbols:
            return None, ErrorResponse(
                answer="Please specify a symbol to calculate the indicator for.",
                error=ErrorDetail(
                    code="NO_SYMBOL",
                    message="No trading symbol found in query"
                )
            )

        if not parsed.indicator:
            return None, ErrorResponse(
                answer="Please specify which indicator you want (e.g., RSI, SMA, MACD).",
                error=ErrorDetail(
                    code="NO_INDICATOR",
                    message="No indicator specified in query"
                )
            )

        symbol = parsed.symbols[0]

        # Check cache
        cache_params = {
            "symbol": symbol,
            "indicator": parsed.indicator,
            "interval": parsed.interval,
            "time_period": parsed.time_period
        }
        cached = await self.cache_repo.get("indicator", cache_params)
        if cached and not cached.get("_stale"):
            return self._format_indicator_response(symbol, parsed.indicator, parsed.time_period, cached)

        # Call MCP
        result = await self.mcp_client.technical_indicator(
            symbol=symbol,
            indicator=parsed.indicator,
            interval=parsed.interval,
            time_period=parsed.time_period,
            outputsize=parsed.outputsize
        )

        if not result.success:
            cached = await self.cache_repo.get("indicator", cache_params, allow_stale=True)
            if cached:
                response, _ = self._format_indicator_response(symbol, parsed.indicator, parsed.time_period, cached)
                response.answer = f"⚠️ Using cached data: {response.answer}"
                return response, None

            return None, ErrorResponse(
                answer=f"Sorry, I couldn't calculate {parsed.indicator.upper()} for {symbol}. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        await self.cache_repo.set("indicator", cache_params, result.data)
        return self._format_indicator_response(symbol, parsed.indicator, parsed.time_period, result.data)

    async def _handle_conversion_query(self, parsed: ParsedQuery) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle currency conversion queries."""
        if not parsed.from_currency or not parsed.to_currency:
            return None, ErrorResponse(
                answer="Please specify both currencies for conversion (e.g., 'convert 100 USD to EUR').",
                error=ErrorDetail(
                    code="MISSING_CURRENCIES",
                    message="Need both source and target currencies"
                )
            )

        amount = parsed.amount or 1.0

        # Call MCP
        result = await self.mcp_client.convert_currency(
            from_currency=parsed.from_currency,
            to_currency=parsed.to_currency,
            amount=amount
        )

        if not result.success:
            return None, ErrorResponse(
                answer=f"Sorry, I couldn't convert {parsed.from_currency} to {parsed.to_currency}. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        return self._format_conversion_response(parsed.from_currency, parsed.to_currency, amount, result.data)

    # Known commodities as fallback when MCP server is unavailable
    KNOWN_COMMODITIES = [
        {"symbol": "XAU/USD", "name": "Gold"},
        {"symbol": "XAG/USD", "name": "Silver"},
        {"symbol": "XPT/USD", "name": "Platinum"},
        {"symbol": "XPD/USD", "name": "Palladium"},
        {"symbol": "NG", "name": "Natural Gas"},
        {"symbol": "CL", "name": "Crude Oil WTI"},
        {"symbol": "BZ", "name": "Brent Crude Oil"},
        {"symbol": "HG", "name": "Copper"},
        {"symbol": "ZC", "name": "Corn"},
        {"symbol": "ZW", "name": "Wheat"},
        {"symbol": "ZS", "name": "Soybeans"},
        {"symbol": "KC", "name": "Coffee"},
        {"symbol": "CT", "name": "Cotton"},
        {"symbol": "SB", "name": "Sugar"},
    ]

    async def _handle_commodities_list(self) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle commodities list queries."""
        now = datetime.utcnow()

        # Check cache first
        cache_params = {"type": "commodities_list"}
        cached = await self.cache_repo.get("commodities", cache_params)
        if cached and not cached.get("_stale"):
            commodities = cached.get("commodities", [])
            return ChatResponse(
                answer=f"Here are the available commodities: {self._format_commodities_list(commodities)}",
                type="quote",
                data={"commodities": commodities},
                timestamp=now.isoformat() + "Z",
                formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
            ), None

        # Try MCP server
        result = await self.mcp_client.list_commodities()

        if result.success:
            # Parse commodities from MCP response
            commodities = result.data if isinstance(result.data, list) else []
            # Cache the result
            await self.cache_repo.set("commodities", cache_params, {"commodities": commodities})
        else:
            # Try stale cache first
            cached = await self.cache_repo.get("commodities", cache_params, allow_stale=True)
            if cached:
                commodities = cached.get("commodities", [])
                return ChatResponse(
                    answer=f"⚠️ Using cached data: Here are the available commodities: {self._format_commodities_list(commodities)}",
                    type="quote",
                    data={"commodities": commodities},
                    timestamp=now.isoformat() + "Z",
                    formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
                ), None

            # Use fallback known commodities list
            commodities = self.KNOWN_COMMODITIES
            return ChatResponse(
                answer=f"⚠️ Using known commodities list (MCP unavailable): {self._format_commodities_list(commodities)}",
                type="quote",
                data={"commodities": commodities},
                timestamp=now.isoformat() + "Z",
                formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
            ), None

        return ChatResponse(
            answer=f"Here are the available commodities: {self._format_commodities_list(commodities)}",
            type="quote",
            data={"commodities": commodities},
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

    def _format_commodities_list(self, commodities: list) -> str:
        """Format commodities list for display."""
        if not commodities:
            return "No commodities available"

        # Handle both simple string list and dict list formats
        formatted = []
        for item in commodities:
            if isinstance(item, dict):
                name = item.get("name", "")
                symbol = item.get("symbol", "")
                if name and symbol:
                    formatted.append(f"{name} ({symbol})")
                elif symbol:
                    formatted.append(symbol)
                elif name:
                    formatted.append(name)
            else:
                formatted.append(str(item))

        return ", ".join(formatted) if formatted else "No commodities available"

    def _format_price_response(self, symbol: str, data: Dict[str, Any]) -> Tuple[ChatResponse, None]:
        """Format a price response."""
        now = datetime.utcnow()

        # Extract price from various possible response formats (convert to float)
        price_raw = data.get("price") or data.get("close") or data.get("last") or 0
        price = float(price_raw) if price_raw else 0

        change_percent_raw = data.get("change_percent") or data.get("percent_change") or data.get("change")
        change_percent = float(change_percent_raw) if change_percent_raw else None

        # Format the conversational answer
        if change_percent is not None:
            direction = "up" if change_percent > 0 else "down"
            answer = f"The current price of {symbol} is ${price:.2f}, {direction} {abs(change_percent):.2f}% today."
        else:
            answer = f"The current price of {symbol} is ${price:.2f}."

        return ChatResponse(
            answer=answer,
            type="price",
            data=PriceData(
                symbol=symbol,
                price=price,
                change_percent=change_percent
            ).model_dump(),
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

    def _format_quote_response(self, symbol: str, data: Dict[str, Any]) -> Tuple[ChatResponse, None]:
        """Format a quote response."""
        now = datetime.utcnow()

        open_price = data.get("open", 0)
        high = data.get("high", 0)
        low = data.get("low", 0)
        close = data.get("close", 0)
        volume = data.get("volume")
        change_percent = data.get("change_percent") or data.get("percent_change")
        high_52 = data.get("fifty_two_week_high") or data.get("52_week_high")
        low_52 = data.get("fifty_two_week_low") or data.get("52_week_low")

        answer = (
            f"Here's the detailed quote for {symbol}: "
            f"Open: ${float(open_price):.2f}, High: ${float(high):.2f}, Low: ${float(low):.2f}, Close: ${float(close):.2f}"
        )
        if volume:
            answer += f", Volume: {int(volume):,}"
        if change_percent:
            answer += f", Change: {float(change_percent):.2f}%"

        return ChatResponse(
            answer=answer,
            type="quote",
            data=QuoteData(
                symbol=symbol,
                open=float(open_price),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=int(volume) if volume else None,
                change_percent=float(change_percent) if change_percent else None,
                fifty_two_week_high=float(high_52) if high_52 else None,
                fifty_two_week_low=float(low_52) if low_52 else None
            ).model_dump(),
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

    def _format_historical_response(
        self,
        symbol: str,
        interval: str,
        data: Dict[str, Any]
    ) -> Tuple[ChatResponse, None]:
        """Format a historical data response."""
        now = datetime.utcnow()

        # Extract candles from data
        values = data.get("values") or data.get("candles") or data.get("data") or []

        candles = []
        for v in values[:100]:  # Limit to 100 candles
            candles.append(CandleData(
                datetime=v.get("datetime", ""),
                open=float(v.get("open", 0)),
                high=float(v.get("high", 0)),
                low=float(v.get("low", 0)),
                close=float(v.get("close", 0)),
                volume=int(v.get("volume")) if v.get("volume") else None
            ))

        answer = f"Here's the {interval} historical data for {symbol}. I found {len(candles)} candles."

        return ChatResponse(
            answer=answer,
            type="historical",
            data=HistoricalData(
                symbol=symbol,
                interval=interval,
                candles=[c.model_dump() for c in candles]
            ).model_dump(),
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

    def _format_indicator_response(
        self,
        symbol: str,
        indicator: str,
        period: int,
        data: Dict[str, Any]
    ) -> Tuple[ChatResponse, None]:
        """Format a technical indicator response."""
        now = datetime.utcnow()

        values = data.get("values") or data.get("data") or []

        answer = f"Here's the {indicator.upper()}({period}) for {symbol}. I calculated {len(values)} data points."

        return ChatResponse(
            answer=answer,
            type="indicator",
            data=IndicatorData(
                symbol=symbol,
                indicator=indicator.upper(),
                period=period,
                values=values[:100]  # Limit values
            ).model_dump(),
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

    def _format_conversion_response(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
        data: Dict[str, Any]
    ) -> Tuple[ChatResponse, None]:
        """Format a conversion response."""
        now = datetime.utcnow()

        rate = data.get("rate") or data.get("exchange_rate") or 1.0
        result = data.get("result") or data.get("amount") or (amount * float(rate))

        answer = f"{amount:.2f} {from_currency} equals {float(result):.2f} {to_currency} (rate: {float(rate):.4f})."

        return ChatResponse(
            answer=answer,
            type="conversion",
            data=ConversionData(
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                result=float(result),
                rate=float(rate)
            ).model_dump(by_alias=True),
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None


# Global chat service instance
chat_service = ChatService()
