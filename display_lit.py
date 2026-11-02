"""Why is a running panel dark?  Needs firmware v11.
   bash run.sh display_lit      (Ctrl+C to stop)
Panel up, then numbered tests, one beep each: all-pixels-on (needs no pixel data) at rising brightness, then
the remaining stock power pins one at a time. Answer with the number where you first saw any light.
"""
import asyncio, time
from display_stock import INIT
from display_steps import came_back, uptime, COME_BACK_S
from display_v11 import step, power_up, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw, pn

ALL_ON = [0x1E, 0x23, 0x00, 0]
EXTRA_PINS = [9, 3, 23]                 # P1_1, P0_3, P2_7: stock drives these, P2_5 is left out (reboots the watch)
n = 0


def bright(v):
    return [0x1E, 0x51, 0x00, 1, v]


async def look(c, name, b, hold=4.0, wait=6):
    global n
    n += 1
    log(f">>> TEST {n}: {name} - LOOK AT THE SCREEN")
    beep("found")
    await step(c, name, b, wait, hold)


async def te(c):
    r = await cmd(c, [0x21, 0xF4, 0x01], 3)
    return int.from_bytes(r[1:3], "little") if r and r[0] == 0xA1 else None


async def regs(c):
    out = {}
    for reg in (0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x52, 0x54, 0x56):
        r = await cmd(c, [0x22, 0x03, 0x00, reg, 0x00, 2, 0, 0, 8])
        out[f"{reg:02X}"] = r[3:5].hex() if r and r[0] == 0xA2 else "none"
    return out


async def panel_up(c):
    await power_up(c, False)
    for hi, lo, data in INIT:
        await step(c, f"init reg {hi:02X}{lo:02X}", [0x1E, hi, lo, len(data), *data])
        if hi == 0x11:
            await asyncio.sleep(0.12)
    await asyncio.sleep(0.12)
    await step(c, "display on", [0x1E, 0x29, 0x00, 0])


async def back(c, res, name, e):
    log(f"!!! DROPPED AT: {e}")
    res[name] = {"died_at": str(e)}
    try:
        await c.disconnect()
    except Exception:
        pass
    by_itself = await came_back(COME_BACK_S)
    c = await connect()
    up, why = await uptime(c)
    log(f"came back by itself: {by_itself} | uptime {up} s, last reset: {why}")
    res[name].update(by_itself=by_itself, uptime=up)
    return c


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 11:
        raise SystemExit("flash v11 first: bash run.sh ota_flash --go firmware/v11/app_MP.bin")
    res = {}
    log("=== Panel starting. Watch the screen; each beep is a new test.")
    try:
        await panel_up(c)
        await step(c, "brightness 6%", bright(0x10))
        res["regs"] = await regs(c)
        log("registers:", res["regs"], "| TE in 0.5 s:", await te(c))
        await look(c, "all pixels on, 6%", ALL_ON)
        await look(c, "all pixels on, 19%", bright(0x30))
        await look(c, "all pixels on, 38%", bright(0x60))
        await look(c, "+ brightness control on (0x53)", [0x1E, 0x53, 0x00, 1, 0x20])
        res["regs_lit"] = await regs(c)
        log("registers:", res["regs_lit"], "| TE in 0.5 s:", await te(c))
    except Dropped as e:
        c = await back(c, res, "base", e)
    for p in EXTRA_PINS:
        name = pn(p)
        try:
            await panel_up(c)
            await step(c, "brightness 38%", bright(0x60))
            await step(c, "all pixels on", ALL_ON)
            await look(c, f"all pixels on + {name} soft start", [0x1B, p, 1, 100])
            log(f"{name}: TE in 0.5 s:", await te(c))
        except Dropped as e:
            c = await back(c, res, name, e)
    beep("found")
    a = ""
    for _ in range(3):
        a = ask(f"Which TEST number first showed ANY light? Type the number, or 'nothing' (1-{n}):")
        if a:
            break
    save_hw(display_lit={"results": res, "seen": a})
    log("RESULT:", res, "| you saw:", a or "(no answer)")
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
