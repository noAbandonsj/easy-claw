param(
    [string]$BasicMemoryProjectName = "easy-claw",
    [string]$BasicMemoryPath = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-BasicMemoryProjectPath {
    param([string]$Name)

    $configPath = Join-Path $env:USERPROFILE ".basic-memory\config.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        return $null
    }

    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "无法读取 Basic Memory 配置：$configPath"
        return $null
    }

    if ($null -eq $config.projects) {
        return $null
    }

    $project = @($config.projects.PSObject.Properties | Where-Object { $_.Name -eq $Name })
    if ($project.Count -eq 0) {
        return $null
    }

    return [string]$project[0].Value.path
}

function Resolve-FullPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

if (-not (Test-Command "uvx")) {
    Write-Error "缺少 uvx。请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/"
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($BasicMemoryPath)) {
    $BasicMemoryPath = Join-Path $projectRoot "data\basic-memory"
}

Write-Host "正在配置 MCP..."
Write-Host "当前默认 MCP 服务：Basic Memory"

$memoryDir = New-Item -ItemType Directory -Force -Path $BasicMemoryPath
$resolvedMemoryPath = $memoryDir.FullName
Write-Host "Basic Memory 目录：$resolvedMemoryPath"

$configuredPath = Get-BasicMemoryProjectPath -Name $BasicMemoryProjectName
if ($configuredPath) {
    $configuredFullPath = Resolve-FullPath $configuredPath
    $targetFullPath = Resolve-FullPath $resolvedMemoryPath
    if ($configuredFullPath -ieq $targetFullPath) {
        Write-Host "Basic Memory 项目 '$BasicMemoryProjectName' 已指向当前目录。"
    }
    else {
        Write-Warning "Basic Memory 项目 '$BasicMemoryProjectName' 已存在，路径为：$configuredPath"
        Write-Warning "为避免迁移老用户数据，本脚本不会自动移动已有项目。"
    }
}
else {
    Write-Host "正在创建 Basic Memory 项目 '$BasicMemoryProjectName'..."
    uvx basic-memory project add $BasicMemoryProjectName $resolvedMemoryPath --local
    if ($LASTEXITCODE -ne 0) {
        throw "创建 Basic Memory 项目失败。"
    }
}

$mcpConfig = Join-Path $projectRoot "mcp_servers.json"
$mcpExample = Join-Path $projectRoot "mcp_servers.json.example"
if (-not (Test-Path -LiteralPath $mcpConfig)) {
    Copy-Item -LiteralPath $mcpExample -Destination $mcpConfig
    Write-Host "已创建 MCP 配置：$mcpConfig"
}
else {
    Write-Host "MCP 配置已存在：$mcpConfig"
}

Write-Host "MCP 已配置。后续启动 easy-claw 时会自动加载已配置的 MCP 工具。"
