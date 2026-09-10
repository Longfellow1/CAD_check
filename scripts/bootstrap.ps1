$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

& $Python -m venv .venv
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.lock.txt

npm --prefix web install
npm --prefix web run build
npm --prefix desktop install

& $VenvPython tools\prepare_demo.py
Write-Host "READY: Electron product -> .\start.cmd"
Write-Host "Standalone browser is development-only and is not an MVP acceptance path."
