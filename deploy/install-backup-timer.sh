#!/usr/bin/env bash
# Install a daily systemd timer (03:10 JST) that runs deploy/backup.sh as the current user.
# Amazon Linux 2023 ships without cron, so a systemd timer is used instead.
# Run from the repo root on the server:  sudo ./deploy/install-backup-timer.sh
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
run_user="${SUDO_USER:-$(id -un)}"

# backups/ may have been created by Docker as root; the backup runs as $run_user.
mkdir -p "$repo_dir/backups"
chown "$run_user":"$run_user" "$repo_dir/backups"
chmod 700 "$repo_dir/backups"

cat > /etc/systemd/system/wintop-backup.service <<UNIT
[Unit]
Description=Dump the wintop MySQL database

[Service]
Type=oneshot
User=$run_user
WorkingDirectory=$repo_dir
ExecStart=$repo_dir/deploy/backup.sh
UNIT

cat > /etc/systemd/system/wintop-backup.timer <<'UNIT'
[Unit]
Description=Daily wintop database backup

[Timer]
OnCalendar=*-*-* 03:10:00 Asia/Tokyo
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now wintop-backup.timer
systemctl list-timers wintop-backup.timer --no-pager
