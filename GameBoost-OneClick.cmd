@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%GameBoost-Start.ps1"
if errorlevel 1 (
  echo.
  echo GameBoost failed to start. Press any key to close.
  pause >nul
)
