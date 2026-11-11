#!/usr/bin/env bash
# One-command local development launcher for the Flask API and Next.js UI.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required." >&2; exit 1; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python 3.10+ is required; Python 3.12+ is recommended." >&2; exit 1; }
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B project_doctor.py
backend_pid=''
cleanup() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
LIBRAAI_ENV=development .venv/bin/python app.py &
backend_pid=$!
for attempt in $(seq 1 45); do
  if "$PYTHON_BIN" -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:5000/api/ready", timeout=1).read()' >/dev/null 2>&1; then break; fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Backend exited before becoming ready. Check the backend error above." >&2
    exit 1
  fi
  if [[ "$attempt" -eq 45 ]]; then echo "Backend readiness timed out at http://127.0.0.1:5000/api/ready" >&2; exit 1; fi
  sleep 1
done
cd "$ROOT/frontend"
if [[ ! -f package-lock.json ]]; then
  echo "frontend/package-lock.json is missing; restore the committed lockfile before running npm ci." >&2
  exit 1
fi
if [[ ! -d node_modules ]] || ! npm ls --depth=0 >/dev/null 2>&1; then npm ci --no-audit --no-fund; fi
node scripts/verify-lockfile.mjs
npm run verify:shell
npm run verify:security-headers
npm run verify:integrations
printf '
LibraAI backend ready at http://127.0.0.1:5000
'
printf 'Starting Next.js at http://localhost:3000 (Ctrl+C stops both services).
'
npm run dev
