<#
.SYNOPSIS
Stable allow-list entrypoint for the `list_recog_items` CLI.

.DESCRIPTION
Runs the project CLI through a fixed `powershell.exe -File` script so Codex can
match a stable command prefix in the repository-scoped rules file.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    <#
    .SYNOPSIS
    Resolve the repository root from the script location.

    .OUTPUTS
    System.String
        The absolute path to the repository root.
    #>

    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Invoke-ProjectCli {
    <#
    .SYNOPSIS
    Execute the Python CLI inside the repository root.

    .PARAMETER RepoRoot
    The absolute path to the repository root.
    #>

    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $pythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonPath)) {
        throw "Python executable not found: $pythonPath"
    }

    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONPATH = "eval-harness"

    Push-Location $RepoRoot
    try {
        & $pythonPath -m cli.list_recog_items
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    finally {
        Pop-Location
    }
}

$repoRoot = Get-RepoRoot
Invoke-ProjectCli -RepoRoot $repoRoot
