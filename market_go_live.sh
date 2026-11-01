#!/usr/bin/env bash
# Production release guard. Run on the VPS after provisioning domain, credentials and rights.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")"
if [[ ! -f .env ]]; then
  echo 'BLOCKED: .env is missing; copy .env.market.example and configure it.' >&2
  exit 1
fi
if [[ "$(stat -c '%a' .env)" != "600" ]]; then
  echo 'BLOCKED: restrict .env with chmod 600 .env' >&2
  exit 1
fi
# Never echo secrets; checks report only missing requirements.
python3 market_preflight.py --env .env
# Validate the Compose configuration before changing a running deployment.
docker compose -f compose.market.yaml config --quiet
# Build only after launch requirements have passed.
docker compose -f compose.market.yaml build libraai
docker compose -f compose.market.yaml up -d --no-build
# Container readiness does not prove merchant or business E2E success.
docker compose -f compose.market.yaml ps
printf '\nDeployment started. Verify public HTTPS, gateway E2E, licensing, refunds, and monitoring before accepting customers.\n'
