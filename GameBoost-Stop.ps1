$ErrorActionPreference = "Stop"
$LogDir = Join-Path $env:LOCALAPPDATA "GameBoost\logs"
$PidPath = Join-Path $LogDir "backend.pid"

if (!(Test-Path -LiteralPath $PidPath)) {
  Write-Host "No GameBoost backend pid file found."
  exit 0
}

$pidText = (Get-Content -LiteralPath $PidPath -ErrorAction Stop | Select-Object -First 1).Trim()
if (!$pidText) {
  Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  Write-Host "Empty pid file removed."
  exit 0
}

$backendProcess = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
if (!$backendProcess) {
  Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  Write-Host "Backend process is not running. Stale pid file removed."
  exit 0
}

Stop-Process -Id $backendProcess.Id -Force
Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
Write-Host "Stopped GameBoost backend process $($backendProcess.Id)."
