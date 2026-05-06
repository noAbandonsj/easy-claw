$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    if ($Ok) {
        Write-Host "[正常] $Name - $Detail"
    }
    else {
        Write-Host "[缺失] $Name - $Detail"
    }
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$pyproject = Test-Path -LiteralPath "pyproject.toml"

Write-Check "uv" ([bool]$uv) ($(if ($uv) { $uv.Source } else { "请先安装 uv" }))
Write-Check "git" ([bool]$git) ($(if ($git) { $git.Source } else { "请先安装 Git" }))
Write-Check "pyproject.toml" $pyproject "项目元数据"

if ($uv -and $pyproject) {
    uv run easy-claw doctor
}
