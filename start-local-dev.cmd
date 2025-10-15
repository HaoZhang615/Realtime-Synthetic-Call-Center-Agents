@echo off
REM Quick launcher for local development
REM Runs start-local-dev.ps1

echo Starting Local Development Environment...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0start-local-dev.ps1" %*

pause
