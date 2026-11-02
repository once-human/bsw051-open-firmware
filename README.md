# bsw051-open-firmware

Open replacement firmware for the **Fire-Boltt BSW051** smartwatch (Realtek **RTL8762D**, Cortex-M4F, BLE),
plus the laptop tools used to reverse-engineer it. Everything is flashed over Bluetooth (Realtek silent OTA) from Linux:
no soldering, no SWD debugger. By [byonkar](https://instagram.com/byonkar).

What runs today: BLE + OTA always available, the 368x448 AMOLED driven over QSPI (SPIC2 + GDMA), CHSC5816 touch,
the button, and a small UI (clock, paint, settings). It is an application on top of Realtek's SDK, not an operating system.

> Working names inside the code (BLE name `ONKAR-LIFE`, `onkar_*` files, "ONKAR OS" in some docstrings) are
> placeholders and will be renamed.

Started on 2026-11-02. Where it got to that day:

1. **Morning: getting in.** Scanned the watch and probed the Da Fit / MoYoung protocol. Uploaded custom watch faces (`faces/`). Read the Realtek OTA service, then flashed our first firmware (v2) over BLE.
2. **Afternoon: mapping the hardware.** Mapped the pins (hwmap, padmap), found the vibration motor, and hunted for the screen (v3 to v9). Dumped the whole stock flash and recovered the stock screen power-up and init sequence from it.
3. **Evening: lighting the screen.** Drove the screen through the SPIC2 QSPI hardware (v10 to v12). The screen's high-voltage rail (P2_5) has to be soft-started with hardware PWM (v13), and that gave the first light on the screen.
4. **Night: a real UI.** Clock, touch and settings screens (v14, v15). v16 is in progress: anti-aliased dirty-rect renderer, gestures, boot animation, apps.

The full story, with every finding and dead end, is in [HANDOFF.md](HANDOFF.md). The project rules are in [CLAUDE.md](CLAUDE.md).

## Layout

| Path | What |
|---|---|
| `*.py`, `*.sh` | Laptop scripts. Run each with `bash run.sh <name>`; every run is logged to `logs/` |
| `firmware/vN/` | Each firmware version: `app_MP.bin` (flashable) and `onkar_vN_src.tgz` (source to unpack over the Realtek SDK) |
| `logs/` | Every run's output (BLE traces, pin maps, test results) |
| `faces/` | Watch faces made for the stock firmware |
| `tools/` | Font generators and helpers for analysing the stock firmware |

To flash a version: `bash run.sh ota_flash --go firmware/v15/app_MP.bin`

## Not in this repo

These are third-party and/or large:

- `sdk/`: Realtek RTL8762D HMI SDK, the build tree.
- `rtl8762d-sdk.zip`
- `gb/`: Gadgetbridge source.
- `dawft/`: Da Fit watch-face tool.
- `DaFup/`: Da Fit uploader.
- `logs/flash_dump.bin`: the stock firmware dump. It is the vendor's code, so it is never committed.

## About the history

Git was set up after the work was done. The first 76 commits were rebuilt from the files themselves:

- Each file is committed at the time it was last modified, so the commit dates are the real times from 2026-11-02.
- Each run log is grouped with the script or firmware it belongs to.
- A file that was edited many times appears once, in its final form.

From now on, `tools/daily_push.sh` commits and pushes any changes once a day.
