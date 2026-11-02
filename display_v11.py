"""Screen ON with the motor parked: SPIC2, reset, stock init, quad pixels; first without the P2_5 rail, then with it soft-started.  Needs firmware v11.
   bash run.sh display_v11      (Ctrl+C to stop)
Fully automatic. Reads the panel's own signals (ID registers, TE pulses) so the log says if the panel is alive.
Watch the screen: white square -> whole screen red -> green square. Answer once at the end.
"""
import asyncio, time
from display_stock import INIT
from display_steps import came_back, uptime, hold_alive, COME_BACK_S
from tool5 import connect, cmd, ask, log, beep, save_hw, WatchGone, alive


class Dropped(Exception):
    pass


async def step(c, name, b, wait=4.0, hold=0):
    log(f"   {name}")
    try:
        r = await cmd(c, b, wait)
        if r is None or (b[0] in (0x1E, 0x1F, 0x20, 0x23) and r[1] != 0):
            log(f"      reply: {r.hex() if r else 'none'}")
        died = await hold_alive(c, hold) if hold else (None if await alive(c) else 0.0)
    except WatchGone:
        raise Dropped(name)
    if died is not None:
        raise Dropped(f"{name} ({died:.1f} s after it was sent)")
    return r


async def signals(c, when):
    out = {}
    for reg in (0x04, 0x0A, 0xDA, 0xDB, 0xDC):
        for ch in (0, 1):               # 0 = one wire, 1 = both wires sampled
            r = await cmd(c, [0x22, 0x03, 0x00, reg, 0x00, 4, 0, ch, 8])
            out[f"{reg:02X}/{ch}"] = r[3:7].hex() if r and r[0] == 0xA2 else "none"
    r = await cmd(c, [0x21, 0xF4, 0x01], 3)      # 500 ms
    te = int.from_bytes(r[1:3], "little") if r and r[0] == 0xA1 else None
    live = any(v not in ("00000000", "ffffffff", "none") for v in out.values())
    log(f"{when}: TE pulses in 0.5 s = {te} | regs (reg/wires): {out}")
    log(f"   panel answers on the bus: {'YES' if live else 'no'} | panel running frames: {'YES' if te else 'no'}")
    return {"te": te, "regs": out, "bus": live}


def fill(x0, x1, y0, y1, col):
    b = [0x23]
    for v in (x0, x1, y0, y1):
        b += [v & 0xFF, v >> 8]
    return b + [col >> 8, col & 0xFF]


def win(reg, a, b):
    return [0x1E, reg, 0x00, 4, a >> 8, a & 0xFF, b >> 8, b & 0xFF]


async def power_up(c, rail):
    # the all-in-one 0x20 rebooted the watch 2/2 within 0.6 s; this is the sequence that survived init, one step at a time
    if rail:
        await step(c, "rail P2_5 soft start (2.5 s ramp)", [0x1B, 21, 1, 250], 6, 1.0)
    await step(c, "SPIC2 setup", [0x1D])
    await step(c, "screen power P0_1", [0x1B, 1, 1, 10], hold=0.5)
    await step(c, "reset P2_0 high", [0x03, 16, 1])
    await asyncio.sleep(0.05)
    await step(c, "reset P2_0 low", [0x03, 16, 0])
    await asyncio.sleep(0.12)
    await step(c, "reset P2_0 high", [0x03, 16, 1])
    await asyncio.sleep(0.05)


async def run(c, rail):
    res = {}
    await power_up(c, rail)
    res["before_init"] = await signals(c, "before init")
    for i, (hi, lo, data) in enumerate(INIT):
        await step(c, f"init {i + 1}/{len(INIT)} reg {hi:02X}{lo:02X}", [0x1E, hi, lo, len(data), *data])
        if hi == 0x11:
            await asyncio.sleep(0.12)
    await asyncio.sleep(0.12)
    await step(c, "display on (stock second 0x29)", [0x1E, 0x29, 0x00, 0])
    await step(c, "brightness low", [0x1E, 0x51, 0x00, 1, 0x10])
    res["after_init"] = await signals(c, "after init")
    await step(c, "paint everything black", fill(0, 367, 0, 447, 0x0000), 30)
    await step(c, "WHITE SQUARE - look now", fill(134, 233, 174, 273, 0xFFFF), 30, 4.0)
    await step(c, "brighter", [0x1E, 0x51, 0x00, 1, 0x60], hold=4.0)
    await step(c, "WHOLE SCREEN RED - look now", fill(0, 367, 0, 447, 0xF800), 30, 6.0)
    await step(c, "one-wire range x", win(0x2A, 134, 233))
    await step(c, "one-wire range y", win(0x2B, 174, 273))
    await step(c, "GREEN SQUARE (slow path) - look now", [0x1F, 0x07, 0xE0, *(100 * 100).to_bytes(4, "little")], 30, 6.0)
    res["end"] = await signals(c, "end")
    return res


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 11:
        raise SystemExit("flash v11 first: bash run.sh ota_flash --go firmware/v11/app_MP.bin")
    up, why = await uptime(c)
    log(f"start: uptime {up} s, last reset: {why}")
    res = {}
    for name, rail in (("no_rail", False), ("rail_soft", True)):
        log(f"=== {name}: WATCH THE SCREEN. Starting in 3 s.")
        beep("found")
        await asyncio.sleep(3)
        t0 = time.time()
        try:
            res[name] = await run(c, rail)
            log(f"{name}: all steps survived ({time.time() - t0:.0f} s)")
        except Dropped as e:
            log(f"!!! DROPPED AT: {e} ({time.time() - t0:.1f} s in)")
            res[name] = {"died_at": str(e)}
            try:
                await c.disconnect()
            except Exception:
                pass
            log(f"hands off - waiting up to {COME_BACK_S} s for the watch to return by itself")
            by_itself = await came_back(COME_BACK_S)
            c = await connect()
            up, why = await uptime(c)
            log(f"came back by itself: {by_itself} | uptime {up} s, last reset: {why}")
            res[name].update(by_itself=by_itself, uptime=up)
    beep("found")
    a = m = ""
    for _ in range(3):
        a = ask("What showed on the SCREEN? (white square / red / green square / flicker / nothing):")
        if a:
            break
    for _ in range(3):
        m = ask("Did the MOTOR buzz during the test? (yes / no):")
        if m:
            break
    save_hw(display_v11={"results": res, "seen": a, "motor": m})
    log("RESULT saw:", a or "(no answer)", "| motor:", m or "(no answer)")
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
