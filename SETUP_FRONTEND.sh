#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/frontend"
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required." >&2; exit 1; }
if [ ! -f package-lock.json ]; then
  echo "Generating initial package-lock.json (internet required once)..."
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund
fi
if [ ! -d node_modules ]; then
  npm ci --no-audit --no-fund
else
  if ! npm ls --depth=0 >/dev/null 2>&1; then npm ci --no-audit --no-fund; fi
fi
node scripts/verify-lockfile.mjs
npm run verify:shell
npm run verify:security-headers
npm run verify:integrations
printf '
Frontend dependencies and static checks are ready.
'
printf 'Commit frontend/package-lock.json to keep future installs reproducible.
'
