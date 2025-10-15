"""Model Context Protocol (MCP) data models.

Based on MCP specification: https://modelcontextprotocol.io/
JSON-RPC 2.0 protocol for tool discovery and execution.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ==========================================
# Base MCP Protocol Models (JSON-RPC 2.0)
# ==========================================

class MCPRequest(BaseModel):
    """Base MCP request following JSON-RPC 2.0 spec."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    """MCP error response."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """Base MCP response following JSON-RPC 2.0 spec."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None


# ==========================================
# Tools List Protocol (Discovery)
# ==========================================

class Tool(BaseModel):
    """Tool definition for MCP tools/list response."""
    name: str = Field(description="Unique identifier for the tool")
    description: str = Field(description="Human-readable description of what the tool does")
    inputSchema: Dict[str, Any] = Field(
        description="JSON Schema defining the tool's input parameters"
    )


class ToolsListRequest(BaseModel):
    """Request to list available tools (tools/list method)."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: Literal["tools/list"] = "tools/list"
    params: Optional[Dict[str, Any]] = None


class ToolsListResponse(BaseModel):
    """Response containing list of available tools."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Dict[str, List[Tool]] = Field(
        description="Dictionary with 'tools' key containing array of Tool objects"
    )


# ==========================================
# Tools Call Protocol (Execution)
# ==========================================

class ToolContent(BaseModel):
    """Content item in tool call response."""
    type: Literal["text"] = "text"
    text: str = Field(description="The actual content/result from the tool")


class ToolsCallRequest(BaseModel):
    """Request to execute a specific tool (tools/call method)."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: Literal["tools/call"] = "tools/call"
    params: Dict[str, Any] = Field(
        description="Must contain 'name' (tool name) and 'arguments' (tool parameters)"
    )


class ToolsCallResponse(BaseModel):
    """Response from tool execution."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Dict[str, List[ToolContent]] = Field(
        description="Dictionary with 'content' key containing array of ToolContent"
    )


# ==========================================
# Error Codes (JSON-RPC 2.0 Standard)
# ==========================================

class MCPErrorCode:
    """Standard MCP/JSON-RPC error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom application errors (MCP spec allows -32000 to -32099)
    TOOL_NOT_FOUND = -32000
    TOOL_EXECUTION_ERROR = -32001
    AGENT_INITIALIZATION_ERROR = -32002
    TIMEOUT_ERROR = -32003
