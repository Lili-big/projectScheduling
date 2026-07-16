[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9._-]+$')]
  [string]$Name,

  [Parameter(Mandatory = $true)]
  [string]$FilePath,

  [string[]]$ArgumentList = @(),

  [string]$WorkingDirectory
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $WorkingDirectory) {
  $WorkingDirectory = $repoRoot
}
$resolvedWorkingDirectory = (Resolve-Path $WorkingDirectory).Path
if (-not $resolvedWorkingDirectory.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "WorkingDirectory must stay inside the repository: $resolvedWorkingDirectory"
}

$session = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$logDirectory = Join-Path $repoRoot ".local-data\logs\$session"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stdout = Join-Path $logDirectory "$Name.out.log"
$stderr = Join-Path $logDirectory "$Name.err.log"

# Some Windows launchers can inject both `Path` and `PATH` into the process
# environment. Start-Process treats environment keys case-insensitively and
# fails before the child starts when both variants are present. Re-register the
# current process path once with the canonical Windows key so the full inherited
# environment is retained without the duplicate.
$processPath = [Environment]::GetEnvironmentVariable("Path", "Process")
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $processPath, "Process")

$process = Start-Process `
  -FilePath $FilePath `
  -ArgumentList $ArgumentList `
  -WorkingDirectory $resolvedWorkingDirectory `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -WindowStyle Hidden `
  -PassThru

[pscustomobject]@{
  Name = $Name
  ProcessId = $process.Id
  StandardOutput = $stdout
  StandardError = $stderr
  WorkingDirectory = $resolvedWorkingDirectory
}
