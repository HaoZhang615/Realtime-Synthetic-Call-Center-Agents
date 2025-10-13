"""
AI Foundry Agent MCP Server - FastAPI Application

Exposes Azure AI Foundry Agent via Model Context Protocol (MCP).
Implements tools/list and tools/call endpoints for web search capability.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Load environment variables from .env file
load_dotenv()

from models.mcp_protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPErrorCode,
    Tool,
    ToolContent,
)
from services.foundry_agent import AIFoundryAgentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Reduce noise from Azure SDK and HTTP libraries
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Global AI Foundry service instance
agent_service: AIFoundryAgentService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Initializes AI Foundry agent on startup, cleans up on shutdown.
    """
    global agent_service
    
    # Startup
    try:
        logger.info("🚀 Starting AI Foundry MCP Server...")
        
        # Load configuration from environment
        endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        project_id = os.getenv("AZURE_AI_FOUNDRY_PROJECT_ID")
        bing_connection_id = os.getenv("AZURE_AI_FOUNDRY_BING_CONNECTION_ID")
        model_deployment = os.getenv("AZURE_OPENAI_GPT_CHAT_DEPLOYMENT", "gpt-4.1-nano")
        
        if not all([endpoint, project_id, bing_connection_id]):
            raise RuntimeError(
                "Missing required environment variables: "
                "AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_PROJECT_ID, AZURE_AI_FOUNDRY_BING_CONNECTION_ID"
            )
        
        # Initialize AI Foundry service
        agent_service = AIFoundryAgentService(
            endpoint=endpoint,
            project_id=project_id,
            bing_connection_id=bing_connection_id,
            model_deployment=model_deployment,
            max_retries=1,
            timeout_seconds=30,
        )
        
        await agent_service.initialize()
        logger.info("✅ AI Foundry MCP Server started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}", exc_info=True)
        raise
    
    yield  # Server is running
    
    # Shutdown
    logger.info("Shutting down AI Foundry MCP Server...")
    if agent_service:
        await agent_service.cleanup()
    logger.info("✅ Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="AI Foundry Agent MCP Server",
    description="Model Context Protocol server for Azure AI Foundry Agent with Bing Search",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for Container Apps health probes.
    
    Returns 200 OK if agent is initialized, 503 Service Unavailable otherwise.
    """
    if agent_service and agent_service._initialized:
        return {
            "status": "healthy",
            "service": "ai-foundry-mcp",
            "agent_id": agent_service.agent.id if agent_service.agent else "unknown"
        }
    else:
        raise HTTPException(status_code=503, detail="Agent not initialized")


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> JSONResponse:
    """
    Main MCP protocol endpoint.
    
    Handles:
    - tools/list: Returns list of available tools
    - tools/call: Executes a specific tool
    
    Follows JSON-RPC 2.0 spec.
    """
    try:
        # Parse JSON body
        body = await request.json()
        
        # Validate MCP request structure
        try:
            mcp_request = MCPRequest(**body)
        except ValidationError as e:
            logger.warning(f"Invalid MCP request: {e}")
            return _error_response(
                request_id=body.get("id", 0),
                code=MCPErrorCode.INVALID_REQUEST,
                message="Invalid MCP request format",
                data={"errors": e.errors()}
            )
        
        # Route to appropriate handler
        method = mcp_request.method
        request_id = mcp_request.id
        
        logger.info(f"Received MCP request: method={method}, id={request_id}")
        
        if method == "tools/list":
            return await _handle_tools_list(request_id)
        elif method == "tools/call":
            return await _handle_tools_call(request_id, mcp_request.params or {})
        else:
            logger.warning(f"Unknown method: {method}")
            return _error_response(
                request_id=request_id,
                code=MCPErrorCode.METHOD_NOT_FOUND,
                message=f"Method not found: {method}"
            )
    
    except Exception as e:
        logger.error(f"Unexpected error handling MCP request: {e}", exc_info=True)
        return _error_response(
            request_id=body.get("id", 0) if 'body' in locals() else 0,
            code=MCPErrorCode.INTERNAL_ERROR,
            message=f"Internal server error: {str(e)}"
        )


async def _handle_tools_list(request_id: int | str) -> JSONResponse:
    """
    Handle tools/list request.
    
    Returns list of available tools with their schemas.
    """
    tools = [
        Tool(
            name="search_web_ai_foundry",
            description=(
                "Search the web using Azure AI Foundry Agent with Bing Search. "
                "Use this tool to find current information, news, facts, or answers "
                "to questions that require up-to-date knowledge from the internet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute"
                    }
                },
                "required": ["query"]
            }
        )
    ]
    
    response = MCPResponse(
        jsonrpc="2.0",
        id=request_id,
        result={"tools": [tool.model_dump() for tool in tools]}
    )
    
    logger.info(f"✅ Returned {len(tools)} tools")
    return JSONResponse(content=response.model_dump())


async def _handle_tools_call(request_id: int | str, params: Dict[str, Any]) -> JSONResponse:
    """
    Handle tools/call request.
    
    Executes the specified tool with given arguments.
    """
    # Extract tool name and arguments
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.INVALID_PARAMS,
            message="Missing required parameter: name"
        )
    
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
    
    # Route to appropriate tool handler
    if tool_name == "search_web_ai_foundry":
        return await _execute_web_search(request_id, arguments)
    else:
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.TOOL_NOT_FOUND,
            message=f"Tool not found: {tool_name}"
        )


async def _execute_web_search(request_id: int | str, arguments: Dict[str, Any]) -> JSONResponse:
    """
    Execute web search using AI Foundry agent.
    
    Args:
        request_id: MCP request ID
        arguments: Tool arguments (must contain 'query')
    """
    # Validate arguments
    query = arguments.get("query")
    if not query:
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.INVALID_PARAMS,
            message="Missing required argument: query"
        )
    
    # Check if agent is initialized
    if not agent_service or not agent_service._initialized:
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.AGENT_INITIALIZATION_ERROR,
            message="AI Foundry agent not initialized"
        )
    
    # Execute search with timeout and retry logic
    try:
        result_text = await agent_service.search_web(query)
        
        # Construct MCP response
        response = MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            result={
                "content": [
                    ToolContent(type="text", text=result_text).model_dump()
                ]
            }
        )
        
        logger.info(f"✅ Search completed: {len(result_text)} chars")
        return JSONResponse(content=response.model_dump())
        
    except TimeoutError as e:
        logger.error(f"Search timeout: {e}")
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.TIMEOUT_ERROR,
            message=str(e)
        )
    except RuntimeError as e:
        logger.error(f"Search execution error: {e}")
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.TOOL_EXECUTION_ERROR,
            message=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}", exc_info=True)
        return _error_response(
            request_id=request_id,
            code=MCPErrorCode.INTERNAL_ERROR,
            message=f"Unexpected error: {str(e)}"
        )


def _error_response(
    request_id: int | str,
    code: int,
    message: str,
    data: Dict[str, Any] = None
) -> JSONResponse:
    """
    Construct MCP error response.
    
    Follows JSON-RPC 2.0 error response format.
    """
    response = MCPResponse(
        jsonrpc="2.0",
        id=request_id,
        error=MCPError(code=code, message=message, data=data)
    )
    
    return JSONResponse(
        content=response.model_dump(),
        status_code=200  # MCP uses 200 OK even for errors (JSON-RPC spec)
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,  # Disable reload in production
    )
