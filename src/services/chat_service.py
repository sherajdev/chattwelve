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
from src.services.mcp_client import mcp_client, MCPToolResult
from src.services.query_processor import query_processor, QueryIntent, ParsedQuery
from src.api.schemas.responses import (
    ChatResponse, ErrorResponse, ErrorDetail,
    PriceData, QuoteData, HistoricalData, CandleData,
    IndicatorData, ConversionData
)


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
        query: str
    ) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """
        Process a chat query.

        Args:
            session_id: Session ID for context
            query: Natural language query

        Returns:
            Tuple of (ChatResponse, None) on success or (None, ErrorResponse) on error
        """
        # Log the request
        log_request(session_id, query)

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

    async def _handle_commodities_list(self) -> Tuple[Optional[ChatResponse], Optional[ErrorResponse]]:
        """Handle commodities list queries."""
        result = await self.mcp_client.list_commodities()

        if not result.success:
            return None, ErrorResponse(
                answer=f"Sorry, I couldn't get the commodities list. {result.error}",
                error=ErrorDetail(
                    code="MCP_ERROR",
                    message=result.error
                )
            )

        now = datetime.utcnow()
        commodities = result.data if isinstance(result.data, list) else []

        return ChatResponse(
            answer=f"Here are the available commodities: {', '.join(commodities) if commodities else 'No commodities available'}",
            type="quote",
            data={"commodities": commodities},
            timestamp=now.isoformat() + "Z",
            formatted_time=now.strftime("%B %d, %Y at %I:%M %p UTC")
        ), None

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
