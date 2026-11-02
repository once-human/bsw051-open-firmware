#!/usr/bin/env bash
# One-time: log in to GitHub, create the PUBLIC repo "bsw051-open-firmware", push all history, turn on the daily push.
set -e
cd "$(dirname "$0")/.."
beep() { paplay /usr/share/sounds/freedesktop/stereo/dialog-warning.oga 2>/dev/null; }
if ! gh auth status >/dev/null 2>&1; then
    beep; beep; notify-send "GitHub login" "Finish the login in the browser (terminal shows a code)" 2>/dev/null || true
    gh auth login --hostname github.com --git-protocol https --web
fi
gh auth setup-git
if ! git remote get-url origin >/dev/null 2>&1; then
    gh repo create bsw051-open-firmware --public --source . --remote origin \
        --description "Open replacement firmware + reverse-engineering tools for the Fire-Boltt BSW051 smartwatch (Realtek RTL8762D), flashed over BLE"
fi
git push -u origin main
bash tools/install_daily_push.sh
echo "DONE: $(gh repo view --json url -q .url)  ($(git rev-list --count HEAD) commits)"
beep
