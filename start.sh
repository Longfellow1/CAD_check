#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python ]] || { echo '请先运行 ./scripts/bootstrap.sh'; exit 2; }
exec .venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
