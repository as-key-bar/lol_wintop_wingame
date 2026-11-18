#!/usr/bin/env bash
# Install a daily systemd timer (04:00 JST) that deletes YouTube-derived rows older than the
# retention limit (YouTube API Services Developer Policies III.E.4: at most 30 days).
# It runs inside the already running api container, so it uses the same code and database.
# Run from the repo root on the server:  sudo ./deploy/install-retention-timer.sh
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
run_user="${SUDO_USER:-$(id -un)}"

cat > /etc/systemd/system/wintop-retention.service <<UNIT
[Unit]
Description=Delete expired YouTube-derived data from the wintop database

[Service]
Type=oneshot
User=$run_user
WorkingDirectory=$repo_dir
ExecStart=/usr/bin/docker compose -f compose.prod.yaml --env-file deploy/.env exec -T api python -m app.retention
UNIT

cat > /etc/systemd/system/wintop-retention.timer <<'UNIT'
[Unit]
Description=Daily purge of expired YouTube-derived data

[Timer]
OnCalendar=*-*-* 04:00:00 Asia/Tokyo
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now wintop-retention.timer
systemctl list-timers wintop-retention.timer --no-pager
