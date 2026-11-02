# ONKAR-LIFE watch project (read this first)

Custom firmware for a Fire-Boltt BSW051 smartwatch (Realtek RTL8762D, BLE), flashed over Bluetooth from this laptop.
**Read HANDOFF.md fully before doing anything** (latest state is at the bottom, newest UPDATE wins), then FIRMWARE_PLAN.md if needed.

## How things run here
- Every script: `bash run.sh <script-name-without-.py> [args]` -> log saved in logs/<time>-<name>.txt. Read the logs yourself.
- Flash: `bash run.sh ota_flash --go firmware/vN/app_MP.bin` (waits for the watch forever).
- Watch BLE: name ONKAR-LIFE, address 00:E0:12:34:56:78. Shared helpers (connect/beep/cmd): tool5.py.
- Firmware source: firmware/vN/onkar_vN_src.tgz. Build: copy sdk/rtl8762d-hmi-sdk-master somewhere, unpack the newest tgz over it,
  `make` in board/evb_stack_img/silent_ota_gcc -> bin/app_MP.bin (arm-none-eabi-gcc needed).
- Stock firmware remains: logs/flash_dump.bin (1 MB copy of the watch flash). Analysis helpers in tools/.

## Hard safety rules
- Never touch P1_3 / P1_4 (freezes the watch). Never put anything risky (e.g. P2_5) unconditionally at boot:
  a boot loop would kill Bluetooth flashing, which is the only way in.
- Keep Bluetooth + OTA working in every firmware build.

## How Onkar wants to work
- He is a software person, not hardware: no soldering, no holding probes. Give complete copy-paste commands (incl. how to stop).
- Automate everything; scripts must keep retrying/reconnecting by themselves, never give up.
- Sound: only the low warning sound (paplay /usr/share/sounds/freedesktop/stereo/dialog-warning.oga):
  1 beep = detected/finished, 2 beeps = needs his attention, plus notify-send. NO terminal bell (it steals window focus).
- Ask him only for what software can't see (e.g. "did the screen light up?"). Don't be overly cautious; one check per step.
- Be blunt and honest, flag uncertainty explicitly, don't overclaim. Prices in INR with links.
- He may run on charger only (battery wires are loose/held by hand) - ask which before power-hungry tests.
