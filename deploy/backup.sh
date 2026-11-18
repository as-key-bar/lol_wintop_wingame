#!/usr/bin/env bash
# Dump the MySQL database to ./backups (kept 14 days). Run from the repo root on the server.
# Cron example (daily 03:10):  10 3 * * * cd /opt/wintop && ./deploy/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups
stamp="$(date +%Y%m%d-%H%M%S)"

docker compose -f compose.prod.yaml --env-file deploy/.env exec -T mysql \
  sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --no-tablespaces wintop' \
  | gzip > "backups/wintop-${stamp}.sql.gz"

find backups -name 'wintop-*.sql.gz' -mtime +14 -delete
echo "backup ok: backups/wintop-${stamp}.sql.gz"
