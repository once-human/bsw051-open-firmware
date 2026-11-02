#!/usr/bin/env bash
# Beeps + notifies the moment ONKAR-LIFE shows up. Reacts within ~1 s of the watch advertising,
# prints a "still looking" line every 5 s.
# Usage: bash waitfor.sh      (Ctrl+C to stop)
cd "$(dirname "$0")"; mkdir -p logs; out="logs/waitfor-$(date +%H%M%S).txt"
ADDR="00:E0:12:34:56:78"
SCAN_TAG="--timeout 86400 scan on"

stop_scan() { pkill -f "bluetoothctl $SCAN_TAG" 2>/dev/null; bluetoothctl scan off >/dev/null 2>&1; }
trap 'stop_scan; echo; echo "stopped."; exit 130' INT TERM

found() {
  stop_scan
  msg="$(date +%H:%M:%S) ONKAR-LIFE IS BACK ($1) - it has power. Hold the watch exactly where it is!"
  echo "$msg" | tee -a "$out"
  command -v notify-send >/dev/null && notify-send -u critical "WATCH IS ALIVE" "$msg"
  for i in 1 2 3 4 5; do printf '\a'; command -v paplay >/dev/null && paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null; sleep 0.4; done
  exit 0
}

# forget the old cached 'keyboard' record, so the laptop can't silently grab the watch
# and the first advertisement shows up as a fresh [NEW] line
bluetoothctl disconnect "$ADDR" >/dev/null 2>&1
bluetoothctl remove "$ADDR" >/dev/null 2>&1
echo "Scanning nonstop for ONKAR-LIFE (status every 5 s). Put the watch on power; it beeps the moment it appears." | tee "$out"

while true; do
  # one long scan; every advertisement line is checked as it arrives
  while true; do
    if IFS= read -r -t 5 line; then
      case "$line" in *"$ADDR"*|*ONKAR*) found "seen advertising";; esac
    else
      rc=$?
      [ $rc -le 128 ] && break          # scan ended -> restart it
      bluetoothctl info "$ADDR" 2>/dev/null | grep -q 'Connected: yes' && found "connected"
      echo "$(date +%H:%M:%S) not seen yet" | tee -a "$out"
    fi
  done < <(stdbuf -oL bluetoothctl $SCAN_TAG 2>/dev/null)
  stop_scan
  sleep 1
done
