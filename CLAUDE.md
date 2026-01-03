# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatTwelve is a conversational AI backend that accepts natural language questions about market data and communicates with a TwelveData MCP server to fetch real-time financial information. Built with FastAPI, it returns both human-readable responses and structured JSON data while maintaining conversation context across sessions.

## Commands

### Quick Start
```bash
./init.sh  # Sets up venv, installs deps, initializes DB, starts server
```

### Manual Development
```bash
source venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
pytest tests/ -v                    # Run pytest suite
python check_session.py             # Test session functionality
python check_cache.py               # Test caching
python check_rate_limit.py          # Test rate limiting
bash test_rate_limit.sh             # Rate limit shell test
bash test_long_query.sh             # Long query validation test
bash test_injection.sh              # Input sanitization test
```

### API Endpoints
- Swagger UI: http://localhost:8000/docs
- Health: GET http://localhost:8000/api/health
- MCP Health: GET http://localhost:8000/api/mcp-health
- AI Health: GET http://localhost:8000/api/ai-health

## Architecture

### Request Flow

**AI Agent Mode (default, USE_AI_AGENT=true):**
```
Client → FastAPI Router → ChatService
                            ├→ SessionRepository (session validation)
                            ├→ CacheRepository (cache lookup/store)
                            └→ AIAgentService (autonomous tool calling)
                                  ├→ MCPClient tools (price, quote, historical, etc.)
                                  └→ Tavily web_search tool
```

**Manual Routing Mode (USE_AI_AGENT=false):**
```
Client → FastAPI Router → ChatService
                            ├→ SessionRepository (session validation)
                            ├→ QueryProcessor (NLP parsing)
                            ├→ CacheRepository (cache lookup/store)
                            ├→ MCPClient (TwelveData MCP calls)
                            └→ AIService (OpenRouter AI generation)
```

### Core Services (src/services/)

**ChatService** (`chat_service.py`) - Main orchestrator handling:
- Session validation and rate limiting
- Query intent routing to appropriate handlers
- Response formatting by type (price, quote, historical, indicator, conversion)
- Cache coordination

**QueryProcessor** (`query_processor.py`) - NLP engine that:
- Detects intent: price, quote, historical, indicator, conversion, commodities_list
- Extracts symbols from natural names (e.g., "gold" → XAU/USD, "apple" → AAPL)
- Parses time periods, intervals, and indicator parameters
- Handles follow-up queries using conversation context

**MCPClient** (`mcp_client.py`) - JSON-RPC 2.0 client for TwelveData MCP server with:
- 7 tools: get_price, get_quote, get_time_series, get_exchange_rate, convert_currency, list_commodities, technical_indicator
- Error handling with fallback support

**AIService** (`ai_service.py`) - OpenRouter AI integration with:
- Primary model: `openai/gpt-5.2`
- Fallback model: `google/gemini-3-flash-preview`
- Automatic fallback when primary model fails
- Retry with exponential backoff (1s, 2s, 4s)
- Health check via `health_check()` method
- Returns `AIResponse` dataclass with success status, content, model used, and errors

**AIAgentService** (`ai_agent_service.py`) - Pydantic AI agent with autonomous tool calling:
- Uses FallbackModel chain (primary → fallback)
- Registered tools: `get_price`, `get_quote`, `get_historical_data`, `get_technical_indicator`, `convert_currency`, `web_search`
- System prompt loaded from database on each request
- Returns `AgentResponse` with content, model_used, tools_used, and success status
- Web search via Tavily API (requires `TAVILY_API_KEY`)

**PromptRepository** (`prompt_repo.py`) - System prompts management:
- CRUD operations for system prompts
- Active prompt selection
- Default trading-focused prompt pre-loaded

### Database (SQLite via aiosqlite)

**sessions table** - UUID-based sessions with:
- Conversation context (last 10 entries as JSON array)
- Rate limit tracking (request_count, request_window_start)
- 60-minute expiry with automatic cleanup

**cache table** - SHA256-keyed cache with:
- Type-specific TTLs (price: 45s, historical/indicator: 300s)
- Stale cache fallback when MCP unavailable

**system_prompts table** - Editable AI system prompts:
- UUID-based with name, prompt text, description
- `is_active` flag for active prompt selection
- Default trading-focused prompt pre-seeded on init

## Key Configuration (src/core/config.py)

- MCP_SERVER_URL: Set via environment variable (e.g., `http://localhost:3847`)
- RATE_LIMIT_REQUESTS: 30 per 60 seconds per session
- SESSION_TIMEOUT_MINUTES: 60
- MAX_QUERY_LENGTH: 5000 characters
- OPENROUTER_API_KEY: Required for AI service (get from openrouter.ai/keys)
- AI_PRIMARY_MODEL: `openai/gpt-5.2` (default primary model)
- AI_FALLBACK_MODEL: `google/gemini-3-flash-preview` (default fallback model)
- USE_AI_AGENT: `true` (default) for autonomous tool calling, `false` for manual routing
- TAVILY_API_KEY: Required for web search tool (get from tavily.com, free tier: 1,000 searches/month)

## Supported Query Types

| Type | Example | Output |
|------|---------|--------|
| Price | "What is the price of AAPL?" | Current price + % change |
| Quote | "Get detailed quote for gold" | OHLC, volume, 52-week range |
| Historical | "Show me last 30 days of AAPL" | Candlestick data |
| Indicator | "Calculate RSI for BTC" | Technical indicator values |
| Conversion | "Convert 100 USD to EUR" | Exchange rate + result |
| Commodities | "List available commodities" | Supported commodities |
| Web Search | "Latest news about Tesla stock" | AI answer + source URLs |

## Symbol Resolution

The QueryProcessor maps natural language to trading symbols:
- Metals: gold→XAU/USD, silver→XAG/USD
- Crypto: bitcoin→BTC/USD, ethereum→ETH/USD
- Stocks: apple→AAPL, microsoft→MSFT, google→GOOGL
- Forex: Pairs like EUR/USD, GBP/USD are recognized directly

## Error Handling Patterns

- MCP disconnection: Falls back to cached data or returns fallback lists
- Rate limiting: Returns 429 with user-friendly message
- Invalid session: Returns 404 with session creation instructions
- Query validation: Returns 400 with specific validation errors
- OpenRouter unavailable: Automatic retry with exponential backoff, then graceful error response
- AI rate limited: Returns user-friendly message with retry suggestion
- AI auth failure: Marks service unavailable, returns config error message
- Tavily unavailable: Returns error message, agent continues with other tools
- Missing TAVILY_API_KEY: web_search tool returns configuration error

## AI Agent Service Usage (Recommended)

```python
from src.services.ai_agent_service import ai_agent_service, AgentResponse

# Run the AI agent with autonomous tool calling
response: AgentResponse = await ai_agent_service.run_agent(
    user_query="What is the current gold price and any recent news?",
    session_context={"user_id": "123"}  # Optional context
)

if response.success:
    print(response.content)       # AI-generated response
    print(response.model_used)    # e.g., "openai/gpt-5.2"
    print(response.tools_used)    # e.g., ["get_price", "web_search"]
    print(response.used_fallback) # True if fallback model was used
else:
    print(response.error)         # Error message

# Health check
is_healthy, error = await ai_agent_service.health_check()

# Model info
info = ai_agent_service.get_model_info()
# {'primary_model': 'openai/gpt-5.2', 'fallback_model': 'google/gemini-3-flash-preview', ...}
```

## System Prompts API

```python
# List all prompts
GET /api/prompts

# Get active prompt
GET /api/prompts/active

# Create new prompt
POST /api/prompts
{
    "name": "My Custom Prompt",
    "prompt": "You are a helpful trading assistant...",
    "description": "Custom trading prompt",
    "is_active": false
}

# Update prompt
PUT /api/prompts/{id}

# Delete prompt (cannot delete active)
DELETE /api/prompts/{id}

# Activate a prompt
POST /api/prompts/{id}/activate
```

## Legacy AI Service Usage (Manual Routing Mode)

```python
from src.services import ai_service, AIResponse

# Async generation with error handling
response: AIResponse = await ai_service.generate(
    prompt="Your prompt",
    system_prompt="Optional system prompt",
    use_fallback=True,      # Use fallback chain (default)
    max_retries=2,          # Retry attempts (default)
)

if response.success:
    print(response.content)      # Generated text
    print(response.model_used)   # e.g., "openai/gpt-5.2"
    print(response.used_fallback) # True if fallback was used
else:
    print(response.error)        # Error message

# Health check
is_healthy, error = await ai_service.health_check()
```
