param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$ApiServer,
    [switch]$Mcp
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "uv")) {
    Write-Error "缺少 uv。请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/"
}

if ($Mcp) {
    & (Join-Path $PSScriptRoot "setup-mcp.ps1")
}

Write-Host "正在同步依赖..."
uv sync

Write-Host "正在初始化本地数据库..."
uv run easy-claw init-db

if ($ApiServer) {
    Write-Host "正在启动 easy-claw API：http://$HostAddress`:$Port"
    Write-Host "接口文档：http://$HostAddress`:$Port/docs"
    Write-Host "本地聊天页面：http://$HostAddress`:$Port/"
    Write-Host "如需改用交互式 AI 助手，请运行："
    Write-Host "  uv run easy-claw chat --interactive"
    uv run easy-claw serve --host $HostAddress --port $Port
}
else {
    Write-Host ""
    Write-Host "正在启动 easy-claw 交互式聊天..."
    uv run easy-claw chat --interactive
}
