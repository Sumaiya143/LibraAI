#!/usr/bin/env bash
# Run from the project directory on the VPS. Requires docker compose.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")"
BACKUP_DIR="${LIBRAAI_BACKUP_DIR:-./private-backups}"
mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REMOTE="/data/backups/libraai-${STAMP}.db"
LOCAL="$BACKUP_DIR/libraai-${STAMP}.db"
if [[ -e "$LOCAL" ]]; then echo 'Backup already exists' >&2; exit 1; fi
docker compose -f compose.market.yaml exec -T libraai python -c 'from pathlib import Path; Path("/data/backups").mkdir(mode=0o700,exist_ok=True)' 
docker compose -f compose.market.yaml exec -T libraai python backup_manager.py backup /data/libraai.db "$REMOTE"
# Stage in a protected local directory. No live SQLite file is copied directly.
if ! docker compose -f compose.market.yaml cp "libraai:$REMOTE" "$LOCAL"; then
  rm -f "$LOCAL"
  exit 1
fi
chmod 600 "$LOCAL"
if ! python3 backup_manager.py verify "$LOCAL"; then
  rm -f "$LOCAL"
  exit 1
fi
sha256sum "$LOCAL" > "${LOCAL}.sha256"
# Clean up temporary container copy; local verified backup remains.
docker compose -f compose.market.yaml exec -T libraai python -c 'import os,sys; os.unlink(sys.argv[1])' "$REMOTE"
echo "Verified backup: $LOCAL"
