#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
python -m pip install -r requirements-dev.txt
python -m compileall -q .
python -B verify_full_test_suite.py
(
  cd frontend
  npm ci --no-audit --no-fund
  for f in scripts/verify-*.mjs; do node "$f"; done
  npm run build
)
echo "All local verification steps passed."
