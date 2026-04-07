<#
.SYNOPSIS
    Step 1 — start the FastMCP HTTP server (listen on port 8000, path /mcp).

    Run this FIRST in its own terminal. Leave it running.
    Then open another terminal for 02-operator.ps1 or 03-web.ps1.

.EXAMPLE
    cd secure-agentic-mcp
    .\scripts\01-mcp-server.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

. "$PSScriptRoot\common.ps1"
$python = Get-RepoPython
Set-SecureAgenticEnv -ForMcpServer

Show-Banner "Step 1 — MCP HTTP server"
Write-Host "  Command: $python -m mcp_server"
Write-Host "  MCP URL (clients): http://127.0.0.1:8000/mcp"
Write-Host "  Browser status: http://127.0.0.1:8000/  (do not use http://0.0.0.0/ in a browser)"
Write-Host "  Stop:    Ctrl+C in this window"
Write-Host ""
Show-EnvSummary @("PYTHONPATH", "MCP_DATA_DIR")
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host ""
Show-Banner "For inqueries contact: ali.mousavi.contact@gmail.com"


& $python -m mcp_server
