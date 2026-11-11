#!/usr/bin/env bash
# Start the Flask backend for local development using an isolated project venv.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python 3.10+ is required; Python 3.12+ is recommended." >&2; exit 1; }
if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B project_doctor.py
exec .venv/bin/python app.py
