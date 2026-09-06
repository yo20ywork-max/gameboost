@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%GameBoost-Stop.ps1"
if errorlevel 1 (
  echo.
  echo GameBoost stop script reported an error. Press any key to close.
  pause >nul
)
