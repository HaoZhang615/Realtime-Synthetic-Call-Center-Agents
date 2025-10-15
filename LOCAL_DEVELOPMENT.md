# Local Development Scripts

Quick-start scripts for running the entire application stack locally.

## 📋 Prerequisites

Before using these scripts, ensure you have:

1. **Python Virtual Environments**:
   ```powershell
   # Backend
   cd src\backend
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   
   # MCP Server
   cd src\mcp-servers\ai-foundry-agent
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

2. **Frontend Dependencies**:
   ```powershell
   cd src\frontend
   npm install
   ```

3. **Environment Variables**:
   - Copy `.azure/RTtest/.env` (or your environment) to `src/backend/.env` for local testing
   - Or ensure Azure credentials are configured

## 🚀 Quick Start

### Option 1: Double-click (Windows)
Simply double-click `start-local-dev.cmd` to start all services.

### Option 2: PowerShell
```powershell
.\start-local-dev.ps1
```

This will open **3 terminal windows**:
1. **MCP Server** - http://localhost:8888
2. **Backend API** - http://localhost:8000
3. **Frontend** - http://localhost:5173

## 🎛️ Advanced Usage

### Start with Custom Ports
```powershell
.\start-local-dev.ps1 -McpPort 9000 -BackendPort 8001 -FrontendPort 3000
```

### Skip Specific Services
```powershell
# Use Azure MCP server instead of local
.\start-local-dev.ps1 -SkipMcp

# Only start frontend (backend already running)
.\start-local-dev.ps1 -SkipMcp -SkipBackend

# Only start MCP and backend
.\start-local-dev.ps1 -SkipFrontend
```

### Stop All Services
```powershell
.\stop-local-dev.ps1
```

Or close each terminal window individually.

## 📊 Service Details

| Service | Default Port | URL | Purpose |
|---------|-------------|-----|---------|
| **Frontend** | 5173 | http://localhost:5173 | React UI (Vite dev server) |
| **Backend** | 8000 | http://localhost:8000 | FastAPI server with realtime WebSocket |
| **MCP Server** | 8888 | http://localhost:8888 | AI Foundry Agent MCP server |

### Service Endpoints

**Backend:**
- API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/api/realtime
- Health: http://localhost:8000/health

**MCP Server:**
- Health: http://localhost:8888/health
- MCP Endpoint: http://localhost:8888/mcp (JSON-RPC 2.0)

**Frontend:**
- Main UI: http://localhost:5173
- Proxies `/api` requests to backend

## 🔧 Troubleshooting

### Port Already in Use
If you see "port already in use" errors:

1. **Check running processes**:
   ```powershell
   Get-NetTCPConnection -LocalPort 8000,8888,5173 | Select OwningProcess | Get-Process
   ```

2. **Stop all services**:
   ```powershell
   .\stop-local-dev.ps1
   ```

3. **Use different ports**:
   ```powershell
   .\start-local-dev.ps1 -BackendPort 8001 -McpPort 8889
   ```

### Virtual Environment Not Found
```powershell
# Recreate backend venv
cd src\backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# Recreate MCP venv
cd src\mcp-servers\ai-foundry-agent
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### MCP Server Connection Failed
If backend shows "MCP connection error":

1. **Check MCP server is running**:
   ```powershell
   curl http://localhost:8888/health
   ```

2. **Check environment variable**:
   - Backend should have `AZURE_AI_FOUNDRY_MCP_URL=http://localhost:8888`
   - The script sets this automatically

3. **Use Azure MCP server instead**:
   ```powershell
   .\start-local-dev.ps1 -SkipMcp
   ```

### Frontend Not Connecting to Backend
1. **Check backend is running**: http://localhost:8000/docs
2. **Check Vite proxy configuration**: `src/frontend/vite.config.ts`
3. **Clear browser cache** and reload

## 🧪 Testing After Startup

Once all services are running:

1. **Open Frontend**: http://localhost:5173
2. **Click "Start Session"** to begin voice chat
3. **Test Web Search**: Ask "What's the weather in Seattle?"
4. **Check Logs**: Look at the terminal windows to see request flow

### Expected Log Flow

**Frontend Console:**
```
Connected to backend WebSocket
Session started
```

**Backend Terminal:**
```
INFO: WebSocket connection established
INFO: MCP Client initialized: base_url=http://localhost:8888
INFO: Executing MCP tool: search_web_ai_foundry
```

**MCP Terminal:**
```
INFO: Received MCP request: method=tools/call
INFO: Executing tool: search_web_ai_foundry
INFO: ✅ Search completed: 456 chars
```

## 📝 Environment Variables

The script automatically sets:
- `AZURE_AI_FOUNDRY_MCP_URL=http://localhost:8888` (for backend)
- `PORT=8888` (for MCP server)

Other required variables should be in:
- `src/backend/.env` (Azure credentials, AI Foundry config)
- `src/mcp-servers/ai-foundry-agent/.env` (AI Foundry config)

## 🔍 Script Internals

### start-local-dev.ps1
1. Checks prerequisites (venvs, node_modules)
2. Opens 3 PowerShell windows
3. Sets environment variables for each service
4. Starts services in order (MCP → Backend → Frontend)
5. Displays startup summary

### stop-local-dev.ps1
1. Finds processes listening on ports 8888, 8000, 5173
2. Kills those processes
3. Confirms shutdown

## 💡 Tips

- **Keep the main script window open** to see the startup summary
- **Each service window** shows its own logs
- **Close any window** to stop that service
- **Use Ctrl+C** in a terminal to gracefully stop
- **Check health endpoints** if something isn't working

## 🚀 Next Steps

After starting services:
- **Develop**: Edit code, servers will auto-reload
- **Debug**: Check logs in each terminal window
- **Test**: Use frontend UI or API docs
- **Deploy**: Run `azd deploy` when ready

---

**Happy coding!** 🎉
