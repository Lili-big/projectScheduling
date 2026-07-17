param(
  [string]$PythonPath = ".\.venv\Scripts\python.exe",
  [int]$Port = 8765,
  [int]$StartupTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$dist = Join-Path $repoRoot "04-demo\frontend\dist"
if (-not (Test-Path (Join-Path $dist "index.html"))) {
  throw "04-demo/frontend/dist is missing; run npm.cmd run build first."
}
$python = (Resolve-Path (Join-Path $repoRoot $PythonPath)).Path
$baseUrl = "http://127.0.0.1:$Port"

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $python
$startInfo.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port $Port --app-dir 04-demo/backend"
$startInfo.WorkingDirectory = $repoRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$process = [System.Diagnostics.Process]::Start($startInfo)

try {
  $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  do {
    if ($process.HasExited) { throw "uvicorn exited with code $($process.ExitCode)." }
    try {
      $health = Invoke-WebRequest "$baseUrl/api/health" -UseBasicParsing -TimeoutSec 2
      if ($health.StatusCode -eq 200) { break }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while ([DateTime]::UtcNow -lt $deadline)
  if (-not $health -or $health.StatusCode -ne 200) { throw "health check timed out." }

  $root = Invoke-WebRequest "$baseUrl/" -UseBasicParsing -TimeoutSec 10
  if ($root.StatusCode -ne 200 -or $root.Content -notmatch 'id="root"') { throw "SPA root check failed." }
  $asset = Get-ChildItem (Join-Path $dist "assets") -File | Select-Object -First 1
  if (-not $asset) { throw "04-demo/frontend/dist/assets is empty." }
  $assetResponse = Invoke-WebRequest "$baseUrl/assets/$($asset.Name)" -UseBasicParsing -TimeoutSec 10
  if ($assetResponse.StatusCode -ne 200) { throw "static asset check failed." }
  $fallback = Invoke-WebRequest "$baseUrl/architecture-smoke-route" -UseBasicParsing -TimeoutSec 10
  if ($fallback.StatusCode -ne 200 -or $fallback.Content -notmatch 'id="root"') { throw "SPA fallback check failed." }

  Write-Output "single-service smoke: OK health=200 root=200 asset=200 fallback=200 port=$Port"
} finally {
  if ($process -and -not $process.HasExited) {
    $process.Kill()
    $process.WaitForExit()
  }
}
