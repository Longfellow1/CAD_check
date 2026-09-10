#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "ERROR: $PYTHON_BIN not found"; exit 2; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required for the Electron MVP'; exit 2; }

"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip --isolated install --upgrade pip
python -m pip --isolated install -r requirements.lock.txt

npm --prefix web install
npm --prefix web run build
npm --prefix desktop install

python tools/prepare_demo.py

echo 'READY: Electron product -> ./start.sh'
echo 'DEBUG ONLY: standalone browser -> ./scripts/start-web-dev.sh'
