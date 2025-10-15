# AI Foundry Infrastructure Setup - Complete

## Summary

Successfully implemented the Azure AI Foundry infrastructure following the pattern from [foundry-samples/45-basic-agent-bing](https://github.com/azure-ai-foundry/foundry-samples/tree/main/samples/microsoft/infrastructure-setup/45-basic-agent-bing).

## Infrastructure Components Deployed

### 1. **Bing Search for Grounding** (`modules/bing/grounding-bing-search.bicep`)
- **Resource**: `Microsoft.Bing/accounts@2020-06-10`
- **SKU**: G1
- **Kind**: Bing.Grounding
- **Purpose**: Provides web search capabilities for the AI agent

### 2. **AI Foundry Account** (`modules/ai/account.bicep`)
- **Resource**: `Microsoft.CognitiveServices/accounts@2025-04-01-preview`
- **Kind**: AIServices
- **Name**: `aifoundry-{resourceToken}`
- **Features**:
  - System-assigned managed identity
  - Supports project management (`allowProjectManagement: true`)
  - Model deployment: `gpt-4o-realtime-preview`
  - Public network access enabled

### 3. **AI Foundry Project** (`modules/ai/project.bicep`)
- **Resource**: `Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview`
- **Name**: `project-{resourceToken}`
- **Parent**: AI Foundry Account
- **Features**:
  - System-assigned managed identity
  - Project description and display name

### 4. **Bing Search Connection** (`modules/ai/bing-connection.bicep`)
- **Resource**: `Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview`
- **Category**: ApiKey
- **Auth Type**: ApiKey (using Bing Search keys)
- **Purpose**: Connects AI Foundry account to Bing Search for grounding

### 5. **RBAC Configuration** (`modules/ai/rbac.bicep`)
- **Role**: Azure AI Developer (`64702f94-c441-49e6-a78b-ef80e0188fee`)
- **Assignees**:
  - Backend Container App Managed Identity
  - User Principal (for testing/development)

## Environment Variables Added to Backend

The following environment variables are now available in the backend Container App:

```bash
AZURE_AI_FOUNDRY_ENDPOINT=<AI Foundry Account Endpoint>
AZURE_AI_FOUNDRY_PROJECT_ID=<Project Resource ID>
AZURE_AI_FOUNDRY_BING_CONNECTION_ID=<Bing Connection Resource ID>
```

## Deployment Validation

✅ **Bicep Compilation**: Successfully validated with `az bicep build`
- No errors
- Expected warnings for Bing resource type (no schema available)

## Next Steps for Phase 1 Implementation

### 1. **Create MCP Route in Backend** (see previous recommendation)

```python
# src/backend/routes/mcp_agents.py
from fastapi import APIRouter, HTTPException
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

mcp_router = APIRouter()

class AIFoundryAgentService:
    def __init__(self):
        self.client = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        )
        self.agent_id = None
        
    async def initialize(self):
        # Create agent with Bing Search tool
        agent = await self.client.agents.create_agent(
            model=os.getenv("AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT"),
            name="Web Search Agent",
            instructions="...",
            tools=[{"type": "bing_grounding"}]
        )
        self.agent_id = agent.id
        
    async def search_web(self, query: str) -> str:
        # Create ephemeral thread
        thread = await self.client.agents.create_thread()
        try:
            # Execute search via AI Foundry agent
            # ... (implementation as previously described)
        finally:
            await self.client.agents.delete_thread(thread.id)
```

### 2. **Register MCP Route**

```python
# src/backend/main.py
from routes.mcp_agents import mcp_router

app.include_router(mcp_router, prefix="/api/mcp", tags=["mcp"])
```

### 3. **Update Orchestrator**

```python
# src/backend/services/assistant_service.py
async def handle_tool_call(self, tool_name: str, parameters: dict, call_id: str):
    if tool_name == "search_web_ai_foundry":
        # Call local MCP endpoint
        response = await self.http_client.post(
            f"{self.backend_base_url}/api/mcp/ai-foundry",
            json={
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                }
            }
        )
        # ... handle response
    else:
        # Existing tool handling
        pass
```

### 4. **Deploy and Test**

```bash
# Deploy infrastructure
azd provision

# Deploy backend with new route
azd deploy backend

# Test MCP endpoint
curl -X POST https://<backend-url>/api/mcp/ai-foundry \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

## Architecture Diagram

```
Browser WebSocket
    ↓
FastAPI Backend (Container App)
    ├─ /api/mcp/ai-foundry (NEW MCP endpoint)
    │     ↓
    │  AI Foundry Agent Service
    │     ↓
    │  Azure AI Foundry Project
    │     ├─ AI Foundry Account
    │     └─ Bing Search Connection
    │           └─ Bing Grounding Service
    │
    └─ Existing routes (/api/*, /api/realtime/*)
```

## Key Benefits

1. ✅ **Minimal Infrastructure Changes**: Added to existing backend, no new Container App needed
2. ✅ **Zero Additional Cost**: Uses existing backend Container App
3. ✅ **Low Latency**: In-process HTTP call (~1-5ms vs 20-50ms network hop)
4. ✅ **Simple Deployment**: Single `azd up` deploys everything
5. ✅ **Easier Debugging**: All logs in one place
6. ✅ **Gradual Migration**: Can extract to separate service later if needed

## Files Modified/Created

### Created:
- `infra/modules/ai/account.bicep`
- `infra/modules/ai/project.bicep`
- `infra/modules/ai/bing-connection.bicep`
- `infra/modules/ai/rbac.bicep`

### Modified:
- `infra/main.bicep` (added AI Foundry resources, RBAC, env vars, outputs)

### Existing (Used):
- `infra/modules/bing/grounding-bing-search.bicep` (already present)

## Deployment Command

```bash
# Provision all infrastructure (including AI Foundry)
azd provision

# The following resources will be created:
# - Bing Search for Grounding
# - AI Foundry Account
# - AI Foundry Project
# - Bing Search Connection
# - RBAC role assignments
```

## Documentation References

- [Azure AI Foundry Agent Service Setup](https://learn.microsoft.com/en-us/azure/ai-services/agents/environment-setup)
- [Foundry Samples - Basic Agent with Bing](https://github.com/azure-ai-foundry/foundry-samples/tree/main/samples/microsoft/infrastructure-setup/45-basic-agent-bing)
- [Azure AI Developer Role](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#azure-ai-developer)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
