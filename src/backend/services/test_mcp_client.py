"""
Test MCP Client

Simple test to validate MCP client connectivity and functionality.
Run this after starting the AI Foundry MCP Server.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mcp_client import MCPClient, MCPClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_mcp_client():
    """Test MCP client functionality"""
    
    # Set MCP server URL (default to localhost)
    mcp_url = os.getenv("AZURE_AI_FOUNDRY_MCP_URL", "http://localhost:8888")
    logger.info(f"Testing MCP client against: {mcp_url}")
    
    try:
        async with MCPClient(base_url=mcp_url) as client:
            logger.info("✅ MCP Client initialized")
            
            # Test 1: Discover tools
            logger.info("\n--- Test 1: Tool Discovery ---")
            tools = await client.discover_tools()
            logger.info(f"Found {len(tools)} tools:")
            for tool in tools:
                logger.info(f"  - {tool['name']}: {tool['description']}")
            
            # Test 2: Get tool schema
            logger.info("\n--- Test 2: Get Tool Schema ---")
            schema = await client.get_tool_schema("search_web_ai_foundry")
            logger.info(f"Tool schema: {schema['inputSchema']}")
            
            # Test 3: Execute web search
            logger.info("\n--- Test 3: Execute Web Search ---")
            query = "What is the weather in Seattle today?"
            logger.info(f"Search query: {query}")
            result = await client.search_web(query)
            logger.info(f"Search result ({len(result)} chars):")
            logger.info(f"  {result[:200]}...")
            
            logger.info("\n✅ All tests passed!")
            
    except MCPClientError as e:
        logger.error(f"❌ MCP Client error: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_mcp_client())
    sys.exit(exit_code)
