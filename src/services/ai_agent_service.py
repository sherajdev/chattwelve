"""
AI Agent Service with Pydantic AI tools support.

This service provides an autonomous AI agent that can use tools to:
- Fetch market data via MCP tools
- Search the web for real-time information
- Answer financial questions with context
"""

from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging
import httpx

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.core.config import settings
from src.services.mcp_client import mcp_client
from src.database.prompt_repo import prompt_repo

logger = logging.getLogger(__name__)


class AIAgentServiceError(Exception):
    """Base exception for AI agent service errors."""
    pass


class AIAgentServiceUnavailable(AIAgentServiceError):
    """Raised when AI service is unavailable."""
    pass


class AIAgentServiceConfigError(AIAgentServiceError):
    """Raised when AI service is misconfigured."""
    pass


@dataclass
class AgentResponse:
    """Response from AI agent with metadata."""
    content: str
    model_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    used_fallback: bool = False
    tools_used: list = None


class Dependencies(BaseModel):
    """Dependencies passed to tools."""
    session_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AIAgentService:
    """Service for AI agent with tool calling capabilities."""

    OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

    def __init__(self):
        self._provider: Optional[OpenRouterProvider] = None
        self._primary_model: Optional[OpenRouterModel] = None
        self._fallback_model: Optional[OpenRouterModel] = None
        self._model: Optional[FallbackModel] = None
        self._agent: Optional[Agent] = None
        self._initialized = False
        self._available = True
        self._last_error: Optional[str] = None

    def _ensure_initialized(self) -> None:
        """Initialize the AI models and agent lazily."""
        if self._initialized:
            return

        if not settings.OPENROUTER_API_KEY:
            raise AIAgentServiceConfigError("OPENROUTER_API_KEY is not set in environment variables")

        try:
            # Create the provider
            self._provider = OpenRouterProvider(
                api_key=settings.OPENROUTER_API_KEY,
                app_url=settings.AI_APP_URL,
                app_title=settings.AI_APP_TITLE,
            )

            # Create primary model
            self._primary_model = OpenRouterModel(
                settings.AI_PRIMARY_MODEL,
                provider=self._provider,
            )
            logger.info(f"Primary AI model initialized: {settings.AI_PRIMARY_MODEL}")

            # Create fallback model
            self._fallback_model = OpenRouterModel(
                settings.AI_FALLBACK_MODEL,
                provider=self._provider,
            )
            logger.info(f"Fallback AI model initialized: {settings.AI_FALLBACK_MODEL}")

            # Create fallback model chain
            self._model = FallbackModel(self._primary_model, self._fallback_model)
            logger.info("AI service initialized with fallback support")

            self._initialized = True
            self._available = True

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Failed to initialize AI agent service: {e}")
            raise AIAgentServiceConfigError(f"Failed to initialize AI agent service: {e}")

    async def _get_system_prompt(self) -> str:
        """Get the active system prompt from database or use default."""
        try:
            active_prompt = await prompt_repo.get_active_prompt()
            if active_prompt:
                return active_prompt.prompt
        except Exception as e:
            logger.warning(f"Failed to get active prompt from database: {e}")

        # Fallback to default prompt
        return """You are a helpful financial data assistant powered by ChatTwelve.

Your role is to help users get real-time financial market data including stock prices, quotes, historical data, technical indicators, and currency conversions.

You have access to various tools to fetch this data. Use them wisely based on what the user asks for:
- For current prices: use get_price
- For detailed quotes: use get_quote
- For historical data: use get_historical_data
- For technical indicators: use get_technical_indicator
- For currency conversions: use convert_currency
- For general web search: use web_search

Always be conversational, accurate, and cite the data source. If you're unsure about something, ask clarifying questions."""

    async def _create_agent(self) -> Agent:
        """Create or recreate the agent with tools and current system prompt."""
        self._ensure_initialized()

        # Get system prompt from database
        system_prompt = await self._get_system_prompt()

        # Create agent with model and system prompt
        agent = Agent(
            self._model,
            deps_type=Dependencies,
            system_prompt=system_prompt
        )

        # Register tools
        self._register_tools(agent)

        logger.info("AI agent created with tools")
        return agent

    def _register_tools(self, agent: Agent) -> None:
        """Register all tools with the agent."""

        @agent.tool
        async def get_price(ctx: RunContext[Dependencies], symbol: str) -> Dict[str, Any]:
            """
            Get the current real-time price for a stock, commodity, or cryptocurrency.

            Args:
                ctx: Runtime context
                symbol: Trading symbol (e.g., AAPL, XAU/USD, BTC/USD)

            Returns:
                Dictionary with price data including current price and percent change
            """
            logger.info(f"Tool called: get_price({symbol})")
            result = await mcp_client.get_price(symbol)

            if not result.success:
                return {"error": result.error, "success": False}

            return {"success": True, "data": result.data}

        @agent.tool
        async def get_quote(ctx: RunContext[Dependencies], symbol: str) -> Dict[str, Any]:
            """
            Get detailed quote information for a symbol including OHLC, volume, and 52-week range.

            Args:
                ctx: Runtime context
                symbol: Trading symbol (e.g., AAPL, GOOGL)

            Returns:
                Dictionary with detailed quote data
            """
            logger.info(f"Tool called: get_quote({symbol})")
            result = await mcp_client.get_quote(symbol)

            if not result.success:
                return {"error": result.error, "success": False}

            return {"success": True, "data": result.data}

        @agent.tool
        async def get_historical_data(
            ctx: RunContext[Dependencies],
            symbol: str,
            interval: str = "1day",
            outputsize: int = 30
        ) -> Dict[str, Any]:
            """
            Get historical OHLC (Open, High, Low, Close) candlestick data for a symbol.

            Args:
                ctx: Runtime context
                symbol: Trading symbol
                interval: Time interval (e.g., 1min, 5min, 1hour, 1day)
                outputsize: Number of data points to return

            Returns:
                Dictionary with historical candle data
            """
            logger.info(f"Tool called: get_historical_data({symbol}, {interval}, {outputsize})")
            result = await mcp_client.get_time_series(
                symbol=symbol,
                interval=interval,
                outputsize=outputsize
            )

            if not result.success:
                return {"error": result.error, "success": False}

            return {"success": True, "data": result.data}

        @agent.tool
        async def get_technical_indicator(
            ctx: RunContext[Dependencies],
            symbol: str,
            indicator: str,
            interval: str = "1day",
            time_period: int = 14,
            outputsize: int = 30
        ) -> Dict[str, Any]:
            """
            Calculate a technical indicator for a symbol.

            Args:
                ctx: Runtime context
                symbol: Trading symbol
                indicator: Indicator type (e.g., RSI, SMA, EMA, MACD)
                interval: Time interval
                time_period: Period for calculation (default 14)
                outputsize: Number of data points

            Returns:
                Dictionary with indicator calculation results
            """
            logger.info(f"Tool called: get_technical_indicator({symbol}, {indicator}, {time_period})")
            result = await mcp_client.technical_indicator(
                symbol=symbol,
                indicator=indicator,
                interval=interval,
                time_period=time_period,
                outputsize=outputsize
            )

            if not result.success:
                return {"error": result.error, "success": False}

            return {"success": True, "data": result.data}

        @agent.tool
        async def convert_currency(
            ctx: RunContext[Dependencies],
            from_currency: str,
            to_currency: str,
            amount: float
        ) -> Dict[str, Any]:
            """
            Convert an amount from one currency to another.

            Args:
                ctx: Runtime context
                from_currency: Source currency code (e.g., USD)
                to_currency: Target currency code (e.g., EUR)
                amount: Amount to convert

            Returns:
                Dictionary with conversion result and exchange rate
            """
            logger.info(f"Tool called: convert_currency({amount} {from_currency} to {to_currency})")
            result = await mcp_client.convert_currency(
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount
            )

            if not result.success:
                return {"error": result.error, "success": False}

            return {"success": True, "data": result.data}

        @agent.tool
        async def web_search(ctx: RunContext[Dependencies], query: str) -> Dict[str, Any]:
            """
            Search the web for real-time information beyond financial data.
            Use this for general questions, news, or when market data tools don't have the answer.

            Args:
                ctx: Runtime context
                query: Search query string

            Returns:
                Dictionary with search results
            """
            logger.info(f"Tool called: web_search({query})")

            # Using DuckDuckGo HTML search as a simple web search implementation
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": query},
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }
                    )

                    if response.status_code == 200:
                        # Simple extraction of first few results
                        # In production, you'd want to parse this properly or use a search API
                        text = response.text[:2000]  # Limit response size
                        return {
                            "success": True,
                            "data": {
                                "query": query,
                                "snippet": text,
                                "message": "Web search completed. Results may be limited."
                            }
                        }
                    else:
                        return {
                            "error": f"Search failed with status {response.status_code}",
                            "success": False
                        }

            except Exception as e:
                logger.error(f"Web search failed: {e}")
                return {
                    "error": f"Web search error: {str(e)}",
                    "success": False
                }

    async def run_agent(
        self,
        user_query: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Run the AI agent with the user query.

        Args:
            user_query: User's question or request
            session_context: Optional session context for personalization

        Returns:
            AgentResponse with the agent's response and metadata
        """
        try:
            # Create agent (gets fresh system prompt from DB)
            agent = await self._create_agent()

            # Prepare dependencies
            deps = Dependencies(session_context=session_context or {})

            # Run the agent
            result = await agent.run(user_query, deps=deps)

            # Extract tools used from messages
            tools_used = []
            for message in result.all_messages():
                if hasattr(message, 'tool_name') and message.tool_name:
                    tools_used.append(message.tool_name)

            # Get the model name
            messages = result.all_messages()
            model_name = None
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'model_name'):
                    model_name = last_msg.model_name

            self._available = True
            self._last_error = None

            return AgentResponse(
                content=result.output,
                model_used=model_name,
                success=True,
                used_fallback=model_name == settings.AI_FALLBACK_MODEL if model_name else False,
                tools_used=list(set(tools_used))  # Unique tools
            )

        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            self._last_error = str(e)
            return AgentResponse(
                content="",
                success=False,
                error=str(e)
            )

    async def health_check(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Check if OpenRouter API is reachable.

        Args:
            timeout: Request timeout in seconds

        Returns:
            Tuple of (is_healthy, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.OPENROUTER_API_BASE}/models",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
                )

                if response.status_code == 200:
                    self._available = True
                    self._last_error = None
                    return True, None
                elif response.status_code == 401:
                    error = "Invalid API key"
                    self._available = False
                    self._last_error = error
                    return False, error
                elif response.status_code == 429:
                    error = "Rate limited"
                    self._last_error = error
                    return False, error
                else:
                    error = f"Unexpected status code: {response.status_code}"
                    self._last_error = error
                    return False, error

        except httpx.ConnectError:
            error = "Cannot connect to OpenRouter API"
            self._available = False
            self._last_error = error
            return False, error
        except httpx.TimeoutException:
            error = "OpenRouter API request timed out"
            self._last_error = error
            return False, error
        except Exception as e:
            error = f"Health check failed: {str(e)}"
            self._last_error = error
            return False, error

    @property
    def is_available(self) -> bool:
        """Check if the AI service is available."""
        return self._initialized and self._available

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def get_model_info(self) -> dict:
        """Get information about the configured models."""
        return {
            "primary_model": settings.AI_PRIMARY_MODEL,
            "fallback_model": settings.AI_FALLBACK_MODEL,
            "app_title": settings.AI_APP_TITLE,
            "initialized": self._initialized,
            "available": self._available,
            "last_error": self._last_error,
        }


# Global AI agent service instance
ai_agent_service = AIAgentService()
