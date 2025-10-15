#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check status of local development services
    
.DESCRIPTION
    Checks if MCP Server, Backend, and Frontend are running
    and displays their status with URLs
#>

param(
    [int]$McpPort = 8888,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

function Test-ServiceStatus {
    param(
        [int]$Port,
        [string]$ServiceName,
        [string]$HealthEndpoint = $null
    )
    
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    
    if ($connection) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "✅ $ServiceName" -ForegroundColor Green -NoNewline
        Write-Host " - Running (PID: $($process.Id))" -ForegroundColor Gray
        Write-Host "   URL: http://localhost:$Port" -ForegroundColor Cyan
        
        # Test health endpoint if provided
        if ($HealthEndpoint) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:$Port$HealthEndpoint" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-Host "   Health: OK" -ForegroundColor Green
                }
            } catch {
                Write-Host "   Health: Failed ($($_.Exception.Message))" -ForegroundColor Yellow
            }
        }
        
        return $true
    } else {
        Write-Host "❌ $ServiceName" -ForegroundColor Red -NoNewline
        Write-Host " - Not running on port $Port" -ForegroundColor Gray
        return $false
    }
}

Write-Host "`n📊 Local Development Services Status`n" -ForegroundColor Magenta

$mcpRunning = Test-ServiceStatus -Port $McpPort -ServiceName "MCP Server    " -HealthEndpoint "/health"
Write-Host ""

$backendRunning = Test-ServiceStatus -Port $BackendPort -ServiceName "Backend API   " -HealthEndpoint "/health"
Write-Host ""

$frontendRunning = Test-ServiceStatus -Port $FrontendPort -ServiceName "Frontend      "
Write-Host ""

# Summary
$runningCount = @($mcpRunning, $backendRunning, $frontendRunning) | Where-Object { $_ } | Measure-Object | Select-Object -ExpandProperty Count
Write-Host "────────────────────────────────────────" -ForegroundColor Gray
Write-Host "Running: $runningCount / 3 services" -ForegroundColor $(if ($runningCount -eq 3) { "Green" } elseif ($runningCount -gt 0) { "Yellow" } else { "Red" })

if ($runningCount -lt 3) {
    Write-Host "`nTo start all services, run: .\start-local-dev.ps1" -ForegroundColor Cyan
}

Write-Host ""
