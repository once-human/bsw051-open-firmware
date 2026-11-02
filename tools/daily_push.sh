#!/usr/bin/env bash
# Daily snapshot: commit whatever changed in each project repo and push it to GitHub.
# Run by the systemd user timer "daily-push.timer" (installed by tools/install_daily_push.sh).
# Add more project folders to REPOS to back them up too.
REPOS=("$HOME/Projects/dafit-watch")
for r in "${REPOS[@]}"; do
    cd "$r" || continue
    git add -A
    if ! git diff --cached --quiet; then
        n=$(git diff --cached --name-only | wc -l)
        git commit -q -m "Daily snapshot $(date +%F): $n file(s) changed" -m "$(git diff --cached --stat | tail -1)"
    fi
    # push even if nothing new today (catches up after a day the laptop was offline)
    for i in 1 2 3; do git push -q origin HEAD 2>&1 && break; sleep 60; done
    echo "$(date '+%F %T') $r: $(git log -1 --format='%h %s')"
done
