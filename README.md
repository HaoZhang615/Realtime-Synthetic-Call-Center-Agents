# Realtime Synthetic Call Center Agents

**Realtime Synthetic Call Center Agents** is an enterprise-grade AI solution that demonstrates intelligent contact center scenarios using synthetic data and real-time voice interaction powered by Azure AI Foundry.

Built on a modern **FastAPI + React** architecture (refactored from the legacy Streamlit/Chainlit implementation), this solution showcases production-ready patterns for multi-agent orchestration, real-time voice conversations, and enterprise integration.

## Overview

This solution combines:

- **🎙️ Real-time Voice Interaction**: Azure OpenAI GPT-Realtime API for natural, low-latency conversations, in GA status suited for production grade applications.
- **🤖 AI Foundry powered Multi-Agent System**: Multiple agents powered by Azure AI Foundry
  - ***📚 Grounding with Bing Search**: Web search using Bing search as grounding engine
  - ***📚 Document Intelligence**: Vector search over internal knowledge base using Azure AI Search
  - ***💾 Database Operations**: CRUD operations on synthetic customer, product, and transaction data via Cosmos DB
  - ***📧 Email Automation**: Azure Logic Apps integration for outbound communication
- **⚡ Modern Web Stack**: FastAPI backend with async WebSocket support + React TypeScript frontend, plus MCP server invokation.

![Assistant Interface](./docs/images/Realtime-Synthetic-Call-Center-Agents.webp)

The multi-agent system supports internal knowledge base queries, web search (grounded by Bing Search), and database actions (read, create, update), making it ideal for showcasing AI-driven customer support and automation in call centers and retail environments.

## Security & Networking

This solution supports **enterprise-grade security** with configurable Zero Trust architecture. During deployment with `azd up`, users can choose to enable Zero Trust networking for enhanced security:

### Zero Trust Architecture (Optional - Selected During Deployment) (**Work In Progress**) 
The `azd up` deployment process allows users to decide whether to enable Zero Trust architecture. When enabled:
- **All public endpoints are disabled** except for the AI Foundry/AI Services account (required for AI Search indexing skillset functionality)
- **Virtual Network (VNet) Integration**: Container Apps Environment deployed with VNet integration using workload profiles
- **Private Endpoints**: Backend services (Azure Storage, Cosmos DB, Azure AI Search, Key Vault) communicate privately through dedicated private endpoints
- **Private DNS Zones**: Custom DNS resolution ensures services resolve to private IP addresses within the VNet
- **Network Security**: Backend services deny public access and only allow communication through private endpoints
- **AI Services Exception**: The AI Foundry/AI Services account maintains public access and key-based authentication for AI Search compatibility

### Standard Deployment (Default)
When Zero Trust is not enabled:
- Services use public endpoints with managed identity authentication
- Simplified networking while maintaining security through RBAC and managed identities
- Easier troubleshooting and development workflows

### Authentication & Authorization
- **User-Assigned Managed Identity**: Single managed identity used across all Azure services for secure, keyless authentication
- **Role-Based Access Control (RBAC)**: Granular permissions assigned to the managed identity for each service
- **Azure Key Vault**: Secure storage for sensitive configuration like API keys
- **Azure Trusted Services**: Storage account configured to allow trusted Azure services (like AI Search) access

## How to get it work

- [Deploy the application](#how-to-deploy)
1. Access the backend FastAPI admin interface at the backend URL from the output of `azd up`.
2. Access the React frontend at the frontend URL from the output of `azd up` process
3. In the "Admin Portal" page:
-     Use the "Upload" tab in the admin interface to upload documents (PDF, DOCX, TXT) to populate the internal knowledge base
-     Use the "Files" tab in the admin interface to verify the documents have been indexed and delete any unwanted files
-     Use the "Synthetic Data" tab in the admin interface to create synthetic customers, products, purchases histories and customer conversations
-     Use the "Dashboard" tab in the admin interface to overview on the setup status and synthetic customer conversations by topic, product and agents.
4. In the "Voice Chat" page:
-     Choose one of the (synthesized) customer names to log in
-     Select the voice you want to use
-     Click on the microphone button to start voice interaction
-     Speak to interact with the AI assistant

## 🚀 Local Development

For rapid local testing and development, use the provided automation scripts:

### Quick Start (All Services)
```powershell
# Start MCP Server, Backend, and Frontend in separate windows
.\start-local-dev.ps1

# Or double-click: start-local-dev.cmd
```

This opens 3 terminal windows:
- **MCP Server** (port 8888) - AI Foundry Agent with Bing Search
- **Backend API** (port 8000) - FastAPI server
- **Frontend** (port 5173) - React UI

### Check Service Status
```powershell
.\status-local-dev.ps1
```

### Stop All Services
```powershell
.\stop-local-dev.ps1
```

### Advanced Options
```powershell
# Use Azure MCP server instead of local
.\start-local-dev.ps1 -SkipMcp

# Custom ports
.\start-local-dev.ps1 -McpPort 9000 -BackendPort 8001

# Only start specific services
.\start-local-dev.ps1 -SkipFrontend
```

📖 **Full documentation:** [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md)

### Sample Questions

- I want to check if you have the up-to-date information about me.
- Pleae change my address to [any address with street, number, city, postal code, country]
- What products are currently available from your product catalog?
- I want to take an new order with 2 units of [any product from the catalog]
- Send an email to [your real Email address] to confirm my order. 
- Looking at the internal knowledge base, could you tell me [any question for the document you ingested]
- What is the latest news about [the company name you synthesized data from or one of its related brand]?

## How to deploy

### Prerequisites

#### Tool Dependencies
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli): `az` - For Azure resource management
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview): `azd` - For streamlined deployment
- [Python 3.12+](https://www.python.org/downloads/): `python` - Backend runtime
- [UV Package Manager](https://docs.astral.sh/uv/getting-started/installation/): `uv` - Fast Python dependency management
- [Node.js 18+](https://nodejs.org/): `node` and `npm` - Frontend build tools
- Optionally [Docker](https://www.docker.com/get-started/): `docker` - For local container testing

#### Azure Permissions Required

**⚠️ Important**: This deployment requires **subscription-level permissions** due to resource group creation, managed identity provisioning, and role assignments.

The deploying user must have **one of the following** at the subscription level:

1. **Owner role** (Recommended)
   - Full access to create and manage all resources
   - Can assign roles to managed identities

2. **Contributor + User Access Administrator roles**
   - Contributor: Create and manage Azure resources
   - User Access Administrator: Assign roles for managed identity authentication

3. **Custom role** with these specific permissions:
   ```json
   {
     "permissions": [
       {
         "actions": [
           "Microsoft.Resources/subscriptions/resourceGroups/write",
           "Microsoft.Authorization/roleAssignments/write", 
           "Microsoft.Authorization/roleAssignments/read",
           "Microsoft.ManagedIdentity/userAssignedIdentities/*/action",
           "Microsoft.Resources/deployments/*",
           "*"
         ]
       }
     ]
   }
   ```

**Why subscription-level permissions are needed:**
- Creates a new resource group (if not specified)
- Provisions user-assigned managed identity
- Assigns RBAC roles across multiple Azure services (Storage, AI Search, Cosmos DB, Key Vault)
- Deploys infrastructure with subscription-scoped Bicep template

### Deployment and setup

```sh
git clone https://github.com/HaoZhang615/Realtime-Synthetic-Call-Center-Agents.git
cd .\Realtime-Synthetic-Call-Center-Agents\
azd up
```

During the `azd up` process, you will be prompted to decide whether to enable **Zero Trust architecture**. When enabled, all public endpoints (except the AI Foundry/AI Services account) will be disabled for enhanced security.

The deployment process automatically provisions:
- **Azure Container Apps Environment** with optional VNet integration and workload profiles
- **AI Foundry Project** with Bing Search grounding connection
- **MCP Server** for AI Foundry agent integration (internal ingress only)
- **Private networking** with VNet, private endpoints, and DNS zones for backend services (when Zero Trust is enabled)
- **Managed identity** with appropriate RBAC permissions across all services
- **Secure storage** configuration with trusted services access for AI Search indexing
- **Model deployments** for GPT-4o Realtime, GPT-4.1-nano, and text-embedding-3-large

#### Zero Trust Architecture Features

When Zero Trust is enabled during deployment:
- **Private Endpoints**: Azure Storage, Cosmos DB, Azure AI Search, and Key Vault communicate through private endpoints only
- **Network Isolation**: Backend services deny public access and only allow communication through the VNet
- **AI Services Exception**: The AI Foundry/AI Services account maintains public access and key-based authentication to ensure compatibility with AI Search operations
- **Container Apps**: Deployed with VNet integration for secure communication with backend services

Example: initiate deployment
![azd_up_start](docs/images/azdup.png)
Example: successful deployment
![azd_up_final](docs/images/azd_up_final_state.png)


[!NOTE]
>Once deployed, you need to authorise the solution to use your M365 email account for the outbound email capability.
> [Authorise mail access](./docs/mail_authorisation.md)

>[!IMPORTANT]
>**Manual Configuration Required: Bing Search Connection**
>
>After deployment, the Bing Search connection created via Bicep is **not automatically discoverable** by the AI Foundry Agent, which is a current limitation. You must manually recreate the connection in the Azure AI Foundry Portal:
>
>1. Navigate to [Azure AI Foundry Portal](https://ai.azure.com/)
>2. Open your AI Foundry project (e.g., `project-<resourceToken>`)
>3. Go to **Management Center** → **Connected resources**
>4. Delete the existing Bing Search connection
>5. Click **+ New connection** and choose **Grounding with Bing Search**
>6. Choose your existing Bing Search resource (e.g., `bing-<resourceToken>`)
>7. Complete the connection setup
>
>This manual step is required for the **Web Search Agent** to function properly. Without it, web search queries will fail even though the Bing Search resource is deployed and configured.

>[!NOTE]
>AZD will also setup the local Python environment for you, using `venv` and installing the required packages.

## Customization and Iteration

This solution is designed to be easily customizable without requiring complete redeployment of Azure resources:

- To modify and deploy only the frontend components:
  ```sh
  # Make your changes to the frontend code
  azd deploy frontend
  ```

- To modify and deploy only the backend components:
  ```sh
  # Make your changes to the backend code
  azd deploy backend
  ```

These targeted deployments allow for faster development cycles and testing while preserving your Azure resource configuration and data.

Additionally, thanks to Azure Logic Apps' extensive connector ecosystem, the solution offers promising extensibility options. You can easily integrate with hundreds of services and systems such as:
- CRM and business systems (Dynamics 365, Salesforce, etc.)
- Communication platforms (Teams, Slack, SMS)
- Additional database systems
- Enterprise applications and services

This enables you to build complete end-to-end workflows that connect the AI assistant with your existing business processes and data sources without extensive custom coding.

## Local execution

Once the environment has been deployed with `azd up` you can also run the application locally.

Please follow the instructions in [the instructions in `src/frontend`](./src/frontend/README.md)

## Architecture

The solution is built on **Azure Container Apps** with a modern, cloud-native architecture:

### Technology Stack

**Frontend**
- **React 18** with TypeScript for type-safe component development
- **Vite** for fast builds and hot module replacement
- **WebSocket client** for real-time bidirectional communication with Azure OpenAI
- **Tailwind CSS** for responsive UI styling
- Deployed as Azure Container App with NGINX serving

**Backend**
- **FastAPI** REST API framework with async/await support
- **WebSocket server** bridging React frontend to Azure OpenAI Realtime API
- **Python 3.12** with modern type hints and async patterns
- **Uvicorn** ASGI server with auto-reload for development
- Deployed as Azure Container App

**AI Foundry MCP Server** (New in this refactoring)
- **Model Context Protocol (MCP)** server for AI Foundry agent integration
- **Stateless wrapper** for Azure AI Foundry web search agent
- **JSON-RPC 2.0** over HTTP for backend communication
- **Ephemeral threads** for each search request (no state persistence)
- Deployed as internal Azure Container App

**Azure Services**
- **Azure AI Foundry**: Agent orchestration with Bing Search grounding tool
- **Azure OpenAI**: GPT-4o Realtime (voice), GPT-4.1-nano (chat), text-embedding-3-large (embeddings)
- **Azure AI Search**: Hybrid search with semantic ranking and vector indexing
- **Azure Cosmos DB**: NoSQL database for synthetic customer/product/transaction data
- **Azure Storage**: Blob storage for document ingestion with AI Search indexer integration
- **Azure Logic Apps**: Workflow automation for email sending (Office 365 connector)
- **Azure Container Apps**: Serverless container hosting with auto-scaling
- **Azure Key Vault**: Secure secrets management for API keys

### Core Components

#### 1. Frontend (React + TypeScript)

**Key Files:**
- `src/frontend/src/utils/realtimeClient.ts`: WebSocket client for Azure OpenAI Realtime API
- `src/frontend/react-app/pages/chat.tsx`: Main voice chat interface
- `src/frontend/src/components/`: Reusable UI components

**Features:**
- Real-time audio streaming to/from Azure OpenAI
- Visual feedback for active agent and conversation state
- Session configuration (voice selection, turn detection settings)
- Error handling with user-friendly messages

#### 2. Backend (FastAPI)

**Key Files:**
- `src/backend/main.py`: FastAPI application entry point with CORS and routes
- `src/backend/websocket/realtime_handler.py`: WebSocket bridge to Azure OpenAI Realtime API
- `src/backend/services/assistant_service.py`: Multi-agent orchestration service
- `src/backend/routes/`: REST API endpoints (admin, customers, websocket)

**Features:**
- Async WebSocket proxy between React and Azure OpenAI
- Agent routing and tool execution
- Session state management
- Health check and admin endpoints

#### 3. AI Foundry MCP Server

**Key Files:**
- `src/mcp-servers/ai-foundry-agent/main.py`: MCP server implementation
- `src/backend/services/mcp_client.py`: Backend client for MCP communication

**Features:**
- **Tools API**: `/tools/list` and `/tools/call` endpoints
- **Stateless design**: Ephemeral threads created per request
- **Bing grounding**: Built-in Bing Search integration from AI Foundry
- **Product filtering**: Results grounded by company product URLs

#### Multi-Agent System

**1. Root Orchestrator Agent**
- Routes user requests to specialized agents
- Maintains customer context and conversation state
- Handles greetings and conversation closing

**2. Internal Knowledge Base Agent**
- Queries indexed documents via Azure AI Search
- Performs hybrid search (keyword + vector + semantic)
- Returns grounded responses with source citations

**3. Database Agent**
- CRUD operations on Cosmos DB containers
- Customer profile management
- Purchase record creation and retrieval

**4. Web Search Agent (AI Foundry)** ⭐ **NEW**
- **Implementation**: Azure AI Foundry agent with Bing Search tool
- **Architecture**: Stateless MCP server wrapper
- **Grounding**: Filters results by company product URLs from synthetic data
- **Authentication**: Azure managed identity (no API keys required)

**Code Pattern:**
```python
# Backend calls MCP server
async def search_web(self, query: str) -> str:
    response = await self.mcp_client.call_tool(
        tool_name="web_search",
        arguments={"query": query}
    )
    return response["result"]

# MCP server creates ephemeral thread
async def handle_web_search(params: dict) -> str:
    thread = await client.agents.create_thread()
    try:
        # Run AI Foundry agent with Bing tool
        run = await client.agents.create_and_process_run(
            thread_id=thread.id,
            agent_id=agent_id,
            instructions=params["query"]
        )
        return extract_response(run)
    finally:
        await client.agents.delete_thread(thread.id)
```

**5. Executive Assistant Agent**
- Sends emails via Azure Logic Apps
- Summarizes conversations
- Confirms actions with users

### Realtime Multi-Agent Orchestration

**Key Improvements in FastAPI + React Refactoring:**

- **WebSocket Bridge** (`src/backend/websocket/realtime_handler.py`):
  - Owns agent selection and routing logic
  - Emits merged `session.update` payloads when agents switch
  - Caches per-session configuration (voice, turn detection, tools)
  - Ensures browser preferences persist across agent transitions

- **Assistant Service** (`src/backend/services/assistant_service.py`):
  - Centralizes agent registration and management
  - Returns either tool outputs or new session instructions
  - Unit tested for both execution paths (`src/backend/tests/test_assistant_service.py`)

- **React Realtime Client** (`src/frontend/src/utils/realtimeClient.ts`):
  - Listens for `session.updated` events from backend
  - Tracks active agent ID for UI hints
  - Surfaces function call errors via shared error channel

- **Tool Safety**:
  - Time-bound execution with configurable timeouts
  - Structured logging for debugging
  - Graceful fallbacks prevent conversation stalls

### Networking Architecture

The solution supports two deployment modes:

**Standard Deployment (Default):**
- Services use public endpoints with managed identity authentication
- Simplified networking for development and testing scenarios
- Faster deployment and easier troubleshooting

**Zero Trust Deployment (Optional):**
- **Virtual Network**: Dedicated VNet with segregated subnets for apps and backend services
- **Container Apps Environment**: VNet-integrated with workload profiles for enhanced security
- **Private Endpoints**: Secure, private connections to Azure Storage, Cosmos DB, AI Search, and Key Vault
- **Private DNS Zones**: Custom DNS resolution for private endpoint connectivity
- **AI Services Exception**: AI Foundry/AI Services account maintains public access for AI Search skillset compatibility
- **Managed Identity**: User-assigned managed identity for secure, keyless service authentication
- **Internal Communication**: MCP server uses internal `.internal` domain (not exposed to internet)

### Data Flow Diagrams

**Voice Interaction Flow:**
```
User Microphone 
  → React Frontend (WebSocket client)
  → FastAPI Backend (WebSocket proxy)
  → Azure OpenAI Realtime API
  → GPT-4o Realtime Model
  → Response streaming back through WebSocket
  → Browser audio playback
```

**Web Search Flow (AI Foundry):**
```
User: "What's the latest news about Microsoft?"
  → Root Agent (routes to web search)
  → Backend calls MCP server (HTTP POST)
  → MCP server creates ephemeral thread
  → AI Foundry agent executes Bing Search tool
  → Results filtered by product URLs (e.g., microsoft.com)
  → Response returned to user
  → Thread deleted (stateless)
```

**Document Search Flow:**
```
User: "What's in the policy document?"
  → Root Agent (routes to knowledge base)
  → Backend queries Azure AI Search
  → Hybrid search (keyword + vector + semantic)
  → Top-K chunks retrieved with metadata
  → GPT-4.1-nano synthesizes answer
  → Citations included in response
```

**Database Operation Flow:**
```
User: "Update my address to..."
  → Root Agent (routes to database agent)
  → Backend validates customer context
  → Cosmos DB update operation
  → Confirmation returned to user
```

## Architecture Diagram

![Architecture Diagram](./docs/images/architecture.png)

## Contributing

This project welcomes contributions and suggestions. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License. See [LICENSE.md](LICENSE.md) for details.

## Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-studio/)
- [Azure OpenAI Realtime API](https://learn.microsoft.com/azure/ai-services/openai/realtime-audio-quickstart)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [VoiceRAG Pattern](https://techcommunity.microsoft.com/blog/azure-ai-services-blog/voicerag-an-app-pattern-for-rag--voice-using-azure-ai-search-and-the-gpt-4o-real/4259116)

**Inspiration and Credits:**
- [Azure Samples: agentic-voice-assistant](https://github.com/Azure-Samples/agentic-voice-assistant) - Original Streamlit implementation
- [Azure Samples: chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
- [AOAI ContactCenterDemo](https://github.com/HaoZhang615/AOAI_ContactCenterDemo)

## Migration from Legacy Architecture

This project has been **refactored from Streamlit + Chainlit to FastAPI + React**. Key improvements:

| Component | Legacy (Streamlit/Chainlit) | Current (FastAPI/React) |
|-----------|----------------------------|-------------------------|
| **Frontend** | Streamlit (Python-based UI) | React + TypeScript (modern SPA) |
| **Backend** | Chainlit (websocket wrapper) | FastAPI (async REST + WebSocket) |
| **Web Search** | Bing Search V7 API (direct calls) | AI Foundry agent (MCP server wrapper) |
| **Agent Orchestration** | Sequential function calls | Multi-agent service with tool routing |
| **Deployment** | Single container | Multi-container (frontend, backend, MCP server) |
| **Authentication** | API keys in config | Managed identity + Key Vault |
| **Scalability** | Limited by Streamlit | Auto-scaling with Container Apps |

**Benefits of Refactoring:**
- ✅ **Better Performance**: Async FastAPI vs synchronous Streamlit
- ✅ **Type Safety**: TypeScript frontend vs dynamic Python UI
- ✅ **Modern UX**: React components vs Streamlit widgets
- ✅ **Enterprise Ready**: Managed identity, Key Vault, RBAC
- ✅ **Scalable**: Container Apps auto-scaling
- ✅ **Maintainable**: Separation of concerns (frontend/backend/MCP)

## to-do
- [ ] Add demo video
- [ ] Implement conversation logging to Cosmos DB (AI_Conversations container)
- [ ] Add Power BI dashboard integration for post-call analytics
- [ ] Add conversation transcription download feature
- [ ] Implement customer authentication flow
- [ ] Add support for multiple languages in voice interaction