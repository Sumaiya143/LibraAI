#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Engine and Docker Compose plugin are required." >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  cp .env.production.example .env
  echo "Created .env from template. Edit it, set your domain and a unique SECRET_KEY, then rerun." >&2
  exit 2
fi
if grep -Eqi 'REPLACE_WITH|your-domain\.example|CHANGE_ME|PLACEHOLDER' .env; then
  echo "ERROR: .env still contains placeholder values. Configure it before deployment." >&2
  exit 3
fi
if ! grep -Eq '^SECRET_KEY=.{32,}$' .env; then
  echo "ERROR: SECRET_KEY must contain at least 32 characters." >&2
  exit 4
fi
if ! grep -Eq '^LIBRAAI_PUBLIC_URL=https://[^/[:space:]]+$' .env; then
  echo "ERROR: Set LIBRAAI_PUBLIC_URL to your real HTTPS domain." >&2
  exit 5
fi
if ! grep -Eq '^LIBRAAI_TRUSTED_HOSTS=[^[:space:]]+' .env; then
  echo "ERROR: Set LIBRAAI_TRUSTED_HOSTS to your domain(s)." >&2
  exit 6
fi
docker compose config --quiet
docker compose up -d --build
docker compose ps
echo "LibraAI containers started. Configure Nginx TLS using nginx/libraai.conf.example."
