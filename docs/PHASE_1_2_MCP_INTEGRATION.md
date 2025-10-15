# Phase 1.2: Backend MCP Client Integration

## Overview

This phase integrates the AI Foundry MCP Server with the backend realtime voice system, enabling web search capabilities during live voice conversations.

## Architecture

```
Browser WebSocket
    ↓
Backend Realtime Handler
    ↓
AgentOrchestrator
    ↓
AssistantService (Tool Routing)
    ├─ Web Search Agent → MCP Client → AI Foundry MCP Server → Azure AI Foundry (Bing)
    ├─ Database Agent → Cosmos DB
    ├─ Email Agent → Logic Apps
    └─ Knowledge Base Agent → Internal Knowledge

```

## Components Created

### 1. MCP Client (`src/backend/services/mcp_client.py`)

**Purpose**: HTTP client for communicating with AI Foundry MCP Server

**Features**:
- JSON-RPC 2.0 protocol implementation
- Tool discovery (`tools/list`)
- Tool execution (`tools/call`)
- Retry logic with exponential backoff (3 attempts, 2-10s delays)
- Connection pooling for performance
- Comprehensive error handling

**Key Methods**:
- `initialize()` - Verify connectivity and discover tools
- `discover_tools()` - Get available tools from MCP server
- `execute_tool(name, args)` - Execute a tool and get results
- `search_web(query)` - Convenience method for web search

**Error Types**:
- `MCPConnectionError` - Network/connectivity issues
- `MCPToolNotFoundError` - Requested tool doesn't exist
- `MCPExecutionError` - Tool execution failed

### 2. Web Search Agent (`src/backend/agents/web_search_agent.py`)

**Purpose**: Specialized agent for web search queries

**Capabilities**:
- Real-time web search via Azure AI Foundry + Bing
- Handles: weather, news, current events, stock prices, research
- AI-synthesized responses from Bing results
- Voice-optimized output

**Tool Definition**:
```python
{
    "name": "search_web_ai_foundry",
    "description": "Search the web using Azure AI Foundry Agent with Bing Search",
    "parameters": {
        "query": {
            "type": "string",
            "description": "Search query with context"
        }
    }
}
```

### 3. AssistantService Updates

**Added Methods**:
- `initialize_mcp_client()` - Lazy initialization of MCP client
- `search_web_ai_foundry(query)` - Async web search execution

**Integration Flow**:
1. User asks question requiring web search in voice call
2. Azure OpenAI Realtime API routes to Assistant_WebSearch agent
3. Agent calls `search_web_ai_foundry` tool
4. AssistantService routes to MCP Client
5. MCP Client calls AI Foundry MCP Server (JSON-RPC)
6. AI Foundry Agent executes Bing search with ephemeral threading
7. Results flow back through chain to user as voice

## Configuration

Add to backend `.env`:

```bash
# AI Foundry MCP Server URL
AZURE_AI_FOUNDRY_MCP_URL=http://localhost:8000

# Optional: Tool call timeout (default: 15s)
TOOL_CALL_TIMEOUT_SECONDS=30
```

**For Azure deployment**, this will point to the Container App:
```bash
AZURE_AI_FOUNDRY_MCP_URL=https://aifoundry-mcp-xxxxx.azurecontainerapps.io
```

## Testing

### 1. Test MCP Client Standalone

```bash
cd src/backend

# Ensure MCP server is running
# Terminal 1: cd src/mcp-servers/ai-foundry-agent && python main.py

# Terminal 2: Test client
python -m services.test_mcp_client
```

Expected output:
```
--- Test 1: Tool Discovery ---
Found 1 tools:
  - search_web_ai_foundry: Search the web using Azure AI Foundry Agent...

--- Test 2: Get Tool Schema ---
Tool schema: {...}

--- Test 3: Execute Web Search ---
Search query: What is the weather in Seattle today?
Search result (311 chars):
  The weather in Seattle today is mostly cloudy with a temperature around 55°F...

✅ All tests passed!
```

### 2. Test in Voice Conversation

1. **Start Backend** (with MCP client integration):
   ```bash
   cd src/backend
   python main.py
   ```

2. **Start Frontend**:
   ```bash
   cd src/frontend
   npm run dev
   ```

3. **Test Web Search in Call**:
   - Open browser to frontend
   - Start a voice call
   - Say: *"Can you search the web for today's weather in Seattle?"*
   - System should:
     - Route to Web Search Agent
     - Call search_web_ai_foundry tool
     - Return Bing-powered results via voice

### 3. Test Multi-Agent Routing

**Scenario 1**: Web Search → Database
- *"What's the weather in Seattle?"* → Web Search Agent
- *"Now show me my order history"* → Database Agent

**Scenario 2**: Database → Web Search
- *"What products did I buy?"* → Database Agent
- *"Search the web for reviews of [product name]"* → Web Search Agent

## Error Handling

### MCP Server Unavailable
```python
# Backend gracefully degrades
if not self.mcp_client:
    return "Web search is currently unavailable. Please try again later."
```

### Search Timeout
- MCP Client: 3 retries with exponential backoff
- Backend tool timeout: 30s (configurable)
- User receives: "Search is taking longer than expected..."

### Invalid Query
- MCP validates required parameters
- Returns JSON-RPC error
- Backend returns: "I couldn't complete that search. Please try rephrasing."

## Performance Considerations

### Connection Pooling
```python
httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20
    )
)
```

### Caching
- Tool discovery results cached (invalidated on initialize)
- No caching of search results (real-time data)

### Timeouts
- HTTP request timeout: 60s
- Tool execution timeout: 30s (15s default, configurable)
- Retry delays: 2s, 4s, 8s (exponential)

## Monitoring

### Logs to Watch

**MCP Client Initialization**:
```
INFO - MCP Client initialized: base_url=http://localhost:8000, timeout=60s
INFO - MCP server health: healthy (agent: asst_xxx)
INFO - Discovered 1 tools: ['search_web_ai_foundry']
INFO - ✅ MCP Client initialized successfully for web search
```

**Tool Execution**:
```
INFO - Executing MCP tool: search_web_ai_foundry with args: {'query': '...'}
INFO - ✅ Tool search_web_ai_foundry completed: 311 chars
```

**Errors**:
```
ERROR - MCP HTTP error: 503 - Service Unavailable
WARNING - MCP request timeout (will retry): method=tools/call
ERROR - Web search failed: MCP error: Agent not initialized
```

## Dependencies Added

**Backend `requirements.txt`**:
- `httpx>=0.27.0` - Async HTTP client
- `tenacity>=8.2.0` - Retry logic with exponential backoff

## Next Steps

- **Phase 1.3**: Deploy AI Foundry MCP Server as Azure Container App
- **Phase 1.4**: Add Application Insights, circuit breaker, load testing

## Known Limitations

1. **MCP Server Must Be Running**: Backend requires MCP server availability
   - Mitigation: Graceful degradation with user-friendly error messages
   
2. **No Request Deduplication**: Multiple identical queries execute independently
   - Future: Add request caching with TTL
   
3. **Single MCP Server Instance**: No load balancing yet
   - Phase 1.3: Deploy multiple Container App replicas

## Troubleshooting

### "Web search is currently unavailable"
- Check `AZURE_AI_FOUNDRY_MCP_URL` environment variable
- Verify MCP server is running: `curl http://localhost:8000/health`
- Check backend logs for MCP initialization errors

### Slow Search Responses
- Check MCP server logs for Azure AI Foundry API latency
- Verify network connectivity between backend and MCP server
- Consider increasing `TOOL_CALL_TIMEOUT_SECONDS`

### Tool Not Found Errors
- Ensure MCP server has search_web_ai_foundry tool
- Run tool discovery: `python -m services.test_mcp_client`
- Check MCP server logs for agent initialization issues
