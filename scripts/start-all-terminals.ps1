<#
.SYNOPSIS
    Opens three separate PowerShell windows and runs 01 (MCP), 02 (Operator), 03 (Web) in parallel.

.DESCRIPTION
    Stops you from manually opening three terminals and pasting commands. Each window runs one
    numbered script; close that window or Ctrl+C inside it to stop that process only.

    Run from the repo root (or anywhere):
        .\scripts\start-all-terminals.ps1

.EXAMPLE
    .\scripts\start-all-terminals.ps1
#>
$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$s1 = Join-Path $PSScriptRoot "01-mcp-server.ps1"
$s2 = Join-Path $PSScriptRoot "02-operator.ps1"
$s3 = Join-Path $PSScriptRoot "03-web.ps1"

foreach ($p in @($s1, $s2, $s3)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Error "Missing script: $p"
    }
}

$psArgs = @(
    "-NoExit"
    "-ExecutionPolicy", "Bypass"
    "-File"
)

Write-Host "Starting three separate PowerShell windows (MCP -> Operator -> Web)..." -ForegroundColor Green
Write-Host "  Repo: $root"
Write-Host ""

Start-Process -FilePath "powershell.exe" -WorkingDirectory $root -ArgumentList ($psArgs + $s1)
Start-Sleep -Milliseconds 400
Start-Process -FilePath "powershell.exe" -WorkingDirectory $root -ArgumentList ($psArgs + $s2)
Start-Sleep -Milliseconds 400
Start-Process -FilePath "powershell.exe" -WorkingDirectory $root -ArgumentList ($psArgs + $s3)

Write-Host "Done. Three windows should appear; wait for MCP to start before using Operator/Web." -ForegroundColor Cyan
