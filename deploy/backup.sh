#!/usr/bin/env bash
# Dump the MySQL database to ./backups (kept 14 days). Run from the repo root on the server.
# Scheduled daily by the systemd timer installed with deploy/install-backup-timer.sh.
set -euo pipefail
umask 077

cd "$(dirname "$0")/.."
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"

tmp="backups/.wintop-${stamp}.sql.gz.partial"
trap 'rm -f "$tmp"' EXIT

docker compose -f compose.prod.yaml --env-file deploy/.env exec -T mysql \
  sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --no-tablespaces wintop' \
  | gzip > "$tmp"

# A dump that is only the gzip header means mysqldump produced nothing; never keep it.
if [ "$(gzip -dc "$tmp" | wc -c)" -lt 1000 ]; then
  echo "backup failed: dump is empty" >&2
  exit 1
fi
mv "$tmp" "backups/wintop-${stamp}.sql.gz"

find backups -name 'wintop-*.sql.gz' -mtime +14 -delete
echo "backup ok: backups/wintop-${stamp}.sql.gz"
