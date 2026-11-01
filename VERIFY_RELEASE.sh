#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python 3 is required" >&2; exit 2; }
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -c "import flask, werkzeug; print('Flask and Werkzeug imports OK')"
"$PYTHON_BIN" -B buyer_preflight.py
"$PYTHON_BIN" -B verify_payment_route_tests.py
"$PYTHON_BIN" -B verify_full_test_suite.py
PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/libraai-pycache" "$PYTHON_BIN" -m compileall -q .
echo "Local backend checks passed with zero skipped tests. External production gates remain separate; see RELEASE_READINESS_BN.md."
