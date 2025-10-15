#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start all services for local development testing
    
.DESCRIPTION
    This script starts the following services in separate terminal windows:
    1. AI Foundry MCP Server (port 8888)
    2. Backend API (port 8000)
    3. Frontend Dev Server (port 5173)
    
.EXAMPLE
    .\start-local-dev.ps1
    
.EXAMPLE
    .\start-local-dev.ps1 -SkipMcp
    Start only backend and frontend (use Azure MCP server)
    
.NOTES
    Requirements:
    - Python virtual environments must exist in:
      - src/backend/.venv
      - src/mcp-servers/ai-foundry-agent/.venv
    - Node modules must be installed in src/frontend
#>

param(
    [switch]$SkipMcp,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [int]$McpPort = 8888,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Colors for output
function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host "`n$('=' * 70)" -ForegroundColor Magenta
    Write-Host "  $Message" -ForegroundColor Magenta
    Write-Host "$('=' * 70)`n" -ForegroundColor Magenta
}

# Verify prerequisites
function Test-Prerequisites {
    Write-Header "Checking Prerequisites"
    
    $allGood = $true
    
    # Check MCP virtual environment
    if (-not $SkipMcp) {
        $mcpVenvPath = Join-Path $ScriptDir "src\mcp-servers\ai-foundry-agent\.venv"
        if (-not (Test-Path $mcpVenvPath)) {
            Write-Error "MCP virtual environment not found: $mcpVenvPath"
            Write-Info "Create it with: cd src\mcp-servers\ai-foundry-agent; python -m venv .venv"
            $allGood = $false
        } else {
            Write-Success "MCP virtual environment found"
        }
    }
    
    # Check Backend virtual environment
    if (-not $SkipBackend) {
        $backendVenvPath = Join-Path $ScriptDir "src\backend\.venv"
        if (-not (Test-Path $backendVenvPath)) {
            Write-Error "Backend virtual environment not found: $backendVenvPath"
            Write-Info "Create it with: cd src\backend; python -m venv .venv"
            $allGood = $false
        } else {
            Write-Success "Backend virtual environment found"
        }
    }
    
    # Check Frontend node_modules
    if (-not $SkipFrontend) {
        $frontendNodeModules = Join-Path $ScriptDir "src\frontend\node_modules"
        if (-not (Test-Path $frontendNodeModules)) {
            Write-Error "Frontend node_modules not found: $frontendNodeModules"
            Write-Info "Install with: cd src\frontend; npm install"
            $allGood = $false
        } else {
            Write-Success "Frontend node_modules found"
        }
    }
    
    if (-not $allGood) {
        Write-Error "`nPrerequisites check failed. Please fix the issues above.`n"
        exit 1
    }
    
    Write-Success "All prerequisites satisfied!`n"
}

# Start MCP Server
function Start-McpServer {
    if ($SkipMcp) {
        Write-Warning "Skipping MCP Server (will use Azure deployment)"
        return
    }
    
    Write-Header "Starting AI Foundry MCP Server"
    
    $mcpDir = Join-Path $ScriptDir "src\mcp-servers\ai-foundry-agent"
    $mcpVenv = Join-Path $mcpDir ".venv\Scripts\python.exe"
    
    Write-Info "Port: $McpPort"
    Write-Info "Directory: $mcpDir"
    
    # Start in new PowerShell window
    $mcpCommand = @"
`$host.ui.RawUI.WindowTitle = 'AI Foundry MCP Server - Port $McpPort'
cd '$mcpDir'
`$env:PORT = '$McpPort'
Write-Host '🚀 Starting AI Foundry MCP Server on port $McpPort...' -ForegroundColor Green
Write-Host 'URL: http://localhost:$McpPort' -ForegroundColor Cyan
Write-Host 'Health: http://localhost:$McpPort/health' -ForegroundColor Cyan
Write-Host ''
& '$mcpVenv' main.py
Write-Host ''
Write-Host '❌ MCP Server stopped. Press any key to close...' -ForegroundColor Red
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@
    
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", $mcpCommand
    Write-Success "MCP Server terminal opened"
    Start-Sleep -Seconds 2  # Give it time to start
}

# Start Backend
function Start-Backend {
    if ($SkipBackend) {
        Write-Warning "Skipping Backend Server"
        return
    }
    
    Write-Header "Starting Backend API"
    
    $backendDir = Join-Path $ScriptDir "src\backend"
    $backendVenv = Join-Path $backendDir ".venv\Scripts\python.exe"
    $mcpUrl = if ($SkipMcp) { 
        "https://ca-aifoundry-mcp-y76cngbvoa5e4.internal.salmonriver-934e57a9.swedencentral.azurecontainerapps.io"
    } else { 
        "http://localhost:$McpPort" 
    }
    
    Write-Info "Port: $BackendPort"
    Write-Info "Directory: $backendDir"
    Write-Info "MCP Server: $mcpUrl"
    
    # Start in new PowerShell window
    $backendCommand = @"
`$host.ui.RawUI.WindowTitle = 'Backend API - Port $BackendPort'
cd '$backendDir'
`$env:AZURE_AI_FOUNDRY_MCP_URL = '$mcpUrl'
Write-Host '🚀 Starting Backend API on port $BackendPort...' -ForegroundColor Green
Write-Host 'URL: http://localhost:$BackendPort' -ForegroundColor Cyan
Write-Host 'API Docs: http://localhost:$BackendPort/docs' -ForegroundColor Cyan
Write-Host 'MCP URL: $mcpUrl' -ForegroundColor Yellow
Write-Host ''
& '$backendVenv' -m uvicorn main:app --reload --port $BackendPort
Write-Host ''
Write-Host '❌ Backend stopped. Press any key to close...' -ForegroundColor Red
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@
    
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", $backendCommand
    Write-Success "Backend terminal opened"
    Start-Sleep -Seconds 3  # Give it time to start
}

# Start Frontend
function Start-Frontend {
    if ($SkipFrontend) {
        Write-Warning "Skipping Frontend Server"
        return
    }
    
    Write-Header "Starting Frontend Dev Server"
    
    $frontendDir = Join-Path $ScriptDir "src\frontend"
    
    Write-Info "Port: $FrontendPort"
    Write-Info "Directory: $frontendDir"
    Write-Info "Backend Proxy: http://localhost:$BackendPort"
    
    # Start in new PowerShell window
    $frontendCommand = @"
`$host.ui.RawUI.WindowTitle = 'Frontend - Port $FrontendPort'
cd '$frontendDir'
Write-Host '🚀 Starting Frontend Dev Server on port $FrontendPort...' -ForegroundColor Green
Write-Host 'URL: http://localhost:$FrontendPort' -ForegroundColor Cyan
Write-Host 'Backend: http://localhost:$BackendPort' -ForegroundColor Yellow
Write-Host ''
npm run dev
Write-Host ''
Write-Host '❌ Frontend stopped. Press any key to close...' -ForegroundColor Red
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@
    
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", $frontendCommand
    Write-Success "Frontend terminal opened"
    Start-Sleep -Seconds 2
}

# Main execution
function Main {
    Write-Header "🚀 Starting Local Development Environment"
    
    Write-Info "Configuration:"
    if (-not $SkipMcp) { Write-Info "  MCP Server: http://localhost:$McpPort" }
    if (-not $SkipBackend) { Write-Info "  Backend API: http://localhost:$BackendPort" }
    if (-not $SkipFrontend) { Write-Info "  Frontend: http://localhost:$FrontendPort" }
    Write-Host ""
    
    # Check prerequisites
    Test-Prerequisites
    
    # Start services in order
    if (-not $SkipMcp) {
        Start-McpServer
    }
    
    if (-not $SkipBackend) {
        Start-Backend
    }
    
    if (-not $SkipFrontend) {
        Start-Frontend
    }
    
    # Final summary
    Write-Header "🎉 All Services Started!"
    
    Write-Success "Development environment is ready!"
    Write-Host ""
    Write-Info "Access your application at: http://localhost:$FrontendPort"
    Write-Info "Backend API docs: http://localhost:$BackendPort/docs"
    if (-not $SkipMcp) {
        Write-Info "MCP Server health: http://localhost:$McpPort/health"
    }
    Write-Host ""
    Write-Info "To stop all services, close each terminal window."
    Write-Info "Or press Ctrl+C in each terminal."
    Write-Host ""
    Write-Warning "Keep this window open to see the startup summary."
    Write-Host ""
}

# Run main
Main
