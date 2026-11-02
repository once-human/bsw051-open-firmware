# BSW051 custom firmware — findings & plan

## Hardware / firmware identity (verified)
- Chip: **Realtek RTL8762D ("SBee2")**, Cortex-M4F, BLE only. Source: OTA device-info icType=9 = IC_SBEE2 (Realtek DFU SDK constants); Realtek docs: RTL8762D = SBee2.
- Firmware: MOY-OKJ5-2.0.3, Moyoung protocol V2, face template 53 (368x448).
- Realtek OTA service d0ff-3c17-..., DFU service 6287-3c17-... both present.
- OTA device info (fff1 = 0901000700080000f00f0000):
  - specVersion 1, secureVersion 0
  - mode 0x07: buffer check ON, **AES-256 encrypted OTA ON**, AES mode 16N
  - maxBufferCheckSize 2048, otaTempBufferSize 0
  - imageVersionIndicator 0x0ff0 -> **single bank (no automatic fallback)**
- Patch version (ffd3) 0x580ef000, app version (ffd4) 0x90000001.
- No "read flash" opcode in Realtek DFU -> stock firmware can't be dumped over BLE.
- Moyoung server (api.moyoung.com/v2/upgrade/factory?version=&mac=&app_version=1.0.2) has no file for OKJ5.

## Gates
1. Chip — DONE: RTL8762D.
2. SDK — DONE: Realtek official RTL8762D SDK (gitee realmcu/rtl8762d-hmi-sdk), has GCC projects incl. silent_ota_gcc.
3. OTA AES key — DONE (high confidence): Realtek library default
   4e46f8c5092b29e29a971a0cd1f610fb1f6763df807a7e70960d4cd3118e601a
   (libRtkAesJni.so prints "use default key"; Moyoung never sets a key).
4. Signature / secure boot — OPEN. Image has 256B RSA signature field; OTA itself only checks CRC16/SHA256.
   SDK ships Realtek default signing key tool/keys/rtk_rsa.pem. Unknown if watch enforces secure boot.
5. Flash map (where the app lives) — OPEN. SDK default: app @0x0082C000. Watch layout unknown.
6. Patch/upperstack ABI match — OPEN. Watch patch 0x580ef000 vs SDK bundled versions.
7. Hardware map (display/touch/buttons/motor/PMIC pins) — OPEN, only needed after lifeline works.

## Strategy: "lifeline first"
- First custom image = Realtek's own silent_ota sample: BLE advertising + OTA/DFU service, NO display code.
  If it boots, it advertises and accepts the next image -> we always keep a way back in.
- Never send anything until gates 4-6 are answered on paper.
- Recovery if all else fails: RTL8762D UART download mode (needs opening watch, ART-Badge rescue tools as reference).

## Update 07:15
- Toolchain OK (arm-none-eabi-gcc 16.2). Realtek SDK in sdk/. silent_ota_gcc builds: 37 KB app,
  packed by prepend_header with -b 9 (= SBEE2 = our icType). Signed with sha256 checksum mode.
- Version format (patch_header_check.h): major 4b | minor 8b | revision 15b | build 5b (LSB first).
  Watch (ffe0, likely OTA hdr/SecureBoot/Patch/App): 0x00000001, 0.0.2.1, 0.0.239.11, 1.0.0.18
  SDK default images: OTAHeader 1.0.0.1, fsbl 0.0.2.2, Patch 0.0.440.4, UpperStack 1.1.5.0, App 1.8.0.28
- Safe DFU opcodes (read-only per SDK): 0x06 report image version, 0x0b IC type, 0x0d version check.
  NEVER in dry run: 0x01 start, 0x02, 0x03 validate, 0x04 activate+reset, 0x05 reset, 0x0c copy image.
- ota_dryrun.py written (allowlist enforced in code).

## Update 07:25 — dry run 1 results (watch, read-only)
- IC type 9 confirmed via DFU. Images: OTA hdr 0x00000001, SecureBoot 0.0.2.1, RomPatch 0.0.239.11, App 1.0.0.18,
  AppData1 0. AppData2-6 + UpperStack all return identical 0x041006bb -> likely "unknown/not reported", ambiguous.
- 1-byte 0x0d -> status 0xff (length error) = same behaviour as current SDK's 0x0d IMAGE_VERSION check.
- Realtek reference images (SDK release patch/fsbl/upperstack/app + RT-Thread ART-Badge factory images):
  signature field EMPTY, no RSA pubkey -> Realtek stock boot chain is unsigned. Watch runs stock fsbl/patch
  -> secure boot likely OFF (strong evidence, not proof).
- Standard RTL8762D layout identical in 2020 badge and 2025 SDK: patch 0x803000, fsbl 0x80D000,
  upperstack 0x80E000, app 0x82C000.
- No public SDK matches watch patch 0.0.239.11 -> plan = Realtek-tested matched set
  (Patch 0.0.440.4 + UpperStack 1.1.5.0 + our App) unless the watch refuses patch updates.
- ota_dryrun2.py: 0x0d acceptance checks (read-only compare per SDK).

## Update 07:35 — dry run 2
- All 0x0d replies = 0xff = "opcode >= DFU_OPCODE_MAX" -> watch DFU is older, has no 0x0d.
  (Earlier note that 0x0d matched new SDK was WRONG.)
- START_DFU (0x01) per SDK: checks ic_type + image_id after AES-decrypting 16B header, RAM only,
  no erase/write until data arrives. ota_handshake.py probes it (App/RomPatch/UpperStack headers),
  tries AES byte orders A-E, never sends data/validate/activate/reset.

## 2026-11-02 07:46 — CUSTOM FIRMWARE RUNNING
- Flashed RomPatch 0.0.440.4 -> UpperStack 1.1.5.0 -> lifeline App 1.8.0.28 (ONKAR-LIFE). All validated, all booted.
- New BLE address: 00:E0:12:34:56:78 (Realtek default). Buffer CRC size must EXCLUDE the 12B header.
- Next: v2 firmware = battery voltage (internal VBAT ADC) + GPIO/I2C pin tools + display probe (QSPI LCD pins P4_0..3, P0_6, P0_7 per Realtek platform driver).

## v3 (2026-11-02) - safety + hardware discovery
- Pin guard in firmware: H_0/H_1/H_2 refused by every command (that was the freeze).
- Watchdog 8 s, armed only after 3 heartbeats (no boot-loop risk), paused when a firmware update starts.
- Dead-man: driven pins released on disconnect or 30 s without commands (input + pull-down = motor off).
- Advertises as a watch (0x00C0) + battery UUID, no HID/keyboard.
- No deep sleep (decided: stability first).
- New cmds: 0x10 status, 0x11 ADC sweep P2_0..7+VBAT, 0x12/13/14 I2C, 0x15 display-bus hunt, 0x16 SPI xfer, 0x17 pixel fill.
- Theory: VBAT reads flat 3.29 V because the chip's VBAT pin sits on the 3.3 V regulator; real battery is on a P2_x divider. UNCONFIRMED.
- Laptop: tool3.py (status, motor, findbattery, battery, i2c, lcdhunt, lcdtest, auto) -> logs/hw.json

## v4 (2026-11-02 18:10) - safe pins
- FINDING: 'read all pins' (0x05) killed the watch twice on charger-only power, even with H pins excluded.
  Watch did NOT come back by itself (watchdog didn't rescue it) -> looks like power loss, i.e. some pin
  the board needs left floating (power-hold?). UNCONFIRMED which pin.
- Motor: none of P0_6/P0_7/P4_3/P4_0/P4_1/P4_2 buzzed (HIGH or LOW) on charger-only power.
- v4: every pin's exact boot state (AON pad bytes + pinmux) saved before first touch and restored on release.
  0x18 read-only pad dump. 0x19 float test. Boot-time software outputs never touched by hunt/read.
- tool4: map (dump + per-pin float test, auto-reconnect after a death) -> lcdhunt -> lcdtest.

## v5 (18:22) - go for the display
- map result: P1_3 and P1_4 (peripheral mode, pull-up at boot) KILL the watch when floated -> never touch.
- boot pinmux: P4_3/P4_0/P4_1/P4_2 = SPI0 slave CS/CLK/SO/SI (0x2d-0x30); P0_3 UART2_TX (log); P3_0/P3_1 HCI UART;
  P1_0/P1_1 SWD; P0_0 + P2_4 DWGPIO (our TP0/KEY).
- v4 full hunt (one 90 s command) dropped the link ~7 s in -> v5 splits the hunt into one CS per command (~1 s each).
- tool5 display: backlight sweep (HIGH then LOW, user watches screen) -> blind init+paint on reference pins
  -> chunked ID hunt (no reset, then reset sweep with CS=P4_3, then full) -> paint.

## v7 (18:45) - automatic screen finder
- screen.py (v6): every read on P4_2 = 00000000 for all 20 reset pins -> screen silent (unpowered / in reset / not connected).
- SDK: hardware screen pins of RTL8762D = CS P4_3, CLK P4_0, D0 P4_2, D1 P4_1, D2 P0_6, D3 P0_7 (qspi_lcd_platform.c).
  Board labels only CS/CLK/SIO0 -> 1-line mode -> P0_7 free -> motor on P0_7 (vibe.py) fits.
- 0x1A screen_search: power pin x level x every reset pin x 4 read protocols, ghost filter (repeat + edges + must vanish with CS high).
- find_screen.py: fully automatic over 3 bus variants; on hit -> wake, read 0x0A, paint, backlight sweep.
- If nothing: suspect display flex cable loose after opening the watch.

## v8 (19:06) - power rail theory
- is_screen_connected: NO pin has an external pull-up -> peripheral rail (screen/touch/sensors + their pull-ups) is OFF.
- P2_3 and P2_5 driven HIGH froze the watch instantly -> classic load-switch enable inrush on battery-less supply.
- 0x1B soft-start: PWM ramp of an enable pin (0.5 s / 2.5 s) then hold.
- power_up.py: ramp P2_3, P2_5, P1_5, then others; success = new pull-ups appear; then screen search + paint.

## STOCK FIRMWARE FINDINGS (flash dump 2026-11-02 20:06, logs/flash_dump.bin, 1 MB)
- OTA header layout: patch 0x803000, secboot 0x80D000, stack 0x80E000, APP 0x82C000 size 0x7D000, appdata1 0x8A9000 size 0x10000.
- Our app overwrote 0x82C000-0x838604; stock app 0x839000-0x8A9000 SURVIVES (strings: lcd_on_off_change_timer, moter_flag_timer, INIT_BK, MOY-OKJ5-2.0.3).
- Stock Pad_Config = 0x842CF0 (args pin, mode, pwron, pull[0=UP,1=DOWN,2=NONE], OE, O).
- Stock LCD power/reset fn 0x8602CC: P2_0 H + P0_1 H, 50ms, P2_0 L 120ms, P2_0 H, 50ms.  => LCD_RST = P2_0, LCD power = P0_1.
- Stock LCD cmd write 0x862614 uses SPIC2 (0x400A0000) DR: 02 00 cmd 00 params  => QSPI panel on hardware pins (P4_x).
- Other stock outputs HIGH: P2_7 (0x8554a4), P2_3 (0x847f9e), P1_1 (0x8507c4), P0_3 switchable (0x8554aa).
- Motor P2_5 (0x84ad9a/0x84adf2). I2C0/I2C1 used with H_1/H_2 and P0_5/P1_2 (H pins are I2C here, not a crystal!).
- LCD init sequence itself is NOT found (probably in the overwritten first 50 KB).
