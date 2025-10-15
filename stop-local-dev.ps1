#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stop all local development services
    
.DESCRIPTION
    Kills all Python (backend/MCP) and Node (frontend) processes
    running on the development ports.
    
.EXAMPLE
    .\stop-local-dev.ps1
#>

param(
    [int]$McpPort = 8888,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Continue"

Write-Host "`n🛑 Stopping Local Development Services...`n" -ForegroundColor Yellow

# Function to kill process on port
function Stop-ProcessOnPort {
    param(
        [int]$Port,
        [string]$ServiceName
    )
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    
    if ($connections) {
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "  Stopping $ServiceName (PID: $($process.Id))..." -ForegroundColor Cyan
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                Write-Host "  ✅ $ServiceName stopped" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "  ℹ️  $ServiceName not running on port $Port" -ForegroundColor Gray
    }
}

# Stop services
Stop-ProcessOnPort -Port $McpPort -ServiceName "MCP Server"
Stop-ProcessOnPort -Port $BackendPort -ServiceName "Backend API"
Stop-ProcessOnPort -Port $FrontendPort -ServiceName "Frontend"

Write-Host "`n✅ All services stopped!`n" -ForegroundColor Green
