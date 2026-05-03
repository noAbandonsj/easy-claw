param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$ApiServer
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

if ($ApiServer) {
    Write-Host "Starting easy-claw API at http://$HostAddress`:$Port"
    uv run easy-claw serve --host $HostAddress --port $Port
    Write-Host ""
    Write-Host "API is running. Swagger docs at http://$HostAddress`:$Port/docs"
    Write-Host "To start the interactive AI assistant, run:"
    Write-Host "  uv run easy-claw chat --interactive"
}
else {
    Write-Host ""
    Write-Host "Starting easy-claw interactive chat..."
    uv run easy-claw chat --interactive
}
