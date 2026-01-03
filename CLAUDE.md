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

## Architecture

### Request Flow
```
Client → FastAPI Router → ChatService
                            ├→ SessionRepository (session validation)
                            ├→ QueryProcessor (NLP parsing)
                            ├→ CacheRepository (cache lookup/store)
                            └→ MCPClient (TwelveData MCP calls)
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

### Database (SQLite via aiosqlite)

**sessions table** - UUID-based sessions with:
- Conversation context (last 10 entries as JSON array)
- Rate limit tracking (request_count, request_window_start)
- 60-minute expiry with automatic cleanup

**cache table** - SHA256-keyed cache with:
- Type-specific TTLs (price: 45s, historical/indicator: 300s)
- Stale cache fallback when MCP unavailable

## Key Configuration (src/core/config.py)

- MCP_SERVER_URL: Set via environment variable (e.g., `http://localhost:3847`)
- RATE_LIMIT_REQUESTS: 30 per 60 seconds per session
- SESSION_TIMEOUT_MINUTES: 60
- MAX_QUERY_LENGTH: 5000 characters
- AI_MODEL: openai:gpt-4o-mini (requires OPENAI_API_KEY env var)

## Supported Query Types

| Type | Example | Output |
|------|---------|--------|
| Price | "What is the price of AAPL?" | Current price + % change |
| Quote | "Get detailed quote for gold" | OHLC, volume, 52-week range |
| Historical | "Show me last 30 days of AAPL" | Candlestick data |
| Indicator | "Calculate RSI for BTC" | Technical indicator values |
| Conversion | "Convert 100 USD to EUR" | Exchange rate + result |
| Commodities | "List available commodities" | Supported commodities |

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
