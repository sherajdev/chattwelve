"""
Query processor for parsing natural language market data queries.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from src.core.logging import logger


class QueryIntent(Enum):
    """Possible query intents."""
    PRICE = "price"
    QUOTE = "quote"
    HISTORICAL = "historical"
    INDICATOR = "indicator"
    CONVERSION = "conversion"
    COMPARISON = "comparison"
    COMMODITIES_LIST = "commodities_list"
    UNKNOWN = "unknown"


@dataclass
class ParsedQuery:
    """Parsed query result."""
    intent: QueryIntent
    symbols: List[str]
    interval: Optional[str] = None
    indicator: Optional[str] = None
    time_period: Optional[int] = None
    outputsize: Optional[int] = None
    from_currency: Optional[str] = None
    to_currency: Optional[str] = None
    amount: Optional[float] = None
    raw_query: str = ""


class QueryProcessor:
    """Process natural language queries about market data."""

    # Common symbol patterns
    FOREX_PAIRS = [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD",
        "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY"
    ]

    METALS = {
        "gold": "XAU/USD",
        "silver": "XAG/USD",
        "platinum": "XPT/USD",
        "palladium": "XPD/USD"
    }

    CRYPTO = {
        "bitcoin": "BTC/USD",
        "btc": "BTC/USD",
        "ethereum": "ETH/USD",
        "eth": "ETH/USD",
        "litecoin": "LTC/USD",
        "ltc": "LTC/USD"
    }

    # Stock tickers
    COMMON_STOCKS = [
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
        "JPM", "V", "MA", "UNH", "JNJ", "WMT", "PG", "XOM", "CVX", "BAC"
    ]

    # Company names to stock ticker mapping
    STOCK_NAMES = {
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "meta": "META",
        "facebook": "META",
        "nvidia": "NVDA",
        "tesla": "TSLA",
        "jpmorgan": "JPM",
        "jp morgan": "JPM",
        "walmart": "WMT",
        "johnson": "JNJ",
        "exxon": "XOM",
        "chevron": "CVX"
    }

    # Technical indicators
    INDICATORS = {
        "sma": "sma",
        "simple moving average": "sma",
        "moving average": "sma",  # Default to SMA for generic "moving average"
        "ema": "ema",
        "exponential moving average": "ema",
        "rsi": "rsi",
        "relative strength index": "rsi",
        "macd": "macd",
        "moving average convergence divergence": "macd",
        "bollinger bands": "bbands",
        "bbands": "bbands",
        "stochastic": "stoch",
        "stoch": "stoch",
        "adx": "adx",
        "average directional index": "adx",
        "atr": "atr",
        "average true range": "atr",
        "cci": "cci",
        "commodity channel index": "cci",
        "obv": "obv",
        "on balance volume": "obv",
        "momentum": "mom",
        "mom": "mom",
        "roc": "roc",
        "rate of change": "roc",
        "williams %r": "willr",
        "willr": "willr"
    }

    # Intervals
    INTERVALS = {
        "1 minute": "1min",
        "1min": "1min",
        "5 minute": "5min",
        "5min": "5min",
        "15 minute": "15min",
        "15min": "15min",
        "30 minute": "30min",
        "30min": "30min",
        "1 hour": "1h",
        "1h": "1h",
        "hourly": "1h",
        "4 hour": "4h",
        "4h": "4h",
        "daily": "1day",
        "1 day": "1day",
        "1day": "1day",
        "day": "1day",
        "weekly": "1week",
        "1 week": "1week",
        "1week": "1week",
        "week": "1week",
        "monthly": "1month",
        "1 month": "1month",
        "1month": "1month",
        "month": "1month"
    }

    def __init__(self):
        pass

    def parse(self, query: str, context: Optional[List[Dict[str, Any]]] = None) -> ParsedQuery:
        """
        Parse a natural language query.

        Args:
            query: Natural language query string
            context: Optional conversation context from previous queries

        Returns:
            ParsedQuery with extracted intent and parameters
        """
        query_lower = query.lower()

        # Determine intent
        intent = self._detect_intent(query_lower)

        # Extract symbols
        symbols = self._extract_symbols(query)

        # Extract interval if present
        interval = self._extract_interval(query_lower)

        # Extract indicator if present
        indicator = self._extract_indicator(query_lower)

        # Extract time period if present
        time_period = self._extract_time_period(query_lower)

        # Extract conversion details if present
        from_currency, to_currency, amount = self._extract_conversion(query_lower)

        # Extract outputsize
        outputsize = self._extract_outputsize(query_lower)

        # If no symbols found but we have context, check for follow-up references
        if not symbols and context:
            symbols = self._extract_symbols_from_context(query_lower, context)

        return ParsedQuery(
            intent=intent,
            symbols=symbols,
            interval=interval or "1day",
            indicator=indicator,
            time_period=time_period or 14,
            outputsize=outputsize or 30,
            from_currency=from_currency,
            to_currency=to_currency,
            amount=amount,
            raw_query=query
        )

    def _detect_intent(self, query: str) -> QueryIntent:
        """Detect the intent from the query."""
        # Check for commodities list
        if any(phrase in query for phrase in ["list commodities", "available commodities", "show commodities"]):
            return QueryIntent.COMMODITIES_LIST

        # Check for conversion
        if any(phrase in query for phrase in ["convert", "exchange", "to usd", "to eur", "to gbp", "how much is"]):
            return QueryIntent.CONVERSION

        # Check for technical indicator
        if any(ind in query for ind in self.INDICATORS.keys()):
            return QueryIntent.INDICATOR

        # Check for historical data
        historical_phrases = ["historical", "history", "past", "chart", "time series", "candles", "over time",
                            "last week", "last month", "last year", "trend"]
        if any(phrase in query for phrase in historical_phrases):
            return QueryIntent.HISTORICAL

        # Check for patterns like "last N days/weeks/months"
        if re.search(r'last\s+\d+\s+(?:days?|weeks?|months?|hours?)', query):
            return QueryIntent.HISTORICAL

        # Check for detailed quote
        quote_phrases = ["quote", "detailed", "52 week", "volume", "high low", "open close", "ohlc"]
        if any(phrase in query for phrase in quote_phrases):
            return QueryIntent.QUOTE

        # Check for comparison
        comparison_phrases = ["compare", "vs", "versus", "against", "difference between"]
        if any(phrase in query for phrase in comparison_phrases):
            return QueryIntent.COMPARISON

        # Default to price for simple queries
        price_phrases = ["price", "cost", "worth", "value", "trading at", "what is", "how much"]
        if any(phrase in query for phrase in price_phrases):
            return QueryIntent.PRICE

        # If symbols detected but no clear intent, assume price
        return QueryIntent.PRICE

    # Common English words to exclude from symbol detection
    EXCLUDED_WORDS = {
        "THE", "IS", "OF", "TO", "FOR", "AT", "BY", "IN", "ON", "AN", "IT",
        "WHAT", "HOW", "SHOW", "GET", "GIVE", "ME", "AND", "OR", "WITH",
        "PRICE", "COST", "WORTH", "VALUE", "RATE", "DATA", "QUOTE",
        "LAST", "PAST", "TODAY", "NOW", "CURRENT", "DAILY", "WEEKLY",
        "SMA", "EMA", "RSI", "MACD", "ADX", "ATR", "CCI", "OBV", "ROC",  # Indicators
        "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD",  # Single currencies
        "DAY", "WEEK", "MONTH", "YEAR", "HOUR", "MIN",
        "CAN", "YOU", "TELL", "ABOUT", "THIS", "THAT", "FROM",
        "GOLD", "SILVER", "PLATINUM", "BITCOIN", "ETHEREUM",  # Names (symbols already added)
        # Common non-financial words that might appear as uppercase
        "JOKE", "FUNNY", "HELP", "HELLO", "HI", "BYE", "THANKS", "PLEASE",
        "STOCK", "STOCKS", "MARKET", "TRADING", "TRADE", "TRADES",
        "INFO", "TELL", "SHOW", "KNOW", "WANT", "NEED", "LIKE",
    }

    # Phrases that indicate financial intent (needed for fallback symbol extraction)
    FINANCIAL_INTENT_PHRASES = [
        "price", "quote", "cost", "worth", "value", "trading at",
        "buy", "sell", "invest", "stock", "share", "ticker",
        "chart", "history", "historical", "candle", "ohlc",
        "indicator", "sma", "ema", "rsi", "macd"
    ]

    def _extract_symbols(self, query: str) -> List[str]:
        """Extract trading symbols from the query."""
        symbols = []
        query_upper = query.upper()
        query_lower = query.lower()

        # Check for metal names (highest priority)
        for metal_name, symbol in self.METALS.items():
            if metal_name in query_lower:
                if symbol not in symbols:
                    symbols.append(symbol)

        # Check for crypto names
        for crypto_name, symbol in self.CRYPTO.items():
            if crypto_name in query_lower:
                if symbol not in symbols:
                    symbols.append(symbol)

        # Check for company names (e.g., "Apple" -> "AAPL")
        for company_name, symbol in self.STOCK_NAMES.items():
            if company_name in query_lower:
                if symbol not in symbols:
                    symbols.append(symbol)

        # Check for forex pairs (explicit format like "EUR/USD" or "EURUSD")
        for pair in self.FOREX_PAIRS:
            if pair in query_upper or pair.replace("/", "") in query_upper:
                if pair not in symbols:
                    symbols.append(pair)

        # Check for stock tickers (known common stocks first)
        words = re.findall(r'\b[A-Z]{2,5}\b', query_upper)
        for word in words:
            if word in self.COMMON_STOCKS and word not in self.EXCLUDED_WORDS:
                if word not in symbols:
                    symbols.append(word)

        # If no known symbols found, accept any uppercase ticker-like word (2-5 chars)
        # BUT only if the query shows financial intent
        if not symbols:
            has_financial_intent = any(
                phrase in query_lower for phrase in self.FINANCIAL_INTENT_PHRASES
            )
            if has_financial_intent:
                for word in words:
                    if word not in self.EXCLUDED_WORDS and len(word) >= 2:
                        if word not in symbols:
                            symbols.append(word)
                            break  # Only take the first potential ticker

        # Check for explicit forex/pair patterns (e.g., XAU/USD)
        explicit_pairs = re.findall(r'\b([A-Z]{2,6}/[A-Z]{2,6})\b', query_upper)
        for pair in explicit_pairs:
            if pair not in symbols:
                symbols.append(pair)

        return symbols

    def _extract_interval(self, query: str) -> Optional[str]:
        """Extract time interval from query."""
        for phrase, interval in self.INTERVALS.items():
            if phrase in query:
                return interval
        return None

    def _extract_indicator(self, query: str) -> Optional[str]:
        """Extract technical indicator from query."""
        for phrase, indicator in self.INDICATORS.items():
            if phrase in query:
                return indicator
        return None

    def _extract_time_period(self, query: str) -> Optional[int]:
        """Extract time period for indicators."""
        # Look for patterns like "14 period", "20-day", "20 day", etc.
        patterns = [
            r'(\d+)[\s-]*(?:period|day|days)',
            r'period\s*of\s*(\d+)',
            r'(\d+)[\s-]*(?:day|week)\s*(?:sma|ema|rsi|macd)'
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return int(match.group(1))
        return None

    def _extract_outputsize(self, query: str) -> Optional[int]:
        """Extract number of data points to return."""
        patterns = [
            r'last\s*(\d+)\s*(?:days?|weeks?|candles?|points?|bars?)',
            r'(\d+)\s*(?:days?|weeks?|candles?|points?|bars?)\s*of'
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return min(int(match.group(1)), 5000)  # Cap at 5000
        return None

    def _extract_conversion(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[float]]:
        """Extract currency conversion details."""
        # Pattern: "convert 100 USD to EUR" or "100 dollars to euros"
        currency_map = {
            "dollar": "USD", "dollars": "USD", "usd": "USD",
            "euro": "EUR", "euros": "EUR", "eur": "EUR",
            "pound": "GBP", "pounds": "GBP", "gbp": "GBP",
            "yen": "JPY", "jpy": "JPY",
            "franc": "CHF", "francs": "CHF", "chf": "CHF"
        }

        # Try to find amount
        amount_match = re.search(r'(\d+(?:\.\d+)?)', query)
        amount = float(amount_match.group(1)) if amount_match else None

        # Find currencies
        from_currency = None
        to_currency = None

        words = query.split()
        for i, word in enumerate(words):
            word_lower = word.lower().rstrip("s")
            if word_lower in currency_map:
                if from_currency is None:
                    from_currency = currency_map[word_lower]
                else:
                    to_currency = currency_map[word_lower]

        # Check for explicit currency codes
        codes = re.findall(r'\b(USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD)\b', query.upper())
        if len(codes) >= 2:
            from_currency = codes[0]
            to_currency = codes[1]
        elif len(codes) == 1 and from_currency is None:
            from_currency = codes[0]

        return from_currency, to_currency, amount

    def _extract_symbols_from_context(self, query: str, context: List[Dict[str, Any]]) -> List[str]:
        """
        Extract symbols from conversation context for follow-up queries.

        Checks if the query is a follow-up (using pronouns like 'it', 'its', 'that', etc.)
        and retrieves the symbol from the most recent context entry.

        Args:
            query: The lowercase query string
            context: List of previous conversation context entries

        Returns:
            List of symbols from context if this appears to be a follow-up query
        """
        # Follow-up indicators - words that suggest referring to previous subject
        follow_up_patterns = [
            r'\bits?\b',  # "it", "its"
            r'\bthat\b',
            r'\bthe same\b',
            r'\bthis\b',
            r'\bsame stock\b',
            r'\bsame symbol\b',
            r'\band what about\b',
            r'\bhow about\b',
            r'\bwhat about\b',
            r'\balso\b',
            r'\btoo\b',
        ]

        # Check if query contains follow-up indicators
        is_follow_up = any(re.search(pattern, query) for pattern in follow_up_patterns)

        if not is_follow_up:
            return []

        # Look for symbols in recent context (most recent first)
        for entry in reversed(context):
            symbols = entry.get("symbols", [])
            if symbols:
                logger.info(f"Using symbol from context: {symbols}")
                return symbols

        return []


# Global query processor instance
query_processor = QueryProcessor()
