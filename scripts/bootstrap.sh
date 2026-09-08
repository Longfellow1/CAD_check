#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip --isolated install --upgrade pip
python -m pip --isolated install -r requirements.lock.txt
if command -v npm >/dev/null 2>&1; then (cd web && npm install && npm run build); else echo 'WARN: npm not found'; fi
python tools/prepare_demo.py
echo 'READY: ./start.sh'
