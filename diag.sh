#!/usr/bin/env bash
# Bluetooth diagnosis for ONKAR-LIFE (no sudo). Saves everything to logs/diag-*.txt
cd "$(dirname "$0")"; out="logs/diag-$(date +%H%M%S).txt"
{
echo "## 1. what BlueZ knows about the watch"
bluetoothctl info 00:E0:12:34:56:78 2>&1
echo; echo "## 2. connected devices"
bluetoothctl devices Connected 2>&1
echo; echo "## 3. 30 second scan (everything seen)"
timeout 32 bluetoothctl --timeout 30 scan on 2>&1
echo; echo "## 4. watch info again after scan"
bluetoothctl info 00:E0:12:34:56:78 2>&1
} | tee "$out"
echo "== saved $out"
