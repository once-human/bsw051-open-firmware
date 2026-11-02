#!/usr/bin/env bash
# Installs a systemd user timer that runs tools/daily_push.sh every day at 23:30
# (and catches up at the next boot if the laptop was off). Undo:  systemctl --user disable --now daily-push.timer
set -e
d="$HOME/.config/systemd/user"; mkdir -p "$d"
script="$(cd "$(dirname "$0")" && pwd)/daily_push.sh"
cat > "$d/daily-push.service" <<EOF
[Unit]
Description=Commit + push project repos to GitHub
After=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/bin/bash $script
EOF
cat > "$d/daily-push.timer" <<EOF
[Unit]
Description=Daily GitHub push of project repos
[Timer]
OnCalendar=*-*-* 23:30
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now daily-push.timer
systemctl --user list-timers daily-push.timer --no-pager
