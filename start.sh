#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

[[ -x .venv/bin/python ]] || { echo 'ERROR: Python runtime missing. Run ./scripts/bootstrap.sh first.'; exit 2; }
command -v npm >/dev/null 2>&1 || { echo 'ERROR: npm is required to launch the Electron desktop app.'; exit 2; }

if [[ ! -f web/dist/index.html ]]; then
  echo '[cad-check] renderer build missing; building web/ for Electron Renderer...'
  npm --prefix web run build
fi

if [[ ! -x desktop/node_modules/.bin/electron ]]; then
  echo '[cad-check] Electron dependencies missing; installing desktop/ dependencies...'
  npm --prefix desktop install
fi

export CAD_CHECK_PYTHON="$ROOT/.venv/bin/python"
export CAD_CHECK_PRODUCT_FORM="electron"
exec npm --prefix desktop start
