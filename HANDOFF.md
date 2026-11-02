# ONKAR-LIFE watch project - handoff (updated 2026-11-02 21:45 IST)

Paste this whole file into the new chat. Files live in ~/Projects/dafit-watch (Arch laptop, kitty).
More detail: FIRMWARE_PLAN.md (full history) and logs/ (every run is logged by run.sh).

**NOTE (added 00:10): the "21:45 snapshot" block below is OUT OF DATE (screen was dark, v12 then). The newest UPDATE at the
BOTTOM of this file wins (screen lit at 22:12, ONKAR OS v14-v17 since).**

## 21:45 snapshot (SUPERSEDED - kept for the hardware/stock facts in it)
- Watch runs OUR firmware v12 (BLE ONKAR-LIFE, 00:E0:12:34:56:78), still flashable over Bluetooth. Source + image: firmware/v12/.
- SCREEN STILL DARK. No light in any test. Panel logic is proven working; lighting power is probably missing.
- User is close to done and accepts bricking. Won't go to a repair shop or buy parts for this cheap watch.
- WAITING ON USER: whether to try the one idea left (below). Nothing is running.

### Proven (logs 21:27-21:38)
- Panel works on SPIC2 hardware: reg 0x0A = 08 before init, 9C after. 0x0D = 10 with all pixels on. 0x0F = C0 (self-check OK).
  0x0C = 05. TE on P3_0 = 26 pulses per 0.5 s (~52 Hz). Flex and data path are fine.
- Read that works: firmware 0x22, frame 03 00 RR 00, single wire, baud 8.
- Working sequence (display_v11.py power_up + display_lit.py panel_up): 0x1D SPIC2 -> P0_1 soft start -> P2_0 H/L/H -> 22-command INIT -> 120 ms
  -> 0x29 -> 0x51 one byte. Survives every step with the battery connected.
- MOTOR = P0_0 (stock PWM2_N, idle HIGH). v11+ parks it HIGH at boot; user reported no buzz in the runs after that. This was the "everything just
  runs the motor" problem. Older notes calling P2_5 or P0_7 the motor pin are wrong or unproven.
- White at 0x51=FF, motor parked: no reboot, no light. So the 21:00 reboot at full white was probably the motor, and the panel draws no noticeable lighting current.
- P1_1, P0_3, P2_7 soft-started under all-pixels-on: no light, no reboot.
- P2_5 HIGH reboots the watch EVERY time: 1 ms pulse, PWM ramp (0x1B), hard on (0x20), exact stock cycle with H_1/H_2 (v12 0x24). No flash seen.
  Same in logs back to 18:24. It returns on its own in ~13 s.

### Not proven / open
- That P2_5 feeds the panel. Stock turns it on before the screen (0x84AD88: P2_5, H_1, H_2, P1_2, P0_5 low, 50 ms, P2_5 high, 100 ms). It could be the sensor rail.
- Why a 1 ms pulse reboots. Too short for a normal inrush story. Could be a shorted rail, or it could be tripping the supply.
- Other causes of no light: panel supply from the battery line, damage from opening the watch or removing the heart-rate/sensor board, dead OLED.
- When the sensor board came off is unknown. P2_5 already killed the watch at 18:24, so if the removal came later it is not the cause.
- Battery: user says connected for the tests, held by hand, charge unknown. Wires came off B+/B- pads; user can't solder.
- 0x52 reads about half of what 0x51 wrote (10->08, 60->30, FF->FF80). Unexplained. It does follow writes.
- Whether pixel writes land. 0x23 quad DMA and 0x1F one-wire fills return OK, but nothing has ever been visible.

### The one idea left (NOT built)
v13: one-shot P2_5 at early boot, before Bluetooth starts, armed by the laptop. Clear the flash flag BEFORE trying. NEVER do it unconditionally at boot:
an instant reboot would loop forever and lose Bluetooth flashing. Odds are low. If the screen lights: build the full firmware. If not: stop.

### No way back to stock
No complete stock copy exists. logs/flash_dump.bin was taken at 20:06, after the first flash at 07:46. Missing: first 52 KB of the app (0x82C000-0x839000),
stock patch and upper stack (replaced by Realtek's). Web search found nothing for MOY-OKJ5, and the Moyoung server had no file. Don't flash the leftover part.

### Full firmware
User asked for it if the screen can't be fixed. Not built, and the user was told why: it can't create light, and can't be checked without a picture.
If the screen ever lights: clock face, button, battery %, then touch. Heart rate is gone (sensor board removed).

### Stock code map (logs/flash_dump.bin, base 0x800000; RAM code at flash = RAM + 0x678204)
- Boot 0x84DCF0: rail cycle 0x84AD88 -> P0_0 HIGH -> ... -> screen 0x83E5E8 -> 0x85421C (120 ms, 0x29) -> 0x8540FA (0x51 one byte = value<<1).
- Screen 0x83E5E8: SPIC2 setup 0x882F60 -> IF8080 clock off/on -> power/reset 0x8602CC -> TE P3_0 0x860330 -> INIT 0x83BBF4.
- Sleep 0x854118: 0x28, 100 ms, 0x10, 300 ms, then P0_1 low. Pixels: 0x88309E + 0x88314E (32 00 2C 00, GDMA ch1, handshake 22).
- Motor PWM: 0x83E6AC / 0x854F68 on P0_0. P2_3 looks like a peripheral reset pulse (0x864A68).
- tools/stock_pads.py lists every Pad_Config call, tools/stock_xref.py finds callers. Both read an objdump of the stock area and are one-off scripts:
  stock_pads.py takes the .dis path; stock_xref.py takes the folder holding stock.dis and runs from the project root.

### Build and run
- sdk/ still holds OLD v2 source. To build: copy sdk/rtl8762d-hmi-sdk-master somewhere, unpack firmware/v12/onkar_v12_src.tgz over it (its Makefile adds rtl876x_gdma.c),
  then `make` in board/evb_stack_img/silent_ota_gcc. Output bin/app_MP.bin. v11 and v12 were built this way and booted.
- Flash: `bash run.sh ota_flash --go firmware/vN/app_MP.bin`. Replug the charger if the watch isn't visible.
- v11/v12 commands: 0x20 stock power-up (reboots, contains P2_5), 0x21 TE count, 0x22 SPIC2 read, 0x23 quad fill, 0x24 stock rail cycle (v12, reboots).
- Tests: display_v11.py, display_lit.py, display_max.py, display_p25.py, display_rail.py, display_steps.py. All via `bash run.sh <name>`.
- ask() uses blocking input(), which stalls the Bleak loop; the link looked dead after a long Enter wait. Newer tests only ask at the end.

### Working with this user
Not a hardware person. Wants plain language, automatic scripts, one command, and honest conclusions. Run it for them where possible. Don't call a result proof until it is.

---
# HISTORY (earlier notes, kept as written)

## The device
- Fire-Boltt BSW051 smartwatch. Chip: Realtek RTL8762D (Cortex-M4, BLE). Board MOY.M80182.03.
  Stock firmware MOY-OKJ5-2.0.3 (Moyoung / Da Fit).
- Currently running OUR firmware v9 (BLE name ONKAR-LIFE, addr 00:E0:12:34:56:78).
- Battery wires came off B+/B- pads; user mostly runs it on the charger only (no battery). Holding the battery
  on is fiddly. Charger-only power seems to drop the watch when big loads switch on (unconfirmed).
- User: not a hardware person, can't solder or hold probes on pads. Wants fully automatic scripts,
  copy-paste commands, beeps (1 low beep = detected/finished, 2 = needs attention, + notify-send, NO terminal bell).

## What works
- Flashing our own firmware over BLE: `bash run.sh ota_flash --go firmware/vN/app_MP.bin` (waits forever, beeps).
- Our firmware (Realtek SDK silent_ota sample + src/app/silent_ota/onkar_tool.c): BLE first, OTA always available,
  8 s watchdog (armed after 3 heartbeats, paused during OTA), dead-man pin release after 30 s, pin guard,
  exact pin-state restore. Source: firmware/v9/onkar_v9_src.tgz. Build: SDK board/evb_stack_img/silent_ota_gcc, `make`.
- Tool service: write 0xB002 / notify 0xB003. Commands in the header comment of onkar_tool.c
  (0x03 hold pin, 0x08 pulse, 0x0A release, 0x10 status, 0x11 ADC sweep, 0x12-14 I2C, 0x16 SPI xfer,
   0x17 pixel fill, 0x18 pad dump, 0x19 float test, 0x1A screen search, 0x1B soft-start pin, 0x1C read flash).
- Laptop scripts: tool5.py (shared connect/beep helpers), find_screen.py, power_up.py, display_on.py,
  dump_flash.py, vibe.py, is_screen_connected.py. All via `bash run.sh <name>`.

## Hardware facts (confirmed)
- Vibration motor: P2_5 HIGH = strong vibration (stock code confirms). Something else also triggers buzzing during
  screen tests (P0_7 / bus pins?) - unresolved.
- P1_3, P1_4: floating them freezes the watch -> never touch.
- Laptop BlueZ grabs the watch as a keyboard sometimes -> scripts run `bluetoothctl remove` first.

## STOCK FIRMWARE RECOVERED (most of it) - logs/flash_dump.bin (1 MB copy of the watch flash)
- Layout: patch 0x803000, secboot 0x80D000, stack 0x80E000, APP 0x82C000 (size 0x7D000), appdata1 0x8A9000.
- Our app overwrote only 0x82C000-0x838604. Stock app 0x839000-0x8A9000 survives.
- Stock Pad_Config = 0x842CF0 (args: pin, mode, pwron, pull [0=UP,1=DOWN,2=NONE], OE, O).
- Stock LCD power/reset routine at 0x8602CC:
  P2_0 HIGH + P0_1 HIGH, wait 50 ms, P2_0 LOW, wait 120 ms, P2_0 HIGH, wait 50 ms.
  => LCD_RST = P2_0, LCD power enable = P0_1.
- Stock LCD command writer 0x862614 uses the SPIC2 hardware QSPI (0x400A0000), frame 02 00 CMD 00 params.
  Realtek's reference pins for SPIC2: CS P4_3, CLK P4_0, D0 P4_2, D1 P4_1, D2 P0_6, D3 P0_7.
- Other pins the stock code drives HIGH: P2_7, P2_3, P1_1; P0_3 switched on/off.
- Two I2C buses (I2C0/I2C1) on H_1/H_2 and P0_5/P1_2 (H pins are NOT the 32 kHz crystal on this board).
- NOT found: the panel's init command list and the SPIC2 pin setup - probably in the overwritten first 50 KB.

## Screen status: STILL DARK
- Every read of the panel ID (bit-banged on P4_x, 1-line, 4 protocols) returns 00000000, with or without
  P0_1 power + P2_0 reset (stock timing) + P0_3/P2_7/P2_3/P1_1 high. No pin shows an I2C pull-up either
  (touch/sensor rail looks unpowered).
- display_on.py (last run 20:11): first variant (P0_1 on) dropped the watch; the rest ran; nothing visible; IDs 0.

## Best next steps (in order)
1. Photo of the screen's flex cable / back of the display module: the printed part number identifies the
   panel + driver IC -> known init sequence. (No soldering needed.)
2. Use the SPIC2 hardware peripheral (copy src/platform/qspi_lcd_platform.c) instead of bit-banging, exactly like stock:
   power P0_1, reset P2_0, then SPIC2 read of reg 0x04/0xDA in 1-line mode, then init + fill.
   Consider that the stock may drive the panel in 4-line (P0_6/P0_7 = D2/D3).
3. In flash_dump.bin, keep looking for the SPIC2 pin/mode setup and any init table in surviving code
   (search for SYSBLKCTRL 0x40000210 / 0x400002A8 references, delay+cmd patterns).
4. Run tests with the battery actually connected to rule out charger-only brownouts.
5. Then: battery % (find the ADC pin from stock code - search for ADC 0x40010000 refs) and the motor/haptics.

## UPDATE 20:19 - STOCK INIT SEQUENCE RECOVERED
- Screen driver code runs from RAM (stored at flash 0x88xxxx, runs at 0x20xxxx, delta 0x678204).
  SPIC2 setup at flash ~0x882FC8: Pad_Config P4_x/P0_6/P0_7 pinmux+pullup, SYSBLK 0x210|=0x20, 0x2A8|=0x200,
  0x300|=BIT31, SPIC2 ser=1 baudr=1 ctrlr2|=0x30000. Pixel writes use opcode 0x32 (quad): 32 00 2C 00 + quad data.
- Cmd writer (RAM 0x20AE50): frame 02 00 HI LO data... (16-bit register addresses).
- Stock init routine 0x83BBF4 (22 cmds, FT2308-style): see INIT list in display_stock.py.
  Note stock init sets brightness 51 00 = 00 00 (app raises it later).
- display_stock.py = stock power (P0_1) + stock reset (P2_0) + stock init + brightness + 1-line paint, 4 variants.
- If 1-line pixel writes don't show, next: implement real SPIC2 quad pixel write (opcode 0x32) in firmware.

## UPDATE 20:30 - v10: screen via SPIC2 hardware (stock-identical)
- display_stock.py (bit-banged stock init) -> nothing visible; GREEN variant (P2_7+P2_3 high) dropped the watch.
- v10 firmware: 0x1D = qspi_lcd_platform_init() (SDK, matches stock register writes), 0x1E = stock cmd writer
  port (02 00 HI LO data via SPIC2 DR), 0x1F = fill via 02 00 2C 00 / 3C 00 chunks of 28 bytes.
- display_hw.py: SPIC2 init -> P0_1 power -> P2_0 reset -> stock INIT -> 51=FFFF -> 0x23 all-pixels-on 2 s -> colour.

## UPDATE 20:47 - WATCH REBOOTS AT PANEL SLEEP-OUT (display_steps.py)
- Watch is on v10 (flashed 20:26 and 20:32). Line 9 above (v9) is out of date.
- display_steps.py = display_hw sequence, watch checked after every step, no Enter wait, uptime read after a drop.
- Both attempts: SPIC2 setup, P0_1 power, P2_0 reset and init 1-15 all survive. Dies on init 16, reg 0x11 (sleep out),
  5.7 / 5.8 s in. Uptime 13 / 12 s on return and reset reason power-on = real reboot, returned without touching the charger.
- Best reading (not proven): sleep out starts the AMOLED's power circuits, the current surge browns out charger-only power.
  That would also mean the panel is receiving SPIC2 commands.
- Old display_hw results are not valid screen tests: it never got past sleep out. RED's instant drops came right after
  its blocking Enter prompt (input() stalls the Bleak loop), so RED probably sent nothing.
- Next: repeat `bash run.sh display_steps` with the battery connected. Past 0x11 -> battery was the blocker, watch the white step.
  Same drop with battery -> suspect panel/flex or the init values.

## UPDATE 21:04 - second display_steps run (battery test, user to confirm it was connected)
- Attempt 2 PASSED sleep out, display on, all 22 init commands and brightness max (first time ever). Dropped during the
  3 s full-white hold at max brightness, 10.1 s in; rebooted, power-on reset, did not return by itself within 40 s.
- Attempt 1 failed 0.0 s in before reaching the watch: link already down during the 5 s countdown (loose contact?), not a 0x1D fault.
- User saw nothing on the screen in this run.
- display_steps.py now starts at 6% brightness (white 6 -> 19 -> 38%), then a 100x100 white square, then max,
  and pings during each hold so a drop is timed to ~0.5 s.
- If it stays dark with the watch alive: check how stock sets brightness, and whether the last init command (FF00 23 08 01 01,
  which looks like a page switch) makes later commands miss. Consider firmware v11 with a SPIC2 ID read (needs no battery).

## UPDATE 21:30 - v11: PANEL IS ALIVE, MOTOR FIXED (screen still dark)
- firmware/v11 (build: unpack src over a copy of the SDK; Makefile now includes rtl876x_gdma.c). Watch is on v11.
  New: 0x20 all-in-one stock power-up, 0x21 TE count, 0x22 SPIC2 read, 0x23 quad DMA fill. P0_0 parked HIGH at boot.
- logs/20261102-212709-display_v11.txt: reg 0x0A = 0x08 before init, 0x9C after; TE = ~52 Hz on P3_0; all steps survive with battery.
  So SPIC2 path, panel, flex, init and the 1-wire read (SIO1, opcode 03) all work. User still saw nothing on the screen.
- MOTOR: P0_0 is the motor PWM (stock PWM2_N, idle HIGH). Parked -> no buzz for the first time. Not P0_7 / P2_5 as noted above.
- P2_5: reboots the watch within 0.6 s, hard (0x20, 2/2) or PWM ramp (0x1B). Stock turns it on before the screen (0x84AD88).
  Cause unknown; it was not needed for the panel to run.
- Other stock pins: P2_3 looks like a reset pulse for a peripheral (0x864A68), not power. P3_0 = TE.
- No complete stock firmware exists: first 52 KB of the app, patch and stack were overwritten before the 20:06 dump.
- User also removed the heart-rate/sensor board. Accepts bricking; next goal after lit screen = full firmware.
- Next: display_lit.py = all-pixels-on at low brightness + P1_1/P0_3/P2_7.

## UPDATE 21:42 - CONCLUSION OF SCREEN TESTS (watch on v12)
- Panel logic fully proven (logs display_lit 21:29, display_max 21:35): 0x0A=9C, 0x0D=10 (all pixels on), 0x0F=C0 (self-check OK),
  0x52 follows writes, TE ~52 Hz. User saw NO light in any test, even white at 0x51=FF. Watch does NOT reboot at full white
  now the motor is parked -> panel draws no noticeable lighting current -> high-voltage supply (ELVDD/ELVSS) is probably off.
  The 21:00 reboot at full white was probably the motor, not the panel.
- P1_1, P0_3, P2_7 high: no light, no reboot.
- P2_5 reboots the watch every time: 1 ms pulse, PWM ramp, hard on, and exact stock cycle with H_1/H_2 (v12 0x24). No flash seen.
  A 1 ms pulse is too short for a normal inrush story, cause unknown. Whether P2_5 feeds the panel is NOT proven.
- Remaining explanations: P2_5 rail (shorted or tripping the supply), panel supply from the battery line, damage from opening
  the watch or the sensor board removal, dead OLED.
- Last software idea, not built: one-shot P2_5 at early boot before Bluetooth starts, with a flash flag cleared BEFORE trying.
  Never do it unconditionally at boot: an instant reboot would loop forever and lose Bluetooth flashing.
- Full firmware needs a lit screen to be checked, so it was not built.

## UPDATE 21:55 - display_rail rerun (logs/20261102-215212-display_rail.txt)
- Watch was not visible for ~2 min (user switched to charger only, says the battery may be dead), then connected on v12.
- 0x24 stock rail cycle (P2_5 on) dropped it again, back by itself after ~13 s. Same as 21:38. Screen-light answer not collected
  (script ran with no input).
- Reset reason is mixed across P2_5 drops (power-on some runs, watchdog others) and the firmware calls it unreliable. Don't read anything into it.
- Correction: "1 ms is too short for inrush" is wrong. Capacitor inrush on a load-switch or boost enable happens within microseconds,
  so a 1 ms pulse can collapse a weak supply. A charger-only or dead-battery supply explains every P2_5 drop. Still not proven.
- If the battery was dead, the earlier "battery connected" P2_5 tests (21:27-21:38) were effectively charger-only too.
- Decision: v13 (early-boot P2_5) not built. It can't help if the supply itself can't deliver the surge. The only meaningful test left
  is P2_5 with a CHARGED battery properly attached. No battery -> stop the screen work.

## UPDATE 22:00 - SCREEN WORK STOPPED (battery dead)
- User saw no light in the 21:54 run.
- User re-attached the battery: the small red LED under the board (came on before when the battery was attached) stays off now.
  User believes the battery is dead and can't charge it. Not proven: it could also be a broken or loose wire contact, or the battery's
  protection cutting it off. Software can't tell these apart.
- Without a working battery the only meaningful test (P2_5 with real battery power) can't be run. Screen work stopped here.
  Full firmware not built: it can't be checked without a lit screen, and battery % is meaningless without a battery.
- Watch state: v12, charger only, Bluetooth + OTA still work. Nothing running.
- Resume only if a working battery is attached: charge it, then `bash run.sh display_rail` and ask the user whether anything lit.

## UPDATE 22:06 - v13 + display_pwm.py (user asked to keep going: "just show something")
- firmware/v13 (watch is on it, flashed 22:03): new 0x25 pin period_us(u16) high(u16, 0.1 us) = hardware PWM on TIM5
  (TIM6 is the SDK watchdog timer). Bluetooth stays up while it runs. high 0 = off, high >= period = held HIGH. 0B/dead-man stop it.
  Makefile adds rtl876x_tim.c. NOT yet confirmed that the PWM actually reaches P2_5 (if every PWM duty survives but "held fully ON"
  reboots, PWM output is broken).
- display_pwm.py: panel white at 25% (no P2_5), then P2_5 PWM rising (250 us period, then 25 us), display off/on at each step
  (in case the OLED power chip only starts at display-on). Retries panel setup up to 3x per ladder.
- First run 22:03 (charger only, battery dead): dropped at INIT command 2 (FF80), before P2_5. Needed a charger replug.
  So charger-only power can't even reliably run the panel init now; with the battery held on (21:27-21:38) all init passed.
- User wants to run commands in the visible Terminal tab (run_in_terminal), not hidden Bash.

## UPDATE 22:12 - FIRST LIGHT! (logs/20261102-220724-display_pwm.txt)
- display_pwm run 22:07: panel white (all pixels on, 0x51=0x40), P2_5 fed by v13 hardware PWM rising 0.4% -> 96% -> held fully ON,
  at 250 us and at 25 us period. Watch SURVIVED every step, both ladders, on charger only. USER SAW LIGHT (answered "yes").
  Which step it appeared at is not known yet.
- So: P2_5 = OLED high-voltage supply enable (now likely, was unproven). Hard switch-on reboots the watch (inrush);
  a PWM soft start (hardware TIM5, ~0.3-3 s per step) does not.
- Earlier charger-only runs dropped at random points during panel setup (22:03 init #2, 22:05 display on, 22:06 after white).
  User switched to a wall charger / pressed it on harder around then; the 22:07 run passed everything.
- Next: display_show.py = soft start then real colour fills (red/green/blue/square/quarters) to prove pixel data lands.
  If that works: full firmware with the PWM soft start built into boot - but only AFTER Bluetooth is up and only if the
  previous boot didn't die there (flash flag), never unconditionally at boot.
- User detail: light visible from ~60% duty (250 us ladder, ~22:08:47) through fully ON (~22:09:00). The 25 us ladder (22:09:12-22:10)
  showed NO light, even fully ON. Guess (unproven): fast pulses latched the OLED power chip into a fault/off state. Use 250 us only.

## UPDATE 22:35 - colour test, hardware found, v14 "ONKAR OS" built (NOT yet flashed)
- display_show 22:14 (logs/*display_show*): user saw red/green/blue/square/quarters "mostly right" but with stripes/patches;
  blue bottom-left quarter half cut. Likely cause: v11-v13 fill re-sent the 2B row window every 11-row block (odd start rows)
  and disabled SPIC2 between blocks. Stock firmware (0x881996/0x88309E) sets the full window once, waits TE, one 2C header,
  streams the whole frame in chained 8096-byte GDMA blocks. v14 copies that (stream mode 0); mode 1 = per-band even-aligned windows.
- display_discover 22:22 (logs/20261102-222214-display_discover.txt): touch chip answers at I2C 0x2E on SCL P0_5 / SDA P1_2
  (Chipsemi/Hynitron, probably CHSC5816: 32-bit register 0x2000002C, 8 bytes, FF n xl yl z xy_hi ...; protocol from memory of
  SensorLib, UNVERIFIED). Button not found (P3_1 and P2_4 didn't change). Crown = QDEC Y on P1_0/P2_6 (stock pinmux).
  Stock wake pins: P2_4 (pull-up, low), P3_1 (low), P2_2 (high), P1_6 (UART RX).
- firmware/v14 (app_MP.bin 109044 B, src tgz incl. onkar_os.inc + onkar_font.h; fonts from tools/gen_font.py, JetBrains Mono):
  ONKAR OS on top of the v13 tool. Bluetooth/OTA untouched; OTA start shows "UPDATING..." and freezes the UI.
  * Autostart 6 s after boot only if setting on AND boot-failure counter < 2 (counter saved before each start, cleared after
    15 s of RUN) -> a reboot during screen power-up can't loop forever. `os_ctl start` clears the counter.
  * Power-up = proven sequence + P2_5 PWM soft start 250 us period, 1 s per step (ramp setting).
  * Screens (swipe left/right, crown, button): clock, eyes (moods, blink), paint, info (all live debug), settings.
  * Info screen shows P2_2/P2_4/P3_1 level/changes, crown count, raw touch bytes. Button default "auto" = P3_1 or P2_2 changing.
  * BLE cmds 0x30-0x35 (status/start/stop, time, settings, fake input, re-probe touch, raw I2C). Laptop: os_ctl.py.
- Next: flash v14, check picture quality (try `os_ctl set stream 1` if stripes), touch on paint screen, which pin the button is.

## UPDATE 22:53 - v14 tested, v15 flashed
- v14 (flashed 22:39) photos: clock drawn but heavily glitched (doubled/shifted digits), clean only by luck.
  Cause: stream mode 0 renders strip N+1 while strip N is DMA'd; big text renders slower than a strip sends ->
  SPIC2 FIFO runs dry -> transfer ends -> remaining pixel bytes read as commands. Mode 1 (each 12-row strip its own
  window + 2C transfer) is correct. v15 default = mode 1 (stored setting 0x32 09).
- Watch kept restarting (boot failures counter 1-2, last reset = power-on, i.e. power loss, not watchdog): charger-only
  supply + lit screen, contact dropping. v14 cleared the failure counter after 15 s of RUN -> endless loop possible.
  v15 clears it only after 3 min of RUN. Invisible-over-Bluetooth periods were these reboots, not a BLE bug:
  os_rescue 22:48 proved BLE stays connected AND advertises while the screen runs (mode 1, ~50 s, no reboot).
- Button = P3_1 (5 edges when pressed, screen changed); "auto" button setting works.
- Touch "not found" in v14: probe did a 1-byte register read, the 0x2E chip NAKs that. v15 probes by address ACK only.
- Stored settings now: autostart OFF (set by os_rescue), stream mode 1. Start screen: `bash run.sh os_ctl start`;
  autostart back on: `bash run.sh os_ctl set autostart 1`. os_rescue.py = grab the watch in the 6 s window after boot.
- firmware/v15 flashed 22:51. Untested yet: touch protocol (CHSC5816 guess), crown (crown count stayed 0 in v14 test,
  user may not have turned it).

## UPDATE 23:45 - v16 "ONKAR OS 16" flashed and running
- New architecture (src in firmware/v16/onkar_v16_src.tgz; laptop simulator + same sources in tools/os_sim/):
  * onkar_gfx.inc: portable anti-aliased renderer. Display list of float primitives (rounded rects, rings, arcs, capsule
    lines, 4-bit anti-aliased text/icons), only the dirty rectangle is rendered, in 12-row strips, double-buffered with GDMA
    (each strip = own 2A/2B window + 2C write = the proven "mode 1"). Inner loops run from RAM (.app.data_ram.text),
    vsqrt inline, text decoded once per strip.
  * onkar_ui.inc: portable UI. Boot animation (3 rings + ONKAR), faces Stack / Analog (smooth second hand) / Modular,
    swipe left/right between faces (follows the finger), swipe up from bottom = control centre (flashlight, always-on,
    screen off, BT, next face, settings, brightness slider), button = app list / back home, long press = screen off.
    Apps: Stopwatch (laps), Timer (crown sets minutes), Sketch, Flashlight, Breathe, Settings, About (live fps/frame time).
    Inertia scrolling + crown scrolling, back-swipe from the left edge, pressed states, fades for wake/sleep.
  * onkar_os.inc: hardware core (panel/power/touch/button/crown from v15) + plat_* glue + status/commands.
  * fonts: tools/gen_font2.py (Adwaita Sans variable + Material Symbols Rounded; F_L only has the letters the UI uses).
- Settings magic ONK2 (fresh defaults): autostart ON, bright 180, timeout 15 s. Starts 3 s after power-up; failed-start
  counter -> back-off 3 s/120 ms ramp steps, 3 s/300 ms, 12 s/1 s, 48 s, 120 s. Counter cleared after 60 s running.
  Always retries. Clock: laptop sets it (any os_ctl call); saved to FTL every 5 min and restored after a power cut
  (shown as "not synced").
- 0x32 keys v16: 1 autostart 2 bright 3 ramp 4 touch_flags(bit3 = reverse crown) 5 button 7 touch_rst 8 always_on
  9 full_rows (send whole rows instead of partial-width windows) 10 te_sync 12 timeout 13 face 14 accent.
  0x30 02 status is 80 bytes: frame time/wait/pixels/fps/slowest at 52..71 (os_ctl prints them).
- Measured on the watch: build 1 = 95 ms per full-screen frame (CPU bound, SPI send only 0.6 ms). Build 2 (RAM code,
  inline vsqrt, single-pass text) = 43 ms. Build 3 (solid spans in circles/rounded rects) flashed 23:41 - see os_ctl.
  Touch + button confirmed working in v16 (user navigated to Settings / app list).
- Size: app 148.3 KB of 148 KB slot (0x25000 = 151552 B) -> ~3 KB left. Next space savers: F_H 206 -> 190 px,
  drop unused onkar_tool debug commands (onkar_tool_handle is 8.7 KB).
- Not verified yet: crown direction/feel, partial-width windows on this panel (if corners show garbage: os_ctl set full_rows 1).

## UPDATE 23:52 - root cause of bad colours found; v17 built (NOT flashed yet)
- Every build up to v16 called spic2_stock_init(false): P0_6/P0_7 (QSPI D2/D3) never routed to SPIC2, so 2 of every 4 pixel
  bits were floating -> patchy fills, grey shown green, white as dim teal, noisy edges. Stock and Realtek's
  qspi_lcd_platform.c claim them. (P0_7 was once suspected as the motor; the motor is P0_0.) Byte order was fine.
- "build 3 crash" was really resets during the P2_5 ramp (before any frame) at brightness 255 on charger power, not the span code.
- te_sync wait (up to 20 ms busy wait per frame) made 43 ms frames run at 14.5 fps. v17 defaults te_sync 0.
- firmware/v17: D2/D3 claimed, te_sync off, settings magic ONK3 (fresh defaults: bright 180, autostart on), status byte 79 = 17.
  Flash: bash run.sh ota_flash --go firmware/v17/app_MP.bin && bash run.sh os_ctl
- os_ctl/os_rescue still say v16 in places (key handling is the same), not updated yet.
- Still to do: shorter boot animation that a touch skips, remove Sketch/Breathe, reset reason in status, profile frame time.

## UPDATE 00:05 (Nov 3) - v17 IS WORKING; "not turning on" = power drops + back-off + screen sleep
- v17 flashed 23:55 / 23:58 fine. User reported "not turning on". Logs: the first starts reset the watch during the P2_5 ramp
  (23:59:01, ~5 s into a 1 s/step ramp, same as v16 at 23:42). Each failure raises the boot-failure counter -> back-off
  3 s / 12 s / 48 s / 120 s before the next try, so the watch looked dead for minutes. Last reset reason = power-on (power dip,
  not watchdog) -> charger-only supply, not a software bug.
- os_diag.py (new, `bash run.sh os_diag`): sets ramp 1 s/step, starts the screen, logs each ramp step + P2_5 duty until RUNNING,
  and after a drop reconnects and prints the reset reason. 00:02 run: watch had ALREADY come up by itself (~00:01:50 after the
  120 s back-off), run past 60 s (failures back to 0), then SLEPT after the 15 s screen timeout -> looked off.
- `os_ctl press` woke it at 00:02:45: RUNNING, watch face, 25 ms frames, touch chip 0x2E found.
- Settings now: ramp 100 (1 s per step, ~18 s to light up - slower but gentler; back to default: `os_ctl set ramp 10`).
- If it looks off: press the button (P3_1) first. Longer screen-on: `bash run.sh os_ctl set timeout 4` (5 min) or `set always_on 1`.
- Still open: the ramp still sometimes browns out on charger power; only fix is a better supply (battery). Not verified with user
  yet that the v17 colours (D2/D3 fix) look right.

## UPDATE 00:50 (Nov 3) - v18: haptics + crown working; screen start still intermittent on charger power
User feedback on v17: colour fix worked, frame rate good, face swiping a bit jittery (OS will be redesigned later anyway),
boot slow with no visible boot animation, crown did nothing, no haptics. Asked for haptics everywhere.
- firmware/v18 (src tgz = exactly what is on the watch, 144312 B; build tree as before):
  * Haptics: motor P0_0 (LOW = on, stock PWM2_N). TIM2 = 25 kHz PWM on P0_0 (timer_pwm2), TIM3 = 1 kHz tick, ISR in RAM
    (onkar_tim3_isr; patterns + tables in RAM; no flash reads, no calls). Between patterns P0_0 is parked as plain HIGH output.
    Patterns: tick soft tap click double success long bump alarm boot; 3 ms 100% kick on ERM start; level Off/Light/Medium/
    Strong scales duty + length. Timers are started only after the screen is up (never at boot) or by the laptop (0x36/0x37)
    while the OS is off. Hooks everywhere: crown detents (bump at list ends), button tap / long, taps, toggles, face snap,
    control centre, back-swipe, brightness slider every 10%, stopwatch, timer (alarm repeats every 1.5 s), Breathe
    (accelerating taps on inhale, quiet on exhale), boot. Settings has a "Haptics" row.
  * Crown: QDEC never counts on this board (QDEC CR_Y=0x800010A0, SR_Y stays 0 while turning). Crown mode 1 = software
    quadrature in the same 1 kHz ISR: CONFIRMED working 00:48 (both pins toggle, count follows direction). Set on the watch
    (0x32 16 1, saved). Source default is still crown_mode 0 -> make it 1 in the next build. crown_div (counts per click)
    = 2, NOT yet confirmed with the user. Crown on the watch face now switches faces.
  * Boot: logo drawn into panel memory before the ramp, fades in after it (brightness 0 during the ramp), held, then face.
    Boot wait 2 s; back-off 2/2/6/12/30 s (was up to 120 s); ramp steps 120/250/500 ms; finer RAMP table through 4-30%.
  * Removed old screen bring-up commands 11 15-17 19-1B 1D-1F 20 22-24 (saved 7.5 KB; old display_*.py tests need v17).
  * New BLE cmds: 36 id = play haptic (FF stop), 37 = crown/haptic diag, 38 addr n = peek peripheral registers.
    0x32 keys 15 haptic 16 crown 17 crown_div 18 hap_inv 19 fastramp. os_ctl: buzz NAME|all, crown (live view), peek, set ...
  * os_diag.py [ramp_ms]: starts the screen, logs each ramp step, reconnects after a drop and prints the reset reason.
- SCREEN START PROBLEM (also hit v16 23:42 and v17 23:59): with a weak charger supply the chip HANGS (watchdog reset 8 s
  later) the moment the P2_5 ramp reaches ~9.5-10% duty (~24 us pulses of 250 us). Deterministic per session: 6/6 at
  00:31-00:40, at 1 s, 0.5 s and 120 ms steps, with and without a lit logo. fastramp=1 (6->96% in 0.4 s from RAM, IRQs
  off) made it WORSE (power-on reset) -> real supply collapse, not flash/XIP. Left fastramp=0. It passes at other times
  (22:07, 00:01, 00:09, 00:47 all came up) -> charger contact/supply quality. Best fix: battery or firm charger contact.
- 00:46 motor test with the screen off: all 10 patterns played, watch stayed up. The watch did a power-on reset at ~00:47:10
  (cause unknown - possibly motor current on charger power; watch for this). After that reboot the screen came up by itself.
- Open questions for the user: do haptics feel like crisp taps (if they feel like long buzzes: os_ctl set hap_inv 1)?
  Does one crown click = one step (else os_ctl set crown_div 4 or 1)? Did the boot logo show?
