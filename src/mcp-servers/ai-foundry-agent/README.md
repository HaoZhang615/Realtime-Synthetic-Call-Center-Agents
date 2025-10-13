# AI Foundry Agent MCP Server

Model Context Protocol (MCP) server that exposes Azure AI Foundry Agent with Bing Search capabilities.

## 🎯 Purpose

This microservice wraps Azure AI Foundry Agent API and exposes it via the standardized MCP protocol. It enables:
- **Web Search**: Execute Bing-powered web searches through AI Foundry Agent
- **Ephemeral Threading**: Stateless, one-shot searches with automatic cleanup
- **Retry Logic**: Network error resilience with exponential backoff
- **MCP Protocol**: Standardized tool discovery and execution

## 🏗️ Architecture

```
MCP Client (Backend Gateway)
    ↓ HTTP/JSON-RPC 2.0
AI Foundry MCP Server (This Service)
    ├─ FastAPI App
    │   ├─ POST /mcp (tools/list, tools/call)
    │   └─ GET /health
    ├─ AI Foundry Agent Service
    │   ├─ Ephemeral Thread Management
    │   └─ Retry Logic
    └─ Azure AI Foundry SDK
        ↓
Azure AI Foundry Project
    ├─ AI Services Account
    └─ Bing Search Connection
```

## 📦 Dependencies

- Python 3.12+
- FastAPI 0.115.0
- Azure AI Projects SDK 1.0.0b3
- Azure Identity 1.19.0
- Pydantic 2.9.2

## 🚀 Local Setup & Testing

### Step 1: Install Dependencies

```bash
cd src/mcp-servers/ai-foundry-agent

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your Azure resources (from `azd provision` output):

```bash
# Get from: azd env get-values
AZURE_AI_FOUNDRY_ENDPOINT=https://cog-xxx.cognitiveservices.azure.com/
AZURE_AI_FOUNDRY_PROJECT_ID=/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}
AZURE_AI_FOUNDRY_BING_CONNECTION_ID=/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/connections/{connection}
AZURE_OPENAI_GPT_CHAT_DEPLOYMENT=gpt-4.1-nano
PORT=8000
```

**To get these values from your existing deployment:**

```bash
# Navigate to project root
cd ../../../

# Get all environment variables
azd env get-values

# Copy the values for:
# - AZURE_AI_FOUNDRY_ENDPOINT
# - AZURE_AI_FOUNDRY_PROJECT_ID (from Azure portal or azd outputs)
# - AZURE_AI_FOUNDRY_BING_CONNECTION_ID (from Azure portal)
# - AZURE_OPENAI_GPT_CHAT_DEPLOYMENT
```

### Step 3: Authenticate with Azure

```bash
# Login to Azure (for Managed Identity simulation)
az login

# Set the subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### Step 4: Run the Server

```bash
# From ai-foundry-agent directory
python main.py
```

Expected output:
```
2025-10-14 10:00:00 - __main__ - INFO - 🚀 Starting AI Foundry MCP Server...
2025-10-14 10:00:01 - services.foundry_agent - INFO - Initializing AI Foundry Agent Service...
2025-10-14 10:00:01 - services.foundry_agent - INFO - Endpoint: https://cog-xxx.cognitiveservices.azure.com/
2025-10-14 10:00:02 - services.foundry_agent - INFO - Creating AI Foundry agent with Bing Search tool...
2025-10-14 10:00:03 - services.foundry_agent - INFO - ✅ AI Foundry Agent initialized successfully: asst_xxx
2025-10-14 10:00:03 - __main__ - INFO - ✅ AI Foundry MCP Server started successfully
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 5: Test the MCP Endpoints

#### Test 1: Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "ai-foundry-mcp",
  "agent_id": "asst_xyz123"
}
```

#### Test 2: Tools List (Discovery)

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "search_web_ai_foundry",
        "description": "Search the web using Azure AI Foundry Agent with Bing Search...",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "The search query to execute"
            }
          },
          "required": ["query"]
        }
      }
    ]
  }
}
```

#### Test 3: Tool Execution (Web Search)

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_web_ai_foundry",
      "arguments": {
        "query": "What is the weather in Seattle today?"
      }
    }
  }'
```

Expected response (after 2-5 seconds):
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "According to current weather data from Bing, Seattle is experiencing partly cloudy skies with a temperature of 52°F (11°C). There is a 30% chance of rain later in the afternoon..."
      }
    ]
  }
}
```

**Check server logs for execution details:**
```
INFO - Received MCP request: method=tools/call, id=2
INFO - Executing tool: search_web_ai_foundry with args: {'query': 'What is the weather in Seattle today?'}
INFO - Executing web search: 'What is the weather in Seattle today?'
DEBUG - Creating ephemeral thread...
DEBUG - Thread created: thread_xxx
DEBUG - Adding user message: 'What is the weather in Seattle today?'
DEBUG - Creating run...
DEBUG - Run created: run_xxx, Status: completed
DEBUG - Retrieving messages...
DEBUG - Deleting ephemeral thread: thread_xxx
DEBUG - Thread deleted successfully
INFO - ✅ Search completed successfully (length: 234 chars)
INFO - ✅ Search completed: 234 chars
```

## 🧪 Testing Different Scenarios

### Test Error Handling: Invalid Tool

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "nonexistent_tool",
      "arguments": {}
    }
  }'
```

Expected:
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32000,
    "message": "Tool not found: nonexistent_tool"
  }
}
```

### Test Error Handling: Missing Required Parameter

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_web_ai_foundry",
      "arguments": {}
    }
  }'
```

Expected:
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32602,
    "message": "Missing required argument: query"
  }
}
```

### Test Performance: Multiple Concurrent Requests

```bash
# Test 5 concurrent searches
for i in {1..5}; do
  curl -X POST http://localhost:8000/mcp \
    -H "Content-Type: application/json" \
    -d "{
      \"jsonrpc\": \"2.0\",
      \"id\": $i,
      \"method\": \"tools/call\",
      \"params\": {
        \"name\": \"search_web_ai_foundry\",
        \"arguments\": {
          \"query\": \"Test query $i\"
        }
      }
    }" &
done
wait
```

Expected: All 5 requests complete successfully (ephemeral threading ensures no state conflicts)

## 🐛 Troubleshooting

### Issue: Agent Initialization Fails

**Symptoms:**
```
ERROR - Failed to start server: AI Foundry Agent initialization failed
```

**Solutions:**
1. Check environment variables are set correctly:
   ```bash
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'Endpoint: {os.getenv(\"AZURE_AI_FOUNDRY_ENDPOINT\")}')"
   ```

2. Verify Azure authentication:
   ```bash
   az account show
   ```

3. Check Azure RBAC permissions (you need "Azure AI Developer" role):
   ```bash
   az role assignment list --assignee $(az account show --query user.name -o tsv) --scope <PROJECT_ID>
   ```

### Issue: 503 Service Unavailable on /health

**Symptoms:**
```json
{"detail": "Agent not initialized"}
```

**Solutions:**
- Check server logs for initialization errors
- Verify Bing Connection ID exists in Azure portal
- Ensure AI Foundry project has Bing connection configured

### Issue: Tool Execution Timeout

**Symptoms:**
```json
{
  "error": {
    "code": -32003,
    "message": "Search execution exceeded 30 seconds"
  }
}
```

**Solutions:**
- This is normal for complex queries or slow Bing responses
- Retry the request (ephemeral threads ensure clean state)
- Check Azure AI Foundry service health in portal

### Issue: Thread Cleanup Warnings

**Symptoms:**
```
WARNING - Failed to cleanup thread thread_xxx: ...
```

**Impact:** Low - threads will be cleaned up eventually by Azure
**Solutions:** Monitor logs; if persistent, restart the server

## 📊 Monitoring & Observability

### Key Metrics to Watch

1. **Request Rate**: Tools calls per minute
2. **Latency**: P50, P95, P99 response times
3. **Error Rate**: % of failed searches
4. **Thread Lifecycle**: Threads created vs deleted

### Log Levels

- `INFO`: Request/response logs, agent lifecycle
- `DEBUG`: Thread management, message details
- `WARNING`: Retry attempts, cleanup failures
- `ERROR`: Initialization failures, execution errors

### Structured Logs

All logs include:
- Timestamp
- Logger name
- Log level
- Message
- (Optional) Stack trace for errors

Example:
```
2025-10-14 10:05:23 - services.foundry_agent - INFO - Executing web search: 'weather Seattle'
```

## 🔒 Security Considerations

- **Managed Identity**: Uses DefaultAzureCredential (no keys in code)
- **Non-root User**: Container runs as `appuser` (UID 1000)
- **No Persistent State**: Ephemeral threads prevent data leakage
- **Input Validation**: Pydantic models validate all inputs
- **Error Sanitization**: Sensitive data not exposed in error messages

## 📁 Project Structure

```
ai-foundry-agent/
├── main.py                    # FastAPI application & MCP endpoints
├── models/
│   ├── __init__.py
│   └── mcp_protocol.py        # Pydantic models for MCP protocol
├── services/
│   ├── __init__.py
│   └── foundry_agent.py       # AI Foundry Agent wrapper with threading
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project metadata & build config
├── Dockerfile                 # Container image definition
├── .env.example               # Environment variable template
└── README.md                  # This file
```

## 🚢 Deployment to Azure (Phase 2)

Deployment will be covered in Phase 1.3. For now, focus on local testing.

Quick preview:
```bash
# Build container image
docker build -t aifoundry-mcp:latest .

# Deploy to Azure Container Apps (azd integration)
azd deploy
```

## 📚 References

- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [Azure AI Foundry Agent API](https://learn.microsoft.com/en-us/azure/ai-services/agents/)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 🤝 Support

For issues or questions:
1. Check troubleshooting section above
2. Review server logs for detailed error messages
3. Verify Azure resources are correctly provisioned
4. Test with simpler queries first

## ✅ Phase 1.1 Checklist

- [x] Project structure created
- [x] MCP protocol models implemented
- [x] AI Foundry Agent wrapper with ephemeral threading
- [x] FastAPI application with retry logic
- [x] Configuration and dependencies
- [x] Dockerfile for containerization
- [x] Local testing instructions

**Next Steps:** Complete local testing, then proceed to Phase 1.2 (Backend MCP Client Integration)
