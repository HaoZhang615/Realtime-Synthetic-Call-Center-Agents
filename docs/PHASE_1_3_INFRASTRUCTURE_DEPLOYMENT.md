# Phase 1.3: Infrastructure Deployment (Bicep)

## Overview

This phase deploys the **AI Foundry MCP Server** to Azure Container Apps alongside the existing backend and frontend services. The MCP server is deployed with internal-only ingress, accessible exclusively by the backend service.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Azure Container Apps Environment                  │
│                                                             │
│  ┌────────────┐      ┌────────────┐      ┌──────────────┐ │
│  │  Frontend  │◄─────┤  Backend   │◄─────┤ AI Foundry   │ │
│  │ Container  │ HTTPS│ Container  │ HTTP │ MCP Server   │ │
│  │    App     │      │    App     │      │ Container    │ │
│  └────────────┘      └────────────┘      └──────────────┘ │
│       ▲                    ▲                     ▲         │
│       │                    │                     │         │
│   External              External             Internal      │
│   Ingress              Ingress              Ingress Only   │
└───────┼────────────────────┼─────────────────────┼─────────┘
        │                    │                     │
        │                    │                     │
    Internet            Internet         AI Foundry Agent
                                        (Bing Search)
```

### Key Design Decisions

1. **Internal Ingress Only**: MCP server is NOT exposed to the internet
2. **Service-to-Service Communication**: Backend calls MCP server via internal FQDN
3. **Shared Identity**: All containers use the same managed identity for Azure resource access
4. **Environment Parity**: MCP server uses same AI Foundry configuration as backend

## Infrastructure Components

### New Resources

#### 1. AI Foundry MCP Server Container App
- **Module**: `infra/modules/app/aifoundry-mcp.bicep`
- **Purpose**: Deploy MCP server with specialized configuration
- **Features**:
  - Internal ingress only (`external: false`)
  - Health probes (startup, liveness, readiness)
  - Auto-scaling (1-3 replicas based on HTTP requests)
  - Managed identity authentication

#### 2. Environment Variable: `AZURE_AI_FOUNDRY_MCP_URL`
- **Set on**: Backend Container App
- **Value**: Internal FQDN of MCP server (e.g., `https://ca-aifoundry-mcp-{token}.internal.{region}.azurecontainerapps.io`)
- **Used by**: MCP Client (`src/backend/services/mcp_client.py`)

### Modified Resources

#### 1. Backend Container App (`infra/main.bicep`)
- **New Environment Variable**: `AZURE_AI_FOUNDRY_MCP_URL`
- **Value Source**: `mcpServerApp.outputs.fqdn`
- **Impact**: Backend can now discover and connect to MCP server

#### 2. Azure Container Apps Environment
- **Change**: Now hosts 3 container apps instead of 2
- **Services**: frontend, backend, ai-foundry-mcp

## Deployment Files

### 1. `infra/modules/app/aifoundry-mcp.bicep`

Specialized Bicep module for MCP server deployment:

```bicep
// Key Configuration
configuration: {
  ingress: {
    external: false  // ❗ Internal only
    targetPort: 8000
    allowInsecure: false
  }
}

// Health Probes
probes: [
  {
    type: 'Startup'
    httpGet: { path: '/health', port: 8000 }
    failureThreshold: 30  // 5 minutes total
  }
  {
    type: 'Liveness'
    httpGet: { path: '/health', port: 8000 }
    periodSeconds: 30
  }
  {
    type: 'Readiness'
    httpGet: { path: '/health', port: 8000 }
    periodSeconds: 10
  }
]

// Auto-scaling
scale: {
  minReplicas: 1
  maxReplicas: 3
  rules: [{
    name: 'http-scaling'
    http: { concurrentRequests: '50' }
  }]
}
```

### 2. `infra/main.bicep` (Updated)

Added MCP server module call and updated backend environment variables:

```bicep
// Backend: Add MCP URL
module backendApp 'modules/app/containerapp.bicep' = {
  params: {
    env: {
      // ...existing vars...
      AZURE_AI_FOUNDRY_MCP_URL: mcpServerApp.outputs.fqdn  // 🆕
    }
  }
}

// New: MCP Server
module mcpServerApp 'modules/app/aifoundry-mcp.bicep' = {
  params: {
    appName: '${abbrs.appContainerApps}aifoundry-mcp-${resourceToken}'
    serviceName: 'ai-foundry-mcp'
    env: {
      AZURE_AI_FOUNDRY_ENDPOINT: account.outputs.accountEndpoint
      AZURE_AI_FOUNDRY_PROJECT_ID: aiFoundryProject.outputs.projectId
      AZURE_AI_FOUNDRY_BING_CONNECTION_ID: bingConnection.outputs.connectionId
      AZURE_OPENAI_GPT_CHAT_DEPLOYMENT: aoaiGptChatModelName
      AZURE_CLIENT_ID: appIdentity.outputs.clientId
    }
  }
}
```

### 3. `azure.yaml` (Updated)

Added MCP server as a new azd service:

```yaml
services:
  frontend:
    project: ./src/frontend
    host: containerapp
  backend:
    project: ./src/backend
    host: containerapp
  ai-foundry-mcp:  # 🆕 New service
    project: ./src/mcp-servers/ai-foundry-agent
    host: containerapp
    language: python
    docker:
      path: Dockerfile
      remoteBuild: true
```

## Deployment Steps

### Prerequisites

1. **Azure Developer CLI (azd)** installed
2. **Existing deployment** of backend and frontend
3. **MCP server code** complete (Phase 1.1 ✅)
4. **MCP client integration** complete (Phase 1.2 ✅)

### Step 1: Provision Infrastructure

```bash
# Navigate to project root
cd C:\repo\Realtime-Synthetic-Call-Center-Agents

# Provision Azure resources (updates existing deployment)
azd provision
```

**What happens:**
- Updates Container Apps Environment with new MCP server
- Creates AI Foundry MCP Container App with internal ingress
- Updates backend with `AZURE_AI_FOUNDRY_MCP_URL` environment variable
- No downtime for existing frontend/backend

**Expected Output:**
```
Provisioning Azure resources...
✓ Created resource group: rg-{env-name}
✓ Updated container apps environment: cae-{token}
✓ Created container app: ca-aifoundry-mcp-{token}
✓ Updated container app: ca-backend-{token}
```

### Step 2: Deploy Application Code

```bash
# Deploy all services (builds and pushes containers)
azd deploy
```

**What happens:**
- Builds Docker image for MCP server (`src/mcp-servers/ai-foundry-agent`)
- Pushes image to Azure Container Registry
- Deploys new revision of MCP server container app
- Redeploys backend (to pick up new environment variable)
- Redeploys frontend (no changes, but part of multi-service deployment)

**Expected Output:**
```
Deploying services...
  ✓ Building ai-foundry-mcp container...
  ✓ Pushing to Azure Container Registry...
  ✓ Deploying ai-foundry-mcp revision...
  ✓ Updating backend...
  ✓ Updating frontend...
All services deployed successfully!
```

### Step 3: Verify Deployment

#### Check Container App Status

```bash
# List all container apps
az containerapp list --resource-group rg-{env-name} --query "[].{Name:name, Status:properties.provisioningState, Ingress:properties.configuration.ingress.external}" -o table
```

**Expected Output:**
```
Name                       Status      Ingress
-------------------------  ----------  --------
ca-frontend-{token}        Succeeded   true
ca-backend-{token}         Succeeded   true
ca-aifoundry-mcp-{token}   Succeeded   false    ⬅️ Internal only
```

#### Check MCP Server Health

```bash
# Get backend container app URL
BACKEND_URL=$(az containerapp show --name ca-backend-{token} --resource-group rg-{env-name} --query properties.configuration.ingress.fqdn -o tsv)

# Test MCP server via backend (backend can access internal MCP server)
# Note: Direct access from outside is not possible due to internal ingress
```

#### Check Environment Variables

```bash
# Verify backend has MCP URL configured
az containerapp show --name ca-backend-{token} --resource-group rg-{env-name} --query "properties.template.containers[0].env[?name=='AZURE_AI_FOUNDRY_MCP_URL']" -o table
```

**Expected Output:**
```
Name                        Value
--------------------------  --------------------------------------------------------
AZURE_AI_FOUNDRY_MCP_URL    https://ca-aifoundry-mcp-{token}.internal.{region}.azurecontainerapps.io
```

### Step 4: Test End-to-End Integration

#### Option 1: Via Frontend (Recommended)

1. Open frontend URL: `https://ca-frontend-{token}.{region}.azurecontainerapps.io`
2. Start a voice conversation
3. Ask a question that requires web search: "What's the weather in Seattle?"
4. Backend should route to MCP server → AI Foundry → Bing → Return results

#### Option 2: Via Backend API

```bash
# Get backend URL
BACKEND_URL=$(az containerapp show --name ca-backend-{token} --resource-group rg-{env-name} --query properties.configuration.ingress.fqdn -o tsv)

# Make a test request (adjust based on your API)
curl -X POST https://${BACKEND_URL}/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "latest news about AI"}'
```

#### Option 3: Check Application Insights Logs

```bash
# Query Application Insights for MCP client logs
az monitor app-insights query \
  --app {app-insights-name} \
  --analytics-query "traces | where message contains 'MCP' | order by timestamp desc | take 20"
```

**Expected Logs:**
```
✅ MCP Client initialized successfully
MCP server health: healthy (agent: asst_...)
Discovered 1 tools: ['search_web_ai_foundry']
Executing MCP tool: search_web_ai_foundry with args: {'query': '...'}
✅ Tool search_web_ai_foundry completed: 456 chars
```

## Environment Variables Reference

### Backend Container App

| Variable | Source | Example Value |
|----------|--------|---------------|
| `AZURE_AI_FOUNDRY_MCP_URL` | `mcpServerApp.outputs.fqdn` | `https://ca-aifoundry-mcp-abc123.internal.eastus2.azurecontainerapps.io` |
| `AZURE_AI_FOUNDRY_ENDPOINT` | `account.outputs.accountEndpoint` | `https://cog-abc123.cognitiveservices.azure.com/` |
| `AZURE_AI_FOUNDRY_PROJECT_ID` | `aiFoundryProject.outputs.projectId` | `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}` |
| `AZURE_AI_FOUNDRY_BING_CONNECTION_ID` | `bingConnection.outputs.connectionId` | `bing_grounding_{token}` |

### MCP Server Container App

| Variable | Source | Example Value |
|----------|--------|---------------|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Same as backend | `https://cog-abc123.cognitiveservices.azure.com/` |
| `AZURE_AI_FOUNDRY_PROJECT_ID` | Same as backend | `/subscriptions/{sub}/...` |
| `AZURE_AI_FOUNDRY_BING_CONNECTION_ID` | Same as backend | `bing_grounding_{token}` |
| `AZURE_OPENAI_GPT_CHAT_DEPLOYMENT` | `aoaiGptChatModelName` | `gpt-4.1-nano` |
| `AZURE_CLIENT_ID` | `appIdentity.outputs.clientId` | `{guid}` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `monitoring.outputs.appInsightsConnectionString` | `InstrumentationKey={key};...` |

## Troubleshooting

### Issue: MCP Server Not Starting

**Symptoms**: Container app shows "Failed" provisioning state

**Check logs**:
```bash
az containerapp logs show --name ca-aifoundry-mcp-{token} --resource-group rg-{env-name} --tail 100
```

**Common causes**:
1. Missing environment variables → Check AI Foundry endpoint/project/connection
2. Health check failing → Verify `/health` endpoint returns 200 OK
3. Image pull errors → Check Azure Container Registry access

**Fix**:
```bash
# Restart container app
az containerapp revision restart --name ca-aifoundry-mcp-{token} --resource-group rg-{env-name} --revision {revision-name}
```

### Issue: Backend Cannot Reach MCP Server

**Symptoms**: Backend logs show "MCP connection error" or "Health check failed"

**Check connectivity**:
```bash
# Exec into backend container
az containerapp exec --name ca-backend-{token} --resource-group rg-{env-name} --command /bin/bash

# Inside container, test MCP URL
curl $AZURE_AI_FOUNDRY_MCP_URL/health
```

**Common causes**:
1. Wrong MCP URL → Check `AZURE_AI_FOUNDRY_MCP_URL` environment variable
2. MCP server not running → Check container app status
3. Network policy blocking internal traffic → Verify Container Apps Environment settings

**Fix**:
```bash
# Update backend environment variable if MCP URL is wrong
az containerapp update --name ca-backend-{token} --resource-group rg-{env-name} \
  --set-env-vars AZURE_AI_FOUNDRY_MCP_URL={correct-url}
```

### Issue: Web Search Not Working End-to-End

**Symptoms**: No search results returned, timeout errors

**Debug steps**:

1. **Check MCP Server Logs**:
   ```bash
   az containerapp logs show --name ca-aifoundry-mcp-{token} --resource-group rg-{env-name} --tail 50
   ```
   Look for: Agent initialization, tool execution logs

2. **Check Backend Logs**:
   ```bash
   az containerapp logs show --name ca-backend-{token} --resource-group rg-{env-name} --tail 50 | grep MCP
   ```
   Look for: MCP client initialization, tool discovery, execution attempts

3. **Check AI Foundry Agent**:
   ```bash
   # Verify Bing connection exists
   az cognitiveservices account show --name cog-{token} --resource-group rg-{env-name}
   ```

4. **Test MCP Server Directly** (from backend container):
   ```bash
   # Exec into backend
   az containerapp exec --name ca-backend-{token} --resource-group rg-{env-name} --command /bin/bash
   
   # Inside container, test MCP tools/list
   curl -X POST $AZURE_AI_FOUNDRY_MCP_URL/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
   ```

**Expected response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [{
      "name": "search_web_ai_foundry",
      "description": "Search the web using Azure AI Foundry Agent with Bing Search...",
      "inputSchema": {...}
    }]
  }
}
```

### Issue: Deployment Takes Too Long

**Symptoms**: `azd deploy` hangs or times out

**Common causes**:
1. Large Docker image build → Use `.dockerignore` to exclude unnecessary files
2. Slow container registry push → Use `remoteBuild: true` in azure.yaml
3. Health check taking too long → Adjust startup probe failureThreshold

**Fix**:
```bash
# Deploy specific service only
azd deploy --service ai-foundry-mcp

# Or skip build cache
azd deploy --no-cache
```

## Cost Optimization

### Current Configuration

- **MCP Server**: 1 vCPU, 2GB RAM, 1-3 replicas
- **Scaling**: HTTP request-based (50 concurrent requests threshold)
- **Always On**: Minimum 1 replica

### Estimated Monthly Cost

| Resource | Configuration | Estimated Cost (USD) |
|----------|---------------|---------------------|
| MCP Server Container App | 1 vCPU, 2GB, min 1 replica | ~$50/month |
| Container Apps Environment | Shared with backend/frontend | $0 (already provisioned) |
| Application Insights | Standard tier | ~$10/month (additional logs) |

**Total Additional Cost**: ~$60/month

### Cost Reduction Options

1. **Reduce Minimum Replicas to 0** (Cold Start trade-off):
   ```bicep
   scale: {
     minReplicas: 0  // ⚠️ First request will be slow
     maxReplicas: 3
   }
   ```
   **Savings**: ~$30/month

2. **Reduce CPU/Memory**:
   ```bicep
   resources: {
     cpu: json('0.5')    // Half vCPU
     memory: '1Gi'       // 1GB instead of 2GB
   }
   ```
   **Savings**: ~$25/month

3. **Use Consumption Plan** (when available):
   - Pay only for execution time
   - No minimum replicas cost

## Security Considerations

### Internal Ingress Only

✅ **Enforced**: MCP server is NOT accessible from internet
- `external: false` in Bicep configuration
- No public DNS name assigned
- Only accessible within Container Apps Environment

### Managed Identity Authentication

✅ **Implemented**: No API keys stored in environment variables
- Uses User-Assigned Managed Identity
- Identity has Azure AI Foundry permissions
- Keys fetched from Key Vault at runtime

### Network Isolation (Zero Trust Mode)

If deploying with `enableZeroTrust=true`:
- VNet integration for all containers
- Private endpoints for backend services
- No public internet access from containers

### TLS/HTTPS Enforcement

✅ **Configured**: All internal traffic uses HTTPS
- `allowInsecure: false` in ingress configuration
- Container Apps Environment provides automatic TLS

## Monitoring and Observability

### Application Insights Integration

Both backend and MCP server send telemetry to Application Insights:

**Key Metrics to Monitor**:
1. **MCP Server Health**: Liveness probe success rate
2. **Request Latency**: Time from backend → MCP → AI Foundry → Response
3. **Error Rate**: Failed web searches, timeout errors
4. **Scaling Events**: Replica count changes

**Useful Queries**:

```kusto
// MCP server health check failures
requests
| where name == "GET /health"
| where resultCode != "200"
| summarize FailureCount = count() by bin(timestamp, 5m)
```

```kusto
// MCP tool execution performance
traces
| where message contains "Tool search_web_ai_foundry completed"
| extend Duration = extract(@"(\d+) chars", 1, message)
| summarize avg(todouble(Duration)), percentile(todouble(Duration), 95) by bin(timestamp, 1h)
```

```kusto
// Backend → MCP communication errors
exceptions
| where outerMessage contains "MCP"
| summarize count() by outerMessage, bin(timestamp, 15m)
| order by timestamp desc
```

### Alerts (Recommended)

Configure alerts for:
1. MCP server availability < 99% (5 minutes)
2. Tool execution errors > 10 in 15 minutes
3. Request latency > 10 seconds (P95)

## Next Steps

After successful deployment, proceed to **Phase 1.4: Observability & Hardening**:

1. ✅ Add comprehensive Application Insights instrumentation
2. ✅ Implement circuit breaker pattern in MCP client
3. ✅ Perform load testing (100 concurrent users)
4. ✅ Performance tuning and optimization
5. ✅ Set up production-ready alerts and dashboards

## References

- [Azure Container Apps Documentation](https://learn.microsoft.com/azure/container-apps/)
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Phase 1.1: AI Foundry MCP Server](./PHASE_1_1_MCP_SERVER.md)
- [Phase 1.2: Backend MCP Client Integration](./PHASE_1_2_MCP_INTEGRATION.md)
