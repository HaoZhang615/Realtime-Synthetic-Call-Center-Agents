# Copilot Instructions for Realtime Synthetic Call Center Agents

These instructions help AI coding agents quickly become productive in this repo by outlining architecture, workflows, and project-specific patterns. Keep changes minimal and consistent with the existing structure.

## Big Picture
- **Stack:** FastAPI backend + React/Vite frontend + AI Foundry MCP server; deployed to Azure Container Apps with supporting services (Cosmos DB, AI Search, Key Vault).
- **Realtime voice:** Browser connects to backend WebSocket, which bridges to Azure OpenAI Realtime for audio/text, and routes tool calls into the multi-agent system.
- **Agents:** Root orchestrator delegates to specialized agents: internal KB, database (Cosmos), web search (via MCP), and email (Logic Apps). See [src/backend/agents](src/backend/agents).
- **Infra:** `azd up` provisions resources described in Bicep under [infra](infra). Optional Zero Trust networking is supported (VNet + private endpoints).

## Developer Workflow
- **Local dev (Windows):** Use scripts in repo root.
  - Start all services: `.
start-local-dev.ps1` → MCP (8888), backend (8000), frontend (5173). Details in [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md).
  - Status/stop: [status-local-dev.ps1](status-local-dev.ps1), [stop-local-dev.ps1](stop-local-dev.ps1).
- **Azure deploy:** `azd up` to provision; targeted deploys with `azd deploy frontend` or `azd deploy backend`.
- **Frontend dev server:** Vite proxies `/api` → backend. See [src/frontend/vite.config.ts](src/frontend/vite.config.ts). Start with `npm run dev` from [src/frontend](src/frontend).
- **Backend dev server:** Uvicorn app at [src/backend/main.py](src/backend/main.py) with routers under [src/backend/routes](src/backend/routes). Start via `uvicorn main:app --reload --port 8000`.

## Realtime Flow & Endpoints
- **Token:** POST `/api/realtime/token` returns AOAI access token and deployment info. See [src/backend/routes/realtime.py](src/backend/routes/realtime.py).
- **WebSocket:** `ws://localhost:8000/api/realtime` handles voice sessions and bridges to Azure OpenAI Realtime. See [src/backend/routes/websocket.py](src/backend/routes/websocket.py).
- **Transcription:** `ws://localhost:8000/api/transcription` is a separate transcription channel (placeholder implementation).
- **Session management:** [voice_session.py](src/backend/websocket/voice_session.py) tracks sessions and logs conversations to Cosmos via [conversation_logger.py](src/backend/services/conversation_logger.py).

## Multi‑Agent Orchestration
- **Root agent:** Provides system instructions and routing; customer context pulled from Cosmos. See [agents/root.py](src/backend/agents/root.py).
- **Tool handling:** Azure Realtime function calls are intercepted server-side in [realtime_handler.py](src/backend/websocket/realtime_handler.py) and executed via `AgentOrchestrator`.
- **MCP client:** Web search uses AI Foundry MCP over JSON‑RPC. HTTP client and retries in [services/mcp_client.py](src/backend/services/mcp_client.py). MCP server health at `http://localhost:8888/health`.

## Data & Services
- **Cosmos DB:** Containers include `Customer`, `Product`, `AI_Conversations`, etc. Access via `DefaultAzureCredential`. Endpoints configured by env vars (e.g., `COSMOSDB_ENDPOINT`, `COSMOSDB_DATABASE`). See [services/conversation_logger.py](src/backend/services/conversation_logger.py) and [agents/root.py](src/backend/agents/root.py).
- **Azure OpenAI:** Realtime deployment and API version configured via env (`AZURE_OPENAI_GPT_REALTIME_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`); endpoint derived from `AZURE_AI_FOUNDRY_ENDPOINT` and converted to `wss://`.
- **Key Vault:** Secrets can be injected locally via `start-local-dev.ps1` by resolving `@Microsoft.KeyVault(SecretUri=...)` references from `azd env get-values`.

## Environment & Conventions
- **Env coordination:** `load_azd_env.py` loads Azure Developer CLI env values into the backend. The local scripts set `AZURE_AI_FOUNDRY_MCP_URL` to backend and `PORT` for MCP.
- **CORS:** Allowed origins configured in [main.py](src/backend/main.py) via `FRONTEND_ORIGINS`. Default includes `http://localhost:5173`.
- **Message tracking:** Azure messages (`response.audio_transcript.done`, `conversation.item.input_audio_transcription.completed`, etc.) are logged to `message_pairs` for post‑session storage.
- **Error handling:** Tool call events (`response.function_call_arguments.done`) are blocked from client and handled server-side; timeouts return function_call_output with error and resume with `response.create`.
- **Python style:** Follow PEP 8 and project docstrings/type hints per [python.instructions.md](.github/instructions/python.instructions.md).

## Common Tasks & Examples
- **Add a new agent tool:** Register in the assistant service and ensure it’s exposed to the root agent’s `tools`. Intercept calls in [realtime_handler.py](src/backend/websocket/realtime_handler.py) and return either `session.update` (agent switch) or `conversation.item.create` outputs.
- **Use MCP search:** Initialize `MCPClient` and call `await client.search_web(query)`. See usage pattern in [services/mcp_client.py](src/backend/services/mcp_client.py).
- **Log conversations:** Ensure `COSMOSDB_*` envs are set; `ConversationLogger` will persist session metadata and titles (via Azure OpenAI if configured). See [conversation_logger.py](src/backend/services/conversation_logger.py).
- **Frontend API calls:** Hit `/api/*` paths; Vite proxy forwards to backend. For WebSocket chat, connect to `/api/realtime` and first fetch session config from `/api/session/config` in [websocket.py](src/backend/routes/websocket.py).

## Notes
- The frontend README in [src/frontend/README.md](src/frontend/README.md) references Chainlit/uv and appears outdated relative to the Vite/React app; prefer root docs and scripts.
- For Azure deployment and networking modes, follow [README.md](README.md) and Bicep in [infra](infra).

If anything above seems unclear or incomplete, tell me what needs refinement (e.g., agent tool registration details, MCP server config, or frontend session setup), and I’ll iterate.
