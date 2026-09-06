$ErrorActionPreference = "Stop"

$Root = Resolve-Path ".."
Set-Location $Root

if (Test-Path ".venv") {
  try {
    .\.venv\Scripts\python.exe -m PyInstaller --version | Out-Null
  } catch {
    Write-Host "Existing .venv looks broken. Recreating it..."
    Remove-Item -LiteralPath ".venv" -Recurse -Force
  }
}

if (!(Test-Path ".venv")) {
  py -3.11 -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .

python -m PyInstaller --noconfirm --clean package\gameboost.spec

Write-Host "PyInstaller build finished: dist\GameBoost\GameBoost.exe"

$Inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $Inno) {
  & $Inno package\inno_setup.iss
  Write-Host "Installer created in desktop\installer-output"
} else {
  Write-Host "Inno Setup not found. Install Inno Setup 6 to build setup.exe."
}
