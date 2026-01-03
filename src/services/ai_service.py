"""
AI Service for ChatTwelve using OpenRouter with Pydantic AI.

Provides model switching with fallback support and robust error handling.
"""

from typing import Optional, Tuple
from dataclasses import dataclass
import logging
import asyncio
import httpx

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.core.config import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class AIServiceUnavailable(AIServiceError):
    """Raised when OpenRouter is unavailable."""
    pass


class AIServiceConfigError(AIServiceError):
    """Raised when AI service is misconfigured."""
    pass


class AIServiceRateLimited(AIServiceError):
    """Raised when rate limited by OpenRouter."""
    pass


@dataclass
class AIResponse:
    """Response from AI generation with metadata."""
    content: str
    model_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    used_fallback: bool = False


class AIService:
    """Service for AI model interactions using OpenRouter."""

    # OpenRouter API base URL for health checks
    OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

    def __init__(self):
        self._provider: Optional[OpenRouterProvider] = None
        self._primary_model: Optional[OpenRouterModel] = None
        self._fallback_model: Optional[OpenRouterModel] = None
        self._model: Optional[FallbackModel] = None
        self._initialized = False
        self._available = True
        self._last_error: Optional[str] = None

    def _ensure_initialized(self) -> None:
        """Initialize the AI models lazily."""
        if self._initialized:
            return

        if not settings.OPENROUTER_API_KEY:
            raise AIServiceConfigError("OPENROUTER_API_KEY is not set in environment variables")

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
            logger.error(f"Failed to initialize AI service: {e}")
            raise AIServiceConfigError(f"Failed to initialize AI service: {e}")

    @property
    def is_available(self) -> bool:
        """Check if the AI service is available."""
        return self._initialized and self._available

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    @property
    def provider(self) -> OpenRouterProvider:
        """Get the OpenRouter provider."""
        self._ensure_initialized()
        return self._provider

    @property
    def model(self) -> FallbackModel:
        """Get the fallback model (primary with fallback)."""
        self._ensure_initialized()
        return self._model

    @property
    def primary_model(self) -> OpenRouterModel:
        """Get the primary model only."""
        self._ensure_initialized()
        return self._primary_model

    @property
    def fallback_model(self) -> OpenRouterModel:
        """Get the fallback model only."""
        self._ensure_initialized()
        return self._fallback_model

    async def health_check(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Check if OpenRouter API is reachable.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            Tuple of (is_healthy, error_message).
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

    def get_agent(
        self,
        system_prompt: str = "",
        use_fallback: bool = True,
        model_override: Optional[str] = None,
    ) -> Agent:
        """
        Create an agent with the configured model.

        Args:
            system_prompt: System prompt for the agent.
            use_fallback: Whether to use fallback model chain (default: True).
            model_override: Optional model ID to use instead of configured models.

        Returns:
            Configured Pydantic AI Agent.

        Raises:
            AIServiceConfigError: If service is not properly configured.
        """
        self._ensure_initialized()

        if model_override:
            # Use a specific model override
            model = OpenRouterModel(model_override, provider=self._provider)
            logger.debug(f"Using model override: {model_override}")
        elif use_fallback:
            # Use the fallback model chain
            model = self._model
            logger.debug(f"Using fallback chain: {settings.AI_PRIMARY_MODEL} -> {settings.AI_FALLBACK_MODEL}")
        else:
            # Use primary model only
            model = self._primary_model
            logger.debug(f"Using primary model only: {settings.AI_PRIMARY_MODEL}")

        return Agent(model, system_prompt=system_prompt) if system_prompt else Agent(model)

    def _handle_error(self, error: Exception) -> AIResponse:
        """
        Handle errors and return appropriate AIResponse.

        Args:
            error: The exception that occurred.

        Returns:
            AIResponse with error details.
        """
        error_str = str(error)
        self._last_error = error_str

        # Check for specific error types
        if "401" in error_str or "unauthorized" in error_str.lower():
            self._available = False
            return AIResponse(
                content="",
                success=False,
                error="Invalid OpenRouter API key. Please check your configuration."
            )
        elif "429" in error_str or "rate limit" in error_str.lower():
            return AIResponse(
                content="",
                success=False,
                error="Rate limited by OpenRouter. Please try again later."
            )
        elif "timeout" in error_str.lower() or "connect" in error_str.lower():
            self._available = False
            return AIResponse(
                content="",
                success=False,
                error="Cannot connect to OpenRouter. The service may be temporarily unavailable."
            )
        elif "503" in error_str or "502" in error_str or "504" in error_str:
            return AIResponse(
                content="",
                success=False,
                error="OpenRouter is temporarily unavailable. Please try again later."
            )
        else:
            return AIResponse(
                content="",
                success=False,
                error=f"AI generation failed: {error_str}"
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        use_fallback: bool = True,
        model_override: Optional[str] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> AIResponse:
        """
        Generate a response from the AI model with error handling.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            use_fallback: Whether to use fallback model chain.
            model_override: Optional model ID to use instead of configured models.
            max_retries: Maximum number of retry attempts.
            retry_delay: Initial delay between retries (exponential backoff).

        Returns:
            AIResponse with content and metadata.
        """
        try:
            agent = self.get_agent(
                system_prompt=system_prompt,
                use_fallback=use_fallback,
                model_override=model_override,
            )
        except AIServiceConfigError as e:
            return AIResponse(content="", success=False, error=str(e))

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = await agent.run(prompt)

                # Get the model name from the response
                messages = result.all_messages()
                model_name = None
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, 'model_name'):
                        model_name = last_msg.model_name

                self._available = True
                self._last_error = None

                return AIResponse(
                    content=result.output,
                    model_used=model_name,
                    success=True,
                    used_fallback=model_name == settings.AI_FALLBACK_MODEL if model_name else False
                )

            except Exception as e:
                last_error = e
                logger.warning(f"AI generation attempt {attempt + 1} failed: {e}")

                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)

        # All retries failed
        logger.error(f"AI generation failed after {max_retries + 1} attempts: {last_error}")
        return self._handle_error(last_error)

    def generate_sync(
        self,
        prompt: str,
        system_prompt: str = "",
        use_fallback: bool = True,
        model_override: Optional[str] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> AIResponse:
        """
        Generate a response from the AI model synchronously with error handling.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            use_fallback: Whether to use fallback model chain.
            model_override: Optional model ID to use instead of configured models.
            max_retries: Maximum number of retry attempts.
            retry_delay: Initial delay between retries (exponential backoff).

        Returns:
            AIResponse with content and metadata.
        """
        import time

        try:
            agent = self.get_agent(
                system_prompt=system_prompt,
                use_fallback=use_fallback,
                model_override=model_override,
            )
        except AIServiceConfigError as e:
            return AIResponse(content="", success=False, error=str(e))

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = agent.run_sync(prompt)

                # Get the model name from the response
                messages = result.all_messages()
                model_name = None
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, 'model_name'):
                        model_name = last_msg.model_name

                self._available = True
                self._last_error = None

                return AIResponse(
                    content=result.output,
                    model_used=model_name,
                    success=True,
                    used_fallback=model_name == settings.AI_FALLBACK_MODEL if model_name else False
                )

            except Exception as e:
                last_error = e
                logger.warning(f"AI generation attempt {attempt + 1} failed: {e}")

                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)

        # All retries failed
        logger.error(f"AI generation failed after {max_retries + 1} attempts: {last_error}")
        return self._handle_error(last_error)

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


# Global AI service instance
ai_service = AIService()
