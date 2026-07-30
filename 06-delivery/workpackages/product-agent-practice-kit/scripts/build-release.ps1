[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolkitRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $toolkitRoot 'toolkit-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($manifest.id -ne 'product-agent-starter-kit') {
    throw "Unexpected toolkit id: $($manifest.id)"
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $toolkitRoot '../../..'))
$stageParent = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.local-data/product-agent-starter-kit-release'))
$stageRoot = [System.IO.Path]::GetFullPath((Join-Path $stageParent $manifest.version))
$releaseRoot = Join-Path $stageRoot $manifest.release_folder
$releaseDirectory = Join-Path $toolkitRoot 'releases'
$archivePath = Join-Path $releaseDirectory "$($manifest.release_folder)-v$($manifest.version).zip"

if (-not $stageRoot.StartsWith($stageParent, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Staging path escapes the allowed root: $stageRoot"
}

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $releaseDirectory | Out-Null

foreach ($relative in $manifest.release_include) {
    $source = Join-Path $toolkitRoot $relative
    $destination = Join-Path $releaseRoot $relative

    if (-not (Test-Path -LiteralPath $source)) {
        throw "Release allowlist entry does not exist: $relative"
    }

    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse
}

Compress-Archive -LiteralPath $releaseRoot -DestinationPath $archivePath -CompressionLevel Optimal -Force

$hash = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
Write-Host "Release archive: $archivePath"
Write-Host "SHA-256: $($hash.Hash.ToLowerInvariant())"

Remove-Item -LiteralPath $stageRoot -Recurse -Force
