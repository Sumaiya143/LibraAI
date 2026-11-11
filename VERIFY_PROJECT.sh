#!/usr/bin/env bash
# Reproducible local release gate for Windows-independent development hosts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required." >&2; exit 1; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python 3.10+ is required; Python 3.12+ is recommended." >&2; exit 1; }
node -e 'const major=Number(process.versions.node.split(".")[0]); if(major<20) process.exit(1)' || { echo "Node.js 20+ is required." >&2; exit 1; }
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B project_doctor.py
.venv/bin/python -B buyer_preflight.py
.venv/bin/python -B verify_payment_route_tests.py
.venv/bin/python -B verify_full_test_suite.py
PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/libraai-pycache" .venv/bin/python -m compileall -q .
cd "$ROOT/frontend"
npm ci --no-audit --no-fund
node scripts/verify-lockfile.mjs
for script in scripts/verify-*.mjs; do node "$script"; done
NEXT_TELEMETRY_DISABLED=1 LIBRAAI_BACKEND_URL=http://127.0.0.1:5000 npm run build
printf '\nLocal release checks passed. Live SSL certificates, production database durability, real payment credentials, publisher rights, external AI and independent security review must still be verified in the target deployment.\n'
