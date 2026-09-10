@echo off
setlocal
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo ERROR: Python runtime missing. Run powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 first.
  exit /b 2
)

where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm is required to launch CAD Check Electron.
  exit /b 2
)

if not exist web\dist\index.html (
  call npm --prefix web run build || exit /b 1
)

if not exist desktop\node_modules\.bin\electron.cmd (
  call npm --prefix desktop install || exit /b 1
)

set CAD_CHECK_PYTHON=%CD%\.venv\Scripts\python.exe
set CAD_CHECK_PRODUCT_FORM=electron
call npm --prefix desktop start
