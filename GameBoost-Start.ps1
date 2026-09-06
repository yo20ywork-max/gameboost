param(
  [int]$Port = 8080,
  [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSCommandPath
$BackendDir = Join-Path $Root "backend"
$DesktopExe = Join-Path $Root "desktop\dist\GameBoost\GameBoost.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "GameBoost\logs"
$PidPath = Join-Path $LogDir "backend.pid"
$BackendVenv = Join-Path $BackendDir ".venv"
$BackendPython = Join-Path $BackendVenv "Scripts\python.exe"

function Test-Admin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SelfElevated {
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`"",
    "-Port", $Port
  )
  if ($NoLaunch) {
    $arguments += "-NoLaunch"
  }
  Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -Verb RunAs
}

function Find-PythonLauncher {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    try {
      & py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" | Out-Null
      return @{ Command = "py"; Args = @("-3.11") }
    } catch {
    }
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    try {
      & $python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" | Out-Null
      return @{ Command = $python.Source; Args = @() }
    } catch {
    }
  }

  throw "Python 3.11 was not found. Install Python 3.11, then run GameBoost-OneClick.cmd again."
}

function Invoke-LauncherPython {
  param(
    [hashtable]$Launcher,
    [string[]]$Arguments
  )
  & $Launcher.Command @($Launcher.Args + $Arguments)
}

function Test-BackendHealth {
  try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
    return [bool]$response.ok
  } catch {
    return $false
  }
}

function Ensure-BackendEnv {
  if (!(Test-Path -LiteralPath $BackendPython)) {
    Write-Host "Creating backend Python environment..."
    $launcher = Find-PythonLauncher
    Invoke-LauncherPython -Launcher $launcher -Arguments @("-m", "venv", $BackendVenv)
  }

  Write-Host "Installing backend dependencies..."
  & $BackendPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
  if ($LASTEXITCODE -ne 0) {
    throw "Backend dependency installation failed."
  }

  Write-Host "Seeding demo users..."
  & $BackendPython (Join-Path $BackendDir "scripts\seed_demo.py")
  if ($LASTEXITCODE -ne 0) {
    throw "Backend seed failed."
  }
}

function Start-Backend {
  if (Test-BackendHealth) {
    Write-Host "Backend is already running on http://127.0.0.1:$Port"
    return
  }

  $existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Warning "Port $Port is already in use by another process. GameBoost will try to use the existing API."
    return
  }

  Write-Host "Starting backend API..."
  $stdout = Join-Path $LogDir "backend.out.log"
  $stderr = Join-Path $LogDir "backend.err.log"
  $process = Start-Process -FilePath $BackendPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $BackendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru
  Set-Content -LiteralPath $PidPath -Value $process.Id -Encoding ASCII

  for ($i = 0; $i -lt 30; $i++) {
    if (Test-BackendHealth) {
      Write-Host "Backend is ready: http://127.0.0.1:$Port"
      return
    }
    Start-Sleep -Seconds 1
  }

  throw "Backend did not become ready. See logs in $LogDir"
}

function Test-WireGuardInstalled {
  $candidates = @()
  foreach ($base in @($env:ProgramFiles, [Environment]::GetEnvironmentVariable("ProgramFiles(x86)"))) {
    if ($base) {
      $candidates += Join-Path $base "WireGuard\wireguard.exe"
      $candidates += Join-Path $base "WireGuard\wg.exe"
    }
  }
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return $true
    }
  }
  return [bool](Get-Command wireguard.exe -ErrorAction SilentlyContinue)
}

function Start-DesktopApp {
  if (!(Test-Path -LiteralPath $DesktopExe)) {
    throw "GameBoost.exe was not found. Run desktop\package\build_windows.ps1 first."
  }

  if (!(Test-WireGuardInstalled)) {
    Write-Warning "WireGuard for Windows is not installed. Login and route testing can work, but real tunnel connect requires WireGuard."
    Write-Warning "Install it from: https://www.wireguard.com/install/"
  }

  Write-Host "Launching GameBoost desktop app..."
  Start-Process -FilePath $DesktopExe -WorkingDirectory (Split-Path -Parent $DesktopExe)
}

if (!(Test-Admin)) {
  Write-Host "Requesting Administrator permission..."
  Invoke-SelfElevated
  exit 0
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

Write-Host "GameBoost one-click startup"
Write-Host "Project: $Root"

Ensure-BackendEnv
Start-Backend

if (!$NoLaunch) {
  Start-DesktopApp
}

Write-Host "Done."
