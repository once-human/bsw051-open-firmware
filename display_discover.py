"""Find the button, touch chip and crown, with the screen lit.  Needs firmware v13.
   bash run.sh display_discover      (Ctrl+C to stop)
The terminal tells you what to do (beep = do it now):
  1. BUTTON phase (12 s): press the side button / crown button a few times
  2. TOUCH phase  (15 s): keep tapping and swiping the screen, finger on it as much as possible
  3. CROWN phase  (12 s): turn the crown back and forth
Candidates from the stock firmware: button P3_1, touch interrupt P2_4, crown P1_0/P2_6 (QDEC), touch I2C on P0_5/P1_2.
"""
import asyncio, time
from display_show import light_up, W, H
from display_lit import back
from display_v11 import step, fill, Dropped
from tool5 import connect, cmd, log, beep, save_hw, pn, I2C_KNOWN, WatchGone

BUTTON, TOUCH_INT, CROWN_A, CROWN_B = 25, 20, 8, 22      # P3_1, P2_4, P1_0, P2_6
TOUCH_RST = 19                                            # P2_3 (stock pulses it like a reset)
I2C0 = (5, 10)                                            # SCL P0_5, SDA P1_2 (stock I2C0 pinmux)


async def rd(c, pin, pull=1):
    r = await cmd(c, [0x04, pin, pull], 2)
    return r[2] if r and r[0] == 0x84 else None


async def scan(c, scl, sda):
    r = await cmd(c, [0x12, scl, sda], 6)
    if not r or r[0] != 0x92 or r[1] != 0:
        return None
    addrs = [a for a in range(0x08, 0x78) if r[3 + (a >> 3)] >> (a & 7) & 1]
    return addrs if len(addrs) <= 20 else None


async def watch(c, name, pins, secs, scans=False):
    log(f">>> {name} NOW ({secs} s)")
    beep("lost")
    last, changes, found = {}, {p: 0 for p in pins}, set()
    end, next_scan = time.time() + secs, time.time() + 1
    while time.time() < end:
        for p in pins:
            v = await rd(c, p)
            if v is None:
                continue
            if p in last and v != last[p]:
                changes[p] += 1
                log(f"   {pn(p)}: {last[p]} -> {v}")
            last[p] = v
        if scans and time.time() > next_scan:
            for scl, sda in (I2C0, I2C0[::-1]):
                a = await scan(c, scl, sda)
                if a:
                    found.update(a)
                    log(f"   I2C SCL={pn(scl)} SDA={pn(sda)}:", ", ".join(f"0x{x:02X} {I2C_KNOWN.get(x, '?')}" for x in a))
            next_scan = time.time() + 2
    log(f"   {name} done. pin changes:", {pn(p): n for p, n in changes.items()}, "| idle levels:", {pn(p): v for p, v in last.items()})
    return {"changes": {pn(p): n for p, n in changes.items()}, "i2c": sorted(found)}


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 13:
        raise SystemExit("flash v13 first: bash run.sh ota_flash --go firmware/v13/app_MP.bin")
    res = {}
    for attempt in (1, 2, 3):
        try:
            await light_up(c)
            hw, hh = W // 2, H // 2
            for b in (fill(0, hw - 1, 0, hh - 1, 0xF800), fill(hw, W - 1, 0, hh - 1, 0x07E0),
                      fill(0, hw - 1, hh, H - 1, 0x001F), fill(hw, W - 1, hh, H - 1, 0xFFFF)):
                await step(c, "picture", b, 30)
            break
        except Dropped as e:
            c = await back(c, res, f"light{attempt}", e)
    try:
        log("screen should be on now. Before touching anything, an I2C scan (touch chips may sleep until touched):")
        for scl, sda in (I2C0, I2C0[::-1]):
            log(f"   SCL={pn(scl)} SDA={pn(sda)}:", await scan(c, scl, sda))
        res["button"] = await watch(c, "PRESS THE BUTTON a few times", [BUTTON, TOUCH_INT], 12)
        res["touch"] = await watch(c, "TOUCH: keep tapping and swiping the screen", [TOUCH_INT, BUTTON], 15, scans=True)
        res["crown"] = await watch(c, "TURN THE CROWN back and forth", [CROWN_A, CROWN_B], 12)
        if not res["touch"]["i2c"]:
            log("no I2C answer yet -> releasing the touch reset line P2_3 (HIGH) and trying once more")
            await step(c, "P2_3 high", [0x03, TOUCH_RST, 1], hold=0.5)
            res["touch_rst"] = await watch(c, "TOUCH AGAIN: keep tapping and swiping", [TOUCH_INT], 12, scans=True)
    except (Dropped, WatchGone) as e:
        log(f"!!! watch dropped: {e}")
        res["dropped"] = str(e)
    beep("found")
    save_hw(display_discover=res)
    log("RESULT:", res)
    try:
        await cmd(c, [0x0B], 2)
        await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
