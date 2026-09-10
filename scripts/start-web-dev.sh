#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cat <<'EOF'
============================================================
CAD Check standalone Web DEBUG mode
NOT PRODUCT / NOT DEMO / NOT MVP ACCEPTANCE
Use ./start.sh for the Electron product.
============================================================
EOF

[[ -x .venv/bin/python ]] || { echo 'ERROR: run ./scripts/bootstrap.sh first'; exit 2; }
exec .venv/bin/python -m uvicorn server.app_v2:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
