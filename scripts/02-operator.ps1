<#
.SYNOPSIS
    Step 2 — start the Gradio Operator (browser UI on port 7860).

    Requires script 01 (MCP server) to be running, or list/call actions will time out.

.EXAMPLE
    cd secure-agentic-mcp
    .\scripts\02-operator.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

. "$PSScriptRoot\common.ps1"
$python = Get-RepoPython
Set-SecureAgenticEnv -ForClients

# Gradio bind address (0.0.0.0 = all interfaces; 127.0.0.1 = local only)
if (-not $env:GRADIO_SERVER_NAME) { $env:GRADIO_SERVER_NAME = "127.0.0.1" }
if (-not $env:GRADIO_SERVER_PORT) { $env:GRADIO_SERVER_PORT = "7860" }

Show-Banner "Step 2 — Operator (Gradio)"
Write-Host "  Command: $python -m mcp_operator.gradio_app"
Write-Host "  Open:    http://127.0.0.1:$($env:GRADIO_SERVER_PORT)/"
Write-Host "  Stop:    Ctrl+C"
Write-Host ""
Show-EnvSummary @("PYTHONPATH", "MCP_DATA_DIR", "MCP_SERVER_URL", "PERMISSIONS_PATH", "GRADIO_SERVER_NAME", "GRADIO_SERVER_PORT")
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host ""

& $python -m mcp_operator.gradio_app
