"""Is the screen module even plugged in?  Fully automatic, ~1-2 min, no questions.
   bash run.sh is_screen_connected        (Ctrl+C to stop)

The touch chip sits on the same ribbon cable as the screen and talks over I2C.
If the watch can find the touch chip, the ribbon is connected and the screen has power.
If it finds the motion sensor (main board) but NO touch chip, the ribbon is most likely loose.
"""
import asyncio
from tool5 import connect, cmd, log, pn, load_hw, save_hw, WatchGone, VALID, alive, watch_back, NOT_DISPLAY

TOUCH = {0x15: "touch CST816/CST716", 0x38: "touch FT6x06/FT3x68", 0x5D: "touch GT911", 0x14: "touch GT911",
         0x2E: "touch HYN", 0x1A: "touch CST3xx", 0x48: "touch ?", 0x24: "touch ?"}
OTHER = {0x18: "motion SC7A20/LIS3DH", 0x19: "motion SC7A20/LIS3DH", 0x0F: "motion STK8321", 0x12: "motion QMA7981",
         0x68: "motion BMI/MPU", 0x6A: "motion QMI8658", 0x6B: "motion QMI8658", 0x44: "heart-rate HRS3300",
         0x33: "heart-rate VC31", 0x57: "heart-rate MAX3010x", 0x51: "RTC", 0x36: "fuel gauge", 0x55: "fuel gauge"}


async def safe(c, msg, timeout=5):
    try:
        r = await cmd(c, msg, timeout)
    except WatchGone:
        r = None
    if r is None and not await alive(c):
        log("watch dropped - waiting for it to come back (replug the charger if it doesn't within ~20 s)")
        c = await watch_back(c)
        return c, None
    return c, r


async def main():
    c = await connect()
    hw = load_hw()
    danger = set(hw.get("danger", []))
    skip = danger | {3, 8, 9, 20, 11, 12} | {6, 7, 32, 33, 34, 35}   # log UART, SWD, button, critical, screen bus, motor
    pins = [p for p in VALID if p not in skip]
    # I2C lines have a pull-up resistor on the board: they read HIGH even while we pull them down
    sus = []
    for p in pins:
        c, r = await safe(c, [0x04, p, 2])
        if r and r[0] == 0x84 and r[2] == 1:
            sus.append(p)
    log("pins held HIGH by the board (I2C suspects):", [pn(p) for p in sus] or "none")
    found = {}
    resets = [None] + [p for p in pins if p not in sus]
    for rst in resets:
        if rst is not None:   # wake a sleeping touch chip: pulse its reset
            c, _ = await safe(c, [0x03, rst, 0]); await asyncio.sleep(0.02)
            c, _ = await safe(c, [0x03, rst, 1]); await asyncio.sleep(0.06)
        for scl in sus:
            for sda in sus:
                if scl == sda:
                    continue
                c, r = await safe(c, [0x12, scl, sda], 6)
                if not r or r[0] != 0x92 or r[1] != 0:
                    continue
                addrs = [a for a in range(0x08, 0x78) if r[3 + (a >> 3)] >> (a & 7) & 1]
                if 0 < len(addrs) <= 12:
                    key = (scl, sda)
                    new = set(addrs) - found.get(key, set())
                    if new:
                        found.setdefault(key, set()).update(addrs)
                        log(f"I2C SCL={pn(scl)} SDA={pn(sda)} reset={pn(rst) if rst is not None else '-'}: " +
                            ", ".join(f"0x{a:02X} {TOUCH.get(a) or OTHER.get(a) or '?'}" for a in sorted(new)))
        if rst is not None:
            c, _ = await safe(c, [0x0A, rst])
        if any(a in TOUCH for s in found.values() for a in s):
            break
    alla = {a for s in found.values() for a in s}
    touch = sorted(a for a in alla if a in TOUCH)
    save_hw(i2c_found={f"{pn(k[0])}/{pn(k[1])}": sorted(v) for k, v in found.items()})
    print()
    if touch:
        log(f"VERDICT: touch chip found ({', '.join(TOUCH[a] for a in touch)}) -> the screen ribbon IS connected and powered.")
        log("         So the screen problem is software (power sequence/init). Send this log to Claude.")
    elif alla:
        log("VERDICT: main-board chips answer, but NO touch chip -> the screen/touch ribbon is very likely LOOSE or unplugged.")
        log("         Open the watch, press the screen's ribbon connector firmly back into its socket, then rerun find_screen.")
    else:
        log("VERDICT: no I2C chip answered at all -> sensors are unpowered or on pins I can't reach. Send this log to Claude.")
    try:
        await cmd(c, [0x0B], 2); await c.disconnect()
    except Exception:
        pass

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nstopped.")
