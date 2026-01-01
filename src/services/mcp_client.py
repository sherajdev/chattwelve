"""
MCP Client for TwelveData server communication.
"""

import json
import time
import httpx
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from src.core.config import settings
from src.core.logging import logger, log_mcp_call, log_error


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time_ms: float = 0


class MCPClient:
    """Client for communicating with TwelveData MCP server."""

    def __init__(self, server_url: str = None):
        self.server_url = server_url or settings.MCP_SERVER_URL
        self.timeout = settings.MCP_TIMEOUT_SECONDS

    async def _call_mcp(self, method: str, params: Dict[str, Any] = None) -> MCPToolResult:
        """
        Make a JSON-RPC call to the MCP server.

        Args:
            method: The MCP method/tool to call
            params: Parameters for the method

        Returns:
            MCPToolResult with success status and data or error
        """
        start_time = time.time()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/mcp",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                )

                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    log_mcp_call(method, params or {}, response_time_ms, success=False)
                    return MCPToolResult(
                        success=False,
                        error=f"MCP server returned status {response.status_code}",
                        response_time_ms=response_time_ms
                    )

                result = response.json()

                if "error" in result:
                    log_mcp_call(method, params or {}, response_time_ms, success=False)
                    error_msg = result["error"].get("message", "Unknown MCP error")
                    return MCPToolResult(
                        success=False,
                        error=error_msg,
                        response_time_ms=response_time_ms
                    )

                # Extract data from MCP response format
                mcp_result = result.get("result", {})

                # Check for error in result
                if mcp_result.get("isError"):
                    content = mcp_result.get("content", [])
                    error_text = content[0].get("text", "Unknown error") if content else "Unknown error"
                    log_mcp_call(method, params or {}, response_time_ms, success=False)
                    return MCPToolResult(
                        success=False,
                        error=error_text,
                        response_time_ms=response_time_ms
                    )

                # Extract actual data - prefer structuredContent if available
                data = mcp_result.get("structuredContent")
                if data is None:
                    content = mcp_result.get("content", [])
                    if content and len(content) > 0:
                        text = content[0].get("text", "")
                        # Try to parse as JSON if response_format was json
                        try:
                            data = json.loads(text)
                        except (json.JSONDecodeError, TypeError):
                            data = {"text": text}

                log_mcp_call(method, params or {}, response_time_ms, success=True)
                return MCPToolResult(
                    success=True,
                    data=data,
                    response_time_ms=response_time_ms
                )

        except httpx.ConnectError as e:
            response_time_ms = (time.time() - start_time) * 1000
            log_mcp_call(method, params or {}, response_time_ms, success=False)
            log_error(e, context="MCP connection")
            return MCPToolResult(
                success=False,
                error="Failed to connect to MCP server",
                response_time_ms=response_time_ms
            )
        except httpx.TimeoutException as e:
            response_time_ms = (time.time() - start_time) * 1000
            log_mcp_call(method, params or {}, response_time_ms, success=False)
            log_error(e, context="MCP timeout")
            return MCPToolResult(
                success=False,
                error="MCP request timed out",
                response_time_ms=response_time_ms
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            log_mcp_call(method, params or {}, response_time_ms, success=False)
            log_error(e, context="MCP call")
            return MCPToolResult(
                success=False,
                error=f"MCP error: {str(e)}",
                response_time_ms=response_time_ms
            )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> MCPToolResult:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call (get_price, get_quote, etc.)
            arguments: Tool arguments

        Returns:
            MCPToolResult with success status and data or error
        """
        return await self._call_mcp(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments or {}
            }
        )

    async def get_price(self, symbol: str) -> MCPToolResult:
        """Get real-time price for a symbol."""
        return await self.call_tool("twelvedata_get_price", {
            "symbol": symbol,
            "response_format": "json"
        })

    async def get_quote(self, symbol: str) -> MCPToolResult:
        """Get detailed quote for a symbol."""
        return await self.call_tool("twelvedata_get_quote", {
            "symbol": symbol,
            "response_format": "json"
        })

    async def get_time_series(
        self,
        symbol: str,
        interval: str = "1day",
        outputsize: int = 30,
        start_date: str = None,
        end_date: str = None
    ) -> MCPToolResult:
        """Get historical OHLC candles."""
        args = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "response_format": "json"
        }
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date

        return await self.call_tool("twelvedata_get_time_series", args)

    async def get_exchange_rate(self, symbol: str) -> MCPToolResult:
        """Get current exchange rate for currency pair."""
        return await self.call_tool("twelvedata_get_exchange_rate", {
            "symbol": symbol,
            "response_format": "json"
        })

    async def convert_currency(
        self,
        from_currency: str,
        to_currency: str,
        amount: float
    ) -> MCPToolResult:
        """Convert amount between currencies."""
        return await self.call_tool("twelvedata_convert_currency", {
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
            "response_format": "json"
        })

    async def list_commodities(self) -> MCPToolResult:
        """List all available commodities."""
        return await self.call_tool("twelvedata_list_commodities", {
            "response_format": "json"
        })

    async def technical_indicator(
        self,
        symbol: str,
        indicator: str,
        interval: str = "1day",
        time_period: int = 14,
        outputsize: int = 30
    ) -> MCPToolResult:
        """Calculate technical indicator."""
        return await self.call_tool("twelvedata_technical_indicator", {
            "symbol": symbol,
            "indicator": indicator,
            "interval": interval,
            "time_period": time_period,
            "outputsize": outputsize,
            "response_format": "json"
        })

    async def list_tools(self) -> MCPToolResult:
        """List available MCP tools."""
        return await self._call_mcp("tools/list")

    async def health_check(self) -> bool:
        """Check if MCP server is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.server_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# Global MCP client instance
mcp_client = MCPClient()
