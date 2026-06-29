<#
.SYNOPSIS
Stable allow-list entrypoint for reading CodeBuddy documentation pages.

.DESCRIPTION
Fetches a CodeBuddy documentation page through a fixed `powershell.exe -File`
script so Codex can match a stable command prefix in the repository-scoped
rules file. The script is intentionally read-only and only allows HTTPS URLs
under the official `/docs/` path.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Uri
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-CodeBuddyDocsUri {
    <#
    .SYNOPSIS
    Normalize and validate the target CodeBuddy documentation URL.

    .DESCRIPTION
    Accepts either a full HTTPS URL or a relative docs path, then validates
    that the final target stays on the official CodeBuddy docs host and under
    the `/docs/` prefix. This keeps the allow-list entry scoped to the
    intended read-only documentation use case.

    .PARAMETER RawUri
    The user-provided URL or relative documentation path.

    .OUTPUTS
    System.Uri
        A normalized HTTPS URI pointing to `https://www.codebuddy.ai/docs/...`.
    #>

    param(
        [Parameter(Mandatory = $true)]
        [string]$RawUri
    )

    $trimmedUri = $RawUri.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmedUri)) {
        throw "The documentation URI cannot be empty."
    }

    $candidateUri = $null
    if ([System.Uri]::TryCreate($trimmedUri, [System.UriKind]::Absolute, [ref]$candidateUri)) {
        if ($candidateUri.Scheme -ne "https") {
            throw "Only HTTPS documentation URLs are allowed."
        }
    }
    else {
        $relativePath = $trimmedUri
        if (-not $relativePath.StartsWith("/")) {
            $relativePath = "/$relativePath"
        }

        if (($relativePath -ne "/docs") -and (-not $relativePath.StartsWith("/docs/", [System.StringComparison]::OrdinalIgnoreCase))) {
            $relativePath = "/docs/$($relativePath.TrimStart('/'))"
        }

        $candidateUri = [System.Uri]::new("https://www.codebuddy.ai$relativePath")
    }

    $allowedHosts = @("www.codebuddy.ai", "codebuddy.ai")
    if ($allowedHosts -notcontains $candidateUri.Host) {
        throw "Only official CodeBuddy hosts are allowed."
    }

    $absolutePath = $candidateUri.AbsolutePath
    if (($absolutePath -ne "/docs") -and (-not $absolutePath.StartsWith("/docs/", [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Only CodeBuddy documentation pages under /docs/ are allowed."
    }

    return $candidateUri
}

function Get-CodeBuddyDocsPage {
    <#
    .SYNOPSIS
    Download the HTML source of a CodeBuddy documentation page.

    .DESCRIPTION
    Uses `Invoke-WebRequest -UseBasicParsing` to fetch the documentation page
    and returns the response body as plain text so downstream tools can inspect
    the raw page content without any local file writes.

    .PARAMETER TargetUri
    The validated CodeBuddy documentation URI to fetch.

    .OUTPUTS
    System.String
        The HTML content returned by the documentation page.
    #>

    param(
        [Parameter(Mandatory = $true)]
        [System.Uri]$TargetUri
    )

    $response = Invoke-WebRequest -UseBasicParsing -Uri $TargetUri.AbsoluteUri
    return $response.Content
}

$resolvedUri = Resolve-CodeBuddyDocsUri -RawUri $Uri
$pageContent = Get-CodeBuddyDocsPage -TargetUri $resolvedUri
Write-Output $pageContent
