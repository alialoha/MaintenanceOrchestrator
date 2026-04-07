<#
.SYNOPSIS
    Step 3 — start the Flask user UI (port 5000).

    Demo mode works without the MCP server. Live mode needs MCP (script 01) + OPENAI_API_KEY in .env.

.EXAMPLE
    cd secure-agentic-mcp
    .\scripts\03-web.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

# Load .env if present (Flask app also loads it, but this makes MCP_SERVER_URL visible in the banner)
$envFile = Join-Path (Get-Location) ".env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $pair = $_.Split('=', 2)
        $name = $pair[0].Trim()
        $val = $pair[1].Trim().Trim('"')
        [Environment]::SetEnvironmentVariable($name, $val, "Process")
    }
}

. "$PSScriptRoot\common.ps1"
$python = Get-RepoPython
Set-SecureAgenticEnv -ForClients

if (-not $env:FLASK_HOST) { $env:FLASK_HOST = "127.0.0.1" }
if (-not $env:FLASK_PORT) { $env:FLASK_PORT = "5000" }

Show-Banner "Step 3 — User UI (Flask)"
Write-Host "  Command: $python -m web.app"
Write-Host "  Open:    http://127.0.0.1:$($env:FLASK_PORT)/"
Write-Host "  Stop:    Ctrl+C"
Write-Host ""
Show-EnvSummary @("PYTHONPATH", "MCP_DATA_DIR", "MCP_SERVER_URL", "FLASK_HOST", "FLASK_PORT")
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host ""

& $python -m web.app
