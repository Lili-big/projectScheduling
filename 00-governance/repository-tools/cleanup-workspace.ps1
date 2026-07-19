[CmdletBinding()]
param(
    [switch]$Apply,
    [ValidateSet('diagnostic-log', 'rebuildable', 'cache', 'temporary')]
    [string[]]$Category,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ProtectedClasses = @('persistent-state', 'user-input', 'formal-output')
$Definitions = @(
    [pscustomobject]@{ Category = 'diagnostic-log'; Path = '.local-data/logs/legacy-unclassified'; Measure = $true },
    [pscustomobject]@{ Category = 'rebuildable'; Path = '.local-data/archive/rebuildable'; Measure = $true },
    [pscustomobject]@{ Category = 'cache'; Path = '.local-data/cache'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.codex-tmp'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.edge-profile'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.netlify'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.netlify-cli-runtime'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.npm-cache'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.npm-cache-netlify-deploy'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.pip-cache'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.playwright-cli'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.skill-build'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = '.venv'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = 'node_modules'; Measure = $false },
    [pscustomobject]@{ Category = 'cache'; Path = 'outputs/lugu-validation-20260715'; Measure = $false },
    [pscustomobject]@{ Category = 'temporary'; Path = '.local-data/tmp'; Measure = $true },
    [pscustomobject]@{ Category = 'temporary'; Path = '.local-data/locks'; Measure = $true },
    [pscustomobject]@{ Category = 'temporary'; Path = '.netlify-deploy-staging'; Measure = $false },
    [pscustomobject]@{ Category = 'temporary'; Path = '.git-tmp-projectScheduling'; Measure = $false }
)

if ($Apply -and (-not $Category -or $Category.Count -eq 0)) {
    throw 'Apply mode requires at least one explicit non-protected -Category.'
}

if ($Apply -and (@($Category | Where-Object { $_ -in @('diagnostic-log', 'temporary') }).Count -gt 0)) {
    $Ports = @(3000, 4173, 5000, 5173, 8000, 8080, 8888)
    $Listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in $Ports })
    if ($Listeners.Count -gt 0) {
        throw 'Standard development ports are active; log or temporary cleanup is refused.'
    }
}

$Candidates = @()
foreach ($Definition in $Definitions) {
    $AbsolutePath = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot $Definition.Path))
    if (-not $AbsolutePath.StartsWith([System.IO.Path]::GetFullPath($RepositoryRoot), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Candidate path escapes the repository: $($Definition.Path)"
    }
    if (-not (Test-Path -LiteralPath $AbsolutePath)) {
        continue
    }
    $Item = Get-Item -LiteralPath $AbsolutePath -Force
    $FileCount = $null
    $SizeBytes = $null
    if (-not $Item.PSIsContainer) {
        $FileCount = 1
        $SizeBytes = [int64]$Item.Length
    }
    elseif ($Definition.Measure) {
        $Files = @(Get-ChildItem -LiteralPath $AbsolutePath -File -Recurse -Force -ErrorAction SilentlyContinue)
        $FileCount = $Files.Count
        $SizeBytes = [int64](($Files | Measure-Object -Property Length -Sum).Sum)
    }
    $Candidates += [pscustomobject]@{
        category = $Definition.Category
        path = $Definition.Path
        kind = if ($Item.PSIsContainer) { 'directory' } else { 'file' }
        file_count = $FileCount
        size_bytes = $SizeBytes
        protected = $false
    }
}

$DeletedCount = 0
if ($Apply) {
    foreach ($Candidate in @($Candidates | Where-Object { $_.category -in $Category })) {
        $AbsolutePath = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot $Candidate.path))
        $ProtectedRoots = @(
            [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot '.local-data/state')),
            [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot '01-customer-validation')),
            [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot '03-requirements')),
            [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot '06-delivery'))
        )
        if (@($ProtectedRoots | Where-Object { $AbsolutePath.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) {
            throw "Candidate intersects a protected root: $($Candidate.path)"
        }
        Remove-Item -LiteralPath $AbsolutePath -Recurse -Force
        $DeletedCount += 1
    }
}

$KnownLocalTop = @('README.md', 'state', 'logs', 'cache', 'tmp', 'locks', 'archive')
$Unknown = @(
    Get-ChildItem -LiteralPath (Join-Path $RepositoryRoot '.local-data') -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin $KnownLocalTop } |
        Select-Object -ExpandProperty Name
)
$CategoryCounts = @{}
foreach ($Name in @('diagnostic-log', 'rebuildable', 'cache', 'temporary')) {
    $CategoryCounts[$Name] = @($Candidates | Where-Object { $_.category -eq $Name }).Count
}
$KnownSizes = @($Candidates | Where-Object { $null -ne $_.size_bytes })
$Report = [ordered]@{
    mode = if ($Apply) { 'apply' } else { 'dry-run' }
    selected_categories = @($Category | Where-Object { $_ })
    protected_classes = $ProtectedClasses
    candidate_count = $Candidates.Count
    category_counts = $CategoryCounts
    total_known_bytes = [int64](($KnownSizes | Measure-Object -Property size_bytes -Sum).Sum)
    size_unknown_count = @($Candidates | Where-Object { $null -eq $_.size_bytes }).Count
    protected_candidate_count = @($Candidates | Where-Object { $_.protected }).Count
    unknown_count = $Unknown.Count
    unknown = $Unknown
    deleted_count = $DeletedCount
    candidates = $Candidates
}

if ($Json) {
    $Report | ConvertTo-Json -Depth 6 -Compress
}
else {
    $Report | ConvertTo-Json -Depth 6
}
