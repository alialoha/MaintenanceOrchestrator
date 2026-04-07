# Shared settings for all secure-agentic-mcp runners.
# Dot-source this file from the repo root OR from scripts/:
#   . .\scripts\common.ps1
#   Set-SecureAgenticEnv -ForMcpServer
#
# Nothing runs a server by itself — it only sets paths and env vars.

# Caller scope (when dot-sourced) so 00-print-env.ps1 can print $RepoRoot.
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-RepoPython {
    $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        return $venvPy
    }
    Write-Warning "No .venv found; using 'python' from PATH. Create a venv: python -m venv .venv"
    return "python"
}

<#
.SYNOPSIS
    Sets PYTHONPATH, MCP_DATA_DIR, and optional client vars.

.PARAMETER ForMcpServer
    Only what the FastMCP HTTP process needs (no MCP_SERVER_URL).

.PARAMETER ForClients
    Adds MCP_SERVER_URL and PERMISSIONS_PATH for Gradio / Flask.
#>
function Set-SecureAgenticEnv {
    param(
        [switch]$ForMcpServer,
        [switch]$ForClients
    )
    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    $env:MCP_DATA_DIR = Join-Path $RepoRoot "data"
    $env:PERMISSIONS_PATH = Join-Path $RepoRoot "data\permissions.json"

    if ($ForClients) {
        if (-not $env:MCP_SERVER_URL) {
            $env:MCP_SERVER_URL = "http://127.0.0.1:8000"
        }
    }
}

function Show-Banner {
    param([string]$Title)
    $sep = "=" * 64
    Write-Host ""
    Write-Host $sep -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host $sep -ForegroundColor Cyan
}

function Show-EnvSummary {
    param([string[]]$Keys)
    foreach ($k in $Keys) {
        $v = [Environment]::GetEnvironmentVariable($k, "Process")
        if ($null -eq $v) { $v = "(unset)" }
        Write-Host ("  {0,-18} {1}" -f ($k + ":"), $v)
    }
}
