$ErrorActionPreference = "Stop"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    if ($Ok) {
        Write-Host "[ok] $Name - $Detail"
    }
    else {
        Write-Host "[missing] $Name - $Detail"
    }
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$pyproject = Test-Path -LiteralPath "pyproject.toml"

Write-Check "uv" ([bool]$uv) ($(if ($uv) { $uv.Source } else { "install uv first" }))
Write-Check "git" ([bool]$git) ($(if ($git) { $git.Source } else { "install Git first" }))
Write-Check "pyproject.toml" $pyproject "project metadata"

if ($uv -and $pyproject) {
    uv run easy-claw doctor
}
