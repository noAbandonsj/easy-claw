param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "uv")) {
    Write-Error "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
}

Write-Host "Syncing dependencies..."
uv sync

Write-Host "Initializing local database..."
uv run easy-claw init-db

Write-Host "Starting easy-claw API at http://$HostAddress`:$Port"
uv run easy-claw serve --host $HostAddress --port $Port
