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
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        $commandText = "$FilePath $($Arguments -join ' ')"
        throw "命令失败（退出码 $LASTEXITCODE）：$commandText"
    }
}

Push-Location -LiteralPath $ProjectRoot
try {
    if (-not (Test-Command "uv")) {
        Write-Error @"
缺少 uv。请先安装 uv 后重新运行本脚本。

Windows 推荐：
  winget install --id=astral-sh.uv -e

如果没有 winget，也可以使用官方安装脚本：
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

安装说明：
  https://docs.astral.sh/uv/getting-started/installation/
"@
    }

    if ($Mcp) {
        & (Join-Path $PSScriptRoot "setup-mcp.ps1")
    }

    Write-Host "正在同步依赖..."
    Invoke-NativeCommand -FilePath "uv" -Arguments @("sync")

    Write-Host "正在初始化本地数据库..."
    Invoke-NativeCommand -FilePath "uv" -Arguments @("run", "easy-claw", "init-db")

    if ($ApiServer) {
        Write-Host "正在启动 easy-claw API：http://$HostAddress`:$Port"
        Write-Host "接口文档：http://$HostAddress`:$Port/docs"
        Write-Host "本地聊天页面：http://$HostAddress`:$Port/"
        Write-Host "如需改用交互式 AI 助手，请运行："
        Write-Host "  uv run easy-claw chat --interactive"
        Invoke-NativeCommand -FilePath "uv" -Arguments @(
            "run",
            "easy-claw",
            "serve",
            "--host",
            $HostAddress,
            "--port",
            [string]$Port
        )
    }
    else {
        Write-Host ""
        Write-Host "正在启动 easy-claw 交互式聊天..."
        Invoke-NativeCommand -FilePath "uv" -Arguments @("run", "easy-claw", "chat", "--interactive")
    }
}
finally {
    Pop-Location
}
