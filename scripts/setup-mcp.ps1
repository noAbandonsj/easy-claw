param(
    [string]$BasicMemoryProjectName = "easy-claw",
    [string]$BasicMemoryPath = "",
    [string]$RepositoryPath = ""
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

function Import-DotEnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        $equalsIndex = $trimmed.IndexOf("=")
        if ($equalsIndex -le 0) {
            continue
        }

        $name = $trimmed.Substring(0, $equalsIndex).Trim()
        $value = $trimmed.Substring($equalsIndex + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, "Process"))) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Get-ProcessEnvValue {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $null
    }
    return $value
}

function Read-McpConfig {
    param([string]$Path)

    $config = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $config
    }

    try {
        $raw = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    }
    catch {
        throw "无法读取 MCP 配置：$Path"
    }

    if ($null -eq $raw) {
        return $config
    }

    foreach ($property in $raw.PSObject.Properties) {
        $config[$property.Name] = $property.Value
    }
    return $config
}

function Merge-McpConfig {
    param(
        [System.Collections.Specialized.OrderedDictionary]$Existing,
        [System.Collections.Specialized.OrderedDictionary]$DefaultServers
    )

    $merged = [ordered]@{
        "_comment" = "easy-claw 的本机 MCP 配置。由 scripts\setup-mcp.ps1 生成，可按需手动调整。"
    }

    foreach ($key in $Existing.Keys) {
        if ($key -eq "_comment") {
            continue
        }
        $merged[$key] = $Existing[$key]
    }

    foreach ($key in $DefaultServers.Keys) {
        $merged[$key] = $DefaultServers[$key]
    }

    return $merged
}

function New-DefaultMcpServers {
    param(
        [string]$MemoryProjectName,
        [string]$RepoPath
    )

    $servers = [ordered]@{
        "basic-memory" = [ordered]@{
            "command" = "uvx"
            "args" = @("basic-memory", "mcp", "--project", $MemoryProjectName)
            "transport" = "stdio"
        }
        "git" = [ordered]@{
            "command" = "uvx"
            "args" = @("mcp-server-git", "--repository", $RepoPath)
            "transport" = "stdio"
        }
    }

    if (Get-ProcessEnvValue "GITHUB_PERSONAL_ACCESS_TOKEN") {
        $servers["github"] = [ordered]@{
            "transport" = "http"
            "url" = "https://api.githubcopilot.com/mcp/"
            "headers" = [ordered]@{
                "Authorization" = "Bearer `${GITHUB_PERSONAL_ACCESS_TOKEN}"
            }
        }
    }
    else {
        Write-Warning "未设置 GITHUB_PERSONAL_ACCESS_TOKEN，跳过 GitHub MCP。"
    }

    if (Get-ProcessEnvValue "AMAP_MAPS_API_KEY") {
        if (Test-Command "npx") {
            $servers["amap-maps"] = [ordered]@{
                "command" = "npx"
                "args" = @("-y", "@amap/amap-maps-mcp-server")
                "transport" = "stdio"
                "env" = [ordered]@{
                    "AMAP_MAPS_API_KEY" = "`${AMAP_MAPS_API_KEY}"
                }
            }
        }
        else {
            Write-Warning "已设置 AMAP_MAPS_API_KEY，但缺少 npx，跳过高德地图 MCP。"
        }
    }
    else {
        Write-Warning "未设置 AMAP_MAPS_API_KEY，跳过高德地图 MCP。"
    }

    return $servers
}

if (-not (Test-Command "uvx")) {
    Write-Error "缺少 uvx。请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/"
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Import-DotEnvFile -Path (Join-Path $projectRoot ".env")

if ([string]::IsNullOrWhiteSpace($BasicMemoryPath)) {
    $BasicMemoryPath = Join-Path $projectRoot "data\basic-memory"
}
if ([string]::IsNullOrWhiteSpace($RepositoryPath)) {
    $RepositoryPath = $projectRoot
}
$resolvedRepositoryPath = Resolve-FullPath $RepositoryPath

Write-Host "正在配置 MCP..."
Write-Host "当前默认 MCP 服务：Basic Memory、Git；配置了密钥时启用 GitHub 和高德地图。"

$memoryDir = New-Item -ItemType Directory -Force -Path $BasicMemoryPath
$resolvedMemoryPath = $memoryDir.FullName
Write-Host "Basic Memory 目录：$resolvedMemoryPath"
Write-Host "Git MCP 仓库目录：$resolvedRepositoryPath"

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
$hadMcpConfig = Test-Path -LiteralPath $mcpConfig
$existingConfig = Read-McpConfig -Path $mcpConfig
$defaultServers = New-DefaultMcpServers -MemoryProjectName $BasicMemoryProjectName -RepoPath $resolvedRepositoryPath
$mergedConfig = Merge-McpConfig -Existing $existingConfig -DefaultServers $defaultServers
$mergedConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $mcpConfig -Encoding utf8

if (-not $hadMcpConfig) {
    Write-Host "已创建 MCP 配置：$mcpConfig"
}
else {
    Write-Host "已更新 MCP 配置：$mcpConfig"
}

Write-Host "MCP 已配置。后续启动 easy-claw 时会自动加载已配置的 MCP 工具。"
