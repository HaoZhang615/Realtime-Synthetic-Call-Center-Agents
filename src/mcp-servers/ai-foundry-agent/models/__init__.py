"""MCP protocol models for AI Foundry Agent MCP Server."""

from .mcp_protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    ToolsListRequest,
    ToolsListResponse,
    ToolsCallRequest,
    ToolsCallResponse,
    Tool,
    ToolContent,
)

__all__ = [
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "ToolsListRequest",
    "ToolsListResponse",
    "ToolsCallRequest",
    "ToolsCallResponse",
    "Tool",
    "ToolContent",
]
