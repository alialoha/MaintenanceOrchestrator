<#
.SYNOPSIS
    Step 0 — show what the numbered scripts will set (no servers started).

.EXAMPLE
    cd secure-agentic-mcp
    .\scripts\00-print-env.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

. "$PSScriptRoot\common.ps1"
$python = Get-RepoPython

Show-Banner "Environment preview (nothing is started yet)"
Write-Host ""
Write-Host "Repo root: $RepoRoot"
Write-Host "Python:    $python"
Write-Host ""
Write-Host "--- MCP server (script 01) would set ---" -ForegroundColor Yellow
Set-SecureAgenticEnv -ForMcpServer
Show-EnvSummary @("PYTHONPATH", "MCP_DATA_DIR")
Write-Host ""
Write-Host "--- Operator / Web (scripts 02 / 03) would add ---" -ForegroundColor Yellow
Set-SecureAgenticEnv -ForClients
Show-EnvSummary @("PYTHONPATH", "MCP_DATA_DIR", "MCP_SERVER_URL", "PERMISSIONS_PATH")
Write-Host ""
Write-Host "Optional: copy .env.example to .env and set OPENAI_API_KEY for AI chat / Live mode."
Write-Host ""
