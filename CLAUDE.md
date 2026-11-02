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

## Watch hardware (confirmed)
- Panel 368x448 AMOLED, QSPI on SPIC2 (P4_0 CLK, P4_3 CS, P4_2/P4_1/P0_6/P0_7 data), TE P3_0. Power: P0_1 logic (soft start),
  P2_0 reset, P2_5 high voltage (TIM5 PWM ramp only, never switched on hard).
- Touch CHSC5816 at I2C 0x2E, SCL P0_5 / SDA P1_2 (bit-banged), INT P2_4 (low while touched). Button P3_1 (low = pressed).
  Crown = quadrature on P1_0 / P2_6 (pull-ups). The QDEC block never counts (CR_Y ok, SR_Y stays 0): v18 decodes it in
  software in a 1 kHz TIM3 ISR (setting crown = 1, saved on the watch). Motor = P0_0, LOW = on (stock PWM2_N, idles HIGH);
  v18 drives it with TIM2 PWM (timer_pwm2). TIM5 = P2_5 ramp, TIM6 unused (SDK watchdog timer is compiled out).
  No battery fitted right now: charger only. The screen start (P2_5 ramp) hangs/resets the chip at ~10% duty when the
  charger supply is weak - intermittent, not a code bug (see HANDOFF 00:50).

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
