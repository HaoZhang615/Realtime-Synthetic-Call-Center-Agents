"""
MCP Client for AI Foundry Agent Integration

HTTP client for communicating with the AI Foundry MCP Server.
Implements JSON-RPC 2.0 protocol for tool discovery and execution.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP client errors"""
    pass


class MCPConnectionError(MCPClientError):
    """Connection to MCP server failed"""
    pass


class MCPToolNotFoundError(MCPClientError):
    """Requested tool not found on MCP server"""
    pass


class MCPExecutionError(MCPClientError):
    """Tool execution failed on MCP server"""
    pass


class MCPClient:
    """
    MCP Client for AI Foundry Agent
    
    Communicates with the AI Foundry MCP Server to execute web searches
    via Bing-powered AI agents with ephemeral threading.
    
    Features:
    - Tool discovery via tools/list
    - Tool execution via tools/call
    - Retry logic with exponential backoff
    - Error handling and logging
    - Connection pooling for performance
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize MCP client.
        
        Args:
            base_url: MCP server URL (default: from AZURE_AI_FOUNDRY_MCP_URL env var)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = (base_url or os.getenv("AZURE_AI_FOUNDRY_MCP_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._request_id = 0
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._initialized = False
        
        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        
        logger.info(f"MCP Client initialized: base_url={self.base_url}, timeout={timeout}s")
    
    async def initialize(self) -> None:
        """
        Initialize MCP client and verify connectivity.
        
        Raises:
            MCPConnectionError: If health check or tool discovery fails
        """
        if self._initialized:
            return
        
        try:
            # Health check
            await self._health_check()
            
            # Discover tools
            await self.discover_tools()
            
            self._initialized = True
            logger.info("✅ MCP Client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            raise MCPConnectionError(f"MCP client initialization failed: {e}") from e
    
    async def _health_check(self) -> None:
        """
        Verify MCP server is healthy.
        
        Raises:
            MCPConnectionError: If health check fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            health = response.json()
            logger.info(f"MCP server health: {health.get('status')} (agent: {health.get('agent_id', 'N/A')})")
        except httpx.HTTPError as e:
            raise MCPConnectionError(f"Health check failed: {e}") from e
    
    def _next_request_id(self) -> int:
        """Generate next JSON-RPC request ID"""
        self._request_id += 1
        return self._request_id
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _json_rpc_call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute JSON-RPC 2.0 call to MCP server.
        
        Args:
            method: RPC method name (e.g., "tools/list", "tools/call")
            params: Optional method parameters
            
        Returns:
            RPC result object
            
        Raises:
            MCPConnectionError: If network/connection error occurs
            MCPClientError: If RPC returns error response
        """
        request_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            payload["params"] = params
        
        logger.debug(f"MCP RPC call: method={method}, id={request_id}")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug: Log the actual response
            logger.debug(f"MCP response: {data}")
            
            # Check for JSON-RPC error (must have non-null error field)
            if "error" in data and data["error"] is not None:
                error = data["error"]
                error_msg = error.get("message", "Unknown error")
                error_code = error.get("code", -32000)
                logger.error(f"MCP RPC error: {error_msg} (code: {error_code})")
                raise MCPClientError(f"MCP error: {error_msg}")
            
            return data.get("result", {})
            
            return data.get("result", {})
            
        except httpx.HTTPStatusError as e:
            logger.error(f"MCP HTTP error: {e.response.status_code} - {e.response.text}")
            raise MCPConnectionError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.TimeoutException as e:
            logger.warning(f"MCP request timeout (will retry): method={method}")
            raise
        except httpx.NetworkError as e:
            logger.warning(f"MCP network error (will retry): {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected MCP error: {e}", exc_info=True)
            raise MCPClientError(f"Unexpected error: {e}") from e
    
    async def discover_tools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover available tools from MCP server.
        
        Args:
            force_refresh: Force refresh of cached tools
            
        Returns:
            List of tool definitions
            
        Raises:
            MCPConnectionError: If discovery fails
        """
        if self._tools_cache and not force_refresh:
            return self._tools_cache
        
        logger.info("Discovering MCP tools...")
        result = await self._json_rpc_call("tools/list")
        tools = result.get("tools", [])
        
        self._tools_cache = tools
        logger.info(f"Discovered {len(tools)} tools: {[t['name'] for t in tools]}")
        
        return tools
    
    async def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool schema definition
            
        Raises:
            MCPToolNotFoundError: If tool not found
        """
        tools = await self.discover_tools()
        
        for tool in tools:
            if tool["name"] == tool_name:
                return tool
        
        raise MCPToolNotFoundError(f"Tool not found: {tool_name}")
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> str:
        """
        Execute a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result as text
            
        Raises:
            MCPToolNotFoundError: If tool not found
            MCPExecutionError: If execution fails
        """
        logger.info(f"Executing MCP tool: {tool_name} with args: {arguments}")
        
        try:
            result = await self._json_rpc_call(
                "tools/call",
                params={
                    "name": tool_name,
                    "arguments": arguments,
                },
            )
            
            # Extract text from MCP content response
            content = result.get("content", [])
            if not content:
                logger.warning(f"Tool {tool_name} returned empty content")
                return "No results returned"
            
            # Get first text content item
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    logger.info(f"✅ Tool {tool_name} completed: {len(text)} chars")
                    return text
            
            logger.warning(f"Tool {tool_name} returned non-text content")
            return "No text content in response"
            
        except MCPClientError as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            raise MCPExecutionError(f"Tool {tool_name} execution failed: {e}") from e
    
    async def search_web(self, query: str) -> str:
        """
        Execute web search using AI Foundry Agent.
        
        Convenience method for the search_web_ai_foundry tool.
        
        Args:
            query: Search query
            
        Returns:
            Search results as text
            
        Raises:
            MCPExecutionError: If search fails
        """
        return await self.execute_tool("search_web_ai_foundry", {"query": query})
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources"""
        await self.client.aclose()
        logger.info("MCP Client closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
